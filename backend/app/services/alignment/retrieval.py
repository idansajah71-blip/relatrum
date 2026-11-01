"""Candidate retrieval: TF-IDF cosine + RapidFuzz on normalized text.

Retrieval is intentionally cheap (CPU-friendly) and reduces expensive or
unbounded AI classification calls to plausible pairs only.

Tokenizer: light deterministic stemmer (suffix truncation for ing/ed/es/s) so
lexical variants ("applications"/"application", "processed"/"processing") match
without training data. The floor is deliberately low because weak-but-relevant
candidates may be missing_observation or contradiction context; filtering by
class happens downstream in the engine.
"""
from __future__ import annotations

import re
from typing import Iterable

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.alignment._types import Candidate

_TOKEN_SPLIT = re.compile(r"\W+")

# (suffix, minimum stem length) - conservative truncation, applied in order.
_SUFFIXES = (("ies", 5), ("ing", 5), ("ed", 4), ("es", 4), ("s", 3))


def _stem(token: str) -> str:
    lowered = token.lower()
    if lowered in ENGLISH_STOP_WORDS or len(lowered) < 3:
        return ""
    for suffix, min_stem in _SUFFIXES:
        if lowered.endswith(suffix) and len(lowered) - len(suffix) >= min_stem:
            stem = lowered[:-len(suffix)]
            if not stem.endswith("s") or len(stem) >= min_stem + 2:
                return stem
            break
    return lowered


def _stem_analyzer(text: str) -> list[str]:
    tokens = [t for t in (_stem(tok) for tok in _TOKEN_SPLIT.split(text)) if t]
    pairs = [" ".join(p) for p in zip(tokens, tokens[1:])]
    return tokens + pairs


def content_stems(text: str) -> set[str]:
    """Unigram content stems (no bigrams) for cross-statement topic checks."""
    return {t for t in (_stem(tok) for tok in _TOKEN_SPLIT.split(text)) if t}


def retrieve_candidates(
    requirements: Iterable, observations: Iterable, *, min_similarity: float = 0.10, top_k: int = 20
) -> list[Candidate]:
    """Return requirement-observation pairs above the lexical floor.

    min_similarity is deliberately low: alignment classification refinements
    happen downstream; retrieval must not silently discard weak-but-relevant
    candidates (they may surface missing_observation or contradiction context).
    """
    requirements = list(requirements)
    observations = list(observations)
    if not requirements or not observations:
        return []
    req_texts = [_primary_text(r) for r in requirements]
    obs_texts = [_primary_text(o) for o in observations]
    if not any(t.strip() for t in req_texts) or not any(t.strip() for t in obs_texts):
        return []

    vectorizer = TfidfVectorizer(analyzer=_stem_analyzer, sublinear_tf=True, min_df=1)
    matrix = vectorizer.fit_transform(req_texts + obs_texts)
    req_matrix = matrix[: len(requirements)]
    obs_matrix = matrix[len(requirements):]
    similarity = cosine_similarity(req_matrix, obs_matrix)

    pairs: list[Candidate] = []
    for i, requirement in enumerate(requirements):
        ranked = sorted(range(len(observations)), key=lambda j: similarity[i][j], reverse=True)
        kept = 0
        for j in ranked:
            if kept >= top_k:
                break
            if similarity[i][j].item() <= 0 and fuzz.partial_ratio(req_texts[i], obs_texts[j]) / 100.0 < min_similarity:
                continue
            lexical = float(similarity[i][j])
            fuzzy = fuzz.partial_ratio(req_texts[i], obs_texts[j]) / 100.0
            combined = max(lexical, lexical * 0.7 + fuzzy * 0.3)
            if combined < min_similarity:
                continue
            pairs.append(
                Candidate(
                    requirement=requirement,
                    observation=observations[j],
                    lexical_similarity=round(lexical, 4),
                    fuzzy_similarity=round(float(fuzz.ratio(req_texts[i], obs_texts[j])) / 100.0, 4),
                    combined_similarity=round(combined, 4),
                )
            )
            kept += 1
    return pairs


def _primary_text(statement) -> str:
    return statement.normalized_text or statement.original_text or ""
