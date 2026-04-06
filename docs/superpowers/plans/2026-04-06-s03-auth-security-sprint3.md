# S03 Auth Security Hardening — Sprint 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the last BOLA gap, add PDP-compliant consent tracking, brute force detection, API key scoping, and 4 quick security fixes — all validated by Codex CLI, Gemini CLI, and DeepSeek R1.

**Architecture:** All items are independent and additive. BOLA fix is 1 line. Brute force uses Redis INCR in the login endpoint (not middleware). Consent uses an append-only table. API key scoping adds a dependency check. Quick fixes are surgical edits.

**Tech Stack:** Python 3.11, FastAPI, asyncpg, Redis (via RedisManager), python-jose

**Spec:** `docs/superpowers/specs/2026-04-06-auth-security-hardening-design.md`
**Multi-agent validation:** Codex (GPT-5.4), Gemini (2.5 Pro), DeepSeek R1 (671b) — all 3 confirmed design.

---

## File Structure

**New files:**
- `backend/migrations/migration_091_client_consent_log.py` — PDP consent history table
- `backend/services/security/brute_force.py` — Login brute force detection
- `backend/services/security/pdp_service.py` — PDP breach notify + consent management
- `backend/app/routers/admin_security.py` — Admin security endpoints
- `backend/app/deps/permissions.py` — Permission-based auth dependencies
- `backend/tests/unit/services/security/test_brute_force.py`
- `backend/tests/unit/services/security/test_pdp_service.py`
- `backend/tests/unit/app/deps/test_permissions.py`

**Modified files:**
- `backend/app/routers/crm_portal_integration.py:423` — Add verify_client_access (BOLA fix)
- `backend/app/routers/auth.py` — Brute force check at login start
- `backend/app/core/config.py` — Remove jwt_grace_period_days, dev_scraper_key default
- `backend/app/deps/auth.py` — Validate type=access claim
- `backend/app/modules/identity/service.py` — Remove residual secret string

---

### Task 1: Quick Fixes (I2, I3, I4, I6)

**Files:**
- Modify: `apps/backend-rag/backend/app/core/config.py:397,437`
- Modify: `apps/backend-rag/backend/app/deps/auth.py:89-94`
- Modify: `apps/backend-rag/backend/app/modules/identity/service.py:31-38`
- Test: `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`

- [ ] **Step 1: Write tests for all 4 quick fixes**

Append to `apps/backend-rag/backend/tests/unit/app/deps/test_auth_hardened.py`:

