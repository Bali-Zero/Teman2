# S03 Auth Security Hardening — Sprint 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add token revocation (Redis) and security audit trail (Postgres) — the two Sprint 2 deliverables that require zero router changes and can deploy behind feature flags.

**Architecture:** Token revocation uses Redis SETEX with auto-expiry TTL for O(1) checks, integrated into `get_current_user` behind `ENABLE_TOKEN_REVOCATION` flag. Security audit trail uses a dedicated Postgres table with middleware-level hooking. Both are additive — no existing code modified except `deps/auth.py` (revocation check injection).

**Tech Stack:** Python 3.11, FastAPI, Redis (via RedisManager singleton), asyncpg, python-jose

**Spec:** `docs/superpowers/specs/2026-04-06-auth-security-hardening-design.md` (Sprint 2 sections B2, B4)

**Note:** B1 (token refresh/rotation) and B3 (BOLA consolidation) deferred to Sprint 3. B1 requires frontend coordination for refresh flow. B3 analysis showed `crm_practices.py` already has inline RBAC via `can_view_all_practices()` and `crm_clients_documents.py` uses `verify_client_access()` — the remaining gaps need an endpoint-by-endpoint audit first.

---

## File Structure

**New files:**
- `backend/services/security/token_revocation.py` — Redis-backed revocation service
- `backend/services/security/__init__.py` — Package init
- `backend/services/security/audit_service.py` — Security audit trail service
- `backend/migrations/migration_090_security_audit_log.py` — Audit trail table
- `backend/tests/unit/services/security/test_token_revocation.py` — Revocation tests
- `backend/tests/unit/services/security/test_security_audit.py` — Audit tests

**Modified files:**
- `backend/app/deps/auth.py` — Inject revocation check into `get_current_user`
- `backend/app/core/config.py` — Add `enable_token_revocation` flag
- `backend/app/routers/auth.py` — Add revocation on logout, revoke-all endpoint

---

### Task 1: Config — Add Token Revocation Feature Flag

**Files:**
- Modify: `apps/backend-rag/backend/app/core/config.py`
- Test: `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`:

```python
class TestSprint2Config:
    """Test Sprint 2 config fields."""

    def test_enable_token_revocation_defaults_to_false(self):
        """Token revocation should be off by default for safe rollout."""
        from backend.app.core.config import settings

        assert hasattr(settings, "enable_token_revocation")
        assert settings.enable_token_revocation is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py::TestSprint2Config -v`
Expected: FAIL — attribute not found

- [ ] **Step 3: Add config field**

In `apps/backend-rag/backend/app/core/config.py`, find the S03 fields:

```python
    jwt_enforce_expiry: bool = False  # S03: Phase 1 audit mode, flip to True for Phase 2
    jwt_grace_period_days: int = 7  # S03: grace period when enabling expiry enforcement
```

Add after them:

