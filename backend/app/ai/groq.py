"""Groq provider (OpenAI-compatible chat completions API)."""
from __future__ import annotations

import json
import time

import httpx

from app.ai.base import (
    AIProvider,
    ClassificationResult,
    ExtractedStatement,
    ExtractionResult,
    TokenUsage,
    VerificationSuggestion,
)
from app.ai import prompts
from app.core.exceptions import AiProviderError


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str, timeout_seconds: int, retry_limit: int):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.retry_limit = max(0, retry_limit)
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    async def _generate(self, system: str, user: str) -> tuple[dict, TokenUsage, int]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_error: Exception | None = None
        for _attempt in range(1, self.retry_limit + 2):
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(self.endpoint, json=payload, headers=headers)
                latency_ms = int((time.monotonic() - started) * 1000)
                if resp.status_code == 429:
                    raise AiProviderError("Groq rate limit exceeded (HTTP 429).", error_code="rate_limited")
                if resp.status_code >= 400:
                    raise AiProviderError(
                        f"Groq request failed (HTTP {resp.status_code}).", error_code="provider_http_error"
                    )
                body = resp.json()
                text = body["choices"][0]["message"]["content"]
                parsed = json.loads(text)
                usage = body.get("usage", {})
                token_usage = TokenUsage(
                    input_token_count=int(usage.get("prompt_tokens") or 0),
                    output_token_count=int(usage.get("completion_tokens") or 0),
                    estimated_cost=0.0,
                )
                return parsed, token_usage, latency_ms
            except httpx.TimeoutException as exc:
                last_error = exc
            except AiProviderError:
                raise
            except Exception as exc:
                last_error = exc
        raise AiProviderError(
            f"Groq failed after {self.retry_limit + 1} attempts: {last_error}",
            error_code="provider_unavailable",
        )

    async def extract_statements(self, document_text: str, *, context: dict | None = None) -> ExtractionResult:
        user = prompts.EXTRACTION_USER_TEMPLATE.format(
            context=json.dumps(context or {}, default=str), text=document_text
        )
        parsed, usage, latency = await self._generate(prompts.EXTRACTION_SYSTEM, user)
        try:
            out = []
            for s in parsed.get("statements", []):
                s = dict(s)
                s.setdefault("extraction_confidence", None)
                out.append(ExtractedStatement(**s))
            return ExtractionResult(
                statements=out,
                provider=self.name,
                model=self.model,
                token_usage=usage,
                latency_ms=latency,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise AiProviderError(f"Malformed Groq extraction output: {exc}", error_code="bad_output")

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
