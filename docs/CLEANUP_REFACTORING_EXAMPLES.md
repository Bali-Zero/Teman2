# 🔧 Refactoring Examples: app/routers/*

This document provides concrete code examples for the refactoring plan outlined in `CLEANUP_REPORT_ROUTERS.md`.

---

## Example 1: Migrating from Sync to Async DB (P0)

### Before: `crm_clients.py`

```python
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get PostgreSQL connection"""
    database_url = settings.database_url
    if not database_url:
        raise Exception("DATABASE_URL environment variable not set")
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

@router.post("/", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    created_by: str = Query(..., description="Team member email creating this client"),
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO clients (
                full_name, email, phone, whatsapp, nationality, passport_number,
                client_type, assigned_to, address, notes, tags, custom_fields,
                first_contact_date, created_by, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING *
        """,
            (
                client.full_name,
                client.email,
                client.phone,
                client.whatsapp,
                client.nationality,
                client.passport_number,
                client.client_type,
                client.assigned_to,
                client.address,
                client.notes,
                Json(client.tags),
                Json(client.custom_fields),
                datetime.now(),
                created_by,
                "active",
            ),
        )

        new_client = cursor.fetchone()
        conn.commit()

        cursor.close()
        conn.close()

        logger.info(f"✅ Created client: {client.full_name} (ID: {new_client['id']})")
        return ClientResponse(**new_client)

    except psycopg2.IntegrityError as e:
        logger.error(f"❌ Integrity error creating client: {e}")
        raise HTTPException(
            status_code=400, detail="Client with this email or phone already exists"
        ) from e
    except Exception as e:
        logger.error(f"❌ Failed to create client: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
```

### After: Using Async Pool

```python
import asyncpg
from fastapi import Depends
from app.dependencies import get_database_pool

@router.post("/", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    created_by: str = Query(..., description="Team member email creating this client"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Create a new client

    - **full_name**: Client's full name (required)
    - **email**: Email address (optional but recommended)
    - **phone**: Phone number
    - **whatsapp**: WhatsApp number (can be same as phone)
    - **nationality**: Client's nationality
    - **passport_number**: Passport number
    - **assigned_to**: Team member email to assign client to
    - **tags**: Array of tags (e.g., ['vip', 'urgent'])
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO clients (
                    full_name, email, phone, whatsapp, nationality, passport_number,
                    client_type, assigned_to, address, notes, tags, custom_fields,
                    first_contact_date, created_by, status
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
                )
                RETURNING *
                """,
                client.full_name,
                client.email,
                client.phone,
                client.whatsapp,
                client.nationality,
                client.passport_number,
                client.client_type,
                client.assigned_to,
                client.address,
                client.notes,
                client.tags,  # asyncpg handles JSON automatically
                client.custom_fields,
                datetime.now(),
                created_by,
                "active",
            )

            if not row:
                raise HTTPException(status_code=500, detail="Failed to create client")

            new_client = dict(row)
            logger.info(f"✅ Created client: {client.full_name} (ID: {new_client['id']})")
            return ClientResponse(**new_client)

    except asyncpg.UniqueViolationError as e:
        logger.error(f"❌ Integrity error creating client: {e}")
        raise HTTPException(
            status_code=400, detail="Client with this email or phone already exists"
        ) from e
    except asyncpg.PostgresError as e:
        logger.error(f"❌ Database error creating client: {e}")
        raise HTTPException(status_code=503, detail="Database error") from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
```

**Key Changes**:
1. ✅ Uses `asyncpg` instead of `psycopg2`
2. ✅ Uses connection pool via dependency injection
3. ✅ Uses `$1, $2, ...` parameterized queries (asyncpg syntax)
4. ✅ Proper exception handling (asyncpg-specific exceptions)
5. ✅ Context manager ensures connection cleanup
6. ✅ No manual cursor management needed

---

## Example 2: Extracting Authentication (P1)

### Before: Duplicated in Multiple Files

