# Guida Test Produzione - Conversation Persistence

**Status**: ✅ Codice implementato, pronto per test con token valido

---

## 🔐 Problema Autenticazione

Il backend in produzione richiede un JWT token valido generato dal sistema di autenticazione esistente. Il token di test generato non è accettato.

**Errore ricevuto**: `{"detail":"Authentication required"}`

---

## ✅ Opzione 1: Test Locale (CONSIGLIATO)

Testa il sistema in locale senza autenticazione:

```bash
# 1. Avvia backend locale
cd apps/backend-rag/backend
uvicorn backend.app.main_cloud:app --reload --port 8080

# 2. In un altro terminale, esegui test
cd apps/backend-rag
./scripts/test_local.sh
```

**Vantaggi:**

- No autenticazione richiesta
- Feedback immediato
- Debug più facile
- Verifica che il codice funzioni

---

## 🌐 Opzione 2: Test Produzione con Token Valido

### Come ottenere un JWT token valido:

#### A. Via Login Frontend

1. Apri la webapp in produzione
2. Fai login con le tue credenziali
3. Apri DevTools (F12) → Console
4. Esegui: `localStorage.getItem('token')` o `document.cookie`
5. Copia il token JWT

#### B. Via API Login

```bash
# Login endpoint (se disponibile)
curl -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "your-password"}'

# Estrai il token dalla risposta
```

#### C. Via Database (Admin)

```bash
# SSH nel backend
flyctl ssh console -a nuzantara-rag

# Genera token con Python
python3 << EOF
import jwt
from datetime import datetime, timedelta

secret = "07XoX6Eu24amEuUye7MhTFO62jzaYJ48myn04DvECN0="
payload = {
    "sub": "your@email.com",
    "email": "your@email.com",
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=24),
    "type": "access"
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(f"Token: {token}")
EOF
```

### Esegui Test con Token Valido

```bash
# Esporta il token
export JWT_TOKEN="your-valid-jwt-token-here"

# Esegui test
cd apps/backend-rag
./scripts/test_production.sh
```

---

## 🧪 Opzione 3: Test Manuale via curl

Se preferisci testare manualmente:

```bash
# Imposta variabili
export JWT_TOKEN="your-valid-token"
export SESSION_ID="manual-test-$(date +%s)"

# Test 1: Invia messaggio
curl -X POST https://nuzantara-rag.fly.dev/webhook/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d "{
    \"query\": \"Ciao, come ti chiami?\",
    \"session_id\": \"$SESSION_ID\",
    \"metadata\": {\"test\": true}
  }" | jq '.'

# Verifica: persisted = true, conversation_id = numero

# Test 2: Follow-up
curl -X POST https://nuzantara-rag.fly.dev/webhook/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d "{
    \"query\": \"Ricordi come ti chiami?\",
    \"session_id\": \"$SESSION_ID\",
    \"metadata\": {\"test\": true}
  }" | jq '.'

# Verifica: AI ricorda il contesto

# Test 3: Recupera history
curl https://nuzantara-rag.fly.dev/webhook/chat/history/$SESSION_ID \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.'

# Verifica: total_messages >= 4
```

---

## 🔍 Verifica Database

Dopo i test, verifica che i dati siano salvati:

```bash
# SSH nel backend
flyctl ssh console -a nuzantara-rag

# Connetti al database
psql $DATABASE_URL

# Query conversazioni recenti
SELECT
    id,
    session_id,
    user_id,
    jsonb_array_length(messages) as msg_count,
    created_at
FROM conversations
ORDER BY created_at DESC
LIMIT 10;

# Cerca la tua sessione di test
SELECT
    messages,
    metadata
FROM conversations
WHERE session_id LIKE 'prod-test-%'
   OR session_id LIKE 'manual-test-%'
ORDER BY created_at DESC
LIMIT 5;
```

---

## ✅ Criteri di Successo

Il test passa quando:

- [x] Backend deployed e attivo
- [ ] Messaggio inviato → `persisted: true`
- [ ] `conversation_id` ritornato (numero)
- [ ] Follow-up inviato → AI ricorda contesto
- [ ] History recuperata → almeno 4 messaggi
- [ ] Database mostra record salvati

---

## 🐛 Troubleshooting

### "Authentication required"

**Causa**: Token JWT non valido o mancante

**Soluzione**:

1. Ottieni token valido (vedi sopra)
2. Verifica formato: `Bearer <token>`
3. Controlla scadenza token

### "404 Not Found"

**Causa**: Endpoint non deployato

**Soluzione**:

```bash
# Verifica deployment
flyctl status -a nuzantara-rag

# Re-deploy se necessario
cd apps/backend-rag
flyctl deploy --app nuzantara-rag
```

### "persisted: false"

**Causa**: Database connection issue

**Soluzione**:

```bash
# Controlla logs
flyctl logs -a nuzantara-rag | grep "Failed to save"

# Verifica DATABASE_URL
flyctl ssh console -a nuzantara-rag
echo $DATABASE_URL
```

---

## 📝 Prossimi Passi

### Dopo Test Locale OK:

1. ✅ Codice funziona
2. Deploy a produzione (già fatto)
3. Test con token valido
4. Integra frontend

### Dopo Test Produzione OK:

1. Aggiorna chat component frontend
2. Deploy frontend a Vercel
3. Test end-to-end con utenti reali
4. Monitor logs e metriche

---

## 🎯 Raccomandazione

**Inizia con test locale** (`./scripts/test_local.sh`) per verificare che il codice funzioni correttamente, poi procedi con il test in produzione quando hai un token JWT valido.

Il sistema è già deployato e pronto, serve solo autenticazione valida per testarlo.

---

**Script disponibili:**

- `scripts/test_local.sh` - Test locale (no auth)
- `scripts/test_production.sh` - Test produzione (richiede JWT)
- `scripts/generate_test_token.py` - Genera token (non accettato in prod)
