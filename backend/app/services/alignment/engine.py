"""Deterministic alignment classification engine.

Classifies (requirement, observation) candidate pairs into explicit, auditable
types. This engine is deliberately rule-based: every decision names the rule
and the measured quantities that produced it. No outcome is hardcoded per
case - the same rules apply to whichever data flows through.

Decision order (first hit wins):
  1. contradiction       - requirement states a measurable bound and the
                           observation states it was clearly breached
                           (duration beyond the stated maximum, or an explicit
                           prohibition contradicted by a similar affirmative);
  2. temporal_mismatch   - temporal judgement is INCOMPATIBLE on a strong
                           candidate (observation happened outside the
                           requirement's applicability window);
  3. full_match            - combined similarity >= FULL_THRESHOLD;
  4. partial_match         - combined similarity >= PARTIAL_THRESHOLD;
  5. insufficient_info     - similarity below the partial floor AND either
                           statement carries too little content to interpret;
  6. unrelated             - above the retrieval floor but lexically weak.

Case-level categories are computed downstream in
app.services.orchestration.analysis_service: requirements with no counterpart
become missing_observation, and operational_practice statements whose
behaviour nothing explains become unexplained_practice. They are reported as
run metadata rather than fabricated alignment rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.alignment._types import Candidate
from app.services.alignment.retrieval import content_stems
from app.services.temporal.reasoning import (
    extract_duration_days,
    extract_elapsed_days,
    classify_temporal_pair,
)

FULL_THRESHOLD = 0.80
PARTIAL_THRESHOLD = 0.40

ALIGNED_TYPES = ("full_match_candidate", "partial_match_candidate")
RESOLVABLE_TYPES = ("full_match_candidate", "partial_match_candidate", "possible_contradiction", "temporal_mismatch")

_NEGATION_RE = re.compile(
    r"\b(must not|shall not|cannot|can not|may not|not allowed|not be counted|"
    r"prohibited|forbidden|waived|suspended|discontinued|no longer)\b",
    re.IGNORECASE,
)

_TIME_TOPIC_STEMS = {"day", "days", "week", "weeks", "month", "months", "year", "years", "hour", "hours", "time", "date", "period"}

_MIN_CONTENT_TOKENS = 4


@dataclass(frozen=True)
class AlignmentDecision:
    requirement: object
    observation: object
    alignment_type: str
    lexical_similarity: float
    fuzzy_similarity: float
    combined_similarity: float
    temporal_compatibility: str
    temporal_detail: dict
    explanation: str

    @property
    def resolvable(self) -> bool:
        """Pair establishes something concrete about the requirement."""
        return self.alignment_type in RESOLVABLE_TYPES


def classify_candidates(
    candidates: list[Candidate],
    *,
    full_threshold: float = FULL_THRESHOLD,
    partial_threshold: float = PARTIAL_THRESHOLD,
) -> list[AlignmentDecision]:
    return [
        classify_candidate(c, full_threshold=full_threshold, partial_threshold=partial_threshold)
        for c in candidates
    ]


def classify_candidate(
    candidate: Candidate,
    *,
    full_threshold: float = FULL_THRESHOLD,
    partial_threshold: float = PARTIAL_THRESHOLD,
) -> AlignmentDecision:
    req, obs = candidate.requirement, candidate.observation
    req_text = req.normalized_text or req.original_text or ""
    obs_text = obs.normalized_text or obs.original_text or ""
    lexical = candidate.lexical_similarity
    fuzzy = candidate.fuzzy_similarity
    combined = candidate.combined_similarity or max(lexical, lexical * 0.7 + fuzzy * 0.3)

    temporal = classify_temporal_pair(req, obs)
    temporal_detail = {"detail": temporal.detail}

    duration_violation = _duration_conflict(req_text, obs_text)
    strong_pair = combined >= partial_threshold
    negation_conflict = strong_pair and _negation_conflict(req_text, obs_text)
    req_topic = content_stems(req_text) - _TIME_TOPIC_STEMS
    obs_topic = content_stems(obs_text) - _TIME_TOPIC_STEMS
    shared_topic = bool(req_topic & obs_topic)

    if duration_violation and (strong_pair or shared_topic):
        return _decision(
            candidate, "possible_contradiction", combined, lexical, fuzzy, temporal, temporal_detail,
            full_threshold, partial_threshold,
            reason=(
                f"Requirement states a processing bound that the observation's stated "
                f"elapsed duration exceeds ({duration_violation})."
            ),
            extra={
                "duration_requirement_max_days": _req_duration(req_text),
                "duration_observed_days": _obs_elapsed(obs_text),
            },
        )
    if negation_conflict:
        return _decision(
            candidate, "possible_contradiction", combined, lexical, fuzzy, temporal, temporal_detail,
            full_threshold, partial_threshold,
            reason=(
                "Statements are lexically close but one explicitly negates or forbids "
                "what the other affirms (rule-based negation detection)."
            ),
        )
    if temporal.compatibility == "incompatible" and combined >= partial_threshold:
        return _decision(
            candidate, "temporal_mismatch", combined, lexical, fuzzy, temporal, temporal_detail,
            full_threshold, partial_threshold,
            reason=f"Lexically similar pair is not temporally applicable: {temporal.detail}",
        )
    if combined >= full_threshold:
        return _decision(
            candidate, "full_match_candidate", combined, lexical, fuzzy, temporal, temporal_detail,
            full_threshold, partial_threshold,
            reason=(
                f"Combined similarity {combined:.2f} meets the full-match threshold "
                f"({full_threshold:.2f}); temporal judgement: {temporal.compatibility}."
            ),
        )
    if combined >= partial_threshold:
        return _decision(
            candidate, "partial_match_candidate", combined, lexical, fuzzy, temporal, temporal_detail,
            full_threshold, partial_threshold,
            reason=(
                f"Combined similarity {combined:.2f} sits between the partial "
                f"({partial_threshold:.2f}) and full ({full_threshold:.2f}) thresholds; "
                "manual confirmation of intent is required before treating it as a full match."
            ),
        )
    if _thin_content(req_text) or _thin_content(obs_text):
        return _decision(
            candidate, "insufficient_information", combined, lexical, fuzzy, temporal, temporal_detail,
            full_threshold, partial_threshold,
            reason=(
                f"Similarity {combined:.2f} is below the partial threshold and one or "
                f"both statements carry too little content for a meaningful ruling."
            ),
        )
    if shared_topic:
        return _decision(
            candidate, "uncertain", combined, lexical, fuzzy, temporal, temporal_detail,
            full_threshold, partial_threshold,
            reason=(
                f"Combined similarity {combined:.2f} is below the partial threshold but the "
                "statements share a topic; relationship cannot be ruled in or out."
            ),
        )
    return _decision(
        candidate, "unrelated", combined, lexical, fuzzy, temporal, temporal_detail,
        full_threshold, partial_threshold,
        reason=(
            f"Combined similarity {combined:.2f} is below the partial threshold "
            f"({partial_threshold:.2f}) with no shared topic."
        ),
    )


# ---------------------------------------------------------------------------
# helpers


def _duration_conflict(req_text: str, obs_text: str) -> str | None:
    req_max = extract_duration_days(req_text)
    obs_elapsed = extract_elapsed_days(obs_text)
    if req_max is None or obs_elapsed is None:
        return None
    if obs_elapsed > req_max:
        return f"max {req_max:g}d vs observed {obs_elapsed:g}d"
    return None


def _req_duration(req_text: str) -> float | None:
    return extract_duration_days(req_text)


def _obs_elapsed(obs_text: str) -> float | None:
    return extract_elapsed_days(obs_text)


def _negation_conflict(req_text: str, obs_text: str) -> bool:
    req_negated = bool(_NEGATION_RE.search(req_text))
    obs_negated = bool(_NEGATION_RE.search(obs_text))
    return req_negated != obs_negated


def _thin_content(text: str) -> bool:
    tokens = [t for t in re.split(r"\W+", text.lower()) if len(t) > 1]
    return len(tokens) < _MIN_CONTENT_TOKENS


def _decision(
    candidate: Candidate,
    alignment_type: str,
    combined: float,
    lexical: float,
    fuzzy: float,
    temporal,
    temporal_detail: dict,
    full_threshold: float,
    partial_threshold: float,
    *,
    reason: str,
    extra: dict | None = None,
) -> AlignmentDecision:
    detail = dict(temporal_detail)
    if extra:
        detail.update(extra)
    explanation = (
        f"{reason} Measured: lexical={lexical:.4f}, fuzzy={fuzzy:.4f}, combined={combined:.4f}; "
        f"thresholds full>{full_threshold:.2f}, partial>{partial_threshold:.2f}. "
        "Deterministic rule-based classification; no AI claim involved."
    )
    return AlignmentDecision(
        requirement=candidate.requirement,
        observation=candidate.observation,
        alignment_type=alignment_type,
        lexical_similarity=round(lexical, 4),
        fuzzy_similarity=round(fuzzy, 4),
        combined_similarity=round(combined, 4),
        temporal_compatibility=temporal.compatibility,
        temporal_detail=detail,
        explanation=explanation,
    )
