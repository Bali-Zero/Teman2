"""Portal Champion challenge — Round 2 "Lascia o raddoppia" (October window).

Round 1 (`challenge_leaderboard.py`) is FROZEN — its window, tiers and scoring
never change again after 2026-09-29 00:00 WITA. This module is the Round 2
engine: a client-count carried from September plus a general-competition
scoring system (registrations, first-document bonuses, response/review-time
penalties) and a separate personal mission for Asya.

Window: 2026-09-29 00:00 WITA (Asia/Makassar) inclusive → 2026-10-30 00:00
WITA exclusive — the start moved from 09-30 to 09-29 on Zero's 2026-09-29
call; Round 1 closes at that same instant, so no registration is counted in
both the September carry and October's points. Fixed for this round — no CLI/query override, same reasoning
as R1 (the live endpoint and the offline report can never disagree about
"when").

This module has NO asyncpg/FastAPI import at module level — only stdlib (plus
the sibling `challenge_leaderboard` module, itself stdlib-only) — so a plain
`python3` process (the script) can import it without the backend venv. DB
access stays with the caller: this module hands back SQL text + pure Python
transforms, never opens a connection itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from backend.services.portal.challenge_leaderboard import (
    REAL_CLIENTS_CTE,
    WITA,
    AwardedEntry,
    _is_real_staff_row,
    build_aggregates_sql_for_window,
    build_recent_activations_sql_for_window,
    build_team_total_activations_sql_for_window,
    member_key_from_email,
)
from backend.services.portal.challenge_leaderboard import WINDOW_END as R1_WINDOW_END
from backend.services.portal.challenge_leaderboard import WINDOW_START as R1_WINDOW_START

ROUND2_START = datetime(2026, 9, 29, 0, 0, tzinfo=WITA)
ROUND2_END = datetime(2026, 10, 30, 0, 0, tzinfo=WITA)  # exclusive

# Zero's ruling, 2026-09-29: these three took the September prize ("Ambil
# hadiah") and start October at 0. Everyone else carries their September
# activations ("Bawa poin" — the default for non-winners).
SEPTEMBER_PRIZE_TAKEN: frozenset[str] = frozenset(
    {"surya@balizero.com", "ari.firda@balizero.com", "krisna@balizero.com"}
)

# Zero's ruling, 2026-09-29: Round 2 is ranked and prized among the six
# September players ONLY. Anyone else's events are counted-not-credited,
# exactly like unattributed ones.
ROUND2_PARTICIPANTS: frozenset[str] = frozenset(
    {
        "ari.firda@balizero.com",
        "surya@balizero.com",
        "krisna@balizero.com",
        "adit@balizero.com",
        "vino@balizero.com",
        "damar@balizero.com",
    }
)

REGISTRATION_POINTS = 1
FIRST_DOCUMENT_POINTS = 3
UNANSWERED_REQUEST_PENALTY = 2
UNREVIEWED_DOCUMENT_PENALTY = 1
RESPONSE_WORKING_HOURS_LIMIT = 3.0
REVIEW_WORKING_HOURS_LIMIT = 9.5  # one working day

RANK_PRIZES_IDR: dict[int, int] = {
    1: 6_000_000,
    2: 3_500_000,
    3: 2_000_000,
    4: 1_000_000,
    5: 700_000,
}

ASYA_EMAIL = "asya@balizero.com"
ASYA_TARGET_POINTS = 60
ASYA_PRIZE_IDR = 1_000_000
ASYA_BONUS_POINTS = 3
ASYA_REQUEST_LOOKBACK_DAYS = 30

# ── Working hours ────────────────────────────────────────────────────────
# Senin-Jumat 09.00-18.30 WITA (Asia/Makassar), 9.5h/day. No holidays yet —
# the guide says the holiday rule is announced separately; this stays an
# empty frozenset until that announcement lands, never a hardcoded list.
WORKDAY_START = time(9, 0)
WORKDAY_END = time(18, 30)
WORKDAY_HOURS = 9.5
HOLIDAYS: frozenset[date] = frozenset()


def _to_wita(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(WITA)


def _is_workday(day: date) -> bool:
    return day.weekday() < 5 and day not in HOLIDAYS


def working_hours_between(start: datetime, end: datetime) -> float:
    """Working hours elapsed between two datetimes, Mon-Fri 09:00-18:30 WITA.

    Naive inputs are treated as UTC (per spec) before converting to WITA.
    Reproduces the team guide's example exactly: Friday 17:00 -> Monday
    10:30 = 3.0h (1.5h Friday remainder + 1.5h Monday morning; the weekend
    contributes nothing).
    """
    start_w = _to_wita(start)
    end_w = _to_wita(end)
    if end_w <= start_w:
        return 0.0

    total_hours = 0.0
    cursor_date = start_w.date()
    end_date = end_w.date()
    while cursor_date <= end_date:
        if _is_workday(cursor_date):
            day_start = datetime.combine(cursor_date, WORKDAY_START, tzinfo=WITA)
            day_end = datetime.combine(cursor_date, WORKDAY_END, tzinfo=WITA)
            overlap_start = max(start_w, day_start)
            overlap_end = min(end_w, day_end)
            if overlap_start < overlap_end:
                total_hours += (overlap_end - overlap_start).total_seconds() / 3600.0
        cursor_date += timedelta(days=1)
    return total_hours


def working_deadline(start: datetime, hours: float) -> datetime:
    """Inverse of `working_hours_between`: the datetime at which `hours` of
    working time have elapsed from `start`. Used for the same-incident
    dedupe window and for "penalty fires at" displays."""
    cursor = _to_wita(start)
    remaining = hours
    while True:
        cursor_date = cursor.date()
        if _is_workday(cursor_date):
            day_end = datetime.combine(cursor_date, WORKDAY_END, tzinfo=WITA)
            day_business_start = datetime.combine(cursor_date, WORKDAY_START, tzinfo=WITA)
            day_start = max(cursor, day_business_start)
            if day_start < day_end:
                available = (day_end - day_start).total_seconds() / 3600.0
                if available >= remaining:
                    return day_start + timedelta(hours=remaining)
                remaining -= available
        cursor = datetime.combine(cursor_date + timedelta(days=1), time(0, 0), tzinfo=WITA)


# ── Round selection ──────────────────────────────────────────────────────


def active_round(now: datetime) -> int:
    """1 while `now < ROUND2_START`, 2 from then on. `upcoming` never occurs
    for R2 in practice (the spec is written the moment before R2 opens)."""
    return 1 if now < ROUND2_START else 2


def compute_round_status(now: datetime, round_number: int) -> str:
    """upcoming | live | closed, for either round's own fixed window."""
    if round_number == 1:
        start, end = R1_WINDOW_START, R1_WINDOW_END
    else:
        start, end = ROUND2_START, ROUND2_END
    if now < start:
        return "upcoming"
    if now < end:
        return "live"
    return "closed"


