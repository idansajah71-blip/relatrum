"""Evidence graph data for a case."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.finding import Finding
from app.models.statement import Statement
from app.models.alignment import Alignment
from app.models.verification import VerificationTask


def build_graph(db: Session, case_id: str) -> dict:
    case = db.get(Case, case_id)
    if case is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Case {case_id} not found.")

    statements = db.query(Statement).filter(Statement.case_id == case.id).all()
    alignments = db.query(Alignment).filter(Alignment.case_id == case.id).all()
    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    finding_ids = [f.id for f in findings]
    tasks = db.query(VerificationTask).filter(VerificationTask.finding_id.in_(finding_ids)).all() if finding_ids else []

    nodes = []
    edges = []

    for s in statements:
        nodes.append({"id": f"stmt:{s.id}", "type": "statement", "label": s.statement_type, "data": {"text": s.original_text}})

    for a in alignments:
        edges.append({"id": f"align:{a.id}", "source": f"stmt:{a.requirement_statement_id}", "target": f"stmt:{a.observation_statement_id}", "type": a.alignment_type, "label": a.alignment_type})

    for f in findings:
        nodes.append({"id": f"finding:{f.id}", "type": "finding", "label": f.finding_type, "data": {"title": f.title, "status": f.status}})
        # link finding to involved statements via evidence
        from app.services.findings.service import get_finding_evidence
        for e in get_finding_evidence(db, f.id):
            if e.get("statement_id"):
                edges.append({"id": f"fe:{e['id']}", "source": f"stmt:{e['statement_id']}", "target": f"finding:{f.id}", "type": e["evidence_polarity"], "label": e["evidence_polarity"]})

    for t in tasks:
        nodes.append({"id": f"task:{t.id}", "type": "verification", "label": "verification", "data": {"question": t.question, "status": t.status}})
        edges.append({"id": f"ft:{t.id}", "source": f"finding:{t.finding_id}", "target": f"task:{t.id}", "type": "requires", "label": "requires"})

    return {"nodes": nodes, "edges": edges}
