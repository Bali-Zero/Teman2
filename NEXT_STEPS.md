# Next Steps - Conversation Persistence

**Situazione**: ✅ Codice implementato, endpoint deployato, JWT_SECRET diverso in produzione (corretto)

---

## 🎯 Azione Immediata

### Test Locale (5 minuti)

```bash
# Terminal 1: Avvia backend locale
cd apps/backend-rag/backend
uvicorn backend.app.main_cloud:app --reload --port 8080

# Terminal 2: Esegui test
cd apps/backend-rag
./scripts/test_local.sh
```

**Questo verificherà:**
- ✅ Endpoint `/webhook/chat` funziona
- ✅ Messaggi vengono salvati in DB
- ✅ History viene recuperata
- ✅ Context viene mantenuto

---

## 📋 Dopo Test Locale OK

### 1. Per Produzione
Hai 2 opzioni:

**A. Ottieni token valido da webapp**
```javascript
// Login nella webapp → DevTools Console
localStorage.getItem('auth_token')
```

**B. Aggiungi `/webhook/chat` agli endpoint pubblici** (se appropriato)
```python
# backend/middleware/hybrid_auth.py
PUBLIC_PATHS = [
    "/docs",
    "/webhook/chat",  # <-- Aggiungi
]
```

### 2. Integra Frontend

**File da modificare**: Il tuo chat component (es. `apps/mouth/src/app/chat/page.tsx`)

```typescript
import { useConversationPersistence } from '@/hooks/useConversationPersistence';
import { WebhookChatApi } from '@/lib/api/chat/webhook-chat.api';

export function ChatPage() {
  const { sessionId } = useConversationPersistence();
  const webhookApi = new WebhookChatApi(apiClient);

  const handleSend = async (message: string) => {
    const response = await webhookApi.sendMessage(
      message,
      sessionId,
      { source: 'webapp' }
    );
    // Usa response.answer per UI
    // response.persisted conferma salvataggio
  };
}
```

### 3. Deploy Frontend
```bash
cd apps/mouth
pnpm build
vercel --prod
```

### 4. Test End-to-End
1. Invia messaggio
2. Refresh pagina (F5)
3. Invia follow-up
4. Verifica che AI ricordi ✅

---

## 📊 Stato Attuale

### ✅ Completato
- Backend implementato (repository, router, cleanup)
- Frontend API client e hook creati
- Tests e documentazione pronti
- Endpoint deployato in produzione

### ⏳ Da Fare
- Test locale per verifica
- Integrazione frontend
- Deploy frontend
- Test end-to-end con utenti

---

## 🔍 Perché JWT Non Funziona in Produzione

**È corretto!** Il `JWT_SECRET_KEY` in produzione è diverso da quello in `.env` locale per sicurezza.

**Logs produzione**:
```
"JWT validation failed: Signature verification failed."
"Authentication failed for: /webhook/chat"
```

Questo significa:
- ✅ Endpoint esiste e risponde
- ✅ Middleware auth funziona
- ❌ Token generato con secret locale non valido per produzione

**Soluzione**: Usa token valido da webapp o testa in locale.

---

## 🚀 Comando Rapido

```bash
# Test tutto in locale (RACCOMANDATO)
cd apps/backend-rag/backend && \
uvicorn backend.app.main_cloud:app --reload --port 8080 &
sleep 5 && \
cd .. && ./scripts/test_local.sh
```

---

**Pronto per testare?** Avvia il backend locale e esegui `./scripts/test_local.sh` 🎯