# ── SQL ──────────────────────────────────────────────────────────────────
# Same convention as challenge_leaderboard.py: literals baked into the SQL
# text, no bind params (except `build_asya_client_events_sql`'s bind-free
# text mirrors that pattern too) — the offline script runs this exact text
# through `pg.sh`.


def _window_ts() -> tuple[str, str]:
    return ROUND2_START.isoformat(), ROUND2_END.isoformat()


def build_registration_aggregates_sql() -> str:
    """Per-creator registrations/invited/last_activation_at inside the R2
    window — same CTE shape as R1's `build_aggregates_sql`, parameterised."""
    start_ts, end_ts = _window_ts()
    return build_aggregates_sql_for_window(start_ts, end_ts)


def build_recent_registrations_sql() -> str:
    """Last 10 registration events inside the R2 window. No client data."""
    start_ts, end_ts = _window_ts()
    return build_recent_activations_sql_for_window(start_ts, end_ts)


def build_team_total_registrations_sql() -> str:
    """DISTINCT client_id across the R2 window — see R1's equivalent for why
    this must never be a sum of per-creator counts."""
    start_ts, end_ts = _window_ts()
    return build_team_total_activations_sql_for_window(start_ts, end_ts)


def build_goal_lookup_sql() -> str:
    """Identify a just-registered client's creator, R2 window — the live
    goal celebration's identity lookup. The "activations" column this
    returns (a raw registration count, R1-style) is NOT what the R2 goal
    displays: the caller re-scores the creator's full R2 `points` via the
    normal SQL + `score_round2` pipeline and uses that instead."""
    from backend.services.portal.challenge_leaderboard import build_goal_sql_for_window

    start_ts, end_ts = _window_ts()
    return build_goal_sql_for_window(start_ts, end_ts)


