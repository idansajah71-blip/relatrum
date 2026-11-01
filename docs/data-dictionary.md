# Data Dictionary (summary)

Core tables:
- users: accounts.
- workspaces, workspace_members: tenant + RBAC (owner/editor/reviewer/viewer).
- cases: investigation scope.
- sources, source_versions: uploaded documents and extracted text versions.
- evidence_spans: exact quote + char offsets.
- statements, statement_evidence: atomic statements linked to spans.
- statement_relations: cross-statement relations (supersedes, etc.).
- alignments: requirement-observation candidate classification.
- findings, finding_evidence: evidence dossiers with polarity.
- verification_tasks, verification_responses: MRE workflow.
- reviews: append-only human review history.
- analysis_runs, ai_invocations: reproducible runs + provider accounting.
- audit_events: append-only audit trail.

All PKs UUID; timestamps UTC; FKs enforced.
