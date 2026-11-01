"""Context normalization for extraction (honest, minimal, reversible)."""
from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_statement_text(text: str) -> str:
    """Collapse whitespace and normalize trailing punctuation spacing.

    Original text is always preserved alongside; normalization exists only to
    make cross-statement matching stable.
    """
    return _WHITESPACE_RE.sub(" ", text or "").strip()
