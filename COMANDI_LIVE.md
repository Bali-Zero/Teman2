# 🔴 COMANDI PER SEGUIRE LIVE

## 🎯 COMANDO PRINCIPALE (Consigliato)

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step [1-5]|Generating test|salvato|passato|fallito|Coverage aggiornata|completed|Summary"
```

**Cosa fa:** Mostra in tempo reale solo le informazioni importanti

---

## 📊 VERSIONE DETTAGLIATA (Tutti i log)

```bash
tail -f logs/unified_test_force.log
```

**Cosa fa:** Mostra TUTTI i log in tempo reale (può essere molto verboso)

---

## 🔍 VERSIONE FILTRATA (Solo Step e Test)

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step|Test|Coverage|✅|❌|📊|🤖"
```

**Cosa fa:** Mostra solo step, test, coverage e emoji importanti

---

## ⚡ VERSIONE ULTRA-FILTRATA (Solo eventi chiave)

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step 4|Step 5|salvato|passato|fallito|Coverage aggiornata|completed"
```

**Cosa fa:** Mostra SOLO quando:

- Arriva allo Step 4 (generazione test)
- Test vengono salvati
- Test vengono eseguiti
- Coverage viene ricalcolata
- Processo completa

---

## 🎨 VERSIONE COLORATA (se supportato)

```bash
tail -f logs/unified_test_force.log | grep --color=always --line-buffered -E "Step [1-5]|Generating test|salvato|passato|fallito|Coverage aggiornata|completed"
```

---

## 📈 MONITORAGGIO MULTI-TERMINAL

### **Terminal 1: Log principale**

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step|Test|Coverage|✅|❌"
```

### **Terminal 2: Solo Step 4-5**

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step 4|Step 5|salvato|passato|Coverage aggiornata"
```

### **Terminal 3: Verifica test salvati**

```bash
watch -n 5 'find apps -name "test_*.py" -mmin -10 | wc -l'
```

---

## 🔔 NOTIFICA QUANDO ARRIVA A STEP 4

```bash
tail -f logs/unified_test_force.log | grep --line-buffered "Step 4" && echo "🔔 STEP 4 RAGGIUNTO!" && say "Step 4 raggiunto"
```

---

## 📊 STATO PROCESSO IN TEMPO REALE

```bash
watch -n 2 'ps aux | grep unified_test_force_orchestrator | grep -v grep && echo "---" && tail -3 logs/unified_test_force.log'
```

**Cosa fa:** Aggiorna ogni 2 secondi mostrando:

- Se il processo è attivo
- Ultimi 3 log

---

## 🎯 COMANDO RACCOMANDATO (Copia e incolla)

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step [1-5]|Generating test|salvato|passato|fallito|Coverage aggiornata|completed|Summary"
```

**Premi `Ctrl+C` per uscire**

---

## 💡 SUGGERIMENTI

- **Per vedere tutto:** Usa `tail -f logs/unified_test_force.log`
- **Per vedere solo importante:** Usa il comando raccomandato sopra
- **Per vedere solo Step 4-5:** Filtra con `Step 4|Step 5|salvato|passato`
- **Per uscire:** Premi `Ctrl+C`

---

## 🔴 COSA VEDRAI QUANDO ARRIVA A STEP 4

```
🤖 Step 4: Generating tests for critical gaps (Qwen)...
🎯 Generating tests for 15 critical gaps...
   [1/15] Generating test for mouth-frontend/src/middleware.ts
   ✅ Test salvato: apps/mouth-frontend/tests/middleware.test.ts
   ✅ Test passato: middleware.test.ts
   [2/15] Generating test for...
   ...
📊 Step 5: Ricalcolo coverage dopo test generati...
✅ Coverage aggiornata: 45.2% (era 44.5%)
✅ Unified analysis completed
```

---

**Usa il comando raccomandato per seguire live!** 🔴
