# ZANTARA Fluidity and Strength Documentation

**Data:** 2026-01-19  
**Status:** ✅ Production Ready  
**Scope:** Miglioramenti per fluidità e proattività di ZANTARA

---

## 🎯 OBIETTIVO

Rendere ZANTARA più fluida (risponde spesso) e forte (proattiva, suggerisce sempre prossimi passi).

---

## ✅ MIGLIORAMENTI IMPLEMENTATI

### 1. Fluidità (Low ABSTAIN Rate)

#### Threshold ABSTAIN abbassato: 0.3 → 0.2

**File:** `apps/backend-rag/backend/app/core/constants.py`

```python
class EvidenceScoreConstants:
    ABSTAIN_THRESHOLD = 0.2  # Increased from 0.3
```

**Effetto:**

- ZANTARA risponde più spesso invece di rifiutare
- Solo evidenza molto debole (< 0.2) porta ad ABSTAIN
- Maggiore fluidità nella conversazione

#### Messaggio ABSTAIN più proattivo

**File:** `apps/backend-rag/backend/services/rag/agentic/reasoning.py`

**Prima:**

```
"Mi dispiace, non ho trovato informazioni verificate sufficienti
nei documenti ufficiali per rispondere alla tua domanda specifica.
Posso aiutarti con altro?"
```

**Ora:**

```
"Per questa domanda specifica non ho informazioni verificate sufficienti nei documenti ufficiali.
Posso aiutarti con:
• Informazioni su visti e KITAS
• Setup aziendale (PT PMA)
• Questioni fiscali e legali
• Procedure e documentazione

Prova a riformulare la domanda o chiedi qualcosa di più specifico!"
```

**Effetto:**

- Suggerisce alternative concrete invece di solo "altro?"
- Guida l'utente verso argomenti disponibili
- Più utile e proattivo

### 2. Proattività (Always Suggest Next Steps)

#### Proattività nel prompt

**File:** `apps/backend-rag/backend/services/rag/agentic/prompt_builder.py`

**Aggiunto al role:**

```
4. **PROACTIVITY:** Always suggest next steps or related topics. Be helpful and anticipatory.

**PROACTIVITY RULES:**
- After answering, ALWAYS suggest 1-2 related topics or next steps naturally
- Examples: "Vuoi sapere anche quanto costa?" / "Ti interessa anche il processo di estensione?" / "Posso spiegarti anche i requisiti documentali"
- Be anticipatory: Think about what the user might need next based on their question
- Make suggestions feel natural, not forced
```

**Effetto:**

- ZANTARA suggerisce sempre prossimi passi dopo ogni risposta
- Suggerimenti naturali e contestuali
- Migliore engagement dell'utente

#### Final prompt include suggerimenti

**File:** `apps/backend-rag/backend/services/rag/agentic/reasoning.py`

**Aggiunto al final prompt:**

```
IMPORTANT: After your answer, naturally suggest 1-2 related topics or next steps that might be helpful.
Examples: "Vuoi sapere anche quanto costa?" / "Ti interessa anche il processo completo?" / "Posso spiegarti anche i requisiti documentali"
Make it feel natural and helpful, not forced.
```

**Effetto:**

- Ogni risposta include suggerimenti per prossimi passi
- Migliore esperienza utente
- Conversazione più fluida

### 3. Warning migliorato per evidenza moderata

**File:** `apps/backend-rag/backend/services/rag/agentic/reasoning.py`

**Prima:**

- Range: 0.3-0.6
- Linguaggio negativo: "limited information"

**Ora:**

- Range: 0.2-0.5
- Linguaggio positivo: "available information"
- Istruzioni per suggerire prossimi passi anche con evidenza moderata

**Effetto:**

- Risposte più utili anche quando evidenza non è perfetta
- Linguaggio più confidente
- Suggerimenti anche con evidenza moderata

---

## 📊 FOLLOWUPSERVICE - LOGGING E METRICHE

### Logging strutturato completo

**File:** `apps/backend-rag/backend/services/misc/followup_service.py`

**Caratteristiche:**

- Structured logging con `extra` fields
- Tracciamento richieste con ID sequenziale
- Logging durata, metodo, topic, language
- Logging errori con stack trace completo

**Esempio:**

```python
logger.info(
    f"✅ [Followups] Generated {len(result)} follow-ups in {duration:.3f}s",
    extra={
        "component": "FollowupService",
        "action": "get_followups_complete",
        "request_id": self._total_requests,
        "method": method,
        "status": status,
        "topic": topic,
        "language": language,
        "followup_count": len(result),
        "duration_seconds": duration,
    },
)
```

### Metriche Prometheus aggiunte

**4 nuove metriche:**

1. **`zantara_followup_requests_total`**
   - Labels: `method`, `topic`, `language`, `status`
   - Traccia ogni richiesta di follow-up

2. **`zantara_followup_generation_duration_seconds`**
   - Histogram con buckets ottimizzati
   - Labels: `method`, `topic`, `language`

3. **`zantara_followup_ai_generation_total`**
   - Labels: `status` (success, error, parse_failure, ai_unavailable)
   - Traccia successi/fallimenti AI

4. **`zantara_followup_topic_based_total`**
   - Labels: `topic`, `language`
   - Traccia uso del fallback topic-based

### Health check migliorato

**Include statistiche aggregate:**

```python
{
    "status": "healthy",
    "ai_available": bool,
    "features": {...},
    "metrics": {
        "total_requests": int,
        "ai_generation_count": int,
        "fallback_count": int,
        "ai_usage_rate": float,  # 0.0-1.0
    },
}
```

---

## 🧪 TEST COVERAGE

### Test esistenti

- **File:** `apps/backend-rag/backend/tests/unit/services/misc/test_followup_service.py`
- **30+ test** per funzionalità base
- **Coverage target:** >95%

