# 🤖 Test Automation System

**Sistema completo di automazione per creazione, gestione e manutenzione test**

---

## 📋 Panoramica

Il sistema di Test Automation fornisce 4 strumenti principali:

1. **Test Generator** - Genera automaticamente test skeleton
2. **Coverage Monitor** - Monitora coverage e identifica gap
3. **Test Quality Checker** - Verifica qualità dei test esistenti
4. **Test Master** - Orchestrazione completa di tutti gli strumenti

---

## 🚀 Quick Start

### Esecuzione Completa (Recommended)

```bash
# Esegui tutto il sistema di automazione
npm run test:automation

# Dry run (non crea file)
npm run test:automation:dry
```

### Strumenti Individuali

```bash
# 1. Genera test per moduli non testati
npm run test:auto-generate

# 2. Monitora coverage e identifica gap
npm run test:coverage-monitor

# 3. Verifica qualità test esistenti
npm run test:quality-check
```

---

## 🔧 Tool 1: Test Generator

**Funzione**: Genera automaticamente test skeleton per moduli Python senza test

### Utilizzo

```bash
# Genera test per tutti i moduli non testati
python3 scripts/test_automation/test_generator.py

# Dry run (mostra cosa verrebbe creato)
python3 scripts/test_automation/test_generator.py --dry-run
```

### Cosa Fa

1. Scansiona directory `apps/backend-rag/backend/services/`
2. Identifica moduli senza test corrispondente
3. Analizza ogni modulo con AST (Abstract Syntax Tree)
4. Estrae classi, metodi, funzioni
5. Genera test skeleton con:
   - Import statements
   - Test class per ogni class
   - Test function per ogni method/function
   - Pytest fixtures
   - AsyncIO support
   - Mock setup
   - AAA pattern (Arrange, Act, Assert)

### Output Example

```python
"""
Tests for search_service
Auto-generated test skeleton - PLEASE COMPLETE IMPLEMENTATION
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

class TestSearchService:
    """Tests for SearchService class"""

    @pytest.fixture
    def search_service_instance(self):
        """Fixture for SearchService instance"""
        # TODO: Create and return SearchService instance
        pass

    @pytest.mark.asyncio
    async def test_search(self, search_service_instance):
        """Test: search() method"""
        # TODO: Implement test for search
        # Arrange
        # Act
        # Assert
        pass
```

### Configurazione

Modifica in `test_generator.py`:
```python
source_dir = "apps/backend-rag/backend/services"  # Directory sorgenti
test_dir = "apps/backend-rag/tests/unit"          # Directory test
```

---

## 📊 Tool 2: Coverage Monitor

**Funzione**: Monitora coverage continuo e identifica gap

### Utilizzo

```bash
# Target coverage 90%
python3 scripts/test_automation/coverage_monitor.py 90

# Target coverage 85%
python3 scripts/test_automation/coverage_monitor.py 85
```

### Cosa Fa

1. Esegue pytest con coverage
2. Genera coverage.json con dettagli
3. Identifica file sotto target coverage
4. Ordina per coverage (più basso prima)
5. Genera report dettagliato
6. Salva in `coverage_report.txt`

### Output Example

```
================================================================================
📊 COVERAGE MONITOR REPORT
================================================================================

Total Coverage: 87.34%
Target: 90%
Gap: 2.66%

⚠️  BELOW TARGET by 2.66%

📉 Coverage Gaps (15 files below 90%):
--------------------------------------------------------------------------------
 65.2% |   34 missing | services/notification_hub.py
 72.1% |   28 missing | services/intelligent_router.py
 78.5% |   21 missing | services/cultural_rag_service.py
...

================================================================================
💡 RECOMMENDATIONS:

1. Focus on lowest coverage files first
2. Use test_generator.py to create test skeletons
3. Run: python scripts/test_automation/test_generator.py
4. Check missing lines in coverage.json for specifics

================================================================================
```

### Exit Code

- **0**: Coverage >= target
- **1**: Coverage < target

---

## 🔍 Tool 3: Test Quality Checker

**Funzione**: Verifica qualità dei test esistenti

### Utilizzo

```bash
# Check test directory
python3 scripts/test_automation/test_quality_checker.py apps/backend-rag/tests/unit
```

### Cosa Verifica

1. **Docstrings**: Ogni test ha docstring?
2. **Assertions**: Ogni test ha almeno un assert?
3. **Pytest Import**: File usa pytest?
4. **Mock Usage**: Test usa mocking appropriato?
5. **Structure**: Segue best practices?

### Quality Score

```
Quality Score = Docstrings (30%) + Assertions (40%) + Structure (30%)
```

- **80-100**: ✅ Excellent
- **60-79**: ⚠️ Good
- **<60**: ❌ Poor (needs improvement)

### Output Example

```
================================================================================
🔍 TEST QUALITY CHECKER REPORT
================================================================================

Total Test Files: 65
Total Tests: 1565
Average Quality Score: 78.5/100

Quality Distribution:
  ✅ Excellent (80-100): 42 files
  ⚠️  Good (60-79): 18 files
  ❌ Poor (<60): 5 files

📉 Low Quality Files (need improvement):
--------------------------------------------------------------------------------
 52.3/100 |  12 tests | test_notification_hub.py
           └─ test_send_alert: Missing docstring
           └─ test_send_alert: No assertions found
           └─ Missing pytest import

 58.7/100 |  18 tests | test_intelligent_router.py
           └─ test_route_query: Missing docstring

...

================================================================================
💡 RECOMMENDATIONS:

1. Add docstrings to all test functions
2. Ensure every test has at least one assertion
3. Use pytest fixtures for setup/teardown
4. Use mocking for external dependencies
5. Follow AAA pattern: Arrange, Act, Assert

================================================================================
```

