"""Provenance indexing: build evidence spans that exactly quote extracted text.

Spans are paragraph units nested inside PDF page boundaries. Every quote is
verified by slicing the extracted text; a failure to match raises instead of
silently storing an unverifiable reference.
"""
from __future__ import annotations

from app.core.exceptions import ValidationFailedError
from app.models.evidence import EvidenceSpan
from app.utils.text import split_paragraph_batches


def compute_spans(
    *,
    extracted_text: str,
    source_version_id: str,
    page_start_offsets: list[int] | tuple[int, ...] | None = None,
) -> list[EvidenceSpan]:
    """Build evidence spans over paragraph units.

    page_start_offsets carries each page's start character index inside the
    assembled extracted_text (page N = index N-1 in that list); when provided,
    spans carry a physical page number.
    """
    spans: list[EvidenceSpan] = []
    offset_map = {i + 1: int(off) for i, off in enumerate(page_start_offsets or [])}
    units = split_paragraph_batches(extracted_text)
    for paragraph_text, start, end, index, heading in units:
        page = _page_for_offset(start, offset_map)
        quote = extracted_text[start:end]
        _assert_quote_matches(quote, paragraph_text, start, end)
        spans.append(
            EvidenceSpan(
                source_version_id=source_version_id,
                page_number=page,
                start_char=start,
                end_char=end,
                exact_quote=quote,
                paragraph_index=index,
                section_heading=heading,
            )
        )
    return spans


def _page_for_offset(offset: int, page_start_offsets: dict[int, int] | None) -> int | None:
    if not page_start_offsets:
        return None
    current_page = None
    for page_number, page_start in sorted(page_start_offsets.items()):
        if page_start <= offset:
            current_page = page_number
    return current_page


def _assert_quote_matches(quote: str, paragraph_text: str, start: int, end: int) -> None:
    if not quote or quote.strip() != paragraph_text.strip():
        raise ValidationFailedError(
            f"Provenance indexing produced an unverifiable quote at {start}:{end}; refusing to store."
        )
