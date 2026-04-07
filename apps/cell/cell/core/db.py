"""Database connection for CELL pulse logging."""
import asyncpg
import logging
from typing import Any
from cell.core.config import settings

logger = logging.getLogger("cell.db")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None or _pool._closed:
        logger.info("Creating database connection pool...")
        _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
        logger.info("Database pool created.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None and not _pool._closed:
        await _pool.close()
        logger.info("Database pool closed.")
        _pool = None


async def log_pulse(
    pulse_number: int,
    health_status: str,
    response_time_ms: int,
    dna_intact: bool,
    budget_spent: float,
    budget_limit: float,
    memory_stm_count: int = 0,
    memory_ltm_count: int = 0,
    procedures_count: int = 0,
    cells_active: int = 1,
    cells_total: int = 1,
    action_taken: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO cell_pulse_log
               (pulse_number, health_status, response_time_ms, dna_intact,
                budget_spent, budget_limit, memory_stm_count, memory_ltm_count,
                procedures_count, cells_active, cells_total, action_taken, error_message)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            pulse_number, health_status, response_time_ms, dna_intact,
            budget_spent, budget_limit, memory_stm_count, memory_ltm_count,
            procedures_count, cells_active, cells_total, action_taken, error_message,
        )
    except Exception as e:
        logger.error(f"Failed to log pulse to DB: {e}")


async def create_patterns_table() -> None:
    """Create cell_patterns table if it does not exist."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_patterns (
                id              SERIAL PRIMARY KEY,
                health_status   VARCHAR(16) NOT NULL,
                response_time_ms INTEGER NOT NULL,
                budget_pct      FLOAT NOT NULL,
                action          VARCHAR(64) NOT NULL,
                reason          TEXT NOT NULL,
                confidence      FLOAT NOT NULL,
                tier_used       INTEGER NOT NULL,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_patterns_created_at
            ON cell_patterns (created_at DESC)
        """)
        logger.info("cell_patterns table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_patterns table: {e}")


async def save_pattern(
    health_status: str,
    response_time_ms: int,
    budget_pct: float,
    action: str,
    reason: str,
    confidence: float,
    tier_used: int,
) -> None:
    """Persist a resolved pattern to the DB (fire-and-forget)."""
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO cell_patterns
               (health_status, response_time_ms, budget_pct, action, reason, confidence, tier_used)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            health_status, response_time_ms, budget_pct, action, reason, confidence, tier_used,
        )
    except Exception as e:
        logger.error(f"Failed to save pattern to DB: {e}")


async def load_patterns(limit: int = 500) -> list[dict[str, Any]]:
    """Load most recent patterns from DB. Returns list of dicts."""
    try:
        pool = await get_pool()
        rows = await pool.fetch(
            """SELECT health_status, response_time_ms, budget_pct,
                      action, reason, confidence, tier_used, created_at
               FROM cell_patterns
               ORDER BY created_at DESC
               LIMIT $1""",
            limit,
        )
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to load patterns from DB: {e}")
        return []


async def log_alert(
    level: str,
    action: str,
    message: str,
    health_status: str = "",
    pulse_number: int = 0,
) -> None:
    """Write a silent alert to cell_alerts table (for dashboard + alert_silent action)."""
    try:
        pool = await get_pool()
        await pool.execute(
            """INSERT INTO cell_alerts (level, action, message, health_status, pulse_number)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT DO NOTHING""",
            level, action, message, health_status, pulse_number,
        )
    except Exception as e:
        logger.error(f"Failed to log alert to DB: {e}")


async def create_episodes_table() -> None:
    """Create cell_episodes table for episodic memory."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_episodes (
                id              SERIAL PRIMARY KEY,
                timestamp       DOUBLE PRECISION NOT NULL,
                situation       JSONB NOT NULL,
                emotion         VARCHAR(16) NOT NULL,
                action_taken    VARCHAR(64) NOT NULL,
                outcome         VARCHAR(16) NOT NULL,
                lesson          TEXT NOT NULL,
                recall_count    INTEGER NOT NULL DEFAULT 0,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_episodes_timestamp
            ON cell_episodes (timestamp DESC)
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_episodes_emotion
            ON cell_episodes (emotion)
        """)
        logger.info("cell_episodes table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_episodes table: {e}")


