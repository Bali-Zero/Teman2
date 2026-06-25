-- WR2 episodic state machine schema
-- Per-slide checkpointing addresses Gemini FLAW HIGH (rate-limit 429 → Frankenstein
-- on restart). Resume reads last-clean-state instead of full regen.
--
-- DB location: ~/.claude/projects/-Users-nuzantara/memory/wr2-episodic.db
-- Created/migrated by orchestrator at first carousel run.

-- One row per carousel run.
CREATE TABLE IF NOT EXISTS carousel_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_slug TEXT NOT NULL,
    started_at TEXT NOT NULL,           -- ISO-8601
    completed_at TEXT,                  -- NULL while in progress
    domain TEXT NOT NULL,               -- visa | tax | property | hr | regulatory
    audience_segment TEXT,
    body_case_chosen TEXT,              -- UPPERCASE | TITLE_CASE
    layout_families_used TEXT,          -- JSON array
    slide_count INTEGER,
    hero_count INTEGER,
    nb_sources_consulted TEXT,          -- JSON array
    critic_overall_verdict TEXT,        -- pass | soft_fail | hard_fail | hard_fail_unrecoverable
    canva_design_id TEXT,
    instagram_published_at TEXT,        -- NULL until Damar publishes
    instagram_post_url TEXT,
    designer_override_diff TEXT,        -- JSON: what Damar changed before publishing
    ig_save_count INTEGER,              -- ingested post-publish
    ig_share_count INTEGER,
    ig_reach INTEGER,
    notes TEXT
);

-- One row per slide.
CREATE TABLE IF NOT EXISTS slide_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES carousel_runs(id),
    slide_index INTEGER NOT NULL,
    layout_family TEXT NOT NULL,
    state TEXT NOT NULL,                -- pending | spec_drafted | image_generated | html_composed | rendered | critic_passed | critic_failed | exported | published
    is_hero_image INTEGER DEFAULT 0,    -- 0=false, 1=true
    image_url TEXT,
    image_seed TEXT,                    -- topic-hash for image consistency (Article 5.1.1)
    image_provider TEXT,                -- codex | playwright_gemini | flowkit | stockphoto
    html_path TEXT,
    png_path TEXT,
    critic_score_brand INTEGER,
    critic_score_typography INTEGER,
    critic_score_copy INTEGER,
    critic_score_image_fit INTEGER,
    critic_hard_failures TEXT,          -- JSON array
    critic_soft_failures TEXT,          -- JSON array
    retries_consumed INTEGER DEFAULT 0,
    last_state_change_at TEXT NOT NULL,
    error TEXT,                         -- non-null if state contains 'failed'
    UNIQUE(run_id, slide_index)
);

-- Index for resume queries
CREATE INDEX IF NOT EXISTS idx_slide_states_run_state ON slide_states(run_id, state);
CREATE INDEX IF NOT EXISTS idx_carousel_runs_topic ON carousel_runs(topic_slug);
CREATE INDEX IF NOT EXISTS idx_carousel_runs_published ON carousel_runs(instagram_published_at) WHERE instagram_published_at IS NOT NULL;

-- Voyager curriculum table — track topic-type representation for underrepresented detection
CREATE TABLE IF NOT EXISTS topic_type_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES carousel_runs(id),
    topic_slug TEXT NOT NULL,
    domain TEXT NOT NULL,
    audience_segment TEXT NOT NULL,
    tone_register_primary TEXT NOT NULL,
    layout_family_primary TEXT NOT NULL,
    is_exploration INTEGER DEFAULT 0,   -- 1 if Voyager-curriculum-driven
    week_number INTEGER NOT NULL        -- ISO week
);

CREATE INDEX IF NOT EXISTS idx_topic_type_log_week_domain ON topic_type_log(week_number, domain);

-- Skill graduation tracking (Voyager) — strengthened bar per Codex FLAW MEDIUM #12
CREATE TABLE IF NOT EXISTS skill_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT UNIQUE NOT NULL,    -- e.g., "split-photo-grid"
    proposed_at TEXT NOT NULL,
    proposed_by TEXT NOT NULL,           -- agent name that proposed
    reflection_lesson TEXT,              -- the lesson that motivated the proposal
    spec_path TEXT NOT NULL,             -- path to layouts/_proposed/<name>.md
    status TEXT NOT NULL,                -- proposed | tested | graduated | archived | rejected
    successful_uses INTEGER DEFAULT 0,
    distinct_topics TEXT,                -- JSON array of topic_slugs
    distinct_months TEXT,                -- JSON array of YYYY-MM
    human_published_count INTEGER DEFAULT 0,
    negative_examples_count INTEGER DEFAULT 0,
    graduated_at TEXT,
    graduated_to_path TEXT,              -- path in layouts/ after graduation
    archived_at TEXT,
    archive_reason TEXT
);

-- Graduation requires (per Codex review):
-- - successful_uses >= 3
-- - LENGTH(distinct_topics) >= 3 (3+ distinct topics, NOT 3 uses on same topic)
-- - LENGTH(distinct_months) >= 2 (≥2 month span)
-- - human_published_count >= 1 (at least one Damar-published proof)
-- - negative_examples_count >= 1 (at least one rejected variant for comparison)
-- These are checked by a graduation cron, not by orchestrator at runtime.

-- Reflexion lessons (weekly cron output)
CREATE TABLE IF NOT EXISTS reflective_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_synthesized TEXT NOT NULL,      -- YYYY-W## ISO week
    lesson_text TEXT NOT NULL,
    motivating_run_ids TEXT NOT NULL,    -- JSON array of carousel_runs.id
    lesson_category TEXT NOT NULL,       -- voice | layout | image | copy | regulatory
    confidence TEXT NOT NULL,            -- low | medium | high (based on N motivating runs + designer-delta strength)
    proposed_amendment_path TEXT,        -- if lesson proposes constitution change
    accepted_at TEXT,                    -- when Antonello commits the lesson
    rejected_at TEXT,
    rejection_reason TEXT
);

-- Resume query (read last-clean-state on restart):
-- SELECT * FROM slide_states WHERE run_id = ? AND state IN ('rendered', 'critic_passed', 'exported')
-- Returns slides that survived a partial run; orchestrator skips these and resumes from
-- the first slide in 'pending' or 'critic_failed' state with retries_consumed < 2.
