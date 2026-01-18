# 🚀 COMANDI UNIFIED TEST FORCE

## ✅ COMANDO PRINCIPALE

```bash
./scripts/unified_test_force.sh
```

**Cosa fa:**

- Testa TUTTO il sistema (backend + frontend)
- Calcola coverage complessivo
- Calcola coverage differenziale
- Genera test con Qwen

**Durata:** 60-120 minuti (prima volta, poi più veloce)

---

## 📊 MONITORAGGIO IN TEMPO REALE

### **Vedi log in tempo reale:**

```bash
tail -f logs/unified_test_force.log
```

### **Vedi ultimi 50 righe:**

```bash
tail -50 logs/unified_test_force.log
```

### **Cerca errori:**

```bash
grep -i error logs/unified_test_force.log | tail -20
```

---

## 📈 VEDERE RISULTATI

### **Report JSON completo:**

```bash
cat logs/unified_coverage_report.json | python3 -m json.tool
```

### **Coverage complessivo:**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('📊 Overall Coverage:', data['coverage_report']['overall_coverage'], '%')
print('\nPer Tipo:')
for type_name, coverage in data['coverage_report']['coverage_by_type'].items():
    print(f'  {type_name}: {coverage:.1f}%')
"
```

### **Coverage per componente:**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('📊 Coverage per Componente:\n')
for name, comp in data['coverage_report']['components'].items():
    print(f\"  {name}: {comp['coverage']:.1f}% ({comp['files']} files, {comp['gaps']} gaps)\")
"
```

### **Differential (delta vs baseline):**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
diff = data.get('differential_report')
if diff:
    print('📈 Coverage Differential:')
    print(f\"  Overall Delta: {diff.get('overall_delta', 0):+.1f}%\")
    print(f\"  Regressions: {diff.get('regressions', 0)}\")
    print(f\"  Improvements: {diff.get('improvements', 0)}\")
    print(f\"  Critical Regressions: {diff.get('critical_regressions', 0)}\")
else:
    print('⚠️ No baseline - run with --save-baseline first')
"
```

---

## 💾 SALVARE BASELINE

**Prima volta (salva baseline):**

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --provider=local \
    --save-baseline \
    --generate-tests=false
```

**Poi ogni esecuzione calcola il delta vs questa baseline.**

---

## 🔧 OPZIONI AVANZATE

### **Solo coverage (no test generation):**

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --provider=local \
    --generate-tests=false
```

### **Con più test per componente:**

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --provider=local \
    --max-tests=10
```

### **Salva report custom:**

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --output=/path/to/custom_report.json
```

---

## ⚡ COMANDI RAPIDI

```bash
# Esegui test completo
./scripts/unified_test_force.sh

# Monitora progresso
tail -f logs/unified_test_force.log

# Vedi risultati
cat logs/unified_coverage_report.json | python3 -m json.tool | less

# Verifica cron
crontab -l | grep unified_test_force
```

---

## ✅ STATO SISTEMA

**Il sistema è configurato e funzionante!**

- ✅ Cron attivo (ogni notte 2:15 AM)
- ✅ Testa tutto (backend + frontend)
- ✅ Coverage complessivo
- ✅ Coverage differenziale
- ✅ Qwen per generazione test

**Non serve fare nulla - tutto automatico!** 🎉
