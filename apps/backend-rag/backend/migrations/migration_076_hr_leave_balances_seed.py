"""Migration 076: Seed hr_employees + hr_leave_balances for 2026.

- Creates hr_employee records for team members missing one (ruslana, veronika, dea, anton, etc.)
- Seeds annual leave balances for 2026:
    - Veronika: 18 days
    - Everyone else: 12 days (default per hr_leave_types.default_days)
"""
import logging

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_ID = "076"
DESCRIPTION = (
    "Seed hr_employees records and 2026 annual leave balances. "
    "Veronika gets 18 days; all other active balizero.com team members get 12 days."
)

# Active balizero.com team members that should have HR records.
# Format: (email, full_name)  — only @balizero.com staff
BALIZERO_TEAM: list[tuple[str, str]] = [
    ("adit@balizero.com",       "Adit"),
    ("ari.firda@balizero.com",  "Ari"),
    ("surya@balizero.com",      "Surya"),
    ("krisna@balizero.com",     "Krishna"),
    ("sahira@balizero.com",     "Sahira"),
    ("vino@balizero.com",       "Vino"),
    ("damar@balizero.com",      "Damar"),
    ("asya@balizero.com",       "Asya Nadia Firdauzi"),
    ("ruslana@balizero.com",    "Ruslana"),
    ("zero@balizero.com",       "Zero"),
    ("dea@balizero.com",        "Dea"),
    ("veronika@balizero.com",   "Veronika"),
]

# Veronika gets 18 days, everyone else 12
VERONIKA_EMAIL = "veronika@balizero.com"
DEFAULT_DAYS = 12
VERONIKA_DAYS = 18


async def up(conn: asyncpg.Connection) -> None:
    # ── 1. Ensure every team member has an hr_employee record ───────────────
    for email, _full_name in BALIZERO_TEAM:
        # Find team_member id
        tm = await conn.fetchrow(
            "SELECT id FROM team_members WHERE email = $1 LIMIT 1", email
        )
        if not tm:
            logger.warning("Migration 076: team_member not found for %s — skipping", email)
            continue

        tm_id = tm["id"]

        # Upsert hr_employee (hire_date=today, salary=0 as placeholder)
        await conn.execute(
            """
            INSERT INTO hr_employees (team_member_id, hire_date, base_salary_idr, is_active)
            VALUES ($1, CURRENT_DATE, 0, TRUE)
            ON CONFLICT (team_member_id) DO NOTHING
            """,
            tm_id,
        )

    # ── 2. Seed 2026 annual leave balances ──────────────────────────────────
    annual_type_id: int = await conn.fetchval(
        "SELECT id FROM hr_leave_types WHERE code = 'annual' LIMIT 1"
    )
    if not annual_type_id:
        logger.error("Migration 076: hr_leave_types 'annual' not found — aborting balance seed")
        return

    for email, _ in BALIZERO_TEAM:
        tm = await conn.fetchrow(
            "SELECT id FROM team_members WHERE email = $1 LIMIT 1", email
        )
        if not tm:
            continue

        emp = await conn.fetchrow(
            "SELECT id FROM hr_employees WHERE team_member_id = $1 LIMIT 1", tm["id"]
        )
        if not emp:
            logger.warning("Migration 076: hr_employee still missing for %s — skipping balance", email)
            continue

        emp_id = emp["id"]
        days = VERONIKA_DAYS if email == VERONIKA_EMAIL else DEFAULT_DAYS

        await conn.execute(
            """
            INSERT INTO hr_leave_balances
                (employee_id, leave_type_id, balance_year, allocated_days,
                 carried_over, used_days, pending_days)
            VALUES ($1, $2, 2026, $3, 0, 0, 0)
            ON CONFLICT (employee_id, leave_type_id, balance_year)
            DO UPDATE SET allocated_days = EXCLUDED.allocated_days
            """,
            emp_id,
            annual_type_id,
            days,
        )
        logger.debug("Migration 076: set %d days for %s (emp_id=%d)", days, email, emp_id)

    logger.info(
        "Migration 076 applied: hr_employees + 2026 leave balances seeded (%d members)",
        len(BALIZERO_TEAM),
    )


async def down(conn: asyncpg.Connection) -> None:
    # Only remove balances we created — don't drop employee records
    annual_type_id = await conn.fetchval(
        "SELECT id FROM hr_leave_types WHERE code = 'annual' LIMIT 1"
    )
    if annual_type_id:
        await conn.execute(
            """
            DELETE FROM hr_leave_balances
            WHERE leave_type_id = $1 AND balance_year = 2026
            """,
            annual_type_id,
        )
    logger.info("Migration 076 rolled back: 2026 annual leave balances removed")