**In `conversations.py`**:
```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Validate JWT token and return current user.
    Required for all conversation endpoints to prevent user spoofing.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        from jose import JWTError, jwt
        from app.core.config import settings

        token = credentials.credentials
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])

        user_email = payload.get("sub") or payload.get("email")
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token: missing user identifier")

        return {
            "email": user_email,
            "user_id": payload.get("user_id", user_email),
            "role": payload.get("role", "user"),
            "permissions": payload.get("permissions", []),
        }
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed") from e
```

**In `agents.py`** (same code duplicated):
```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    # ... identical code ...
```

### After: Centralized in `app/dependencies.py`

**Add to `app/dependencies.py`**:
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """
    Validate JWT token and return current user.

    Used by all protected endpoints to extract authenticated user information.

    Returns:
        dict: User information with keys: email, user_id, role, permissions

    Raises:
        HTTPException: 401 if authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])

        user_email = payload.get("sub") or payload.get("email")
        if not user_email:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user identifier"
            )

        return {
            "email": user_email,
            "user_id": payload.get("user_id", user_email),
            "role": payload.get("role", "user"),
            "permissions": payload.get("permissions", []),
        }
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail="Authentication failed") from e
```

**Update `conversations.py`**:
```python
from app.dependencies import get_current_user

# Remove the duplicate function, use the one from dependencies
# All endpoints already use Depends(get_current_user), so no changes needed!
```

**Update `agents.py`**:
```python
from app.dependencies import get_current_user

# Same - just import instead of defining
```

**Key Changes**:
1. ✅ Single source of truth for authentication
2. ✅ Consistent behavior across all routers
3. ✅ Easier to update security logic
4. ✅ Better error messages and logging

---

## Example 3: Fixing Connection Leaks (P1)

### Before: Potential Leak

```python
@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int):
    """Get client by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
        client = cursor.fetchone()

        cursor.close()
        conn.close()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        return ClientResponse(**client)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get client: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
```

**Problem**: If `cursor.fetchone()` raises an exception, `cursor.close()` and `conn.close()` are never called.

### After: Proper Cleanup

**Option A: Using Context Manager (Recommended)**
```python
@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get client by ID"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM clients WHERE id = $1", client_id
            )

            if not row:
                raise HTTPException(status_code=404, detail="Client not found")

            return ClientResponse(**dict(row))

    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"❌ Database error getting client {client_id}: {e}")
        raise HTTPException(status_code=503, detail="Database error") from e
    except Exception as e:
        logger.error(f"❌ Failed to get client {client_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
```

**Option B: Using Try/Finally (If context manager not available)**
```python
@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int):
    """Get client by ID"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
        client = cursor.fetchone()

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        return ClientResponse(**client)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get client: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

**Key Changes**:
1. ✅ Context manager ensures cleanup even on exceptions
2. ✅ Proper exception handling hierarchy
3. ✅ No connection leaks

---

## Example 4: Standardizing Error Handling (P1)

### Before: Inconsistent Error Handling

```python
# File 1: Generic exception
except Exception as e:
    logger.error(f"Error: {e}")
    raise HTTPException(status_code=500, detail=str(e))

# File 2: Specific exception
except psycopg2.IntegrityError as e:
    raise HTTPException(status_code=400, detail="Duplicate entry")
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

# File 3: No exception handling
# Just let it crash
```

### After: Standardized Error Handler

**Create `app/utils/error_handlers.py`**:
```python
"""
Standardized error handling utilities for routers.
"""
import logging
from fastapi import HTTPException
import asyncpg

logger = logging.getLogger(__name__)

def handle_database_error(e: Exception) -> HTTPException:
    """
    Handle database errors consistently across all routers.

    Args:
        e: The exception that occurred

    Returns:
        HTTPException: Appropriate HTTP exception with user-friendly message
    """
    if isinstance(e, asyncpg.UniqueViolationError):
        logger.warning(f"Unique constraint violation: {e}")
        return HTTPException(
            status_code=400,
            detail="A record with this information already exists"
        )

    if isinstance(e, asyncpg.ForeignKeyViolationError):
        logger.warning(f"Foreign key violation: {e}")
        return HTTPException(
            status_code=400,
            detail="Referenced record does not exist"
        )

    if isinstance(e, asyncpg.CheckViolationError):
        logger.warning(f"Check constraint violation: {e}")
        return HTTPException(
            status_code=400,
            detail="Invalid data provided"
        )

    if isinstance(e, asyncpg.PostgresError):
        logger.error(f"Database error: {e}", exc_info=True)
        return HTTPException(
            status_code=503,
            detail="Database service temporarily unavailable"
        )

    # Generic fallback
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail="Internal server error"
    )
```

**Use in routers**:
```python
from app.utils.error_handlers import handle_database_error

@router.post("/", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    created_by: str = Query(...),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(...)
            return ClientResponse(**dict(row))

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise handle_database_error(e)  # Standardized handling
```

**Key Changes**:
1. ✅ Consistent error messages
2. ✅ Proper HTTP status codes
3. ✅ No information leakage
4. ✅ Easier to maintain

---

## Example 5: Adding Input Validation (P1)

### Before: No Validation

```python
@router.get("/{client_id}")
async def get_client(client_id: int):
    # What if client_id is negative? Or 0?
    # What if it's too large?
    # ...
```

### After: With Validation

```python
from fastapi import Path
from pydantic import Field

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int = Path(
        ...,
        gt=0,  # Greater than 0
        description="Client ID (must be positive)",
        example=123
    ),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get client by ID

    Args:
        client_id: Positive integer client ID

    Returns:
        ClientResponse: Client information

    Raises:
        HTTPException: 404 if client not found
    """
    # ... implementation ...
