"""MockProvider: deterministic, offline statement extraction.

This provider is the default and must be fully honest: it performs LOCAL
rule-based mining (no LLM). Every claim it outputs must exist verbatim in the
source text, and downstream quote verification re-checks this.

Rule families:
  * requirement cues: modal verbs (must/should/shall), 'wajib/harus',
    processing-time patterns;
  * observation cues: first/third-hand reporting ('received', 'took',
    'reported', 'my application');
  * operational practice cues: 'practice', 'we check', internal records;
  * contextual claims: volumes, periods, explanations without modality.
"""
from __future__ import annotations

import re

from app.ai.base import AIProvider, ClassificationResult, ExtractionResult, ExtractedStatement, VerificationSuggestion

_MODAL_RE = re.compile(r"\b(must|shall|required to|harus|wajib)\b", re.IGNORECASE)
_RECOMMEND_RE = re.compile(r"\b(should|sebaiknya)\b", re.IGNORECASE)
_CONDITION_RE = re.compile(r"\b(if|only if|when|whenever|setelah|ketika)\b", re.IGNORECASE)
_OBSERVATION_RE = re.compile(
    r"\b(received|received it|took|reported|reported that|arrived|completed|got|"
    r"dikirim|selesai|diterima finished)\b",
    re.IGNORECASE,
)
_PRACTICE_RE = re.compile(
    r"\b(we (?:check|stamp|process|validate)|practice|normally we|we usually|"
    r"ops record|operational record|volume was)\b",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(r"\b(within\s+\w+(?:\s+\w+)?\s+days?|\d+\s+days?|dua hari kerja)\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2}|"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})\b",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class MockProvider(AIProvider):
    name = "mock"
    model = "deterministic-heuristics-v1"

    async def extract_statements(self, document_text: str, *, context: dict | None = None) -> ExtractionResult:
        statements: list[ExtractedStatement] = []
        paragraphs = _split_paragraphs(document_text)
        for p_index, (paragraph, p_start) in enumerate(paragraphs):
            pending_heading = None
            for sentence, s_start in _sentences(paragraph):
                stripped = sentence.strip()
                if not stripped:
                    continue
                if _is_heading(stripped):
                    pending_heading = stripped[:-1]
                    continue
                s_type = _classify_type(stripped)
                if s_type == "unknown":
                    continue  # semantic noise: skip unclassifiable fragments honestly
                modality = _classify_modality(stripped, s_type)
                duration = _match(_DURATION_RE, stripped)
                observed = _match(_DATE_RE, stripped)
                abs_start = p_start + s_start
                abs_end = abs_start + len(stripped)
                statements.append(
                    ExtractedStatement(
                        statement_type=s_type,
                        original_text=stripped,
                        exact_quote=stripped,
                        paragraph_index=p_index,
                        page_number=None,
                        start_char=abs_start,
                        end_char=abs_end,
                        subject=_guess_subject(stripped),
                        actor=_guess_actor(stripped),
                        action=_guess_action(stripped),
                        condition=_condition_only(stripped),
                        modality=modality,
                        frequency=_frequency(stripped),
                        temporal_valid_from=None,
                        temporal_valid_until=None,
                        observed_at=observed if s_type == "observation" else None,
                        reported_at=observed if s_type == "observation" else None,
                        extraction_confidence=_confidence(s_type, modality, duration is not None),
                    )
                )
        return ExtractionResult(
            statements=statements,
            provider=self.name,
            model=self.model,
            request_status="success",
        )

    async def classify_alignment(self, requirement_text: str, observation_text: str) -> ClassificationResult:
        # Deterministic lexical heuristic; never claims external LLM certainty.
        req = set(_tokens(requirement_text))
        obs = set(_tokens(observation_text))
        overlap = len(req & obs) / max(len(req), 1)
        if _negation_conflict(requirement_text, observation_text):
            alignment_type = "possible_contradiction"
        elif overlap >= 0.6:
            alignment_type = "full_match_candidate"
        elif overlap >= 0.3:
            alignment_type = "partial_match_candidate"
        elif overlap > 0.05:
            alignment_type = "uncertain"
        else:
            alignment_type = "unrelated"
        return ClassificationResult(
            alignment_type=alignment_type,
            explanation=(
                f"Lexical overlap between requirement and observation tokens is "
                f"{overlap:.2f}; classification rule based on thresholded overlap "
                f"and explicit negation conflict detection."
            ),
        )

    async def generate_verification_requests(
        self, finding_context: dict, evidence_texts: list[str]
    ) -> list[VerificationSuggestion]:
        title = finding_context.get("title") or "Unresolved finding"
        unresolved = finding_context.get("unresolved_issue") or (
            "Available evidence does not establish which competing explanation applies."
        )
        return [
            VerificationSuggestion(
                question=(
                    f"Collect submission and completion timestamps for a defined sample of affected "
                    f"applications related to: {title}, including whether each submission was complete "
                    f"at receipt."
                ),
                unresolved_issue=unresolved,
                missing_information=(
                    "Per-item submission dates, completion dates, and document-completeness status "
                    "are not represented in the current evidence."
                ),
                suggested_evidence_type="operational_record",
                suggested_source="Administrative processing records or equivalent official log",
                expected_answer_structure={
                    "fields": [
                        "application_id",
                        "submission_date",
                        "completion_date",
                        "complete_at_submission",
                        "processing_category",
                    ]
                },
                hypothesis_a=finding_context.get("hypothesis_a") or "Processing is routinely delayed.",
                hypothesis_b=finding_context.get("hypothesis_b") or "Delays concentrate in specific conditions.",
                decision_relevance=(
                    "Timestamps plus completeness status separate systematic delays from "
                    "case-mix explanations."
                ),
                limitations=(
                    "A single sample may not represent all periods; sampling period must be stated and "
                    "results treated as preliminary evidence, not proof."
                ),
            )
        ]