---

## 🎯 Tool 4: Test Master

**Funzione**: Orchestrazione completa di tutti gli strumenti

### Utilizzo

```bash
# Esegui tutto con target 90%
bash scripts/test_automation/test_master.sh 90

# Dry run (non genera file)
bash scripts/test_automation/test_master.sh 90 true
```

### Flusso Esecuzione

```
Step 1/4: Test Quality Check
  └─ Verifica qualità test esistenti
  └─ Genera test_quality_report.txt

Step 2/4: Coverage Analysis
  └─ Esegue pytest con coverage
  └─ Identifica gap
  └─ Genera coverage_report.txt

Step 3/4: Auto-Generate Missing Tests
  └─ Trova moduli non testati
  └─ Genera test skeleton

Step 4/4: Run Complete Test Suite
  └─ Esegue tutti i test
  └─ Verifica passaggio
```

### Output Reports

- `test_quality_report.txt` - Report qualità test
- `coverage_report.txt` - Report coverage gap
- `apps/backend-rag/coverage.json` - Coverage dettagliato

---

## 🔄 Automated Testing & Deployment

### Automated Workflow

File: Testing and deployment configuration

**Trigger**:
- Push su `main` o `develop`
- Pull/Merge request
- Schedule: Daily at 2 AM UTC

**Jobs**:

1. **test-quality** - Verifica qualità test
2. **coverage-analysis** - Analizza coverage
3. **auto-generate-tests** - Check moduli non testati
4. **run-tests** - Esegue suite completa

### Features

- 📊 **Coverage Report** su PR comments
- 📝 **Artifacts Upload** (quality report, coverage report)
- 🤖 **Auto-Issue Creation** se mancano test
- ☁️ **Codecov Integration** per coverage tracking

---

## 📈 Workflow Consigliato

### 1. Prima Esecuzione

```bash
# Verifica stato attuale
npm run test:automation:dry

# Genera test mancanti
npm run test:auto-generate

# Verifica coverage
npm run test:coverage-monitor
```

### 2. Sviluppo Iterativo

```bash
# Dopo ogni modifica codice
npm run test:automation

# Review reports
cat test_quality_report.txt
cat coverage_report.txt

# Implementa test skeleton generati
# Migliora test con bassa quality
```

### 3. Pre-Commit

```bash
# Verifica qualità prima di commit
npm run test:quality-check

# Verifica coverage
npm run test:coverage-monitor
```

### 4. CI/CD

- Push automaticamente triggera workflow
- Review coverage su PR
- Fix issues automaticamente creati

---

## 🎨 Customization

### Cambiare Target Coverage

```bash
# Nel codice
python3 scripts/test_automation/coverage_monitor.py 85  # Target 85%

# Npm script
npm run test:coverage-monitor  # Default 90%
```

### Cambiare Directory Test

Modifica in ogni script:
```python
source_dir = "apps/backend-rag/backend/services"
test_dir = "apps/backend-rag/tests/unit"
```

### Aggiungere Custom Checks

In `test_quality_checker.py`, aggiungi:
```python
def check_custom_pattern(self, test_file: Path) -> bool:
    # Your custom check logic
    pass
```

---

## 📊 Metriche e KPI

### Target Metrics

- **Coverage Target**: 90%
- **Quality Score Target**: 80/100
- **Test Pass Rate**: 100%
- **New Code Coverage**: 100%

### Monitoring

```bash
# Daily monitoring
npm run test:automation

# Weekly deep analysis
python3 scripts/test_automation/test_quality_checker.py
```

---

## 🔧 Troubleshooting

### Problema: "No module named 'pytest'"

```bash
cd apps/backend-rag
pip install pytest pytest-cov pytest-asyncio
```

### Problema: "Permission denied"

```bash
chmod +x scripts/test_automation/*.sh
```

### Problema: "Coverage file not found"

```bash
# Esegui prima i test
cd apps/backend-rag
pytest tests/unit --cov=backend --cov-report=json
```

---

## 🚀 Best Practices

### 1. Test Generation

- ✅ Review generated skeletons prima di commit
- ✅ Complete TODOs con implementation
- ✅ Add meaningful test data
- ❌ Non committare test skeleton vuoti

### 2. Coverage

- ✅ Focus su file con coverage più basso
- ✅ Test edge cases
- ✅ Test error paths
- ❌ Non mirare a 100% coverage inutile

### 3. Quality

- ✅ Add docstrings descrittivi
- ✅ Follow AAA pattern
- ✅ Use mocking per dependencies
- ❌ Non creare test troppo complessi

---

## 📚 Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Python AST](https://docs.python.org/3/library/ast.html)
- [Test Best Practices](https://docs.python-guide.org/writing/tests/)

---

## 🎯 Roadmap

### Planned Features

- [ ] AI-powered test implementation (not just skeleton)
- [ ] Mutation testing integration
- [ ] Visual coverage dashboard
- [ ] Auto-fix low quality tests
- [ ] Integration test generation
- [ ] Performance test generation

---

**Maintainer**: Claude Code
**Last Updated**: 2025-11-30
