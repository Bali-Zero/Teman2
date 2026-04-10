"""
Backfill leave requests for Jan-Apr 2026 from attendance spreadsheet.
Each date becomes an individual 1-day leave request (status=approved).
Also updates hr_leave_balances.used_days accordingly.

Usage:
    cd apps/backend-rag && source venv/bin/activate
    PYTHONPATH=. python scripts/backfill_leave_2026.py [--dry-run]
"""

import asyncio
import asyncpg
import sys
from datetime import date

# ── Attendance data from spreadsheet (Marzo 2026) ─────────────────────
# Format: (employee_email_fragment, sick_dates, leave_dates)
# sick → leave_type_id=2, leave/cuti → leave_type_id=1 (annual)

ATTENDANCE_DATA = [
    # Faysha Tax: 0 sick, 8 cuti/izin
    ("faysha.tax@balizero.com", [], [
        date(2026, 2, 18), date(2026, 3, 16), date(2026, 3, 17),
        date(2026, 3, 25), date(2026, 3, 26), date(2026, 3, 27),
        date(2026, 3, 30), date(2026, 3, 31),
    ]),
    # Kadek Tax: 0 sick, 7 cuti
    ("kadek.tax@balizero.com", [], [
        date(2026, 3, 16), date(2026, 3, 17),
        date(2026, 3, 25), date(2026, 3, 26), date(2026, 3, 27),
        date(2026, 3, 30), date(2026, 3, 31),
    ]),
    # Dewaayu Tax: 0 sick, 7 cuti
    ("dewaayu.tax@balizero.com", [], [
        date(2026, 3, 16), date(2026, 3, 17),
        date(2026, 3, 25), date(2026, 3, 26), date(2026, 3, 27),
        date(2026, 3, 30), date(2026, 3, 31),
    ]),
    # Angel Tax: 0 sick, 7 cuti
    ("angel.tax@balizero.com", [], [
        date(2026, 3, 16), date(2026, 3, 17),
        date(2026, 3, 25), date(2026, 3, 26), date(2026, 3, 27),
        date(2026, 3, 30), date(2026, 3, 31),
    ]),
    # Dea: 0 sick, 6 cuti
    ("dea@balizero.com", [], [
        date(2026, 3, 17),
        date(2026, 3, 25), date(2026, 3, 26), date(2026, 3, 27),
        date(2026, 3, 30), date(2026, 3, 31),
    ]),
    # Rina: 3 sick (Jan 19, 20, Apr 1), 2 cuti (Mar 17, 25)
    ("rina@balizero.com", [
        date(2026, 1, 19), date(2026, 1, 20), date(2026, 4, 1),
    ], [
        date(2026, 3, 17), date(2026, 3, 25),
    ]),
    # Damar: 0 sick, 1 cuti (Feb 13)
    ("damar@balizero.com", [], [
        date(2026, 2, 13),
    ]),
    # Surya: 1 sick (Feb 24), 2 cuti (Mar 16, 17)
    ("surya@balizero.com", [
        date(2026, 2, 24),
    ], [
        date(2026, 3, 16), date(2026, 3, 17),
    ]),
    # Krisna: 0 sick, 0 cuti — skip
    # Sahira: 0 sick, 2 cuti (Mar 16, 17)
    ("sahira@balizero.com", [], [
        date(2026, 3, 16), date(2026, 3, 17),
    ]),
    # Adit: 2 sick (Mar 12, 27), 4 cuti (Feb 2, 3, Mar 16, 17)
    ("adit@balizero.com", [
        date(2026, 3, 12), date(2026, 3, 27),
    ], [
        date(2026, 2, 2), date(2026, 2, 3),
        date(2026, 3, 16), date(2026, 3, 17),
    ]),
    # Vino: 0 sick, 2 cuti (Mar 16, 17)
    ("vino@balizero.com", [], [
        date(2026, 3, 16), date(2026, 3, 17),
    ]),
    # Asya: 0 sick, 0 cuti — skip
    # Ari Firda: 1 sick (Mar 30), 2 cuti (Mar 16, 17)
    ("ari.firda@balizero.com", [
        date(2026, 3, 30),
    ], [
        date(2026, 3, 16), date(2026, 3, 17),
    ]),
]

LEAVE_TYPE_ANNUAL = 1
LEAVE_TYPE_SICK = 2

# Zero's team_member ID — used as reviewed_by for backfilled approvals
REVIEWER_ID = "7dfe56b2-ff63-4d40-b78b-90c018127a02"

DB_URL = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"


