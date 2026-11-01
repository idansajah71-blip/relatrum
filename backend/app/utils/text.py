"""Text hygiene used across extraction and provenance indexing."""
from __future__ import annotations

import re

# Normalization applied ONLY when validating a quote against extracted text:
# documents regularly contain typographic quotes/dashes that survive copy-paste.
_FOLD = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}


def fold_quote(text: str) -> str:
    """Minor, lossless folding used for quote validation only (never for storage)."""
    for src, dst in _FOLD.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text)


def split_paragraph_batches(text: str) -> list[tuple[str, int, int, int, str | None]]:
    """Return paragraph units for span indexing.

    Semantics:
      * only '\\n\\n' splits paragraphs — single newlines are soft wraps;
      * each unit carries (paragraph_text, argv_start, end_char, paragraph_index, section_heading)
        where section headings ('lines ending with:') belong to the next paragraph.
    """
    units: list[tuple[str, int, int, int, str | None]] = []
    paragraphs = text.split("\n\n")
    cursor = 0
    heading: str | None = None
    index = 0
    for part in paragraphs:
        stripped = part.strip()
        if not stripped:
            cursor += len(part) + 2
            continue
        # char offsets relative to the original text (start of this paragraph)
        start = cursor + part.find(stripped) if stripped in part else cursor
        end = start + len(stripped)
        # Promote short trailing-colon lines to section headings of the next unit.
        lines = stripped.split("\n")
        last_line = lines[-1].strip()
        if len(lines) >= 1 and last_line.endswith(":") and not ends_with_sentence(last_line):
            heading = last_line[:-1][:400]
        else:
            units.append((stripped, start, end, index, heading))
            index += 1
        cursor += len(part) + 2
    return units


def ends_with_sentence(fragment: str) -> bool:
    return any(fragment.rstrip().endswith(mark) for mark in (".", "!", "?", "\u2026"))
