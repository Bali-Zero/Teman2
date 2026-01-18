# ZANTARA Communication Quality Audit

**Data:** 2026-01-19  
**Status:** 🔍 Analisi Completa  
**Scope:** Qualità e Precisione della Comunicazione nella Webapp

---

## 📊 EXECUTIVE SUMMARY

ZANTARA ha **5 sistemi di controllo qualità** implementati per garantire comunicazioni accurate e professionali:

1. ✅ **Evidence Scoring System** - Valuta la qualità delle fonti (0.0-1.0)
2. ✅ **Response Sanitization** - Rimuove artefatti dai training data
3. ✅ **Response Validator** - Valida coerenza dell'identità ZANTARA
4. ✅ **Verification Service** - Verifica risposte contro contesto sorgente
5. ✅ **Prompt System** - Regole rigorose per pricing, citazioni, linguaggio

**Threshold Critico:** Evidence Score < 0.3 → **ABSTAIN** (rifiuta di rispondere)

---

## 🛡️ SISTEMI DI CONTROLLO QUALITÀ

### 1. Evidence Scoring System

**File:** `backend/services/rag/agentic/reasoning.py`

**Come Funziona:**

- Calcola un punteggio di evidenza basato su:
  - Qualità delle fonti (score > 0.3 = alta qualità)
  - Numero di fonti (>3 fonti = bonus)
  - Rilevanza del contesto (keyword matching)

**Threshold:**

- **< 0.3** → ABSTAIN (rifiuta di rispondere)
- **0.3-0.6** → Risposta cauta con warning
- **> 0.6** → Risposta normale

**Status:** ✅ ATTIVO

**Codice:**

```python
# EvidenceScoreConstants.ABSTAIN_THRESHOLD = 0.3
if evidence_score < 0.3 and not state.skip_rag and not trusted_tools_used:
    state.final_answer = "Mi dispiace, non ho trovato informazioni verificate sufficienti..."
```

**Problema Potenziale:** Threshold molto basso (0.3) potrebbe permettere risposte con evidenza debole.

---

### 2. Response Sanitization

**File:** `backend/utils/response_sanitizer.py`

**Cosa Rimuove:**

- ✅ Placeholder markers: `[PRICE]`, `[MANDATORY]`, `[OPTIONAL]`
- ✅ Training format leaks: `User:`, `Assistant:`, `Context:`
- ✅ Agentic artifacts: `THOUGHT:`, `ACTION:`, `OBSERVATION:`, `Final Answer:`
- ✅ Meta-commentary: "natural language summary", "(from KB source)"
- ✅ Markdown headers in plain text
- ✅ Messaggi "Non ho documenti" → Sostituiti con messaggio utile

**Pattern Catturati:**

- `non ho documenti/documento`
- `non trovo documenti`
- `non ho informazioni`
- `i don't have documents`
- `no documents available`
- `no information found`

**Status:** ✅ ATTIVO

**Problema Potenziale:** Potrebbe non catturare tutti i pattern nuovi.

---

### 3. Response Validator

**File:** `backend/services/response/validator.py`

**Cosa Valida:**

- ✅ Rimuove filler openings ("Certainly", "Of course", "Grazie per la domanda")
- ✅ Enforce length limits (max sentences per mode)
- ✅ Ensure hook (call-to-action) se richiesto
- ✅ Clean formatting artifacts

**Status:** ⚠️ **DRY_RUN MODE** (non modifica, solo reporta)

**Problema:** Il validator è in `dry_run=True` per default, quindi **non applica correzioni automatiche**.

---

### 4. Verification Service

**File:** `backend/services/rag/verification_service.py`

**Come Funziona:**

- Usa un LLM leggero come "Guardian" per verificare risposte
- Confronta risposta generata con contesto sorgente
- Score di verifica: >= 0.7 = valido

**Status:** ✅ ATTIVO (ma potrebbe non essere chiamato sempre)

---

### 5. Prompt System (ZANTARA V6)

**File:** `backend/services/rag/agentic/prompt_builder.py`

**Regole Critiche:**

#### Pricing Rules (ABSOLUTE)

- ✅ **RULE 1:** Solo prezzi da `get_pricing` tool
- ✅ **RULE 2:** Se prezzo non nel tool → "DA VERIFICARE"
- ✅ **RULE 3:** Solo fatti verificabili

#### Language Protocol (ABSOLUTE)

- ✅ Risposta DEVE corrispondere alla lingua della query
- ✅ Italiano → Italiano, English → English, ecc.

#### Greeting Rules (CRITICAL)

- ✅ Saluto SOLO al primo messaggio
- ✅ Controlla conversation history prima di salutare

#### Citation Rules

- ✅ Citazione obbligatoria per leggi/regolamenti
- ✅ Formato: "📜 Sumber: [Nama Peraturan], Pasal [X]"

#### Closing Phrases

- ✅ Varietà obbligatoria (non ripetere stesso closing)

**Status:** ✅ ATTIVO

---

