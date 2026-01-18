# Test Fix Report - 2026-01-18

## Overview
An analysis of the failing test suite (~300 failures) revealed two primary categories of issues:
1.  **Unit Test Failures:** Caused by `ImportError` or `ModuleNotFoundError` when tests imported modules with heavy dependencies (e.g., `qdrant_client` -> `numpy`, or `backend.services.intel`) that were not properly mocked.
2.  **Integration Test Failures:** Caused by the inability to spin up Docker containers (PostgreSQL, Qdrant) in the current environment, leading to connection errors.

## Fixes Implemented

### 1. Fixed `tests/unit/app/routers/test_intel_coverage.py`
**Issue:** The test crashed with `ModuleNotFoundError: No module named 'numpy._typing._char_codes'` and other import errors because it triggered the import of `backend.app.dependencies` and `backend.services.intel`, which loaded the real `qdrant_client` (incompatible with the environment's numpy) and other unmocked services.

**Fix:**
*   Aggressively mocked `sys.modules` for:
    *   `backend.app.dependencies`
    *   `backend.services.intel` (and its classes: `IntelClassificationService`, etc.)
    *   `backend.app.metrics`
    *   `backend.app.utils.internal_api_auth`
*   Updated `_make_client` helper to retrieve `get_current_user` from the mocked `sys.modules` instead of importing it directly.

**Result:** All 7 tests in this file now **PASS**.

### 2. Fixed `tests/unit/core/test_qdrant_db_95_coverage.py`
**Issue:** The test crashed with `ModuleNotFoundError` for `numpy._typing._char_codes` because it imported the real `qdrant_client` which has a version mismatch with `numpy`.

**Fix:**
*   Mocked `numpy`, `numpy._typing`, `numpy._typing._char_codes`, and `qdrant_client` in `sys.modules` **before** importing the `qdrant_db` module under test.

**Result:** All 48 tests in this file now **PASS**.

## Remaining Issues & Recommendations

### Integration Tests
The integration tests in `tests/integration/` rely on `testcontainers` to spin up Docker containers. In the current environment, this fails or falls back to empty/invalid `DATABASE_URL`s.

**Recommendation:**
*   **Local Dev:** Ensure Docker is running.
*   **CI/CD:** Ensure the runner has Docker-in-Docker capability.
*   **Refactor:** For environments without Docker, implement a `pytest` marker (e.g., `@pytest.mark.docker`) and skip these tests automatically if Docker is unavailable, rather than failing with obscure errors. The current `conftest.py` attempts this but fails to catch all import-time side effects.

### Unit Tests
Other unit tests likely suffer from similar "Dependency Leakage" issues. The strategy used above (mocking `sys.modules` before import) should be applied to them.

**Next Priority Targets:**
*   `tests/unit/app/routers/test_crm_clients_router.py` (Likely similar dependency issues)
*   `tests/unit/services/test_memory_service_postgres.py` (Likely database import issues)