async def create_dreams_table() -> None:
    """Create cell_dreams table for Dreamer nocturnal consolidation."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_dreams (
                id              SERIAL PRIMARY KEY,
                dream_date      DATE NOT NULL,
                episodes_count  INTEGER NOT NULL DEFAULT 0,
                rules_extracted JSONB NOT NULL DEFAULT '[]',
                merged_count    INTEGER NOT NULL DEFAULT 0,
                gaps_identified JSONB NOT NULL DEFAULT '[]',
                summary         TEXT NOT NULL DEFAULT '',
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_dreams_date
            ON cell_dreams (dream_date DESC)
        """)
        logger.info("cell_dreams table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_dreams table: {e}")


async def create_journal_table() -> None:
    """Create cell_journal table for daily narrative entries."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_journal (
                id              SERIAL PRIMARY KEY,
                journal_date    DATE NOT NULL UNIQUE,
                narrative       TEXT NOT NULL,
                emotion_summary VARCHAR(32) NOT NULL DEFAULT 'calm',
                actions_taken   INTEGER NOT NULL DEFAULT 0,
                lessons_count   INTEGER NOT NULL DEFAULT 0,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_journal_date
            ON cell_journal (journal_date DESC)
        """)
        logger.info("cell_journal table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_journal table: {e}")


# ---------------------------------------------------------------------------
# Phase 3+4 — Cortex tables
# ---------------------------------------------------------------------------

_CREATE_CELL_SKILLS = """
CREATE TABLE IF NOT EXISTS cell_skills (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    trigger_nl      TEXT,
    action_sequence JSONB,
    rationale_nl    TEXT,
    fitness         DOUBLE PRECISION DEFAULT 0.0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    use_count       INTEGER DEFAULT 0,
    generation      INTEGER DEFAULT 0,
    parent_id       INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    embedding       BYTEA,
    status          VARCHAR(16) DEFAULT 'candidate'
                    CHECK (status IN ('active','candidate','frozen','apoptosed')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    last_decay_check TIMESTAMPTZ DEFAULT NOW()
)
"""

_CREATE_CELL_SKILLS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_skills_active_fitness ON cell_skills (status, fitness DESC) WHERE status = 'active'",
    "CREATE INDEX IF NOT EXISTS idx_cell_skills_parent ON cell_skills (parent_id)",
    "CREATE INDEX IF NOT EXISTS idx_cell_skills_last_used ON cell_skills (last_used_at DESC NULLS LAST)",
]

_CREATE_CELL_CRITIC_EXPECTATIONS = """
CREATE TABLE IF NOT EXISTS cell_critic_expectations (
    id                      SERIAL PRIMARY KEY,
    pulse_number            INTEGER,
    episode_id              INTEGER REFERENCES cell_episodes(id) ON DELETE CASCADE,
    action                  VARCHAR(64),
    skill_id                INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    expected_outcome        VARCHAR(16),
    expected_rt_delta_ms    INTEGER DEFAULT 0,
    expected_health_in_n    VARCHAR(16),
    n_pulses_horizon        INTEGER DEFAULT 5,
    confidence_at_proposal  DOUBLE PRECISION,
    rationale_nl            TEXT DEFAULT '',
    critique_id             INTEGER,
    created_at              TIMESTAMPTZ DEFAULT NOW()
)
"""

_CREATE_CELL_CRITIC_EXPECTATIONS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_critic_exp_pending ON cell_critic_expectations (pulse_number) WHERE critique_id IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_cell_critic_exp_episode ON cell_critic_expectations (episode_id)",
]

_CREATE_CELL_CRITIQUES = """
CREATE TABLE IF NOT EXISTS cell_critiques (
    id                  SERIAL PRIMARY KEY,
    expectation_id      INTEGER REFERENCES cell_critic_expectations(id) ON DELETE CASCADE,
    pulse_number        INTEGER,
    actual_outcome      VARCHAR(16),
    actual_rt_delta_ms  INTEGER DEFAULT 0,
    actual_health       VARCHAR(16),
    miscalibration      DOUBLE PRECISION,
    self_critique_nl    TEXT,
    weakness_tag        VARCHAR(64),
    created_at          TIMESTAMPTZ DEFAULT NOW()
)
"""

_CREATE_CELL_CRITIQUES_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_critiques_weakness ON cell_critiques (weakness_tag) WHERE weakness_tag IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_cell_critiques_miscalib ON cell_critiques (miscalibration DESC)",
]

