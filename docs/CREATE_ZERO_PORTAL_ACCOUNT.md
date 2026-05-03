# 🔐 Creare Account Portal per zero@balizero.com

> **SECURITY:** Never hardcode PINs. Use environment variable `ADMIN_PIN`.

**Email:** `zero@balizero.com`
**PIN:** `$ADMIN_PIN` (from environment variable)

---

## ⚡ Metodo 1: Via Dashboard Admin (PIÙ SEMPLICE)

### Step 1: Login Dashboard Admin

1. Vai su: `https://kita.balizero.com/login`
2. Login con: `zero@balizero.com` + [il tuo PIN admin]

### Step 2: Crea Invito Portal

1. Vai su **Clients** → Cerca o crea cliente con email `zero@balizero.com`
2. Clicca **"Send Portal Invite"**
3. Inserisci email: `zero@balizero.com`
4. Clicca **Send**

### Step 3: Completa Registrazione

1. Controlla email `zero@balizero.com`
2. Clicca sul link invito
3. Crea PIN: `$ADMIN_PIN` [PIN from env]
4. Completa registrazione

### Step 4: Accedi

1. Vai su: `https://my.balizero.com/portal/login`
2. Email: `zero@balizero.com`
3. PIN: `$ADMIN_PIN` [PIN from env]
4. Enter Portal ✅

---

## ⚡ Metodo 2: Via API (Se hai token admin)

### Step 1: Ottieni Token Admin

1. Login su: `https://kita.balizero.com/login`
2. Apri DevTools (F12) → Application → Cookies
3. Copia valore di `access_token`

### Step 2: Esegui Script

```bash
cd apps/backend-rag/backend/scripts
export ADMIN_TOKEN="il_tuo_token_qui"
export BACKEND_URL="https://nuzantara-rag.fly.dev"

./create_portal_account_via_api.sh zero@balizero.com $ADMIN_PIN
```

---

## ⚡ Metodo 3: SQL Diretto (Se hai accesso database)

### Step 1: Genera Hash PIN

```bash
cd apps/backend-rag
python3 << 'PYEOF'
import os, bcrypt
pin = os.environ.get('ADMIN_PIN', 'CHANGE_ME')  # Set ADMIN_PIN env var
pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
print(f"UPDATE team_members SET pin_hash = '{pin_hash}', active = true, portal_access = true, updated_at = NOW() WHERE email = 'zero@balizero.com';")
PYEOF
```

### Step 2: Esegui SQL

```bash
psql $DATABASE_URL -c "
-- Verifica se esiste
SELECT id, email, full_name, role, active
FROM team_members
WHERE email = 'zero@balizero.com';

-- Aggiorna PIN (usa hash generato sopra)
UPDATE team_members
SET pin_hash = '\$2b\$12\$...',  -- Sostituisci con hash generato
    active = true,
    portal_access = true,
    updated_at = NOW()
WHERE email = 'zero@balizero.com';

-- Se non esiste, crea client e user
INSERT INTO clients (full_name, email, created_at, updated_at)
VALUES ('Zero Admin', 'zero@balizero.com', NOW(), NOW())
ON CONFLICT DO NOTHING;

INSERT INTO team_members (
    email, full_name, pin_hash, role, active,
    linked_client_id, portal_access, created_at, updated_at
)
SELECT
    'zero@balizero.com',
    'Zero Admin',
    '\$2b\$12\$...',  -- Sostituisci con hash generato
    'client',
    true,
    (SELECT id FROM clients WHERE email = 'zero@balizero.com'),
    true,
    NOW(),
    NOW()
ON CONFLICT (email) DO UPDATE
SET pin_hash = EXCLUDED.pin_hash,
    active = true,
    portal_access = true,
    updated_at = NOW();
"
```

---

## ✅ Verifica Account

Dopo aver creato l'account, verifica:

```bash
# Via API
curl -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "zero@balizero.com", "credentials": "'$ADMIN_PIN'"}'

# Dovresti ricevere un JWT token se funziona
```

---

## 🎯 Quick Access

**Una volta creato l'account:**

1. Vai su: `https://my.balizero.com/portal/login`
2. Email: `zero@balizero.com`
3. PIN: `$ADMIN_PIN` [PIN from env]
4. Enter Portal ✅

---

## 🆘 Troubleshooting

### "Invalid email or PIN"

- Verifica che l'account esista in `team_members`
- Verifica che `pin_hash` sia corretto (bcrypt)
- Verifica che `active = true` e `portal_access = true`

### "Account inactive"

- Esegui: `UPDATE team_members SET active = true WHERE email = 'zero@balizero.com';`

### Non riesco a connettermi al database

- Usa Metodo 1 (Dashboard Admin) - è il più semplice!
- Oppure usa Metodo 2 (API) se hai token admin

---

**Raccomandazione:** Usa **Metodo 1** (Dashboard Admin) - è il più semplice e sicuro! 🚀