def build_first_documents_sql() -> str:
    """First client-uploaded document per practice, EVER (not just inside
    the window) — the outer WHERE then keeps only the rows whose overall
    first document happens to fall inside the R2 window. A practice whose
    real first document predates the window therefore never appears here,
    which is exactly the "no bonus, ever" rule: the pure scorer downstream
    sees only qualifying rows and does not need to re-check the date."""
    start_ts, end_ts = _window_ts()
    return f"""
WITH {REAL_CLIENTS_CTE},
first_doc AS (
    SELECT d.practice_id, MIN(d.created_at) AS first_doc_at
    FROM documents d
    JOIN practices p ON p.id = d.practice_id
    JOIN real_clients c ON c.id = p.client_id
    WHERE d.uploaded_source = 'client'
      AND d.deleted_at IS NULL
      AND d.is_archived IS NOT TRUE
      AND d.practice_id IS NOT NULL
      AND p.status <> 'cancelled'
    GROUP BY d.practice_id
)
SELECT fd.practice_id, fd.first_doc_at, p.client_id,
       lower(p.assigned_to) AS practice_assignee,
       lower(cl.assigned_to) AS client_assignee
FROM first_doc fd
JOIN practices p ON p.id = fd.practice_id
JOIN real_clients c ON c.id = p.client_id
JOIN clients cl ON cl.id = c.id
WHERE fd.first_doc_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
  AND fd.first_doc_at <  TIMESTAMP WITH TIME ZONE '{end_ts}';
""".strip()


def build_client_requests_sql() -> str:
    """Client request rows inside the R2 window: one row per pending
    request, `reply_at` = the first staff reply after it (NULL if still
    open). Predicate mirrors `portal_reply_service.py::_PENDING_QUERY`."""
    start_ts, end_ts = _window_ts()
    return f"""
WITH {REAL_CLIENTS_CTE}
SELECT pm.client_id, pm.practice_id, pm.created_at,
       (SELECT MIN(reply.created_at) FROM portal_messages reply
        WHERE reply.client_id = pm.client_id
          AND reply.direction = 'team_to_client'
          AND reply.is_system_generated = FALSE
          AND (reply.created_at, reply.id) > (pm.created_at, pm.id)) AS reply_at,
       lower(cl.assigned_to) AS client_assignee,
       lower(p.assigned_to) AS practice_assignee
FROM portal_messages pm
JOIN real_clients c ON c.id = pm.client_id
JOIN clients cl ON cl.id = c.id
LEFT JOIN practices p ON p.id = pm.practice_id
WHERE pm.direction = 'client_to_team'
  AND pm.is_system_generated = FALSE
  AND COALESCE(pm.sent_by, '') <> 'portal'
  AND pm.created_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
  AND pm.created_at <  TIMESTAMP WITH TIME ZONE '{end_ts}';
""".strip()


