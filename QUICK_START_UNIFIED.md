# 🚀 QUICK START - Unified Test Force

## ✅ SISTEMA COMPLETO IMPLEMENTATO

Il nuovo sistema testa **TUTTO**:

- ✅ Backend (Python)
- ✅ Frontend (TypeScript/JS)
- ✅ Integration
- ✅ Calcola coverage differenziale

---

## 🎯 COMANDO PRINCIPALE

```bash
./scripts/unified_test_force.sh
```

**Cosa fa:**

1. Raccoglie coverage da TUTTI i componenti
2. Calcola coverage differenziale vs baseline
3. Identifica gap critici
4. Genera test con Qwen per tutti i componenti

---

## 📊 PRIMA ESECUZIONE (Salva Baseline)

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --provider=local \
    --save-baseline \
    --generate-tests=false
```

**Questo salva la baseline corrente.**

---

## 🔄 ESECUZIONI SUCCESSIVE

```bash
./scripts/unified_test_force.sh
```

**Ogni esecuzione:**

- Calcola coverage corrente
- Confronta con baseline
- Mostra delta (regressioni/miglioramenti)
- Genera test per gap critici

---

## 📈 VEDERE RISULTATI

### **Report JSON:**

```bash
cat logs/unified_coverage_report.json | python3 -m json.tool
```

### **Log Completo:**

```bash
tail -100 logs/unified_test_force.log
```

### **Coverage per Componente:**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Overall Coverage:', data['coverage_report']['overall_coverage'], '%')
print('\nPer Component:')
for name, comp in data['coverage_report']['components'].items():
    print(f\"  {name}: {comp['coverage']:.1f}%\")
"
```

### **Differential:**

```bash
cat logs/unified_coverage_report.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
diff = data.get('differential_report', {})
if diff:
    print('Overall Delta:', diff.get('overall_delta', 0), '%')
    print('Regressions:', diff.get('regressions', 0))
    print('Improvements:', diff.get('improvements', 0))
"
```

---

## 🔧 CONFIGURAZIONE CRON

Il cron è già configurato per usare il nuovo sistema unified.

**Verifica:**

```bash
crontab -l | grep unified_test_force
```

**Se non c'è, riconfigura:**

```bash
./scripts/setup_all_automation.sh
```

---

## ✅ TUTTO PRONTO!

Il sistema:

- ✅ Testa TUTTO (backend + frontend + integration)
- ✅ Calcola coverage differenziale
- ✅ Genera test con Qwen
- ✅ Funziona automaticamente ogni notte

**Non serve fare nulla - tutto automatico!** 🎉
