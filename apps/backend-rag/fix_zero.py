import asyncio
import os

import asyncpg


async def fix():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # Add rules for zero@balizero.com
    rules = [
        (
            "zero@balizero.com",
            [
                "Setup",
                "Tax",
                "BOARD",
                "_Shared",
                "Shared",
                "Templates",
                "INSTRUCTIONS",
                "Common",
                "Marketing",
            ],
            "BALI ZERO",
            25,
            "Zero: full access inside BALI ZERO",
        ),
        (
            "zero@balizero.com",
            ["Anton", "Rina", "Dea", "_Shared", "Shared", "Templates", "Common"],
            "Setup",
            25,
            "Zero: full access inside Setup",
        ),
        (
            "zero@balizero.com",
            [
                "Kadek",
                "Dewa Ayu",
                "Faysha",
                "Angel",
                "Dea",
                "_Shared",
                "Shared",
                "Templates",
                "Common",
            ],
            "Tax",
            25,
            "Zero: full access inside Tax",
        ),
        (
            "zero@balizero.com",
            ["_Shared", "Shared", "Templates", "Common", "Minutes", "Reports", "Strategic"],
            "BOARD",
            25,
            "Zero: full access inside BOARD",
        ),
    ]

    for email, folders, context, priority, desc in rules:
        await conn.execute(
            """
            INSERT INTO folder_access_rules (user_email, allowed_folders, context_folder, priority, description)
            VALUES ($1, $2, $3, $4, $5)
        """,
            email,
            folders,
            context,
            priority,
            desc,
        )
        print(f"Added: {context} -> {len(folders)} folders")

    print("Done! Zero now has full access.")
    await conn.close()


asyncio.run(fix())
