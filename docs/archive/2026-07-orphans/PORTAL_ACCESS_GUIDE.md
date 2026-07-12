# Guida Accesso Portal Clienti - my.balizero.com

**URL Portal:** `https://my.balizero.com`  
**Data:** 2025-01-29

---

## 🔐 Come Accedere al Portal

### Processo di Accesso

Il portal clienti utilizza un sistema di autenticazione a **2 step** con **PIN**:

1. **Inserisci Email** → Verifica email
2. **Inserisci PIN** → Accesso al portal

---

## 📧 Primo Accesso (Nuovo Cliente)

### Step 1: Ricezione Invito

1. **Il team Bali Zero invia un invito** al tuo indirizzo email
2. **Ricevi email** con link di invito
3. **Link contiene token** valido per 72 ore (3 giorni)

### Step 2: Registrazione

1. **Clicca sul link** nell'email di invito
2. **Vai su:** `https://my.balizero.com/portal/register?token=XXXXX`
3. **Valida il token** (automatico)
4. **Crea il tuo PIN:**
   - 4-6 cifre numeriche
   - Esempio: `1234` o `567890`
5. **Completa la registrazione**

### Step 3: Primo Login

Dopo la registrazione, puoi accedere con:

- **Email:** Il tuo indirizzo email
- **PIN:** Il PIN che hai creato

---

## 🔑 Accesso Successivo (Cliente Registrato)

### Metodo 1: Via URL Diretto

1. Vai su: **`https://my.balizero.com`**
2. Verrai reindirizzato automaticamente a `/portal/login`
3. Inserisci:
   - **Email:** Il tuo indirizzo email
   - **PIN:** Il tuo PIN (4-6 cifre)

### Metodo 2: Via Link Portal

1. Vai su: **`https://my.balizero.com/portal/login`**
2. Inserisci email e PIN
3. Clicca "Enter Portal"

---

## 📋 Dettagli Login

### Step 1: Email

```
1. Inserisci il tuo indirizzo email
2. Clicca "Continue"
3. Passa allo step PIN
```

### Step 2: PIN

```
1. Inserisci il tuo PIN (4-6 cifre)
2. Il PIN è nascosto (••••••)
3. Clicca "Enter Portal"
4. Se sbagli email, clicca "Change Email"
```

---

## 🆘 Problemi di Accesso

### Non Ho Ricevuto l'Invito

**Soluzione:**

- Contatta il team Bali Zero
- Verifica che l'email sia corretta
- Controlla spam/promozioni

### Ho Perso il PIN

**Soluzione:**

- Contatta supporto: `info@balizero.com`
- Il team può resettare il PIN
- Potrebbe essere necessario un nuovo invito

### Il Link di Invito è Scaduto

**Soluzione:**

- I link scadono dopo 72 ore
- Contatta il team per un nuovo invito
- Il team può inviare un nuovo link

### Email o PIN Non Funzionano

**Soluzione:**

- Verifica di usare l'email corretta
- Verifica che il PIN sia 4-6 cifre numeriche
- Contatta supporto se il problema persiste

---

## 🔄 Processo Invito (Per il Team)

### Come Invitare un Cliente

1. **Dashboard Admin** → `kita.balizero.com`
2. Vai su **Clients** → Seleziona cliente
3. Clicca **"Send Portal Invite"**
4. Il sistema:
   - Genera token sicuro
   - Invia email al cliente
   - Crea record invito nel database

### Endpoint API

```bash
POST /api/portal/invite/send
{
  "client_id": 123,
  "email": "cliente@example.com"
}
```

---

## 📱 Accesso Mobile

Il portal è **mobile-responsive**:

- ✅ Funziona su smartphone
- ✅ Design ottimizzato per mobile
- ✅ Stesso processo di login

---

## 🔒 Sicurezza

### PIN Requirements

- ✅ **Lunghezza:** 4-6 cifre
- ✅ **Formato:** Solo numeri (0-9)
- ✅ **Hash:** Salvato in modo sicuro (bcrypt)
- ✅ **Non recuperabile:** Se perso, serve reset

### Best Practices

- ✅ **Non condividere** il PIN con altri
- ✅ **Usa PIN unico** (non riutilizzare PIN comuni)
- ✅ **Cambia PIN** se sospetti compromissione
- ✅ **Logout** quando finisci di usare il portal

---

## 📞 Supporto

### Contatti

- **Email:** `info@balizero.com`
- **WhatsApp:** `+62 813 3805 1876`
- **Portal:** `https://my.balizero.com`

### Messaggi di Errore Comuni

| Errore                     | Causa                | Soluzione             |
| -------------------------- | -------------------- | --------------------- |
| "Invalid email or PIN"     | Credenziali errate   | Verifica email/PIN    |
| "Account inactive"         | Account disabilitato | Contatta supporto     |
| "Invitation expired"       | Link scaduto         | Richiedi nuovo invito |
| "Invalid invitation token" | Token non valido     | Richiedi nuovo invito |

---

## 🎯 URL Utili

### Portal Clienti

```
✅ https://my.balizero.com              → Redirect a login
✅ https://my.balizero.com/portal/login → Pagina login
✅ https://my.balizero.com/portal       → Dashboard (dopo login)
```

### Pagine Portal (Dopo Login)

```
✅ https://my.balizero.com/portal/vault     → Documenti
✅ https://my.balizero.com/portal/profile   → Profilo
✅ https://my.balizero.com/portal/settings  → Impostazioni
✅ https://my.balizero.com/portal/visa      → Status visto
✅ https://my.balizero.com/portal/taxes     → Tasse
✅ https://my.balizero.com/portal/chat      → Messaggi
✅ https://my.balizero.com/portal/companies → Aziende
```

---

## 📝 Riepilogo Processo

### Per Nuovi Clienti

```
1. Ricevi email invito
   ↓
2. Clicca link invito
   ↓
3. Vai su /portal/register?token=XXX
   ↓
4. Crea PIN (4-6 cifre)
   ↓
5. Registrazione completata
   ↓
6. Login con email + PIN
   ↓
7. Accesso al portal ✅
```

### Per Clienti Esistenti

```
1. Vai su my.balizero.com
   ↓
2. Inserisci email
   ↓
3. Inserisci PIN
   ↓
4. Accesso al portal ✅
```

---

## ✅ Checklist Accesso

### Primo Accesso

- [ ] Email invito ricevuta
- [ ] Link invito cliccato
- [ ] Token validato
- [ ] PIN creato (4-6 cifre)
- [ ] Registrazione completata
- [ ] Login effettuato

### Accessi Successivi

- [ ] Email corretta inserita
- [ ] PIN corretto inserito
- [ ] Accesso al portal riuscito

---

**Ultimo Update:** 2025-01-29  
**Status:** ✅ Portal attivo e funzionante