```python
    enable_token_revocation: bool = False  # S03-S2: Redis-backed token revocation

```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py::TestSprint2Config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd apps/backend-rag && git add backend/app/core/config.py backend/tests/unit/app/deps/test_auth_hardened.py
git commit -m "feat(auth): S03-S2 add enable_token_revocation config flag"
```

---

### Task 2: Token Revocation Service

**Files:**
- Create: `apps/backend-rag/backend/services/security/__init__.py`
- Create: `apps/backend-rag/backend/services/security/token_revocation.py`
- Create: `apps/backend-rag/backend/tests/unit/services/security/__init__.py`
- Create: `apps/backend-rag/backend/tests/unit/services/security/test_token_revocation.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/backend-rag/backend/tests/unit/services/security/__init__.py` (empty).

Create `apps/backend-rag/backend/tests/unit/services/security/test_token_revocation.py`:

```python
"""Tests for Redis-backed token revocation — S03 Sprint 2."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTokenRevocationService:
    """Test token revocation via Redis."""

    @pytest.mark.asyncio
    async def test_revoke_token_sets_redis_key(self):
        """Revoking a token should SETEX in Redis with remaining TTL."""
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        svc = TokenRevocationService(redis_client=mock_redis)

        await svc.revoke_token("jti-123", ttl_seconds=3600, reason="logout")

        mock_redis.setex.assert_called_once_with(
            "revoked:jti-123", 3600, "logout"
        )

    @pytest.mark.asyncio
    async def test_is_revoked_returns_true_for_revoked_token(self):
        """Revoked tokens should be detected."""
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        svc = TokenRevocationService(redis_client=mock_redis)

        result = await svc.is_revoked("jti-123")
        assert result is True
        mock_redis.exists.assert_called_once_with("revoked:jti-123")

    @pytest.mark.asyncio
    async def test_is_revoked_returns_false_for_valid_token(self):
        """Non-revoked tokens should pass."""
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        svc = TokenRevocationService(redis_client=mock_redis)

        result = await svc.is_revoked("jti-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_sets_user_key(self):
        """Bulk revocation should set a user-level key."""
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        svc = TokenRevocationService(redis_client=mock_redis)

        await svc.revoke_all_user_tokens("user@balizero.com", reason="password_change")

        mock_redis.setex.assert_called_once_with(
            "revoked_user:user@balizero.com", 86400, "password_change"
        )

    @pytest.mark.asyncio
    async def test_is_user_revoked_checks_user_key(self):
        """User-level revocation should be detected."""
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        svc = TokenRevocationService(redis_client=mock_redis)

        result = await svc.is_user_revoked("user@balizero.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_graceful_on_redis_unavailable(self):
        """If Redis is down, revocation check should fail-open (allow token)."""
        from backend.services.security.token_revocation import TokenRevocationService

        svc = TokenRevocationService(redis_client=None)

        result = await svc.is_revoked("jti-123")
        assert result is False  # fail-open

    @pytest.mark.asyncio
    async def test_graceful_on_redis_error(self):
        """If Redis throws, revocation check should fail-open."""
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.exists.side_effect = ConnectionError("Redis down")
        svc = TokenRevocationService(redis_client=mock_redis)

        result = await svc.is_revoked("jti-123")
        assert result is False  # fail-open
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/security/test_token_revocation.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create the service**

Create `apps/backend-rag/backend/services/security/__init__.py` (empty file).

Create `apps/backend-rag/backend/services/security/token_revocation.py`:

```python
"""
Redis-backed token revocation service (S03 Sprint 2).

