# 📊 VEDERE RISULTATI - Unified Test Force

## ✅ COMANDI PER VEDERE RISULTATI

### **1. Vedi se è finito:**

```bash
tail -5 logs/unified_test_force.log | grep -E "completed|Summary|✅"
```

### **2. Report JSON completo:**

```bash
cat logs/unified_coverage_report.json | python3 -m json.tool | less
```

### **3. Coverage Complessivo:**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('🌐 UNIFIED COVERAGE REPORT')
print('=' * 50)
print(f\"Overall Coverage: {data['coverage_report']['overall_coverage']:.1f}%\")
print(f\"Total Components: {len(data['coverage_report']['components'])}\")
print()
print('📊 Coverage per Tipo:')
for type_name, coverage in data['coverage_report']['coverage_by_type'].items():
    print(f\"  {type_name}: {coverage:.1f}%\")
print()
print('📦 Coverage per Componente:')
for name, comp in data['coverage_report']['components'].items():
    print(f\"  {name}: {comp['coverage']:.1f}% ({comp['files']} files, {comp['gaps']} gaps)\")
print()
print(f\"🎯 Critical Gaps: {data['coverage_report']['critical_gaps']}\")
"
```

### **4. Test Generati:**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
test_gen = data.get('test_generation', {})
print('🤖 TEST GENERATION RESULTS')
print('=' * 50)
print(f\"Tests Generated: {test_gen.get('tests_generated', 0)}\")
print(f\"Tests Passed: {test_gen.get('tests_passed', 0)}\")
print(f\"Tests Failed: {test_gen.get('tests_failed', 0)}\")
print()
print('📦 Tests per Componente:')
for comp, count in test_gen.get('tests_by_component', {}).items():
    print(f\"  {comp}: {count} tests\")
"
```

### **5. Differential (se baseline esiste):**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
diff = data.get('differential_report')
if diff:
    print('📈 COVERAGE DIFFERENTIAL')
    print('=' * 50)
    print(f\"Overall Delta: {diff.get('overall_delta', 0):+.1f}%\")
    print(f\"Regressions: {diff.get('regressions', 0)}\")
    print(f\"Improvements: {diff.get('improvements', 0)}\")
    print(f\"Critical Regressions: {diff.get('critical_regressions', 0)}\")
else:
    print('⚠️ No baseline - save baseline first')
"
```

### **6. Summary Completo:**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
summary = data.get('summary', {})
print('📊 UNIFIED TEST FORCE SUMMARY')
print('=' * 50)
print(f\"Duration: {summary.get('duration', 0):.1f}s\")
print(f\"Components Analyzed: {summary.get('components_analyzed', 0)}\")
print(f\"Overall Coverage: {summary.get('overall_coverage', 0):.1f}%\")
print(f\"Tests Generated: {summary.get('tests_generated', 0)}\")
if summary.get('regressions', 0) > 0:
    print(f\"⚠️ Regressions: {summary.get('regressions', 0)}\")
if summary.get('improvements', 0) > 0:
    print(f\"✅ Improvements: {summary.get('improvements', 0)}\")
"
```

---

## 💾 SALVARE BASELINE (Dopo Prima Esecuzione)

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --provider=local \
    --save-baseline \
    --generate-tests=false
```

**Questo salva la baseline corrente per confronti futuri.**

---

## 🔄 PROSSIMA ESECUZIONE

Dopo aver salvato la baseline, ogni esecuzione successiva mostrerà:

- Delta vs baseline
- Regressioni (>1% decrease)
- Miglioramenti (>1% increase)
- Critical regressions (>5% decrease)

---

## 📝 LOG IN TEMPO REALE

```bash
tail -f logs/unified_test_force.log
```

**Premi Ctrl+C per uscire.**
