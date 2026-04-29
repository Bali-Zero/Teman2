-- 146_eventbus_triggers_use_outbox.sql
--
-- P0-2 phase 2: refactor every DB trigger that emits a pg_notify on a
-- PG_CHANNEL_MAP channel so it ALSO writes the event to events_outbox in
-- the SAME transaction.  This closes the durability gap that phase 1
-- (migration 144 + services/events/outbox.py) only solved at the helper
-- level — until this migration lands, trigger-emitted events are still
-- volatile (lost during a listener reconnect window).
--
-- Affected channels (consumers in PG_CHANNEL_MAP):
--   * practice_changed     — trigger trg_practice_changed on practices
--                            (created in migration 075)
--   * client_changed       — trigger trg_client_changed on clients
--                            (created in migration 076)
--   * compliance_alert     — trigger trg_compliance_alert on compliance_alerts
--                            (created in migration 076, conditional)
--   * war_room_event       — triggers trg_war_room_drafts_notify and
--                            trg_war_room_posts_notify (migration 112)
--   * intel_event          — triggers trg_trend_signals_notify and
--                            trg_research_dossiers_notify (migration 113)
--   * cognitive_event      — triggers trg_cross_dossier_theses_notify,
--                            trg_wr_anomaly_alerts_notify,
--                            trg_weekly_strategic_briefs_notify,
--                            trg_ultra_moves_notify (migration 114)
--
-- NOT touched here:
--   * wr2_status_change (migration 138) — has its own consumer
--     (wr2_supervisor.py launchd daemon), not registered in
--     PG_CHANNEL_MAP, replay-on-reconnect would not dispatch it.
--   * partner.commission_changed (services/crm/partners/events.py) —
--     dotted channel name fails validate_channel(); not registered in
--     PG_CHANNEL_MAP either. Out of scope for phase 2.
--
-- Atomicity contract:
--   Each trigger fires AFTER INSERT/UPDATE inside the user transaction.
--   The INSERT into events_outbox + the pg_notify call run in that same
--   transaction. If the user's tx rolls back, both vanish (Postgres
--   queues NOTIFY until COMMIT, and the outbox row never becomes visible
--   to other connections). If the user's tx commits but the listener is
--   disconnected, the outbox row stays unconsumed and gets replayed on
--   reconnect via EventBus._replay_outbox_on_reconnect (event_bus.py).
--
-- Idempotency:
--   CREATE OR REPLACE FUNCTION + DROP TRIGGER IF EXISTS + CREATE TRIGGER
--   makes this migration safe to re-run. Unique trigger names per table
--   are preserved from earlier migrations.
--
-- Squawk lint suppressions:
--   The migration drops triggers from earlier migrations and recreates
--   them with new function bodies. We use `-- squawk-ignore: ban-drop-trigger`
--   per-line because each DROP TRIGGER is followed immediately by a
--   CREATE TRIGGER on the same table — there is no observable window
--   where the trigger is missing within a single transaction.

-- ── Helper: shared body that every refactored trigger calls. ──────────
-- The trigger function builds the channel-specific JSONB payload first
-- (preserving the exact shape from the original trigger function — see
-- migrations 075/076/112/113/114), then writes it to events_outbox AND
-- fires pg_notify with _outbox_id injected. Consumers can ack via the
-- _outbox_id, mirroring the contract in services/events/outbox.py.