def _split_paragraphs(text: str) -> list[tuple[str, int]]:
    units = []
    cursor = 0
    for raw in text.split("\n\n"):
        stripped = raw.strip()
        if stripped:
            start = text.find(stripped, cursor)
            units.append((stripped, start if start != -1 else cursor))
        cursor += len(raw) + 2
    return units


def _sentences(paragraph: str) -> list[tuple[str, int]]:
    out = []
    cursor = 0
    for raw in _SENTENCE_SPLIT_RE.split(paragraph):
        out.append((raw, cursor))
        cursor += len(raw) + 1
    return out


def _is_heading(sentence: str) -> bool:
    return sentence.endswith(":") and len(sentence.split()) <= 10


def _classify_type(sentence: str) -> str:
    if _MODAL_RE.search(sentence) or _RECOMMEND_RE.search(sentence) and _condition_cue(sentence):
        return "requirement"
    if _PRACTICE_RE.search(sentence):
        return "operational_practice"
    if _OBSERVATION_RE.search(sentence):
        return "observation"
    if _DURATION_RE.search(sentence) or "day" in sentence.lower() and "process" in sentence.lower():
        return "contextual_claim"
    return "unknown"


def _condition_cue(sentence: str) -> bool:
    return bool(_CONDITION_RE.search(sentence))


def _condition_only(sentence: str) -> str | None:
    m = _CONDITION_RE.search(sentence)
    return sentence[m.start():].strip() if m else None


def _classify_modality(sentence: str, s_type: str) -> str:
    if s_type != "requirement":
        return "unknown"
    if _MODAL_RE.search(sentence):
        return "mandatory"
    if _RECOMMEND_RE.search(sentence):
        return "recommended"
    return "unknown"


def _frequency(sentence: str) -> str | None:
    lowered = sentence.lower()
    for cue in ("usually", "normally", "sometimes", "always", "often"):
        if cue in lowered:
            return cue
    return None


def _guess_subject(sentence: str) -> str | None:
    m = re.search(
        r"\b(applications?|certificates?|documents?|submissions?|reports?|records?|requests?)\b",
        sentence,
        re.IGNORECASE,
    )
    return m.group(0).lower() if m else None


def _guess_actor(sentence: str) -> str | None:
    m = re.search(
        r"\b(administrative office|school|staff|team|applicant|student|system|office)\b",
        sentence,
        re.IGNORECASE,
    )
    return m.group(0).lower() if m else None


def _guess_action(sentence: str) -> str | None:
    m = re.search(
        r"\b(process(?:ed|es|ing)?|received?|submitted?|checked?|completed?|stamped?|validated?)\b",
        sentence,
        re.IGNORECASE,
    )
    return m.group(0).lower() if m else None


def _confidence(s_type: str, modality: str | None, has_duration: bool) -> float:
    score = 0.5
    if s_type == "requirement" and modality in ("mandatory", "recommended"):
        score += 0.2
    if s_type == "observation":
        score += 0.15
    if has_duration:
        score += 0.1
    return round(score, 2)


def _match(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    return m.group(0) if m else None


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 2]


def _negation_conflict(requirement: str, observation: str) -> bool:
    req_days = _match(_DURATION_RE, requirement)
    obs_days = _match(_DURATION_RE, observation)
    if not (req_days and obs_days):
        return False
    return _days(req_days) * 2 < _days(obs_days)


def _days(text: str) -> float:
    m = re.search(r"(\d+|\w+)", text.lower().replace("within", "").strip())
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "ten": 10, "dua": 2,
    }
    if m:
        token = m.group(1)
        if token.isdigit():
            return float(token)
        return float(word_map.get(token, 1))
    return 1.0