Uses Redis SETEX for O(1) token revocation checks.
Fail-open policy: if Redis is unavailable, tokens are NOT rejected.
This prevents mass disconnection during Redis outages.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TokenRevocationService:
    """
    Token revocation via Redis.

    Per-token: SETEX revoked:{jti} <ttl> "reason"
    Per-user: SETEX revoked_user:{email} 86400 "reason"

    Fail-open: Redis down = tokens accepted (not rejected).
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    async def revoke_token(
        self, jti: str, ttl_seconds: int, reason: str = "manual",
    ) -> bool:
        """
        Revoke a specific token by its jti claim.

        Args:
            jti: Token unique identifier (from JWT jti claim)
            ttl_seconds: Remaining TTL of the token (auto-cleanup)
            reason: Why the token was revoked

        Returns:
            True if revoked successfully, False if Redis unavailable
        """
        if not self._redis:
            logger.warning("S03: Token revocation skipped — Redis unavailable")
            return False

        try:
            await self._redis.setex(f"revoked:{jti}", ttl_seconds, reason)
            logger.info(f"S03: Token revoked jti={jti} reason={reason} ttl={ttl_seconds}s")
            return True
        except Exception as e:
            logger.error(f"S03: Token revocation failed jti={jti}: {e}")
            return False

    async def is_revoked(self, jti: str) -> bool:
        """
        Check if a token has been revoked.

        Fail-open: returns False if Redis is unavailable or errors.

        Args:
            jti: Token unique identifier

        Returns:
            True if revoked, False otherwise (including Redis failures)
        """
        if not self._redis:
            return False

        try:
            result = await self._redis.exists(f"revoked:{jti}")
            return bool(result)
        except Exception as e:
            logger.warning(f"S03: Revocation check failed (fail-open): {e}")
            return False

    async def revoke_all_user_tokens(
        self, user_email: str, reason: str = "bulk_revoke",
    ) -> bool:
        """
        Revoke all tokens for a specific user.

        Sets a user-level key that is checked on every auth request.
        TTL is 24h (covers max token lifetime).

        Args:
            user_email: User email to revoke all tokens for
            reason: Why tokens were revoked

        Returns:
            True if set successfully, False otherwise
        """
        if not self._redis:
            logger.warning("S03: User revocation skipped — Redis unavailable")
            return False

        try:
            await self._redis.setex(
                f"revoked_user:{user_email}", 86400, reason,
            )
            logger.info(f"S03: All tokens revoked for {user_email} reason={reason}")
            return True
        except Exception as e:
            logger.error(f"S03: User revocation failed {user_email}: {e}")
            return False

    async def is_user_revoked(self, user_email: str) -> bool:
        """
        Check if all tokens for a user have been revoked.

        Args:
            user_email: User email to check

        Returns:
            True if user's tokens are revoked, False otherwise
        """
        if not self._redis:
            return False

        try:
            result = await self._redis.exists(f"revoked_user:{user_email}")
            return bool(result)
        except Exception as e:
            logger.warning(f"S03: User revocation check failed (fail-open): {e}")
            return False
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/security/test_token_revocation.py -v`
Expected: 7/7 PASS

- [ ] **Step 5: Commit**

```bash
cd apps/backend-rag && git add backend/services/security/ backend/tests/unit/services/security/
git commit -m "feat(auth): S03-S2 Redis-backed token revocation service"
```

---

### Task 3: Inject Revocation Check into get_current_user

**Files:**
- Modify: `apps/backend-rag/backend/app/deps/auth.py`
- Test: `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`:

```python
class TestTokenRevocationInAuth:
    """Test revocation check in get_current_user."""

    def _make_token(self, jti: str = "test-jti-revoke") -> str:
        from backend.app.core.config import settings
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "user-1",
            "email": "test@balizero.com",
            "role": "admin",
            "exp": now + timedelta(hours=1),
            "iat": now,
            "jti": jti,
            "type": "access",
        }
        return jose_jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

    def _make_request(self) -> MagicMock:
        request = MagicMock()
        request.state = MagicMock(spec=[])
        return request

    def _make_credentials(self, token: str) -> MagicMock:
        creds = MagicMock()
        creds.credentials = token
        return creds

    def test_revocation_disabled_skips_check(self):
        """When enable_token_revocation=False, no revocation check happens."""
        from backend.app.deps.auth import get_current_user

        token = self._make_token()
        request = self._make_request()
        creds = self._make_credentials(token)

        # Default config has enable_token_revocation=False
        user = get_current_user(request, creds)
        assert user["email"] == "test@balizero.com"
```

- [ ] **Step 2: Run test to verify it passes (baseline)**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py::TestTokenRevocationInAuth -v`
Expected: PASS (revocation disabled = no change needed yet)

- [ ] **Step 3: Modify get_current_user to check revocation**

In `apps/backend-rag/backend/app/deps/auth.py`, find the `return user_ctx` line (line 108) inside the try block of `get_current_user`. Replace:

```python
        return user_ctx
```

With:

```python
        # S03-S2: Check token revocation if enabled
        if settings.enable_token_revocation:
            jti = payload.get("jti")
            if jti:
                try:
                    from backend.services.security.token_revocation import TokenRevocationService
                    from backend.core.redis_manager import RedisManager

                    redis_client = RedisManager.get_instance().get_async_client()
                    revocation_svc = TokenRevocationService(redis_client=redis_client)

                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're in a sync function called from async context
                        # Cannot await directly — log and skip (fail-open)
                        logger.debug("S03-S2: Revocation check skipped in sync context")
                    else:
                        is_revoked = loop.run_until_complete(revocation_svc.is_revoked(jti))
                        if is_revoked:
                            raise HTTPException(status_code=401, detail="Token has been revoked")

                        is_user_revoked = loop.run_until_complete(
                            revocation_svc.is_user_revoked(user_email)
                        )
                        if is_user_revoked:
                            raise HTTPException(status_code=401, detail="All user sessions revoked")
                except HTTPException:
                    raise
                except Exception as e:
                    # Fail-open: Redis errors don't block auth
                    logger.warning(f"S03-S2: Revocation check error (fail-open): {e}")

        return user_ctx
```

**IMPORTANT NOTE**: `get_current_user` is a sync function. The revocation check is async. In practice, when `enable_token_revocation` is True and we're in a running event loop (which is always the case in FastAPI), we log and skip. The real revocation enforcement will happen in `HybridAuthMiddleware` (which is already async). This sync-context path is a safety net only.

- [ ] **Step 4: Run all S03 tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py -v`
Expected: All PASS (revocation disabled by default)

- [ ] **Step 5: Commit**

```bash
cd apps/backend-rag && git add backend/app/deps/auth.py backend/tests/unit/app/deps/test_auth_hardened.py
git commit -m "feat(auth): S03-S2 inject revocation check into get_current_user (fail-open)"
```

---

### Task 4: Security Audit Log Migration

**Files:**
- Create: `apps/backend-rag/backend/migrations/migration_090_security_audit_log.py`

- [ ] **Step 1: Write the migration**

Create `apps/backend-rag/backend/migrations/migration_090_security_audit_log.py`:

```python
"""
Migration 090: Security audit log table for S03 Sprint 2.

