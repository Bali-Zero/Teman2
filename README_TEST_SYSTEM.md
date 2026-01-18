# 🧪 NUZANTARA TEST SYSTEM - Quick Start

## 🚀 AVVIO RAPIDO

### **Esegui Test Completo:**

```bash
./scripts/unified_test_force.sh
```

### **Segui Live:**

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step [1-5]|Generating test|salvato|passato|Coverage aggiornata"
```

### **Vedi Risultati:**

```bash
./scripts/show_unified_results.sh
```

---

## 📊 COSA FA IL SISTEMA

1. ✅ Raccoglie coverage da tutti i componenti
2. ✅ Identifica gap critici
3. ✅ Genera test con Qwen
4. ✅ **Salva test in file** ⭐
5. ✅ **Esegue test automaticamente** ⭐
6. ✅ **Ricalcola coverage** ⭐
7. ✅ Mostra aumento coverage

---

## 📁 FILE GENERATI

- **Test:** `apps/{component}/tests/unit/test_*.py`
- **Report:** `logs/unified_coverage_report.json`
- **Log:** `logs/unified_test_force.log`

---

## ⏱️ TEMPO STIMATO

- **Raccolta coverage:** 30-60 minuti
- **Generazione test:** 90-120 minuti
- **Totale:** 2-3 ore

---

## 📚 DOCUMENTAZIONE COMPLETA

- `UNIFIED_TEST_SYSTEM.md` - Documentazione completa
- `COMANDI_LIVE.md` - Comandi per monitoraggio
- `VERIFICA_PIU_TARDI.md` - Verifica post-esecuzione

---

**Sistema pronto all'uso!** 🎉