### Nuovi test creati

#### 1. Test per logging e metriche

**File:** `apps/backend-rag/backend/tests/unit/services/misc/test_followup_service_metrics.py`

- **13 nuovi test** per logging e metriche
- TestFollowupServiceMetrics (7 test)
- TestFollowupServiceLogging (3 test)
- TestFollowupServiceHealthCheck (3 test)

#### 2. Test per fluidità e forza

**File:** `apps/backend-rag/backend/tests/integration/zantara/test_fluidity_and_strength_simple.py`

- **14 test** per verificare fluidità e proattività
- TestZantaraFluidity (3 test)
- TestZantaraStrength (5 test)
- TestZantaraProactivity (3 test)
- TestZantaraEvidenceScore (2 test)
- TestZantaraIntegration (1 test)

**Risultato:** ✅ Tutti i test passano (14/14)

---

## 📋 CONFIGURAZIONE TEST

### File creati

1. **`apps/backend-rag/backend/tests/unit/services/misc/conftest.py`**
   - Configurazione test con mock Settings
   - Variabili d'ambiente di test
   - Prevenzione errori di validazione Pydantic

2. **`apps/backend-rag/.env.example`**
   - Template per configurazione (committato)
   - Nessun valore reale

3. **`apps/backend-rag/.env.test`**
   - Configurazione test con valori mock (committato)
   - Sicuro da committare

### Best Practices

**Documentazione:** `docs/TEST_CONFIGURATION_BEST_PRACTICES.md`

**Regole:**

- ✅ Mai configurazioni reali nei test (anche con venv)
- ✅ Mock sempre valori di test
- ✅ Separazione ambienti (Dev/Staging/Prod)
- ✅ Secrets Manager per produzione

---

## 🎯 RISULTATI ATTESI

### Fluidità

- ✅ Risponde più spesso (threshold 0.2)
- ✅ Meno "non so" / ABSTAIN
- ✅ Conversazione più naturale

### Proattività

- ✅ Suggerisce sempre prossimi passi
- ✅ Messaggi ABSTAIN più utili
- ✅ Migliore engagement utente

### Monitoraggio

- ✅ Metriche Prometheus per follow-up
- ✅ Logging strutturato completo
- ✅ Health check con statistiche

---

## 📊 METRICHE DA MONITORARE

### Prometheus Metrics

```promql
# Tasso di ABSTAIN (dovrebbe diminuire)
rate(zantara_rag_abstain_total[5m])

# Follow-up generati
rate(zantara_followup_requests_total[5m])

# Successo AI vs fallback
rate(zantara_followup_ai_generation_total{status="success"}[5m])
rate(zantara_followup_ai_generation_total{status="fallback"}[5m])

# Durata generazione follow-up
histogram_quantile(0.95, zantara_followup_generation_duration_seconds)
```

### Log Analysis

Cercare nei log:

- `[Followups]` - Logging follow-up service
- `[Proactive]` - Suggerimenti proattivi
- `[Uncertainty]` - ABSTAIN triggers
- `evidence_score` - Score di evidenza

---

## 🔍 VERIFICA

### Test di verifica

```bash
# Test fluidità e forza
cd apps/backend-rag/backend
pytest tests/integration/zantara/test_fluidity_and_strength_simple.py -v

# Test follow-up service
pytest tests/unit/services/misc/test_followup_service_metrics.py -v

# Test coverage
pytest tests/unit/services/misc/test_followup_service.py --cov=backend.services.misc.followup_service --cov-report=term-missing
```

### Verifica manuale

1. **Test ABSTAIN threshold:**

   ```python
   from backend.app.core.constants import EvidenceScoreConstants
   assert EvidenceScoreConstants.ABSTAIN_THRESHOLD == 0.2
   ```

2. **Test messaggio ABSTAIN:**
   - Verificare che includa "Posso aiutarti con:"
   - Verificare che suggerisca alternative concrete

3. **Test proattività:**
   - Verificare che ogni risposta includa suggerimenti
   - Verificare che suggerimenti siano naturali

---

## 📝 FILE MODIFICATI

### Core

- `apps/backend-rag/backend/app/core/constants.py` - Threshold ABSTAIN
- `apps/backend-rag/backend/services/rag/agentic/reasoning.py` - Messaggio ABSTAIN, final prompt
- `apps/backend-rag/backend/services/rag/agentic/prompt_builder.py` - Regole PROACTIVITY

### FollowupService

- `apps/backend-rag/backend/services/misc/followup_service.py` - Logging e metriche

### Test

- `apps/backend-rag/backend/tests/unit/services/misc/test_followup_service_metrics.py` - Nuovo
- `apps/backend-rag/backend/tests/integration/zantara/test_fluidity_and_strength_simple.py` - Nuovo
- `apps/backend-rag/backend/tests/unit/services/misc/conftest.py` - Nuovo

### Configurazione

- `apps/backend-rag/.env.example` - Nuovo
- `apps/backend-rag/.env.test` - Nuovo
- `.gitignore` - Aggiornato

### Documentazione

- `docs/TEST_CONFIGURATION_BEST_PRACTICES.md` - Nuovo
- `docs/ZANTARA_FLUIDITY_AND_STRENGTH.md` - Questo documento

---

## ✅ STATO FINALE

**ZANTARA è ora:**

- ✅ **Fluida:** Risponde spesso (threshold 0.2)
- ✅ **Proattiva:** Suggerisce sempre prossimi passi
- ✅ **Monitorata:** Metriche e logging completi
- ✅ **Testata:** 57+ test, tutti passano
- ✅ **Documentata:** Best practices e guide complete

**Production Ready:** ✅

---

**Last Updated:** 2026-01-19
