# 📱 Meta WhatsApp API - Webhook Setup Guide

**Date:** 2026-02-12
**Purpose:** Connettere Meta WhatsApp Business API alla webapp sul Mac Air

---

## ✅ Situazione Attuale

### Backend Status

- ✅ **Mac Air:** Backend running su porta 8001
- ✅ **Webhook endpoint:** `/webhook/whatsapp` già implementato
- ✅ **Router:** `backend/app/routers/whatsapp_chat.py` completo
- ✅ **Services:** `whatsapp_service.py`, `whatsapp_triage_service.py` operativi

### Architettura

```
Meta WhatsApp Cloud API
         ↓
   (HTTPS Webhook)
         ↓
   nuzantara-rag.fly.dev/webhook/whatsapp
         ↓
   Backend FastAPI (Mac Air via Fly.io)
         ↓
   Claude Sonnet 4.5 + Zantara AI
         ↓
   Risposta → WhatsApp API → Cliente
```

---

## 🔧 Setup Completo (Step-by-Step)

### Step 1: Verifica Environment Variables

**Sul Mac Air (o Fly.io secrets):**

```bash
# Necessari per Meta WhatsApp API
WHATSAPP_API_TOKEN=EAAxxxxxxxxxxxxxxxx  # Meta access token
WHATSAPP_PHONE_NUMBER_ID=123456789      # Business phone number ID
WHATSAPP_BUSINESS_ACCOUNT_ID=987654321  # WABA ID
WHATSAPP_VERIFY_TOKEN=your_random_secret_token  # Per webhook verification
```

**Come ottenerli:**

1. **Meta Business Manager:** https://business.facebook.com
2. **App Dashboard:** https://developers.facebook.com/apps
3. Vai a: **WhatsApp → Getting Started**
4. Copia i valori mostrati

**Verifica su Fly.io:**

```bash
fly secrets list -a nuzantara-rag | grep WHATSAPP
```

**Se mancano, impostali:**

```bash
fly secrets set \
  WHATSAPP_API_TOKEN="EAAxxxxxxxxx" \
  WHATSAPP_PHONE_NUMBER_ID="123456789" \
  WHATSAPP_BUSINESS_ACCOUNT_ID="987654321" \
  WHATSAPP_VERIFY_TOKEN="$(openssl rand -hex 32)" \
  -a nuzantara-rag
```

---

### Step 2: Configure Webhook su Meta Business

**URL da configurare:**

```
Production: https://nuzantara-rag.fly.dev/webhook/whatsapp
Local Test: https://YOUR_NGROK_URL.ngrok.io/webhook/whatsapp
```

**Procedura:**

1. **Vai a:** [Meta App Dashboard](https://developers.facebook.com/apps)
2. **Seleziona la tua App** WhatsApp Business
3. **WhatsApp → Configuration**
4. **Webhook Section:**
   - Click **"Edit"** o **"Configure Webhook"**
   - **Callback URL:** `https://nuzantara-rag.fly.dev/webhook/whatsapp`
   - **Verify Token:** Il valore di `WHATSAPP_VERIFY_TOKEN` (stesso secret impostato sopra)
   - Click **"Verify and Save"**

5. **Subscribe to Webhooks:**
   - Check: `messages` ✅
   - Optional: `message_status`, `message_echoes` (per tracking)

**Meta farà una richiesta GET:**

```
GET https://nuzantara-rag.fly.dev/webhook/whatsapp?
  hub.mode=subscribe&
  hub.verify_token=YOUR_TOKEN&
  hub.challenge=CHALLENGE_STRING
```

**Il backend risponderà con:**

```
200 OK
Content: CHALLENGE_STRING
```

Se vedi ✅ verde su Meta → **Webhook configured successfully!**

---

### Step 3: Test Webhook (Development con ngrok)

**Se vuoi testare localmente sul Mac Air prima di usare Fly.io:**

**A) Installa ngrok:**

```bash
brew install ngrok
```

**B) Autentica ngrok:**

```bash
ngrok config add-authtoken YOUR_NGROK_TOKEN
# Get token free at: https://ngrok.com
```

**C) Tunnel to Mac Air backend:**

```bash
# Sul Mac Air
ngrok http 8001

# Output:
# Forwarding: https://abc123.ngrok.io → http://localhost:8001
```

**D) Configure Meta webhook:**

```
Callback URL: https://abc123.ngrok.io/webhook/whatsapp
Verify Token: (stesso di prima)
```

**E) Send test message:**

Invia un messaggio WhatsApp al tuo Business Number.

**F) Check logs:**

```bash
# Sul Mac Air
ssh air
cd ~/Projects/nuzantara/apps/backend-rag
tail -f logs/app.log

# Dovresti vedere:
# [INFO] WhatsApp webhook received: {...}
# [INFO] Processing message from +628123456789
# [INFO] Triage decision: business → AI response
```

---

### Step 4: Verifica Funzionamento

**Test Flow Completo:**

1. **Invia messaggio** al tuo WhatsApp Business Number:

   ```
   "Ciao, quanto costa il visto business?"
   ```

