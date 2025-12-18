"""
NUZANTARA PRIME - Identity Service
Business logic for authentication and user management
"""

import logging
from datetime import datetime, timedelta, timezone

import asyncpg
import bcrypt
from jose import jwt

from app.core.config import settings
from app.modules.identity.models import User

logger = logging.getLogger(__name__)


class IdentityService:
    """
    Identity Service - Authentication and user management

    Replicates the exact login flow from Node.js backend (team-login.ts)
    """

    def __init__(self):
        """Initialize Identity Service"""
        self.jwt_secret = settings.jwt_secret_key
        self.jwt_algorithm = settings.jwt_algorithm

        # Warn if using default or empty secret key
        if (
            not self.jwt_secret
            or self.jwt_secret == "zantara_default_secret_key_2025_change_in_production"
        ):
            logger.warning(
                "⚠️  Using default or empty JWT secret key. This is insecure for production!"
            )

    def get_password_hash(self, password: str) -> str:
        """
        Hash password/PIN using bcrypt nativo

        Args:
            password: Plain text password/PIN

        Returns:
            Hashed password string (utf-8 encoded)
        """
        # Encode string to bytes, hash it, decode back to utf-8 string for DB storage
        pwd_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(pwd_bytes, salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify PIN/password against bcrypt hash

        Args:
            plain_password: Plain text password/PIN
            hashed_password: bcrypt hashed password from database

        Returns:
            True if password matches, False otherwise
        """
        # Encode both to bytes and check
        try:
            plain_bytes = plain_password.encode("utf-8")
            hashed_bytes = hashed_password.encode("utf-8")
            return bcrypt.checkpw(plain_bytes, hashed_bytes)
        except Exception as e:
            logger.error(f"Bcrypt verification failed: {e}")
            return False

    async def get_db_connection(self) -> asyncpg.Connection:
        """
        Get database connection

        Returns:
            asyncpg.Connection instance
        """
        if not settings.database_url:
            raise ValueError("DATABASE_URL not configured")
        return await asyncpg.connect(settings.database_url)

    async def authenticate_user(self, email: str, pin: str) -> User | None:
        """
        Authenticate user by email and PIN

        Args:
            email: User email address
            pin: User PIN (4-8 digits)

        Returns:
            User object if authentication succeeds, None otherwise
        """
        # Validate PIN format (4-8 digits, same as Node.js)
        if not pin or not pin.isdigit() or len(pin) < 4 or len(pin) > 8:
            logger.warning(f"Invalid PIN format for {email}")
            return None

        conn = None
        try:
            conn = await self.get_db_connection()

            # Query user (case-insensitive email, same as Node.js)
            # Note: Using full_name and active in SQL, mapped to name and is_active in Python model
            query = """
                SELECT id, full_name as name, email, pin_hash, role, department, language,
                       personalized_response, active as is_active, last_login,
                       failed_attempts, locked_until, created_at, updated_at
                FROM team_members
                WHERE LOWER(email) = LOWER($1) AND active = true
            """

            row = await conn.fetchrow(query, email)

            if not row:
                logger.warning(f"User not found or inactive: {email}")
                return None

            # Check if account is locked
            if row["locked_until"] and row["locked_until"] > datetime.now(timezone.utc):
                logger.warning(f"Account locked until {row['locked_until']} for {email}")
                return None

            # Verify PIN
            pin_hash_from_db = row["pin_hash"]
            logger.info(
                f"🔍 Verifying PIN for {email}, hash length: {len(pin_hash_from_db)}, hash prefix: {pin_hash_from_db[:20] if pin_hash_from_db else 'None'}"
            )

            if not self.verify_password(pin, pin_hash_from_db):
                # Increment failed attempts
                await conn.execute(
                    """
                    UPDATE team_members
                    SET failed_attempts = failed_attempts + 1,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                )
                logger.warning(f"❌ Invalid PIN for {email} (hash verification failed)")
                return None

            logger.info(f"✅ PIN verified successfully for {email}")

            # Reset failed attempts on successful login
            await conn.execute(
                """
                UPDATE team_members
                SET failed_attempts = 0,
                    locked_until = NULL,
                    last_login = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                row["id"],
            )

            # Create User object from database row
            # Note: Query already maps full_name -> name and active -> is_active
            user = User(
                id=str(row["id"]),  # Ensure string type
                name=row["name"],  # Already mapped from full_name in query
                email=row["email"],
                pin_hash=row["pin_hash"],
                role=row["role"],
                department=row["department"],
                language=row["language"] or "en",
                personalized_response=row["personalized_response"] or False,
                is_active=row["is_active"],  # Already mapped from active in query
                last_login=row["last_login"],
                failed_attempts=0,  # Reset after successful login
                locked_until=None,  # Reset after successful login
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

            logger.info(f"✅ User authenticated: {user.name} ({user.email})")
            return user

        except Exception as e:
            logger.error(f"Authentication error for {email}: {e}", exc_info=True)
            return None
        finally:
            if conn:
                await conn.close()

    def create_access_token(self, user: User, session_id: str) -> str:
        """
        Create JWT access token (exactly matching Node.js format)

        Args:
            user: Authenticated User object
            session_id: Session identifier

        Returns:
            JWT token string
        """
        # Payload structure matches Node.js exactly
        # Expiration: 7 days (same as Node.js '7d')
        expiration = datetime.now(timezone.utc) + timedelta(days=7)

        payload = {
            "sub": user.id,  # Standard Subject claim
            "userId": user.id,  # Node.js uses "userId" not "id"
            "email": user.email,
            "role": user.role,
            "department": user.department,
            "sessionId": session_id,
            "exp": int(expiration.timestamp()),  # JWT exp claim (Unix timestamp)
        }

        # Generate token with same secret and algorithm as Node.js
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

        return token

    def get_permissions_for_role(self, role: str) -> list[str]:
        """
        Get permissions based on role (matches Node.js logic)

        Args:
            role: User role string

        Returns:
            List of permission strings
        """
        permissions_map: dict[str, list[str]] = {
            "CEO": ["all", "admin", "finance", "hr", "tech", "marketing"],
            "Board Member": ["all", "finance", "hr", "tech", "marketing"],
            "AI Bridge/Tech Lead": ["all", "tech", "admin", "finance"],
            "Executive Consultant": ["setup", "finance", "clients", "reports"],
            "Specialist Consultant": ["setup", "clients", "reports"],
            "Junior Consultant": ["setup", "clients"],
            "Crew Lead": ["setup", "clients", "team"],
            "Tax Manager": ["tax", "finance", "reports", "clients"],
            "Tax Expert": ["tax", "reports", "clients"],
            "Tax Consultant": ["tax", "clients"],
            "Tax Care": ["tax", "clients"],
            "Marketing Specialist": ["marketing", "clients", "reports"],
            "Marketing Advisory": ["marketing", "clients"],
            "Reception": ["clients", "appointments"],
            "External Advisory": ["clients", "reports"],
        }

        return permissions_map.get(role, ["clients"])
