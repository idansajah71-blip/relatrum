# AI Methodology

## Extraction
MockProvider performs deterministic rule-based mining (modal verbs, observation cues, operational practice cues). Every `exact_quote` is verified verbatim against extracted text; fabricated quotes are rejected and counted. External providers (Gemini/Groq) use strict Pydantic schemas and the same verification.

## Candidate retrieval
TF-IDF (word n-grams 1–2) + RapidFuzz partial ratio, with light suffix stemming so lexical variants match. Retrieval floor is deliberately low (0.10) to avoid discarding weak-but-relevant pairs; classification happens downstream.

## Alignment classification
Rule-based, deterministic, thresholded:
- `full_match_candidate` (combined >= 0.80)
- `partial_match_candidate` (combined >= 0.40)
- `possible_contradiction` (duration breach or negation conflict)
- `temporal_mismatch` (strong pair, incompatible temporal judgement)
- `insufficient_information` (thin content)
- `uncertain` (shared topic, weak similarity)
- `unrelated` (no shared topic)

## Temporal reasoning
Unknown bounds remain unknown (never implicit infinity). Interval overlap, effective dates, version-aware comparison, supersession by non-overlapping windows, elapsed-duration parsing ("within N days" vs "took N days", working days treated as calendar days).

## Counter-evidence
Every finding preserves supporting, contradicting, contextual, and unresolved evidence with explicit polarity. Conflicting evidence is never discarded.

## Bidirectional alignment
Requirement→observation: deviations, missing observations, temporal mismatches.
Observation→requirement: unexplained practices, undocumented procedures, contextual claims.

## Minimum Resolving Evidence (MRE)
Rule-based templates per finding type producing targeted verification questions, competing hypotheses, expected answer structure, and limitations. Responses are linked to sources.

## Quality profile
extraction_quality, evidence_coverage, temporal_alignment_quality, semantic_alignment_quality, source_diversity, counter_evidence_presence, reviewer_validation_status (null until reviewed).

## Limitations
- Mock mode is deterministic heuristics, not LLM inference (disclosed in system info and reports).
- No causal claims without explicit evidence.
- Human review required for acceptance; RELATRUM is decision support, not an accusation engine.
