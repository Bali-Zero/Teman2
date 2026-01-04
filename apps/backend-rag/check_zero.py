import asyncio
import os

import asyncpg


async def check():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    users = await conn.fetch(
        "SELECT email, department, full_name FROM team_members WHERE email LIKE '%zero%' OR email LIKE '%anton%'"
    )
    for user in users:
        print(f"Email: {user[0]}, Dept: {user[1]}, Name: {user[2]}")
        dept = await conn.fetchrow(
            "SELECT code, name, can_see_all FROM departments WHERE code = $1", user[1]
        )
        if dept:
            print(f"  -> Dept: {dept[0]}, can_see_all: {dept[2]}")
    await conn.close()


asyncio.run(check())