## ⚠️ PROBLEMI IDENTIFICATI

### 1. **Threshold Evidence Score Troppo Basso**

**Problema:** Threshold 0.3 è molto basso. Potrebbe permettere risposte con evidenza debole.

**Raccomandazione:** Considerare di aumentare a 0.4-0.5 per risposte più accurate.

**Codice Attuale:**

```python
ABSTAIN_THRESHOLD = 0.3  # Cambiato da 0.8 a 0.3 (v1175, 2025-12-30)
```

---

### 2. **Response Validator in Dry-Run**

**Problema:** Il validator non applica correzioni automatiche.

**Raccomandazione:** Verificare se deve essere attivato o se è intenzionale.

**Codice:**

```python
def __init__(self, mode_config: dict, dry_run: bool = True):
    self.dry_run = dry_run  # Default: True
```

---

### 3. **Sanitizer Potrebbe Non Catturare Tutti i Pattern**

**Problema:** Pattern regex potrebbero non catturare tutte le variazioni.

**Raccomandazione:** Aggiungere test per verificare copertura pattern.

---

### 4. **Verification Service Non Sempre Chiamato**

**Problema:** Non è chiaro se il verification service viene chiamato sempre o solo in certi casi.

**Raccomandazione:** Verificare nel codice dell'orchestrator se viene chiamato.

---

## ✅ PUNTI DI FORZA

1. **Sistema Multi-Layer:** 5 sistemi di controllo qualità diversi
2. **ABSTAIN Mechanism:** Sistema rifiuta di rispondere se evidenza insufficiente
3. **Sanitization Aggressiva:** Rimuove molti artefatti comuni
4. **Prompt Rigoroso:** Regole molto specifiche per pricing, citazioni, linguaggio
5. **Trusted Tools:** Alcuni tool bypassano evidence check (corretto)

---

## 📈 METRICHE DA MONITORARE

1. **Evidence Score Distribution:** Quante risposte hanno score < 0.3, 0.3-0.6, > 0.6?
2. **ABSTAIN Rate:** Quante volte il sistema rifiuta di rispondere?
3. **Sanitizer Matches:** Quante volte il sanitizer trova pattern problematici?
4. **Validator Violations:** Quante violazioni vengono rilevate?
5. **Verification Failures:** Quante risposte falliscono la verifica?

---

## 🔧 RACCOMANDAZIONI

### Priorità Alta

1. **Verificare se Response Validator deve essere attivato**
   - Se sì, cambiare `dry_run=False` in produzione
   - Se no, documentare perché è in dry-run

2. **Monitorare Evidence Score Distribution**
   - Aggiungere metriche per tracciare distribuzione score
   - Alert se troppe risposte hanno score < 0.4

3. **Test Sanitizer Coverage**
   - Creare test suite per verificare che tutti i pattern siano catturati
   - Aggiungere nuovi pattern se necessario

### Priorità Media

4. **Considerare aumento threshold**
   - Valutare se 0.3 è troppo basso
   - Testare con threshold 0.4-0.5

5. **Verificare Verification Service Usage**
   - Assicurarsi che venga chiamato sempre
   - Documentare quando viene chiamato

### Priorità Bassa

6. **Aggiungere più pattern al sanitizer**
   - Monitorare risposte per nuovi pattern problematici
   - Aggiungere pattern man mano che vengono trovati

---

## 🧪 TEST DA ESEGUIRE

1. **Test Evidence Score:**
   - Query con evidenza forte → Score > 0.6
   - Query con evidenza debole → Score 0.3-0.6
   - Query senza evidenza → Score < 0.3 → ABSTAIN

2. **Test Sanitizer:**
   - Risposta con `[PRICE]` → Deve essere rimosso
   - Risposta con `THOUGHT:` → Deve essere rimosso
   - Risposta con "Non ho documenti" → Deve essere sostituita

3. **Test Pricing Rules:**
   - Query su prezzo → Deve chiamare `get_pricing`
   - Prezzo non nel tool → Deve dire "DA VERIFICARE"
   - Prezzo inventato → NON deve apparire

4. **Test Language Matching:**
   - Query in italiano → Risposta in italiano
   - Query in inglese → Risposta in inglese

5. **Test Greeting Rules:**
   - Primo messaggio → Può salutare
   - Messaggi successivi → NON deve salutare

---

## 📝 CONCLUSIONI

**Stato Generale:** ✅ **BUONO**

ZANTARA ha un sistema robusto di controllo qualità con **5 layer di protezione**. I sistemi sono attivi e funzionanti.

**Aree di Miglioramento:**

- Response Validator in dry-run (verificare se deve essere attivato)
- Threshold evidence score molto basso (considerare aumento)
- Monitoraggio metriche (aggiungere dashboard)

**Raccomandazione Finale:**

1. Verificare se Response Validator deve essere attivato
2. Aggiungere metriche per monitorare qualità
3. Eseguire test suite per verificare copertura

---

**Last Updated:** 2026-01-19
