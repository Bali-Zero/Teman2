# ConversationTrainer - Setup e Verifica

## ✅ Implementazione Completata

Tutti i componenti sono stati implementati:

1. ✅ **Migration 025** - Tabella `conversation_ratings` e vista `v_rated_conversations`
2. ✅ **API Router** - Endpoint `/api/feedback/rate-conversation`
3. ✅ **Scheduler Fix** - Flusso completo `analyze → generate → create_pr`
4. ✅ **ConversationTrainer** - Query aggiornata per usare `v_rated_conversations`
5. ✅ **Frontend Integration** - FeedbackWidget collegato al backend
6. ✅ **Test** - Test API e unit test aggiornati

---

## 🚀 Prossimi Passi

### Step 1: Eseguire Migration

**In Produzione (Fly.io):**
```bash
# Connessione al database Fly.io
fly proxy 15432:5432 -a nuzantara-postgres &

# Esegui migration
export DATABASE_URL="postgresql://user:pass@localhost:15432/nuzantara_db"
python apps/backend-rag/backend/migrations/migration_025.py
```

**In Sviluppo Locale:**
```bash
# Configura DATABASE_URL
export DATABASE_URL="postgresql://user:pass@localhost:5432/nuzantara_db"

# Esegui migration
python apps/backend-rag/backend/migrations/migration_025.py
```

**Verifica Migration:**
```sql
-- Verifica tabella
SELECT COUNT(*) FROM conversation_ratings;

-- Verifica vista
SELECT * FROM v_rated_conversations LIMIT 5;

-- Verifica indici
SELECT indexname FROM pg_indexes WHERE tablename = 'conversation_ratings';
```

---

### Step 2: Verificare API Endpoint

**Test con curl:**
```bash
# Genera un session_id valido (UUID)
SESSION_ID=$(python -c "import uuid; print(uuid.uuid4())")

# Test rating positivo
curl -X POST http://localhost:8080/api/feedback/rate-conversation \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"rating\": 5,
    \"feedback_type\": \"positive\",
    \"feedback_text\": \"Ottima conversazione!\",
    \"turn_count\": 10
  }"

# Verifica rating salvato
curl http://localhost:8080/api/feedback/ratings/$SESSION_ID \
  -H "X-API-Key: YOUR_API_KEY"
```

**Risposta attesa:**
```json
{
  "success": true,
  "message": "Rating saved successfully",
  "rating_id": "uuid-here"
}
```

---

### Step 3: Test Frontend

1. Avvia frontend: `cd apps/mouth && npm run dev`
2. Apri chat e fai almeno 8 messaggi
3. Il FeedbackWidget dovrebbe apparire automaticamente
4. Invia feedback positivo/negativo/issue
5. Verifica nel database che il rating sia salvato:
   ```sql
   SELECT * FROM conversation_ratings ORDER BY created_at DESC LIMIT 1;
   ```

---

### Step 4: Verificare Scheduler

**Trigger Manuale (per test):**
```bash
curl -X POST http://localhost:8080/api/autonomous-agents/conversation-trainer/run?days_back=7 \
  -H "X-API-Key: YOUR_API_KEY"
```

**Verifica Status:**
```bash
curl http://localhost:8080/api/autonomous-agents/scheduler/status \
  -H "X-API-Key: YOUR_API_KEY"
```

**Verifica Logs:**
```bash
# Backend logs
fly logs --app nuzantara-rag | grep "Conversation Trainer"

# O in locale
tail -f logs/backend.log | grep "Conversation Trainer"
```

**Log attesi:**
```
🎓 Conversation Trainer found X patterns
✅ Generated improved prompt from conversation analysis
✅ Conversation Trainer: PR auto/prompt-improvement-YYYYMMDD-HHMM created
```

---

### Step 5: Verifica End-to-End

**Scenario completo:**

1. **Crea conversazione con rating alto:**
   ```sql
   -- Inserisci rating manualmente per test
   INSERT INTO conversation_ratings (session_id, rating, feedback_text, turn_count)
   VALUES (
     '00000000-0000-0000-0000-000000000001'::uuid,
     5,
     'Ottima risposta!',
     10
   );
   ```

2. **Assicurati che ci siano messaggi in conversation_history:**
   ```sql
   SELECT COUNT(*) FROM conversation_history 
   WHERE session_id = '00000000-0000-0000-0000-000000000001'::uuid;
   ```

3. **Esegui ConversationTrainer:**
   ```bash
   curl -X POST http://localhost:8080/api/autonomous-agents/conversation-trainer/run?days_back=7 \
     -H "X-API-Key: YOUR_API_KEY"
   ```

4. **Verifica risultato:**
   - Controlla logs per vedere se PR è stato creato
   - Verifica branch git: `git branch | grep auto/prompt-improvement`

---

## 🔍 Script di Verifica

Esegui lo script di verifica completo:

```bash
python apps/backend-rag/scripts/verify_conversation_trainer_setup.py
```

Questo script verifica:
- ✅ Struttura file migration
- ✅ Router API registrato
- ✅ Scheduler configurato
- ✅ Database (se DATABASE_URL configurato)

---

## 📊 Monitoraggio

**Metriche da monitorare:**

1. **Ratings salvati:**
   ```sql
   SELECT 
     rating,
     COUNT(*) as count,
     AVG(turn_count) as avg_turns
   FROM conversation_ratings
   GROUP BY rating
   ORDER BY rating DESC;
   ```

2. **High-rated conversations disponibili:**
   ```sql
   SELECT COUNT(*) FROM v_rated_conversations;
   ```

3. **ConversationTrainer executions:**
   ```bash
   curl http://localhost:8080/api/autonomous-agents/executions?limit=10 \
     -H "X-API-Key: YOUR_API_KEY"
   ```

---

## 🐛 Troubleshooting

### Problema: Migration fallisce

**Errore:** `DATABASE_URL not configured`
**Soluzione:** 
```bash
export DATABASE_URL="postgresql://user:pass@host:port/db"
```

### Problema: Vista vuota

**Causa:** Nessun rating >= 4 salvato
**Soluzione:** 
- Verifica che ci siano ratings nella tabella
- Verifica che ci siano messaggi in `conversation_history` per quei session_id

### Problema: API ritorna 503

**Causa:** Database pool non disponibile
**Soluzione:** 
- Verifica che backend sia avviato
- Verifica che `app.state.db_pool` sia inizializzato

### Problema: Scheduler non esegue

**Causa:** Scheduler non avviato o task disabilitato
**Soluzione:**
```bash
# Verifica status
curl http://localhost:8080/api/autonomous-agents/scheduler/status

# Abilita task se disabilitato
curl -X POST http://localhost:8080/api/autonomous-agents/scheduler/task/conversation_trainer/enable
```

---

## ✅ Checklist Finale

Prima di considerare il setup completo:

- [ ] Migration 025 eseguita con successo
- [ ] Tabella `conversation_ratings` creata
- [ ] Vista `v_rated_conversations` creata
- [ ] API endpoint `/api/feedback/rate-conversation` risponde correttamente
- [ ] Frontend FeedbackWidget salva rating nel backend
- [ ] Scheduler esegue ConversationTrainer ogni 6h
- [ ] ConversationTrainer crea PR con miglioramenti prompt
- [ ] Test passano: `pytest tests/api/test_feedback_endpoints.py -v`

---

**Ultimo aggiornamento:** 2025-01-22  
**Status:** ✅ Implementazione Completa

