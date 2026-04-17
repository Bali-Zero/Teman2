"""Migration 080: HR team roster cleanup + tax team leave balances 2026.

Why:
- Migration 076b seeded hr_employees + 2026 leave balances using a hardcoded
  list of 12 emails. The list missed the entire tax team (Angel, Kadek, Dewa
  Ayu, Faisha) and Reception (Rina), and used wrong emails for Veronika
  ("veronika@" instead of "tax@"), Vino ("vino@" instead of "info@"), and
  Adit ("adit@" instead of "consulting@"). Result: several team members had
  hr_employees records but zero allocated leave days for 2026, while others
  had no hr_employees record at all.
- Two members are no longer with the company: Amanda (terminated) and Nina
  (offboarded). They have zero rows in any dependent CRM/practice/email
  table (verified before migration), so DELETE is safe.
- Zainal (CEO) is intentionally left out of the HR seed.

What this migration does:
1. DELETE Amanda + Nina from team_members (no FK cascades trigger any data
   loss — verified empty in clients, practices, interactions, companies,
   email_activity_log, zoho_email_*).
2. INSERT hr_employees row for Rina (the only team member missing one).
   The five tax team members already have hr_employees from earlier seeds.
3. UPSERT hr_leave_balances for 2026 with the correct allocation:
   - Veronika: 18 days (manager exception)
   - Everyone else (Angel, Kadek, Dewa Ayu, Faisha, Rina): 12 days
   This UPSERT is idempotent and re-runnable.

Rollback (down):
- Removes the 6 leave balance rows created here.
- Removes Rina's hr_employees row.
- Does NOT recreate Amanda/Nina (the DELETE is intentionally not reversible
  via this migration — restore from backup if ever needed).
"""

from __future__ import annotations

import logging

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = "080"
DESCRIPTION = (
    "HR team roster cleanup: remove Amanda+Nina, seed Rina hr_employees, "
    "fix 2026 leave balances for tax team + Rina (Veronika 18d, others 12d)."
)

# ─── Targets ────────────────────────────────────────────────────────────
# (email, full_name, allocated_days)
# Veronika gets the manager exception of 18 days.
TAX_TEAM_FIX: list[tuple[str, str, int]] = [
    ("tax@balizero.com",          "Veronika", 18),
    ("angel.tax@balizero.com",    "Angel",    12),
    ("kadek.tax@balizero.com",    "Kadek",    12),
    ("dewaayu.tax@balizero.com",  "Dewa Ayu", 12),
    ("faysha.tax@balizero.com",   "Faisha",   12),
]

RECEPTION_FIX: list[tuple[str, str, int]] = [
    ("rina@balizero.com",         "Rina",     12),
]

# Offboarded — must have zero references in any dependent table.
OFFBOARDED_EMAILS: list[str] = [
    "amanda@balizero.com",   # terminated
    "nina@balizero.com",     # offboarded
]


