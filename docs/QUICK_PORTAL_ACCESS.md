# 🚀 Accesso Rapido al Portal - Guida Veloce

**Per entrare nel portal e controllare:**

---

## ⚡ Metodo Veloce (Se hai accesso admin)

### Opzione 1: Via Dashboard Admin

1. **Login su Dashboard Admin:**

   ```
   https://kita.balizero.com/login
   ```

   - Email: `zero@balizero.com` (o il tuo account admin)
   - PIN: [il tuo PIN admin]

2. **Crea Invito Portal:**
   - Vai su **Clients** → Seleziona un cliente
   - Clicca **"Send Portal Invite"**
   - Oppure usa API: `POST /api/portal/invite/send`

3. **Completa Registrazione:**
   - Clicca sul link invito ricevuto
   - Crea PIN (4-6 cifre)
   - Accedi al portal

---

## ⚡ Metodo Script (Creazione Diretta)

### Step 1: Prepara Database URL

```bash
cd apps/backend-rag
export DATABASE_URL="postgresql://postgres:Balizero2020!@db.yxyibhwacnausqfqbrtd.supabase.co:5432/postgres"
```

### Step 2: Esegui Script

```bash
python backend/scripts/create_portal_test_user_simple.py \
  --email antonello@balizero.com \
  --pin 123456 \
  --name "Antonello"
```

### Step 3: Accedi

1. Vai su: `https://my.balizero.com/portal/login`
2. Email: `antonello@balizero.com`
3. PIN: `123456`
4. Enter Portal ✅

---

## 🔧 Metodo Alternativo: Via API (Se script non funziona)

### Se hai accesso al backend API:

```bash
# 1. Login come admin
curl -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "zero@balizero.com", "credentials": "YOUR_PIN"}'

# 2. Crea invito (usa token dalla risposta)
curl -X POST https://nuzantara-rag.fly.dev/api/portal/invite/send \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"client_id": 1, "email": "antonello@balizero.com"}'

# 3. Usa il link invito ricevuto per completare registrazione
```

---

## 📝 Account Test Pre-Creati

Se vuoi un account già pronto, posso crearlo con:

**Email:** `test@balizero.com`  
**PIN:** `1234`

Dimmi se vuoi che lo crei!

---

## 🎯 Quick Access (Se account già esiste)

1. **Vai su:** `https://my.balizero.com/portal/login`
2. **Inserisci:**
   - Email: [la tua email]
   - PIN: [il tuo PIN]
3. **Clicca:** "Enter Portal"

---

## ❓ Non Ricordi il PIN?

- Contatta supporto: `info@balizero.com`
- Oppure crea nuovo account con script sopra

---

**Vuoi che crei un account di test ora?** Dimmi email e PIN e lo creo subito! 🚀