async def get_employee_id(conn: asyncpg.Connection, email: str) -> int | None:
    """Resolve email → hr_employees.id via team_members join."""
    row = await conn.fetchrow("""
        SELECT he.id
        FROM hr_employees he
        JOIN team_members tm ON tm.id::text = he.team_member_id
        WHERE tm.email = $1
    """, email)
    return row["id"] if row else None


async def main():
    dry_run = "--dry-run" in sys.argv

    conn = await asyncpg.connect(DB_URL)
    print(f"{'DRY RUN — ' if dry_run else ''}Backfilling leave requests for 2026\n")

    total_inserted = 0
    total_skipped = 0
    errors = []

    for email, sick_dates, leave_dates in ATTENDANCE_DATA:
        emp_id = await get_employee_id(conn, email)
        if emp_id is None:
            errors.append(f"Employee not found: {email}")
            continue

        print(f"  {email} (hr_id={emp_id}):")

        for d in sick_dates:
            # Check if request already exists for this date
            existing = await conn.fetchval("""
                SELECT id FROM hr_leave_requests
                WHERE employee_id = $1 AND start_date = $2 AND leave_type_id = $3
            """, emp_id, d, LEAVE_TYPE_SICK)
            if existing:
                print(f"    SKIP sick {d} (already exists id={existing})")
                total_skipped += 1
                continue

            if not dry_run:
                await conn.execute("""
                    INSERT INTO hr_leave_requests
                        (employee_id, leave_type_id, start_date, end_date, total_days,
                         reason, status, requested_at, reviewed_by, reviewed_at)
                    VALUES ($1, $2, $3, $3, 1,
                            'Sick leave (backfill from attendance)', 'approved',
                            NOW(), $4, NOW())
                """, emp_id, LEAVE_TYPE_SICK, d, REVIEWER_ID)
            print(f"    + sick {d}")
            total_inserted += 1

        for d in leave_dates:
            existing = await conn.fetchval("""
                SELECT id FROM hr_leave_requests
                WHERE employee_id = $1 AND start_date = $2 AND leave_type_id = $3
            """, emp_id, d, LEAVE_TYPE_ANNUAL)
            if existing:
                print(f"    SKIP annual {d} (already exists id={existing})")
                total_skipped += 1
                continue

            if not dry_run:
                await conn.execute("""
                    INSERT INTO hr_leave_requests
                        (employee_id, leave_type_id, start_date, end_date, total_days,
                         reason, status, requested_at, reviewed_by, reviewed_at)
                    VALUES ($1, $2, $3, $3, 1,
                            'Annual leave (backfill from attendance)', 'approved',
                            NOW(), $4, NOW())
                """, emp_id, LEAVE_TYPE_ANNUAL, d, REVIEWER_ID)
            print(f"    + annual {d}")
            total_inserted += 1

    # ── Update leave balances (used_days) ──────────────────────────────
    if not dry_run:
        print("\nUpdating leave balances...")
        updated = await conn.execute("""
            UPDATE hr_leave_balances lb
            SET used_days = sub.total_used,
                updated_at = NOW()
            FROM (
                SELECT lr.employee_id, lr.leave_type_id,
                       COUNT(*) AS total_used
                FROM hr_leave_requests lr
                WHERE lr.status = 'approved'
                  AND EXTRACT(YEAR FROM lr.start_date) = 2026
                GROUP BY lr.employee_id, lr.leave_type_id
            ) sub
            WHERE lb.employee_id = sub.employee_id
              AND lb.leave_type_id = sub.leave_type_id
              AND lb.balance_year = 2026
        """)
        print(f"  Balance update: {updated}")

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'DRY RUN ' if dry_run else ''}SUMMARY:")
    print(f"  Inserted: {total_inserted}")
    print(f"  Skipped (duplicates): {total_skipped}")
    if errors:
        print(f"  ERRORS:")
        for e in errors:
            print(f"    ⚠ {e}")

    # ── Verify final state ─────────────────────────────────────────────
    if not dry_run:
        print("\nFinal leave balances 2026:")
        balances = await conn.fetch("""
            SELECT tm.full_name, lt.code,
                   lb.allocated_days, lb.used_days, lb.pending_days,
                   (lb.allocated_days - lb.used_days - lb.pending_days) AS remaining
            FROM hr_leave_balances lb
            JOIN hr_employees he ON lb.employee_id = he.id
            JOIN team_members tm ON tm.id::text = he.team_member_id
            JOIN hr_leave_types lt ON lb.leave_type_id = lt.id
            WHERE lb.balance_year = 2026
            ORDER BY tm.full_name, lt.code
        """)
        for b in balances:
            print(f"  {b['full_name']}: {b['code']} "
                  f"alloc={b['allocated_days']} used={b['used_days']} "
                  f"pend={b['pending_days']} rem={b['remaining']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