async def up(conn: asyncpg.Connection) -> None:
    # ── 1. Defensive check: refuse to delete offboarded users if they have
    #    any data in CRM/practice/email tables. Better to fail loud than
    #    cascade-destroy work history.
    for email in OFFBOARDED_EMAILS:
        tm_id = await conn.fetchval(
            "SELECT id FROM team_members WHERE email = $1", email,
        )
        if tm_id is None:
            logger.info("Migration 080: %s already absent — skipping delete", email)
            continue

        # Count references in tables that don't have ON DELETE rules
        # that would silently drop the data we care about.
        refs = await conn.fetchrow(
            """
            SELECT
              (SELECT COUNT(*) FROM clients WHERE assigned_to = $1::text OR created_by = $1::text) AS clients,
              (SELECT COUNT(*) FROM practices WHERE assigned_to = $1::text OR created_by = $1::text) AS practices,
              (SELECT COUNT(*) FROM interactions WHERE created_by = $1::text) AS interactions,
              (SELECT COUNT(*) FROM companies WHERE created_by = $1::text) AS companies,
              (SELECT COUNT(*) FROM hr_employees WHERE team_member_id = $1::text) AS hr_employees
            """,
            tm_id,
        )
        total = sum(refs.values()) if refs else 0
        if total > 0:
            msg = (
                f"Migration 080 ABORTED: {email} (id={tm_id}) has "
                f"{total} dependent rows: {dict(refs)}. "
                f"Refusing to delete — investigate manually."
            )
            logger.error(msg)
            raise RuntimeError(msg)

        # Safe to delete. Cascading FKs (email_activity_log, zoho_email_*)
        # are intentional cleanups; SET NULL FKs (hr_*) preserve audit trail.
        deleted = await conn.execute(
            "DELETE FROM team_members WHERE id = $1", tm_id,
        )
        logger.info("Migration 080: deleted offboarded team_member %s (%s)", email, deleted)

    # ── 2. Ensure Rina has an hr_employees record. Other targets in
    #    TAX_TEAM_FIX already have one from earlier seeds.
    for email, full_name, _ in RECEPTION_FIX:
        tm = await conn.fetchrow(
            "SELECT id FROM team_members WHERE email = $1", email,
        )
        if not tm:
            logger.warning("Migration 080: team_member not found for %s — skipping", email)
            continue
        await conn.execute(
            """
            INSERT INTO hr_employees (team_member_id, hire_date, base_salary_idr, is_active)
            VALUES ($1, CURRENT_DATE, 0, TRUE)
            ON CONFLICT (team_member_id) DO NOTHING
            """,
            tm["id"],
        )
        logger.info("Migration 080: ensured hr_employees row for %s (%s)", full_name, email)

    # ── 3. Upsert 2026 annual leave balances for tax team + Rina.
    annual_type_id: int | None = await conn.fetchval(
        "SELECT id FROM hr_leave_types WHERE code = 'annual' LIMIT 1",
    )
    if not annual_type_id:
        msg = "Migration 080 ABORTED: hr_leave_types 'annual' not found"
        logger.error(msg)
        raise RuntimeError(msg)

    targets = TAX_TEAM_FIX + RECEPTION_FIX
    for email, full_name, days in targets:
        tm = await conn.fetchrow(
            "SELECT id FROM team_members WHERE email = $1", email,
        )
        if not tm:
            logger.warning(
                "Migration 080: team_member not found for %s — skipping balance",
                email,
            )
            continue

        emp = await conn.fetchrow(
            "SELECT id FROM hr_employees WHERE team_member_id = $1",
            tm["id"],
        )
        if not emp:
            logger.warning(
                "Migration 080: hr_employees still missing for %s — skipping balance",
                email,
            )
            continue

        await conn.execute(
            """
            INSERT INTO hr_leave_balances
                (employee_id, leave_type_id, balance_year, allocated_days,
                 carried_over, used_days, pending_days)
            VALUES ($1, $2, 2026, $3, 0, 0, 0)
            ON CONFLICT (employee_id, leave_type_id, balance_year)
            DO UPDATE SET allocated_days = EXCLUDED.allocated_days
            """,
            emp["id"],
            annual_type_id,
            days,
        )
        logger.info(
            "Migration 080: %s (%s) → %d days for 2026",
            full_name, email, days,
        )

    logger.info(
        "Migration 080 applied: deleted=%d, hr_employees_added=%d, balances_set=%d",
        len(OFFBOARDED_EMAILS),
        len(RECEPTION_FIX),
        len(TAX_TEAM_FIX) + len(RECEPTION_FIX),
    )


async def down(conn: asyncpg.Connection) -> None:
    # Reversible parts only — Amanda/Nina are NOT recreated.
    annual_type_id = await conn.fetchval(
        "SELECT id FROM hr_leave_types WHERE code = 'annual' LIMIT 1",
    )

    if annual_type_id:
        for email, _, _ in TAX_TEAM_FIX + RECEPTION_FIX:
            tm = await conn.fetchrow(
                "SELECT id FROM team_members WHERE email = $1", email,
            )
            if not tm:
                continue
            emp = await conn.fetchrow(
                "SELECT id FROM hr_employees WHERE team_member_id = $1",
                tm["id"],
            )
            if not emp:
                continue
            await conn.execute(
                """
                DELETE FROM hr_leave_balances
                WHERE employee_id = $1
                  AND leave_type_id = $2
                  AND balance_year = 2026
                """,
                emp["id"],
                annual_type_id,
            )

    # Drop only the hr_employees row this migration created (Rina).
    for email, _, _ in RECEPTION_FIX:
        tm = await conn.fetchrow(
            "SELECT id FROM team_members WHERE email = $1", email,
        )
        if not tm:
            continue
        await conn.execute(
            "DELETE FROM hr_employees WHERE team_member_id = $1",
            tm["id"],
        )

    logger.info(
        "Migration 080 rolled back: balances removed, Rina hr_employees removed. "
        "Amanda/Nina were NOT recreated — restore from backup if needed."
    )
