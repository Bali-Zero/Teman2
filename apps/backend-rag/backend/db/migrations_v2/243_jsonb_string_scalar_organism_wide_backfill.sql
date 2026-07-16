-- Migration 243: jsonb string-scalar -> object backfill, organism-wide (P1).
--
-- Root cause (live-probe 2026-07-16, following the conversation_messages
-- precedent in migration 242): backend/app/core/database.py +
-- service_initializer.py register a jsonb type codec whose encoder is
-- json.dumps. Every writer that pre-serialized a value with json.dumps() /
-- to_jsonb() / orjson.dumps() and bound it to a jsonb-typed placeholder
-- WITHOUT casting the param to text got that value dumped a SECOND time,
-- landing in Postgres as a jsonb STRING SCALAR instead of an object --
-- invisible to every ->>'key' / ? / @> SQL-side reader on that column.
--
-- The writers are fixed in the companion PR (backend fix, this repo's
-- Phase-2 cure of the P1 organism-wide sweep tracked in
-- .claude/skills/modus/PENDING-ARMS.md): every affected INSERT/UPDATE now
-- either types its placeholder $N::text::jsonb (server parses the text into
-- an object, bypassing the codec's own encode step) or binds the raw
-- dict/list directly (the codec then encodes it exactly once, correctly).
-- A repo-wide class-guard test (backend/tests/db/
-- test_jsonb_double_encoding_class_guard.py) keeps future writers cured.
--
-- This migration repairs the EXISTING rows for every column proven polluted
-- (jsonb_typeof = 'string') by the 2026-07-16 read-only catalog probe
-- against nuzantara_readonly, following migration 242's exact repair shape:
--   col = (col #>> '{}')::jsonb WHERE jsonb_typeof(col) = 'string'
--         AND left(ltrim(col #>> '{}'), 1) IN ('{', '[')
-- The left()/ltrim() guard keeps the cast from ever seeing a non-JSON
-- string (defensive; every polluted row observed is json.dumps() output, so
-- in practice every string-typed row converts). Idempotent: converted rows
-- become jsonb_typeof = 'object'/'array' and no longer match the WHERE.
--
-- PII boundary (clients.passport_ocr_data, documents.ocr_extracted_data):
-- this migration is a pure in-place SQL re-encode. It never SELECTs or logs
-- column contents -- only jsonb_typeof()/COUNT() are used anywhere in this
-- repo to verify it (see PR description for the verification transcript).
--
-- Skipped on purpose (per Phase-1 inventory): golden_routes.routing_hints
-- and any crm_dedup_backup_* snapshot table have no live writer (dead
-- tables) -- a data-only repair there is cron-theater, not a cure.
--
-- Each table is guarded with to_regclass(): the SQL migration lineage can
-- run against a fresh CI database where a table created by the PYTHON
-- migration lineage (e.g. conversation_threads, interactions, documents)
-- does not exist yet -- same guard shape as migration 242.
--
-- On the Pro apply manually like 212-242:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/243_jsonb_string_scalar_organism_wide_backfill.sql
-- === FORWARD ===

DO $$
BEGIN
    IF to_regclass('public.olympus_actions') IS NOT NULL THEN
        UPDATE olympus_actions
        SET detail = (detail #>> '{}')::jsonb
        WHERE jsonb_typeof(detail) = 'string'
          AND left(ltrim(detail #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.olympus_heartbeats') IS NOT NULL THEN
        UPDATE olympus_heartbeats
        SET bloat_top3 = CASE
                WHEN jsonb_typeof(bloat_top3) = 'string'
                     AND left(ltrim(bloat_top3 #>> '{}'), 1) IN ('{', '[')
                THEN (bloat_top3 #>> '{}')::jsonb
                ELSE bloat_top3
            END,
            top_tables_by_size = CASE
                WHEN jsonb_typeof(top_tables_by_size) = 'string'
                     AND left(ltrim(top_tables_by_size #>> '{}'), 1) IN ('{', '[')
                THEN (top_tables_by_size #>> '{}')::jsonb
                ELSE top_tables_by_size
            END
        WHERE jsonb_typeof(bloat_top3) = 'string'
           OR jsonb_typeof(top_tables_by_size) = 'string';
    END IF;

    IF to_regclass('public.olympus_insights') IS NOT NULL THEN
        UPDATE olympus_insights
        SET evidence = (evidence #>> '{}')::jsonb
        WHERE jsonb_typeof(evidence) = 'string'
          AND left(ltrim(evidence #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.funnel_sessions') IS NOT NULL THEN
        UPDATE funnel_sessions
        SET lead_profile = CASE
                WHEN jsonb_typeof(lead_profile) = 'string'
                     AND left(ltrim(lead_profile #>> '{}'), 1) IN ('{', '[')
                THEN (lead_profile #>> '{}')::jsonb
                ELSE lead_profile
            END,
            step_state = CASE
                WHEN jsonb_typeof(step_state) = 'string'
                     AND left(ltrim(step_state #>> '{}'), 1) IN ('{', '[')
                THEN (step_state #>> '{}')::jsonb
                ELSE step_state
            END
        WHERE jsonb_typeof(lead_profile) = 'string'
           OR jsonb_typeof(step_state) = 'string';
    END IF;

    IF to_regclass('public.activity_log') IS NOT NULL THEN
        UPDATE activity_log
        SET changes = (changes #>> '{}')::jsonb
        WHERE jsonb_typeof(changes) = 'string'
          AND left(ltrim(changes #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.team_timesheet') IS NOT NULL THEN
        UPDATE team_timesheet
        SET metadata = (metadata #>> '{}')::jsonb
        WHERE jsonb_typeof(metadata) = 'string'
          AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.crm_audit_log') IS NOT NULL THEN
        UPDATE crm_audit_log
        SET old_state = CASE
                WHEN jsonb_typeof(old_state) = 'string'
                     AND left(ltrim(old_state #>> '{}'), 1) IN ('{', '[')
                THEN (old_state #>> '{}')::jsonb
                ELSE old_state
            END,
            new_state = CASE
                WHEN jsonb_typeof(new_state) = 'string'
                     AND left(ltrim(new_state #>> '{}'), 1) IN ('{', '[')
                THEN (new_state #>> '{}')::jsonb
                ELSE new_state
            END,
            changes = CASE
                WHEN jsonb_typeof(changes) = 'string'
                     AND left(ltrim(changes #>> '{}'), 1) IN ('{', '[')
                THEN (changes #>> '{}')::jsonb
                ELSE changes
            END,
            metadata = CASE
                WHEN jsonb_typeof(metadata) = 'string'
                     AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[')
                THEN (metadata #>> '{}')::jsonb
                ELSE metadata
            END
        WHERE jsonb_typeof(old_state) = 'string'
           OR jsonb_typeof(new_state) = 'string'
           OR jsonb_typeof(changes) = 'string'
           OR jsonb_typeof(metadata) = 'string';
    END IF;

    IF to_regclass('public.kg_nodes_staging') IS NOT NULL THEN
        UPDATE kg_nodes_staging
        SET properties = (properties #>> '{}')::jsonb
        WHERE jsonb_typeof(properties) = 'string'
          AND left(ltrim(properties #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.kg_edges_staging') IS NOT NULL THEN
        UPDATE kg_edges_staging
        SET properties = (properties #>> '{}')::jsonb
        WHERE jsonb_typeof(properties) = 'string'
          AND left(ltrim(properties #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.kg_nodes') IS NOT NULL THEN
        UPDATE kg_nodes
        SET properties = (properties #>> '{}')::jsonb
        WHERE jsonb_typeof(properties) = 'string'
          AND left(ltrim(properties #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.kg_edges') IS NOT NULL THEN
        UPDATE kg_edges
        SET properties = (properties #>> '{}')::jsonb
        WHERE jsonb_typeof(properties) = 'string'
          AND left(ltrim(properties #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.inbound_webhooks') IS NOT NULL THEN
        UPDATE inbound_webhooks
        SET payload = (payload #>> '{}')::jsonb
        WHERE jsonb_typeof(payload) = 'string'
          AND left(ltrim(payload #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.conversation_threads') IS NOT NULL THEN
        UPDATE conversation_threads
        SET metadata = (metadata #>> '{}')::jsonb
        WHERE jsonb_typeof(metadata) = 'string'
          AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.events_outbox') IS NOT NULL THEN
        UPDATE events_outbox
        SET payload = (payload #>> '{}')::jsonb
        WHERE jsonb_typeof(payload) = 'string'
          AND left(ltrim(payload #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.events_outbox_dlq') IS NOT NULL THEN
        UPDATE events_outbox_dlq
        SET payload = (payload #>> '{}')::jsonb
        WHERE jsonb_typeof(payload) = 'string'
          AND left(ltrim(payload #>> '{}'), 1) IN ('{', '[');
    END IF;

    -- PII column: pure in-place re-encode, never SELECTed/logged by this
    -- migration or its verification (jsonb_typeof()/COUNT() only).
    IF to_regclass('public.documents') IS NOT NULL THEN
        UPDATE documents
        SET ocr_extracted_data = (ocr_extracted_data #>> '{}')::jsonb
        WHERE jsonb_typeof(ocr_extracted_data) = 'string'
          AND left(ltrim(ocr_extracted_data #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.practices') IS NOT NULL THEN
        UPDATE practices
        SET documents = (documents #>> '{}')::jsonb
        WHERE jsonb_typeof(documents) = 'string'
          AND left(ltrim(documents #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.interactions') IS NOT NULL THEN
        UPDATE interactions
        SET metadata = CASE
                WHEN jsonb_typeof(metadata) = 'string'
                     AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[')
                THEN (metadata #>> '{}')::jsonb
                ELSE metadata
            END,
            extracted_entities = CASE
                WHEN jsonb_typeof(extracted_entities) = 'string'
                     AND left(ltrim(extracted_entities #>> '{}'), 1) IN ('{', '[')
                THEN (extracted_entities #>> '{}')::jsonb
                ELSE extracted_entities
            END,
            action_items = CASE
                WHEN jsonb_typeof(action_items) = 'string'
                     AND left(ltrim(action_items #>> '{}'), 1) IN ('{', '[')
                THEN (action_items #>> '{}')::jsonb
                ELSE action_items
            END
        WHERE jsonb_typeof(metadata) = 'string'
           OR jsonb_typeof(extracted_entities) = 'string'
           OR jsonb_typeof(action_items) = 'string';
    END IF;

    IF to_regclass('public.failed_messages') IS NOT NULL THEN
        UPDATE failed_messages
        SET metadata = (metadata #>> '{}')::jsonb
        WHERE jsonb_typeof(metadata) = 'string'
          AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.naga_sessions') IS NOT NULL THEN
        UPDATE naga_sessions
        SET action_items = CASE
                WHEN jsonb_typeof(action_items) = 'string'
                     AND left(ltrim(action_items #>> '{}'), 1) IN ('{', '[')
                THEN (action_items #>> '{}')::jsonb
                ELSE action_items
            END,
            sub_questions = CASE
                WHEN jsonb_typeof(sub_questions) = 'string'
                     AND left(ltrim(sub_questions #>> '{}'), 1) IN ('{', '[')
                THEN (sub_questions #>> '{}')::jsonb
                ELSE sub_questions
            END
        WHERE jsonb_typeof(action_items) = 'string'
           OR jsonb_typeof(sub_questions) = 'string';
    END IF;

    IF to_regclass('public.crm_workspace_ai_snapshots') IS NOT NULL THEN
        UPDATE crm_workspace_ai_snapshots
        SET facts = (facts #>> '{}')::jsonb
        WHERE jsonb_typeof(facts) = 'string'
          AND left(ltrim(facts #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.visa_types') IS NOT NULL THEN
        UPDATE visa_types
        SET cost_details = CASE
                WHEN jsonb_typeof(cost_details) = 'string'
                     AND left(ltrim(cost_details #>> '{}'), 1) IN ('{', '[')
                THEN (cost_details #>> '{}')::jsonb
                ELSE cost_details
            END,
            requirements = CASE
                WHEN jsonb_typeof(requirements) = 'string'
                     AND left(ltrim(requirements #>> '{}'), 1) IN ('{', '[')
                THEN (requirements #>> '{}')::jsonb
                ELSE requirements
            END,
            restrictions = CASE
                WHEN jsonb_typeof(restrictions) = 'string'
                     AND left(ltrim(restrictions #>> '{}'), 1) IN ('{', '[')
                THEN (restrictions #>> '{}')::jsonb
                ELSE restrictions
            END,
            allowed_activities = CASE
                WHEN jsonb_typeof(allowed_activities) = 'string'
                     AND left(ltrim(allowed_activities #>> '{}'), 1) IN ('{', '[')
                THEN (allowed_activities #>> '{}')::jsonb
                ELSE allowed_activities
            END,
            benefits = CASE
                WHEN jsonb_typeof(benefits) = 'string'
                     AND left(ltrim(benefits #>> '{}'), 1) IN ('{', '[')
                THEN (benefits #>> '{}')::jsonb
                ELSE benefits
            END,
            process_steps = CASE
                WHEN jsonb_typeof(process_steps) = 'string'
                     AND left(ltrim(process_steps #>> '{}'), 1) IN ('{', '[')
                THEN (process_steps #>> '{}')::jsonb
                ELSE process_steps
            END,
            tips = CASE
                WHEN jsonb_typeof(tips) = 'string'
                     AND left(ltrim(tips #>> '{}'), 1) IN ('{', '[')
                THEN (tips #>> '{}')::jsonb
                ELSE tips
            END,
            metadata = CASE
                WHEN jsonb_typeof(metadata) = 'string'
                     AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[')
                THEN (metadata #>> '{}')::jsonb
                ELSE metadata
            END
        WHERE jsonb_typeof(cost_details) = 'string'
           OR jsonb_typeof(requirements) = 'string'
           OR jsonb_typeof(restrictions) = 'string'
           OR jsonb_typeof(allowed_activities) = 'string'
           OR jsonb_typeof(benefits) = 'string'
           OR jsonb_typeof(process_steps) = 'string'
           OR jsonb_typeof(tips) = 'string'
           OR jsonb_typeof(metadata) = 'string';
    END IF;

    IF to_regclass('public.conversations') IS NOT NULL THEN
        UPDATE conversations
        SET messages = CASE
                WHEN jsonb_typeof(messages) = 'string'
                     AND left(ltrim(messages #>> '{}'), 1) IN ('{', '[')
                THEN (messages #>> '{}')::jsonb
                ELSE messages
            END,
            metadata = CASE
                WHEN jsonb_typeof(metadata) = 'string'
                     AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[')
                THEN (metadata #>> '{}')::jsonb
                ELSE metadata
            END
        WHERE jsonb_typeof(messages) = 'string'
           OR jsonb_typeof(metadata) = 'string';
    END IF;

    -- PII column: pure in-place re-encode, never SELECTed/logged by this
    -- migration or its verification (jsonb_typeof()/COUNT() only).
    IF to_regclass('public.clients') IS NOT NULL THEN
        UPDATE clients
        SET passport_ocr_data = CASE
                WHEN jsonb_typeof(passport_ocr_data) = 'string'
                     AND left(ltrim(passport_ocr_data #>> '{}'), 1) IN ('{', '[')
                THEN (passport_ocr_data #>> '{}')::jsonb
                ELSE passport_ocr_data
            END,
            custom_fields = CASE
                WHEN jsonb_typeof(custom_fields) = 'string'
                     AND left(ltrim(custom_fields #>> '{}'), 1) IN ('{', '[')
                THEN (custom_fields #>> '{}')::jsonb
                ELSE custom_fields
            END
        WHERE jsonb_typeof(passport_ocr_data) = 'string'
           OR jsonb_typeof(custom_fields) = 'string';
    END IF;

    IF to_regclass('public.companies') IS NOT NULL THEN
        UPDATE companies
        SET custom_fields = (custom_fields #>> '{}')::jsonb
        WHERE jsonb_typeof(custom_fields) = 'string'
          AND left(ltrim(custom_fields #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.crm_settings') IS NOT NULL THEN
        UPDATE crm_settings
        SET value = (value #>> '{}')::jsonb
        WHERE jsonb_typeof(value) = 'string'
          AND left(ltrim(value #>> '{}'), 1) IN ('{', '[');
    END IF;

    IF to_regclass('public.lead_intents') IS NOT NULL THEN
        UPDATE lead_intents
        SET context = (context #>> '{}')::jsonb
        WHERE jsonb_typeof(context) = 'string'
          AND left(ltrim(context #>> '{}'), 1) IN ('{', '[');
    END IF;
END $$;

-- === ROLLBACK ===
-- Intentionally none: re-double-encoding object rows back into string
-- scalars would re-blind every jsonb-path reader across all 27 tables above
-- (same rationale as migration 242). Forward-only data repair.
