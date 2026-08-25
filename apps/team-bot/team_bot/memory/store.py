"""SqliteMemberMemoryStore — the three-layer per-member memory (owner
directive #1 §3), sqlite-backed.

Steals the CAS/idempotent-branch shape from `team_bot.confirmation.store`
(same repo, same lane, already reviewed) where it applies: an upsert is one
`INSERT ... ON CONFLICT DO UPDATE`, re-read after write rather than trusting
the write call's own return value. It does NOT steal `PendingAction`'s
`leader_epoch`/PROPOSED->CONFIRMED->EXECUTED gate — see "Cross-lane note on
the F6/F9 epoch gap" below for why that is a deliberate omission, not an
oversight.

**PII boundary**: every value this store persists is either an opaque ID
(`principal_id`, `target_id`) or a closed enum (see `models.py`'s module
docstring for the full argument). This module never accepts, and the
schema below has no column that could hold, a client's `full_name`, phone
number, passport/KTP/NPWP number, or the text of a chat message. There is
therefore no encryption-at-rest concern of the kind
`confirmation/crypto.py`'s `ArgsCipher` exists to solve — that module
protects a mutation's ARGUMENTS (which legitimately carry business data:
practice IDs, status transitions); this store never holds anything whose
exposure would be a Law 2 (CLAUDE.md §14) output-frontier breach in the
first place, so there is nothing here for a cipher to protect.

**Cross-lane note on the F6/F9 epoch gap** (`docs/plans/2026-08-25-due-bot-live/
ops/F6-F9-PENDING-ACTION-EPOCH-GAP.md` — read that file before touching
this one). B5 named an OPEN question: what is the failover contract for
per-node SQLite state that is not the F9 leader record itself? This store
is a SECOND consumer of exactly that gap — the directive's own words
("sqlite Mini, replicato Pro — la memoria sopravvive al failover") assume
a resolution that does not exist yet. This module deliberately does NOT
invent one:

- No `leader_epoch` field, no live or cached read of F9's
  `IngressLeaderStore`. Unlike `PendingAction` (a mutation gate, where a
  stale-epoch write means an unconfirmed CRM action could execute twice
  from two nodes), a memory write here is idempotent-ish by construction —
  `upsert_profile` is last-write-wins, `record_episodic_event` is an
  insert with no cross-node uniqueness assumed, `record_pattern_signal`'s
  counter can double-count under a split-brain but nothing safety-relevant
  depends on that counter being exact (it only ever feeds a "did this come
  up more than once" proactivity nudge, never a CRM mutation or an RBAC
  decision). Concretely: a genuine Mini/Pro split-brain (both nodes
  writing independently) degrades this store to "occasionally
  double-counts a pattern or duplicates one episodic row" — a quality
  regression, not the safety-tier failure class F9's leader-epoch CAS
  exists to prevent for `PendingAction`.
- Mini -> Pro REPLICATION ITSELF IS NOT BUILT HERE — this store is
  single-node, exactly like `SqlitePendingActionStore` ("concurrent
  multi-process writers are out of scope for this unit"). "The memory
  survives failover" (the directive's phrase) is therefore NOT true yet
  for this lane's shipped code — it is true only once someone builds
  Mini<->Pro replication, and that replication mechanism is one of B5's
  own candidate resolution shapes for the SAME gap ("Mini -> Pro SQLite
  replication gets built"). Building a second, independent replication
  scheme here — instead of waiting for whatever the owner rules on for
  F6 — would be a second private answer to a question B5 explicitly
  flagged as "not B5's call to make alone"; it is not this lane's call
  either. See the orchestrator report for the explicit cross-lane
  question this raises.

Author: Claude Sonnet 5 (lane B8 — per-member memory)
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.confirmation.models import PRINCIPAL_ID_PATTERN
from team_bot.confirmation.outcomes import Locale
from team_bot.registry.envelope import TARGET_ID_PATTERN

from .models import (
    PATTERN_KEY_PATTERN,
    WORKING_HOURS_PATTERN,
    EpisodicEvent,
    IntentCategory,
    LearnedPattern,
    MemberProfile,
    ResponseFormat,
    StaffRole,
    TargetType,
)

__all__ = [
    "DEFAULT_MAX_EPISODIC_PER_PRINCIPAL",
    "DEFAULT_MIN_PATTERN_OBSERVATIONS",
    "ForgetResult",
    "ForgetScope",
    "SqliteMemberMemoryStore",
]

DEFAULT_MAX_EPISODIC_PER_PRINCIPAL = 50  # bounded retention — no unbounded growth per member
DEFAULT_MIN_PATTERN_OBSERVATIONS = 2  # a pattern seen once is noise, not a habit

_SCHEMA = """
CREATE TABLE IF NOT EXISTS member_profile (
    principal_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    preferred_language TEXT NOT NULL,
    response_format TEXT NOT NULL,
    working_hours_start TEXT,
    working_hours_end TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episodic_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    principal_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    intent_category TEXT NOT NULL,
    tool_name TEXT,
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_episodic_event_principal_occurred
    ON episodic_event(principal_id, occurred_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_episodic_event_principal_target
    ON episodic_event(principal_id, target_id);
CREATE TABLE IF NOT EXISTS learned_pattern (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    principal_id TEXT NOT NULL,
    pattern_key TEXT NOT NULL,
    observation_count INTEGER NOT NULL DEFAULT 1,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_learned_pattern_principal_key
    ON learned_pattern(principal_id, pattern_key);
"""


class ForgetScope(StrEnum):
    """What "dimentica X" (`forget_input.py`) actually erases."""

    MEMBER = "member"  # full wipe: profile + every episodic row + every pattern row
    TARGET = "target"  # episodic rows referencing exactly one target_id


class ForgetResult(BaseModel):
    """Proof of deletion, not an assertion. Every count here is a real
    ``cursor.rowcount`` from a ``DELETE`` this call actually issued — never
    a caller-supplied or estimated number."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: ForgetScope
    principal_id: Annotated[str, Field(pattern=PRINCIPAL_ID_PATTERN)]
    target_id: Annotated[str, Field(pattern=TARGET_ID_PATTERN)] | None = None
    profile_rows_deleted: Annotated[int, Field(ge=0)]
    episodic_rows_deleted: Annotated[int, Field(ge=0)]
    pattern_rows_deleted: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _scope_constrains_target(self) -> ForgetResult:
        if self.scope == ForgetScope.TARGET and self.target_id is None:
            raise ValueError("target_id is required when scope is target")
        if self.scope == ForgetScope.MEMBER and self.target_id is not None:
            raise ValueError("target_id must be unset when scope is member")
        return self

    @property
    def total_rows_deleted(self) -> int:
        return self.profile_rows_deleted + self.episodic_rows_deleted + self.pattern_rows_deleted


def _row_to_profile(row: sqlite3.Row) -> MemberProfile:
    return MemberProfile(
        principal_id=row["principal_id"],
        role=StaffRole(row["role"]),
        preferred_language=Locale(row["preferred_language"]),
        response_format=ResponseFormat(row["response_format"]),
        working_hours_start=row["working_hours_start"],
        working_hours_end=row["working_hours_end"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_event(row: sqlite3.Row) -> EpisodicEvent:
    return EpisodicEvent(
        principal_id=row["principal_id"],
        target_type=TargetType(row["target_type"]),
        target_id=row["target_id"],
        intent_category=IntentCategory(row["intent_category"]),
        tool_name=row["tool_name"],
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
    )


def _row_to_pattern(row: sqlite3.Row) -> LearnedPattern:
    return LearnedPattern(
        principal_id=row["principal_id"],
        pattern_key=row["pattern_key"],
        observation_count=row["observation_count"],
        first_observed_at=datetime.fromisoformat(row["first_observed_at"]),
        last_observed_at=datetime.fromisoformat(row["last_observed_at"]),
    )


class SqliteMemberMemoryStore:
    """Single-connection, synchronous — same "one process, no
    concurrent-writer contract" scope as `SqlitePendingActionStore` (see
    module docstring's cross-lane note)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        max_episodic_per_principal: int = DEFAULT_MAX_EPISODIC_PER_PRINCIPAL,
    ) -> None:
        conn.row_factory = sqlite3.Row
        self._conn = conn
        self._max_episodic = max_episodic_per_principal
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── layer 1: profile ────────────────────────────────────────────

    def upsert_profile(
        self,
        *,
        principal_id: str,
        role: StaffRole,
        preferred_language: Locale,
        now: datetime,
        response_format: ResponseFormat = ResponseFormat.CONCISE,
        working_hours_start: str | None = None,
        working_hours_end: str | None = None,
    ) -> MemberProfile:
        if working_hours_start is not None and not _matches(WORKING_HOURS_PATTERN, working_hours_start):
            raise ValueError(f"working_hours_start {working_hours_start!r} is not HH:MM")
        if working_hours_end is not None and not _matches(WORKING_HOURS_PATTERN, working_hours_end):
            raise ValueError(f"working_hours_end {working_hours_end!r} is not HH:MM")

        self._conn.execute(
            """
            INSERT INTO member_profile
                (principal_id, role, preferred_language, response_format,
                 working_hours_start, working_hours_end, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(principal_id) DO UPDATE SET
                role = excluded.role,
                preferred_language = excluded.preferred_language,
                response_format = excluded.response_format,
                working_hours_start = excluded.working_hours_start,
                working_hours_end = excluded.working_hours_end,
                updated_at = excluded.updated_at
            """,
            (
                principal_id,
                role.value,
                preferred_language.value,
                response_format.value,
                working_hours_start,
                working_hours_end,
                now.isoformat(),
            ),
        )
        self._conn.commit()
        profile = self.get_profile(principal_id)
        assert profile is not None  # just wrote it, under the same connection
        return profile

    def get_profile(self, principal_id: str) -> MemberProfile | None:
        row = self._conn.execute(
            "SELECT * FROM member_profile WHERE principal_id = ?", (principal_id,)
        ).fetchone()
        return _row_to_profile(row) if row is not None else None

    # ── layer 2: episodic ────────────────────────────────────────────

    def record_episodic_event(
        self,
        *,
        principal_id: str,
        target_type: TargetType,
        target_id: str,
        intent_category: IntentCategory,
        now: datetime,
        tool_name: str | None = None,
    ) -> EpisodicEvent:
        expected_prefix = "CL-" if target_type == TargetType.CLIENT else "PR-"
        if not target_id.startswith(expected_prefix):
            raise ValueError(
                f"target_id {target_id!r} does not match target_type "
                f"{target_type.value!r} (expected prefix {expected_prefix!r})"
            )

        cur = self._conn.execute(
            """
            INSERT INTO episodic_event
                (principal_id, target_type, target_id, intent_category, tool_name, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (principal_id, target_type.value, target_id, intent_category.value, tool_name, now.isoformat()),
        )
        new_id = cur.lastrowid
        # Bounded retention: keep only the newest `max_episodic` rows for
        # this principal — a member's episodic memory does not grow
        # forever. Mirrors `expire_stale`'s sweep-after-write shape in
        # confirmation/store.py, but runs inline (this table has no TTL
        # concept — "recent" is defined by rank, not by expiry).
        self._conn.execute(
            """
            DELETE FROM episodic_event
            WHERE principal_id = ?
              AND id NOT IN (
                  SELECT id FROM episodic_event
                  WHERE principal_id = ?
                  ORDER BY occurred_at DESC, id DESC
                  LIMIT ?
              )
            """,
            (principal_id, principal_id, self._max_episodic),
        )
        self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM episodic_event WHERE id = ?", (new_id,)
        ).fetchone()
        return _row_to_event(row)

    def list_recent_episodic(self, principal_id: str, *, limit: int = 5) -> tuple[EpisodicEvent, ...]:
        rows = self._conn.execute(
            """
            SELECT * FROM episodic_event
            WHERE principal_id = ?
            ORDER BY occurred_at DESC, id DESC
            LIMIT ?
            """,
            (principal_id, limit),
        ).fetchall()
        return tuple(_row_to_event(r) for r in rows)

    # ── layer 3: learned patterns ────────────────────────────────────

    def record_pattern_signal(
        self, *, principal_id: str, pattern_key: str, now: datetime
    ) -> LearnedPattern:
        if not _matches(PATTERN_KEY_PATTERN, pattern_key):
            raise ValueError(f"pattern_key {pattern_key!r} does not match {PATTERN_KEY_PATTERN}")

        self._conn.execute(
            """
            INSERT INTO learned_pattern
                (principal_id, pattern_key, observation_count, first_observed_at, last_observed_at)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(principal_id, pattern_key) DO UPDATE SET
                observation_count = observation_count + 1,
                last_observed_at = excluded.last_observed_at
            """,
            (principal_id, pattern_key, now.isoformat(), now.isoformat()),
        )
        self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM learned_pattern WHERE principal_id = ? AND pattern_key = ?",
            (principal_id, pattern_key),
        ).fetchone()
        return _row_to_pattern(row)

    def list_patterns(
        self,
        principal_id: str,
        *,
        min_observations: int = DEFAULT_MIN_PATTERN_OBSERVATIONS,
        limit: int = 5,
    ) -> tuple[LearnedPattern, ...]:
        rows = self._conn.execute(
            """
            SELECT * FROM learned_pattern
            WHERE principal_id = ? AND observation_count >= ?
            ORDER BY observation_count DESC, last_observed_at DESC
            LIMIT ?
            """,
            (principal_id, min_observations, limit),
        ).fetchall()
        return tuple(_row_to_pattern(r) for r in rows)

    # ── forget ───────────────────────────────────────────────────────

    def forget_member(self, *, principal_id: str, now: datetime) -> ForgetResult:
        """Full erasure: profile row + every episodic row + every pattern
        row for this principal. Real ``DELETE`` statements, committed
        before this returns — nothing left for a later read to find. ``now``
        is accepted (unused in the query itself) for call-site symmetry
        with the rest of this store's clock-discipline and to leave room
        for an audit-log caller to stamp "forgotten at" without this method
        reaching for a wall clock itself."""
        del now
        cur = self._conn.execute("DELETE FROM member_profile WHERE principal_id = ?", (principal_id,))
        profile_deleted = cur.rowcount
        cur = self._conn.execute("DELETE FROM episodic_event WHERE principal_id = ?", (principal_id,))
        episodic_deleted = cur.rowcount
        cur = self._conn.execute("DELETE FROM learned_pattern WHERE principal_id = ?", (principal_id,))
        pattern_deleted = cur.rowcount
        self._conn.commit()
        return ForgetResult(
            scope=ForgetScope.MEMBER,
            principal_id=principal_id,
            target_id=None,
            profile_rows_deleted=profile_deleted,
            episodic_rows_deleted=episodic_deleted,
            pattern_rows_deleted=pattern_deleted,
        )

    def forget_target(self, *, principal_id: str, target_id: str, now: datetime) -> ForgetResult:
        """Narrow erasure: episodic rows referencing exactly one
        ``target_id`` for this principal. Profile and patterns are left
        untouched — a pattern_key never encodes a target_id (closed
        vocabulary, `models.py`), so there is nothing target-specific to
        remove from that layer."""
        del now
        cur = self._conn.execute(
            "DELETE FROM episodic_event WHERE principal_id = ? AND target_id = ?",
            (principal_id, target_id),
        )
        episodic_deleted = cur.rowcount
        self._conn.commit()
        return ForgetResult(
            scope=ForgetScope.TARGET,
            principal_id=principal_id,
            target_id=target_id,
            profile_rows_deleted=0,
            episodic_rows_deleted=episodic_deleted,
            pattern_rows_deleted=0,
        )

    # ── introspection (tests + the forget-completeness proof) ────────

    def count_rows_for_principal(self, principal_id: str) -> dict[str, int]:
        """Raw row counts across all three tables for one principal —
        exists so a test can prove "gone from every layer", not just
        "absent from the render", per the team lead's own bar. Reads the
        actual tables directly, not through any model — this is the
        introspection primitive the forget-completeness test is built on."""
        counts: dict[str, int] = {}
        for table in ("member_profile", "episodic_event", "learned_pattern"):
            (n,) = self._conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE principal_id = ?", (principal_id,)
            ).fetchone()
            counts[table] = n
        return counts


def _matches(pattern: str, value: str) -> bool:
    return re.match(pattern, value) is not None