```python
class TestSprint3QuickFixes:
    """S03-S3: Quick fixes from code review."""

    def test_grace_period_removed(self):
        """jwt_grace_period_days should no longer exist in config."""
        from backend.app.core.config import settings
        assert not hasattr(settings, "jwt_grace_period_days")

    def test_scraper_key_no_hardcoded_default(self):
        """intel_scraper_api_key should not default to dev_scraper_key."""
        import inspect
        from backend.app.core.config import Settings
        source = inspect.getsource(Settings)
        assert 'default="dev_scraper_key"' not in source

    def test_identity_service_no_residual_secret(self):
        """identity/service.py should not contain known weak secret strings."""
        import inspect
        from backend.app.modules.identity.service import IdentityService
        source = inspect.getsource(IdentityService.__init__)
        assert "zantara_default_secret_key_2025" not in source

    def test_type_claim_validated_for_new_tokens(self):
        """Tokens with type=access should pass. Tokens without type should also pass (backward compat)."""
        from backend.app.deps.auth import get_current_user
        from backend.app.core.config import settings

        # Token WITH type=access — should pass
        now = datetime.now(timezone.utc)
        token_with_type = jose_jwt.encode(
            {"sub": "u1", "email": "t@b.com", "role": "admin",
             "exp": now + timedelta(hours=1), "type": "access"},
            settings.jwt_secret_key, algorithm="HS256",
        )
        request = MagicMock(); request.state = MagicMock(spec=[])
        creds = MagicMock(); creds.credentials = token_with_type
        user = get_current_user(request, creds)
        assert user["email"] == "t@b.com"

    def test_type_claim_rejects_refresh_tokens(self):
        """Tokens with type=refresh should be rejected."""
        from backend.app.deps.auth import get_current_user
        from backend.app.core.config import settings
        from fastapi import HTTPException

        now = datetime.now(timezone.utc)
        token_refresh = jose_jwt.encode(
            {"sub": "u1", "email": "t@b.com", "role": "admin",
             "exp": now + timedelta(hours=1), "type": "refresh"},
            settings.jwt_secret_key, algorithm="HS256",
        )
        request = MagicMock(); request.state = MagicMock(spec=[])
        creds = MagicMock(); creds.credentials = token_refresh
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request, creds)
        assert exc_info.value.status_code == 401

    def test_type_claim_absent_passes_backward_compat(self):
        """Pre-S03 tokens without type claim should still pass."""
        from backend.app.deps.auth import get_current_user
        from backend.app.core.config import settings

        now = datetime.now(timezone.utc)
        token_no_type = jose_jwt.encode(
            {"sub": "u1", "email": "t@b.com", "role": "admin",
             "exp": now + timedelta(hours=1)},
            settings.jwt_secret_key, algorithm="HS256",
        )
        request = MagicMock(); request.state = MagicMock(spec=[])
        creds = MagicMock(); creds.credentials = token_no_type
        user = get_current_user(request, creds)
        assert user["email"] == "t@b.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py::TestSprint3QuickFixes -v`
Expected: Multiple FAIL

- [ ] **Step 3: Fix I2 — Remove jwt_grace_period_days**

In `apps/backend-rag/backend/app/core/config.py`, delete this line:

```python
    jwt_grace_period_days: int = 7  # S03: grace period when enabling expiry enforcement
```

- [ ] **Step 4: Fix I6 — Remove dev_scraper_key default**

In `apps/backend-rag/backend/app/core/config.py`, replace:

```python
    intel_scraper_api_key: str = Field(
        default="dev_scraper_key",
        description="API key for internal scraper poller. Set via INTEL_SCRAPER_API_KEY env var.",
    )
```

With:

```python
    intel_scraper_api_key: str = Field(
        default="",
        description="API key for internal scraper poller. Set via INTEL_SCRAPER_API_KEY env var.",
    )
```

- [ ] **Step 5: Fix I4 — Remove residual secret in identity/service.py**

In `apps/backend-rag/backend/app/modules/identity/service.py`, replace lines 31-38:

```python
        # Warn if using default or empty secret key
        if (
            not self.jwt_secret
            or self.jwt_secret == "zantara_default_secret_key_2025_change_in_production"
        ):
            logger.warning(
                "⚠️  Using default or empty JWT secret key. This is insecure for production!",
            )
```

With:

```python
        # Warn if using empty secret key
        if not self.jwt_secret:
            logger.warning(
                "⚠️  Empty JWT secret key. Set JWT_SECRET_KEY env var.",
            )
```

- [ ] **Step 6: Fix I3 — Validate type claim in deps/auth.py**

In `apps/backend-rag/backend/app/deps/auth.py`, find (inside get_current_user, after payload decode):

```python
        user_email = payload.get("email") or payload.get("sub")
```

Add BEFORE that line:

```python
        # S03-S3: Reject non-access tokens (e.g. refresh tokens)
        # Skip check if type claim absent (backward compat with pre-S03 tokens)
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

```

