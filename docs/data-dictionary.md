# Data Dictionary

## users
id (UUID PK), email (unique), password_hash, display_name, is_active, created_at, updated_at.

## workspaces
id, name, slug, description, created_at, updated_at.

## workspace_members
id, workspace_id (FK), user_id (FK), role (owner/editor/reviewer/viewer), joined_at. Unique (workspace_id, user_id).

## cases
id, workspace_id (FK), title, description, domain, scope_definition, status, observation_start, observation_end, created_by (FK user), created_at, updated_at.

## sources
id, workspace_id, case_id, source_type, title, original_filename, mime_type, file_size, storage_key, sha256, source_origin, source_author, authority_label, sensitivity_level, source_date, captured_at, ingestion_status, created_by, created_at.

## source_versions
id, source_id (FK), version_number, content_sha256, extracted_text, extraction_method, extraction_status, extraction_metadata, created_at.

## evidence_spans
id, source_version_id (FK), page_number, start_char, end_char, exact_quote, paragraph_index, section_heading, created_at. Constraint start_char < end_char.

## statements
id, case_id (FK), source_version_id (FK), statement_type, original_text, normalized_text, subject, actor, action, object, condition, modality, frequency, temporal_valid_from, temporal_valid_until, observed_at, reported_at, extraction_confidence, review_status, creator_analysis_run_id (FK analysis_runs), extraction_metadata, created_at, updated_at.

## statement_evidence
id, statement_id (FK), evidence_span_id (FK), evidence_role, created_at.

## statement_relations
id, source_statement_id (FK), target_statement_id (FK), relation_type, relationship_explanation, created_by_analysis_run (FK), created_at.

## alignments
id, case_id (FK), requirement_statement_id (FK), observation_statement_id (FK), lexical_similarity, semantic_similarity, fuzzy_similarity, temporal_compatibility, temporal_detail (JSON), alignment_type, explanation, candidate_status, analysis_run_id (FK), created_at.

## findings
id, case_id (FK), finding_code, finding_type, title, summary, detailed_explanation, status, priority, priority_factors (JSON), impact_context, scope, quality_profile (JSON), first_detected_at, last_updated_at, created_by_analysis_run (FK), last_confirmed_by_run (FK), supersedes_finding_id (FK self), created_at, updated_at.

## finding_evidence
id, finding_id (FK), evidence_span_id (FK nullable), statement_id (FK nullable), evidence_polarity, relevance_explanation, relationship_type, created_at. Constraint at least one reference present.

## verification_tasks
id, finding_id (FK), question, unresolved_issue, missing_information, suggested_evidence_type, suggested_source, expected_answer_structure (JSON), hypothesis_a, hypothesis_b, decision_relevance, limitations, priority, status, assigned_to (FK user), due_at, created_by_run (FK analysis_runs), created_at, updated_at.

## verification_responses
id, verification_task_id (FK), response_text, response_source_id (FK source), reviewer_notes, submitted_by (FK user), submitted_at.

## reviews
id, finding_id (FK), reviewer_id (FK user), decision, review_notes, decision_rationale, previous_status, new_status, created_at (append-only).

## analysis_runs
id, case_id (FK), status, pipeline_version, prompt_version, provider_name, model_name, input_manifest_hash, started_at, completed_at, execution_metadata (JSON), failure_reason.

## ai_invocations
id, analysis_run_id (FK), provider, model, operation_type, prompt_version, input_hash, request_status, input_token_count, output_token_count, estimated_cost, latency_ms, error_code, created_at.

## audit_events
id, workspace_id (FK), actor_id (FK user), entity_type, entity_id, action, before_hash, after_hash, event_metadata (JSON), created_at (append-only).
