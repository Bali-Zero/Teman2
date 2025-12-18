import asyncio
import asyncpg
import os
import sys

# Add backend directory to path
backend_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "apps/backend-rag/backend",
)
sys.path.append(backend_dir)

from dotenv import load_dotenv

load_dotenv(os.path.join(backend_dir, ".env"))


async def apply_migrations():
    print("Applying migrations...")

    # Use nuzantara_dev directly
    db_url = "postgresql://localhost:5432/nuzantara_dev"
    print(f"Connecting to {db_url}")

    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    migrations_dir = os.path.join(backend_dir, "db/migrations")
    files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])

    for filename in files:
        if filename.startswith("008") or filename.startswith("009"):
            print(f"Skipping {filename} (known issues/deprecated)")
            continue

        print(f"Applying {filename}...")
        with open(os.path.join(migrations_dir, filename), "r") as f:
            sql = f.read()

        try:
            await conn.execute(sql)
            print(f"Applied {filename}")
        except Exception as e:
            print(f"Failed to apply {filename}: {e}")
            # Continue? Maybe not.
            # But for now, let's try to continue as some might depend on others
            # or already be applied (IF NOT EXISTS)

    await conn.close()
    print("Migrations completed.")


if __name__ == "__main__":
    asyncio.run(apply_migrations())