- [ ] **Step 7: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py::TestSprint3QuickFixes -v`
Expected: All PASS

- [ ] **Step 8: Verify import chain + existing tests**

Run: `cd apps/backend-rag && python -c "from backend.app.dependencies import get_current_user; print('OK')" && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py -v --tb=short 2>&1 | tail -5`

- [ ] **Step 9: Commit**

```bash
cd apps/backend-rag && git add backend/app/core/config.py backend/app/deps/auth.py backend/app/modules/identity/service.py backend/tests/unit/app/deps/test_auth_hardened.py
git commit -m "sec(auth): S03-S3 quick fixes — type claim validation, remove dead config and residual secrets"
```

---

### Task 2: BOLA Fix — crm_portal_integration.py

**Files:**
- Modify: `apps/backend-rag/backend/app/routers/crm_portal_integration.py:423-434`

- [ ] **Step 1: Add verify_client_access import**

In `apps/backend-rag/backend/app/routers/crm_portal_integration.py`, find line 23:

```python
from backend.app.utils.crm_utils import is_crm_admin
```

Replace with:

```python
from backend.app.utils.crm_utils import is_crm_admin, verify_client_access
```

- [ ] **Step 2: Add ownership check before INSERT**

Find the `send_message_to_client` function (line 423). Inside the `try` block, after `async with db_pool.acquire() as conn:` (line 434) and BEFORE the INSERT query, add:

```python
            # S03-S3: BOLA fix — verify caller has access to this client
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)

```

- [ ] **Step 3: Verify import chain**

Run: `cd apps/backend-rag && python -c "from backend.app.routers.crm_portal_integration import router; print('OK')"`

- [ ] **Step 4: Commit**

```bash
cd apps/backend-rag && git add backend/app/routers/crm_portal_integration.py
git commit -m "sec(auth): S03-S3 BOLA fix — verify_client_access on portal message endpoint"
```

---

### Task 3: Brute Force Detection Service

**Files:**
- Create: `apps/backend-rag/backend/services/security/brute_force.py`
- Create: `apps/backend-rag/backend/tests/unit/services/security/test_brute_force.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/backend-rag/backend/tests/unit/services/security/test_brute_force.py`:

```python
"""Tests for brute force detection — S03 Sprint 3."""

from unittest.mock import AsyncMock

import pytest


