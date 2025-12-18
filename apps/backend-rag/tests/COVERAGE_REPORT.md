# Backend Test Coverage Report

**Generated:** 2025-01-09

## Summary

| Test Type | Coverage | Lines Covered | Files Covered |
|-----------|----------|---------------|---------------|
| **Unit Tests** | 24.86% | 4,228 / 17,009 | 164 / 187 |
| **Integration Tests** | 29.92% | 5,106 / 17,065 | 174 / 188 |
| **API Tests** | 74.90% | 12,887 / 17,206 | 180 / 188 |
| **Average** | **43.23%** | - | - |

## Detailed Breakdown

### Unit Tests Coverage: 24.86%
- **Lines Covered:** 4,228 / 17,009
- **Files Covered:** 164 / 187 (87.7%)
- **Focus:** Individual components and services
- **Location:** `tests/unit/`
- **Status:** ✅ Coverage calculated
- **Recommendation:** Increase to at least 60% by adding tests for services and utilities

### Integration Tests Coverage: 29.92%
- **Lines Covered:** 5,106 / 17,065
- **Files Covered:** 174 / 188 (92.6%)
- **Focus:** Cross-component interactions and workflows
- **Location:** `tests/integration/`
- **Status:** ✅ Coverage calculated
- **Recommendation:** Increase to at least 50% by testing cross-service interactions

### API Tests Coverage: 74.90%
- **Lines Covered:** 12,887 / 17,206
- **Files Covered:** 180 / 188 (95.7%)
- **Focus:** HTTP endpoints and request/response handling
- **Location:** `tests/api/`
- **Status:** ✅ Coverage calculated
- **Recommendation:** Maintain high coverage, add error scenario tests

## Recommendations

1. **Unit Tests**: Increase coverage from 24.86% to at least 60%
   - Focus on services and utilities with low coverage
   - Add tests for edge cases and error handling

2. **Integration Tests**: Increase coverage from 29.92% to at least 50%
   - Test cross-service interactions
   - Add end-to-end workflow tests

3. **API Tests**: Maintain high coverage (currently 74.90%)
   - Continue comprehensive endpoint testing
   - Add tests for error scenarios and edge cases

## Notes

- Coverage calculated using `pytest-cov`
- Coverage files: `coverage_unit.json`, `coverage_integration.json`, `coverage_api.json`
- Run `pytest` with `--cov` flag to regenerate coverage reports