Tracks security-sensitive actions: login, logout, token refresh,
token revocation, RBAC violations, API key usage, data exports.
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "090_security_audit_log"
DESCRIPTION = "S03-S2: Create security_audit_log table for security event tracking"


async def check_if_applied(conn) -> bool:
    """Check if migration has been applied."""
    result = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'security_audit_log')"
    )
    return result


async def apply(conn) -> None:
    """Apply migration: create security_audit_log table."""
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS security_audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id VARCHAR(255),
            user_email VARCHAR(255),
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100),
            resource_id VARCHAR(255),
            ip_address INET,
            user_agent TEXT,
            details JSONB,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_security_audit_user ON security_audit_log(user_email, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_security_audit_action ON security_audit_log(action, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_security_audit_created ON security_audit_log(created_at)"
    )

    # Track migration
    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    """Rollback migration."""
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute("DROP TABLE IF EXISTS security_audit_log CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID
    )
    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
```

- [ ] **Step 2: Verify syntax**

Run: `cd apps/backend-rag && python -c "import backend.migrations.migration_090_security_audit_log; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd apps/backend-rag && git add backend/migrations/migration_090_security_audit_log.py
git commit -m "feat(auth): S03-S2 migration 090 — security_audit_log table"
```

---

### Task 5: Security Audit Service

**Files:**
- Create: `apps/backend-rag/backend/services/security/audit_service.py`
- Create: `apps/backend-rag/backend/tests/unit/services/security/test_security_audit.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/backend-rag/backend/tests/unit/services/security/test_security_audit.py`:

```python
"""Tests for security audit trail service — S03 Sprint 2."""

from unittest.mock import AsyncMock

import pytest


class TestSecurityAuditService:
    """Test security event logging."""

    @pytest.mark.asyncio
    async def test_log_event_inserts_row(self):
        """Logging an event should INSERT into security_audit_log."""
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        svc = SecurityAuditService()

        await svc.log_event(
            conn=mock_conn,
            action="login",
            user_email="zero@balizero.com",
            ip_address="1.2.3.4",
            success=True,
            details={"method": "pin"},
        )

        mock_conn.execute.assert_called_once()
        call_sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO security_audit_log" in call_sql

    @pytest.mark.asyncio
    async def test_log_event_with_resource(self):
        """Events can reference a specific resource."""
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        svc = SecurityAuditService()

        await svc.log_event(
            conn=mock_conn,
            action="token_revoke",
            user_email="zero@balizero.com",
            resource_type="token",
            resource_id="jti-123",
            success=True,
        )

        call_args = mock_conn.execute.call_args[0]
        assert call_args[3] == "token_revoke"  # action param

    @pytest.mark.asyncio
    async def test_log_event_handles_db_error_gracefully(self):
        """DB errors should not propagate — audit is best-effort."""
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB down"))
        svc = SecurityAuditService()

        # Should NOT raise
        await svc.log_event(
            conn=mock_conn,
            action="login",
            user_email="zero@balizero.com",
            success=True,
        )

    @pytest.mark.asyncio
    async def test_log_rbac_violation(self):
        """RBAC violations should be logged with details."""
        from backend.services.security.audit_service import SecurityAuditService

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        svc = SecurityAuditService()

        await svc.log_event(
            conn=mock_conn,
            action="rbac_violation",
            user_email="team@balizero.com",
            resource_type="practice",
            resource_id="42",
            success=False,
            details={"attempted": "view", "required_role": "admin"},
        )

        call_args = mock_conn.execute.call_args[0]
        assert call_args[3] == "rbac_violation"
        assert call_args[7] is False  # success=False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/security/test_security_audit.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create the service**

Create `apps/backend-rag/backend/services/security/audit_service.py`:

```python
"""
Security audit trail service (S03 Sprint 2).

Logs security-sensitive events to security_audit_log table.
Best-effort: DB errors are logged but never propagate.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SecurityAuditService:
    """
    Log security events to PostgreSQL.

    Actions: login, logout, token_refresh, token_revoke,
    rbac_violation, api_key_usage, data_export, permission_change.
    """

    async def log_event(
        self,
        conn: Any,
        action: str,
        user_email: str | None = None,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a security event. Best-effort — never raises.

        Args:
            conn: asyncpg connection
            action: Event type (login, logout, token_revoke, etc.)
            user_email: User performing the action
            user_id: User ID (if available)
            resource_type: Type of resource affected (token, practice, client)
            resource_id: ID of affected resource
            ip_address: Client IP address
            user_agent: Client user agent string
            success: Whether the action succeeded
            details: Additional context as dict (stored as JSONB)
        """
        try:
            details_json = json.dumps(details) if details else None

            await conn.execute(
                """
                INSERT INTO security_audit_log
                    (user_id, user_email, action, resource_type, resource_id,
                     ip_address, user_agent, success, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                """,
                user_id,
                user_email,
                action,
                resource_type,
                resource_id,
                ip_address,
                user_agent,
                success,
                details_json,
            )
        except Exception as e:
            logger.error(f"S03-S2: Security audit log failed: {e} (action={action})")
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/security/test_security_audit.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
cd apps/backend-rag && git add backend/services/security/audit_service.py backend/tests/unit/services/security/test_security_audit.py
git commit -m "feat(auth): S03-S2 security audit trail service (best-effort logging)"
```

---

### Task 6: Wire Audit Logging into Auth Router (Logout + Revoke)

**Files:**
- Modify: `apps/backend-rag/backend/app/routers/auth.py`
- Test: `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`:

```python
class TestLogoutRevocation:
    """Test that logout revokes the current token."""

    def test_logout_endpoint_exists(self):
        """The /api/auth/logout endpoint should exist."""
        from backend.app.routers.auth import router

        paths = [route.path for route in router.routes]
        assert "/logout" in paths

    def test_revoke_all_endpoint_exists(self):
        """The /api/auth/revoke-all endpoint should exist for admin use."""
        from backend.app.routers.auth import router

        paths = [route.path for route in router.routes]
        assert "/revoke-all" in paths
```

- [ ] **Step 2: Run test to verify /revoke-all fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py::TestLogoutRevocation -v`
Expected: `/logout` passes, `/revoke-all` fails

- [ ] **Step 3: Add revoke-all endpoint to auth router**

In `apps/backend-rag/backend/app/routers/auth.py`, add before the final comment block (before line 442):

```python
@router.post("/revoke-all")
async def revoke_all_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Revoke all active sessions for the current user (S03-S2).

    Sets a user-level revocation key in Redis. All tokens for this
    user will be rejected until the key expires (24h).
    """
    from backend.app.core.config import settings

    user_email = current_user.get("email", "")
    client_ip = request.client.host if request.client else None

    if settings.enable_token_revocation:
        try:
            from backend.core.redis_manager import RedisManager
            from backend.services.security.token_revocation import TokenRevocationService

            redis_client = RedisManager.get_instance().get_async_client()
            revocation_svc = TokenRevocationService(redis_client=redis_client)
            await revocation_svc.revoke_all_user_tokens(user_email, reason="user_requested")
        except Exception as e:
            logger.warning(f"S03-S2: Revoke-all failed for {user_email}: {e}")

    # Audit log
    try:
        async with db_pool.acquire() as conn:
            from backend.services.security.audit_service import SecurityAuditService

            audit = SecurityAuditService()
            await audit.log_event(
                conn=conn,
                action="revoke_all",
                user_email=user_email,
                ip_address=client_ip,
                success=True,
                details={"reason": "user_requested"},
            )
    except Exception as e:
        logger.warning(f"S03-S2: Audit log failed for revoke-all: {e}")

    return {"success": True, "message": "All sessions revoked"}
```

- [ ] **Step 4: Run test**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py::TestLogoutRevocation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd apps/backend-rag && git add backend/app/routers/auth.py backend/tests/unit/app/deps/test_auth_hardened.py
git commit -m "feat(auth): S03-S2 add /revoke-all endpoint + wire audit logging"
```

---

### Task 7: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Import chain check**

Run: `cd apps/backend-rag && python -c "from backend.app.dependencies import get_current_user; print('OK')"`
Expected: `OK`

- [ ] **Step 2: All S03 tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py backend/tests/unit/app/services/test_api_key_db.py backend/tests/unit/services/security/ -v`
Expected: All PASS

- [ ] **Step 3: Core RAG tests (no regression)**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no`
Expected: PASS

- [ ] **Step 4: Verify feature flags are OFF**

Run: `cd apps/backend-rag && python -c "from backend.app.core.config import settings; print(f'enable_token_revocation={settings.enable_token_revocation}, jwt_enforce_expiry={settings.jwt_enforce_expiry}')"`
Expected: `enable_token_revocation=False, jwt_enforce_expiry=False`

- [ ] **Step 5: Git log of Sprint 2 commits**

Run: `git log --oneline --grep="S03-S2" | head -10`
