"""Divergence detector: turns alignment results into candidate findings.

Pure function over already-persisted alignment/statement data. No DB writes;
the findings service persists and deduplicates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.services.alignment.retrieval import content_stems

_TIME_STEMS = {"day", "days", "week", "weeks", "month", "months", "year", "years", "hour", "hours", "time", "date", "period"}


@dataclass
class FindingCandidate:
    finding_type: str
    title: str
    summary: str
    detailed_explanation: str
    involved_statement_ids: list[str]
    involved_alignment_ids: list[str] = field(default_factory=list)
    polarity_map: dict[str, str] = field(default_factory=dict)  # statement_id -> polarity
    temporal_context: str | None = None
    unresolved_assumptions: list[str] = field(default_factory=list)
    suggested_verification: str = ""


def _topic(statement) -> set[str]:
    return content_stems(statement.normalized_text or statement.original_text or "") - _TIME_STEMS


def detect_findings(
    *,
    case_id: str,
    statements: list,
    alignments: list,
    superseded_ids: set[str],
    has_observations: bool,
) -> list[FindingCandidate]:
    out: list[FindingCandidate] = []
    stmt_by_id = {s.id: s for s in statements}
    reqs = [s for s in statements if s.statement_type == "requirement"]
    obs_all = [s for s in statements if s.statement_type != "requirement"]

    # A/E: possible deviation + temporal divergence from alignment rows.
    for a in alignments:
        at = a.alignment_type
        if at == "possible_contradiction":
            out.append(FindingCandidate(
                finding_type="possible_requirement_deviation",
                title="Possible requirement deviation",
                summary="An observation appears inconsistent with an applicable requirement.",
                detailed_explanation=(
                    "A requirement and an observation are lexically close but the observation "
                    "states a condition that conflicts with the requirement's bound or negation. "
                    "This is a candidate for review, not a confirmed violation."
                ),
                involved_statement_ids=[a.requirement_statement_id, a.observation_statement_id],
                involved_alignment_ids=[a.id],
                polarity_map={
                    a.requirement_statement_id: "context",
                    a.observation_statement_id: "supports",
                },
                temporal_context=a.temporal_compatibility,
                unresolved_assumptions=[
                    "The statements may describe different cases or conditions.",
                    "Temporal applicability is based on available dates only.",
                ],
                suggested_verification=(
                    "Collect the underlying records (timestamps, document completeness) for the "
                    "affected applications to distinguish systematic delay from case-mix effects."
                ),
            ))
        elif at == "temporal_mismatch":
            out.append(FindingCandidate(
                finding_type="temporal_divergence",
                title="Temporal divergence",
                summary="An observation may relate to a different requirement version or time window.",
                detailed_explanation=(
                    "The observation is lexically similar to a requirement but falls outside that "
                    "requirement's stated validity window. It may concern an older or newer version."
                ),
                involved_statement_ids=[a.requirement_statement_id, a.observation_statement_id],
                involved_alignment_ids=[a.id],
                polarity_map={
                    a.requirement_statement_id: "context",
                    a.observation_statement_id: "supports",
                },
                temporal_context=a.temporal_compatibility,
                unresolved_assumptions=[
                    "The requirement's effective dates may be incomplete.",
                    "The observation date may be approximate.",
                ],
                suggested_verification="Confirm which requirement version was in force on the observation date.",
            ))

    # B: missing observation (requirements with no resolvable alignment).
    resolvable_reqs = {a.requirement_statement_id for a in alignments if a.alignment_type in (
        "full_match_candidate", "partial_match_candidate", "possible_contradiction", "temporal_mismatch",
    )}
    for r in reqs:
        if r.id not in resolvable_reqs:
            out.append(FindingCandidate(
                finding_type="missing_observation",
                title="Missing observation evidence",
                summary="No observational evidence currently maps to this requirement.",
                detailed_explanation=(
                    "The system lacks sufficient observational evidence to assess whether this "
                    "requirement is met in practice. Absence of evidence is not evidence of "
                    "non-compliance."
                ),
                involved_statement_ids=[r.id],
                polarity_map={r.id: "supports"},
                unresolved_assumptions=[
                    "Observations may exist in sources not yet ingested.",
                    "The requirement may be too new to have observations.",
                ],
                suggested_verification="Ingest additional reports or operational records covering this requirement.",
            ))

    # C: unexplained practice.
    resolvable_obs = {a.observation_statement_id for a in alignments if a.alignment_type in (
        "full_match_candidate", "partial_match_candidate", "possible_contradiction", "temporal_mismatch",
    )}
    for o in statements:
        if o.statement_type == "operational_practice" and o.id not in resolvable_obs:
            out.append(FindingCandidate(
                finding_type="unexplained_practice",
                title="Unexplained operational practice",
                summary="An observed practice cannot be mapped to an available requirement.",
                detailed_explanation=(
                    "The practice is reported in source material but no requirement explains or "
                    "authorises it. It may be an undocumented procedure, a gap in policy, or noise."
                ),
                involved_statement_ids=[o.id],
                polarity_map={o.id: "supports"},
                unresolved_assumptions=[
                    "The practice may be authorised by a requirement not yet ingested.",
                    "The extraction may have misclassified the statement.",
                ],
                suggested_verification="Locate the policy or procedure that authorises this practice.",
            ))

    # D: contradictory reports among observations.
    obs_list = [s for s in statements if s.statement_type in ("observation", "operational_practice")]
    neg_re = None
    import re
    neg_re = re.compile(r"\b(must not|shall not|cannot|can not|may not|not allowed|not be counted|prohibited|forbidden|waived|suspended|discontinued|no longer)\b", re.IGNORECASE)
    seen_pairs: set[tuple[str, str]] = set()
    for i in range(len(obs_list)):
        for j in range(i + 1, len(obs_list)):
            a, b = obs_list[i], obs_list[j]
            if not (_topic(a) & _topic(b)):
                continue
            a_neg = bool(neg_re.search(a.original_text or ""))
            b_neg = bool(neg_re.search(b.original_text or ""))
            if a_neg == b_neg:
                continue
            key = tuple(sorted((a.id, b.id)))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            out.append(FindingCandidate(
                finding_type="contradictory_reports",
                title="Contradictory reports",
                summary="Two reports describe incompatible operational conditions.",
                detailed_explanation=(
                    "Both reports are about the same topic but one explicitly negates what the other "
                    "affirms. The evidence conflicts and neither side should be discarded."
                ),
                involved_statement_ids=[a.id, b.id],
                polarity_map={a.id: "supports", b.id: "contradicts"},
                unresolved_assumptions=[
                    "The reports may refer to different time periods or cases.",
                ],
                suggested_verification="Collect timestamps and case identifiers for both reports.",
            ))

    # F: repeated operational friction.
    from collections import defaultdict
    by_req: dict[str, list[str]] = defaultdict(list)
    for a in alignments:
        if a.alignment_type in ("partial_match_candidate", "possible_contradiction"):
            by_req[a.requirement_statement_id].append(a.observation_statement_id)
    for req_id, obs_ids in by_req.items():
        distinct = sorted(set(obs_ids))
        if len(distinct) >= 2:
            out.append(FindingCandidate(
                finding_type="repeated_operational_friction",
                title="Repeated operational friction",
                summary="Multiple observations point to the same operational difficulty.",
                detailed_explanation=(
                    f"{len(distinct)} distinct observations align (partially or contradictorily) to "
                    "the same requirement, suggesting a recurring operational issue rather than an "
                    "isolated case."
                ),
                involved_statement_ids=[req_id] + distinct,
                involved_alignment_ids=[a.id for a in alignments if a.requirement_statement_id == req_id],
                polarity_map={req_id: "context", **{oid: "supports" for oid in distinct}},
                unresolved_assumptions=[
                    "The observations may share a common underlying cause not yet identified.",
                ],
                suggested_verification="Sample the affected cases to separate systematic from case-mix effects.",
            ))

    # G: insufficient evidence.
    if not has_observations or not any(
        a.alignment_type in ("full_match_candidate", "partial_match_candidate", "possible_contradiction", "temporal_mismatch")
        for a in alignments
    ):
        out.append(FindingCandidate(
            finding_type="insufficient_evidence",
            title="Insufficient evidence",
            summary="Available sources cannot yet support a reliable finding.",
            detailed_explanation=(
                "Either no observations were ingested or no alignment could be established. "
                "No conclusion about compliance should be drawn."
            ),
            involved_statement_ids=[s.id for s in reqs] if reqs else [s.id for s in statements],
            polarity_map={s.id: "unresolved" for s in (reqs if reqs else statements)},
            unresolved_assumptions=[
                "More evidence may exist in uningested sources.",
            ],
            suggested_verification="Ingest additional reports or operational records.",
        ))

    return out