2. **Backend riceve webhook** (check logs):

   ```json
   {
     "object": "whatsapp_business_account",
     "entry": [
       {
         "changes": [
           {
             "value": {
               "messages": [
                 {
                   "from": "628123456789",
                   "text": { "body": "Ciao, quanto costa il visto business?" }
                 }
               ]
             }
           }
         ]
       }
     ]
   }
   ```

3. **Triage decide** (business query → AI):

   ```
   [INFO] Triage: business → Zantara AI
   ```

4. **Claude genera risposta:**

   ```
   [INFO] Calling Claude Sonnet 4.5 with Zantara prompt
   [INFO] Response generated: 300 tokens
   ```

5. **Risposta inviata via WhatsApp API:**

   ```
   [INFO] WhatsApp message sent to +628123456789
   ```

6. **Cliente riceve** la risposta su WhatsApp ✅

7. **Zero riceve log** su Telegram (se `ADMIN_TELEGRAM_CHAT_ID` configurato):
   ```
   💬 WhatsApp Bot Conversation Log
   Cliente: +628123456789 🇮🇹
   Domanda: Ciao, quanto costa il visto business?
   Risposta Zan: Ciao! Il visto business...
   ```

---

## 🔍 Debugging & Troubleshooting

### Issue 1: Webhook Verification Fails

**Errore Meta:** "The callback URL or verify token couldn't be validated"

**Cause:**

- `WHATSAPP_VERIFY_TOKEN` non corrisponde
- Backend non risponde (down o firewall)
- URL sbagliato

**Fix:**

```bash
# 1. Verifica backend running
curl https://nuzantara-rag.fly.dev/health
# Should return: {"status":"healthy"}

# 2. Verifica verify token
fly secrets list -a nuzantara-rag | grep WHATSAPP_VERIFY_TOKEN

# 3. Test webhook manualmente
curl "https://nuzantara-rag.fly.dev/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"
# Should return: test123
```

---

### Issue 2: Messages Not Arriving

**Sintomo:** Invii messaggio ma backend non riceve nulla

**Cause:**

- Webhook non subscribed a `messages`
- Phone number non verificato
- WABA suspended

**Fix:**

1. **Check Meta Webhook Subscriptions:**
   - Meta App Dashboard → WhatsApp → Configuration
   - Verify `messages` è checked ✅

2. **Check Webhook Logs su Meta:**
   - Meta App Dashboard → WhatsApp → Webhook Fields
   - Click **"Test"** → dovrebbe mostrare log delle chiamate

3. **Check Backend Logs:**
   ```bash
   fly logs -a nuzantara-rag | grep whatsapp
   ```

---

### Issue 3: Bot Non Risponde

**Sintomo:** Webhook riceve messaggio ma nessuna risposta inviata

**Cause:**

- `WHATSAPP_API_TOKEN` expired/invalid
- Claude API error
- Triage service routing a human invece di bot

**Fix:**

1. **Check API Token:**

   ```bash
   # Test token validity
   curl -X POST "https://graph.facebook.com/v22.0/PHONE_NUMBER_ID/messages" \
     -H "Authorization: Bearer $WHATSAPP_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "messaging_product": "whatsapp",
       "to": "YOUR_TEST_NUMBER",
       "type": "text",
       "text": {"body": "Test"}
     }'
   ```

2. **Check Claude API:**

   ```bash
   fly secrets list -a nuzantara-rag | grep ANTHROPIC_API_KEY
   ```

3. **Check Triage Logic:**
   - File: `backend/services/integrations/whatsapp_triage_service.py`
   - Se sender è in `WHATSAPP_PERSONAL_CONTACTS` → routing to human
   - Verifica lista contatti personali:
     ```bash
     fly secrets list -a nuzantara-rag | grep WHATSAPP_PERSONAL_CONTACTS
     ```

---

### Issue 4: Rate Limiting

**Errore:** `{"error": {"code": 80007, "message": "Rate limit hit"}}`

**Meta Limits:**

- **Tier 1:** 1,000 business-initiated conversations/day
- **User-initiated (reply):** UNLIMITED

**Fix:**

- Sei in **reply-only mode** → no limits!
- Se vedi questo errore, stai mandando template messages (business-initiated)
- Soluzione: Rispondi solo a messaggi ricevuti (attuale comportamento ✅)

---

## 📊 Monitoring & Logs

### Backend Logs (Fly.io)

```bash
# Real-time logs
fly logs -a nuzantara-rag

# Filter WhatsApp only
fly logs -a nuzantara-rag | grep -i whatsapp

# Last 100 lines
fly logs -a nuzantara-rag --lines 100
```

### Key Log Patterns

**Success:**

```
[INFO] WhatsApp webhook received
[INFO] Processing message from +628123456789
[INFO] Triage decision: business
[INFO] Claude API response: 250 tokens
[INFO] WhatsApp message sent successfully
```

**Personal Contact Escalation:**

```
[INFO] Triage decision: personal_contact
[INFO] Telegram notification sent to admin
```

**Error:**