class TestBruteForceDetection:
    """Test login brute force detection via Redis."""

    @pytest.mark.asyncio
    async def test_record_failure_increments_counter(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis)
        await detector.record_failure("1.2.3.4", "user@test.com")
        mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_blocked_returns_false_under_threshold(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        detector = BruteForceDetector(redis_client=mock_redis)
        result = await detector.is_blocked("1.2.3.4", "user@test.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_blocked_returns_true_when_blocked(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        detector = BruteForceDetector(redis_client=mock_redis)
        result = await detector.is_blocked("1.2.3.4", "user@test.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_record_failure_blocks_after_threshold(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=6)  # over threshold of 5
        mock_redis.expire = AsyncMock()
        mock_redis.setex = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis, max_failures=5)
        await detector.record_failure("1.2.3.4", "user@test.com")
        mock_redis.setex.assert_called_once()  # block key set

    @pytest.mark.asyncio
    async def test_graceful_on_redis_unavailable(self):
        from backend.services.security.brute_force import BruteForceDetector
        detector = BruteForceDetector(redis_client=None)
        result = await detector.is_blocked("1.2.3.4", "user@test.com")
        assert result is False  # fail-open

    @pytest.mark.asyncio
    async def test_clear_on_success(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis)
        await detector.clear_on_success("1.2.3.4", "user@test.com")
        mock_redis.delete.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/security/test_brute_force.py -v`

- [ ] **Step 3: Create the service**

Create `apps/backend-rag/backend/services/security/brute_force.py`:

```python
"""
Brute force detection for login endpoint (S03 Sprint 3).

Uses IP+email pair to avoid NAT/coworking collateral blocking.
5 failures in 5 minutes per IP+email → 429 for 5 minutes.
Fail-open: Redis down = no blocking.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_MAX_FAILURES = 5
DEFAULT_WINDOW_SECONDS = 300  # 5 minutes
DEFAULT_BLOCK_SECONDS = 300  # 5 minutes


class BruteForceDetector:
    """
    Brute force detection using Redis.

    Key pattern: auth_fail:{ip}:{email} — counter with TTL
    Block pattern: auth_block:{ip}:{email} — block flag with TTL
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        max_failures: int = DEFAULT_MAX_FAILURES,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        block_seconds: int = DEFAULT_BLOCK_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._block_seconds = block_seconds

    def _fail_key(self, ip: str, email: str) -> str:
        return f"auth_fail:{ip}:{email.lower()}"

    def _block_key(self, ip: str, email: str) -> str:
        return f"auth_block:{ip}:{email.lower()}"

    async def is_blocked(self, ip: str, email: str) -> bool:
        """Check if IP+email pair is currently blocked."""
        if not self._redis:
            return False
        try:
            return bool(await self._redis.exists(self._block_key(ip, email)))
        except Exception as e:
            logger.warning(f"S03: Brute force check failed (fail-open): {e}")
            return False

    async def record_failure(self, ip: str, email: str) -> None:
        """Record a login failure. Blocks if threshold exceeded."""
        if not self._redis:
            return
        try:
            key = self._fail_key(ip, email)
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, self._window_seconds)

            if count > self._max_failures:
                await self._redis.setex(
                    self._block_key(ip, email),
                    self._block_seconds,
                    f"brute_force:{count}_attempts",
                )
                logger.warning(
                    f"S03: Brute force block activated ip={ip} email={email} "
                    f"attempts={count}"
                )
        except Exception as e:
            logger.warning(f"S03: Brute force record failed: {e}")

    async def clear_on_success(self, ip: str, email: str) -> None:
        """Clear failure counter on successful login."""
        if not self._redis:
            return
        try:
            await self._redis.delete(
                self._fail_key(ip, email),
                self._block_key(ip, email),
            )
        except Exception as e:
            logger.warning(f"S03: Brute force clear failed: {e}")
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/security/test_brute_force.py -v`
Expected: 6/6 PASS

- [ ] **Step 5: Commit**

```bash
cd apps/backend-rag && git add backend/services/security/brute_force.py backend/tests/unit/services/security/test_brute_force.py
git commit -m "feat(auth): S03-S3 brute force detection (IP+email, 5 fail/5min → 429)"
```

---

### Task 4: Wire Brute Force into Login Endpoint

**Files:**
- Modify: `apps/backend-rag/backend/app/routers/auth.py`

- [ ] **Step 1: Add brute force check at login start**

In `apps/backend-rag/backend/app/routers/auth.py`, find the `login` function. Inside the try block, BEFORE the database query (before `async with db_pool.acquire() as conn:`), add:

```python
        # S03-S3: Brute force detection
        try:
            from backend.core.redis_manager import RedisManager
            from backend.services.security.brute_force import BruteForceDetector

            redis_client = RedisManager.get_instance().get_async_client()
            brute_force = BruteForceDetector(redis_client=redis_client)

            if await brute_force.is_blocked(client_ip or "", request.email):
                logger.warning(f"S03: Login blocked (brute force) ip={client_ip} email={request.email}")
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed attempts. Please try again later.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.debug(f"S03: Brute force check skipped: {e}")

```

Also, after a SUCCESSFUL login (after `await conn.execute("UPDATE team_members SET last_login..."`), add:

```python
            # S03-S3: Clear brute force counter on success
            try:
                await brute_force.clear_on_success(client_ip or "", request.email)
            except Exception:
                pass

```

And after EACH failed login (where `await audit_service.log_auth_event(... action="failed_login" ...)` is called), add:

```python
                try:
                    await brute_force.record_failure(client_ip or "", request.email)
                except Exception:
                    pass
```

There are 3 `failed_login` sites: "User not found" (line ~178), "Account inactive" (line ~189), "Invalid PIN" (line ~201). Add `record_failure` after each.

- [ ] **Step 2: Verify import chain**

Run: `cd apps/backend-rag && python -c "from backend.app.dependencies import get_current_user; print('OK')"`

- [ ] **Step 3: Commit**

```bash
cd apps/backend-rag && git add backend/app/routers/auth.py
git commit -m "feat(auth): S03-S3 wire brute force detection into login endpoint"
```

---

### Task 5: PDP Consent Log Migration

**Files:**
- Create: `apps/backend-rag/backend/migrations/migration_091_client_consent_log.py`

- [ ] **Step 1: Write the migration**

Create `apps/backend-rag/backend/migrations/migration_091_client_consent_log.py`:

```python
"""
Migration 091: Client consent log for PDP Act (UU 27/2022) compliance.

Append-only, immutable table tracking per-purpose consent grants and revocations.
Required by Art. 20 (granular consent) and Art. 31 (processing records).
"""

import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "091_client_consent_log"
DESCRIPTION = "S03-S3: Create client_consent_log table for PDP Act compliance"


async def check_if_applied(conn) -> bool:
    result = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'client_consent_log')"
    )
    return result