def build_required_document_reviews_sql() -> str:
    """Client-uploaded required-document rows whose `uploaded_at` falls
    inside the R2 window (both bounds — an upload on/after ROUND2_END
    belongs to whatever comes after Round 2, never to this round's -1
    penalty). `review_at` is `updated_at` when a staff review happened
    (`status` moved off `uploaded`/`pending`), else NULL. Naive
    `uploaded_at`/`updated_at` columns are stored as UTC via `NOW()` — cast
    with `AT TIME ZONE 'UTC'` to hand the caller a tz-aware value."""
    start_ts, end_ts = _window_ts()
    return f"""
WITH {REAL_CLIENTS_CTE}
SELECT prd.id, prd.practice_id, p.client_id,
       (prd.uploaded_at AT TIME ZONE 'UTC') AS uploaded_at,
       CASE WHEN prd.status NOT IN ('uploaded', 'pending')
            THEN (prd.updated_at AT TIME ZONE 'UTC') END AS review_at,
       lower(p.assigned_to) AS practice_assignee,
       lower(cl.assigned_to) AS client_assignee
FROM practice_required_documents prd
JOIN practices p ON p.id = prd.practice_id
JOIN real_clients c ON c.id = p.client_id
JOIN clients cl ON cl.id = c.id
WHERE prd.uploaded_by_client = TRUE
  AND (prd.uploaded_at AT TIME ZONE 'UTC') >= TIMESTAMP WITH TIME ZONE '{start_ts}'
  AND (prd.uploaded_at AT TIME ZONE 'UTC') <  TIMESTAMP WITH TIME ZONE '{end_ts}'
  AND p.status <> 'cancelled';
""".strip()


def build_asya_requests_sql() -> str:
    """Every non-system `team_to_client` message Asya sent, per client — the
    lookback source for her mission bonus (not window-limited: a qualifying
    R2 event's message can be up to 30 days BEFORE the window opened)."""
    return f"""
WITH {REAL_CLIENTS_CTE}
SELECT pm.client_id, pm.created_at
FROM portal_messages pm
JOIN real_clients c ON c.id = pm.client_id
WHERE pm.direction = 'team_to_client'
  AND pm.is_system_generated = FALSE
  AND lower(pm.sent_by) = '{ASYA_EMAIL}'
ORDER BY pm.client_id, pm.created_at;
""".strip()


def build_asya_client_events_sql() -> str:
    """Client document uploads inside the R2 window — ANY upload counts for
    Asya's mission (unlike the general first-document-per-practice bonus).
    Combined by the caller with `build_client_requests_sql`'s rows (the
    other qualifying event kind) before scoring."""
    start_ts, end_ts = _window_ts()
    return f"""
WITH {REAL_CLIENTS_CTE}
SELECT d.client_id, d.practice_id, d.created_at
FROM documents d
JOIN real_clients c ON c.id = d.client_id
WHERE d.uploaded_source = 'client'
  AND d.deleted_at IS NULL
  AND d.created_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
  AND d.created_at <  TIMESTAMP WITH TIME ZONE '{end_ts}';
""".strip()


# ── Pure scoring ─────────────────────────────────────────────────────────


@dataclass
class Round2Entry:
    """One row of the Round 2 general-competition ranking. Field names that
    the R1 payload already used (`activations`, `invited`, `award_tier`,
    `prize_idr`, `tax_bonus_idr`, `total_prize_idr`, `next_tier_threshold`,
    `to_next_tier`) keep their existing MEANING for compatibility with the
    deployed widget; new fields are additive."""

    email: str
    member: str
    display_name: str
    department: str | None
    is_tax: bool
    rank: int = 0
    activations: int = 0  # = registrations in R2 (kept name for compat)
    invited: int = 0
    last_activation_at: datetime | None = None
    award_tier: int | None = None  # always None in R2 — no thresholds
    prize_idr: int = 0  # rank prize in R2
    tax_bonus_idr: int = 0  # always 0 in R2 — no new Tax bonus
    total_prize_idr: int = 0
    next_tier_threshold: int | None = None  # always None in R2
    to_next_tier: int | None = None  # always None in R2
    points: int = 0
    carry_points: int = 0
    registrations: int = 0
    document_bonuses: int = 0
    unanswered_requests: int = 0
    unreviewed_documents: int = 0
    penalty_points: int = 0
    september_choice: str | None = None
    last_event_at: datetime | None = None


