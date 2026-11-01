"""Alignment analysis orchestration (Phase 5).

Creates one reproducible AnalysisRun per invocation and persists the complete
deterministic alignment picture:

  * candidate retrieval (TF-IDF + fuzzy) over requirement/observation pairs;
  * rule-based classification per pair (see services.alignment.engine);
  * temporal applicability per pair;
  * supersession relations between requirement statements;
  * case-level absence categories (missing_observation, unexplained_practice)
    recorded as run metadata - absence is never persisted as a fabricated
    alignment row.

Determinism: identical case data + identical settings produce identical
alignment rows (the manifest hash is deliberately included in run metadata to
prove it).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.ai.prompts import PROMPT_VERSION
from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.permissions import require_workspace_member
from app.database import utcnow
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.statement import Statement, StatementRelation
from app.models.user import User
from app.services import audit
from app.services.alignment import (
    PARTIAL_THRESHOLD,
    FULL_THRESHOLD,
    classify_candidates,
    retrieve_candidates,
)
from app.services.temporal.reasoning import supersession_pairs

ANALYSIS_PIPELINE_VERSION = "1.0.0"
ALIGNMENT_RULE_VERSION = "alignment-rules-1.0"

RETRIEVAL_FLOOR = 0.10
RETRIEVAL_TOP_K = 20

# Every non-requirement statement category is a possible counterpart observed
# from practice or reporting; requirements align against all of them.
COUNTERPART_TYPES = (
    "observation",
    "operational_practice",
    "contextual_claim",
    "hypothesis",
    "unknown",
)

_PROVIDER_TYPE_MAP = {
    "full_match_candidate": "full_match",
    "partial_match_candidate": "partial_match",
    "possible_contradiction": "contradiction",
    "unrelated": "unrelated",
    "uncertain": None,  # provider is unsure: keep the deterministic verdict
}


@dataclass
class AlignmentAnalysisReport:
    analysis_run_id: str
    status: str
    provider: str
    manifest_hash: str
    candidates_evaluated: int = 0
    type_counts: dict = field(default_factory=dict)
    missing_observation_ids: list[str] = field(default_factory=list)
    unexplained_practice_ids: list[str] = field(default_factory=list)
    superseded_requirement_ids: list[str] = field(default_factory=list)
    persisted_alignments: int = 0


async def run_alignment_analysis(db: Session, case_id: str, user_id: str) -> AlignmentAnalysisReport:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role="editor")

    statements = (
        db.query(Statement)
        .filter(Statement.case_id == case.id)
        .order_by(Statement.created_at.asc())
        .all()
    )
    requirements = [s for s in statements if s.statement_type == "requirement"]
    counterparts = [s for s in statements if s.statement_type in COUNTERPART_TYPES]
    if not requirements:
        raise ValidationFailedError(
            "Case has no requirement statements to align; run statement extraction first."
        )

    settings = get_settings()
    from app.ai.registry import build_provider

    provider = build_provider()
    started_at = utcnow().isoformat()
    run = AnalysisRun(
        case_id=case.id,
        status="running",
        pipeline_version=ANALYSIS_PIPELINE_VERSION,
        prompt_version=ALIGNMENT_RULE_VERSION,
        provider_name=provider.name,
        model_name=provider.model,
        started_at=started_at,
        execution_metadata={"note": "alignment analysis"},
    )
    db.add(run)
    db.flush()

    manifest_hash = _compute_manifest_hash(requirements, counterparts, provider.name)
    run.input_manifest_hash = manifest_hash

    candidates = retrieve_candidates(
        requirements,
        counterparts,
        min_similarity=RETRIEVAL_FLOOR,
        top_k=RETRIEVAL_TOP_K,
    )
    decisions = classify_candidates(candidates)

    decisions = await _maybe_refine_with_provider(db, run, decisions, provider, settings, manifest_hash)

    persisted = _persist_alignments(db, run, decisions)
    superseded_ids = _persist_supersessions(db, run, requirements)

    # Phase 6: build finding dossiers from this run's alignments.
    from app.services import findings as findings_service

    findings_service.generate_findings(
        db, case_id=case.id, analysis_run_id=run.id, user_id=user.id
    )

    missing_ids = [r.id for r in requirements if not any(
        d.requirement.id == r.id and d.resolvable for d in decisions
    )]
    covered_obs = {d.observation.id for d in decisions if d.resolvable}
    unexplained_ids = [
        o.id for o in counterparts if o.statement_type == "operational_practice" and o.id not in covered_obs
    ]

    type_counts: dict[str, int] = {}
    for d in decisions:
        type_counts[d.alignment_type] = type_counts.get(d.alignment_type, 0) + 1

    run.status = "completed"
    run.completed_at = utcnow().isoformat()
    run.execution_metadata = {
        **(run.execution_metadata or {}),
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "thresholds": {"full": FULL_THRESHOLD, "partial": PARTIAL_THRESHOLD},
        "retrieval": {"floor": RETRIEVAL_FLOOR, "top_k": RETRIEVAL_TOP_K},
        "candidates_evaluated": len(candidates),
        "alignment_type_counts": type_counts,
        "missing_observation_ids": missing_ids,
        "unexplained_practice_ids": unexplained_ids,
        "superseded_requirement_ids": superseded_ids,
        "classification_provenance": "deterministic_rules" if provider.name == "mock" else "provider_refined",
        "input_manifest_hash": manifest_hash,
    }
    report = AlignmentAnalysisReport(
        analysis_run_id=run.id,
        status=run.status,
        provider=provider.name,
        manifest_hash=manifest_hash,
        candidates_evaluated=len(candidates),
        type_counts=type_counts,
        missing_observation_ids=missing_ids,
        unexplained_practice_ids=unexplained_ids,
        superseded_requirement_ids=superseded_ids,
        persisted_alignments=persisted,
    )

    audit.record_event(
        db,
        workspace_id=case.workspace_id,
        actor_id=user.id,
        entity_type="analysis_run",
        entity_id=run.id,
        action="analysis_run",
        after_state={"type": "alignment_analysis", "alignments": persisted},
    )
    db.commit()
    return report


# ---------------------------------------------------------------------------
# helpers


def _compute_manifest_hash(requirements: list[Statement], counterparts: list[Statement], provider_name: str) -> str:
    """Hash of the exact input corpus + engine identity -> reproducibility proof."""
    from app.utils.hashing import sha256_text

    def _dump(items: list[Statement]) -> list[dict]:
        return [
            {
                "id": s.id,
                "type": s.statement_type,
                "text": s.normalized_text or s.original_text,
                "valid_from": s.temporal_valid_from,
                "valid_until": s.temporal_valid_until,
                "observed_at": s.observed_at,
                "reported_at": s.reported_at,
                "modality": s.modality,
            }
            for s in sorted(items, key=lambda s: s.id)
        ]

    payload = {
        "engine": ALIGNMENT_RULE_VERSION,
        "thresholds": {"full": FULL_THRESHOLD, "partial": PARTIAL_THRESHOLD},
        "provider": provider_name,
        "requirements": _dump(requirements),
        "counterparts": _dump(counterparts),
    }
    return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


async def _maybe_refine_with_provider(
    db: Session, run: AnalysisRun, decisions, provider, settings, manifest_hash: str
):
    """Optionally re-classify pairs with the external provider.

    Only active for real AI providers (enable_ai_alignment). The mock provider
    is rule-based already; re-calling it would double-count invocations for no
    informational gain. Decisions are immutable -> returns a new list.
    """
    if not settings.enable_ai_alignment or provider.name == "mock":
        return decisions
    from dataclasses import replace

    from app.ai.usage import record_invocation

    refit: list = []
    changed = 0
    for decision in decisions:
        result = await provider.classify_alignment(
            decision.requirement.normalized_text or decision.requirement.original_text or "",
            decision.observation.normalized_text or decision.observation.original_text or "",
        )
        mapped = _PROVIDER_TYPE_MAP.get(result.alignment_type)
        if mapped and mapped != decision.alignment_type:
            decision = replace(
                decision,
                alignment_type=mapped,
                explanation=(
                    f"Provider ({provider.name}/{provider.model}) classified this pair as "
                    f"{mapped}: {result.explanation}"
                ),
            )
            changed += 1
        refit.append(decision)
    await record_invocation(
        db,
        analysis_run_id=run.id,
        provider=provider.name,
        model=provider.model,
        operation_type="classify_alignment",
        prompt_version=PROMPT_VERSION,
        input_hash=manifest_hash,
        request_status="success",
        token_usage=None,
        latency_ms=None,
        error_code=None,
    )
    run.execution_metadata = {**(run.execution_metadata or {}), "provider_refined_alignments": changed}
    return refit


def _persist_alignments(db: Session, run: AnalysisRun, decisions) -> int:
    from app.models.alignment import Alignment

    persisted = 0
    seen: set[tuple[str, str]] = set()
    for d in decisions:
        key = (d.requirement.id, d.observation.id)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            Alignment(
                case_id=d.requirement.case_id,
                requirement_statement_id=d.requirement.id,
                observation_statement_id=d.observation.id,
                lexical_similarity=d.lexical_similarity,
                semantic_similarity=None,  # no embedding scores in the mock path
                fuzzy_similarity=d.fuzzy_similarity,
                temporal_compatibility=d.temporal_compatibility,
                temporal_detail=d.temporal_detail,
                alignment_type=d.alignment_type,
                explanation=d.explanation,
                candidate_status="candidate",
                analysis_run_id=run.id,
            )
        )
        persisted += 1
    db.flush()
    return persisted


def _persist_supersessions(db: Session, run: AnalysisRun, requirements: list[Statement]) -> list[str]:
    """Persist supersedes relations; returns ids of requirements that were superseded (older)."""
    rows = supersession_pairs(requirements)
    superseded_ids: list[str] = []
    for older_idx, newer_idx, explanation in rows:
        older, newer = requirements[older_idx], requirements[newer_idx]
        if older.id == newer.id:
            continue
        db.add(
            StatementRelation(
                source_statement_id=newer.id,
                target_statement_id=older.id,
                relation_type="supersedes",
                relationship_explanation=explanation,
                created_by_analysis_run=run.id,
            )
        )
        if older.id not in superseded_ids:
            superseded_ids.append(older.id)
    db.flush()
    return superseded_ids
