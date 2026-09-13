"""Portal Champion challenge — single source of scoring logic and SQL.

Shared by `GET /api/dashboard/portal-challenge` (live widget, staff-only) and
`scripts/portal_challenge_leaderboard.py` (read-only report). NEW rules decided
by Zero on 2026-09-14 replace the earlier invited/activated/first_action points
scheme with a pure activation count + tiered prize award.

Window: 2026-09-14 00:00 WITA (Asia/Makassar) inclusive → 2026-09-30 00:00 WITA
exclusive. Fixed for this challenge — no CLI/query override, so the live
endpoint and the offline report can never disagree about "when".

Counted unit = ACTIVATION: a `client_invitations` row with `used_at` inside
the window, credited to that row's `created_by` (a @balizero.com staff
account). Exclusions: soft-deleted clients, clients tagged test/portal-pilot,
invitee emails @balizero.com or with a `+` alias, clients who had already
activated before the window opened.

This module has NO asyncpg/FastAPI import at module level — only stdlib — so
a plain `python3` process (the script) can import it without the backend
venv. DB access stays with the caller: this module hands back SQL text +
pure Python transforms, never opens a connection itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")

WINDOW_START = datetime(2026, 9, 14, 0, 0, tzinfo=WITA)
WINDOW_END = datetime(2026, 9, 30, 0, 0, tzinfo=WITA)  # exclusive


@dataclass(frozen=True)
class Tier:
    tier: int
    threshold: int
    prize_idr: int


TIERS: tuple[Tier, ...] = (
    Tier(tier=1, threshold=20, prize_idr=3_000_000),
    Tier(tier=2, threshold=15, prize_idr=1_500_000),
    Tier(tier=3, threshold=10, prize_idr=700_000),
)

TAX_PODIUM_BONUS_IDR = 1_500_000
TAX_FALLBACK_BONUS_IDR = 1_000_000
TAX_FALLBACK_THRESHOLD = 10

_SORTED_THRESHOLDS_ASC: tuple[int, ...] = tuple(sorted(t.threshold for t in TIERS))


def compute_status(now: datetime) -> str:
    """upcoming | live | closed, per the fixed window above."""
    if now < WINDOW_START:
        return "upcoming"
    if now < WINDOW_END:
        return "live"
    return "closed"


# ── SQL ──────────────────────────────────────────────────────────────────
# All timestamps are baked into the SQL text as literals (fixed constants we
# generate, never request input) rather than bind params — this mirrors the
# style already in `scripts/portal_challenge_leaderboard.py` and lets the
# script run the identical text through `pg.sh` (no asyncpg placeholders).

_SHARED_CTES = """
WITH real_clients AS (
    SELECT c.id
    FROM clients c
    WHERE c.deleted_at IS NULL
      AND NOT (COALESCE(c.tags, ARRAY[]::text[]) && ARRAY['test', 'portal-pilot']::text[])
),
eligible_invites AS (
    SELECT ci.client_id, ci.created_by, ci.created_at, ci.used_at
    FROM client_invitations ci
    JOIN real_clients c ON c.id = ci.client_id
    WHERE lower(ci.email) NOT LIKE '%@balizero.com'
      AND ci.email NOT LIKE '%+%@%'
      AND lower(ci.created_by) LIKE '%@balizero.com'
),
already_active_before_window AS (
    -- A client who activated BEFORE the window earns nothing when re-invited
    -- or re-activated inside it.
    SELECT DISTINCT client_id
    FROM client_invitations
    WHERE used_at IS NOT NULL
      AND used_at < TIMESTAMP WITH TIME ZONE '{start_ts}'
),
window_invites AS (
    -- Secondary "invited" info: one row per client, the FIRST invitation
    -- inside the window, credited to its sender. A resend is a later row for
    -- the same client, so it can never add a second point.
    SELECT DISTINCT ON (client_id) client_id, created_by, created_at
    FROM eligible_invites
    WHERE created_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
      AND created_at <  TIMESTAMP WITH TIME ZONE '{end_ts}'
      AND client_id NOT IN (SELECT client_id FROM already_active_before_window)
    ORDER BY client_id, created_at
),
window_activations AS (
    SELECT client_id, created_by, used_at
    FROM eligible_invites
    WHERE used_at IS NOT NULL
      AND used_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
      AND used_at <  TIMESTAMP WITH TIME ZONE '{end_ts}'
      AND client_id NOT IN (SELECT client_id FROM already_active_before_window)
)
""".strip()

_AGGREGATES_SELECT = """
, activation_agg AS (
    SELECT lower(created_by) AS creator_email,
           COUNT(DISTINCT client_id) AS activations,
           MAX(used_at) AS last_activation_at
    FROM window_activations
    GROUP BY 1
),
invited_agg AS (
    SELECT lower(created_by) AS creator_email,
           COUNT(DISTINCT client_id) AS invited
    FROM window_invites
    GROUP BY 1
)
SELECT
    COALESCE(a.creator_email, i.creator_email) AS creator_email,
    COALESCE(a.activations, 0) AS activations,
    COALESCE(i.invited, 0) AS invited,
    a.last_activation_at
