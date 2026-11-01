"""Domain enumerations for RELATRUM.

Every enum is a plain string Enum so values serialize directly into the API and
database while staying explicit and refactor-safe.
"""
from __future__ import annotations

from enum import Enum


class AppEnv(str, Enum):
    development = "development"
    testing = "testing"
    production = "production"


class WorkspaceRole(str, Enum):
    viewer = "viewer"
    reviewer = "reviewer"
    editor = "editor"
    owner = "owner"


class CaseStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    monitoring = "monitoring"
    closed = "closed"
    archived = "archived"


class SourceType(str, Enum):
    policy = "policy"
    procedure = "procedure"
    official_requirement = "official_requirement"
    field_report = "field_report"
    observation = "observation"
    interview = "interview"
    operational_record = "operational_record"
    contextual_document = "contextual_document"
    counter_evidence = "counter_evidence"
    other = "other"


class SourceOrigin(str, Enum):
    official_document = "official_document"
    first_hand_report = "first_hand_report"
    second_hand_report = "second_hand_report"
    internal_record = "internal_record"
    user_provided = "user_provided"
    unknown = "unknown"


class IngestionStatus(str, Enum):
    pending = "pending"
    extracted = "extracted"
    extraction_failed = "extraction_failed"
    duplicate = "duplicate"
    rejected = "rejected"


class ExtractionStatus(str, Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    partial = "partial"


class StatementType(str, Enum):
    requirement = "requirement"
    observation = "observation"
    contextual_claim = "contextual_claim"
    operational_practice = "operational_practice"
    hypothesis = "hypothesis"
    unknown = "unknown"


class Modality(str, Enum):
    mandatory = "mandatory"
    recommended = "recommended"
    conditional = "conditional"
    permissive = "permissive"
    unknown = "unknown"


class EvidenceRole(str, Enum):
    direct_support = "direct_support"
    contextual_support = "contextual_support"
    qualification = "qualification"
    counter_context = "counter_context"


class ReviewStatus(str, Enum):
    draft = "draft"
    confirmed = "confirmed"
    corrected = "corrected"
    rejected = "rejected"


class RelationType(str, Enum):
    semantically_similar = "semantically_similar"
    supports = "supports"
    contradicts = "contradicts"
    refines = "refines"
    supersedes = "supersedes"
    contextualizes = "contextualizes"
    temporally_overlaps = "temporally_overlaps"
    potentially_related = "potentially_related"


class AlignmentType(str, Enum):
    full_match_candidate = "full_match_candidate"
    partial_match_candidate = "partial_match_candidate"
    possible_contradiction = "possible_contradiction"
    temporal_mismatch = "temporal_mismatch"
    insufficient_information = "insufficient_information"
    unrelated = "unrelated"
    uncertain = "uncertain"


class FindingType(str, Enum):
    possible_requirement_deviation = "possible_requirement_deviation"
    missing_observation = "missing_observation"
    unexplained_practice = "unexplained_practice"
    contradictory_reports = "contradictory_reports"
    temporal_divergence = "temporal_divergence"
    repeated_operational_friction = "repeated_operational_friction"
    insufficient_evidence = "insufficient_evidence"
    underspecified_requirement = "underspecified_requirement"


class FindingStatus(str, Enum):
    draft = "draft"
    pending_review = "pending_review"
    accepted = "accepted"
    rejected = "rejected"
    requires_more_evidence = "requires_more_evidence"
    resolved = "resolved"
    superseded = "superseded"


class FindingPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidencePolarity(str, Enum):
    supports = "supports"
    contradicts = "contradicts"
    context = "context"
    unresolved = "unresolved"


class VerificationStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    in_progress = "in_progress"
    evidence_received = "evidence_received"
    completed = "completed"
    dismissed = "dismissed"


class ReviewDecision(str, Enum):
    accept = "accept"
    reject = "reject"
    insufficient_evidence = "insufficient_evidence"
    request_more_information = "request_more_information"
    needs_reanalysis = "needs_reanalysis"


class AnalysisStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AiOperationType(str, Enum):
    extract_statements = "extract_statements"
    classify_alignment = "classify_alignment"
    generate_verification = "generate_verification"


class AuditAction(str, Enum):
    created = "created"
    updated = "updated"
    deleted = "deleted"
    status_changed = "status_changed"
    review_decision = "review_decision"
    analysis_run = "analysis_run"
