# 💡 CONSIGLI PRATICI - Unified Test Force

## 🎯 CONSIGLI IMMEDIATI

### **1. Aspetta che Finisca il Run Corrente** ⏱️

Il sistema sta ancora lavorando (generando coverage). Aspetta che finisca prima di:

- Modificare configurazioni
- Riavviare
- Fare altre modifiche

**Monitora:**

```bash
tail -f logs/unified_test_force.log
```

---

### **2. Verifica Risultati Quando Finisce** 📊

Quando il sistema finisce, controlla:

```bash
./scripts/show_unified_results.sh
```

**Cosa verificare:**

- Quanti test sono stati generati con Qwen (vs Mock)
- Se ci sono stati timeout
- Se circuit breaker si è aperto
- Coverage complessivo

---

### **3. Salva Baseline Dopo Primo Run** 💾

Dopo che il sistema finisce, salva baseline per confronti futuri:

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --save-baseline \
    --generate-tests=false
```

**Perché:** Così ogni run successivo mostrerà delta vs baseline (regressioni/miglioramenti).

---

## 🔧 MIGLIORAMENTI CONSIGLIATI

### **1. Ottimizza System Prompt** ✏️

**Priorità: ALTA**

Modifica system prompt per migliorare qualità test generati:

```bash
code apps/backend-rag/backend/agents/config/qwen_system_prompts.py
```

**Suggerimenti:**

- Aggiungi regole specifiche per il tuo progetto
- Enfatizza pattern che usi spesso
- Specifica stile di codice preferito

**Esempio:**

```python
TEST_GENERATION_SYSTEM_PROMPT_BACKEND = """...
# AGGIUNGI:
9. Usa sempre type hints nei test
10. Preferisci test parametrizzati con @pytest.mark.parametrize
11. Mocka sempre chiamate HTTP con httpx
12. Testa anche errori e edge cases
"""
```

---

### **2. Monitora Performance Ollama** 📈

**Priorità: MEDIA**

Se vedi ancora timeout frequenti:

**Opzione A: Usa modello più piccolo**

```bash
ollama pull qwen2.5:3b
export OLLAMA_MODEL="qwen2.5:3b"
```

**Opzione B: Verifica risorse**

```bash
# Verifica RAM disponibile
vm_stat

# Verifica CPU
top -l 1 | grep "CPU usage"
```

**Opzione C: Riduci max_tokens ulteriormente**

```python
# In unified_test_force_orchestrator.py
max_tokens=1500  # Invece di 2000
```

---

### **3. Configura Cron per Esecuzione Automatica** ⏰

**Priorità: ALTA**

Il cron è già configurato, ma verifica:

```bash
crontab -l | grep unified_test_force
```

**Se non c'è:**

```bash
./scripts/setup_all_automation.sh
```

**Risultato:** Sistema esegue automaticamente ogni notte alle 2:15 AM.

---

### **4. Crea Dashboard Monitoring** 📊

**Priorità: BASSA (ma utile)**

Crea script per vedere trend coverage:

```bash
# scripts/show_coverage_trend.sh
# Mostra coverage nel tempo
```

**Utile per:**

- Vedere miglioramenti nel tempo
- Identificare regressioni
- Monitorare qualità test

---

### **5. Ottimizza Coverage Collection** ⚡

**Priorità: MEDIA**

Se coverage collection è lenta:

**Opzione A: Salta componenti senza test**

```python
# In unified_coverage_collector.py
# Skip componenti se non hanno test directory
```

**Opzione B: Usa coverage esistenti**

```python
# Se coverage.json esiste, usa quello invece di rigenerare
```

**Opzione C: Parallelizza coverage collection**

```python
# Raccogli coverage in parallelo per componenti diversi
```

---

## 🎯 PRIORITÀ CONSIGLIATE

### **Ora (Immediato):**

1. ✅ Aspetta che finisca run corrente
2. ✅ Verifica risultati quando finisce
3. ✅ Salva baseline

### **Prossimi 1-2 giorni:**

1. 🔧 Ottimizza system prompt per tuo progetto
2. 📊 Analizza risultati primo run
3. ⚙️ Aggiusta parametri se necessario (max_tokens, timeout)

### **Prossima settimana:**

1. 📈 Monitora performance nel tempo
2. 🔍 Identifica pattern nei test generati
3. ✏️ Affina system prompt basato su risultati

---

## 🚨 COSA EVITARE

### **❌ Non riavviare durante esecuzione**

Aspetta che finisca prima di modificare.

### **❌ Non modificare troppo system prompt inizialmente**

Inizia con modifiche piccole, testa, poi aggiungi.

### **❌ Non ignorare timeout frequenti**

Se vedi molti timeout, investiga (RAM, modello, etc.).

---

## ✅ CHECKLIST POST-RUN

Quando il sistema finisce:

- [ ] Verifica risultati: `./scripts/show_unified_results.sh`
- [ ] Conta test generati con Qwen vs Mock
- [ ] Verifica se ci sono stati timeout
- [ ] Controlla coverage complessivo
- [ ] Salva baseline se primo run
- [ ] Analizza qualità test generati
- [ ] Modifica system prompt se necessario
- [ ] Riavvia con modifiche se fatto

---

## 💡 CONSIGLIO FINALE

**Approccio Incrementale:**

1. **Prima run:** Lascia sistema lavorare, vedi risultati
2. **Analizza:** Cosa funziona, cosa no
3. **Ottimizza:** Modifica system prompt e parametri
4. **Ripeti:** Testa modifiche, migliora iterativamente

**Non cercare perfezione subito - migliora gradualmente!**

---

## 🎯 PROSSIMO STEP CONSIGLIATO

**Aspetta che finisca, poi:**

```bash
# 1. Vedi risultati
./scripts/show_unified_results.sh

# 2. Analizza log
grep -E "succeeded|timeout|Mock" logs/unified_test_force.log | tail -20

# 3. Se tutto ok, salva baseline
cd apps/backend-rag
python3 -m backend.agents.agents.unified_test_force_orchestrator \
    --project-root=/Users/antonellosiano/Desktop/nuzantara \
    --save-baseline \
    --generate-tests=false
```

**Poi modifica system prompt se vuoi migliorare qualità test!**
