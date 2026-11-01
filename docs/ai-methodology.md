# AI Methodology

## Extraction
MockProvider: deterministic rule-based mining; every quote verified verbatim; fabricated quotes rejected.

## Candidate retrieval
TF-IDF (word n-grams) + RapidFuzz, with light stemming. Low floor (0.10) to avoid discarding weak-but-relevant pairs.

## Alignment
Rule-based classification: full_match (>=0.80), partial (>=0.40), possible_contradiction (duration/negation), temporal_mismatch, insufficient_information, uncertain, unrelated.

## Temporal reasoning
Unknown bounds stay unknown (never implicit infinity). Interval overlap, effective dates, supersession by non-overlapping windows.

## Counter-evidence
Every finding preserves supporting and contradicting evidence (polarity).

## MRE
Rule-based templates per finding type; not statistically optimized. Responses linked to sources.

## Quality profile
Extraction quality, evidence coverage, temporal/semantic alignment, source diversity, counter-evidence presence, reviewer validation status (null until reviewed).

## Limitations
- Mock mode is deterministic heuristics, not LLM inference (disclosed).
- No causal claims without explicit evidence.
- Human review required for acceptance.
