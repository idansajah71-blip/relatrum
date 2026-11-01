"""Extraction engines for TXT / CSV / PDF / DOCX into normalized text.

Every extractor returns an ExtractionResult with plain text plus metadata that
provenance indexing uses to place page/paragraph boundaries faithfully.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from app.core.exceptions import ValidationFailedError


@dataclass
class ExtractionResult:
    text: str
    method: str
    metadata: dict = field(default_factory=dict)


def extract_text(extension: str, content: bytes) -> ExtractionResult:
    if extension in (".txt", ".md"):
        return _extract_plain(content, extension=extension)
    if extension == ".csv":
        return _extract_csv(content)
    if extension == ".pdf":
        return _extract_pdf(content)
    if extension == ".docx":
        return _extract_docx(content)
    raise ValidationFailedError(f"No extractor for extension '{extension}'.")


def _extract_plain(content: bytes, extension: str) -> ExtractionResult:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValidationFailedError("Text file is not valid UTF-8; re-save with UTF-8 encoding.")
    return ExtractionResult(
        text=text,
        method=f"native_text:{extension[1:]}",
        metadata={"encoding": "utf-8", "preserved_page_boundaries": False},
    )


def _extract_csv(content: bytes) -> ExtractionResult:
    try:
        decoded = content.decode("utf-8-sig")  # tolerate Excel BOM
    except UnicodeDecodeError:
        raise ValidationFailedError("CSV file is not valid UTF-8; re-save with UTF-8 encoding.")
    reader = csv.reader(io.StringIO(decoded))
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise ValidationFailedError(f"Malformed CSV: {exc}") from exc
    if not rows:
        raise ValidationFailedError("CSV contains no rows.")
    header = [h.strip() for h in rows[0]]
    lines: list[str] = []
    for i, row in enumerate(rows[1:], start=1):
        if not row:
            continue
        rendered = " | ".join(f"{header[j]}: {row[j].strip()}" for j in range(min(len(row), len(header))))
        lines.append(f"row {i}: {rendered}")
    text = "\n\n".join(lines)
    return ExtractionResult(
        text=text,
        method="csv_rows",
        metadata={"columns": header, "rows": len(lines)},
    )


def _extract_pdf(content: bytes) -> ExtractionResult:
    try:
        import pymupdf

        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:  # malformed PDF raises during open
        raise ValidationFailedError(f"Could not open PDF: {exc}") from exc

    parts: list[str] = []
    page_map: list[int] = []  # start index of each page's text
    for page in doc:
        page_map.append(sum(len(p) for p in parts))
        txt = page.get_text("text") or ""
        parts.append(txt.strip("\x0c"))
    doc.close()
    text = "\n\n".join(p for p in parts)

    return ExtractionResult(
        text=text,
        method="pymupdf_text",
        metadata={
            "pdf_version": None,
            "pages": len(page_map),
            "preserved_page_boundaries": True,
            "page_start_offsets": page_map,
        },
    )


def _extract_docx(content: bytes) -> ExtractionResult:
    try:
        import io as _io

        import docx

        document = docx.Document(_io.BytesIO(content))
    except Exception as exc:
        raise ValidationFailedError(f"Could not open DOCX: {exc}") from exc
    paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    text = "\n\n".join(paragraphs)
    return ExtractionResult(
        text=text,
        method="python_docx_paragraphs",
        metadata={"paragraphs": len(paragraphs), "preserved_page_boundaries": False},
    )
