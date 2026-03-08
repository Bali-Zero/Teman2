# Come Creare Account Test per Portal

**Data:** 2025-01-29  
**Scopo:** Creare account di test per accedere al portal clienti

---

## 🚀 Metodo Rapido: Script Python

### Step 1: Attiva Virtual Environment

```bash
cd apps/backend-rag
source .venv/bin/activate
```

### Step 2: Crea Account Test

```bash
python backend/scripts/create_portal_test_user.py \
  --email test@example.com \
  --pin 1234 \
  --name "Test User"
```

**Output atteso:**

```
✅ Created client: 123 (Test User)
✅ Created portal user: 456
🎉 Portal account created successfully!

📧 Email: test@example.com
🔑 PIN: 1234

🌐 Login at: https://my.balizero.com/portal/login

✅ You can now login with:
   Email: test@example.com
   PIN: 1234
```

### Step 3: Accedi al Portal

1. Vai su: `https://my.balizero.com/portal/login`
2. Inserisci email: `test@example.com`
3. Inserisci PIN: `1234`
4. Clicca "Enter Portal"

---

## 🔧 Metodo Alternativo: Via API (Se hai accesso admin)

### Step 1: Login su Dashboard Admin

1. Vai su: `https://kita.balizero.com/login`
2. Login con credenziali admin

### Step 2: Crea Cliente (se non esiste)

```bash
POST /api/crm/clients
{
  "full_name": "Test Client",
  "email": "test@example.com"
}
```

### Step 3: Invia Invito Portal

```bash
POST /api/portal/invite/send
{
  "client_id": 123,
  "email": "test@example.com"
}
```

### Step 4: Completa Registrazione

1. Clicca sul link invito ricevuto
2. Crea PIN (4-6 cifre)
3. Completa registrazione

---

## 📝 Esempi di Uso

### Esempio 1: Account Test Semplice

```bash
python backend/scripts/create_portal_test_user.py \
  --email test@balizero.com \
  --pin 1234
```

### Esempio 2: Account Test con Nome Personalizzato

```bash
python backend/scripts/create_portal_test_user.py \
  --email antonello@balizero.com \
  --pin 567890 \
  --name "Antonello Test"
```

### Esempio 3: Account Test per Demo

```bash
python backend/scripts/create_portal_test_user.py \
  --email demo@balizero.com \
  --pin 0000 \
  --name "Demo Client"
```

---

## ✅ Verifica Account Creato

Dopo aver creato l'account, puoi verificare:

```bash
# Verifica nel database
psql $DATABASE_URL -c "
SELECT tm.id, tm.email, tm.full_name, tm.role, tm.active, tm.linked_client_id
FROM team_members tm
WHERE tm.email = 'test@example.com';
"
```

---

## 🎯 Quick Start (Per Te)

**Crea il tuo account test:**

```bash
cd apps/backend-rag
source .venv/bin/activate

python backend/scripts/create_portal_test_user.py \
  --email antonello@balizero.com \
  --pin 123456 \
  --name "Antonello"
```

**Poi accedi:**

1. Vai su: `https://my.balizero.com/portal/login`
2. Email: `antonello@balizero.com`
3. PIN: `123456`
4. Enter Portal ✅

---

## 🔍 Troubleshooting

### Errore: Database connection failed

**Soluzione:**

```bash
# Verifica DATABASE_URL
echo $DATABASE_URL

# Oppure usa .env
source .env
```

### Errore: PIN must be 4-6 digits

**Soluzione:**

- Usa solo numeri
- Lunghezza 4-6 cifre
- Esempio: `1234` ✅, `abc123` ❌

### Account già esistente

**Soluzione:**

- Lo script aggiorna automaticamente account esistenti
- Il PIN viene aggiornato
- Puoi riutilizzare lo stesso account

---

**Ready to test!** 🚀
