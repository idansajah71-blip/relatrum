"""Provider contract and structured output schemas.

Every provider returns provider-agnostic Pydantic models. Quote verification,
modality mapping, and persistence remain outside providers so behavior is
identical regardless of the underlying model (mock / gemini / groq).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field


class ExtractedStatement(BaseModel):
    statement_type: str = Field(
        pattern="^(requirement|observation|contextual_claim|operational_practice|hypothesis|unknown)$"
    )
    original_text: str
    subject: str | None = None
    actor: str | None = None
    action: str | None = None
    object: str | None = None
    condition: str | None = None
    modality: str | None = Field(default=None, pattern="^(mandatory|recommended|conditional|permissive|unknown)$")
    frequency: str | None = None
    temporal_valid_from: str | None = None
    temporal_valid_until: str | None = None
    observed_at: str | None = None
    reported_at: str | None = None
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    exact_quote: str
    page_number: int | None = None
    paragraph_index: int | None = None
    start_char: int | None = None
    end_char: int | None = None


class ExtractionResult(BaseModel):
    statements: list[ExtractedStatement]
    operation: str = "extract_statements"
    provider: str
    model: str
    input_hash: str | None = None
    token_usage: "TokenUsage | None" = None
    request_status: str = "success"
    error_code: str | None = None
    latency_ms: int | None = None


class TokenUsage(BaseModel):
    input_token_count: int = 0
    output_token_count: int = 0
    estimated_cost: float = 0.0


class ClassificationResult(BaseModel):
    alignment_type: str
    explanation: str
    token_usage: TokenUsage | None = None


class VerificationSuggestion(BaseModel):
    question: str
    unresolved_issue: str
    missing_information: str
    suggested_evidence_type: str
    suggested_source: str | None = None
    expected_answer_structure: dict | None = None
    hypothesis_a: str | None = None
    hypothesis_b: str | None = None
    decision_relevance: str | None = None
    limitations: str | None = None
    token_usage: TokenUsage | None = None


class AIProvider(ABC):
    """Interface every provider must satisfy. Implementations must be honest:
    a failure raises; nothing is fabricated locally."""

    name: str = "base"
    model: str = "model"

    @abstractmethod
    async def extract_statements(self, document_text: str, *, context: dict | None = None) -> ExtractionResult:
        ...

    @abstractmethod
    async def classify_alignment(self, requirement_text: str, observation_text: str) -> ClassificationResult:
        ...

    @abstractmethod
    async def generate_verification_requests(
        self, finding_context: dict, evidence_texts: list[str]
    ) -> list[VerificationSuggestion]:
        ...


def normalize_request_text(text: str) -> str:
    return " ".join(text.split())


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


ExtractionResult.model_rebuild()