```

**For Query Parameters**:
```python
@router.get("/")
async def list_clients(
    status: str | None = Query(
        None,
        regex="^(active|inactive|prospect)$",  # Only allow valid values
        description="Filter by status"
    ),
    limit: int = Query(
        50,
        ge=1,  # Greater than or equal to 1
        le=200,  # Less than or equal to 200
        description="Max results to return"
    ),
    offset: int = Query(
        0,
        ge=0,  # Non-negative
        description="Offset for pagination"
    ),
):
    # ... implementation ...
```

**Key Changes**:
1. ✅ Input validation at API level
2. ✅ Clear error messages
3. ✅ Prevents invalid data from reaching business logic

---

## Example 6: Adding Caching (P2)

### Before: No Caching

```python
@router.get("/stats/overview")
async def get_clients_stats():
    """Get overall client statistics"""
    try:
        conn = get_db_connection()
        # ... expensive queries ...
        return stats
    finally:
        conn.close()
```

### After: With Redis Caching

```python
from core.cache import cached
from datetime import timedelta

@router.get("/stats/overview")
@cached(ttl=300, prefix="clients_stats")  # Cache for 5 minutes
async def get_clients_stats(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get overall client statistics

    Performance: Cached for 5 minutes to reduce database load.
    """
    try:
        async with db_pool.acquire() as conn:
            # ... expensive queries ...
            return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
```

**Key Changes**:
1. ✅ Reduces database load
2. ✅ Faster response times
3. ✅ Simple decorator pattern

---

## Summary Checklist

When refactoring a router file:

- [ ] Replace `psycopg2` with `asyncpg`
- [ ] Use `Depends(get_database_pool)` for database connections
- [ ] Use context managers (`async with pool.acquire()`)
- [ ] Import `get_current_user` from `app.dependencies`
- [ ] Use standardized error handling
- [ ] Add input validation with Pydantic
- [ ] Add proper type hints
- [ ] Add docstrings
- [ ] Use try/finally or context managers for cleanup
- [ ] Add caching for expensive operations
- [ ] Extract constants for magic numbers/strings
- [ ] Add logging consistently

---

**Next Steps**: Start with Phase 1 (P0 fixes) and work through each phase systematically.


