```
[ERROR] WhatsApp API error: {"error": {"code": 100, "message": "Invalid parameter"}}
[ERROR] Failed to send message: Connection timeout
```

---

## 🎯 CLI Integration (Con Alias `zan`)

**Il backend già chiama Claude/Gemini internamente**, ma se vuoi testare il prompt:

```bash
# Simula una richiesta WhatsApp
zan "Rispondi a: Quanto costa il visto business?"

# Output sarà simile alla risposta bot WhatsApp
```

**Il flusso interno del bot è:**

```python
# backend/app/routers/whatsapp_chat.py (simplified)
async def process_whatsapp_message(phone, message_text, ...):
    # 1. Triage
    decision = await triage_service.should_escalate(...)

    if decision == "personal":
        # → Send to human via Telegram
        await notify_human_telegram(...)
    else:
        # 2. Build context
        context = await context_builder.build(...)

        # 3. Generate prompt
        system_prompt = build_zantara_prompt(context)

        # 4. Call Claude
        response = await claude_client.messages.create(
            model="claude-sonnet-4-5",
            system=system_prompt,
            messages=[{"role": "user", "content": message_text}]
        )

        # 5. Send response
        await whatsapp_service.send_message(phone, response.content)
```

---

## 🚀 Production Deployment Checklist

Prima di andare live con clienti reali:

- [ ] **Webhook configured** su Meta Business ✅
- [ ] **All secrets set** su Fly.io (API token, phone ID, WABA ID, verify token)
- [ ] **Test message flow** (send → receive → AI response → reply)
- [ ] **Telegram notifications** working (admin chat ID configured)
- [ ] **Triage service** tested (personal vs business routing)
- [ ] **Claude API quota** sufficient (check Anthropic dashboard)
- [ ] **Monitoring** setup (Fly.io logs, Sentry errors)
- [ ] **Backup phone number** (in case primary suspended)

---

## 📱 Meta WhatsApp API Limits & Pricing

### Message Limits

**User-Initiated (Cliente scrive per primo):**

- ✅ **UNLIMITED & FREE** (reply-only mode)
- 24-hour customer service window gratis
- Nessun rate limit

**Business-Initiated (Tu scrivi per primo):**

- Template messages required
- Pricing: ~$0.02-0.05/message (Indonesia)
- Daily limits based on tier

### Quality Rating

Meta assegna un **quality rating** basato su:

- User blocks
- User reports
- Message delivery failures

**Mantieni quality rating alto:**

- ✅ Rispondi solo a messaggi ricevuti
- ✅ Risposte pertinenti e utili
- ✅ No spam, no mass messages
- ✅ Respect 24h window

---

## 🔐 Security Best Practices

### Secrets Management

**NEVER commit secrets to git:**

```bash
# .gitignore should have:
.env
.env.local
*.key
credentials.json
```

**Use Fly.io secrets:**

```bash
fly secrets set KEY=value -a nuzantara-rag
# Secrets are encrypted at rest
```

### Webhook Verification

**Il backend verifica ogni webhook:**

```python
# whatsapp_chat.py
@router.get("")
async def verify_webhook(params: dict):
    token = params.get("hub.verify_token")
    if token == settings.whatsapp_verify_token:
        return PlainTextResponse(params.get("hub.challenge"))
    raise HTTPException(403, "Invalid verify token")
```

**Meta può solo:**

- Inviare messaggi al webhook configurato
- Con il verify token corretto
- Da IP verificati Meta

### Rate Limiting

**Backend non ha rate limiting interno** (fidati di Meta limits).

Se vuoi aggiungere (opzionale):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("")
@limiter.limit("100/minute")  # Max 100 webhook calls/min
async def whatsapp_webhook(...):
    ...
```

---

## 📚 Useful Links

**Meta Documentation:**

- [WhatsApp Business Platform](https://developers.facebook.com/docs/whatsapp)
- [Cloud API Quickstart](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started)
- [Webhook Reference](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks)
- [Pricing 2026](https://business.whatsapp.com/products/platform-pricing)

**Monitoring:**

- [Meta App Dashboard](https://developers.facebook.com/apps)
- [Business Manager](https://business.facebook.com)
- [Fly.io Dashboard](https://fly.io/dashboard/nuzantara-rag)

**Support:**

- Meta: https://developers.facebook.com/support
- Fly.io: https://community.fly.io

---

## ✅ Quick Start Summary

**Minimal setup per iniziare:**

1. **Get Meta credentials** (Business Manager)
2. **Set Fly.io secrets** (`fly secrets set ...`)
3. **Configure webhook** (Meta App Dashboard → WhatsApp → Configuration)
4. **Test message** (invia WhatsApp al tuo numero business)
5. **Check logs** (`fly logs -a nuzantara-rag`)
6. **Done!** 🎉

**Webhook URL:** `https://nuzantara-rag.fly.dev/webhook/whatsapp`

---

**Created by:** Claude Sonnet 4.5
**Date:** 2026-02-12
**Status:** ✅ Ready for Configuration
**Backend:** Already running on Mac Air + Fly.io
