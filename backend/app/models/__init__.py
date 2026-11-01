"""Model registry: importing this package registers all ORM tables.

Alembic and `create_all` must import this module for `Base.metadata` to be
complete. Adding a new model file requires adding it here once.
"""
from app.models.user import User  # noqa: F401
from app.models.workspace import Workspace, WorkspaceMember  # noqa: F401
from app.models.case import Case  # noqa: F401
from app.models.source import Source, SourceVersion  # noqa: F401
from app.models.evidence import EvidenceSpan  # noqa: F401
from app.models.statement import Statement, StatementEvidence, StatementRelation  # noqa: F401
from app.models.alignment import Alignment  # noqa: F401
from app.models.finding import Finding, FindingEvidence  # noqa: F401
from app.models.verification import VerificationTask, VerificationResponse  # noqa: F401
from app.models.review import Review  # noqa: F401
from app.models.analysis_run import AnalysisRun, AiInvocation  # noqa: F401
from app.models.audit import AuditEvent  # noqa: F401

__all__ = [
    "User", "Workspace", "WorkspaceMember", "Case", "Source", "SourceVersion",
    "EvidenceSpan", "Statement", "StatementEvidence", "StatementRelation",
    "Alignment", "Finding", "FindingEvidence", "VerificationTask",
    "VerificationResponse", "Review", "AnalysisRun", "AiInvocation", "AuditEvent",
]
