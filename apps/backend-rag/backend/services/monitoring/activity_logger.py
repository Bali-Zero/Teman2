"""
Activity Logger Service
Centralized service for logging all team activities, interactions, and API calls

Usage:
    from backend.services.monitoring.activity_logger import activity_logger

    # Log general activity
    await activity_logger.log_activity(
        user_email="zero@balizero.com",
        action_type="crm_client_created",
        resource_type="client",
        resource_id="123",
        description="Created new client: John Doe",
        details={"client_name": "John Doe", "status": "active"}
    )

    # Log team interaction
    await activity_logger.log_interaction(
        user_email="zero@balizero.com",
        interaction_type="chat",
        direction="outbound",
        client_email="john@example.com",
        message_content="Hi John, your KITAS is ready!",
        metadata={"response_time_seconds": 120}
    )

    # Log API call
    await activity_logger.log_api_call(
        user_email="zero@balizero.com",
        method="POST",
        endpoint="/api/clients",
        request_body={"name": "John"},
        response_status=201,
        response_time_ms=45
    )
"""

import json
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)


class ActivityLogger:
    """Centralized activity logging service"""

    def __init__(self):
        self.pool: asyncpg.Pool | None = None
        self._initialized = False

    async def initialize(self, pool: asyncpg.Pool):
        """Initialize the logger with a database pool"""
        self.pool = pool
        self._initialized = True
        logger.info("✅ Activity Logger initialized")

    def _sanitize_data(self, data: Any, max_length: int = 10000) -> Any:
        """
        Sanitize sensitive data before logging

        - Removes passwords, tokens, API keys
        - Truncates large payloads
        - Handles circular references
        """
        if data is None:
            return None

        # Convert to dict if possible
        if hasattr(data, "dict"):
            data = data.dict()
        elif not isinstance(data, (dict, list, str, int, float, bool)):
            data = str(data)

        # Handle string
        if isinstance(data, str):
            if len(data) > max_length:
                return data[:max_length] + "... [truncated]"
            return data

        # Handle dict
        if isinstance(data, dict):
            sanitized = {}
            sensitive_keys = {
                "password",
                "token",
                "api_key",
                "secret",
                "authorization",
                "auth",
                "bearer",
                "jwt",
                "credential",
                "private_key",
            }
            for key, value in data.items():
                key_lower = str(key).lower()
                if any(sensitive in key_lower for sensitive in sensitive_keys):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_data(value, max_length=1000)
            return sanitized

        # Handle list
        if isinstance(data, list):
            return [
                self._sanitize_data(item, max_length=1000) for item in data[:100]
            ]  # Max 100 items

        return data

    async def log_activity(
        self,
        user_email: str,
        action_type: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        description: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
    ) -> bool:
        """
        Log a general activity

        Args:
            user_email: Email of the user performing the action
            action_type: Type of action (login, logout, crm_create, etc.)
            resource_type: Type of resource affected (client, practice, document, etc.)
            resource_id: ID of the resource
            description: Human-readable description
            details: Additional details as dict
            ip_address: User's IP address
            user_agent: User's browser/client
            session_id: Session identifier

        Returns:
            True if logged successfully
        """
        if not self._initialized or not self.pool:
            logger.warning("⚠️ Activity logger not initialized, skipping log")
            return False

        try:
            sanitized_details = self._sanitize_data(details or {})

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO activity_logs (
                        user_email, action_type, resource_type, resource_id,
                        description, details, ip_address, user_agent, session_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    user_email,
                    action_type,
                    resource_type,
                    resource_id,
                    description,
                    json.dumps(sanitized_details),
                    ip_address,
                    user_agent,
                    session_id,
                )

            logger.debug(
                f"📝 Logged activity: {action_type} by {user_email}",
                extra={"action_type": action_type, "user_email": user_email},
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to log activity: {e}", exc_info=True)
            return False

    async def log_interaction(
        self,
        user_email: str,
        interaction_type: str,
        direction: str,
        client_email: str | None = None,
        client_name: str | None = None,
        subject: str | None = None,
        message_content: str | None = None,
        attachments: list | None = None,
        metadata: dict | None = None,
        conversation_id: int | None = None,
        practice_id: int | None = None,
        response_time_seconds: int | None = None,
    ) -> bool:
        """
        Log a team interaction (chat, WhatsApp, email, call)

        Args:
            user_email: Team member email
            interaction_type: Type (chat, whatsapp, email, call, meeting)
            direction: Direction (inbound, outbound)
            client_email: Client email (if applicable)
            client_name: Client name
            subject: Email subject or call topic
            message_content: Full message/transcript
            attachments: List of attachments
            metadata: Additional metadata
            conversation_id: Link to conversations table
            practice_id: Link to practices table
            response_time_seconds: Time to respond (for analytics)

        Returns:
            True if logged successfully
        """
        if not self._initialized or not self.pool:
            logger.warning("⚠️ Activity logger not initialized, skipping interaction log")
            return False

        try:
            # Create preview (first 500 chars)
            message_preview = None
            if message_content:
                message_preview = message_content[:500]

            sanitized_metadata = self._sanitize_data(metadata or {})
            sanitized_attachments = self._sanitize_data(attachments or [])

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO team_interactions (
                        user_email, interaction_type, direction, client_email,
                        client_name, subject, message_content, message_preview,
                        attachments, metadata, conversation_id, practice_id,
                        response_time_seconds
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                    user_email,
                    interaction_type,
                    direction,
                    client_email,
                    client_name,
                    subject,
                    message_content,
                    message_preview,
                    json.dumps(sanitized_attachments),
                    json.dumps(sanitized_metadata),
                    conversation_id,
                    practice_id,
                    response_time_seconds,
                )

            logger.debug(
                f"💬 Logged interaction: {interaction_type} ({direction}) by {user_email}",
                extra={"interaction_type": interaction_type, "user_email": user_email},
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to log interaction: {e}", exc_info=True)
            return False

    async def log_api_call(
        self,
        method: str,
        endpoint: str,
        response_status: int,
        response_time_ms: int,
        user_email: str | None = None,
        query_params: dict | None = None,
        request_body: dict | None = None,
        response_body: dict | None = None,
        error_message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
        session_id: str | None = None,
    ) -> bool:
        """
        Log an API call

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint path
            response_status: HTTP status code
            response_time_ms: Response time in milliseconds
            user_email: Authenticated user (if any)
            query_params: URL query parameters
            request_body: Request payload
            response_body: Response payload (optional, usually not logged)
            error_message: Error message (if any)
            ip_address: User's IP
            user_agent: User's browser/client
            correlation_id: Request correlation ID
            session_id: Session ID

        Returns:
            True if logged successfully
        """
        if not self._initialized or not self.pool:
            # API logging is high-volume, so we don't warn for every call
            return False

        try:
            sanitized_query_params = self._sanitize_data(query_params or {})
            sanitized_request_body = self._sanitize_data(request_body)
            sanitized_response_body = self._sanitize_data(response_body)

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO api_audit_trail (
                        user_email, method, endpoint, query_params, request_body,
                        response_status, response_body, response_time_ms, error_message,
                        ip_address, user_agent, correlation_id, session_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                    user_email,
                    method,
                    endpoint,
                    json.dumps(sanitized_query_params),
                    json.dumps(sanitized_request_body) if sanitized_request_body else None,
                    response_status,
                    json.dumps(sanitized_response_body) if sanitized_response_body else None,
                    response_time_ms,
                    error_message,
                    ip_address,
                    user_agent,
                    correlation_id,
                    session_id,
                )

            # Only log errors or slow requests
            if response_status >= 400 or response_time_ms > 1000:
                logger.debug(
                    f"🔍 Logged API call: {method} {endpoint} → {response_status} ({response_time_ms}ms)",
                    extra={
                        "method": method,
                        "endpoint": endpoint,
                        "status": response_status,
                        "response_time_ms": response_time_ms,
                    },
                )
            return True

        except Exception:
            # Don't log API logging failures to avoid infinite loops
            return False

    async def log_session(
        self,
        session_id: str,
        user_email: str,
        event_type: str,  # login, logout, activity
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_type: str | None = None,
        browser: str | None = None,
        os: str | None = None,
    ) -> bool:
        """
        Log session events (login, logout, activity)

        Args:
            session_id: Session identifier
            user_email: User email
            event_type: Type of event (login, logout, activity)
            ip_address: User's IP
            user_agent: User's browser/client
            device_type: Device type (desktop, mobile, tablet)
            browser: Browser name
            os: Operating system

        Returns:
            True if logged successfully
        """
        if not self._initialized or not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                if event_type == "login":
                    # Create new session
                    await conn.execute(
                        """
                        INSERT INTO session_tracking (
                            session_id, user_email, ip_address, user_agent,
                            device_type, browser, os, login_at, last_activity_at, is_active
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW(), TRUE)
                        ON CONFLICT (session_id) DO UPDATE SET
                            last_activity_at = NOW(),
                            is_active = TRUE
                        """,
                        session_id,
                        user_email,
                        ip_address,
                        user_agent,
                        device_type,
                        browser,
                        os,
                    )
                    logger.info(f"🔐 Session started: {user_email} ({session_id})")

                elif event_type == "logout":
                    # Close session
                    await conn.execute(
                        """
                        UPDATE session_tracking
                        SET logout_at = NOW(),
                            is_active = FALSE,
                            duration_seconds = EXTRACT(EPOCH FROM (NOW() - login_at))::INTEGER
                        WHERE session_id = $1
                        """,
                        session_id,
                    )
                    logger.info(f"🔓 Session ended: {user_email} ({session_id})")

                elif event_type == "activity":
                    # Update last activity
                    await conn.execute(
                        """
                        UPDATE session_tracking
                        SET last_activity_at = NOW(),
                            actions_count = actions_count + 1
                        WHERE session_id = $1
                        """,
                        session_id,
                    )

            return True

        except Exception as e:
            logger.error(f"❌ Failed to log session event: {e}", exc_info=True)
            return False


# Global singleton instance
activity_logger = ActivityLogger()
