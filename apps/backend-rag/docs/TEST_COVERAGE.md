# Test Coverage Documentation

## Overview

This document describes the test coverage system for the Nuzantara Backend RAG application.

## Coverage Test Script

### Location
`apps/backend-rag/scripts/run_coverage_test.sh`

### Usage

```bash
# Run all tests with coverage
./apps/backend-rag/scripts/run_coverage_test.sh

# Run only unit tests
./apps/backend-rag/scripts/run_coverage_test.sh unit

# Run only API tests
./apps/backend-rag/scripts/run_coverage_test.sh api

# Run only integration tests
./apps/backend-rag/scripts/run_coverage_test.sh integration

# Pass additional pytest arguments
./apps/backend-rag/scripts/run_coverage_test.sh unit -k "test_feedback"
```

### Features

- **Coverage Reporting**: Generates HTML and XML coverage reports
- **Minimum Threshold**: 75% coverage required (configurable)
- **Test Filtering**: Filter by test type (unit/api/integration)
- **Multiple Formats**: Terminal, HTML, and XML reports

### Output

After running the script, you'll find:

- **Terminal Output**: Coverage summary with missing lines
- **HTML Report**: `htmlcov/index.html` - Interactive coverage report
- **XML Report**: `coverage.xml` - Machine-readable coverage data

### Viewing Reports

```bash
# Open HTML report in browser
open apps/backend-rag/htmlcov/index.html

# Or use Python's HTTP server
cd apps/backend-rag && python3 -m http.server 8000
# Then visit http://localhost:8000/htmlcov/index.html
```

## Coverage Configuration

### Configuration File
`.coveragerc` in `apps/backend-rag/`

### Key Settings

- **Source**: `backend` directory
- **Omit**: Tests, migrations, cache files, virtual environments
- **Exclude Lines**: Abstract methods, type checking blocks, etc.

### Minimum Coverage

Currently set to **75%**. To change:

1. Edit `apps/backend-rag/scripts/run_coverage_test.sh`
2. Modify `--cov-fail-under=75` to desired percentage

## Test Structure

### Test Categories

- **Unit Tests** (`tests/unit/`): 239 files
  - Fast, isolated tests
  - Mock external dependencies
  - Test individual functions/classes

- **Integration Tests** (`tests/integration/`): 139 files
  - Test component interactions
  - Use real services where appropriate
  - End-to-end workflows

- **API Tests** (`tests/api/`): 120 files
  - Test HTTP endpoints
  - Verify request/response handling
  - Authentication and authorization

- **Performance Tests** (`tests/performance/`): 1 file
  - Benchmark critical paths
  - Load testing

### Test Naming Conventions

- `test_*.py`: Standard test files
- `*_95.py`: Coverage-specific tests (targeting 95% coverage)
- `*_coverage.py`: Coverage-focused test suites
- `*_comprehensive.py`: Comprehensive test suites

## Running Tests Manually

### Using pytest directly

```bash
# All tests
pytest apps/backend-rag/tests/

# With coverage
pytest apps/backend-rag/tests/ --cov=backend --cov-report=html

# Specific test file
pytest apps/backend-rag/tests/unit/test_feedback.py

# Specific test function
pytest apps/backend-rag/tests/unit/test_feedback.py::test_submit_feedback

# With verbose output
pytest apps/backend-rag/tests/ -v

# Stop on first failure
pytest apps/backend-rag/tests/ -x
```

## Coverage Best Practices

### 1. Write Tests for New Code

When adding new features:
- Write unit tests for core logic
- Add integration tests for workflows
- Include API tests for endpoints

### 2. Maintain Coverage Threshold

- Keep coverage above 75%
- Aim for 90%+ on critical paths
- Don't sacrifice quality for coverage percentage

### 3. Review Coverage Reports

Regularly check:
- Which files have low coverage
- Which functions are untested
- Dead code that can be removed

### 4. Exclude Appropriate Code

Some code doesn't need coverage:
- Abstract base classes
- Type checking blocks
- Debug/development code
- Migration scripts

## Troubleshooting

### Low Coverage

If coverage is below threshold:

1. Check which files have low coverage
2. Review untested functions
3. Add tests for missing coverage
4. Verify coverage configuration excludes appropriate code

### Import Errors

Some tests may have import errors after refactoring:

1. Check if service paths have changed
2. Update imports to new module structure
3. Verify `pythonpath` in `pytest.ini`

### Slow Tests

If tests are running slowly:

1. Use `-k` to run specific tests
2. Run tests in parallel: `pytest -n auto`
3. Use markers to skip slow tests: `pytest -m "not slow"`

## Continuous Improvement

### Regular Cleanup

- Remove obsolete test files
- Consolidate duplicate tests
- Update tests after refactoring
- Remove skeleton/placeholder tests

### Monitoring

- Track coverage trends over time
- Set coverage goals per module
- Review coverage reports in PRs
- Document coverage decisions

## Related Documentation

- `pytest.ini`: Pytest configuration
- `.coveragerc`: Coverage configuration
- `pyproject.toml`: Project configuration and tool settings