_CREATE_CELL_GOALS = """
CREATE TABLE IF NOT EXISTS cell_goals (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(32),
    question            TEXT,
    motivation          TEXT,
    priority            DOUBLE PRECISION,
    feasibility         DOUBLE PRECISION,
    novelty             DOUBLE PRECISION,
    score               DOUBLE PRECISION,
    status              VARCHAR(16) DEFAULT 'pending'
                        CHECK (status IN ('pending','investigating','resolved','abandoned','archived')),
    findings            TEXT,
    related_skill_id    INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
)
"""

_CREATE_CELL_GOALS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_goals_active ON cell_goals (status, score DESC) WHERE status IN ('pending','investigating')",
    "CREATE INDEX IF NOT EXISTS idx_cell_goals_source ON cell_goals (source, created_at DESC)",
]

_CREATE_CELL_CURIOSITY_FINDINGS = """
CREATE TABLE IF NOT EXISTS cell_curiosity_findings (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(32),
    question            TEXT,
    method              TEXT,
    finding             TEXT,
    actionable          BOOLEAN DEFAULT FALSE,
    information_gain    DOUBLE PRECISION DEFAULT 0.0,
    related_goal_id     INTEGER REFERENCES cell_goals(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
)
"""

_CREATE_CELL_CURIOSITY_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_curiosity_created ON cell_curiosity_findings (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cell_curiosity_actionable ON cell_curiosity_findings (actionable, information_gain DESC) WHERE actionable = TRUE",
]

_CREATE_CELL_SKILL_AUDIT = """
CREATE TABLE IF NOT EXISTS cell_skill_audit (
    id                  SERIAL PRIMARY KEY,
    skill_id            INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    parent_skill_id     INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    action              VARCHAR(32),
    reason              TEXT,
    sandbox_score       DOUBLE PRECISION,
    pattern_match_rate  DOUBLE PRECISION,
    safety_violations   JSONB DEFAULT '[]',
    dna_check           BOOLEAN,
    operator            VARCHAR(64) DEFAULT 'cortex',
    created_at          TIMESTAMPTZ DEFAULT NOW()
)
"""

_CREATE_CELL_SKILL_AUDIT_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_skill_audit_skill ON cell_skill_audit (skill_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cell_skill_audit_action ON cell_skill_audit (action, created_at DESC)",
]

_CREATE_CELL_MUTATIONS = """
CREATE TABLE IF NOT EXISTS cell_mutations (
    id                  SERIAL PRIMARY KEY,
    skill_id            INTEGER REFERENCES cell_skills(id) ON DELETE CASCADE,
    parent_skill_id     INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    parent_fitness      DOUBLE PRECISION,
    monitor_until       TIMESTAMPTZ,
    monitored_at        TIMESTAMPTZ,
    final_fitness       DOUBLE PRECISION,
    outcome             VARCHAR(16),
    created_at          TIMESTAMPTZ DEFAULT NOW()
)
"""

_CREATE_CELL_MUTATIONS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_mutations_pending ON cell_mutations (monitor_until) WHERE outcome IS NULL",
]


async def create_cortex_tables() -> None:
    """Create all Phase 3+4 cortex tables. Idempotent."""
    try:
        pool = await get_pool()
        for stmt in [
            _CREATE_CELL_SKILLS,
            _CREATE_CELL_CRITIC_EXPECTATIONS,
            _CREATE_CELL_CRITIQUES,
            _CREATE_CELL_GOALS,
            _CREATE_CELL_CURIOSITY_FINDINGS,
            _CREATE_CELL_SKILL_AUDIT,
            _CREATE_CELL_MUTATIONS,
        ]:
            await pool.execute(stmt)
        for group in [
            _CREATE_CELL_SKILLS_INDICES,
            _CREATE_CELL_CRITIC_EXPECTATIONS_INDICES,
            _CREATE_CELL_CRITIQUES_INDICES,
            _CREATE_CELL_GOALS_INDICES,
            _CREATE_CELL_CURIOSITY_INDICES,
            _CREATE_CELL_SKILL_AUDIT_INDICES,
            _CREATE_CELL_MUTATIONS_INDICES,
        ]:
            for stmt in group:
                await pool.execute(stmt)
        logger.info(
            "cortex tables ready (cell_skills, cell_critic_expectations, "
            "cell_critiques, cell_goals, cell_curiosity_findings, "
            "cell_skill_audit, cell_mutations)"
        )
    except Exception as e:
        logger.error(f"Failed to create cortex tables: {e}")
