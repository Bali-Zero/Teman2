# Production Test Checklist - Conversation Persistence

**Data**: 2026-02-09  
**Status**: ✅ FATTO - Pronto per test produzione

---

## ✅ Implementazione Completata

### Backend
- [x] `conversation_repository.py` creato
- [x] Integrato in `webhook_chat.py` (lines 17, 89, 193, 227)
- [x] Table `conversations` in baseline migration
- [x] Router registrato in `router_registration.py`
- [x] Cleanup job integrato in `autonomous_scheduler.py`
- [x] Tests creati

### Frontend (Da integrare)
- [x] `webhook-chat.api.ts` creato
- [x] `useConversationPersistence.ts` creato
- [ ] Chat component aggiornato
- [ ] Deploy frontend

---

## 🧪 Test Produzione

### Opzione 1: Script Automatico

```bash
# Esporta il tuo JWT token
export JWT_TOKEN="your-production-jwt-token"

# Esegui test
cd apps/backend-rag
./scripts/test_production.sh
```

### Opzione 2: Test Manuale

```bash
# 1. Health check
curl https://nuzantara-rag.fly.dev/api/health

# 2. Invia messaggio
curl -X POST https://nuzantara-rag.fly.dev/webhook/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "query": "Ciao, come ti chiami?",
    "session_id": "test-session-123",
    "metadata": {"test": true}
  }'

# Verifica risposta:
# - "persisted": true ✅
# - "conversation_id": <numero> ✅

# 3. Invia follow-up
curl -X POST https://nuzantara-rag.fly.dev/webhook/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "query": "Ricordi come ti chiami?",
    "session_id": "test-session-123",
    "metadata": {"test": true}
  }'

# Verifica che l'AI ricordi il contesto ✅

# 4. Recupera history
curl https://nuzantara-rag.fly.dev/webhook/chat/history/test-session-123 \
  -H "Authorization: Bearer $JWT_TOKEN"

# Verifica che ci siano almeno 4 messaggi ✅
```

---

## 🔍 Verifica Database

```bash
# SSH nel container
flyctl ssh console -a nuzantara-rag

# Connetti al database
psql $DATABASE_URL

# Verifica conversazioni recenti
SELECT 
    id,
    session_id,
    user_id,
    jsonb_array_length(messages) as msg_count,
    created_at
FROM conversations
ORDER BY created_at DESC
LIMIT 10;

# Verifica sessione specifica
SELECT 
    messages,
    metadata
FROM conversations
WHERE session_id = 'test-session-123';
```

---

## 📊 Metriche da Verificare

### Performance
- [ ] Query time < 50ms
- [ ] Persistence rate = 100%
- [ ] No errors in logs

### Funzionalità
- [ ] Messaggio salvato in DB
- [ ] conversation_id ritornato
- [ ] History recuperabile
- [ ] Context mantenuto tra richieste

### Cleanup Job
```bash
# Verifica che il job sia attivo
flyctl logs -a nuzantara-rag | grep "Conversation cleanup"

# Dovrebbe vedere:
# "✅ Conversation Cleanup registered (24h interval)"
```

---

## 🐛 Troubleshooting

### "persisted": false

**Causa possibile:**
- Database connection issue
- JWT token invalido
- session_id mancante

**Debug:**
```bash
flyctl logs -a nuzantara-rag | grep "Failed to save"
```

### Context non mantenuto

**Causa possibile:**
- session_id diverso tra richieste
- History non recuperata

**Debug:**
```bash
flyctl logs -a nuzantara-rag | grep "Retrieved.*messages"
```

### Cleanup job non attivo

**Debug:**
```bash
# Verifica scheduler
flyctl logs -a nuzantara-rag | grep "autonomous"

# Run manuale
flyctl ssh console -a nuzantara-rag
python -m backend.jobs.conversation_cleanup
```

---

## 📝 Prossimi Passi

### 1. Test Backend (ADESSO)
```bash
export JWT_TOKEN="your-token"
./scripts/test_production.sh
```

### 2. Aggiorna Frontend
```typescript
// Nel tuo chat component
import { useConversationPersistence } from '@/hooks/useConversationPersistence';
import { WebhookChatApi } from '@/lib/api/chat/webhook-chat.api';

const { sessionId } = useConversationPersistence();
const webhookApi = new WebhookChatApi(apiClient);

// Usa webhookApi.sendMessage() invece del vecchio endpoint
```

### 3. Deploy Frontend
```bash
cd apps/mouth
pnpm build
vercel --prod
```

### 4. Test End-to-End
1. Apri webapp
2. Invia messaggio
3. Refresh pagina (F5)
4. Invia follow-up
5. Verifica che l'AI ricordi ✅

---

## ✅ Criteri di Successo

Il sistema funziona quando:
- [x] Backend deployed
- [ ] Test produzione passati
- [ ] Database mostra conversazioni
- [ ] Frontend integrato
- [ ] Page refresh mantiene conversazione
- [ ] Context awareness funzionante
- [ ] Cleanup job attivo

---

## 🎯 Comando Rapido

```bash
# Test completo in un comando
export JWT_TOKEN="your-token" && \
cd apps/backend-rag && \
./scripts/test_production.sh
```

**Risultato atteso**: Tutti i test ✅ verdi

---

## 📞 Support

**Logs:**
```bash
flyctl logs -a nuzantara-rag
```

**Database:**
```bash
flyctl ssh console -a nuzantara-rag
psql $DATABASE_URL
```

**Docs:**
- `DEPLOYMENT_GUIDE.md` - Guida completa
- `QUICK_START.md` - 3 passi rapidi
- `apps/backend-rag/backend/docs/CONVERSATION_PERSISTENCE.md` - API docs

---

**Pronto per il test?** Esegui `./scripts/test_production.sh` 🚀
