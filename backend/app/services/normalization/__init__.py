from dataclasses import dataclass


@dataclass
class NormalizedStatement:
    original: str
    normalized: str


def normalize(text: str) -> NormalizedStatement:
    from app.services.normalization.normalize import normalize_statement_text

    return NormalizedStatement(
        original=text,
        normalized=normalize_statement_text(text),
    )
