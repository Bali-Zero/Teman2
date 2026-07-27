import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BACKEND_DIR))
sys.path.append(str(BACKEND_DIR / "backend"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Override DB URL for local dev if needed BEFORE imports
if not os.getenv("DATABASE_URL"):
    # Default to local system DB
    os.environ["DATABASE_URL"] = "postgresql://antonellosiano@localhost:5432/nuzantara_dev"
    logger.info(f"Set DATABASE_URL to default: {os.environ['DATABASE_URL']}")

from backend.app.modules.identity.service import IdentityService

DATA_FILE = BACKEND_DIR / "backend/data/team_members.json"

# PINs come from OUTSIDE the repository. Until 2026-07-27 every entry in
# DATA_FILE carried a plaintext `pin`, and this script hashed it straight into
# `team_members.pin_hash` — the column `app/routers/auth.py` authenticates
# against. This repository is PUBLIC, so those were published live credentials,
# not fixtures. The field is gone; supply the PINs here instead.
DEFAULT_PINS_FILE = Path.home() / ".nuzantara" / "team_pins.json"
PINS_FILE = Path(os.getenv("TEAM_PINS_FILE") or DEFAULT_PINS_FILE)


def load_pins() -> dict[str, str]:
    """Return {email: pin} from PINS_FILE, or {} if the file is absent.

    Absent is not fatal: without PINs the seeder still refreshes roster
    metadata for existing members, it just refuses to touch their credential
    (and refuses to CREATE anyone, since an account with no credential is not
    an account). Never logs a PIN value.
    """
    if not PINS_FILE.exists():
        logger.warning(
            "No PIN file at %s — roster metadata only, credentials untouched. "
            "Set TEAM_PINS_FILE to a JSON object {\"email\": \"pin\"} outside "
            "the repository to seed credentials.",
            PINS_FILE,
        )
        return {}

    # A credential file readable by group/other is the same exposure this
    # change exists to remove (cicatrix #4) — refuse rather than reward it.
    mode = PINS_FILE.stat().st_mode
    if mode & 0o077:
        msg = f"{PINS_FILE} is group/other-readable ({mode & 0o777:04o}); run: chmod 600 {PINS_FILE}"
        raise PermissionError(msg)

    with PINS_FILE.open() as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        msg = f"{PINS_FILE} must be a JSON object mapping email -> pin"
        raise ValueError(msg)
    return {str(email).lower(): str(pin) for email, pin in raw.items()}


async def seed_users() -> bool:
    logger.info(f"Seeding users from {DATA_FILE}")

    if not DATA_FILE.exists():
        logger.error(f"Data file not found: {DATA_FILE}")
        return False

    with open(DATA_FILE) as f:
        users = json.load(f)

    # Before any DB connection: a malformed or world-readable PIN file must
    # stop the run, not surface halfway through a partial seed.
    pins = load_pins()

    service = IdentityService()
    conn = await service.get_db_connection()

    try:
        # Check if table exists
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'team_members'
            );
        """,
        )

        if not exists:
            logger.error("Table 'team_members' does not exist. Please run migrations first.")
            return False

        skipped: list[str] = []
        no_credential: list[str] = []

        for user in users:
            email = user["email"]
            name = user["name"]
            role = user["role"]
            department = user["department"]

            notes = user.get("notes", "")

            pin = pins.get(email.lower())

            # Check if user exists
            existing = await conn.fetchrow("SELECT id FROM team_members WHERE email = $1", email)

            if existing and pin is None:
                # Refresh the profile, leave the credential alone. Overwriting
                # pin_hash with a guess would lock a real person out.
                no_credential.append(email)
                logger.info(f"Updating user {name} ({email}) — metadata only, no PIN supplied")
                await conn.execute(
                    """
                    UPDATE team_members
                    SET full_name = $1, role = $2, department = $3, notes = $4, active = true, updated_at = NOW()
                    WHERE email = $5
                """,
                    name,
                    role,
                    department,
                    notes,
                    email,
                )
            elif existing:
                logger.info(f"Updating user {name} ({email})")
                await conn.execute(
                    """
                    UPDATE team_members
                    SET full_name = $1, pin_hash = $2, role = $3, department = $4, notes = $5, active = true, updated_at = NOW()
                    WHERE email = $6
                """,
                    name,
                    service.get_password_hash(pin),
                    role,
                    department,
                    notes,
                    email,
                )
            elif pin is None:
                # An account with no credential is not an account — and
                # pin_hash is NOT NULL. Refuse loudly instead of inventing one.
                skipped.append(email)
                logger.error(f"NOT creating {name} ({email}): no PIN in {PINS_FILE}")
            else:
                logger.info(f"Creating user {name} ({email})")
                await conn.execute(
                    """
                    INSERT INTO team_members (full_name, email, pin_hash, role, department, notes, active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, true, NOW(), NOW())
                """,
                    name,
                    email,
                    service.get_password_hash(pin),
                    role,
                    department,
                    notes,
                )

        if no_credential:
            logger.warning(
                "%d existing member(s) refreshed without touching pin_hash (no PIN supplied): %s",
                len(no_credential),
                ", ".join(no_credential),
            )
        if skipped:
            logger.error(
                "Seeding INCOMPLETE — %d member(s) not created for lack of a PIN: %s",
                len(skipped),
                ", ".join(skipped),
            )
            return False

        logger.info("Seeding complete!")
        return True

    except Exception as e:
        # Exit non-zero: a seeder that reports success on a failed seed is the
        # green-but-dead failure this repository has been bitten by repeatedly.
        logger.error(f"Seeding failed: {e}")
        return False
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(seed_users()) else 1)
