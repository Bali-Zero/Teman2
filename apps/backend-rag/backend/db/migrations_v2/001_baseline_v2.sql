-- Migration: 001_baseline_v2
-- Description: Consolidated V2 Schema Baseline (Squashed V1)
-- Date: 2026-01-25
-- Note: This is the definitive source of truth for the Nuzantara V2 Database Schema.

--
-- PostgreSQL database dump
--



-- Dumped from database version 15.15
-- Dumped by pg_dump version 15.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: content_category; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.content_category AS ENUM (
    'IMMIGRATION',
    'TAX',
    'BUSINESS',
    'PROPERTY',
    'LEGAL',
    'BALI_NEWS',
    'LIFESTYLE',
    'GENERAL'
);


--
-- Name: content_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.content_status AS ENUM (
    'INTAKE',
    'DRAFT',
    'REVIEW',
    'APPROVED',
    'SCHEDULED',
    'PUBLISHED',
    'ARCHIVED'
);


--
-- Name: content_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.content_type AS ENUM (
    'ARTICLE',
    'SOCIAL_POST',
    'NEWSLETTER',
    'PODCAST_SCRIPT',
    'VIDEO_SCRIPT',
    'THREAD'
);


--
-- Name: distribution_platform; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.distribution_platform AS ENUM (
    'TWITTER',
    'LINKEDIN',
    'INSTAGRAM',
    'TIKTOK',
    'TELEGRAM',
    'NEWSLETTER',
    'WEBSITE',
    'YOUTUBE'
);


--
-- Name: distribution_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.distribution_status AS ENUM (
    'PENDING',
    'SCHEDULED',
    'IN_PROGRESS',
    'PUBLISHED',
    'FAILED',
    'CANCELLED'
);