-- 1. practice_changed (was: notify_practice_change in migration 075).
CREATE OR REPLACE FUNCTION notify_practice_change()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    outbox_id    BIGINT;
BEGIN
    IF (OLD.status IS DISTINCT FROM NEW.status)
       OR (OLD.payment_status IS DISTINCT FROM NEW.payment_status)
    THEN
        payload := jsonb_build_object(
            'practice_id',   NEW.id,
            'client_id',     NEW.client_id,
            'old_status',    OLD.status,
            'new_status',    NEW.status,
            'old_payment',   OLD.payment_status,
            'new_payment',   NEW.payment_status,
            'assigned_to',   NEW.assigned_to,
            'ts',            EXTRACT(EPOCH FROM NOW())
        );

        INSERT INTO events_outbox (channel, payload)
        VALUES ('practice_changed', payload)
        RETURNING id INTO outbox_id;

        PERFORM pg_notify(
            'practice_changed',
            (payload || jsonb_build_object('_outbox_id', outbox_id))::text
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. client_changed (was: notify_client_change in migration 076).
CREATE OR REPLACE FUNCTION notify_client_change()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    outbox_id    BIGINT;
BEGIN
    payload := jsonb_build_object(
        'client_id',     NEW.id,
        'email',         NEW.email,
        'full_name',     NEW.full_name,
        'status',        NEW.status,
        'assigned_to',   NEW.assigned_to,
        'operation',     TG_OP,
        'ts',            EXTRACT(EPOCH FROM NOW())
    );

    INSERT INTO events_outbox (channel, payload)
    VALUES ('client_changed', payload)
    RETURNING id INTO outbox_id;

    PERFORM pg_notify(
        'client_changed',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. compliance_alert (was: notify_compliance_alert in migration 076).
-- The original migration created the function conditionally on table
-- existence. The compliance_alerts table is created in
-- db/migrations_v2/114_compliance_alerts.sql which lands BEFORE 146 in
-- the runner's lexicographic ordering, so we can unconditionally
-- (re)create the function here.
CREATE OR REPLACE FUNCTION notify_compliance_alert()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    outbox_id    BIGINT;
BEGIN
    payload := jsonb_build_object(
        'alert_id',    NEW.id,
        'client_id',   NEW.client_id,
        'alert_type',  NEW.alert_type,
        'severity',    NEW.severity,
        'message',     LEFT(NEW.message, 500),
        'ts',          EXTRACT(EPOCH FROM NOW())
    );

    INSERT INTO events_outbox (channel, payload)
    VALUES ('compliance_alert', payload)
    RETURNING id INTO outbox_id;

    PERFORM pg_notify(
        'compliance_alert',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. war_room_event (was: notify_war_room_event in migration 112).
CREATE OR REPLACE FUNCTION notify_war_room_event()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    event_type   TEXT;
    outbox_id    BIGINT;
BEGIN
    IF TG_TABLE_NAME = 'war_room_drafts' THEN
        IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM NEW.status THEN
            RETURN NEW;
        END IF;
        event_type := 'draft_' || NEW.status;
        payload := jsonb_build_object(
            'draft_id',    NEW.id,
            'status',      NEW.status,
            'event_type',  event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'war_room_posts' THEN
        event_type := 'post_published';
        payload := jsonb_build_object(
            'post_id',     NEW.id,
            'draft_id',    NEW.draft_id,
            'platform',    NEW.platform,
            'event_type',  event_type,
            'occurred_at', NEW.published_at
        );
    ELSE
        RETURN NEW;
    END IF;

    INSERT INTO events_outbox (channel, payload)
    VALUES ('war_room_event', payload)
    RETURNING id INTO outbox_id;

    PERFORM pg_notify(
        'war_room_event',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. intel_event (was: notify_intel_event in migration 113).
CREATE OR REPLACE FUNCTION notify_intel_event()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    event_type   TEXT;
    outbox_id    BIGINT;
BEGIN
    IF TG_TABLE_NAME = 'trend_signals' THEN
        event_type := 'trend_signal_detected';
        payload := jsonb_build_object(
            'signal_id',     NEW.id,
            'source',        NEW.source,
            'topic',         NEW.topic,
            'urgency_score', NEW.urgency_score,
            'event_type',    event_type,
            'occurred_at',   NEW.detected_at
        );
    ELSIF TG_TABLE_NAME = 'research_dossiers' THEN
        IF TG_OP = 'INSERT' THEN
            event_type := 'dossier_created';
        ELSE
            event_type := 'dossier_updated';
        END IF;
        payload := jsonb_build_object(
            'dossier_id',     NEW.id,
            'slug',           NEW.slug,
            'topic_category', NEW.topic_category,
            'public_safe',    NEW.public_safe,
            'event_type',     event_type,
            'occurred_at',    NEW.updated_at
        );
    ELSE
        RETURN NEW;
    END IF;

    INSERT INTO events_outbox (channel, payload)
    VALUES ('intel_event', payload)
    RETURNING id INTO outbox_id;

    PERFORM pg_notify(
        'intel_event',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 6. cognitive_event (was: notify_cognitive_event in migration 114).
CREATE OR REPLACE FUNCTION notify_cognitive_event()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    event_type   TEXT;
    outbox_id    BIGINT;
BEGIN
    IF TG_TABLE_NAME = 'cross_dossier_theses' THEN
        event_type := 'thesis_' || TG_OP;
        payload := jsonb_build_object(
            'thesis_id',   NEW.id,
            'table',       'cross_dossier_theses',
            'event_type',  event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'wr_anomaly_alerts' THEN
        event_type := 'alert_' || TG_OP;
        payload := jsonb_build_object(
            'alert_id',    NEW.id,
            'severity',    NEW.severity,
            'table',       'wr_anomaly_alerts',
            'event_type',  event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'weekly_strategic_briefs' THEN
        event_type := 'brief_' || TG_OP;
        payload := jsonb_build_object(
            'brief_id',    NEW.id,
            'week_of',     NEW.week_of,
            'table',       'weekly_strategic_briefs',
            'event_type',  event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'ultra_moves' THEN
        event_type := 'ultra_move_' || TG_OP;
        payload := jsonb_build_object(
            'move_id',       NEW.id,
            'zero_decision', NEW.zero_decision,
            'table',         'ultra_moves',
            'event_type',    event_type,
            'occurred_at',   NOW()
        );
    ELSE
        RETURN NEW;
    END IF;

    INSERT INTO events_outbox (channel, payload)
    VALUES ('cognitive_event', payload)
    RETURNING id INTO outbox_id;

    PERFORM pg_notify(
        'cognitive_event',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- === ROLLBACK ===
-- Restore the original (pre-146) function bodies that fired pg_notify
-- directly without writing to events_outbox. This matches the SQL in
-- migrations 075/076/112/113/114 byte-for-byte. Triggers themselves are
-- not dropped — they keep pointing at the same function names; the
-- functions just revert to their pre-146 implementation.

CREATE OR REPLACE FUNCTION notify_practice_change()
RETURNS TRIGGER AS $$
DECLARE
    payload TEXT;
BEGIN
    IF (OLD.status IS DISTINCT FROM NEW.status)
       OR (OLD.payment_status IS DISTINCT FROM NEW.payment_status)
    THEN
        payload := json_build_object(
            'practice_id',     NEW.id,
            'client_id',       NEW.client_id,
            'old_status',      OLD.status,
            'new_status',      NEW.status,
            'old_payment',     OLD.payment_status,
            'new_payment',     NEW.payment_status,
            'assigned_to',     NEW.assigned_to,
            'ts',              EXTRACT(EPOCH FROM NOW())
        )::text;

        PERFORM pg_notify('practice_changed', payload);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION notify_client_change()
RETURNS TRIGGER AS $$
DECLARE
    payload TEXT;
BEGIN
    payload := json_build_object(
        'client_id',     NEW.id,
        'email',         NEW.email,
        'full_name',     NEW.full_name,
        'status',        NEW.status,
        'assigned_to',   NEW.assigned_to,
        'operation',     TG_OP,
        'ts',            EXTRACT(EPOCH FROM NOW())
    )::text;

    PERFORM pg_notify('client_changed', payload);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION notify_compliance_alert()
RETURNS TRIGGER AS $$
DECLARE
    payload TEXT;
BEGIN
    payload := json_build_object(
        'alert_id',    NEW.id,
        'client_id',   NEW.client_id,
        'alert_type',  NEW.alert_type,
        'severity',    NEW.severity,
        'message',     LEFT(NEW.message, 500),
        'ts',          EXTRACT(EPOCH FROM NOW())
    )::text;

    PERFORM pg_notify('compliance_alert', payload);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION notify_war_room_event()
RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
    event_type TEXT;
BEGIN
    IF TG_TABLE_NAME = 'war_room_drafts' THEN
        IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM NEW.status THEN
            RETURN NEW;
        END IF;
        event_type := 'draft_' || NEW.status;
        payload := jsonb_build_object(
            'draft_id', NEW.id,
            'status', NEW.status,
            'event_type', event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'war_room_posts' THEN
        event_type := 'post_published';
        payload := jsonb_build_object(
            'post_id', NEW.id,
            'draft_id', NEW.draft_id,
            'platform', NEW.platform,
            'event_type', event_type,
            'occurred_at', NEW.published_at
        );
    ELSE
        RETURN NEW;
    END IF;

    PERFORM pg_notify('war_room_event', payload::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION notify_intel_event()
RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
    event_type TEXT;
BEGIN
    IF TG_TABLE_NAME = 'trend_signals' THEN
        event_type := 'trend_signal_detected';
        payload := jsonb_build_object(
            'signal_id', NEW.id,
            'source', NEW.source,
            'topic', NEW.topic,
            'urgency_score', NEW.urgency_score,
            'event_type', event_type,
            'occurred_at', NEW.detected_at
        );
    ELSIF TG_TABLE_NAME = 'research_dossiers' THEN
        IF TG_OP = 'INSERT' THEN
            event_type := 'dossier_created';
        ELSE
            event_type := 'dossier_updated';
        END IF;
        payload := jsonb_build_object(
            'dossier_id', NEW.id,
            'slug', NEW.slug,
            'topic_category', NEW.topic_category,
            'public_safe', NEW.public_safe,
            'event_type', event_type,
            'occurred_at', NEW.updated_at
        );
    ELSE
        RETURN NEW;
    END IF;

    PERFORM pg_notify('intel_event', payload::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION notify_cognitive_event()
RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
    event_type TEXT;
BEGIN
    IF TG_TABLE_NAME = 'cross_dossier_theses' THEN
        event_type := 'thesis_' || TG_OP;
        payload := jsonb_build_object(
            'thesis_id', NEW.id,
            'table', 'cross_dossier_theses',
            'event_type', event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'wr_anomaly_alerts' THEN
        event_type := 'alert_' || TG_OP;
        payload := jsonb_build_object(
            'alert_id', NEW.id,
            'severity', NEW.severity,
            'table', 'wr_anomaly_alerts',
            'event_type', event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'weekly_strategic_briefs' THEN
        event_type := 'brief_' || TG_OP;
        payload := jsonb_build_object(
            'brief_id', NEW.id,
            'week_of', NEW.week_of,
            'table', 'weekly_strategic_briefs',
            'event_type', event_type,
            'occurred_at', NOW()
        );
    ELSIF TG_TABLE_NAME = 'ultra_moves' THEN
        event_type := 'ultra_move_' || TG_OP;
        payload := jsonb_build_object(
            'move_id', NEW.id,
            'zero_decision', NEW.zero_decision,
            'table', 'ultra_moves',
            'event_type', event_type,
            'occurred_at', NOW()
        );
    ELSE
        RETURN NEW;
    END IF;

    PERFORM pg_notify('cognitive_event', payload::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
