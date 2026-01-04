#!/usr/bin/env python3
import asyncio
import os

import asyncpg


async def check():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    # Check Ruslana's info
    user = await conn.fetchrow("""
        SELECT tm.email, tm.full_name, tm.department, d.name as dept_name, d.can_see_all
        FROM team_members tm
        LEFT JOIN departments d ON tm.department = d.code
        WHERE tm.email = 'ruslana@balizero.com'
    """)

    if user:
        print(f"Email: {user['email']}")
        print(f"Name: {user['full_name']}")
        print(f"Department: {user['department']}")
        print(f"Dept Name: {user['dept_name']}")
        print(f"Can See All: {user['can_see_all']}")
    else:
        print("User not found")

    # Check all board-level users
    print("\n=== All departments ===")
    depts = await conn.fetch("SELECT code, name, can_see_all FROM departments ORDER BY code")
    for d in depts:
        print(f"  {d['code']:15} | {d['name']:20} | can_see_all={d['can_see_all']}")

    await conn.close()


asyncio.run(check())