--
-- Name: auto_logout_expired_sessions(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auto_logout_expired_sessions() RETURNS TABLE(out_user_id character varying, out_email character varying, out_clock_in_time timestamp with time zone, out_auto_logout_time timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Find users who clocked in but didn't clock out, and it's past 18:30 Bali time
    RETURN QUERY
    WITH latest_actions AS (
        SELECT DISTINCT ON (t.user_id)
            t.user_id AS la_user_id,
            t.email AS la_email,
            t.timestamp AS la_timestamp,
            t.action_type AS la_action_type
        FROM team_timesheet t
        ORDER BY t.user_id, t.timestamp DESC
    ),
    expired_sessions AS (
        SELECT
            la.la_user_id,
            la.la_email,
            la.la_timestamp as clock_in_time,
            (DATE(la.la_timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00') AT TIME ZONE 'Asia/Makassar' as target_logout
        FROM latest_actions la
        WHERE la.la_action_type = 'clock_in'
          AND NOW() AT TIME ZONE 'Asia/Makassar' > (DATE(la.la_timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00')
    ),
    inserted AS (
        INSERT INTO team_timesheet (user_id, email, action_type, timestamp, notes)
        SELECT
            es.la_user_id,
            es.la_email,
            'clock_out',
            es.target_logout,
            'Auto-logout at 18:30 Bali time'
        FROM expired_sessions es
        RETURNING team_timesheet.user_id, team_timesheet.email, team_timesheet.timestamp
    )
    SELECT
        i.user_id::VARCHAR AS out_user_id,
        i.email::VARCHAR AS out_email,
        es.clock_in_time AS out_clock_in_time,
        i.timestamp AS out_auto_logout_time
    FROM inserted i
    JOIN expired_sessions es ON i.user_id = es.la_user_id;
END;
$$;


--
-- Name: generate_news_slug(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_news_slug(title text) RETURNS text
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN lower(regexp_replace(
        regexp_replace(title, '[^a-zA-Z0-9\s-]', '', 'g'),
        '\s+', '-', 'g'
    )) || '-' || substring(md5(random()::text) from 1 for 6);
END;
$$;


--
-- Name: get_content_with_distribution_status(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_content_with_distribution_status(p_content_id uuid) RETURNS TABLE(content_json jsonb, distributions_json jsonb)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        to_jsonb(c.*) as content_json,
        COALESCE(
            jsonb_agg(to_jsonb(cd.*)) FILTER (WHERE cd.id IS NOT NULL),
            '[]'::jsonb
        ) as distributions_json
    FROM zantara_content c
    LEFT JOIN content_distributions cd ON cd.content_id = c.id
    WHERE c.id = p_content_id
    GROUP BY c.id;
END;
$$;


--
-- Name: get_conversation_messages(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_conversation_messages(session_uuid uuid) RETURNS jsonb
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    result jsonb;
    table_exists boolean;
BEGIN
    -- Check if conversation_history table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_name = 'conversation_history'
    ) INTO table_exists;
    
    IF table_exists THEN
        BEGIN
            SELECT jsonb_agg(
                jsonb_build_object(
                    'role', ch.role,
                    'content', ch.content
                ) ORDER BY ch.created_at
            ) INTO result
            FROM conversation_history ch 
            WHERE ch.session_id = session_uuid;
        EXCEPTION WHEN OTHERS THEN
            result := NULL;
        END;
    ELSE
        result := NULL;
    END IF;
    
    RETURN COALESCE(result, '[]'::jsonb);
END;
$$;


--
-- Name: get_pending_distributions(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_pending_distributions() RETURNS TABLE(id uuid, content_id uuid, platform public.distribution_platform, scheduled_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        cd.id,
        cd.content_id,
        cd.platform,
        cd.scheduled_at
    FROM content_distributions cd
    WHERE cd.status IN ('SCHEDULED', 'PENDING')
        AND cd.scheduled_at <= NOW()
    ORDER BY cd.scheduled_at ASC;
END;
$$;


--
-- Name: get_pending_scheduled_content(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_pending_scheduled_content() RETURNS TABLE(id uuid, title text, scheduled_at timestamp with time zone, category public.content_category)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.title,
        c.scheduled_at,
        c.category
    FROM zantara_content c
    WHERE c.status = 'SCHEDULED'
        AND c.scheduled_at <= NOW()
    ORDER BY c.scheduled_at ASC;
END;
$$;


--
-- Name: get_user_memory_entities(character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_user_memory_entities(p_user_id character varying) RETURNS TABLE(entity_id character varying, entity_type character varying, entity_name text, mention_count bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        ke.id,
        ke.type,
        ke.name,
        COUNT(*)::BIGINT as mention_count
    FROM memory_facts mf
    CROSS JOIN UNNEST(mf.related_entities) AS entity_id_val
    JOIN kg_entities ke ON ke.id = entity_id_val
    WHERE mf.user_id = p_user_id
    GROUP BY ke.id, ke.type, ke.name
    ORDER BY mention_count DESC;
END;
$$;


--
-- Name: news_items_before_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.news_items_before_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.slug IS NULL OR NEW.slug = '' THEN
        NEW.slug := generate_news_slug(NEW.title);
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: news_items_update_timestamp(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.news_items_update_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_collective_memory_stats(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_collective_memory_stats() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Update source count
    UPDATE collective_memories
    SET
        source_count = (
            SELECT COUNT(DISTINCT user_id)
            FROM collective_memory_sources
            WHERE memory_id = NEW.memory_id AND action IN ('contribute', 'confirm')
        ),
        last_confirmed_at = NOW(),
        -- Auto-promote when 3+ sources
        is_promoted = (
            SELECT COUNT(DISTINCT user_id) >= 3
            FROM collective_memory_sources
            WHERE memory_id = NEW.memory_id AND action IN ('contribute', 'confirm')
        ),
        -- Adjust confidence based on confirmations vs refutations
        confidence = LEAST(1.0, GREATEST(0.0,
            0.5 + (
                (SELECT COUNT(*) FROM collective_memory_sources WHERE memory_id = NEW.memory_id AND action IN ('contribute', 'confirm')) * 0.1
            ) - (
                (SELECT COUNT(*) FROM collective_memory_sources WHERE memory_id = NEW.memory_id AND action = 'refute') * 0.15
            )
        ))
    WHERE id = NEW.memory_id;

    RETURN NEW;
END;
$$;


--
-- Name: update_episodic_memories_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_episodic_memories_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_zantara_content_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_zantara_content_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: clients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clients (
    id integer NOT NULL,
    uuid uuid DEFAULT public.uuid_generate_v4(),
    full_name character varying(255) NOT NULL,
    email character varying(255),
    phone character varying(50),
    whatsapp character varying(50),
    nationality character varying(100),
    passport_number character varying(100),
    status character varying(50) DEFAULT 'active'::character varying,
    client_type character varying(50) DEFAULT 'individual'::character varying,
    assigned_to character varying(255),
    first_contact_date timestamp with time zone,
    last_interaction_date timestamp with time zone,
    address text,
    notes text,
    tags jsonb DEFAULT '[]'::jsonb,
    custom_fields jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by character varying(255),
    avatar_url text,
    google_drive_folder_id character varying(100),
    date_of_birth date,
    passport_expiry date,
    company_name character varying(255),
    CONSTRAINT clients_email_or_phone CHECK (((email IS NOT NULL) OR (phone IS NOT NULL)))
);


--
-- Name: practice_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.practice_types (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    category character varying(100),
    description text,
    base_price numeric(12,2),
    currency character varying(10) DEFAULT 'IDR'::character varying,
    duration_days integer,
    required_documents jsonb DEFAULT '[]'::jsonb,
    active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: practices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.practices (
    id integer NOT NULL,
    uuid uuid DEFAULT public.uuid_generate_v4(),
    client_id integer NOT NULL,
    practice_type_id integer NOT NULL,
    status character varying(50) DEFAULT 'inquiry'::character varying,
    priority character varying(20) DEFAULT 'normal'::character varying,
    inquiry_date timestamp with time zone DEFAULT now(),
    start_date timestamp with time zone,
    completion_date timestamp with time zone,
    expiry_date date,
    next_renewal_date date,
    quoted_price numeric(12,2),
    actual_price numeric(12,2),
    currency character varying(10) DEFAULT 'IDR'::character varying,
    payment_status character varying(50) DEFAULT 'unpaid'::character varying,
    paid_amount numeric(12,2) DEFAULT 0,
    assigned_to character varying(255),
    documents jsonb DEFAULT '[]'::jsonb,
    missing_documents jsonb DEFAULT '[]'::jsonb,
    notes text,
    internal_notes text,
    custom_fields jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by character varying(255)
);


--
-- Name: active_practices_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.active_practices_view AS
 SELECT p.id,
    p.uuid,
    p.status,
    p.priority,
    pt.name AS practice_type,
    pt.category,
    c.full_name AS client_name,
    c.email AS client_email,
    c.phone AS client_phone,
    p.assigned_to,
    p.start_date,
    p.expiry_date,
    p.actual_price,
    p.payment_status
   FROM ((public.practices p
     JOIN public.clients c ON ((p.client_id = c.id)))
     JOIN public.practice_types pt ON ((p.practice_type_id = pt.id)))
  WHERE ((p.status)::text <> ALL ((ARRAY['completed'::character varying, 'cancelled'::character varying])::text[]));


--
-- Name: activity_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_log (
    id integer NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id integer NOT NULL,
    action character varying(50) NOT NULL,
    performed_by character varying(255) NOT NULL,
    changes jsonb,
    description text,
    performed_at timestamp with time zone DEFAULT now()
);


--
-- Name: activity_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: activity_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_log_id_seq OWNED BY public.activity_log.id;


--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_events (
    id integer NOT NULL,
    event_type character varying(100) NOT NULL,
    user_id character varying(255),
    resource_id character varying(255),
    action character varying(50) NOT NULL,
    details jsonb DEFAULT '{}'::jsonb,
    ip_address character varying(45),
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE audit_events; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.audit_events IS 'General system audit trail for compliance and security';


--
-- Name: audit_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_events_id_seq OWNED BY public.audit_events.id;


--
-- Name: auth_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_audit_log (
    id integer NOT NULL,
    user_id character varying(255),
    email character varying(255) NOT NULL,
    action character varying(50) NOT NULL,
    ip_address character varying(45),
    user_agent text,
    "timestamp" timestamp with time zone DEFAULT now(),
    success boolean DEFAULT false,
    failure_reason text,
    metadata jsonb DEFAULT '{}'::jsonb
);


--
-- Name: TABLE auth_audit_log; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.auth_audit_log IS 'Security log for all authentication attempts';


--
-- Name: auth_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_audit_log_id_seq OWNED BY public.auth_audit_log.id;


--
-- Name: automation_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.automation_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    run_type text NOT NULL,
    status text NOT NULL,
    items_processed integer DEFAULT 0,
    items_succeeded integer DEFAULT 0,
    items_failed integer DEFAULT 0,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    duration_seconds integer,
    error_message text,
    logs jsonb,
    CONSTRAINT automation_runs_items_failed_check CHECK ((items_failed >= 0)),
    CONSTRAINT automation_runs_items_processed_check CHECK ((items_processed >= 0)),
    CONSTRAINT automation_runs_items_succeeded_check CHECK ((items_succeeded >= 0)),
    CONSTRAINT automation_runs_status_check CHECK ((status = ANY (ARRAY['running'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))
);


--
-- Name: TABLE automation_runs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.automation_runs IS 'Automated pipeline execution logs';


--
-- Name: business_structures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_structures (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    name_indonesian character varying(255),
    minimum_capital character varying(100),
    minimum_investment character varying(100),
    ownership_rules text,
    requirements text[],
    timeline_details jsonb,
    timeline_total character varying(100),
    costs jsonb,
    advantages text[],
    restrictions text[],
    structure_info text,
    purpose text,
    metadata jsonb DEFAULT '{}'::jsonb,
    last_updated timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE business_structures; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.business_structures IS 'Business entity types (PT PMA, Local PT, CV, etc)';


--
-- Name: business_structures_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.business_structures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: business_structures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.business_structures_id_seq OWNED BY public.business_structures.id;


--
-- Name: client_family_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.client_family_members (
    id integer NOT NULL,
    client_id integer NOT NULL,
    full_name character varying(255) NOT NULL,
    relationship character varying(50) NOT NULL,
    date_of_birth date,
    nationality character varying(100),
    passport_number character varying(100),
    passport_expiry date,
    current_visa_type character varying(50),
    visa_expiry date,
    email character varying(255),
    phone character varying(50),
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by character varying(255)
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id integer NOT NULL,
    client_id integer,
    practice_id integer,
    document_type character varying(100) NOT NULL,
    file_name character varying(255),
    storage_type character varying(50),
    file_id character varying(500),
    file_url text,
    file_size_kb integer,
    mime_type character varying(100),
    status character varying(50) DEFAULT 'pending'::character varying,
    uploaded_by character varying(255),
    verified_by character varying(255),
    verified_at timestamp with time zone,
    expiry_date date,
    notes text,
    rejection_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    document_category character varying(50),
    family_member_id integer,
    google_drive_file_url text,
    is_archived boolean DEFAULT false
);


--
-- Name: client_expiry_alerts_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.client_expiry_alerts_view AS
 SELECT 'client'::text AS entity_type,
    c.id AS entity_id,
    c.full_name AS entity_name,
    c.id AS client_id,
    c.full_name AS client_name,
    'passport'::text AS document_type,
    c.passport_expiry AS expiry_date,
    (c.passport_expiry - CURRENT_DATE) AS days_until_expiry,
        CASE
            WHEN (c.passport_expiry <= CURRENT_DATE) THEN 'expired'::text
            WHEN (c.passport_expiry <= (CURRENT_DATE + '8 mons'::interval)) THEN 'red'::text
            WHEN (c.passport_expiry <= (CURRENT_DATE + '1 year'::interval)) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM public.clients c
  WHERE ((c.passport_expiry IS NOT NULL) AND ((c.status)::text = 'active'::text))
UNION ALL
 SELECT 'family_member'::text AS entity_type,
    fm.id AS entity_id,
    fm.full_name AS entity_name,
    fm.client_id,
    c.full_name AS client_name,
    'passport'::text AS document_type,
    fm.passport_expiry AS expiry_date,
    (fm.passport_expiry - CURRENT_DATE) AS days_until_expiry,
        CASE
            WHEN (fm.passport_expiry <= CURRENT_DATE) THEN 'expired'::text
            WHEN (fm.passport_expiry <= (CURRENT_DATE + '8 mons'::interval)) THEN 'red'::text
            WHEN (fm.passport_expiry <= (CURRENT_DATE + '1 year'::interval)) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM (public.client_family_members fm
     JOIN public.clients c ON ((fm.client_id = c.id)))
  WHERE (fm.passport_expiry IS NOT NULL)
UNION ALL
 SELECT 'family_member'::text AS entity_type,
    fm.id AS entity_id,
    fm.full_name AS entity_name,
    fm.client_id,
    c.full_name AS client_name,
    'visa'::text AS document_type,
    fm.visa_expiry AS expiry_date,
    (fm.visa_expiry - CURRENT_DATE) AS days_until_expiry,
        CASE
            WHEN (fm.visa_expiry <= CURRENT_DATE) THEN 'expired'::text
            WHEN (fm.visa_expiry <= (CURRENT_DATE + '8 mons'::interval)) THEN 'red'::text
            WHEN (fm.visa_expiry <= (CURRENT_DATE + '1 year'::interval)) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM (public.client_family_members fm
     JOIN public.clients c ON ((fm.client_id = c.id)))
  WHERE (fm.visa_expiry IS NOT NULL)
UNION ALL
 SELECT 'document'::text AS entity_type,
    d.id AS entity_id,
    d.document_type AS entity_name,
    d.client_id,
    c.full_name AS client_name,
    d.document_type,
    d.expiry_date,
    (d.expiry_date - CURRENT_DATE) AS days_until_expiry,
        CASE
            WHEN (d.expiry_date <= CURRENT_DATE) THEN 'expired'::text
            WHEN (d.expiry_date <= (CURRENT_DATE + '8 mons'::interval)) THEN 'red'::text
            WHEN (d.expiry_date <= (CURRENT_DATE + '1 year'::interval)) THEN 'yellow'::text
            ELSE 'green'::text
        END AS alert_color,
    c.assigned_to
   FROM (public.documents d
     JOIN public.clients c ON ((d.client_id = c.id)))
  WHERE ((d.expiry_date IS NOT NULL) AND ((d.status)::text <> 'rejected'::text) AND ((d.is_archived IS NULL) OR (d.is_archived = false)));


--
-- Name: client_family_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.client_family_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: client_family_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.client_family_members_id_seq OWNED BY public.client_family_members.id;


--
-- Name: client_profile_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.client_profile_view AS
 SELECT c.id,
    c.uuid,
    c.full_name,
    c.email,
    c.phone,
    c.whatsapp,
    c.nationality,
    c.passport_number,
    c.passport_expiry,
    c.date_of_birth,
    c.avatar_url,
    c.company_name,
    c.google_drive_folder_id,
    c.status,
    c.client_type,
    c.assigned_to,
    c.notes,
    c.tags,
    c.created_at,
    c.updated_at,
    ( SELECT count(*) AS count
           FROM public.client_family_members fm
          WHERE (fm.client_id = c.id)) AS family_members_count,
    ( SELECT count(*) AS count
           FROM public.documents d
          WHERE ((d.client_id = c.id) AND ((d.is_archived IS NULL) OR (d.is_archived = false)))) AS documents_count,
    ( SELECT count(*) AS count
           FROM public.practices p
          WHERE (p.client_id = c.id)) AS practices_count,
    ( SELECT count(*) AS count
           FROM public.practices p
          WHERE ((p.client_id = c.id) AND ((p.status)::text <> ALL ((ARRAY['completed'::character varying, 'cancelled'::character varying])::text[])))) AS active_practices_count,
    ( SELECT count(*) AS count
           FROM public.client_expiry_alerts_view e
          WHERE ((e.client_id = c.id) AND (e.alert_color = 'red'::text))) AS red_alerts_count,
    ( SELECT count(*) AS count
           FROM public.client_expiry_alerts_view e
          WHERE ((e.client_id = c.id) AND (e.alert_color = 'yellow'::text))) AS yellow_alerts_count,
    ( SELECT count(*) AS count
           FROM public.client_expiry_alerts_view e
          WHERE ((e.client_id = c.id) AND (e.alert_color = 'expired'::text))) AS expired_count
   FROM public.clients c;


--
-- Name: client_summary_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.client_summary_view AS
SELECT
    NULL::integer AS id,
    NULL::uuid AS uuid,
    NULL::character varying(255) AS full_name,
    NULL::character varying(255) AS email,
    NULL::character varying(50) AS phone,
    NULL::character varying(50) AS status,
    NULL::character varying(255) AS assigned_to,
    NULL::timestamp with time zone AS first_contact_date,
    NULL::timestamp with time zone AS last_interaction_date,
    NULL::bigint AS total_practices,
    NULL::bigint AS active_practices,
    NULL::bigint AS total_interactions,
    NULL::timestamp with time zone AS last_interaction;


--
-- Name: clients_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clients_id_seq OWNED BY public.clients.id;


--
-- Name: collective_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collective_memories (
    id integer NOT NULL,
    content text NOT NULL,
    content_hash character varying(64) NOT NULL,
    category character varying(100) DEFAULT 'general'::character varying,
    confidence double precision DEFAULT 0.5,
    source_count integer DEFAULT 1,
    is_promoted boolean DEFAULT false,
    first_learned_at timestamp with time zone DEFAULT now(),
    last_confirmed_at timestamp with time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb,
    embedding_synced boolean DEFAULT false,
    CONSTRAINT collective_memories_confidence_check CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


--
-- Name: COLUMN collective_memories.category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.collective_memories.category IS 'Categories: process, location, provider, regulation, tip, pricing, timeline, general';


--
-- Name: COLUMN collective_memories.embedding_synced; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.collective_memories.embedding_synced IS 'TRUE when embedding has been synced to Qdrant collective_memories collection';


--
-- Name: collective_memories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.collective_memories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: collective_memories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.collective_memories_id_seq OWNED BY public.collective_memories.id;


--
-- Name: collective_memory_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collective_memory_sources (
    id integer NOT NULL,
    memory_id integer,
    user_id character varying(255) NOT NULL,
    conversation_id integer,
    action character varying(20) DEFAULT 'contribute'::character varying,
    contributed_at timestamp with time zone DEFAULT now()
);


--
-- Name: collective_memory_sources_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.collective_memory_sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: collective_memory_sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.collective_memory_sources_id_seq OWNED BY public.collective_memory_sources.id;


--
-- Name: company_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.company_profiles (
    id integer NOT NULL,
    company_name character varying(255) NOT NULL,
    entity_type character varying(50),
    industry character varying(100),
    annual_revenue bigint,
    profit_margin double precision,
    has_rnd boolean DEFAULT false,
    has_training boolean DEFAULT false,
    has_parent_abroad boolean DEFAULT false,
    parent_country character varying(100),
    has_related_parties boolean DEFAULT false,
    related_party_transactions bigint,
    entertainment_expense bigint,
    cash_transactions bigint,
    vat_gap bigint,
    previous_audit boolean DEFAULT false,
    previous_audit_findings integer DEFAULT 0,
    user_id character varying(255),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE company_profiles; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.company_profiles IS 'Company profiles for tax analysis';


--
-- Name: company_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.company_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: company_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.company_profiles_id_seq OWNED BY public.company_profiles.id;


--
-- Name: compliance_deadlines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compliance_deadlines (
    id integer NOT NULL,
    deadline_type character varying(50) NOT NULL,
    deadline_day character varying(50),
    task_name character varying(255) NOT NULL,
    applies_to text,
    platform character varying(100),
    penalty text,
    recurring boolean DEFAULT true,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE compliance_deadlines; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.compliance_deadlines IS 'Recurring compliance deadlines calendar';


--
-- Name: compliance_deadlines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.compliance_deadlines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: compliance_deadlines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.compliance_deadlines_id_seq OWNED BY public.compliance_deadlines.id;


--
-- Name: content_analytics_daily; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content_analytics_daily (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    content_id uuid NOT NULL,
    date date NOT NULL,
    views integer DEFAULT 0,
    unique_views integer DEFAULT 0,
    engagement_events integer DEFAULT 0,
    conversion_events integer DEFAULT 0,
    platform_metrics jsonb,
    engagement_rate numeric(5,2),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT content_analytics_daily_unique_views_check CHECK ((unique_views >= 0)),
    CONSTRAINT content_analytics_daily_views_check CHECK ((views >= 0))
);


--
-- Name: TABLE content_analytics_daily; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.content_analytics_daily IS 'Daily aggregated content performance metrics';


--
-- Name: content_distributions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content_distributions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    content_id uuid NOT NULL,
    platform public.distribution_platform NOT NULL,
    platform_post_id text,
    platform_url text,
    status public.distribution_status DEFAULT 'PENDING'::public.distribution_status NOT NULL,
    scheduled_at timestamp with time zone,
    published_at timestamp with time zone,
    config jsonb,
    error_message text,
    retry_count integer DEFAULT 0,
    views integer DEFAULT 0,
    likes integer DEFAULT 0,
    shares integer DEFAULT 0,
    comments integer DEFAULT 0,
    engagement_rate numeric(5,2),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT content_distributions_retry_count_check CHECK ((retry_count >= 0))
);


--
-- Name: TABLE content_distributions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.content_distributions IS 'Track multi-platform content distribution';


--
-- Name: content_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    content_id uuid NOT NULL,
    version_number integer NOT NULL,
    title text NOT NULL,
    body text,
    summary text,
    changed_by text,
    change_description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE content_versions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.content_versions IS 'Content editing history and version control';


--
-- Name: conversation_ratings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_ratings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    session_id uuid NOT NULL,
    user_id uuid,
    rating integer NOT NULL,
    feedback_type character varying(20),
    feedback_text text,
    turn_count integer,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT conversation_ratings_rating_check CHECK (((rating >= 1) AND (rating <= 5)))
);


--
-- Name: TABLE conversation_ratings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.conversation_ratings IS 'User ratings and feedback for conversations, used by ConversationTrainer agent';


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id integer NOT NULL,
    user_id character varying(255) NOT NULL,
    session_id character varying(255),
    messages jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE conversations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.conversations IS 'Full conversation history for context retrieval';


--
-- Name: conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conversations_id_seq OWNED BY public.conversations.id;


--
-- Name: crm_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crm_settings (
    id integer NOT NULL,
    key character varying(100) NOT NULL,
    value jsonb NOT NULL,
    description text,
    updated_at timestamp with time zone DEFAULT now(),
    updated_by character varying(255)
);


--
-- Name: crm_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crm_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crm_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crm_settings_id_seq OWNED BY public.crm_settings.id;


--
-- Name: cultural_knowledge; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cultural_knowledge (
    id integer NOT NULL,
    content text NOT NULL,
    language character varying(10) DEFAULT 'en'::character varying,
    category character varying(50),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: cultural_knowledge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cultural_knowledge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cultural_knowledge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cultural_knowledge_id_seq OWNED BY public.cultural_knowledge.id;


--
-- Name: team_timesheet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_timesheet (
    id integer NOT NULL,
    user_id character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    action_type character varying(20) NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT team_timesheet_action_type_check CHECK (((action_type)::text = ANY ((ARRAY['clock_in'::character varying, 'clock_out'::character varying])::text[])))
);


--
-- Name: TABLE team_timesheet; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.team_timesheet IS 'Team work hours tracking (clock-in/clock-out only, Bali timezone UTC+8)';


--
-- Name: COLUMN team_timesheet.action_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_timesheet.action_type IS 'Either clock_in or clock_out';


--
-- Name: COLUMN team_timesheet.metadata; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_timesheet.metadata IS 'JSON: {ip_address, user_agent, auto_logout: bool}';


--
-- Name: daily_work_hours; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.daily_work_hours AS
 SELECT shifts.user_id,
    shifts.email,
    date(shifts.clock_in_bali) AS work_date,
    shifts.clock_in_bali,
        CASE
            WHEN ((shifts.next_action_type)::text = 'clock_out'::text) THEN shifts.clock_out_bali
            ELSE NULL::timestamp without time zone
        END AS clock_out_bali,
        CASE
            WHEN ((shifts.next_action_type)::text = 'clock_out'::text) THEN round((EXTRACT(epoch FROM (shifts.clock_out_bali - shifts.clock_in_bali)) / (3600)::numeric), 2)
            ELSE NULL::numeric
        END AS hours_worked
   FROM ( SELECT team_timesheet.user_id,
            team_timesheet.email,
            (team_timesheet."timestamp" AT TIME ZONE 'Asia/Makassar'::text) AS clock_in_bali,
            lead((team_timesheet."timestamp" AT TIME ZONE 'Asia/Makassar'::text)) OVER (PARTITION BY team_timesheet.user_id ORDER BY team_timesheet."timestamp") AS clock_out_bali,
            team_timesheet.action_type,
            lead(team_timesheet.action_type) OVER (PARTITION BY team_timesheet.user_id ORDER BY team_timesheet."timestamp") AS next_action_type
           FROM public.team_timesheet) shifts
  WHERE ((shifts.action_type)::text = 'clock_in'::text);


--
-- Name: VIEW daily_work_hours; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.daily_work_hours IS 'Daily hours v3: Includes active/incomplete sessions for visibility';


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    drive_folders jsonb DEFAULT '[]'::jsonb,
    can_see_all boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: departments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.departments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: departments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.departments_id_seq OWNED BY public.departments.id;


--
-- Name: document_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_categories (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    category_group character varying(50) NOT NULL,
    description text,
    required_for jsonb DEFAULT '[]'::jsonb,
    has_expiry boolean DEFAULT false,
    sort_order integer DEFAULT 0,
    active boolean DEFAULT true
);


--
-- Name: document_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.document_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: document_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_categories_id_seq OWNED BY public.document_categories.id;


--
-- Name: document_language_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_language_mappings (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    document_id character varying(255) NOT NULL,
    source_language character varying(10) DEFAULT 'id'::character varying,
    document_type character varying(50) NOT NULL,
    jurisdiction character varying(50) DEFAULT 'indonesia'::character varying,
    effective_date date,
    expiry_date date,
    translation_available boolean DEFAULT false,
    quality_score integer,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT document_language_mappings_document_type_check CHECK (((document_type)::text = ANY ((ARRAY['law'::character varying, 'regulation'::character varying, 'policy'::character varying, 'contract'::character varying, 'guideline'::character varying])::text[]))),
    CONSTRAINT document_language_mappings_quality_score_check CHECK (((quality_score >= 1) AND (quality_score <= 5)))
);


--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- Name: email_activity_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.email_activity_log (
    id integer NOT NULL,
    user_id integer NOT NULL,
    user_email text NOT NULL,
    operation character varying(50) NOT NULL,
    email_subject text,
    recipient_email text,
    has_attachments boolean DEFAULT false,
    attachment_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE email_activity_log; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.email_activity_log IS 'Tracks email operations per user for weekly activity reports';


--
-- Name: email_activity_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.email_activity_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_activity_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.email_activity_log_id_seq OWNED BY public.email_activity_log.id;


--
-- Name: episodic_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.episodic_memories (
    id integer NOT NULL,
    user_id character varying(255) NOT NULL,
    event_type character varying(100) DEFAULT 'general'::character varying NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    emotion character varying(50) DEFAULT 'neutral'::character varying,
    occurred_at timestamp with time zone NOT NULL,
    related_entities jsonb DEFAULT '[]'::jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    kg_entity_ids character varying(64)[] DEFAULT '{}'::character varying[]
);


--
-- Name: TABLE episodic_memories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.episodic_memories IS 'Timeline of user events and experiences for temporal memory';


--
-- Name: COLUMN episodic_memories.event_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.episodic_memories.event_type IS 'Type: milestone, problem, resolution, decision, meeting, deadline, discovery';


--
-- Name: COLUMN episodic_memories.emotion; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.episodic_memories.emotion IS 'Emotional context: positive, negative, neutral, urgent, frustrated, excited, worried';


--
-- Name: COLUMN episodic_memories.occurred_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.episodic_memories.occurred_at IS 'When the event happened (user-specified or AI-extracted)';


--
-- Name: COLUMN episodic_memories.related_entities; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.episodic_memories.related_entities IS 'Links to kg_entities: [{"entity_id": 123, "entity_type": "kbli"}]';


--
-- Name: episodic_memories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.episodic_memories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: episodic_memories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.episodic_memories_id_seq OWNED BY public.episodic_memories.id;


--
-- Name: folder_access_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.folder_access_rules (
    id integer NOT NULL,
    user_email character varying(255),
    department_code character varying(50),
    role character varying(50),
    allowed_folders text[] NOT NULL,
    context_folder character varying(255),
    priority integer DEFAULT 0,
    active boolean DEFAULT true,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: TABLE folder_access_rules; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.folder_access_rules IS 'Granular folder visibility rules for Google Drive access';


--
-- Name: COLUMN folder_access_rules.allowed_folders; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.folder_access_rules.allowed_folders IS 'Array of folder names user can see (case-insensitive match)';


--
-- Name: COLUMN folder_access_rules.context_folder; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.folder_access_rules.context_folder IS 'NULL=root level, or folder name for nested visibility rules';


--
-- Name: folder_access_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.folder_access_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: folder_access_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.folder_access_rules_id_seq OWNED BY public.folder_access_rules.id;


--
-- Name: golden_routes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.golden_routes (
    route_id text NOT NULL,
    canonical_query text NOT NULL,
    document_ids text[] DEFAULT '{}'::text[],
    chapter_ids text[] DEFAULT '{}'::text[],
    collections text[] DEFAULT '{legal_unified}'::text[],
    routing_hints jsonb DEFAULT '{}'::jsonb,
    usage_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: google_drive_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.google_drive_tokens (
    user_id text NOT NULL,
    access_token text,
    refresh_token text NOT NULL,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE google_drive_tokens; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.google_drive_tokens IS 'OAuth tokens for Google Drive API access. SYSTEM user provides shared access for all team members.';


--
-- Name: immigration_issues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.immigration_issues (
    id integer NOT NULL,
    issue_type character varying(50) NOT NULL,
    reason_or_cause text NOT NULL,
    solution text NOT NULL,
    frequency_pct double precision,
    impact_days integer,
    prevention text,
    steps text[],
    timeline character varying(100),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE immigration_issues; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.immigration_issues IS 'Common visa/immigration issues and solutions';


--
-- Name: immigration_issues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.immigration_issues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: immigration_issues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.immigration_issues_id_seq OWNED BY public.immigration_issues.id;


--
-- Name: immigration_offices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.immigration_offices (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    address text,
    city character varying(100),
    province character varying(100) DEFAULT 'Bali'::character varying,
    hours character varying(255),
    best_time character varying(255),
    avoid_time character varying(255),
    parking text,
    tips text[],
    less_crowded boolean DEFAULT false,
    services text[],
    lat double precision,
    lng double precision,
    metadata jsonb DEFAULT '{}'::jsonb,
    last_updated timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE immigration_offices; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.immigration_offices IS 'Immigration office locations and practical information';


--
-- Name: immigration_offices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.immigration_offices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: immigration_offices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.immigration_offices_id_seq OWNED BY public.immigration_offices.id;


--
-- Name: indonesian_licenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.indonesian_licenses (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    full_name character varying(255) NOT NULL,
    purpose text,
    validity character varying(100),
    process_info text,
    requirements text[],
    required_for text,
    restrictions text[],
    status character varying(50),
    integrated_into character varying(50),
    applicable_sectors text[],
    metadata jsonb DEFAULT '{}'::jsonb,
    last_updated timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE indonesian_licenses; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.indonesian_licenses IS 'Business licenses and permits information';


--
-- Name: indonesian_licenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.indonesian_licenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: indonesian_licenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.indonesian_licenses_id_seq OWNED BY public.indonesian_licenses.id;


--
-- Name: intel_signals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.intel_signals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    summary text,
    category public.content_category NOT NULL,
    source_name text NOT NULL,
    source_url text,
    source_tier integer,
    confidence_score numeric(3,2),
    priority integer DEFAULT 5,
    processed boolean DEFAULT false,
    processed_at timestamp with time zone,
    action_taken text,
    content_id uuid,
    tags text[] DEFAULT ARRAY[]::text[],
    raw_data jsonb,
    signal_date timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT intel_signals_confidence_score_check CHECK (((confidence_score >= (0)::numeric) AND (confidence_score <= (1)::numeric))),
    CONSTRAINT intel_signals_priority_check CHECK (((priority >= 1) AND (priority <= 10))),
    CONSTRAINT intel_signals_source_tier_check CHECK ((source_tier = ANY (ARRAY[1, 2, 3])))
);


--
-- Name: TABLE intel_signals; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.intel_signals IS 'Intel signals from scraping that feed content generation';


--
-- Name: interactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interactions (
    id integer NOT NULL,
    client_id integer,
    practice_id integer,
    conversation_id integer,
    interaction_type character varying(50) NOT NULL,
    channel character varying(50),
    subject character varying(500),
    summary text,
    full_content text,
    sentiment character varying(20),
    team_member character varying(255),
    direction character varying(20),
    extracted_entities jsonb DEFAULT '{}'::jsonb,
    action_items jsonb DEFAULT '[]'::jsonb,
    interaction_date timestamp with time zone DEFAULT now(),
    duration_minutes integer,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: interactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.interactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: interactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.interactions_id_seq OWNED BY public.interactions.id;


--
-- Name: kbli_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kbli_codes (
    id integer NOT NULL,
    code character varying(10) NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    category_letter character varying(5),
    category_name character varying(255),
    foreign_eligible boolean DEFAULT false,
    minimum_investment character varying(100),
    licenses text[],
    popularity character varying(20),
    tips text,
    restrictions text,
    alternative_code character varying(10),
    metadata jsonb DEFAULT '{}'::jsonb,
    last_updated timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE kbli_codes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.kbli_codes IS 'Indonesian business classification codes (KBLI)';


--
-- Name: kbli_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kbli_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kbli_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kbli_codes_id_seq OWNED BY public.kbli_codes.id;


--
-- Name: kbli_combinations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kbli_combinations (
    id integer NOT NULL,
    package_name character varying(100) NOT NULL,
    display_name character varying(255),
    kbli_codes text[],
    description text,
    use_case text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE kbli_combinations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.kbli_combinations IS 'Pre-configured KBLI packages for common business types';


--
-- Name: kbli_combinations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kbli_combinations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kbli_combinations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kbli_combinations_id_seq OWNED BY public.kbli_combinations.id;


--
-- Name: kg_entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kg_entities (
    id character varying(64) NOT NULL,
    type character varying(32) NOT NULL,
    name text NOT NULL,
    canonical_name text,
    description text,
    mention_count integer DEFAULT 0,
    properties jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: kg_relationships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kg_relationships (
    id integer NOT NULL,
    source_entity_id character varying(64),
    target_entity_id character varying(64),
    relationship_type character varying(32) NOT NULL,
    strength double precision DEFAULT 1.0,
    properties jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: kg_relationships_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kg_relationships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kg_relationships_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kg_relationships_id_seq OWNED BY public.kg_relationships.id;


--
-- Name: knowledge_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.knowledge_feedback (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid,
    query_text text NOT NULL,
    original_answer text,
    user_correction text,
    feedback_type character varying(50) NOT NULL,
    context_documents text[],
    model_used character varying(100),
    response_time_ms integer,
    user_rating integer,
    session_id character varying(100),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    resolved boolean DEFAULT false,
    admin_notes text,
    resolution_date timestamp with time zone,
    CONSTRAINT knowledge_feedback_feedback_type_check CHECK (((feedback_type)::text = ANY ((ARRAY['factual_error'::character varying, 'clarification'::character varying, 'improvement'::character varying, 'toxicity'::character varying, 'incomplete'::character varying, 'outdated'::character varying])::text[]))),
    CONSTRAINT knowledge_feedback_user_rating_check CHECK (((user_rating >= 1) AND (user_rating <= 5)))
);


--
-- Name: media_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.media_assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    content_id uuid,
    asset_type text NOT NULL,
    file_name text,
    file_size_bytes bigint,
    mime_type text,
    storage_url text NOT NULL,
    storage_bucket text,
    storage_path text,
    generated_by text,
    generation_prompt text,
    generation_config jsonb,
    width integer,
    height integer,
    duration_seconds integer,
    usage_count integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT media_assets_asset_type_check CHECK ((asset_type = ANY (ARRAY['image'::text, 'video'::text, 'audio'::text, 'document'::text]))),
    CONSTRAINT media_assets_file_size_bytes_check CHECK ((file_size_bytes >= 0)),
    CONSTRAINT media_assets_usage_count_check CHECK ((usage_count >= 0))
);


--
-- Name: TABLE media_assets; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.media_assets IS 'Generated and uploaded media assets (images, videos)';


--
-- Name: memory_facts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memory_facts (
    id integer NOT NULL,
    user_id character varying(255) NOT NULL,
    content text NOT NULL,
    fact_type character varying(100) DEFAULT 'general'::character varying,
    confidence double precision DEFAULT 1.0,
    source character varying(50) DEFAULT 'user'::character varying,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    related_entities character varying(64)[] DEFAULT '{}'::character varying[]
);


--
-- Name: TABLE memory_facts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.memory_facts IS 'Stores individual facts extracted from conversations for persistent memory';


--
-- Name: memory_facts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.memory_facts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: memory_facts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.memory_facts_id_seq OWNED BY public.memory_facts.id;


--
-- Name: memory_facts_with_entities; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.memory_facts_with_entities AS
 SELECT mf.id,
    mf.user_id,
    mf.content,
    mf.fact_type,
    mf.confidence,
    mf.source,
    mf.metadata,
    mf.created_at,
    mf.related_entities,
    COALESCE(json_agg(json_build_object('id', ke.id, 'type', ke.type, 'name', ke.name, 'canonical_name', ke.canonical_name)) FILTER (WHERE (ke.id IS NOT NULL)), '[]'::json) AS entities
   FROM (public.memory_facts mf
     LEFT JOIN public.kg_entities ke ON (((ke.id)::text = ANY ((mf.related_entities)::text[]))))
  GROUP BY mf.id, mf.user_id, mf.content, mf.fact_type, mf.confidence, mf.source, mf.metadata, mf.created_at, mf.related_entities;


--
-- Name: migration_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.migration_log (
    id integer NOT NULL,
    migration_name character varying(255) NOT NULL,
    executed_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    checksum character varying(64),
    notes text
);


--
-- Name: migration_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.migration_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: migration_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.migration_log_id_seq OWNED BY public.migration_log.id;


--
-- Name: monthly_work_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.monthly_work_summary AS
 SELECT daily_work_hours.user_id,
    daily_work_hours.email,
    date_trunc('month'::text, (daily_work_hours.work_date)::timestamp with time zone) AS month_start,
    count(*) AS days_worked,
    round(sum(daily_work_hours.hours_worked), 2) AS total_hours,
    round(avg(daily_work_hours.hours_worked), 2) AS avg_hours_per_day
   FROM public.daily_work_hours
  GROUP BY daily_work_hours.user_id, daily_work_hours.email, (date_trunc('month'::text, (daily_work_hours.work_date)::timestamp with time zone));


--
-- Name: news_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.news_items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    slug text NOT NULL,
    summary text,
    content text,
    source text NOT NULL,
    source_url text,
    category text NOT NULL,
    priority text DEFAULT 'medium'::text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    image_url text,
    view_count integer DEFAULT 0,
    published_at timestamp with time zone,
    scraped_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    ai_summary text,
    ai_tags text[],
    ai_sentiment text,
    source_feed text,
    external_id text,
    CONSTRAINT news_items_ai_sentiment_check CHECK ((ai_sentiment = ANY (ARRAY['positive'::text, 'neutral'::text, 'negative'::text]))),
    CONSTRAINT news_items_category_check CHECK ((category = ANY (ARRAY['immigration'::text, 'business'::text, 'tax'::text, 'property'::text, 'lifestyle'::text, 'tech'::text, 'legal'::text]))),
    CONSTRAINT news_items_priority_check CHECK ((priority = ANY (ARRAY['high'::text, 'medium'::text, 'low'::text]))),
    CONSTRAINT news_items_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'archived'::text])))
);


--
-- Name: news_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.news_subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email text NOT NULL,
    categories text[] DEFAULT '{}'::text[] NOT NULL,
    frequency text DEFAULT 'daily'::text NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    unsubscribed_at timestamp with time zone,
    CONSTRAINT news_subscriptions_frequency_check CHECK ((frequency = ANY (ARRAY['instant'::text, 'daily'::text, 'weekly'::text])))
);


--
-- Name: oss_issues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oss_issues (
    id integer NOT NULL,
    issue_category character varying(50),
    error_or_issue text NOT NULL,
    solution text NOT NULL,
    frequency_description character varying(100),
    timeline character varying(100),
    browser_recommendation character varying(50),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE oss_issues; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.oss_issues IS 'Common OSS system issues and solutions';


--
-- Name: oss_issues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.oss_issues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oss_issues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.oss_issues_id_seq OWNED BY public.oss_issues.id;


--
-- Name: oss_system_info; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oss_system_info (
    id integer NOT NULL,
    key character varying(100) NOT NULL,
    value text,
    value_array text[],
    metadata jsonb DEFAULT '{}'::jsonb,
    last_updated timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE oss_system_info; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.oss_system_info IS 'OSS system metadata and configuration';


--
-- Name: oss_system_info_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.oss_system_info_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oss_system_info_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.oss_system_info_id_seq OWNED BY public.oss_system_info.id;


--
-- Name: parent_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parent_documents (
    id text NOT NULL,
    document_id text NOT NULL,
    type text,
    title text,
    full_text text,
    summary text,
    char_count integer,
    pasal_count integer,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now(),
    drive_file_id character varying(255),
    drive_web_view_link text,
    mime_type character varying(100),
    text_fingerprint character varying(64),
    is_incomplete boolean DEFAULT false,
    ocr_quality_score double precision DEFAULT 1.0,
    needs_reextract boolean DEFAULT false,
    source_id text,
    source_version character varying(32),
    ingestion_run_id character varying(64),
    is_canonical boolean DEFAULT true
);


--
-- Name: COLUMN parent_documents.text_fingerprint; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.text_fingerprint IS 'SHA256 hash of normalized text (lowercase, no spaces) for OCR duplicate detection';


--
-- Name: COLUMN parent_documents.is_incomplete; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.is_incomplete IS 'True if text contains placeholders (". . .") or missing ayat';


--
-- Name: COLUMN parent_documents.ocr_quality_score; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.ocr_quality_score IS 'Quality score 0.0-1.0: 1.0=perfect, <0.7=needs review';


--
-- Name: COLUMN parent_documents.needs_reextract; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.needs_reextract IS 'Flag for documents requiring re-extraction from better source';


--
-- Name: COLUMN parent_documents.source_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.source_id IS 'Original source identifier (file path, URL, Drive ID)';


--
-- Name: COLUMN parent_documents.source_version; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.source_version IS 'Version identifier for document (e.g., "v1", "2023-12-19", "OCR_tesseract")';


--
-- Name: COLUMN parent_documents.ingestion_run_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.ingestion_run_id IS 'Batch ingestion run ID for tracking and rollback';


--
-- Name: COLUMN parent_documents.is_canonical; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.parent_documents.is_canonical IS 'True if this is the canonical version (used in production queries)';


--
-- Name: practice_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.practice_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: practice_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.practice_types_id_seq OWNED BY public.practice_types.id;


--
-- Name: practices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.practices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: practices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.practices_id_seq OWNED BY public.practices.id;


--
-- Name: property_due_diligence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_due_diligence (
    id integer NOT NULL,
    property_listing_id integer,
    overall_risk character varying(20),
    recommendation character varying(50),
    checks jsonb,
    red_flags text[],
    opportunities text[],
    estimated_value bigint,
    confidence_score double precision,
    comparables jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE property_due_diligence; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.property_due_diligence IS 'Due diligence reports for properties';


--
-- Name: property_due_diligence_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.property_due_diligence_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: property_due_diligence_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.property_due_diligence_id_seq OWNED BY public.property_due_diligence.id;


--
-- Name: property_legal_structures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_legal_structures (
    id integer NOT NULL,
    structure_type character varying(100) NOT NULL,
    name character varying(255),
    description text,
    foreign_eligible boolean DEFAULT false,
    requirements text[],
    pros text[],
    cons text[],
    setup_cost_min bigint,
    setup_cost_max bigint,
    annual_cost_min bigint,
    annual_cost_max bigint,
    timeline_min_days integer,
    timeline_max_days integer,
    risks text[],
    applicable_property_types text[],
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE property_legal_structures; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.property_legal_structures IS 'Legal structure options for property ownership';


--
-- Name: property_legal_structures_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.property_legal_structures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: property_legal_structures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.property_legal_structures_id_seq OWNED BY public.property_legal_structures.id;


--
-- Name: property_listings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_listings (
    id integer NOT NULL,
    content_id character varying(100) NOT NULL,
    title text NOT NULL,
    location character varying(255),
    area character varying(100),
    property_type character varying(50),
    ownership character varying(50),
    price bigint,
    size_are integer,
    price_per_are bigint,
    market_position character varying(100),
    source character varying(255),
    source_url text,
    risks text[],
    opportunities text[],
    metadata jsonb DEFAULT '{}'::jsonb,
    scraped_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE property_listings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.property_listings IS 'Scraped property listings from various sources';


--
-- Name: property_listings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.property_listings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: property_listings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.property_listings_id_seq OWNED BY public.property_listings.id;


--
-- Name: property_market_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_market_data (
    id integer NOT NULL,
    area character varying(100) NOT NULL,
    avg_price_per_are bigint,
    median_price_per_are bigint,
    min_price_per_are bigint,
    max_price_per_are bigint,
    listings_count integer,
    sales_volume integer,
    trend character varying(20),
    price_change_pct double precision,
    avg_days_on_market integer,
    hotness character varying(20),
    period_start date NOT NULL,
    period_end date NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE property_market_data; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.property_market_data IS 'Time-series market data per area';


--
-- Name: property_market_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.property_market_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: property_market_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.property_market_data_id_seq OWNED BY public.property_market_data.id;


--
-- Name: query_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.query_analytics (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid,
    query_hash character varying(64),
    query_text text NOT NULL,
    response_text text,
    language_preference character varying(10),
    model_used character varying(100),
    response_time_ms integer,
    document_count integer,
    user_satisfaction integer,
    session_id character varying(100),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT query_analytics_user_satisfaction_check CHECK (((user_satisfaction >= 1) AND (user_satisfaction <= 5)))
);


--
-- Name: query_clusters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.query_clusters (
    id integer NOT NULL,
    query text NOT NULL,
    cluster_id integer,
    similarity_score double precision,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: query_clusters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.query_clusters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: query_clusters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.query_clusters_id_seq OWNED BY public.query_clusters.id;


--
-- Name: query_route_clusters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.query_route_clusters (
    cluster_id text NOT NULL,
    name text,
    description text,
    route_ids text[] DEFAULT '{}'::text[],
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: regulatory_updates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.regulatory_updates (
    id integer NOT NULL,
    update_date date NOT NULL,
    source character varying(100) NOT NULL,
    update_title text NOT NULL,
    update_description text NOT NULL,
    impact text,
    update_type character varying(50),
    impact_level character varying(20),
    url text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE regulatory_updates; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.regulatory_updates IS 'Recent regulatory changes and announcements';


--
-- Name: regulatory_updates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.regulatory_updates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: regulatory_updates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.regulatory_updates_id_seq OWNED BY public.regulatory_updates.id;


--
-- Name: renewal_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.renewal_alerts (
    id integer NOT NULL,
    practice_id integer NOT NULL,
    client_id integer NOT NULL,
    alert_type character varying(50) NOT NULL,
    description text,
    target_date date NOT NULL,
    alert_date date NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying,
    sent_at timestamp with time zone,
    notify_team_member character varying(255),
    notify_client boolean DEFAULT false,
    notification_sent boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: renewal_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.renewal_alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: renewal_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.renewal_alerts_id_seq OWNED BY public.renewal_alerts.id;


--
-- Name: review_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_queue (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_feedback_id uuid NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    priority character varying(20),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    resolution_notes text,
    CONSTRAINT review_queue_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'resolved'::character varying, 'ignored'::character varying])::text[])))
);


--
-- Name: TABLE review_queue; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.review_queue IS 'Queue for feedback items requiring manual review (low ratings or corrections)';


--
-- Name: COLUMN review_queue.source_feedback_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.review_queue.source_feedback_id IS 'Foreign key to conversation_ratings table';


--
-- Name: COLUMN review_queue.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.review_queue.status IS 'Status: pending (needs review), resolved (reviewed and handled), ignored (dismissed)';


--
-- Name: COLUMN review_queue.priority; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.review_queue.priority IS 'Optional priority level for manual prioritization';


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    id integer NOT NULL,
    migration_name character varying(255) NOT NULL,
    migration_number integer NOT NULL,
    executed_at timestamp with time zone DEFAULT now(),
    checksum character varying(64) NOT NULL,
    description text,
    execution_time_ms integer,
    rollback_sql text,
    applied_by character varying(255) DEFAULT 'system'::character varying
);


--
-- Name: schema_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.schema_migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: schema_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.schema_migrations_id_seq OWNED BY public.schema_migrations.id;


--
-- Name: tax_audit_risk_factors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_audit_risk_factors (
    id integer NOT NULL,
    factor_name character varying(255) NOT NULL,
    factor_category character varying(100),
    description text,
    risk_score_weight integer,
    threshold_type character varying(50),
    threshold_value double precision,
    mitigation_recommendation text,
    active boolean DEFAULT true,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE tax_audit_risk_factors; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.tax_audit_risk_factors IS 'Factors contributing to tax audit risk';


--
-- Name: tax_audit_risk_factors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_audit_risk_factors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_audit_risk_factors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_audit_risk_factors_id_seq OWNED BY public.tax_audit_risk_factors.id;


--
-- Name: tax_optimization_strategies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_optimization_strategies (
    id integer NOT NULL,
    strategy_name character varying(255) NOT NULL,
    strategy_type character varying(100),
    description text,
    eligibility_criteria jsonb,
    potential_saving_formula text,
    example_saving_amount bigint,
    risk_level character varying(20),
    requirements text[],
    timeline character varying(100),
    legal_basis character varying(255),
    applicable_entity_types text[],
    active boolean DEFAULT true,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE tax_optimization_strategies; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.tax_optimization_strategies IS 'Tax optimization strategies and eligibility';


--
-- Name: tax_optimization_strategies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_optimization_strategies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_optimization_strategies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_optimization_strategies_id_seq OWNED BY public.tax_optimization_strategies.id;


--
-- Name: tax_treaty_benefits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_treaty_benefits (
    id integer NOT NULL,
    country_name character varying(100) NOT NULL,
    dividend_rate double precision,
    royalty_rate double precision,
    interest_rate double precision,
    capital_gains_exempt boolean DEFAULT false,
    requirements text[],
    required_documents text[],
    active boolean DEFAULT true,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE tax_treaty_benefits; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.tax_treaty_benefits IS 'Tax treaty benefits by country';


--
-- Name: tax_treaty_benefits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_treaty_benefits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_treaty_benefits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_treaty_benefits_id_seq OWNED BY public.tax_treaty_benefits.id;


--
-- Name: team_access; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_access (
    user_id uuid NOT NULL,
    role character varying(50),
    permissions jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: team_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_members (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    full_name character varying(255) NOT NULL,
    role character varying(100),
    phone character varying(50),
    active boolean DEFAULT true,
    permissions jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    pin_hash character varying(255),
    department character varying(100),
    language character varying(10) DEFAULT 'en'::character varying,
    personalized_response boolean DEFAULT false,
    notes text,
    last_login timestamp with time zone,
    failed_attempts integer DEFAULT 0,
    locked_until timestamp with time zone,
    drive_folders jsonb DEFAULT '[]'::jsonb,
    avatar character varying(255)
);


--
-- Name: COLUMN team_members.full_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.full_name IS 'Full name of team member (mapped to Python model field "name")';


--
-- Name: COLUMN team_members.active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.active IS 'Account active status (mapped to Python model field "is_active")';


--
-- Name: COLUMN team_members.pin_hash; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.pin_hash IS 'Bcrypt hash of user PIN/password';


--
-- Name: COLUMN team_members.department; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.department IS 'Department code: setup, tax, marketing, board';


--
-- Name: COLUMN team_members.language; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.language IS 'Preferred language code (e.g., en, id, it)';


--
-- Name: COLUMN team_members.personalized_response; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.personalized_response IS 'Enable personalized AI responses';


--
-- Name: COLUMN team_members.notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.notes IS 'Character notes and personality traits for AI';


--
-- Name: COLUMN team_members.last_login; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.last_login IS 'Last successful login timestamp';


--
-- Name: COLUMN team_members.failed_attempts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.failed_attempts IS 'Number of failed login attempts';


--
-- Name: COLUMN team_members.locked_until; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.locked_until IS 'Account lock expiry timestamp';


--
-- Name: COLUMN team_members.drive_folders; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.drive_folders IS 'Additional personal folders this member can access';


--
-- Name: COLUMN team_members.avatar; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_members.avatar IS 'URL path to team member profile photo';


--
-- Name: team_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: team_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_members_id_seq OWNED BY public.team_members.id;


--
-- Name: team_online_status; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.team_online_status AS
 SELECT DISTINCT ON (team_timesheet.user_id) team_timesheet.user_id,
    team_timesheet.email,
    (team_timesheet."timestamp" AT TIME ZONE 'Asia/Makassar'::text) AS last_action_bali,
    team_timesheet.action_type,
        CASE
            WHEN ((team_timesheet.action_type)::text = 'clock_in'::text) THEN true
            ELSE false
        END AS is_online
   FROM public.team_timesheet
  ORDER BY team_timesheet.user_id, team_timesheet."timestamp" DESC;


--
-- Name: VIEW team_online_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.team_online_status IS 'Current online/offline status of team members';


--
-- Name: team_timesheet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_timesheet_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: team_timesheet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_timesheet_id_seq OWNED BY public.team_timesheet.id;


--
-- Name: unified_identities_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.unified_identities_view AS
 SELECT (team_members.id)::text AS uuid,
    team_members.full_name AS display_name,
    team_members.email,
    team_members.role,
    team_members.avatar,
    'team_members'::text AS source_table,
    team_members.created_at,
    team_members.active AS is_active
   FROM public.team_members
UNION ALL
 SELECT (clients.uuid)::text AS uuid,
    clients.full_name AS display_name,
    clients.email,
    'client'::character varying AS role,
    NULL::character varying AS avatar,
    'clients'::text AS source_table,
    clients.created_at,
        CASE
            WHEN ((clients.status)::text = 'active'::text) THEN true
            ELSE false
        END AS is_active
   FROM public.clients
  WHERE (clients.uuid IS NOT NULL);


--
-- Name: VIEW unified_identities_view; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.unified_identities_view IS 'Virtual Identity Layer merging Staff (team_members) and Customers (clients) for admin observability.';


--
-- Name: upcoming_renewals_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.upcoming_renewals_view AS
 SELECT p.id,
    p.uuid,
    pt.name AS practice_type,
    c.full_name AS client_name,
    c.email AS client_email,
    p.expiry_date,
    (p.expiry_date - CURRENT_DATE) AS days_until_expiry,
    p.assigned_to
   FROM ((public.practices p
     JOIN public.clients c ON ((p.client_id = c.id)))
     JOIN public.practice_types pt ON ((p.practice_type_id = pt.id)))
  WHERE ((p.expiry_date IS NOT NULL) AND (p.expiry_date > CURRENT_DATE) AND (p.expiry_date <= (CURRENT_DATE + '90 days'::interval)) AND ((p.status)::text = 'completed'::text))
  ORDER BY p.expiry_date;


--
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profiles (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    email character varying(255) NOT NULL,
    name character varying(255),
    role character varying(50),
    status character varying(50),
    avatar character varying(500),
    language character varying(10) DEFAULT 'en'::character varying,
    tone character varying(50),
    complexity character varying(50),
    timezone character varying(50),
    role_level character varying(50),
    meta_json jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_saved_news; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_saved_news (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    news_id uuid NOT NULL,
    saved_at timestamp with time zone DEFAULT now()
);


--
-- Name: user_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_stats (
    user_id character varying(255) NOT NULL,
    conversations_count integer DEFAULT 0,
    searches_count integer DEFAULT 0,
    tasks_count integer DEFAULT 0,
    summary text DEFAULT ''::text,
    preferences jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_activity timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE user_stats; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.user_stats IS 'Tracks user activity counters and conversation summaries';


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id character varying(255) NOT NULL,
    email character varying(255),
    name character varying(255),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    profile_photo_url text,
    profile_photo_updated_at timestamp with time zone,
    role character varying(100),
    status character varying(50) DEFAULT 'active'::character varying,
    meta_json jsonb DEFAULT '{}'::jsonb,
    language_preference character varying(10) DEFAULT 'en'::character varying,
    role_level character varying(20) DEFAULT 'member'::character varying,
    timezone character varying(50) DEFAULT 'Asia/Bali'::character varying,
    CONSTRAINT chk_users_language_preference CHECK (((language_preference)::text = ANY ((ARRAY['en'::character varying, 'id'::character varying, 'it'::character varying, 'es'::character varying, 'fr'::character varying, 'de'::character varying, 'ja'::character varying, 'zh'::character varying, 'uk'::character varying, 'ru'::character varying])::text[]))),
    CONSTRAINT chk_users_role_level CHECK (((role_level)::text = ANY ((ARRAY['executive'::character varying, 'director'::character varying, 'manager'::character varying, 'senior'::character varying, 'intermediate'::character varying, 'junior'::character varying, 'member'::character varying])::text[]))),
    CONSTRAINT chk_users_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'inactive'::character varying, 'suspended'::character varying, 'terminated'::character varying])::text[])))
);


--
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.users IS 'Basic user information and metadata';


--
-- Name: COLUMN users.profile_photo_url; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.profile_photo_url IS 'URL or base64 data of the user''s profile photo';


--
-- Name: COLUMN users.profile_photo_updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.profile_photo_updated_at IS 'Timestamp of the last profile photo update';


--
-- Name: v_rated_conversations; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_rated_conversations AS
 SELECT (cr.session_id)::text AS conversation_id,
    cr.rating,
    cr.feedback_text AS client_feedback,
    cr.created_at,
    public.get_conversation_messages(cr.session_id) AS messages
   FROM public.conversation_ratings cr
  WHERE (cr.rating >= 4);


--
-- Name: VIEW v_rated_conversations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_rated_conversations IS 'High-rated conversations with messages aggregated, used by ConversationTrainer agent';


--
-- Name: visa_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.visa_types (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    duration character varying(100),
    extensions character varying(100),
    total_stay character varying(100),
    renewable boolean DEFAULT false,
    processing_time_normal character varying(100),
    processing_time_express character varying(100),
    processing_timeline jsonb,
    cost_visa character varying(100),
    cost_extension character varying(100),
    cost_details jsonb,
    requirements text[],
    restrictions text[],
    allowed_activities text[],
    benefits text[],
    process_steps text[],
    tips text[],
    category character varying(50),
    foreign_eligible boolean DEFAULT true,
    metadata jsonb DEFAULT '{}'::jsonb,
    last_updated timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: TABLE visa_types; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.visa_types IS 'Visa types and requirements from VISA ORACLE knowledge base';


--
-- Name: visa_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.visa_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: visa_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.visa_types_id_seq OWNED BY public.visa_types.id;


--
-- Name: weekly_work_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.weekly_work_summary AS
 SELECT daily_work_hours.user_id,
    daily_work_hours.email,
    date_trunc('week'::text, (daily_work_hours.work_date)::timestamp with time zone) AS week_start,
    count(*) AS days_worked,
    round(sum(daily_work_hours.hours_worked), 2) AS total_hours,
    round(avg(daily_work_hours.hours_worked), 2) AS avg_hours_per_day
   FROM public.daily_work_hours
  GROUP BY daily_work_hours.user_id, daily_work_hours.email, (date_trunc('week'::text, (daily_work_hours.work_date)::timestamp with time zone));


--
-- Name: zantara_content; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zantara_content (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    slug text NOT NULL,
    body text,
    summary text,
    type public.content_type NOT NULL,
    category public.content_category NOT NULL,
    tags text[] DEFAULT ARRAY[]::text[],
    status public.content_status DEFAULT 'DRAFT'::public.content_status NOT NULL,
    author_id text,
    author_name text,
    seo_title text,
    seo_description text,
    seo_keywords text[],
    cover_image_url text,
    cover_image_alt text,
    word_count integer DEFAULT 0,
    reading_time_minutes integer DEFAULT 0,
    language text DEFAULT 'en'::text,
    ai_generated boolean DEFAULT false,
    ai_model text,
    source_signal_id text,
    approved_by text,
    approved_at timestamp with time zone,
    scheduled_at timestamp with time zone,
    published_at timestamp with time zone,
    view_count integer DEFAULT 0,
    engagement_score numeric(5,2) DEFAULT 0.0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT zantara_content_engagement_score_check CHECK ((engagement_score >= (0)::numeric)),
    CONSTRAINT zantara_content_reading_time_minutes_check CHECK ((reading_time_minutes >= 0)),
    CONSTRAINT zantara_content_view_count_check CHECK ((view_count >= 0)),
    CONSTRAINT zantara_content_word_count_check CHECK ((word_count >= 0))
);


--
-- Name: TABLE zantara_content; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.zantara_content IS 'Main content storage for ZANTARA MEDIA editorial pipeline';


--
-- Name: activity_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log ALTER COLUMN id SET DEFAULT nextval('public.activity_log_id_seq'::regclass);


--
-- Name: audit_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events ALTER COLUMN id SET DEFAULT nextval('public.audit_events_id_seq'::regclass);


--
-- Name: auth_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_audit_log ALTER COLUMN id SET DEFAULT nextval('public.auth_audit_log_id_seq'::regclass);


--
-- Name: business_structures id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_structures ALTER COLUMN id SET DEFAULT nextval('public.business_structures_id_seq'::regclass);


--
-- Name: client_family_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_family_members ALTER COLUMN id SET DEFAULT nextval('public.client_family_members_id_seq'::regclass);


--
-- Name: clients id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients ALTER COLUMN id SET DEFAULT nextval('public.clients_id_seq'::regclass);


--
-- Name: collective_memories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collective_memories ALTER COLUMN id SET DEFAULT nextval('public.collective_memories_id_seq'::regclass);


--
-- Name: collective_memory_sources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collective_memory_sources ALTER COLUMN id SET DEFAULT nextval('public.collective_memory_sources_id_seq'::regclass);


--
-- Name: company_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_profiles ALTER COLUMN id SET DEFAULT nextval('public.company_profiles_id_seq'::regclass);


--
-- Name: compliance_deadlines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_deadlines ALTER COLUMN id SET DEFAULT nextval('public.compliance_deadlines_id_seq'::regclass);


--
-- Name: conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations ALTER COLUMN id SET DEFAULT nextval('public.conversations_id_seq'::regclass);


--
-- Name: crm_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_settings ALTER COLUMN id SET DEFAULT nextval('public.crm_settings_id_seq'::regclass);


--
-- Name: cultural_knowledge id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cultural_knowledge ALTER COLUMN id SET DEFAULT nextval('public.cultural_knowledge_id_seq'::regclass);


--
-- Name: departments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments ALTER COLUMN id SET DEFAULT nextval('public.departments_id_seq'::regclass);


--
-- Name: document_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_categories ALTER COLUMN id SET DEFAULT nextval('public.document_categories_id_seq'::regclass);


--
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- Name: email_activity_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_activity_log ALTER COLUMN id SET DEFAULT nextval('public.email_activity_log_id_seq'::regclass);


--
-- Name: episodic_memories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.episodic_memories ALTER COLUMN id SET DEFAULT nextval('public.episodic_memories_id_seq'::regclass);


--
-- Name: folder_access_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder_access_rules ALTER COLUMN id SET DEFAULT nextval('public.folder_access_rules_id_seq'::regclass);


--
-- Name: immigration_issues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.immigration_issues ALTER COLUMN id SET DEFAULT nextval('public.immigration_issues_id_seq'::regclass);


--
-- Name: immigration_offices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.immigration_offices ALTER COLUMN id SET DEFAULT nextval('public.immigration_offices_id_seq'::regclass);


--
-- Name: indonesian_licenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indonesian_licenses ALTER COLUMN id SET DEFAULT nextval('public.indonesian_licenses_id_seq'::regclass);


--
-- Name: interactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interactions ALTER COLUMN id SET DEFAULT nextval('public.interactions_id_seq'::regclass);


--
-- Name: kbli_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kbli_codes ALTER COLUMN id SET DEFAULT nextval('public.kbli_codes_id_seq'::regclass);


--
-- Name: kbli_combinations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kbli_combinations ALTER COLUMN id SET DEFAULT nextval('public.kbli_combinations_id_seq'::regclass);


--
-- Name: kg_relationships id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kg_relationships ALTER COLUMN id SET DEFAULT nextval('public.kg_relationships_id_seq'::regclass);


--
-- Name: memory_facts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_facts ALTER COLUMN id SET DEFAULT nextval('public.memory_facts_id_seq'::regclass);


--
-- Name: migration_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration_log ALTER COLUMN id SET DEFAULT nextval('public.migration_log_id_seq'::regclass);


--
-- Name: oss_issues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oss_issues ALTER COLUMN id SET DEFAULT nextval('public.oss_issues_id_seq'::regclass);


--
-- Name: oss_system_info id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oss_system_info ALTER COLUMN id SET DEFAULT nextval('public.oss_system_info_id_seq'::regclass);


--
-- Name: practice_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_types ALTER COLUMN id SET DEFAULT nextval('public.practice_types_id_seq'::regclass);


--
-- Name: practices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practices ALTER COLUMN id SET DEFAULT nextval('public.practices_id_seq'::regclass);


--
-- Name: property_due_diligence id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_due_diligence ALTER COLUMN id SET DEFAULT nextval('public.property_due_diligence_id_seq'::regclass);


--
-- Name: property_legal_structures id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_legal_structures ALTER COLUMN id SET DEFAULT nextval('public.property_legal_structures_id_seq'::regclass);


--
-- Name: property_listings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_listings ALTER COLUMN id SET DEFAULT nextval('public.property_listings_id_seq'::regclass);


--
-- Name: property_market_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_market_data ALTER COLUMN id SET DEFAULT nextval('public.property_market_data_id_seq'::regclass);


--
-- Name: query_clusters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.query_clusters ALTER COLUMN id SET DEFAULT nextval('public.query_clusters_id_seq'::regclass);


--
-- Name: regulatory_updates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regulatory_updates ALTER COLUMN id SET DEFAULT nextval('public.regulatory_updates_id_seq'::regclass);


--
-- Name: renewal_alerts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.renewal_alerts ALTER COLUMN id SET DEFAULT nextval('public.renewal_alerts_id_seq'::regclass);


--
-- Name: schema_migrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations ALTER COLUMN id SET DEFAULT nextval('public.schema_migrations_id_seq'::regclass);


--
-- Name: tax_audit_risk_factors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_audit_risk_factors ALTER COLUMN id SET DEFAULT nextval('public.tax_audit_risk_factors_id_seq'::regclass);


--
-- Name: tax_optimization_strategies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_optimization_strategies ALTER COLUMN id SET DEFAULT nextval('public.tax_optimization_strategies_id_seq'::regclass);


--
-- Name: tax_treaty_benefits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_treaty_benefits ALTER COLUMN id SET DEFAULT nextval('public.tax_treaty_benefits_id_seq'::regclass);


--
-- Name: team_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members ALTER COLUMN id SET DEFAULT nextval('public.team_members_id_seq'::regclass);


--
-- Name: team_timesheet id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_timesheet ALTER COLUMN id SET DEFAULT nextval('public.team_timesheet_id_seq'::regclass);


--
-- Name: visa_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visa_types ALTER COLUMN id SET DEFAULT nextval('public.visa_types_id_seq'::regclass);


--
-- Name: activity_log activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_log
    ADD CONSTRAINT activity_log_pkey PRIMARY KEY (id);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: auth_audit_log auth_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_audit_log
    ADD CONSTRAINT auth_audit_log_pkey PRIMARY KEY (id);


--
-- Name: automation_runs automation_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.automation_runs
    ADD CONSTRAINT automation_runs_pkey PRIMARY KEY (id);


--
-- Name: business_structures business_structures_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_structures
    ADD CONSTRAINT business_structures_code_key UNIQUE (code);


--
-- Name: business_structures business_structures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_structures
    ADD CONSTRAINT business_structures_pkey PRIMARY KEY (id);


--
-- Name: client_family_members client_family_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_family_members
    ADD CONSTRAINT client_family_members_pkey PRIMARY KEY (id);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- Name: clients clients_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_uuid_key UNIQUE (uuid);


--
-- Name: collective_memories collective_memories_content_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collective_memories
    ADD CONSTRAINT collective_memories_content_hash_key UNIQUE (content_hash);


--
-- Name: collective_memories collective_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collective_memories
    ADD CONSTRAINT collective_memories_pkey PRIMARY KEY (id);


--
-- Name: collective_memory_sources collective_memory_sources_memory_id_user_id_action_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collective_memory_sources
    ADD CONSTRAINT collective_memory_sources_memory_id_user_id_action_key UNIQUE (memory_id, user_id, action);


--
-- Name: collective_memory_sources collective_memory_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collective_memory_sources
    ADD CONSTRAINT collective_memory_sources_pkey PRIMARY KEY (id);


--
-- Name: company_profiles company_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_profiles
    ADD CONSTRAINT company_profiles_pkey PRIMARY KEY (id);


--
-- Name: compliance_deadlines compliance_deadlines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_deadlines
    ADD CONSTRAINT compliance_deadlines_pkey PRIMARY KEY (id);


--
-- Name: content_analytics_daily content_analytics_daily_content_id_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_analytics_daily
    ADD CONSTRAINT content_analytics_daily_content_id_date_key UNIQUE (content_id, date);


--
-- Name: content_analytics_daily content_analytics_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_analytics_daily
    ADD CONSTRAINT content_analytics_daily_pkey PRIMARY KEY (id);


--
-- Name: content_distributions content_distributions_content_id_platform_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_distributions
    ADD CONSTRAINT content_distributions_content_id_platform_key UNIQUE (content_id, platform);


--
-- Name: content_distributions content_distributions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_distributions
    ADD CONSTRAINT content_distributions_pkey PRIMARY KEY (id);


--
-- Name: content_versions content_versions_content_id_version_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_versions
    ADD CONSTRAINT content_versions_content_id_version_number_key UNIQUE (content_id, version_number);


--
-- Name: content_versions content_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_versions
    ADD CONSTRAINT content_versions_pkey PRIMARY KEY (id);


--
-- Name: conversation_ratings conversation_ratings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_ratings
    ADD CONSTRAINT conversation_ratings_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: crm_settings crm_settings_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_settings
    ADD CONSTRAINT crm_settings_key_key UNIQUE (key);


--
-- Name: crm_settings crm_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crm_settings
    ADD CONSTRAINT crm_settings_pkey PRIMARY KEY (id);


--
-- Name: cultural_knowledge cultural_knowledge_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cultural_knowledge
    ADD CONSTRAINT cultural_knowledge_pkey PRIMARY KEY (id);


--
-- Name: departments departments_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_code_key UNIQUE (code);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: document_categories document_categories_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_categories
    ADD CONSTRAINT document_categories_code_key UNIQUE (code);


--
-- Name: document_categories document_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_categories
    ADD CONSTRAINT document_categories_pkey PRIMARY KEY (id);


--
-- Name: document_language_mappings document_language_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_language_mappings
    ADD CONSTRAINT document_language_mappings_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: email_activity_log email_activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_activity_log
    ADD CONSTRAINT email_activity_log_pkey PRIMARY KEY (id);


--
-- Name: episodic_memories episodic_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.episodic_memories
    ADD CONSTRAINT episodic_memories_pkey PRIMARY KEY (id);


--
-- Name: folder_access_rules folder_access_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.folder_access_rules
    ADD CONSTRAINT folder_access_rules_pkey PRIMARY KEY (id);


--
-- Name: golden_routes golden_routes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.golden_routes
    ADD CONSTRAINT golden_routes_pkey PRIMARY KEY (route_id);


--
-- Name: google_drive_tokens google_drive_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.google_drive_tokens
    ADD CONSTRAINT google_drive_tokens_pkey PRIMARY KEY (user_id);


--
-- Name: immigration_issues immigration_issues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.immigration_issues
    ADD CONSTRAINT immigration_issues_pkey PRIMARY KEY (id);


--
-- Name: immigration_offices immigration_offices_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.immigration_offices
    ADD CONSTRAINT immigration_offices_code_key UNIQUE (code);


--
-- Name: immigration_offices immigration_offices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.immigration_offices
    ADD CONSTRAINT immigration_offices_pkey PRIMARY KEY (id);


--
-- Name: indonesian_licenses indonesian_licenses_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indonesian_licenses
    ADD CONSTRAINT indonesian_licenses_code_key UNIQUE (code);


--
-- Name: indonesian_licenses indonesian_licenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indonesian_licenses
    ADD CONSTRAINT indonesian_licenses_pkey PRIMARY KEY (id);


--
-- Name: intel_signals intel_signals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intel_signals
    ADD CONSTRAINT intel_signals_pkey PRIMARY KEY (id);


--
-- Name: interactions interactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_pkey PRIMARY KEY (id);


--
-- Name: kbli_codes kbli_codes_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kbli_codes
    ADD CONSTRAINT kbli_codes_code_key UNIQUE (code);


--
-- Name: kbli_codes kbli_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kbli_codes
    ADD CONSTRAINT kbli_codes_pkey PRIMARY KEY (id);


--
-- Name: kbli_combinations kbli_combinations_package_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kbli_combinations
    ADD CONSTRAINT kbli_combinations_package_name_key UNIQUE (package_name);


--
-- Name: kbli_combinations kbli_combinations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kbli_combinations
    ADD CONSTRAINT kbli_combinations_pkey PRIMARY KEY (id);


--
-- Name: kg_entities kg_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kg_entities
    ADD CONSTRAINT kg_entities_pkey PRIMARY KEY (id);


--
-- Name: kg_relationships kg_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kg_relationships
    ADD CONSTRAINT kg_relationships_pkey PRIMARY KEY (id);


--
-- Name: kg_relationships kg_relationships_source_entity_id_target_entity_id_relation_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kg_relationships
    ADD CONSTRAINT kg_relationships_source_entity_id_target_entity_id_relation_key UNIQUE (source_entity_id, target_entity_id, relationship_type);


--
-- Name: knowledge_feedback knowledge_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_feedback
    ADD CONSTRAINT knowledge_feedback_pkey PRIMARY KEY (id);


--
-- Name: media_assets media_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_assets
    ADD CONSTRAINT media_assets_pkey PRIMARY KEY (id);


--
-- Name: memory_facts memory_facts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memory_facts
    ADD CONSTRAINT memory_facts_pkey PRIMARY KEY (id);


--
-- Name: migration_log migration_log_migration_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration_log
    ADD CONSTRAINT migration_log_migration_name_key UNIQUE (migration_name);


--
-- Name: migration_log migration_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration_log
    ADD CONSTRAINT migration_log_pkey PRIMARY KEY (id);


--
-- Name: news_items news_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.news_items
    ADD CONSTRAINT news_items_pkey PRIMARY KEY (id);


--
-- Name: news_items news_items_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.news_items
    ADD CONSTRAINT news_items_slug_key UNIQUE (slug);


--
-- Name: news_subscriptions news_subscriptions_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.news_subscriptions
    ADD CONSTRAINT news_subscriptions_email_key UNIQUE (email);


--
-- Name: news_subscriptions news_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.news_subscriptions
    ADD CONSTRAINT news_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: oss_issues oss_issues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oss_issues
    ADD CONSTRAINT oss_issues_pkey PRIMARY KEY (id);


--
-- Name: oss_system_info oss_system_info_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oss_system_info
    ADD CONSTRAINT oss_system_info_key_key UNIQUE (key);


--
-- Name: oss_system_info oss_system_info_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oss_system_info
    ADD CONSTRAINT oss_system_info_pkey PRIMARY KEY (id);


--
-- Name: parent_documents parent_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parent_documents
    ADD CONSTRAINT parent_documents_pkey PRIMARY KEY (id);


--
-- Name: practice_types practice_types_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_types
    ADD CONSTRAINT practice_types_code_key UNIQUE (code);


--
-- Name: practice_types practice_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practice_types
    ADD CONSTRAINT practice_types_pkey PRIMARY KEY (id);


--
-- Name: practices practices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practices
    ADD CONSTRAINT practices_pkey PRIMARY KEY (id);


--
-- Name: practices practices_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practices
    ADD CONSTRAINT practices_uuid_key UNIQUE (uuid);


--
-- Name: property_due_diligence property_due_diligence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_due_diligence
    ADD CONSTRAINT property_due_diligence_pkey PRIMARY KEY (id);


--
-- Name: property_legal_structures property_legal_structures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_legal_structures
    ADD CONSTRAINT property_legal_structures_pkey PRIMARY KEY (id);


--
-- Name: property_listings property_listings_content_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_listings
    ADD CONSTRAINT property_listings_content_id_key UNIQUE (content_id);


--
-- Name: property_listings property_listings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_listings
    ADD CONSTRAINT property_listings_pkey PRIMARY KEY (id);


--
-- Name: property_market_data property_market_data_area_period_start_period_end_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_market_data
    ADD CONSTRAINT property_market_data_area_period_start_period_end_key UNIQUE (area, period_start, period_end);


--
-- Name: property_market_data property_market_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_market_data
    ADD CONSTRAINT property_market_data_pkey PRIMARY KEY (id);


--
-- Name: query_analytics query_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.query_analytics
    ADD CONSTRAINT query_analytics_pkey PRIMARY KEY (id);


--
-- Name: query_clusters query_clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.query_clusters
    ADD CONSTRAINT query_clusters_pkey PRIMARY KEY (id);


--
-- Name: query_route_clusters query_route_clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.query_route_clusters
    ADD CONSTRAINT query_route_clusters_pkey PRIMARY KEY (cluster_id);


--
-- Name: regulatory_updates regulatory_updates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regulatory_updates
    ADD CONSTRAINT regulatory_updates_pkey PRIMARY KEY (id);


--
-- Name: renewal_alerts renewal_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.renewal_alerts
    ADD CONSTRAINT renewal_alerts_pkey PRIMARY KEY (id);


--
-- Name: review_queue review_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_queue
    ADD CONSTRAINT review_queue_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_migration_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_migration_name_key UNIQUE (migration_name);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (id);


--
-- Name: tax_audit_risk_factors tax_audit_risk_factors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_audit_risk_factors
    ADD CONSTRAINT tax_audit_risk_factors_pkey PRIMARY KEY (id);


--
-- Name: tax_optimization_strategies tax_optimization_strategies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_optimization_strategies
    ADD CONSTRAINT tax_optimization_strategies_pkey PRIMARY KEY (id);


--
-- Name: tax_treaty_benefits tax_treaty_benefits_country_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_treaty_benefits
    ADD CONSTRAINT tax_treaty_benefits_country_name_key UNIQUE (country_name);


--
-- Name: tax_treaty_benefits tax_treaty_benefits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_treaty_benefits
    ADD CONSTRAINT tax_treaty_benefits_pkey PRIMARY KEY (id);


--
-- Name: team_members team_members_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_email_key UNIQUE (email);


--
-- Name: team_members team_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_members
    ADD CONSTRAINT team_members_pkey PRIMARY KEY (id);


--
-- Name: team_timesheet team_timesheet_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_timesheet
    ADD CONSTRAINT team_timesheet_pkey PRIMARY KEY (id);


--
-- Name: user_profiles user_profiles_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_email_key UNIQUE (email);


--
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (id);


--
-- Name: user_saved_news user_saved_news_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_saved_news
    ADD CONSTRAINT user_saved_news_pkey PRIMARY KEY (id);


--
-- Name: user_saved_news user_saved_news_user_id_news_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_saved_news
    ADD CONSTRAINT user_saved_news_user_id_news_id_key UNIQUE (user_id, news_id);


--
-- Name: user_stats user_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_stats
    ADD CONSTRAINT user_stats_pkey PRIMARY KEY (user_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: visa_types visa_types_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visa_types
    ADD CONSTRAINT visa_types_code_key UNIQUE (code);


--
-- Name: visa_types visa_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.visa_types
    ADD CONSTRAINT visa_types_pkey PRIMARY KEY (id);


--
-- Name: zantara_content zantara_content_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zantara_content
    ADD CONSTRAINT zantara_content_pkey PRIMARY KEY (id);


--
-- Name: zantara_content zantara_content_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zantara_content
    ADD CONSTRAINT zantara_content_slug_key UNIQUE (slug);


--
-- Name: idx_activity_log_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_date ON public.activity_log USING btree (performed_at DESC);


--
-- Name: idx_activity_log_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_entity ON public.activity_log USING btree (entity_type, entity_id);


--
-- Name: idx_activity_log_performed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_log_performed_by ON public.activity_log USING btree (performed_by);


--
-- Name: idx_audit_events_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_events_timestamp ON public.audit_events USING btree ("timestamp" DESC);


--
-- Name: idx_audit_events_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_events_type ON public.audit_events USING btree (event_type);


--
-- Name: idx_audit_events_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_events_user ON public.audit_events USING btree (user_id);


--
-- Name: idx_audit_factors_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_factors_active ON public.tax_audit_risk_factors USING btree (active);


--
-- Name: idx_audit_factors_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_factors_category ON public.tax_audit_risk_factors USING btree (factor_category);


--
-- Name: idx_auth_audit_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_audit_action ON public.auth_audit_log USING btree (action);


--
-- Name: idx_auth_audit_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_audit_email ON public.auth_audit_log USING btree (email);


--
-- Name: idx_auth_audit_ip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_audit_ip ON public.auth_audit_log USING btree (ip_address);


--
-- Name: idx_auth_audit_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_audit_timestamp ON public.auth_audit_log USING btree ("timestamp" DESC);


--
-- Name: idx_automation_runs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_automation_runs_status ON public.automation_runs USING btree (status);


--
-- Name: idx_automation_runs_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_automation_runs_type ON public.automation_runs USING btree (run_type, started_at DESC);


--
-- Name: idx_business_structures_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_business_structures_code ON public.business_structures USING btree (code);


--
-- Name: idx_clients_assigned_to; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_assigned_to ON public.clients USING btree (assigned_to);


--
-- Name: idx_clients_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_email ON public.clients USING btree (email);


--
-- Name: idx_clients_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_phone ON public.clients USING btree (phone);


--
-- Name: idx_clients_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_status ON public.clients USING btree (status);


--
-- Name: idx_clients_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_tags ON public.clients USING gin (tags);


--
-- Name: idx_clients_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_uuid ON public.clients USING btree (uuid);


--
-- Name: idx_collective_memories_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_collective_memories_category ON public.collective_memories USING btree (category);


--
-- Name: idx_collective_memories_confidence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_collective_memories_confidence ON public.collective_memories USING btree (confidence DESC);


--
-- Name: idx_collective_memories_content_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_collective_memories_content_hash ON public.collective_memories USING btree (content_hash);


--
-- Name: idx_collective_memories_promoted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_collective_memories_promoted ON public.collective_memories USING btree (is_promoted) WHERE (is_promoted = true);


--
-- Name: idx_collective_sources_memory; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_collective_sources_memory ON public.collective_memory_sources USING btree (memory_id);


--
-- Name: idx_collective_sources_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_collective_sources_user ON public.collective_memory_sources USING btree (user_id);


--
-- Name: idx_collective_unsynced; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_collective_unsynced ON public.collective_memories USING btree (embedding_synced) WHERE (embedding_synced = false);


--
-- Name: idx_company_profiles_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_company_profiles_entity ON public.company_profiles USING btree (entity_type);


--
-- Name: idx_company_profiles_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_company_profiles_user ON public.company_profiles USING btree (user_id);


--
-- Name: idx_compliance_deadlines_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compliance_deadlines_type ON public.compliance_deadlines USING btree (deadline_type);


--
-- Name: idx_content_analytics_daily_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_analytics_daily_content_id ON public.content_analytics_daily USING btree (content_id, date DESC);


--
-- Name: idx_content_analytics_daily_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_analytics_daily_date ON public.content_analytics_daily USING btree (date DESC);


--
-- Name: idx_content_distributions_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_distributions_content_id ON public.content_distributions USING btree (content_id);


--
-- Name: idx_content_distributions_platform; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_distributions_platform ON public.content_distributions USING btree (platform);


--
-- Name: idx_content_distributions_published_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_distributions_published_at ON public.content_distributions USING btree (published_at DESC);


--
-- Name: idx_content_distributions_scheduled_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_distributions_scheduled_at ON public.content_distributions USING btree (scheduled_at);


--
-- Name: idx_content_distributions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_distributions_status ON public.content_distributions USING btree (status);


--
-- Name: idx_content_versions_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_content_versions_content_id ON public.content_versions USING btree (content_id, version_number DESC);


--
-- Name: idx_conv_ratings_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conv_ratings_created ON public.conversation_ratings USING btree (created_at DESC);


--
-- Name: idx_conv_ratings_rating; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conv_ratings_rating ON public.conversation_ratings USING btree (rating) WHERE (rating >= 4);


--
-- Name: idx_conv_ratings_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conv_ratings_session ON public.conversation_ratings USING btree (session_id);


--
-- Name: idx_conv_ratings_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conv_ratings_user ON public.conversation_ratings USING btree (user_id) WHERE (user_id IS NOT NULL);


--
-- Name: idx_conversations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_created_at ON public.conversations USING btree (created_at DESC);


--
-- Name: idx_conversations_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_session_id ON public.conversations USING btree (session_id);


--
-- Name: idx_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_user_id ON public.conversations USING btree (user_id);


--
-- Name: idx_cultural_knowledge_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cultural_knowledge_category ON public.cultural_knowledge USING btree (category);


--
-- Name: idx_cultural_knowledge_language; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cultural_knowledge_language ON public.cultural_knowledge USING btree (language);


--
-- Name: idx_doc_mappings_doc_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_doc_mappings_doc_id ON public.document_language_mappings USING btree (document_id);


--
-- Name: idx_doc_mappings_jurisdiction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_doc_mappings_jurisdiction ON public.document_language_mappings USING btree (jurisdiction);


--
-- Name: idx_doc_mappings_lang; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_doc_mappings_lang ON public.document_language_mappings USING btree (source_language);


--
-- Name: idx_doc_mappings_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_doc_mappings_type ON public.document_language_mappings USING btree (document_type);


--
-- Name: idx_documents_archived; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_archived ON public.documents USING btree (is_archived);


--
-- Name: idx_documents_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_category ON public.documents USING btree (document_category);


--
-- Name: idx_documents_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_client_id ON public.documents USING btree (client_id);


--
-- Name: idx_documents_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_expiry ON public.documents USING btree (expiry_date);


--
-- Name: idx_documents_family_member; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_family_member ON public.documents USING btree (family_member_id);


--
-- Name: idx_documents_practice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_practice_id ON public.documents USING btree (practice_id);


--
-- Name: idx_documents_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_status ON public.documents USING btree (status);


--
-- Name: idx_documents_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_type ON public.documents USING btree (document_type);


--
-- Name: idx_due_diligence_property; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_due_diligence_property ON public.property_due_diligence USING btree (property_listing_id);


--
-- Name: idx_due_diligence_risk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_due_diligence_risk ON public.property_due_diligence USING btree (overall_risk);


--
-- Name: idx_email_activity_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_activity_created ON public.email_activity_log USING btree (created_at DESC);


--
-- Name: idx_email_activity_operation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_activity_operation ON public.email_activity_log USING btree (operation);


--
-- Name: idx_email_activity_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_activity_user ON public.email_activity_log USING btree (user_id);


--
-- Name: idx_email_activity_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_activity_user_created ON public.email_activity_log USING btree (user_id, created_at);


--
-- Name: idx_episodic_entities; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_episodic_entities ON public.episodic_memories USING gin (related_entities);


--
-- Name: idx_episodic_kg_entities; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_episodic_kg_entities ON public.episodic_memories USING gin (kg_entity_ids);


--
-- Name: idx_episodic_title_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_episodic_title_search ON public.episodic_memories USING gin (to_tsvector('english'::regconfig, (((title)::text || ' '::text) || COALESCE(description, ''::text))));


--
-- Name: idx_episodic_user_emotion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_episodic_user_emotion ON public.episodic_memories USING btree (user_id, emotion);


--
-- Name: idx_episodic_user_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_episodic_user_time ON public.episodic_memories USING btree (user_id, occurred_at DESC);


--
-- Name: idx_episodic_user_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_episodic_user_type ON public.episodic_memories USING btree (user_id, event_type);


--
-- Name: idx_family_members_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_members_client_id ON public.client_family_members USING btree (client_id);


--
-- Name: idx_family_members_passport_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_members_passport_expiry ON public.client_family_members USING btree (passport_expiry);


--
-- Name: idx_family_members_relationship; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_members_relationship ON public.client_family_members USING btree (relationship);


--
-- Name: idx_family_members_visa_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_family_members_visa_expiry ON public.client_family_members USING btree (visa_expiry);


--
-- Name: idx_feedback_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_created_at ON public.knowledge_feedback USING btree (created_at);


--
-- Name: idx_feedback_metadata_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_metadata_gin ON public.knowledge_feedback USING gin (metadata);


--
-- Name: idx_feedback_resolved; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_resolved ON public.knowledge_feedback USING btree (resolved);


--
-- Name: idx_feedback_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_session_id ON public.knowledge_feedback USING btree (session_id);


--
-- Name: idx_feedback_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_type ON public.knowledge_feedback USING btree (feedback_type);


--
-- Name: idx_feedback_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_feedback_user_id ON public.knowledge_feedback USING btree (user_id);


--
-- Name: idx_folder_access_context; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_folder_access_context ON public.folder_access_rules USING btree (context_folder);


--
-- Name: idx_folder_access_dept; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_folder_access_dept ON public.folder_access_rules USING btree (department_code) WHERE (department_code IS NOT NULL);


--
-- Name: idx_folder_access_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_folder_access_role ON public.folder_access_rules USING btree (role) WHERE (role IS NOT NULL);


--
-- Name: idx_folder_access_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_folder_access_user ON public.folder_access_rules USING btree (user_email) WHERE (user_email IS NOT NULL);


--
-- Name: idx_golden_routes_query; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_golden_routes_query ON public.golden_routes USING btree (canonical_query);


--
-- Name: idx_google_drive_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_google_drive_tokens_user_id ON public.google_drive_tokens USING btree (user_id);


--
-- Name: idx_immigration_issues_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_immigration_issues_type ON public.immigration_issues USING btree (issue_type);


--
-- Name: idx_immigration_offices_city; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_immigration_offices_city ON public.immigration_offices USING btree (city);


--
-- Name: idx_intel_signals_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_intel_signals_category ON public.intel_signals USING btree (category);


--
-- Name: idx_intel_signals_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_intel_signals_content_id ON public.intel_signals USING btree (content_id);


--
-- Name: idx_intel_signals_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_intel_signals_priority ON public.intel_signals USING btree (priority DESC, signal_date DESC);


--
-- Name: idx_intel_signals_processed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_intel_signals_processed ON public.intel_signals USING btree (processed, signal_date DESC);


--
-- Name: idx_interactions_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interactions_client_id ON public.interactions USING btree (client_id);


--
-- Name: idx_interactions_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interactions_conversation_id ON public.interactions USING btree (conversation_id);


--
-- Name: idx_interactions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interactions_date ON public.interactions USING btree (interaction_date DESC);


--
-- Name: idx_interactions_practice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interactions_practice_id ON public.interactions USING btree (practice_id);


--
-- Name: idx_interactions_team_member; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interactions_team_member ON public.interactions USING btree (team_member);


--
-- Name: idx_interactions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interactions_type ON public.interactions USING btree (interaction_type);


--
-- Name: idx_kbli_codes_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kbli_codes_category ON public.kbli_codes USING btree (category_letter);


--
-- Name: idx_kbli_codes_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kbli_codes_code ON public.kbli_codes USING btree (code);


--
-- Name: idx_kbli_codes_foreign_eligible; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kbli_codes_foreign_eligible ON public.kbli_codes USING btree (foreign_eligible);


--
-- Name: idx_kbli_codes_popularity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kbli_codes_popularity ON public.kbli_codes USING btree (popularity);


--
-- Name: idx_kg_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kg_canonical ON public.kg_entities USING btree (canonical_name);


--
-- Name: idx_kg_entity_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kg_entity_name ON public.kg_entities USING btree (name);


--
-- Name: idx_kg_entity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kg_entity_type ON public.kg_entities USING btree (type);


--
-- Name: idx_kg_rel_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kg_rel_source ON public.kg_relationships USING btree (source_entity_id);


--
-- Name: idx_kg_rel_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kg_rel_target ON public.kg_relationships USING btree (target_entity_id);


--
-- Name: idx_kg_rel_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kg_rel_type ON public.kg_relationships USING btree (relationship_type);


--
-- Name: idx_legal_structures_foreign; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_legal_structures_foreign ON public.property_legal_structures USING btree (foreign_eligible);


--
-- Name: idx_legal_structures_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_legal_structures_type ON public.property_legal_structures USING btree (structure_type);


--
-- Name: idx_licenses_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_licenses_code ON public.indonesian_licenses USING btree (code);


--
-- Name: idx_licenses_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_licenses_status ON public.indonesian_licenses USING btree (status);


--
-- Name: idx_media_assets_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_assets_content_id ON public.media_assets USING btree (content_id);


--
-- Name: idx_media_assets_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_assets_created_at ON public.media_assets USING btree (created_at DESC);


--
-- Name: idx_media_assets_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_assets_type ON public.media_assets USING btree (asset_type);


--
-- Name: idx_memory_facts_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_memory_facts_created_at ON public.memory_facts USING btree (created_at DESC);


--
-- Name: idx_memory_facts_entities; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_memory_facts_entities ON public.memory_facts USING gin (related_entities);


--
-- Name: idx_memory_facts_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_memory_facts_user_id ON public.memory_facts USING btree (user_id);


--
-- Name: idx_news_items_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_items_category ON public.news_items USING btree (category);


--
-- Name: idx_news_items_external_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_items_external_id ON public.news_items USING btree (external_id);


--
-- Name: idx_news_items_fts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_items_fts ON public.news_items USING gin (to_tsvector('english'::regconfig, ((((COALESCE(title, ''::text) || ' '::text) || COALESCE(summary, ''::text)) || ' '::text) || COALESCE(content, ''::text))));


--
-- Name: idx_news_items_published_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_items_published_at ON public.news_items USING btree (published_at DESC);


--
-- Name: idx_news_items_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_items_slug ON public.news_items USING btree (slug);


--
-- Name: idx_news_items_source_feed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_items_source_feed ON public.news_items USING btree (source_feed);


--
-- Name: idx_news_items_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_items_status ON public.news_items USING btree (status);


--
-- Name: idx_news_subscriptions_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_subscriptions_active ON public.news_subscriptions USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_news_subscriptions_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_news_subscriptions_email ON public.news_subscriptions USING btree (email);


--
-- Name: idx_oss_issues_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_oss_issues_category ON public.oss_issues USING btree (issue_category);


--
-- Name: idx_parent_docs_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_docs_canonical ON public.parent_documents USING btree (document_id, is_canonical) WHERE (is_canonical = true);


--
-- Name: idx_parent_docs_doc_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_docs_doc_id ON public.parent_documents USING btree (document_id);


--
-- Name: idx_parent_docs_drive_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_docs_drive_id ON public.parent_documents USING btree (drive_file_id);


--
-- Name: idx_parent_docs_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_docs_fingerprint ON public.parent_documents USING btree (document_id, text_fingerprint);


--
-- Name: idx_parent_docs_incomplete; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_parent_docs_incomplete ON public.parent_documents USING btree (is_incomplete) WHERE (is_incomplete = true);


--
-- Name: idx_practice_types_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practice_types_category ON public.practice_types USING btree (category);


--
-- Name: idx_practice_types_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practice_types_code ON public.practice_types USING btree (code);


--
-- Name: idx_practices_assigned_to; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practices_assigned_to ON public.practices USING btree (assigned_to);


--
-- Name: idx_practices_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practices_client_id ON public.practices USING btree (client_id);


--
-- Name: idx_practices_expiry_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practices_expiry_date ON public.practices USING btree (expiry_date);


--
-- Name: idx_practices_next_renewal_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practices_next_renewal_date ON public.practices USING btree (next_renewal_date);


--
-- Name: idx_practices_practice_type_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practices_practice_type_id ON public.practices USING btree (practice_type_id);


--
-- Name: idx_practices_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practices_status ON public.practices USING btree (status);


--
-- Name: idx_practices_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_practices_uuid ON public.practices USING btree (uuid);


--
-- Name: idx_property_listings_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_listings_area ON public.property_listings USING btree (area);


--
-- Name: idx_property_listings_ownership; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_listings_ownership ON public.property_listings USING btree (ownership);


--
-- Name: idx_property_listings_price; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_listings_price ON public.property_listings USING btree (price);


--
-- Name: idx_property_listings_scraped; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_listings_scraped ON public.property_listings USING btree (scraped_at DESC);


--
-- Name: idx_property_listings_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_listings_type ON public.property_listings USING btree (property_type);


--
-- Name: idx_property_market_area; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_market_area ON public.property_market_data USING btree (area);


--
-- Name: idx_property_market_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_market_period ON public.property_market_data USING btree (period_start DESC);


--
-- Name: idx_query_analytics_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_query_analytics_created_at ON public.query_analytics USING btree (created_at);


--
-- Name: idx_query_analytics_lang_pref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_query_analytics_lang_pref ON public.query_analytics USING btree (language_preference);


--
-- Name: idx_query_analytics_query_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_query_analytics_query_hash ON public.query_analytics USING btree (query_hash);


--
-- Name: idx_query_analytics_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_query_analytics_user_id ON public.query_analytics USING btree (user_id);


--
-- Name: idx_query_clusters_cluster_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_query_clusters_cluster_id ON public.query_clusters USING btree (cluster_id);


--
-- Name: idx_regulatory_updates_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_regulatory_updates_date ON public.regulatory_updates USING btree (update_date DESC);


--
-- Name: idx_regulatory_updates_impact; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_regulatory_updates_impact ON public.regulatory_updates USING btree (impact_level);


--
-- Name: idx_regulatory_updates_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_regulatory_updates_source ON public.regulatory_updates USING btree (source);


--
-- Name: idx_renewal_alerts_alert_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_renewal_alerts_alert_date ON public.renewal_alerts USING btree (alert_date);


--
-- Name: idx_renewal_alerts_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_renewal_alerts_client_id ON public.renewal_alerts USING btree (client_id);


--
-- Name: idx_renewal_alerts_practice_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_renewal_alerts_practice_id ON public.renewal_alerts USING btree (practice_id);


--
-- Name: idx_renewal_alerts_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_renewal_alerts_status ON public.renewal_alerts USING btree (status);


--
-- Name: idx_review_queue_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_queue_created ON public.review_queue USING btree (created_at DESC);


--
-- Name: idx_review_queue_feedback_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_queue_feedback_id ON public.review_queue USING btree (source_feedback_id);


--
-- Name: idx_review_queue_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_queue_pending ON public.review_queue USING btree (status, created_at DESC) WHERE ((status)::text = 'pending'::text);


--
-- Name: idx_review_queue_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_queue_status ON public.review_queue USING btree (status);


--
-- Name: idx_schema_migrations_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_schema_migrations_name ON public.schema_migrations USING btree (migration_name);


--
-- Name: idx_schema_migrations_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_schema_migrations_number ON public.schema_migrations USING btree (migration_number);


--
-- Name: idx_tax_strategies_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tax_strategies_active ON public.tax_optimization_strategies USING btree (active);


--
-- Name: idx_tax_strategies_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tax_strategies_type ON public.tax_optimization_strategies USING btree (strategy_type);


--
-- Name: idx_tax_treaties_country; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tax_treaties_country ON public.tax_treaty_benefits USING btree (country_name);


--
-- Name: idx_team_access_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_access_user_id ON public.team_access USING btree (user_id);


--
-- Name: idx_team_members_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_members_active ON public.team_members USING btree (active);


--
-- Name: idx_team_members_department; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_members_department ON public.team_members USING btree (department);


--
-- Name: idx_team_members_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_members_email ON public.team_members USING btree (email);


--
-- Name: idx_team_members_language; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_members_language ON public.team_members USING btree (language);


--
-- Name: idx_team_members_pin_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_members_pin_hash ON public.team_members USING btree (pin_hash) WHERE (pin_hash IS NOT NULL);


--
-- Name: idx_timesheet_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_timesheet_action ON public.team_timesheet USING btree (action_type);


--
-- Name: idx_timesheet_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_timesheet_date ON public.team_timesheet USING btree (date(("timestamp" AT TIME ZONE 'Asia/Makassar'::text)));


--
-- Name: idx_timesheet_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_timesheet_user ON public.team_timesheet USING btree (user_id);


--
-- Name: idx_timesheet_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_timesheet_user_date ON public.team_timesheet USING btree (user_id, date(("timestamp" AT TIME ZONE 'Asia/Makassar'::text)));


--
-- Name: idx_user_profiles_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profiles_email ON public.user_profiles USING btree (email);


--
-- Name: idx_user_saved_news_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_saved_news_user ON public.user_saved_news USING btree (user_id);


--
-- Name: idx_user_stats_last_activity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_stats_last_activity ON public.user_stats USING btree (last_activity DESC);


--
-- Name: idx_users_language_pref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_language_pref ON public.users USING btree (language_preference);


--
-- Name: idx_users_meta_json_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_meta_json_gin ON public.users USING gin (meta_json);


--
-- Name: idx_users_profile_photo_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_profile_photo_updated_at ON public.users USING btree (profile_photo_updated_at DESC);


--
-- Name: idx_users_role_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_role_level ON public.users USING btree (role_level);


--
-- Name: idx_users_status_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_status_role ON public.users USING btree (status, role_level);


--
-- Name: idx_visa_types_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_visa_types_category ON public.visa_types USING btree (category);


--
-- Name: idx_visa_types_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_visa_types_code ON public.visa_types USING btree (code);


--
-- Name: idx_zantara_content_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_category ON public.zantara_content USING btree (category);


--
-- Name: idx_zantara_content_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_created_at ON public.zantara_content USING btree (created_at DESC);


--
-- Name: idx_zantara_content_published_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_published_at ON public.zantara_content USING btree (published_at DESC);


--
-- Name: idx_zantara_content_scheduled_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_scheduled_at ON public.zantara_content USING btree (scheduled_at);


--
-- Name: idx_zantara_content_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_search ON public.zantara_content USING gin (to_tsvector('english'::regconfig, ((((COALESCE(title, ''::text) || ' '::text) || COALESCE(body, ''::text)) || ' '::text) || COALESCE(summary, ''::text))));


--
-- Name: idx_zantara_content_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_status ON public.zantara_content USING btree (status);


--
-- Name: idx_zantara_content_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_tags ON public.zantara_content USING gin (tags);


--
-- Name: idx_zantara_content_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_zantara_content_type ON public.zantara_content USING btree (type);


--
-- Name: client_summary_view _RETURN; Type: RULE; Schema: public; Owner: -
--

CREATE OR REPLACE VIEW public.client_summary_view AS
 SELECT c.id,
    c.uuid,
    c.full_name,
    c.email,
    c.phone,
    c.status,
    c.assigned_to,
    c.first_contact_date,
    c.last_interaction_date,
    count(DISTINCT p.id) AS total_practices,
    count(DISTINCT
        CASE
            WHEN ((p.status)::text = ANY ((ARRAY['inquiry'::character varying, 'in_progress'::character varying, 'waiting_documents'::character varying, 'submitted_to_gov'::character varying])::text[])) THEN p.id
            ELSE NULL::integer
        END) AS active_practices,
    count(DISTINCT i.id) AS total_interactions,
    max(i.interaction_date) AS last_interaction
   FROM ((public.clients c
     LEFT JOIN public.practices p ON ((c.id = p.client_id)))
     LEFT JOIN public.interactions i ON ((c.id = i.client_id)))
  GROUP BY c.id;


--
-- Name: news_items trg_news_items_before_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_news_items_before_insert BEFORE INSERT ON public.news_items FOR EACH ROW EXECUTE FUNCTION public.news_items_before_insert();


--
-- Name: news_items trg_news_items_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_news_items_update BEFORE UPDATE ON public.news_items FOR EACH ROW EXECUTE FUNCTION public.news_items_update_timestamp();


--
-- Name: episodic_memories trigger_episodic_memories_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_episodic_memories_updated_at BEFORE UPDATE ON public.episodic_memories FOR EACH ROW EXECUTE FUNCTION public.update_episodic_memories_updated_at();


--
-- Name: collective_memory_sources trigger_update_collective_stats; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_update_collective_stats AFTER INSERT OR UPDATE ON public.collective_memory_sources FOR EACH ROW EXECUTE FUNCTION public.update_collective_memory_stats();


--
-- Name: content_distributions trigger_update_content_distributions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_update_content_distributions_updated_at BEFORE UPDATE ON public.content_distributions FOR EACH ROW EXECUTE FUNCTION public.update_zantara_content_updated_at();


--
-- Name: zantara_content trigger_update_zantara_content_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_update_zantara_content_updated_at BEFORE UPDATE ON public.zantara_content FOR EACH ROW EXECUTE FUNCTION public.update_zantara_content_updated_at();


--
-- Name: clients update_clients_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON public.clients FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: documents update_documents_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: client_family_members update_family_members_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_family_members_updated_at BEFORE UPDATE ON public.client_family_members FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: practices update_practices_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_practices_updated_at BEFORE UPDATE ON public.practices FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: team_members update_team_members_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_team_members_updated_at BEFORE UPDATE ON public.team_members FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: client_family_members client_family_members_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_family_members
    ADD CONSTRAINT client_family_members_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: collective_memory_sources collective_memory_sources_memory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collective_memory_sources
    ADD CONSTRAINT collective_memory_sources_memory_id_fkey FOREIGN KEY (memory_id) REFERENCES public.collective_memories(id) ON DELETE CASCADE;


--
-- Name: content_analytics_daily content_analytics_daily_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_analytics_daily
    ADD CONSTRAINT content_analytics_daily_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.zantara_content(id) ON DELETE CASCADE;


--
-- Name: content_distributions content_distributions_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_distributions
    ADD CONSTRAINT content_distributions_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.zantara_content(id) ON DELETE CASCADE;


--
-- Name: content_versions content_versions_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_versions
    ADD CONSTRAINT content_versions_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.zantara_content(id) ON DELETE CASCADE;


--
-- Name: conversation_ratings conversation_ratings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_ratings
    ADD CONSTRAINT conversation_ratings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_profiles(id) ON DELETE SET NULL;


--
-- Name: documents documents_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: documents documents_family_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_family_member_id_fkey FOREIGN KEY (family_member_id) REFERENCES public.client_family_members(id) ON DELETE SET NULL;


--
-- Name: documents documents_practice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_practice_id_fkey FOREIGN KEY (practice_id) REFERENCES public.practices(id) ON DELETE CASCADE;


--
-- Name: email_activity_log email_activity_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_activity_log
    ADD CONSTRAINT email_activity_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.team_members(id) ON DELETE CASCADE;


--
-- Name: intel_signals intel_signals_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intel_signals
    ADD CONSTRAINT intel_signals_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.zantara_content(id) ON DELETE SET NULL;


--
-- Name: interactions interactions_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: interactions interactions_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE SET NULL;


--
-- Name: interactions interactions_practice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_practice_id_fkey FOREIGN KEY (practice_id) REFERENCES public.practices(id) ON DELETE SET NULL;


--
-- Name: kg_relationships kg_relationships_source_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kg_relationships
    ADD CONSTRAINT kg_relationships_source_entity_id_fkey FOREIGN KEY (source_entity_id) REFERENCES public.kg_entities(id);


--
-- Name: kg_relationships kg_relationships_target_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kg_relationships
    ADD CONSTRAINT kg_relationships_target_entity_id_fkey FOREIGN KEY (target_entity_id) REFERENCES public.kg_entities(id);


--
-- Name: media_assets media_assets_content_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_assets
    ADD CONSTRAINT media_assets_content_id_fkey FOREIGN KEY (content_id) REFERENCES public.zantara_content(id) ON DELETE SET NULL;


--
-- Name: practices practices_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practices
    ADD CONSTRAINT practices_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: practices practices_practice_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.practices
    ADD CONSTRAINT practices_practice_type_id_fkey FOREIGN KEY (practice_type_id) REFERENCES public.practice_types(id);


--
-- Name: property_due_diligence property_due_diligence_property_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_due_diligence
    ADD CONSTRAINT property_due_diligence_property_listing_id_fkey FOREIGN KEY (property_listing_id) REFERENCES public.property_listings(id);


--
-- Name: renewal_alerts renewal_alerts_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.renewal_alerts
    ADD CONSTRAINT renewal_alerts_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE CASCADE;


--
-- Name: renewal_alerts renewal_alerts_practice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.renewal_alerts
    ADD CONSTRAINT renewal_alerts_practice_id_fkey FOREIGN KEY (practice_id) REFERENCES public.practices(id) ON DELETE CASCADE;


--
-- Name: review_queue review_queue_source_feedback_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_queue
    ADD CONSTRAINT review_queue_source_feedback_id_fkey FOREIGN KEY (source_feedback_id) REFERENCES public.conversation_ratings(id) ON DELETE CASCADE;


--
-- Name: user_saved_news user_saved_news_news_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_saved_news
    ADD CONSTRAINT user_saved_news_news_id_fkey FOREIGN KEY (news_id) REFERENCES public.news_items(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


-- CLEANUP: Remove legacy migration table imported from snapshot
DROP TABLE IF EXISTS public.schema_migrations CASCADE;

