"""
Oracle Database Service
Manages PostgreSQL database operations for Oracle endpoints
"""

import json
import logging
from typing import Any

from db.utils import db_retry
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from services.oracle_config import oracle_config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """PostgreSQL database manager for user profiles and analytics using SQLAlchemy"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        """Initialize SQLAlchemy engine with connection pooling"""
        try:
            self._engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=10,  # Increased from default 5
                max_overflow=20,  # Increased from default 10
                pool_timeout=60,  # Increased timeout
                pool_recycle=1800,  # Recycle connections every 30 min
                pool_pre_ping=True,  # Verify connection before use
            )
            logger.info("✅ Database engine initialized with connection pool")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database engine: {e}")
            raise

    @db_retry(max_retries=3, delay=0.5)
    async def get_user_profile(self, user_email: str) -> dict[str, Any] | None:
        """Retrieve user profile with localization preferences."""
        # 1. First, try static team_members data (always available, no DB dependency)
        try:
            from data.team_members import TEAM_MEMBERS

            for member in TEAM_MEMBERS:
                if member.get("email", "").lower() == user_email.lower():
                    logger.info(f"✅ Loaded user profile for {user_email} from team_members.py")
                    return {
                        "id": member.get("id", ""),
                        "email": member.get("email", user_email),
                        "name": member.get("name", "Team Member"),
                        "role": member.get("role", "Member"),
                        "role_level": member.get("role", "member").lower(),
                        "status": "active",
                        "language_preference": member.get("preferred_language", "en"),
                        "timezone": "Asia/Makassar",
                        "meta_json": {
                            "notes": member.get("notes", ""),
                            "department": member.get("department", ""),
                            "traits": member.get("traits", []),
                            "emotional_preferences": member.get("emotional_preferences", {}),
                        },
                    }
        except ImportError:
            logger.warning("team_members.py not found, falling back to DB")
        except Exception as e:
            logger.warning(f"Error loading team_members: {e}")

        # 2. Fallback to PostgreSQL users table
        try:
            with self._engine.connect() as conn:
                query = text(
                    """
                SELECT id, email, name, role, status, language_preference, meta_json, role_level, timezone
                FROM users
                WHERE email = :email AND status = 'active'
                """
                )
                result = conn.execute(query, {"email": user_email}).mappings().fetchone()

                if result:
                    user_profile = dict(result)
                    # Parse meta_json if it's a string
                    if isinstance(user_profile.get("meta_json"), str):
                        user_profile["meta_json"] = json.loads(user_profile["meta_json"])
                    logger.info(f"✅ Loaded user profile for {user_email} from PostgreSQL")
                    return user_profile

                logger.warning(f"⚠️ User profile not found for {user_email}")
                return None

        except SQLAlchemyError as e:
            logger.error(f"❌ DB Error retrieving user profile for {user_email}: {e}")
            raise  # Let retry logic handle it
        except Exception as e:
            logger.error(f"❌ Error retrieving user profile for {user_email}: {e}")
            return None

    @db_retry(max_retries=3, delay=0.5)
    async def store_query_analytics(self, analytics_data: dict[str, Any]) -> None:
        """Store query analytics for performance monitoring"""
        try:
            with self._engine.begin() as conn:  # Transaction
                query = text(
                    """
                INSERT INTO query_analytics (
                    user_id, query_hash, query_text, response_text,
                    language_preference, model_used, response_time_ms,
                    document_count, session_id, metadata
                ) VALUES (
                    :user_id, :query_hash, :query_text, :response_text,
                    :language_preference, :model_used, :response_time_ms,
                    :document_count, :session_id, :metadata
                )
                """
                )

                params = {
                    "user_id": analytics_data.get("user_id"),
                    "query_hash": analytics_data.get("query_hash"),
                    "query_text": analytics_data.get("query_text"),
                    "response_text": analytics_data.get("response_text"),
                    "language_preference": analytics_data.get("language_preference"),
                    "model_used": analytics_data.get("model_used"),
                    "response_time_ms": analytics_data.get("response_time_ms"),
                    "document_count": analytics_data.get("document_count"),
                    "session_id": analytics_data.get("session_id"),
                    "metadata": json.dumps(analytics_data.get("metadata", {})),
                }

                conn.execute(query, params)

        except SQLAlchemyError as e:
            logger.error(f"❌ DB Error storing query analytics: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error storing query analytics: {e}")

    @db_retry(max_retries=3, delay=0.5)
    async def store_feedback(self, feedback_data: dict[str, Any]) -> None:
        """Store user feedback for continuous learning"""
        try:
            with self._engine.begin() as conn:  # Transaction
                query = text(
                    """
                INSERT INTO knowledge_feedback (
                    user_id, query_text, original_answer, user_correction,
                    feedback_type, model_used, response_time_ms,
                    user_rating, session_id, metadata
                ) VALUES (
                    :user_id, :query_text, :original_answer, :user_correction,
                    :feedback_type, :model_used, :response_time_ms,
                    :user_rating, :session_id, :metadata
                )
                """
                )

                params = {
                    "user_id": feedback_data.get("user_id"),
                    "query_text": feedback_data.get("query_text"),
                    "original_answer": feedback_data.get("original_answer"),
                    "user_correction": feedback_data.get("user_correction"),
                    "feedback_type": feedback_data.get("feedback_type"),
                    "model_used": feedback_data.get("model_used"),
                    "response_time_ms": feedback_data.get("response_time_ms"),
                    "user_rating": feedback_data.get("user_rating"),
                    "session_id": feedback_data.get("session_id"),
                    "metadata": json.dumps(feedback_data.get("metadata", {})),
                }

                conn.execute(query, params)

        except SQLAlchemyError as e:
            logger.error(f"❌ DB Error storing feedback: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error storing feedback: {e}")


# Initialize database manager singleton
db_manager = DatabaseManager(oracle_config.database_url)
