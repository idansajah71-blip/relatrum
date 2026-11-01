# Evaluation

## Synthetic dataset
The test suite (`backend/tests/`) covers:
1. Full alignment candidate.
2. Partial alignment.
3. Possible contradiction (duration breach).
4. Negation conflict.
5. Temporal mismatch (observation outside validity window).
6. Missing observation (requirement without counterpart).
7. Unexplained practice (operational practice without requirement).
8. Contradictory reports (negation conflict between observations).
9. Repeated operational friction (>=2 observations per requirement).
10. Insufficient evidence (no observations / no resolvable alignments).
11. Supersession by effective date.
12. Thin/insufficient info.
13. Unrelated noise.
14. Unexplained practice detection.
15. Deterministic reproducibility (manifest hash equality across runs).
16. RBAC (404 non-member, 403 viewer on mutations).
17. Ingestion (TXT, CSV, PDF, DOCX, duplicate detection, quote verification).
18. Finding dossiers, evidence links, review history, status transitions.
19. MRE generation, task patch, responses, verification queue.
20. Reporting (JSON/Markdown) and evidence graph.

## Method
- Unit tests for engine rules and temporal reasoning.
- Integration tests via FastAPI TestClient with isolated SQLite DB.
- All tests run offline with `AI_PROVIDER=mock`.

## Results
- `python -m pytest` → **100 passed, 1 warning** (as of completion).
- Frontend: `npm run build` succeeds; `npm run lint` 0 errors (1 warning).

## Remaining failure cases / known gaps
- MRE is template-based, not statistically optimized.
- Semantic similarity uses lexical proxy (combined score not persisted).
- No embedding-based retrieval (disabled by default).
