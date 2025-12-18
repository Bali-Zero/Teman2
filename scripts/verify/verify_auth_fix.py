import asyncio
import asyncpg
import bcrypt
import sys
import os

# Add backend directory to path to import app
backend_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "apps/backend-rag/backend",
)
sys.path.append(backend_dir)

from dotenv import load_dotenv

load_dotenv(os.path.join(backend_dir, ".env"))

from app.core.config import settings


async def create_test_user():
    print("Connecting to database...")
    db_url = settings.database_url
    if not db_url:
        print("DATABASE_URL not set in settings! Trying default...")
        # Try without user/pass (local socket/ident)
        db_url = "postgresql://localhost:5432/nuzantara_dev"

    print(f"Using DB URL: {db_url}")

    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Failed to connect to {db_url}: {e}")
        # Try connecting to 'postgres' to list DBs
        try:
            print("Attempting to list databases via 'postgres' DB...")
            sys_conn = await asyncpg.connect("postgresql://localhost:5432/postgres")
            dbs = await sys_conn.fetch(
                "SELECT datname FROM pg_database WHERE datistemplate = false"
            )
            print("Available Databases:", [r["datname"] for r in dbs])
            await sys_conn.close()
        except Exception as ex:
            print(f"Failed to list databases: {ex}")
        return

    email = "zero@balizero.com"
    password = "010719"  # User provided PIN
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Check if user exists
    try:
        user = await conn.fetchrow("SELECT * FROM team_members WHERE email = $1", email)
    except Exception as e:
        print(f"Error querying team_members table: {e}")
        # Check if table exists
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        print("Tables in DB:", [r["table_name"] for r in tables])
        await conn.close()
        return

    if user:
        print(f"User {email} exists. Updating password...")
        try:
            await conn.execute(
                "UPDATE team_members SET pin_hash = $1 WHERE email = $2", hashed, email
            )
            print("Password updated.")
        except Exception as e:
            print(f"Failed to update password: {e}")
            columns = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'team_members'"
            )
            print("Columns in team_members table:", [r["column_name"] for r in columns])
    else:
        print(f"User {email} does not exist. Creating...")
        try:
            # Try to insert with pin_hash
            await conn.execute(
                """
                INSERT INTO team_members (
                    email, full_name, role, active, language, pin_hash
                ) VALUES (
                    $1, 'Zero Test', 'admin', true, 'en', $2
                )
            """,
                email,
                hashed,
            )
            print("User created.")
        except Exception as e:
            print(f"Failed to create user: {e}")
            columns = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'team_members'"
            )
            print("Columns in team_members table:", [r["column_name"] for r in columns])

    await conn.close()


if __name__ == "__main__":
    asyncio.run(create_test_user())
