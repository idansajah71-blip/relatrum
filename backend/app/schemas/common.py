"""Shared API schemas: response envelope and pagination."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    message: str = "OK"
    data: T | None = None
    meta: dict[str, Any] | None = Field(default=None)


class PaginatedEnvelope(BaseModel, Generic[T]):
    success: bool = True
    message: str = "OK"
    data: list[T] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class PaginationParams(BaseModel):
    limit: int = 50
    offset: int = 0

    @classmethod
    def from_query(cls, limit: int | None, offset: int | None) -> "PaginationParams":
        return cls(limit=min(max(limit or 50, 1), 200), offset=max(offset or 0, 0))
