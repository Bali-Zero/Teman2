# Testing Strategy for Nuzantara Backend

This document outlines the comprehensive testing strategy for the Nuzantara backend, following the **Testing Pyramid** approach to achieve **95% test coverage**.

## Test Structure

```
tests/
├── unit/              # Fast unit tests with mocks (existing - 3080+ tests)
├── integration/       # Integration tests with real databases
│   ├── conftest.py    # Database fixtures (PostgreSQL, Qdrant)
│   ├── test_search_service_integration.py
│   ├── test_memory_service_integration.py
│   ├── test_memory_vector_integration.py
│   └── test_work_session_integration.py
└── api/               # E2E tests with FastAPI TestClient
    ├── conftest.py    # TestClient fixtures
    ├── test_health_endpoints.py
    └── test_search_endpoints.py
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)
- **Purpose**: Fast, isolated tests with mocks
- **Coverage**: Business logic, edge cases, error handling
- **Run**: `pytest tests/unit -v`
- **Speed**: Very fast (< 1 minute for all tests)
- **Dependencies**: None (all mocked)

### 2. Integration Tests (`tests/integration/`)
- **Purpose**: Test service-database interactions with real databases
- **Coverage**: Database operations, service layer interactions
- **Run**: `pytest tests/integration -v -m integration`
- **Speed**: Moderate (2-5 minutes)
- **Dependencies**: PostgreSQL, Qdrant (via Docker or testcontainers)

### 3. API Tests (`tests/api/`)
- **Purpose**: Test full request/response cycle
- **Coverage**: Endpoints, middleware, authentication, error responses
- **Run**: `pytest tests/api -v -m api`
- **Speed**: Fast (1-2 minutes)
- **Dependencies**: FastAPI TestClient (mocked services)

## Quick Start

### Prerequisites

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-test.txt
   ```

2. **Start test databases** (choose one):

   **Option A: Docker Compose (Recommended)**
   ```bash
   docker-compose -f docker-compose.test.yml up -d
   export DATABASE_URL="postgresql://test:test@localhost:5433/test"
   export QDRANT_URL="http://localhost:6334"
   ```

   **Option B: Testcontainers (Automatic)**
   ```bash
   # Testcontainers will start containers automatically
   # Just ensure Docker is running
   ```

   **Option C: Existing Services**
   ```bash
   export DATABASE_URL="postgresql://user:pass@localhost:5432/test_db"
   export QDRANT_URL="http://localhost:6333"
   ```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only (fast)
pytest tests/unit -v

# Integration tests only
pytest tests/integration -v -m integration

# API tests only
pytest tests/api -v -m api

# Skip slow tests
pytest tests/ -v -m "not slow"

# With coverage
pytest tests/ --cov=backend --cov-report=html --cov-report=term
```

## Test Markers

| Marker | Description | Usage |
|--------|-------------|-------|
| `@pytest.mark.unit` | Unit tests (fast, mocked) | Default |
| `@pytest.mark.integration` | Integration tests (real DB) | `pytest -m integration` |
| `@pytest.mark.api` | API/E2E tests | `pytest -m api` |
| `@pytest.mark.database` | Tests requiring PostgreSQL | `pytest -m database` |
| `@pytest.mark.slow` | Long-running tests | `pytest -m "not slow"` |

## Coverage Goals

- **Unit Tests**: Cover business logic, edge cases, error handling
- **Integration Tests**: Cover database operations, service interactions
- **API Tests**: Cover endpoints, middleware, authentication, error responses

**Target: 95% overall coverage** with all three test types combined.

## Automated Testing

Automated testing configuration available.

The testing pipeline runs:
1. Unit tests (fast, no dependencies)
2. Integration tests (with PostgreSQL and Qdrant services)
3. API tests (with mocked services)

## Fixed Tests

The following previously skipped tests have been converted to integration tests:

- ✅ `test_memory_workflow_complete` → `tests/integration/test_memory_vector_integration.py`
- ✅ `test_connect_no_database_url` → `tests/integration/test_work_session_integration.py`

## Best Practices

1. **Unit Tests**: Fast, isolated, use mocks - run frequently during development
2. **Integration Tests**: Test service-database interactions - run before commits
3. **API Tests**: Test full request/response cycle - run in CI/CD pipeline

4. **Test Data**: Always use test prefixes (`test_*`) for test data
5. **Cleanup**: Tests should clean up after themselves (handled by fixtures)
6. **Isolation**: Each test should be independent and runnable in any order

## Troubleshooting

### Tests Fail with "Connection Refused"
- Ensure Docker containers are running: `docker-compose -f docker-compose.test.yml ps`
- Check ports are not in use: `lsof -i :5433` and `lsof -i :6334`
- Verify environment variables are set correctly

### Tests Fail with "testcontainers not available"
- Install test dependencies: `pip install -r requirements-test.txt`
- Or use Docker Compose instead: `docker-compose -f docker-compose.test.yml up -d`

### Integration Tests Timeout
- Check database connection pool settings
- Verify containers have enough resources
- Increase timeout if needed (see `pytest.ini`)

## Documentation

- **Integration Testing Guide**: See `tests/INTEGRATION_TESTING.md`
- **Skipped Tests**: See `tests/SKIPPED_TESTS.md`
- **Coverage Progress**: See `docs/COVERAGE_PROGRESS.md`

## Next Steps

1. ✅ Create integration test structure
2. ✅ Create API test structure
3. ✅ Fix skipped tests
4. ⏭️ Add more integration tests for uncovered services
5. ⏭️ Add more API tests for all endpoints
6. ⏭️ Achieve 95% coverage target
