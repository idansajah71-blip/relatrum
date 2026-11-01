"""Pydantic v2 request/response schemas for the RELATRUM API.

Rules:
  * Every persisted response is expressed through read models defined here.
  * Request models validate strictly (extra fields rejected) to catch client
    mistakes early; unknown enum values are hard errors.
  * Timestamps serialize as ISO-8601 UTC strings.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,58}[a-z0-9])?$")

SourceType = Literal[
    "policy", "procedure", "official_requirement", "field_report", "observation",
    "interview", "operational_record", "contextual_document", "counter_evidence", "other",
]
SourceOrigin = Literal[
    "official_document", "first_hand_report", "second_hand_report",
    "internal_record", "user_provided", "unknown",
]
SensitivityLevel = Literal["public", "internal", "confidential"]
AuthorityLabel = Literal[
    "official_document", "first_hand_report", "second_hand_report",
    "internal_record", "user_provided", "unknown",
]
WorkspaceRole = Literal["viewer", "reviewer", "editor", "owner"]
CaseStatus = Literal["open", "in_progress", "monitoring", "closed", "archived"]


# --------------------------------------------------------------------------- auth


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        lowered = v.strip().lower()
        if "@" not in lowered or lowered.startswith("@") or lowered.endswith("@"):
            raise ValueError("Enter a valid email address")
        return lowered


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: "UserRead"


class UserRead(BaseModel):
    id: str
    email: str
    display_name: str
    is_active: bool


# --------------------------------------------------------------------- workspaces


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    slug: str | None = Field(default=None, pattern=_SLUG_RE)

    @field_validator("slug")
    @classmethod
    def _slug_optional(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("Slug may contain lowercase letters, digits, dot, dash, underscore")
        return v


class WorkspaceRead(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    role: WorkspaceRole | None = None
    case_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkspaceMemberAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    role: WorkspaceRole = "viewer"


class WorkspaceMemberRead(BaseModel):
    id: str
    user_id: str
    user_email: str | None = None
    user_display_name: str | None = None
    role: WorkspaceRole
    joined_at: datetime | None = None


# ------------------------------------------------------------------------- cases


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    domain: str | None = Field(default=None, max_length=120)
    scope_definition: str | None = None
    observation_start: str | None = Field(default=None, max_length=64)
    observation_end: str | None = Field(default=None, max_length=64)


class CaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    domain: str | None = Field(default=None, max_length=120)
    scope_definition: str | None = None
    status: CaseStatus | None = None
    observation_start: str | None = Field(default=None, max_length=64)
    observation_end: str | None = Field(default=None, max_length=64)


class CaseRead(BaseModel):
    id: str
    workspace_id: str
    title: str
    description: str | None
    domain: str | None
    scope_definition: str | None
    status: CaseStatus
    observation_start: str | None
    observation_end: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source_count: int | None = None
    statement_count: int | None = None
    finding_count: int | None = None


# ----------------------------------------------------------------------- sources


class SourceCreateMeta(BaseModel):
    """Metadata submitted alongside a file upload or text report."""
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType = "other"
    title: str | None = Field(default=None, max_length=300)
    source_origin: SourceOrigin = "unknown"
    source_author: str | None = Field(default=None, max_length=200)
    authority_label: AuthorityLabel = "unknown"
    sensitivity_level: SensitivityLevel = "internal"
    source_date: str | None = Field(default=None, max_length=64)
    captured_at: str | None = Field(default=None, max_length=64)


class SourceManualText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    meta: SourceCreateMeta = Field(default_factory=lambda: SourceCreateMeta())


class EvidenceSpanRead(BaseModel):
    id: str
    page_number: int | None
    start_char: int
    end_char: int
    exact_quote: str
    paragraph_index: int | None
    section_heading: str | None


class SourceVersionRead(BaseModel):
    id: str
    source_id: str
    version_number: int
    content_sha256: str | None
    extraction_method: str | None
    extraction_status: str
    created_at: datetime | None = None


class SourceRead(BaseModel):
    id: str
    workspace_id: str
    case_id: str
    source_type: str
    title: str
    original_filename: str | None
    mime_type: str | None
    file_size: int | None
    sha256: str | None
    source_origin: str
    source_author: str | None
    authority_label: str | None
    sensitivity_level: str
    source_date: str | None
    captured_at: str | None
    ingestion_status: str
    version_count: int | None = None
    span_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SourceWithText(SourceRead):
    text: str | None = None
    text_truncated: bool = False


AuthResponse.model_rebuild()
