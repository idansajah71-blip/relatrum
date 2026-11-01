"""Gemini provider (structured output via generateContent REST API)."""
from __future__ import annotations

import json
import time

import httpx

from app.ai.base import (
    AIProvider,
    ClassificationResult,
    ExtractionResult,
    TokenUsage,
    VerificationSuggestion,
)
from app.ai import prompts
from app.core.exceptions import AiProviderError


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_seconds: int, retry_limit: int):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retry_limit = max(0, retry_limit)
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )

    async def _generate(self, system: str, user: str, *, input_hash: str | None = None) -> tuple[dict, TokenUsage, int]:
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", " temperature": 0.1},
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retry_limit + 2):
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(
                        self.endpoint,
                        params={"key": self.api_key},
                        json=payload,
                    )
                latency_ms = int((time.monotonic() - started) * 1000)
                if resp.status_code == 429:
                    raise AiProviderError("Gemini rate limit exceeded (HTTP 429).", error_code="rate_limited")
                if resp.status_code >= 400:
                    raise AiProviderError(
                        f"Gemini request failed (HTTP {resp.status_code}).", error_code="provider_http_error"
                    )
                body = resp.json()
                text = body["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                usage = body.get("usageMetadata", {})
                token_usage = TokenUsage(
                    input_token_count=int(usage.get("promptTokenCount") or 0),
                    output_token_count=int(usage.get("candidatesTokenCount") or 0),
                    estimated_cost=0.0,  # free tier: cost not claimed
                )
                return parsed, token_usage, latency_ms
            except httpx.TimeoutException as exc:
                last_error = exc
            except AiProviderError:
                raise
            except Exception as exc:
                last_error = exc
        raise AiProviderError(
            f"Gemini failed after {self.retry_limit + 1} attempts: {last_error}",
            error_code="provider_unavailable",
        )

    async def extract_statements(self, document_text: str, *, context: dict | None = None) -> ExtractionResult:
        user = prompts.EXTRACTION_USER_TEMPLATE.format(
            context=json.dumps(context or {}, default=str), text=document_text
        )
        parsed, usage, latency = await self._generate(prompts.EXTRACTION_SYSTEM, user)
        try:
            statements = parsed.get("statements", [])
            return ExtractionResult(
                statements=[_coerce(s) for s in statements],
                provider=self.name,
                model=self.model,
                token_usage=usage,
                latency_ms=latency,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise AiProviderError(f"Malformed Gemini extraction output: {exc}", error_code="bad_output")

    async def classify_alignment(self, requirement_text: str, observation_text: str) -> ClassificationResult:
        user = prompts.ALIGNMENT_USER_TEMPLATE.format(requirement=requirement_text, observation=observation_text)
        parsed, usage, _ = await self._generate(prompts.ALIGNMENT_SYSTEM, user)
        return ClassificationResult(
            alignment_type=str(parsed.get("alignment_type", "uncertain")),
            explanation=str(parsed.get("explanation", "")),
            token_usage=usage,
        )

    async def generate_verification_requests(self, finding_context: dict, evidence_texts: list[str]) -> list[VerificationSuggestion]:
        user = prompts.VERIFY_USER_TEMPLATE.format(
            summary=finding_context.get("summary", ""),
            unresolved=finding_context.get("unresolved_issue", ""),
            evidence="\n".join(f"- {t}" for t in evidence_texts) or "(none)",
        )
        parsed, usage, _ = await self._generate(prompts.VERIFY_SYSTEM, user)
        suggestions = []
        for raw in parsed.get("suggestions", []):
            raw = dict(raw)
            raw["token_usage"] = usage
            suggestions.append(VerificationSuggestion(**raw))
        return suggestions


def _coerce(raw: dict) -> "object":
    from app.ai.base import ExtractedStatement

    raw = dict(raw)
    raw.pop("confidence", None)
    return ExtractedStatement(**raw)
