# Feedback API - Guida all'Uso

## Endpoint: POST /api/feedback/rate-conversation

Salva un rating e feedback per una conversazione.

### Autenticazione

L'endpoint richiede autenticazione tramite:
- **API Key**: Header `X-API-Key: YOUR_API_KEY`
- **JWT Token**: Header `Authorization: Bearer YOUR_JWT_TOKEN`

### Request

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/feedback/rate-conversation \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "session_id": "f004b5aa-63cc-4bf2-879a-c8095afa505c",
    "rating": 5,
    "feedback_type": "positive",
    "feedback_text": "Ottima conversazione!",
    "turn_count": 10
  }'
```

### Parametri

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `session_id` | string (UUID) | ✅ Sì | ID della sessione conversazione |
| `rating` | integer (1-5) | ✅ Sì | Rating da 1 a 5 stelle |
| `feedback_type` | string | ❌ No | Tipo: `"positive"`, `"negative"`, o `"issue"` |
| `feedback_text` | string | ❌ No | Testo del feedback |
| `turn_count` | integer | ❌ No | Numero di turni nella conversazione |

### Response Success (200)

```json
{
  "success": true,
  "message": "Rating saved successfully",
  "rating_id": "b3e09724-0304-4c76-aa91-773d169e2b17"
}
```

### Response Error (400)

```json
{
  "detail": "Invalid session_id format: invalid-uuid"
}
```

### Response Error (401)

```json
{
  "detail": "Authentication required"
}
```

---

## Endpoint: GET /api/feedback/ratings/{session_id}

Recupera il rating per una specifica sessione conversazione.

### Autenticazione

Stesso sistema di autenticazione del POST endpoint.

### Request

```bash
curl https://nuzantara-rag.fly.dev/api/feedback/ratings/f004b5aa-63cc-4bf2-879a-c8095afa505c \
  -H "X-API-Key: YOUR_API_KEY"
```

### Response Success (200)

```json
{
  "success": true,
  "rating": {
    "rating_id": "b3e09724-0304-4c76-aa91-773d169e2b17",
    "session_id": "f004b5aa-63cc-4bf2-879a-c8095afa505c",
    "rating": 5,
    "feedback_type": "positive",
    "feedback_text": "Ottima conversazione!",
    "turn_count": 10,
    "created_at": "2025-01-22T10:30:00Z"
  }
}
```

### Response Error (404)

```json
{
  "detail": "Rating not found for this session"
}
```

---

## Integrazione Frontend

Il `FeedbackWidget` invia automaticamente i ratings quando l'utente fornisce feedback:

```typescript
// Mapping feedback_type → rating
const ratingMap = {
  positive: 5,
  negative: 2,
  issue: 3,
};

const response = await fetch('/api/feedback/rate-conversation', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    session_id: sessionId,
    rating: ratingMap[feedbackType],
    feedback_type: feedbackType,
    feedback_text: message,
    turn_count: turnCount,
  }),
});
```

---

## Utilizzo da ConversationTrainer

I ratings salvati vengono automaticamente utilizzati dal `ConversationTrainer` agent:

1. **Query Vista**: Il trainer interroga `v_rated_conversations` per ottenere conversazioni con rating >= 4
2. **Analisi Pattern**: Analizza i pattern di successo nelle conversazioni high-rated
3. **Miglioramento Prompt**: Genera miglioramenti ai prompt basati sui pattern trovati
4. **Creazione PR**: Crea automaticamente un PR con i miglioramenti

### Query Vista

```sql
SELECT 
    conversation_id,
    rating,
    client_feedback,
    messages,
    created_at
FROM v_rated_conversations
WHERE rating >= 4
  AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY rating DESC, created_at DESC
LIMIT 20;
```

---

## Test Locale

Per testare localmente senza autenticazione (solo sviluppo):

```python
import asyncio
import asyncpg
from uuid import uuid4

async def test_rating():
    conn = await asyncpg.connect("postgresql://user:pass@localhost:5432/db")
    try:
        session_id = uuid4()
        rating_id = await conn.fetchval('''
            INSERT INTO conversation_ratings (
                session_id, rating, feedback_type, feedback_text, turn_count
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id::text
        ''', session_id, 5, 'positive', 'Test feedback', 10)
        print(f"Rating ID: {rating_id}")
    finally:
        await conn.close()

asyncio.run(test_rating())
```

---

## Note Importanti

1. **Session ID**: Deve essere un UUID valido
2. **Rating**: Solo valori da 1 a 5 sono accettati
3. **Feedback Type**: Se fornito, deve essere uno di: `"positive"`, `"negative"`, `"issue"`
4. **High-Rated**: Solo conversazioni con rating >= 4 vengono incluse nella vista `v_rated_conversations`
5. **Messages**: I messaggi vengono aggregati automaticamente dalla tabella `conversation_history` quando disponibile

---

**Ultimo aggiornamento**: 2025-01-22

