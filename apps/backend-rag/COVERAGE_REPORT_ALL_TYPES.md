# 📊 Test Coverage Report - All 3 Types

**Generated:** $(date)

## Summary

Questo report mostra il coverage dei test per tutti e 3 i tipi:
- **Unit Tests**: Test unitari isolati
- **Integration Tests**: Test di integrazione tra componenti
- **API Tests**: Test degli endpoint API

## Current Status

### Unit Tests
- **Coverage**: 4.89% (parziale - calcolo in corso)
- **Statements**: 17,123
- **Covered**: 838
- **Missing**: 16,285

### Integration Tests
- **Status**: Not yet calculated

### API Tests  
- **Status**: Not yet calculated

## How to Calculate Full Coverage

### Option 1: Using Python Script
```bash
cd /Users/antonellosiano/Desktop/nuzantara
python3 scripts/test_automation/calculate_full_coverage.py apps/backend-rag
```

### Option 2: Using Bash Script
```bash
cd /Users/antonellosiano/Desktop/nuzantara
./scripts/test_automation/run_coverage_all_types.sh
```

### Option 3: Manual Calculation
```bash
cd apps/backend-rag

# Unit tests
export COVERAGE_FILE=.coverage_data/.coverage.unit
coverage run --source=backend -m pytest tests/unit -v
coverage json -o .coverage_data/coverage_unit.json
coverage html -d .coverage_data/htmlcov_unit

# Integration tests
export COVERAGE_FILE=.coverage_data/.coverage.integration
coverage run --source=backend -m pytest tests/integration -v
coverage json -o .coverage_data/coverage_integration.json
coverage html -d .coverage_data/htmlcov_integration

# API tests
export COVERAGE_FILE=.coverage_data/.coverage.api
coverage run --source=backend -m pytest tests/api -v
coverage json -o .coverage_data/coverage_api.json
coverage html -d .coverage_data/htmlcov_api

# Combine all
export COVERAGE_FILE=.coverage_data/.coverage.combined
coverage combine .coverage_data/.coverage.*
coverage json -o .coverage_data/coverage_combined.json
coverage html -d .coverage_data/htmlcov_combined
```

## View Reports

HTML reports are available at:
- Unit: `apps/backend-rag/.coverage_data/htmlcov_unit/index.html`
- Integration: `apps/backend-rag/.coverage_data/htmlcov_integration/index.html`
- API: `apps/backend-rag/.coverage_data/htmlcov_api/index.html`
- Combined: `apps/backend-rag/.coverage_data/htmlcov_combined/index.html`

## Notes

- Il calcolo completo può richiedere molto tempo (migliaia di test)
- I report JSON sono disponibili in `.coverage_data/coverage_*.json`
- Il coverage combinato mostra il coverage totale considerando tutti i tipi di test