FROM activation_agg a
FULL OUTER JOIN invited_agg i ON a.creator_email = i.creator_email;
""".strip()

_RECENT_ACTIVATIONS_SELECT = """
SELECT lower(created_by) AS creator_email, used_at
FROM window_activations
ORDER BY used_at DESC
LIMIT 10;
""".strip()

ROSTER_SQL = """
SELECT lower(email) AS email, name AS display_name, department, role, active
FROM team_members
WHERE active = TRUE
  AND lower(email) LIKE '%@balizero.com'
ORDER BY 1;
""".strip()
# Role filtering happens in `merge_roster_and_activity` via
# `service_accounts.is_human_team_member` (the tested allow-list), not here —
# a bespoke `role <> 'client'` predicate would miss SERVICE_ROLES (e.g. the
# `monitoring` healthcheck probe, live in this table with active=TRUE) and
# would drift from the allow-list the moment a new job title is added there.


def _window_ts() -> tuple[str, str]:
    return WINDOW_START.isoformat(), WINDOW_END.isoformat()


def build_aggregates_sql() -> str:
    """Per-creator activations/invited/last_activation_at, one row per creator."""
    start_ts, end_ts = _window_ts()
    return (_SHARED_CTES + _AGGREGATES_SELECT).format(start_ts=start_ts, end_ts=end_ts)


def build_recent_activations_sql() -> str:
    """Last 10 activation events in the window, most recent first. No client data."""
    start_ts, end_ts = _window_ts()
    return (_SHARED_CTES + "\n" + _RECENT_ACTIVATIONS_SELECT).format(start_ts=start_ts, end_ts=end_ts)


# ── Pure scoring ─────────────────────────────────────────────────────────


@dataclass
class MemberActivations:
    """One row of merged roster + activation data, before award assignment."""

    email: str  # lowercased, full @balizero.com address
    member: str  # local part, lowercase — display key
    display_name: str
    department: str | None
    is_tax: bool
    activations: int = 0
    invited: int = 0
    last_activation_at: datetime | None = None


@dataclass
class AwardedEntry:
    """MemberActivations plus rank + award fields — the shape the endpoint serializes."""

    email: str
    member: str
    display_name: str
    department: str | None
    is_tax: bool
    rank: int
    activations: int
    invited: int
    last_activation_at: datetime | None
    award_tier: int | None
    prize_idr: int
    tax_bonus_idr: int
    total_prize_idr: int
    next_tier_threshold: int | None
    to_next_tier: int | None


def member_key_from_email(email: str) -> str:
    """Local part, lowercase — the `member` field and the roster-merge join key."""
    return email.strip().lower().split("@", 1)[0]


# Fixture/QA accounts that pass `is_human_team_member` on role alone but are
# not real staff — same email-pattern exclusion `admin_team_activity.py` uses
# for people-shaped stats (team_stats), applied here for the same reason: a
# leaderboard widget is exactly that kind of artifact.
_NON_STAFF_EMAIL_PATTERNS = ("test", "demo", "example")


def _is_real_staff_row(email: str, role: str | None) -> bool:
    from backend.app.utils.service_accounts import is_human_team_member

    if not is_human_team_member(role):
        return False
    return not any(pattern in email for pattern in _NON_STAFF_EMAIL_PATTERNS)


def merge_roster_and_activity(
    roster_rows: list[dict],
    activity_rows: list[dict],
) -> list[MemberActivations]:
    """Build the full MemberActivations list: every real active staff member
    (even at 0 activations) plus any credited creator absent from the roster.

    `roster_rows` keys: email, display_name, department, role, active.
    `activity_rows` keys: creator_email, activations, invited, last_activation_at.
    """
    roster: dict[str, MemberActivations] = {}
    for row in roster_rows:
        email = row["email"].strip().lower()
        if not _is_real_staff_row(email, row.get("role")):
            continue
        department = row.get("department")
        is_tax = bool(department and department.strip().lower() == "tax")
        roster[email] = MemberActivations(
            email=email,
            member=member_key_from_email(email),
            display_name=row.get("display_name") or member_key_from_email(email),
            department=department,
            is_tax=is_tax,
        )

    activity: dict[str, dict] = {row["creator_email"].strip().lower(): row for row in activity_rows}

    for email, row in activity.items():
        if email in roster:
            m = roster[email]
            m.activations = int(row.get("activations") or 0)
            m.invited = int(row.get("invited") or 0)
            m.last_activation_at = row.get("last_activation_at")
        else:
            # A credited creator who isn't (or is no longer) a roster member —
            # still earned their activations, so still shows up.
            roster[email] = MemberActivations(
                email=email,
                member=member_key_from_email(email),
                display_name=member_key_from_email(email),
                department=None,
                is_tax=False,
                activations=int(row.get("activations") or 0),
                invited=int(row.get("invited") or 0),
                last_activation_at=row.get("last_activation_at"),
            )

    return list(roster.values())


def _next_tier_threshold(activations: int) -> int | None:
    for threshold in _SORTED_THRESHOLDS_ASC:
        if threshold > activations:
            return threshold
    return None


def compute_awards(members: list[MemberActivations]) -> list[AwardedEntry]:
    """Rank, greedily award podium tiers, then apply the tax bonus rule.

    Ranking: activations desc; tie-break earlier last_activation_at asc
    (members who never activated sort last within a tie); then display_name.
    `rank` is dense over activations value alone, so every zero-activation
    member shares the same (lowest) rank rather than each taking a distinct
    number.

    Award: walking the ranking top to bottom, each member gets the
    highest-prize tier whose threshold they meet that is not yet taken; a
    tier is awarded at most once, a member gets at most one tier. Members
    below every threshold (incl. all zeros) get nothing — enforced simply by
    the threshold check, no special-case needed.

    Tax bonus: every tax member (`is_tax`) holding a podium tier gets
    `TAX_PODIUM_BONUS_IDR` on top. If NO tax member holds a tier, the
    best-ranked tax member with >= TAX_FALLBACK_THRESHOLD activations gets
    `TAX_FALLBACK_BONUS_IDR` instead (at most one fallback winner).
    """
    def sort_key(m: MemberActivations) -> tuple[int, datetime, str]:
        never = datetime.max.replace(tzinfo=timezone.utc)
        last = m.last_activation_at or never
        return (-m.activations, last, m.display_name.lower())

    ordered = sorted(members, key=sort_key)

    distinct_activation_values = sorted({m.activations for m in ordered}, reverse=True)
    rank_of = {value: idx + 1 for idx, value in enumerate(distinct_activation_values)}

    tiers_by_prize_desc = sorted(TIERS, key=lambda t: t.prize_idr, reverse=True)
    taken_tiers: set[int] = set()

    awarded: list[AwardedEntry] = []
    for m in ordered:
        award_tier: int | None = None
        prize_idr = 0
        for tier in tiers_by_prize_desc:
            if tier.tier in taken_tiers:
                continue
            if m.activations >= tier.threshold:
                award_tier = tier.tier
                prize_idr = tier.prize_idr
                taken_tiers.add(tier.tier)
                break

        next_threshold = _next_tier_threshold(m.activations)
        awarded.append(
            AwardedEntry(
                email=m.email,
                member=m.member,
                display_name=m.display_name,
                department=m.department,
                is_tax=m.is_tax,
                rank=rank_of[m.activations],
                activations=m.activations,
                invited=m.invited,
                last_activation_at=m.last_activation_at,
                award_tier=award_tier,
                prize_idr=prize_idr,
                tax_bonus_idr=0,
                total_prize_idr=prize_idr,
                next_tier_threshold=next_threshold,
                to_next_tier=(next_threshold - m.activations) if next_threshold is not None else None,
            )
        )

    podium_tax_entries = [e for e in awarded if e.is_tax and e.award_tier is not None]
    if podium_tax_entries:
        for entry in podium_tax_entries:
            entry.tax_bonus_idr = TAX_PODIUM_BONUS_IDR
            entry.total_prize_idr = entry.prize_idr + entry.tax_bonus_idr
    else:
        fallback = next(
            (e for e in awarded if e.is_tax and e.activations >= TAX_FALLBACK_THRESHOLD),
            None,
        )
        if fallback is not None:
            fallback.tax_bonus_idr = TAX_FALLBACK_BONUS_IDR
            fallback.total_prize_idr = fallback.prize_idr + fallback.tax_bonus_idr

    return awarded
