import asyncio
import os

import asyncpg


async def test_kadek():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # 1. Get Kadek's info
    user = await conn.fetchrow("""
        SELECT tm.email, tm.full_name, tm.department, d.can_see_all
        FROM team_members tm
        LEFT JOIN departments d ON tm.department = d.code
        WHERE tm.full_name ILIKE '%kadek%' OR tm.email ILIKE '%kadek%'
    """)

    if not user:
        print("Kadek not found!")
        return

    email = user["email"]
    department = user["department"]
    full_name = user["full_name"]
    can_see_all = user["can_see_all"]

    print("=== KADEK INFO ===")
    print(f"Email: {email}")
    print(f"Name: {full_name}")
    print(f"Department: {department}")
    print(f"Can See All: {can_see_all}")

    role = "board" if can_see_all else "team"
    print(f"Computed Role: {role}")

    # 2. Check what rules apply for each context
    contexts = [None, "BALI ZERO", "Tax"]

    for ctx in contexts:
        print(f"\n=== CONTEXT: {ctx or 'ROOT'} ===")

        rules = await conn.fetch(
            """
            SELECT allowed_folders, priority, description
            FROM folder_access_rules
            WHERE active = true
              AND (
                (context_folder IS NULL AND $3::text IS NULL)
                OR (context_folder = $3)
              )
              AND (
                user_email = $1
                OR department_code = $2
                OR role = $4
                OR role = '*'
              )
            ORDER BY priority DESC
        """,
            email,
            department,
            ctx,
            role,
        )

        all_folders = set()
        for rule in rules:
            print(f"  Rule (p={rule['priority']}): {rule['description']}")
            print(f"    Folders: {rule['allowed_folders']}")
            all_folders.update(rule["allowed_folders"])

        # Add personal folder
        if full_name:
            first_name = full_name.split()[0]
            all_folders.add(first_name)
            all_folders.add(full_name)

        print(f"  --> TOTAL VISIBLE: {sorted(all_folders)}")

    await conn.close()


asyncio.run(test_kadek())
