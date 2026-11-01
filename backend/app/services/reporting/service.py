"""Case reporting: JSON + Markdown export."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.finding import Finding
from app.models.statement import Statement
from app.models.alignment import Alignment
from app.models.verification import VerificationTask
from app.models.analysis_run import AnalysisRun
from app.models.statement import StatementRelation


def _case_overview(db: Session, case: Case) -> dict:
    from sqlalchemy import func, select
    from app.models.source import Source

    source_count = db.scalar(select(func.count(Source.id)).where(Source.case_id == case.id)) or 0
    stmt_count = db.scalar(select(func.count(Statement.id)).where(Statement.case_id == case.id)) or 0
    finding_count = db.scalar(select(func.count(Finding.id)).where(Finding.case_id == case.id)) or 0
    run_count = db.scalar(select(func.count(AnalysisRun.id)).where(AnalysisRun.case_id == case.id)) or 0
    return {
        "case_id": case.id,
        "title": case.title,
        "domain": case.domain,
        "status": case.status,
        "observation_start": case.observation_start,
        "observation_end": case.observation_end,
        "source_count": source_count,
        "statement_count": stmt_count,
        "finding_count": finding_count,
        "analysis_run_count": run_count,
    }


def build_report(db: Session, case_id: str) -> dict:
    from app.core.exceptions import NotFoundError

    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")

    overview = _case_overview(db, case)

    statements = db.query(Statement).filter(Statement.case_id == case.id).all()
    by_type: dict[str, int] = {}
    for s in statements:
        by_type[s.statement_type] = by_type.get(s.statement_type, 0) + 1

    requirements = [s for s in statements if s.statement_type == "requirement"]
    observations = [s for s in statements if s.statement_type != "requirement"]

    # latest run alignments
    latest_run = db.query(AnalysisRun).filter(AnalysisRun.case_id == case.id).order_by(AnalysisRun.started_at.desc()).first()
    alignments = db.query(Alignment).filter(Alignment.case_id == case.id).all()
    if latest_run:
        alignments = [a for a in alignments if a.analysis_run_id == latest_run.id]
    align_counts: dict[str, int] = {}
    for a in alignments:
        align_counts[a.alignment_type] = align_counts.get(a.alignment_type, 0) + 1
    temporal_counts: dict[str, int] = {}
    for a in alignments:
        temporal_counts[a.temporal_compatibility or "unknown"] = temporal_counts.get(a.temporal_compatibility or "unknown", 0) + 1

    supersessions = db.query(StatementRelation).filter(StatementRelation.relation_type == "supersedes").all()
    # filter to case statements
    stmt_ids = {s.id for s in statements}
    supersessions = [r for r in supersessions if r.source_statement_id in stmt_ids]

    findings = db.query(Finding).filter(Finding.case_id == case.id).order_by(Finding.created_at.desc()).all()

    finding_dossiers = []
    for f in findings:
        ev = []
        from app.services.findings.service import get_finding_evidence
        for e in get_finding_evidence(db, f.id):
            ev.append({
                "polarity": e["evidence_polarity"],
                "statement_text": e["statement_text"],
                "exact_quote": e["exact_quote"],
                "source_version_id": e["source_version_id"],
            })
        finding_dossiers.append({
            "id": f.id,
            "finding_code": f.finding_code,
            "finding_type": f.finding_type,
            "title": f.title,
            "status": f.status,
            "priority": f.priority,
            "summary": f.summary,
            "counter_evidence_present": (f.quality_profile or {}).get("counter_evidence_presence", False),
            "evidence": ev,
        })

    # verification queue
    finding_ids = [f.id for f in findings]
    tasks = db.query(VerificationTask).filter(VerificationTask.finding_id.in_(finding_ids)).all() if finding_ids else []

    # reviews
    from app.models.review import Review
    review_count = db.query(Review).filter(Review.finding_id.in_(finding_ids)).count() if finding_ids else 0

    counter_evidence_items = [e for d in finding_dossiers for e in d["evidence"] if e["polarity"] == "contradicts"]

    report = {
        "overview": overview,
        "requirements_summary": {
            "count": len(requirements),
            "items": [{"id": s.id, "text": s.original_text, "modality": s.modality} for s in requirements],
        },
        "observation_coverage": {
            "statement_counts_by_type": by_type,
            "observation_count": len(observations),
            "alignment_counts": align_counts,
            "temporal_compatibility_counts": temporal_counts,
        },
        "potential_divergences": [
            {"id": f.id, "finding_code": f.finding_code, "type": f.finding_type, "title": f.title,
             "priority": f.priority, "status": f.status, "summary": f.summary}
            for f in findings if f.status != "superseded"
        ],
        "evidence_dossiers": finding_dossiers,
        "counter_evidence_summary": {
            "findings_with_counter_evidence": sum(1 for d in finding_dossiers if d["counter_evidence_present"]),
            "counter_evidence_items": counter_evidence_items,
        },
        "temporal_analysis": {
            "compatibility_counts": temporal_counts,
            "supersession_relations": [
                {"source_statement_id": r.source_statement_id, "target_statement_id": r.target_statement_id,
                 "explanation": r.relationship_explanation}
                for r in supersessions
            ],
        },
        "verification_queue": [
            {"task_id": t.id, "finding_id": t.finding_id, "question": t.question, "status": t.status, "priority": t.priority}
            for t in tasks
        ],
        "review_status": {
            "findings_total": len(findings),
            "review_actions": review_count,
            "by_status": {},
        },
        "methodology_and_limitations": {
            "provider_mode": "deterministic_mock",
            "classification": "Rule-based deterministic alignment (TF-IDF + fuzzy + temporal rules).",
            "limitations": [
                "Findings are candidates requiring human review, not proven violations.",
                "Absence of evidence is not evidence of non-compliance.",
                "Temporal unknowns are represented as unknown, never invented.",
                "MRE suggestions are templates, not statistically optimized.",
            ],
        },
    }
    # by_status
    by_status: dict[str, int] = {}
    for f in findings:
        by_status[f.status] = by_status.get(f.status, 0) + 1
    report["review_status"]["by_status"] = by_status

    # markdown
    md = _to_markdown(case, report)
    report["markdown"] = md
    return report


def _to_markdown(case, report) -> str:
    lines = []
    lines.append(f"# RELATRUM Evidence Report — {case.title}")
    lines.append("")
    lines.append(f"- Domain: {case.domain}")
    lines.append(f"- Status: {case.status}")
    lines.append(f"- Sources: {report['overview']['source_count']}")
    lines.append(f"- Statements: {report['overview']['statement_count']}")
    lines.append(f"- Findings: {report['overview']['finding_count']}")
    lines.append("")
    lines.append("## Requirements Summary")
    for r in report["requirements_summary"]["items"]:
        lines.append(f"- ({r['modality']}) {r['text']}")
    lines.append("")
    lines.append("## Observation Coverage")
    lines.append(f"- Statement counts: {report['observation_coverage']['statement_counts_by_type']}")
    lines.append(f"- Alignments: {report['observation_coverage']['alignment_counts']}")
    lines.append(f"- Temporal: {report['observation_coverage']['temporal_compatibility_counts']}")
    lines.append("")
    lines.append("## Potential Divergences")
    for d in report["potential_divergences"]:
        lines.append(f"- [{d['priority']}] {d['title']} ({d['type']}) — {d['summary']}")
    lines.append("")
    lines.append("## Evidence Dossiers")
    for d in report["evidence_dossiers"]:
        lines.append(f"### {d['title']} ({d['finding_code']})")
        lines.append(f"Status: {d['status']} | Priority: {d['priority']}")
        lines.append(d["summary"] or "")
        for e in d["evidence"]:
            lines.append(f"- ({e['polarity']}) {e['statement_text']}")
            if e["exact_quote"]:
                lines.append(f"  > {e['exact_quote']}")
        lines.append("")
    lines.append("## Counter-Evidence Summary")
    lines.append(f"Findings with counter-evidence: {report['counter_evidence_summary']['findings_with_counter_evidence']}")
    lines.append("")
    lines.append("## Temporal Analysis")
    lines.append(f"Compatibility: {report['temporal_analysis']['compatibility_counts']}")
    for r in report["temporal_analysis"]["supersession_relations"]:
        lines.append(f"- Supersedes: {r['source_statement_id']} -> {r['target_statement_id']}: {r['explanation']}")
    lines.append("")
    lines.append("## Verification Queue")
    for v in report["verification_queue"]:
        lines.append(f"- [{v['status']}] {v['question']}")
    lines.append("")
    lines.append("## Review Status")
    lines.append(f"By status: {report['review_status']['by_status']}")
    lines.append(f"Review actions: {report['review_status']['review_actions']}")
    lines.append("")
    lines.append("## Methodology and Limitations")
    for l in report["methodology_and_limitations"]["limitations"]:
        lines.append(f"- {l}")
    lines.append("")
    lines.append("_Generated by RELATRUM. Findings are candidates requiring human review._")
    return "\n".join(lines)