@dataclass
class AsyaMission:
    member: str = "asya"
    display_name: str = "Asya"
    avatar_url: str | None = None
    target_points: int = ASYA_TARGET_POINTS
    prize_idr: int = ASYA_PRIZE_IDR
    bonus_points: int = ASYA_BONUS_POINTS
    mission_bonuses: int = 0
    unanswered_requests: int = 0
    unreviewed_documents: int = 0
    penalty_points: int = 0
    points: int = 0
    reached: bool = False
    is_me: bool = False


@dataclass
class ScoringEvent:
    """One line of the `recent_events` live feed — display-safe by
    construction: no client identifier field exists on this shape."""

    kind: (
        str  # registration | first_document | unanswered_request | unreviewed_document | asya_bonus
    )
    display_name: str
    points: int
    at: datetime


@dataclass
class Round2Snapshot:
    entries: list[Round2Entry]
    team_total_points: int
    asya_mission: AsyaMission
    recent_events: list[ScoringEvent] = field(default_factory=list)


_NEVER = datetime.max.replace(tzinfo=timezone.utc)


def _bump(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if candidate is None:
        return current
    if current is None or candidate > current:
        return candidate
    return current


def _responsible(practice_assignee: str | None, client_assignee: str | None) -> str | None:
    """Practice assignee first, client assignee fallback, else unattributed
    (counted upstream by the caller, credited to nobody)."""
    if practice_assignee and practice_assignee.strip().lower().endswith("@balizero.com"):
        return practice_assignee.strip().lower()
    if client_assignee and client_assignee.strip().lower().endswith("@balizero.com"):
        return client_assignee.strip().lower()
    return None


def _request_penalties(request_rows: list[dict], now: datetime) -> list[dict]:
    penalties = []
    for row in request_rows:
        created_at = row["created_at"]
        reply_at = row.get("reply_at") or now
        if working_hours_between(created_at, reply_at) > RESPONSE_WORKING_HOURS_LIMIT:
            penalties.append(
                {
                    "client_id": row["client_id"],
                    "created_at": created_at,
                    "responsible": _responsible(
                        row.get("practice_assignee"), row.get("client_assignee")
                    ),
                }
            )
    return penalties


def _review_penalties(review_rows: list[dict], now: datetime) -> list[dict]:
    penalties = []
    for row in review_rows:
        uploaded_at = row["uploaded_at"]
        review_at = row.get("review_at") or now
        if working_hours_between(uploaded_at, review_at) > REVIEW_WORKING_HOURS_LIMIT:
            penalties.append(
                {
                    "client_id": row["client_id"],
                    "uploaded_at": uploaded_at,
                    "responsible": _responsible(
                        row.get("practice_assignee"), row.get("client_assignee")
                    ),
                }
            )
    return penalties


def _drop_same_incident_document_penalties(
    request_penalties: list[dict], review_penalties: list[dict]
) -> list[dict]:
    """Same incident, largest penalty only: drop a document penalty whose
    client also has a request penalty created inside
    [doc.uploaded_at, doc.uploaded_at + 1 working day]."""
    kept = []
    for rp in review_penalties:
        deadline = working_deadline(rp["uploaded_at"], WORKDAY_HOURS)
        same_incident = any(
            qp["client_id"] == rp["client_id"] and rp["uploaded_at"] <= qp["created_at"] <= deadline
            for qp in request_penalties
        )
        if not same_incident:
            kept.append(rp)
    return kept


def _mission_bonus_keys(
    asya_request_rows: list[dict], asya_client_event_rows: list[dict]
) -> set[tuple[int, int]]:
    """(client_id, practice_id-or-0) keys that qualify for Asya's +3 —
    a client event with an Asya message STRICTLY before it (same-timestamp
    does not qualify — she has to have reached out first), no more than
    ASYA_REQUEST_LOOKBACK_DAYS earlier. At most one bonus per key."""
    messages_by_client: dict[int, list[datetime]] = {}
    for row in asya_request_rows:
        messages_by_client.setdefault(row["client_id"], []).append(row["created_at"])

    lookback = timedelta(days=ASYA_REQUEST_LOOKBACK_DAYS)
    keys: set[tuple[int, int]] = set()
    for row in asya_client_event_rows:
        client_id = row["client_id"]
        event_at = row["created_at"]
        for sent_at in messages_by_client.get(client_id, ()):
            if sent_at < event_at and (event_at - sent_at) <= lookback:
                keys.add((client_id, row.get("practice_id") or 0))
                break
    return keys


def score_round2(
    roster_rows: list[dict],
    r1_awarded: list[AwardedEntry],
    registration_rows: list[dict],
    first_document_rows: list[dict],
    request_rows: list[dict],
    review_rows: list[dict],
    asya_request_rows: list[dict],
    asya_client_event_rows: list[dict],
    now: datetime,
) -> Round2Snapshot:
    """Build the full Round 2 snapshot: general-competition entries (ranked,
    prized) plus Asya's personal mission. Deterministic, fully
    unit-testable without a DB — every argument is already-fetched rows.
    """
    r1_activations_by_email = {e.email: e.activations for e in r1_awarded}

    roster: dict[str, Round2Entry] = {}
    for row in roster_rows:
        email = row["email"].strip().lower()
        if not _is_real_staff_row(email, row.get("role")):
            continue
        if email == ASYA_EMAIL:
            continue  # excluded from the general ranking — appears only in asya_mission
        if email not in ROUND2_PARTICIPANTS:
            continue  # not one of the six September players — never ranked or prized
        department = row.get("department")
        is_tax = bool(department and department.strip().lower() == "tax")
        is_winner = email in SEPTEMBER_PRIZE_TAKEN
        carry = 0 if is_winner else r1_activations_by_email.get(email, 0)
        roster[email] = Round2Entry(
            email=email,
            member=member_key_from_email(email),
            display_name=row.get("display_name") or member_key_from_email(email),
            department=department,
            is_tax=is_tax,
            carry_points=carry,
            points=carry,
            september_choice="prize" if is_winner else "carry",
        )

    events: list[ScoringEvent] = []

    # ── registrations ──
    for row in registration_rows:
        email = row["creator_email"].strip().lower()
        entry = roster.get(email)
        if entry is None:
            continue
        entry.registrations = int(row.get("activations") or 0)
        entry.activations = entry.registrations
        entry.invited = int(row.get("invited") or 0)
        entry.last_activation_at = row.get("last_activation_at")
        entry.points += entry.registrations * REGISTRATION_POINTS
        entry.last_event_at = _bump(entry.last_event_at, entry.last_activation_at)

    # ── first-document bonuses (+3) ──
    for row in first_document_rows:
        responsible = _responsible(row.get("practice_assignee"), row.get("client_assignee"))
        entry = roster.get(responsible) if responsible else None
        if entry is None:
            continue  # unattributed (or Asya, who is absent from `roster`) — counted, not credited
        entry.document_bonuses += 1
        entry.points += FIRST_DOCUMENT_POINTS
        entry.last_event_at = _bump(entry.last_event_at, row["first_doc_at"])
        events.append(
            ScoringEvent(
                kind="first_document",
                display_name=entry.display_name,
                points=FIRST_DOCUMENT_POINTS,
                at=row["first_doc_at"],
            )
        )

    # ── penalties, with same-incident dedupe ──
    request_penalties = _request_penalties(request_rows, now)
    review_penalties = _drop_same_incident_document_penalties(
        request_penalties, _review_penalties(review_rows, now)
    )

    asya_mission = AsyaMission()

    for rp in request_penalties:
        responsible = rp["responsible"]
        at = rp["created_at"]
        if responsible == ASYA_EMAIL:
            asya_mission.unanswered_requests += 1
            asya_mission.penalty_points += UNANSWERED_REQUEST_PENALTY
        else:
            entry = roster.get(responsible) if responsible else None
            if entry is None:
                continue  # unattributed — counted, not credited
            entry.unanswered_requests += 1
            entry.penalty_points += UNANSWERED_REQUEST_PENALTY
            entry.points -= UNANSWERED_REQUEST_PENALTY
            entry.last_event_at = _bump(entry.last_event_at, at)
            events.append(
                ScoringEvent(
                    kind="unanswered_request",
                    display_name=entry.display_name,
                    points=-UNANSWERED_REQUEST_PENALTY,
                    at=at,
                )
            )

    for rp in review_penalties:
        responsible = rp["responsible"]
        at = rp["uploaded_at"]
        if responsible == ASYA_EMAIL:
            asya_mission.unreviewed_documents += 1
            asya_mission.penalty_points += UNREVIEWED_DOCUMENT_PENALTY
        else:
            entry = roster.get(responsible) if responsible else None
            if entry is None:
                continue  # unattributed — counted, not credited
            entry.unreviewed_documents += 1
            entry.penalty_points += UNREVIEWED_DOCUMENT_PENALTY
            entry.points -= UNREVIEWED_DOCUMENT_PENALTY
            entry.last_event_at = _bump(entry.last_event_at, at)
            events.append(
                ScoringEvent(
                    kind="unreviewed_document",
                    display_name=entry.display_name,
                    points=-UNREVIEWED_DOCUMENT_PENALTY,
                    at=at,
                )
            )

    # ── Asya's mission bonuses ──
    # Qualifying events are EITHER kind (spec §3): a client request message
    # (already fetched as `request_rows` — the same rows scored for the
    # general -2 penalty) OR a client document upload (`asya_client_event_rows`).
    # Combine both pools so a message-only client can earn the +3 too, not
    # just an upload — this was previously silently dropped since only the
    # document-upload rows ever reached `_mission_bonus_keys`.
    qualifying_client_events = list(request_rows) + list(asya_client_event_rows)
    bonus_keys = _mission_bonus_keys(asya_request_rows, qualifying_client_events)
    asya_mission.mission_bonuses = len(bonus_keys)
    asya_mission.points = (
        asya_mission.mission_bonuses * ASYA_BONUS_POINTS - asya_mission.penalty_points
    )
    asya_mission.reached = asya_mission.points >= ASYA_TARGET_POINTS
    if bonus_keys:
        latest_event_at = max(
            row["created_at"]
            for row in qualifying_client_events
            if (row["client_id"], row.get("practice_id") or 0) in bonus_keys
        )
        events.append(
            ScoringEvent(
                kind="asya_bonus",
                display_name=asya_mission.display_name,
                points=ASYA_BONUS_POINTS,
                at=latest_event_at,
            )
        )

    # ── rank + rank prizes (dense rank over distinct points, R1-style) ──
    ordered = sorted(
        roster.values(),
        key=lambda m: (-m.points, m.last_event_at or _NEVER, m.display_name.lower()),
    )
    distinct_points_desc = sorted({m.points for m in ordered}, reverse=True)
    rank_of = {value: idx + 1 for idx, value in enumerate(distinct_points_desc)}
    for entry in ordered:
        entry.rank = rank_of[entry.points]
        # A rank prize requires points > 0 — a zero-or-negative member never
        # earns one even when they land on a prize-bearing rank (e.g. every
        # untouched member ties for the lowest rank at 0 points; nobody at
        # that rank has "won" anything). Rank itself stays dense as-is.
        entry.prize_idr = RANK_PRIZES_IDR.get(entry.rank, 0) if entry.points > 0 else 0
        entry.total_prize_idr = entry.prize_idr

    team_total_points = sum(e.points for e in ordered)
    events.sort(key=lambda e: e.at, reverse=True)

    return Round2Snapshot(
        entries=ordered,
        team_total_points=team_total_points,
        asya_mission=asya_mission,
        recent_events=events[:10],
    )