async def apply(conn) -> None:
    logger.info(f"Applying migration {MIGRATION_ID}: {DESCRIPTION}")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS client_consent_log (
            id BIGSERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id),
            purpose_key VARCHAR(100) NOT NULL,
            action VARCHAR(20) NOT NULL CHECK (action IN ('granted', 'revoked')),
            legal_basis VARCHAR(50) DEFAULT 'consent',
            policy_version VARCHAR(20),
            captured_by VARCHAR(255),
            channel VARCHAR(50),
            ip_address INET,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consent_log_client ON client_consent_log(client_id, purpose_key, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consent_log_active ON client_consent_log(client_id, purpose_key) WHERE action = 'granted'"
    )

    await conn.execute("""
        INSERT INTO migration_history (migration_id, description, applied_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (migration_id) DO NOTHING
    """, MIGRATION_ID, DESCRIPTION)

    logger.info(f"✅ Migration {MIGRATION_ID} applied successfully")


async def rollback(conn) -> None:
    logger.info(f"Rolling back migration {MIGRATION_ID}")
    await conn.execute("DROP TABLE IF EXISTS client_consent_log CASCADE")
    await conn.execute(
        "DELETE FROM migration_history WHERE migration_id = $1", MIGRATION_ID
    )
    logger.info(f"✅ Migration {MIGRATION_ID} rolled back")
```

- [ ] **Step 2: Verify syntax**

Run: `cd apps/backend-rag && python -c "import backend.migrations.migration_091_client_consent_log; print('OK')"`

- [ ] **Step 3: Commit**

```bash
cd apps/backend-rag && git add backend/migrations/migration_091_client_consent_log.py
git commit -m "feat(auth): S03-S3 migration 091 — client_consent_log table (PDP Act Art.20)"
```

---

### Task 6: API Key Permission Scoping

**Files:**
- Create: `apps/backend-rag/backend/app/deps/permissions.py`
- Create: `apps/backend-rag/backend/tests/unit/app/deps/test_permissions.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/backend-rag/backend/tests/unit/app/deps/test_permissions.py`:

```python
"""Tests for permission-based auth dependencies — S03 Sprint 3."""

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock


