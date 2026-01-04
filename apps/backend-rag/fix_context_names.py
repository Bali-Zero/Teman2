import asyncio
import os

import asyncpg


async def fix():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # Add rules with actual folder names from Google Drive
    rules = [
        # TAX DEPARTMENT context (same as Tax)
        (
            "board",
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
            "TAX DEPARTMENT",
            10,
            "Board: visible members inside TAX DEPARTMENT",
        ),
        (
            "tax",
            ["_Shared", "Shared", "Templates", "Common"],
            "TAX DEPARTMENT",
            5,
            "Tax: shared folders inside TAX DEPARTMENT",
        ),
        # SETUP DEPARTMENT context (if it's named differently)
        (
            "board",
            ["Anton", "Rina", "Dea", "_Shared", "Shared", "Templates", "Common"],
            "SETUP DEPARTMENT",
            10,
            "Board: visible members inside SETUP DEPARTMENT",
        ),
        (
            "setup",
            ["_Shared", "Shared", "Templates", "Common"],
            "SETUP DEPARTMENT",
            5,
            "Setup: shared folders inside SETUP DEPARTMENT",
        ),
        # Also add for zero@balizero.com
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
            "TAX DEPARTMENT",
            25,
            "Zero: full access inside TAX DEPARTMENT",
        ),
        (
            "zero@balizero.com",
            ["Anton", "Rina", "Dea", "_Shared", "Shared", "Templates", "Common"],
            "SETUP DEPARTMENT",
            25,
            "Zero: full access inside SETUP DEPARTMENT",
        ),
    ]

    for item in rules:
        if "@" in item[0]:
            # User email rule
            await conn.execute(
                """
                INSERT INTO folder_access_rules (user_email, allowed_folders, context_folder, priority, description)
                VALUES ($1, $2, $3, $4, $5)
            """,
                item[0],
                item[1],
                item[2],
                item[3],
                item[4],
            )
        else:
            # Role or department rule
            if item[0] in ("board", "team", "*"):
                await conn.execute(
                    """
                    INSERT INTO folder_access_rules (role, allowed_folders, context_folder, priority, description)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO folder_access_rules (department_code, allowed_folders, context_folder, priority, description)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4],
                )
        print(f"Added: {item[2]} -> {item[0]}")

    print("\nDone! Added rules for actual folder names.")
    await conn.close()


asyncio.run(fix())
