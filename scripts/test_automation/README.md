# 🤖 Test Automation Tools

**Automazione completa per creazione, gestione e manutenzione test**

## 📁 Files

- `test_generator.py` - Auto-genera test skeleton per moduli non testati
- `coverage_monitor.py` - Monitora coverage e identifica gap
- `test_quality_checker.py` - Verifica qualità test esistenti
- `test_master.sh` - Orchestrazione completa di tutti gli strumenti

## 🚀 Quick Start

```bash
# Da root directory del progetto

# 1. Dry run completo (consigliato prima volta)
npm run test:automation:dry

# 2. Esegui automazione completa
npm run test:automation

# 3. Genera solo test mancanti
npm run test:auto-generate

# 4. Monitora solo coverage
npm run test:coverage-monitor

# 5. Verifica solo qualità
npm run test:quality-check
```

## 📊 Output Example

```
🤖 TEST MASTER - Complete Test Automation
==========================================

Step 1/4: Test Quality Check
  → Analyzing 65 test files...
  → Average quality: 78.5/100
  → 5 files need improvement

Step 2/4: Coverage Analysis
  → Current coverage: 87.34%
  → Target: 90%
  → Gap: 2.66%
  → 15 files below target

Step 3/4: Auto-Generate Missing Tests
  → Found 2 untested modules
  → Generated: test_response_handler.py
  → Generated: test_specialized_service_router.py

Step 4/4: Run Complete Test Suite
  → Running 1565 tests...
  → ✅ All tests passed!

✅ TEST MASTER COMPLETE

📊 Reports Generated:
  - test_quality_report.txt
  - coverage_report.txt
  - apps/backend-rag/coverage.json
```

## 🔧 Individual Tools

### 1. Test Generator

```bash
python3 scripts/test_automation/test_generator.py

# Dry run
python3 scripts/test_automation/test_generator.py --dry-run
```

**Output**: Test skeleton files in `apps/backend-rag/tests/unit/`

### 2. Coverage Monitor

```bash
# Target 90%
python3 scripts/test_automation/coverage_monitor.py 90

# Target 85%
python3 scripts/test_automation/coverage_monitor.py 85
```

**Output**: `coverage_report.txt` + `coverage.json`

### 3. Test Quality Checker

```bash
python3 scripts/test_automation/test_quality_checker.py
```

**Output**: `test_quality_report.txt`

### 4. Test Master (All-in-One)

```bash
# Production
bash scripts/test_automation/test_master.sh 90

# Dry run
bash scripts/test_automation/test_master.sh 90 true
```

**Output**: All reports + generated tests

## 📖 Full Documentation

See [docs/TEST_AUTOMATION.md](../../docs/TEST_AUTOMATION.md) for complete documentation.

## 🎯 Automated Testing Integration

Automated testing configuration available.

**Triggers**:
- Code changes
- Manual trigger

**Features**:
- Auto-generate tests
- Coverage tracking
- Quality checks
- Coverage reporting
- Auto-create issues for missing tests

## 💡 Best Practices

1. **Before committing**: Run `npm run test:automation:dry`
2. **After generating tests**: Review and complete TODOs
3. **Focus on**: Lowest coverage files first
4. **Quality target**: 80/100 minimum
5. **Coverage target**: 90% minimum

---

**Maintainer**: Claude Code
**Created**: 2025-11-30