class TestVerifyPermission:
    """Test API key permission scoping."""

    def test_wildcard_permission_grants_all(self):
        from backend.app.deps.permissions import check_permission
        user = {"permissions": ["*"], "role": "admin"}
        assert check_permission(user, "crm:write") is True

    def test_exact_permission_match(self):
        from backend.app.deps.permissions import check_permission
        user = {"permissions": ["crm:read", "crm:write"], "role": "user"}
        assert check_permission(user, "crm:write") is True

    def test_missing_permission_denied(self):
        from backend.app.deps.permissions import check_permission
        user = {"permissions": ["crm:read"], "role": "user"}
        assert check_permission(user, "crm:write") is False

    def test_admin_role_grants_all(self):
        from backend.app.deps.permissions import check_permission
        user = {"permissions": [], "role": "admin"}
        assert check_permission(user, "anything") is True

    def test_empty_permissions_denied(self):
        from backend.app.deps.permissions import check_permission
        user = {"permissions": [], "role": "user"}
        assert check_permission(user, "crm:read") is False

    def test_no_permissions_key_denied(self):
        from backend.app.deps.permissions import check_permission
        user = {"role": "user"}
        assert check_permission(user, "crm:read") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_permissions.py -v`

- [ ] **Step 3: Create the permissions module**

Create `apps/backend-rag/backend/app/deps/permissions.py`:

```python
"""
Permission-based authorization dependencies (S03 Sprint 3).

Provides fine-grained permission checks for API key scoped access
and security-sensitive endpoints (e.g., breach notification).
"""

import logging
from typing import Any

from fastapi import Depends, HTTPException

from backend.app.deps.auth import get_current_user

logger = logging.getLogger(__name__)


def check_permission(user: dict[str, Any], required: str) -> bool:
    """
    Check if user has a specific permission.

    Admin role always has all permissions.
    Wildcard '*' in permissions grants all.

    Args:
        user: User context dict (from get_current_user)
        required: Required permission string (e.g., 'crm:write')

    Returns:
        True if user has the permission, False otherwise
    """
    if user.get("role") == "admin":
        return True

    permissions = user.get("permissions", [])
    if "*" in permissions:
        return True

    return required in permissions


def require_permission(required: str):
    """
    FastAPI dependency factory for permission-gated endpoints.

    Usage:
        @router.post("/breach-notify")
        async def notify(user=Depends(require_permission("security.breach_notify"))):
            ...
    """
    def _check(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not check_permission(user, required):
            logger.warning(
                f"S03: Permission denied — user={user.get('email')} "
                f"required={required} has={user.get('permissions', [])}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission required: {required}",
            )
        return user
    return _check
```

- [ ] **Step 4: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_permissions.py -v`
Expected: 6/6 PASS

- [ ] **Step 5: Commit**

```bash
cd apps/backend-rag && git add backend/app/deps/permissions.py backend/tests/unit/app/deps/test_permissions.py
git commit -m "feat(auth): S03-S3 permission-based auth dependencies for API key scoping"
```

---

### Task 7: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Import chain**

Run: `cd apps/backend-rag && python -c "from backend.app.dependencies import get_current_user; print('OK')"`

- [ ] **Step 2: All S03 tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/app/deps/test_auth_hardened.py backend/tests/unit/app/services/test_api_key_db.py backend/tests/unit/services/security/ backend/tests/unit/app/deps/test_permissions.py -v 2>&1 | tail -40`

- [ ] **Step 3: Core RAG tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no`

- [ ] **Step 4: Feature flags**

Run: `cd apps/backend-rag && python -c "from backend.app.core.config import settings; print(f'jwt_enforce_expiry={settings.jwt_enforce_expiry}, enable_token_revocation={settings.enable_token_revocation}'); assert not hasattr(settings, 'jwt_grace_period_days'), 'grace_period should be removed'"`

- [ ] **Step 5: Git log S03 Sprint 3**

Run: `git log --oneline --grep="S03-S3" | head -10`

Expected commits (newest first):
1. `feat(auth): S03-S3 permission-based auth dependencies`
2. `feat(auth): S03-S3 migration 091 — client_consent_log`
3. `feat(auth): S03-S3 wire brute force into login`
4. `feat(auth): S03-S3 brute force detection`
5. `sec(auth): S03-S3 BOLA fix — verify_client_access`
6. `sec(auth): S03-S3 quick fixes — type claim, dead config, secrets`
