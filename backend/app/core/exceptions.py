"""Application exceptions and API error mechanics.

All errors render through the standardized response envelope and never leak
stack traces in production responses.
"""
from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "internal_error"

    def __init__(self, message: str, *, error_code: str | None = None, details: dict | None = None):
        self.message = message
        self.details = details or {}
        if error_code:
            self.error_code = error_code
        super().__init__(message)


class NotFoundError(ApiError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class PermissionDeniedError(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "permission_denied"


class UnauthorizedError(ApiError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"


class ConflictError(ApiError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class ValidationFailedError(ApiError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "validation_failed"


class RateLimitedError(ApiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limited"


class AiProviderError(ApiError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ai_provider_error"


def envelope(success: bool, message: str, data=None, meta: dict | None = None, error_code: str | None = None):
    payload: dict = {"success": success, "message": message}
    if data is not None:
        payload["data"] = data
    if meta:
        payload["meta"] = meta
    if error_code:
        payload["error_code"] = error_code
    return payload


class _ErrBody(BaseModel):
    success: bool
    message: str
    error_code: str | None = None
    details: dict | None = None


def error_response(status_code: int, message: str, error_code: str, details: dict | None = None) -> JSONResponse:
    content = _ErrBody(success=False, message=message, error_code=error_code, details=details).model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=content)


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status_code, exc.message, exc.error_code, exc.details or None)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = {"errors": [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]}
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Request validation failed.",
        "request_validation_error",
        details,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    from app.core.logging import get_logger, request_id_var

    get_logger(__name__).exception("Unhandled error: %s", exc)
    message = "Internal server error." if request.app.state.app_env == "production" else f"Internal server error: {exc}"
    return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, message, "internal_error")
