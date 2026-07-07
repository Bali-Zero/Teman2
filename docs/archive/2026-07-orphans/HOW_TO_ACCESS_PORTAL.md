# 🔐 Come Entrare nel Portal Clienti

**URL:** `https://my.balizero.com/portal/login`

---

## 🎯 Metodo 1: Se Hai Già un Account

### Accesso Diretto

1. **Vai su:** `https://my.balizero.com/portal/login`
2. **Inserisci Email:** La tua email registrata
3. **Inserisci PIN:** Il tuo PIN (4-6 cifre)
4. **Clicca:** "Enter Portal"

**Se non ricordi il PIN:** Contatta supporto o crea nuovo account (vedi Metodo 2)

---

## 🎯 Metodo 2: Creare Nuovo Account

### Opzione A: Via Dashboard Admin (Consigliato)

1. **Login su Dashboard Admin:**

   ```
   https://kita.balizero.com/login
   ```

   - Usa le tue credenziali admin

2. **Crea Invito:**
   - Vai su **Clients** → Seleziona cliente (o creane uno)
   - Clicca **"Send Portal Invite"**
   - Inserisci email dove vuoi ricevere l'invito

3. **Ricevi Email:**
   - Controlla la tua email
   - Clicca sul link invito

4. **Completa Registrazione:**
   - Vai su: `https://my.balizero.com/portal/register?token=XXXXX`
   - Crea PIN (4-6 cifre numeriche)
   - Completa registrazione

5. **Accedi:**
   - Vai su: `https://my.balizero.com/portal/login`
   - Email + PIN → Enter Portal ✅

---

### Opzione B: Via Script Python (Se hai accesso database)

```bash
cd apps/backend-rag

# Carica DATABASE_URL
export DATABASE_URL="postgresql://postgres:Balizero2020!@db.yxyibhwacnausqfqbrtd.supabase.co:5432/postgres"

# Crea account
python backend/scripts/create_portal_test_user_simple.py \
  --email antonello@balizero.com \
  --pin 123456 \
  --name "Antonello"
```

Poi accedi con email + PIN.

---

## 🎯 Metodo 3: Via API (Se hai token admin)

```bash
# 1. Login admin
TOKEN=$(curl -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"zero@balizero.com","credentials":"YOUR_PIN"}' \
  | jq -r '.access_token')

# 2. Crea invito
curl -X POST https://nuzantara-rag.fly.dev/api/portal/invite/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"client_id": 1, "email": "antonello@balizero.com"}'

# 3. Usa link invito per registrazione
```

---

## 📋 Requisiti PIN

- ✅ **Lunghezza:** 4-6 cifre
- ✅ **Formato:** Solo numeri (0-9)
- ✅ **Esempi validi:** `1234`, `567890`, `0000`

---

## 🆘 Problemi Comuni

### "Invalid email or PIN"

- Verifica email corretta
- Verifica PIN corretto (4-6 cifre)
- Controlla maiuscole/minuscole nell'email

### "Account inactive"

- Contatta supporto per riattivare account

### Non ho ricevuto invito

- Controlla spam/promozioni
- Verifica email corretta
- Richiedi nuovo invito

---

## 🎯 Quick Start (Per Te)

**Se vuoi entrare SUBITO:**

1. **Hai già account?**
   - Vai su: `https://my.balizero.com/portal/login`
   - Email + PIN → Enter ✅

2. **Non hai account?**
   - Login su `kita.balizero.com` (dashboard admin)
   - Crea invito per te stesso
   - Completa registrazione
   - Accedi ✅

3. **Vuoi che crei account per te?**
   - Dimmi email e PIN desiderati
   - Lo creo direttamente nel database

---

## 📞 Supporto

- **Email:** `info@balizero.com`
- **WhatsApp:** `+62 813 3805 1876`

---

**Vuoi che crei un account di test ora?** Dimmi email e PIN! 🚀
