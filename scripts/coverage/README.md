# Coverage Automation Scripts

This directory contains scripts for automated test coverage enforcement.

## Scripts

- **`diff_coverage_py.py`** - Backend diff coverage calculator (Python/pytest-cov)
- **`diff_coverage_lcov.mjs`** - Frontend diff coverage calculator (Jest/LCOV)
- **`gate.sh`** - Unified orchestrator for both backend and frontend
- **`report.sh`** - Global coverage report generator

## Quick Usage

```bash
# Check diff coverage (hard gate)
npm run coverage:gate

# Generate global coverage report
npm run coverage:report

# Individual checks
npm run coverage:diff:backend
npm run coverage:diff:frontend
```

## Documentation

See `docs/reports/COVERAGE_AUTOMATION.md` for complete documentation.

