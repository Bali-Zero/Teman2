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
bash scripts/test_automation/test_master.sh 90 true

# 2. Esegui automazione completa
bash scripts/test_automation/test_master.sh 90

# 3. Genera solo test mancanti
python3 scripts/test_automation/test_generator.py

# 4. Monitora solo coverage
python3 scripts/test_automation/coverage_monitor.py 90

# 5. Verifica solo qualità
python3 scripts/test_automation/test_quality_checker.py
```

## 📊 Output Example

```
🤖 TEST MASTER - Complete Test Automation
==========================================

Step 1/4: Test Quality Check
  → Analyzing 109 test files...
  → Average quality: 78.5/100
  → 5 files need improvement

Step 2/4: Coverage Analysis
  → Current coverage: 87.34%
  → Target: 90%
  → Gap: 2.66%
  → 15 files below target

Step 3/4: Auto-Generate Missing Tests
  → Found 0 untested modules
  → All modules have tests!

Step 4/4: Run Complete Test Suite
  → Running 2596 tests...
  → ✅ 2563 passed, 10 failed

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

# Custom directories
python3 scripts/test_automation/test_generator.py \
  --source-dir apps/backend-rag/backend/services \
  --test-dir apps/backend-rag/tests/unit
```

**Output**: Test skeleton files in `apps/backend-rag/tests/unit/`

### 2. Coverage Monitor

```bash
# Target 90%
python3 scripts/test_automation/coverage_monitor.py 90

# Target 85%
python3 scripts/test_automation/coverage_monitor.py 85
```

**Output**: `coverage_report.txt` + `apps/backend-rag/coverage.json`

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

## 💡 Best Practices

1. **Before committing**: Run `bash scripts/test_automation/test_master.sh 90 true`
2. **After generating tests**: Review and complete TODOs
3. **Focus on**: Lowest coverage files first
4. **Quality target**: 80/100 minimum
5. **Coverage target**: 90% minimum

## 📈 Integration with npm

These scripts are integrated into package.json:

```bash
npm run test:auto-generate      # Generate missing tests
npm run test:coverage-monitor   # Monitor coverage
npm run test:quality-check      # Check quality
npm run test:automation         # Run complete automation
npm run test:automation:dry     # Dry run
```

## 🎯 Goals

- **Coverage Target**: 90% minimum
- **Quality Score**: 80/100 minimum
- **Test Pass Rate**: 100%
- **Automation**: Fully automated test generation and monitoring

---

**Created**: 2025-11-30
**Maintainer**: Claude Code
