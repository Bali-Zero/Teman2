import asyncio
import os
from datetime import timedelta

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://nuzantara@localhost:5432/nuzantara_dev")


async def backfill():
    print(f"Connecting to {DATABASE_URL}...")
    conn = await asyncpg.connect(DATABASE_URL)

    # Get all practices
    practices = await conn.fetch(
        "SELECT id, practice_type_code, status, created_at, completion_date FROM practices"
    )
    print(f"Found {len(practices)} practices.")

    updates = 0
    for p in practices:
        p_id = p["id"]
        p_type = p["practice_type_code"]
        status = p["status"]
        created_at = p["created_at"]
        comp_date = p["completion_date"]

        expected_completion_date = None
        expiry_date = None
        next_renewal_date = None

        # 1. Expected completion date
        if created_at:
            if p_type == "kitas":
                expected_completion_date = (created_at + timedelta(days=30)).date()
            elif p_type == "new_pt":
                expected_completion_date = (created_at + timedelta(days=45)).date()
            elif p_type == "tax":
                expected_completion_date = (created_at + timedelta(days=15)).date()
            else:
                expected_completion_date = (created_at + timedelta(days=30)).date()

        # 2. Expiry date and next renewal
        # We assume if it's completed, it has an expiry
        # If comp_date is none, maybe fallback to created_at + expected + 1 year, but better to just use today for testing if completed
        base_date = comp_date or created_at
        if base_date and status == "completed":
            if p_type == "kitas" or p_type == "new_pt":
                expiry_date = (base_date + timedelta(days=365)).date()
            elif p_type == "tax":
                expiry_date = (base_date + timedelta(days=30)).date()  # Monthly tax
            else:
                expiry_date = (base_date + timedelta(days=365)).date()

            if expiry_date:
                # 30 days before expiry for renewal warning
                next_renewal_date = expiry_date - timedelta(days=30)

        # Apply updates
        await conn.execute(
            """
            UPDATE practices
            SET expected_completion_date = COALESCE(expected_completion_date, $1),
                expiry_date = COALESCE(expiry_date, $2),
                next_renewal_date = COALESCE(next_renewal_date, $3)
            WHERE id = $4
        """,
            expected_completion_date,
            expiry_date,
            next_renewal_date,
            p_id,
        )

        updates += 1

    print(f"Successfully processed {updates} practices.")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(backfill())
