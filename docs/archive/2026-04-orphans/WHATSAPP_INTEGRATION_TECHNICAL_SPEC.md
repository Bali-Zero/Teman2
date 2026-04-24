# WhatsApp Integration - Technical Specification

**Feature**: Auto-sync conversazioni WhatsApp → CRM
**Priority**: P0 #2
**Estimated Effort**: 8-10 giorni
**Owner**: TBD
**Status**: Planning

---

## Table of Contents

1. [Come Funziona](#come-funziona)
2. [Architettura Tecnica](#architettura-tecnica)
3. [Setup WhatsApp Business API](#setup-whatsapp-business-api)
4. [Flow Completo](#flow-completo)
5. [AI Data Extraction](#ai-data-extraction)
6. [Database Schema](#database-schema)
7. [Implementation Steps](#implementation-steps)
8. [Costi & Limitazioni](#costi--limitazioni)
9. [Testing Plan](#testing-plan)

---

## Come Funziona

### Panoramica High-Level

```
Cliente scrive WhatsApp
         ↓
WhatsApp Business API (Meta)
         ↓
Webhook → Nuzantara Backend
         ↓
AI estrae dati (nome, email, richiesta)
         ↓
Cerca cliente esistente in DB
         ↓
Se nuovo → Crea cliente
Se esistente → Aggiungi messaggio a timeline
         ↓
Team member vede conversazione in CRM
```

### Due Opzioni Disponibili

#### Opzione 1: WhatsApp Cloud API (CONSIGLIATA) ☁️

**Pro:**

- ✅ Setup veloce (2-3 giorni)
- ✅ Hosting gestito da Meta
- ✅ Scaling automatico
- ✅ Costi bassi per volumi piccoli/medi
- ✅ Manutenzione zero

**Contro:**

- ❌ Devi usare infrastruttura Meta
- ❌ Meno controllo su rate limits

**Quando usarla:** Start rapido, <100K messaggi/mese

---

#### Opzione 2: WhatsApp On-Premises API 🏢

**Pro:**

- ✅ Controllo totale infrastruttura
- ✅ Rate limits più alti
- ✅ Dati rimangono sul tuo server

**Contro:**

- ❌ Setup complesso (7-10 giorni)
- ❌ Devi gestire server dedicato
- ❌ Costi hosting più alti
- ❌ Manutenzione continua

**Quando usarla:** >100K messaggi/mese, requisiti compliance stringenti

---

**RACCOMANDAZIONE:** Parti con **Cloud API**. Migra a On-Premises solo se superi limiti.

---

## Architettura Tecnica

### Componenti

```
┌─────────────────────────────────────────────────────┐
│              WhatsApp Business API                   │
│           (Meta Cloud Hosting)                       │
└─────────────────┬───────────────────────────────────┘
                  │
                  │ HTTPS Webhook
                  │ (POST request on new message)
                  ↓
┌─────────────────────────────────────────────────────┐
│         Nuzantara Backend (FastAPI)                  │
│                                                       │
│  ┌──────────────────────────────────────┐           │
│  │  /webhook/whatsapp (POST endpoint)   │           │
│  │  - Verify webhook signature          │           │
│  │  - Parse incoming message             │           │
│  │  - Queue for processing               │           │
│  └──────────────┬───────────────────────┘           │
│                 │                                     │
│                 ↓                                     │
│  ┌──────────────────────────────────────┐           │
│  │  Message Processing Pipeline         │           │
│  │  1. Extract phone number              │           │
│  │  2. Search existing client (DB)       │           │
│  │  3. If new → AI extraction            │           │
│  │  4. Create/Update client              │           │
│  │  5. Save message to interactions      │           │
│  └──────────────┬───────────────────────┘           │
│                 │                                     │
│                 ↓                                     │
│  ┌──────────────────────────────────────┐           │
│  │  AI Extraction Service                │           │
│  │  - Gemini 1.5 Pro / GPT-4o            │           │
│  │  - Prompt: Extract name, email, etc   │           │
│  │  - Return structured JSON             │           │
│  └──────────────┬───────────────────────┘           │
│                 │                                     │
│                 ↓                                     │
│  ┌──────────────────────────────────────┐           │
│  │  PostgreSQL Database                  │           │
│  │  - clients table                      │           │
│  │  - whatsapp_messages table (new)     │           │
│  │  - interactions table                 │           │
│  └───────────────────────────────────────┘           │
└─────────────────────────────────────────────────────┘
                  ↑
                  │ Frontend queries
                  │
┌─────────────────────────────────────────────────────┐
│         Nuzantara Frontend (Next.js)                 │
│                                                       │
│  Client Detail Page                                  │
│  ├── Timeline shows WhatsApp messages                │
│  ├── Link to open WhatsApp web                       │
│  └── Quick reply button (send via API)              │
└─────────────────────────────────────────────────────┘
```

---

## Setup WhatsApp Business API

### Prerequisiti

1. **Meta Business Account**
   - Account Meta Business Manager
   - Numero di telefono business (non personale)
   - Documento identità per verifica

2. **Infrastruttura Backend**
   - Server con IP pubblico (Fly.io ✅ già ce l'hai)
   - HTTPS endpoint per webhook (obbligatorio)
   - SSL certificate valido (Let's Encrypt OK)

### Step Setup (Cloud API)

#### 1. Crea App su Meta for Developers

```bash
1. Vai su https://developers.facebook.com/
2. Crea nuova app → "Business" type
3. Aggiungi prodotto: "WhatsApp"
4. Configura WhatsApp Business API
```

#### 2. Configura Numero Telefono

```bash
# Opzioni:
A) Usa numero test gratuito (per dev/testing)
   - Fornito da Meta
   - Limite: 5 destinatari
   - Valido 90 giorni

B) Usa tuo numero business
   - Serve verifica SMS
   - Richiede Business Verification (1-3 giorni)
   - No limiti destinatari
```

#### 3. Genera Access Token

```bash
# Nel dashboard WhatsApp Business API:
1. System User → Create system user
2. Assign assets → Assign WhatsApp Business Account
3. Generate token → Permissions: whatsapp_business_messaging
4. Copia token (serve per API calls)
```

**IMPORTANTE:** Salva token in variabili ambiente, MAI nel codice!

```bash
# .env
WHATSAPP_ACCESS_TOKEN=your_token_here
WHATSAPP_PHONE_NUMBER_ID=1234567890
WHATSAPP_BUSINESS_ACCOUNT_ID=9876543210
WHATSAPP_WEBHOOK_VERIFY_TOKEN=random_secret_string_here
```

#### 4. Configura Webhook

```python
# Backend endpoint
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Riceve messaggi da WhatsApp Business API
    """
    body = await request.json()

    # Verifica signature (security)
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_webhook_signature(body, signature):
        raise HTTPException(401, "Invalid signature")

    # Process message
    await process_whatsapp_message(body)
    return {"status": "ok"}


@app.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge")
):
    """
    Verifica webhook (chiamato da Meta durante setup)
    """
    if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)

    raise HTTPException(403, "Verification failed")
```

**Deploy webhook su Fly.io:**

```bash
# Il tuo backend è già su Fly.io ✅
# URL webhook sarà: https://nuzantara-rag.fly.dev/webhook/whatsapp

# In Meta Developer Console:
1. WhatsApp → Configuration
2. Webhook URL: https://nuzantara-rag.fly.dev/webhook/whatsapp
3. Verify Token: <stesso di WHATSAPP_WEBHOOK_VERIFY_TOKEN>
4. Subscribe to: messages, message_status
```

---

## Flow Completo

### Scenario 1: Nuovo Cliente Scrive su WhatsApp

```
Cliente: "Ciao, sono Marco Rossi. Vorrei info su KITAS"
         ↓
WhatsApp API invia webhook:
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "6281234567890",
          "text": { "body": "Ciao, sono Marco Rossi. Vorrei info su KITAS" },
          "timestamp": "1674567890"
        }]
      }
    }]
  }]
}
         ↓
Backend riceve webhook
         ↓
1. Estrai phone: +6281234567890
2. Search DB: SELECT * FROM clients WHERE whatsapp = '+6281234567890'
3. Result: NULL (cliente nuovo)
         ↓
4. Call AI Extraction:

   Prompt: """
   Extract structured data from this WhatsApp message:

   Message: "Ciao, sono Marco Rossi. Vorrei info su KITAS"
   Phone: +6281234567890

   Return JSON:
   {
     "full_name": "...",
     "email": "...",  // if mentioned
     "nationality": "...",  // if mentioned or infer from context
     "service_interest": ["..."],
     "summary": "..."
   }
   """

   AI Response:
   {
     "full_name": "Marco Rossi",
     "email": null,
     "nationality": "Italian",  // inferred from name
     "service_interest": ["KITAS"],
     "summary": "Richiede informazioni su KITAS"
   }
         ↓
5. Create client in DB:

   INSERT INTO clients (
     full_name, whatsapp, nationality,
     service_interest, status, lead_source,
     assigned_to, created_at
   ) VALUES (
     'Marco Rossi', '+6281234567890', 'Italian',
     ARRAY['KITAS'], 'lead', 'whatsapp',
     'auto-assign-logic', NOW()
   ) RETURNING id;

   // Auto-assign logic: round-robin o load balancing tra team
         ↓
6. Save message to timeline:

   INSERT INTO interactions (
     client_id, interaction_type, channel,
     summary, direction, interaction_date,
     metadata
   ) VALUES (
     123, 'message', 'whatsapp',
     'Richiede informazioni su KITAS', 'inbound', NOW(),
     '{"from": "+6281234567890", "message_id": "wamid.xxx"}'
   );
         ↓
7. Notify assigned team member (optional):

   - Email: "Nuovo lead WhatsApp: Marco Rossi - KITAS"
   - In-app notification
   - Slack webhook (se integrato)
         ↓
✅ Cliente creato in CRM!
   Team member vede:
   - Nuovo cliente "Marco Rossi" in kanban (status: lead)
   - Timeline con messaggio WhatsApp
   - Link per rispondere
```

### Scenario 2: Cliente Esistente Scrive

```
Cliente esistente (già in DB): "Ciao, a che punto è la mia pratica?"
         ↓
Backend riceve webhook
         ↓
1. Estrai phone: +6281234567890
2. Search DB: SELECT * FROM clients WHERE whatsapp = '+6281234567890'
3. Result: Cliente #123 (Marco Rossi) FOUND ✅
         ↓
4. Append messaggio a timeline:

   INSERT INTO interactions (
     client_id, interaction_type, channel,
     summary, direction, interaction_date
   ) VALUES (
     123, 'message', 'whatsapp',
     'Chiede status pratica', 'inbound', NOW()
   );
         ↓
5. (Optional) Smart Reply Suggestion:

   // AI analizza pratica e suggerisce risposta
   AI Prompt: """
   Cliente #123 ha pratica KITAS in fase "pending_documents"
   Missing: Passport copy, Bank statement

   Cliente chiede: "A che punto è la mia pratica?"

   Suggerisci risposta professionale.
   """

   AI Suggested Reply:
   "Ciao Marco! La tua pratica KITAS è in fase di completamento documenti.
   Ci mancano solo:
   - Copia passaporto aggiornata
   - Estratto conto bancario ultimi 3 mesi

   Puoi inviarmeli qui su WhatsApp? Poi procediamo subito! 🚀"
         ↓
✅ Team member vede:
   - Alert: "Cliente #123 ha scritto"
   - Messaggio in timeline
   - Suggested reply (può modificare o inviare direttamente)
```

---

## AI Data Extraction

### Prompt Engineering

````python
# backend/services/whatsapp/ai_extractor.py

EXTRACTION_PROMPT = """
You are a data extraction assistant for a CRM system.

Extract structured information from this WhatsApp conversation:

**Message:**
{message_text}

**Phone Number:**
{phone_number}

**Context:**
- Business: Immigration & legal services (Indonesia)
- Common services: KITAS, PT PMA, Tax consulting, Work permits
- Common nationalities: Italian, Russian, American, Australian

**Extract the following (if mentioned):**
- full_name: Client's name (if introduced)
- email: Email address
- nationality: Inferred or explicit (from name/context)
- service_interest: Array of services mentioned
- urgency: low | medium | high
- summary: 1-sentence summary of request

**Return ONLY valid JSON:**
```json
{
  "full_name": null or "string",
  "email": null or "string",
  "nationality": null or "string",
  "service_interest": [],
  "urgency": "medium",
  "summary": "string"
}
````

**Rules:**

- If name not explicit, return null
- Infer nationality from name patterns if confident (>80%)
- Extract ALL service keywords (KITAS, PT PMA, visa, etc)
- Be conservative: when unsure, return null
  """

async def extract_client_data(message: str, phone: str) -> dict:
"""
Usa Gemini 1.5 Pro per estrarre dati strutturati
"""
import google.generativeai as genai

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro')

    prompt = EXTRACTION_PROMPT.format(
        message_text=message,
        phone_number=phone
    )

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.1,  # Low temperature = più deterministico
            "response_mime_type": "application/json"
        }
    )

    try:
        data = json.loads(response.text)
        return data
    except json.JSONDecodeError:
        logger.error(f"AI returned invalid JSON: {response.text}")
        return {
            "full_name": None,
            "email": None,
            "nationality": None,
            "service_interest": [],
            "urgency": "medium",
            "summary": message[:100]  # Fallback: primi 100 char
        }

```

### Esempi Extraction

**Input 1:**
```

Message: "Hi, I'm John from Australia. Need help with KITAS extension"
Phone: +6287654321

````

**AI Output:**
```json
{
  "full_name": "John",
  "email": null,
  "nationality": "Australian",
  "service_interest": ["KITAS extension"],
  "urgency": "medium",
  "summary": "Australian client requests help with KITAS extension"
}
````

---

**Input 2:**

```
Message: "Ciao! Sono Maria Bianchi, email maria.b@gmail.com.
Vorrei aprire PT PMA urgentemente, ho già tutti i documenti pronti."
Phone: +6281234567
```

**AI Output:**

```json
{
  "full_name": "Maria Bianchi",
  "email": "maria.b@gmail.com",
  "nationality": "Italian",
  "service_interest": ["PT PMA"],
  "urgency": "high",
  "summary": "Italian client wants to open PT PMA urgently, documents ready"
}
```

---

**Input 3:**

```
Message: "Hello, tax question please"
Phone: +6289876543
```

**AI Output:**

```json
{
  "full_name": null,
  "email": null,
  "nationality": null,
  "service_interest": ["Tax consulting"],
  "urgency": "low",
  "summary": "Client has a tax-related question"
}
```

---

## Database Schema

### Nuove Tabelle

```sql
-- Messaggi WhatsApp (storico completo)
CREATE TABLE whatsapp_messages (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    message_id VARCHAR(255) UNIQUE NOT NULL,  -- WhatsApp message ID
    from_number VARCHAR(50) NOT NULL,
    to_number VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- 'inbound' | 'outbound'
    message_type VARCHAR(50),  -- 'text' | 'image' | 'document' | 'audio'
    text_body TEXT,
    media_url TEXT,  -- For images/documents
    status VARCHAR(50),  -- 'sent' | 'delivered' | 'read' | 'failed'
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB,  -- Dati extra (coordinates, reply_to, etc)
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_whatsapp_messages_client ON whatsapp_messages(client_id);
CREATE INDEX idx_whatsapp_messages_from ON whatsapp_messages(from_number);
CREATE INDEX idx_whatsapp_messages_timestamp ON whatsapp_messages(timestamp DESC);

-- Mapping phone → client (per lookup veloce)
CREATE TABLE whatsapp_phone_mappings (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(50) UNIQUE NOT NULL,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_phone_mappings_phone ON whatsapp_phone_mappings(phone_number);
```

### Modifiche Tabelle Esistenti

```sql
-- Aggiungi colonna whatsapp_verified (per sapere se numero è verificato)
ALTER TABLE clients
ADD COLUMN whatsapp_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN whatsapp_last_message_at TIMESTAMP;

-- Index per performance
CREATE INDEX idx_clients_whatsapp ON clients(whatsapp) WHERE whatsapp IS NOT NULL;
```

---

## Implementation Steps

### Phase 1: Setup & Foundation (Giorni 1-2)

**Tasks:**

- [ ] Crea Meta Business Account
- [ ] Setup app WhatsApp Business API
- [ ] Genera access token
- [ ] Configura numero telefono test
- [ ] Deploy webhook endpoint su Fly.io
- [ ] Verifica webhook con Meta

**Deliverable:** Webhook funzionante che riceve messaggi test

---

### Phase 2: Message Processing Pipeline (Giorni 3-4)

**Tasks:**

- [ ] Implementa webhook signature verification
- [ ] Parse incoming message structure
- [ ] Phone number normalization (+62...)
- [ ] Client lookup logic (by phone)
- [ ] Create database schema (whatsapp_messages, phone_mappings)
- [ ] Save message to DB

**Deliverable:** Messaggi WhatsApp salvati in database

---

### Phase 3: AI Extraction (Giorni 5-6)

**Tasks:**

- [ ] Implementa AI extraction service (Gemini 1.5 Pro)
- [ ] Test prompt con vari esempi
- [ ] Error handling (fallback se AI fails)
- [ ] Auto-create client from extracted data
- [ ] Link messaggio a cliente

**Deliverable:** Nuovi clienti creati automaticamente da WhatsApp

---

### Phase 4: Frontend Integration (Giorni 7-8)

**Tasks:**

- [ ] Aggiungi tab "WhatsApp" in client detail page
- [ ] Timeline shows WhatsApp messages con icona speciale
- [ ] Link "Open in WhatsApp Web" (https://wa.me/{number})
- [ ] (Optional) Quick reply button (send via API)
- [ ] Badge "New WhatsApp message" se unread

**Deliverable:** Team vede conversazioni WhatsApp in CRM

---

### Phase 5: Auto-Assignment & Notifications (Giorno 9)

**Tasks:**

- [ ] Round-robin assignment logic (distribuisce lead ai team members)
- [ ] Email notification "Nuovo lead WhatsApp"
- [ ] In-app notification badge
- [ ] (Optional) Slack webhook integration

**Deliverable:** Team riceve alert automatici per nuovi lead

---

### Phase 6: Testing & Rollout (Giorno 10)

**Tasks:**

- [ ] Test end-to-end con numero reale
- [ ] Test edge cases (emoji, media, group messages)
- [ ] Performance testing (100 messaggi simultanei)
- [ ] Rollout graduale (1 team member → 5 → all 17)
- [ ] Monitoring & logging

**Deliverable:** Sistema live in produzione

---

## Costi & Limitazioni

### Costi WhatsApp Business API

**Cloud API Pricing (2026):**

| Tipo Messaggio             | Costo (per messaggio) | Note                   |
| -------------------------- | --------------------- | ---------------------- |
| **Inbound** (cliente → te) | **GRATIS**            | Sempre gratuito ✅     |
| **Outbound - Business**    | ~$0.005-0.02          | Varia per paese        |
| **Outbound - Marketing**   | ~$0.03-0.05           | Promozioni, newsletter |
| **Outbound - Utility**     | ~$0.01                | OTP, conferme ordine   |

**Esempi Costo Mensile:**

**Scenario Low (100 clienti/mese):**

- 100 lead inbound WhatsApp: **$0** (gratis)
- 50 risposte outbound: ~$0.50
- **Totale: ~$1-2/mese**

**Scenario Medium (500 clienti/mese):**

- 500 lead inbound: **$0**
- 300 risposte outbound: ~$3-5
- **Totale: ~$5-10/mese**

**Scenario High (2000 clienti/mese):**

- 2000 lead inbound: **$0**
- 1500 risposte outbound: ~$15-25
- **Totale: ~$25-40/mese**

**CONCLUSIONE:** Costi bassissimi. Anche con 2K clienti/mese = <$50/mese.

---

### Costi AI Extraction (Gemini 1.5 Pro)

**Gemini 1.5 Pro Pricing:**

- Input: $0.00125 / 1K tokens
- Output: $0.005 / 1K tokens

**Stima per messaggio:**

- Prompt: ~200 tokens
- Response: ~100 tokens
- **Costo: ~$0.0005 per messaggio** (mezzo centesimo)

**Mensile (500 nuovi clienti):**

- 500 extractions × $0.0005 = **$0.25/mese**

**TRASCURABILE** ✅

---

### Rate Limits

**Cloud API (Free Tier):**

- 1,000 conversazioni gratuite/mese
- 250 messaggi/secondo (burst)
- 80 messaggi/secondo (sostenuto)

**Se superi:**

- Pay-as-you-go automatico
- Nessun downtime

**Per 17 team members:**

- Anche se tutti scrivono contemporaneamente: 17 messaggi << 250/sec
- **Nessun problema** ✅

---

### Limitazioni Tecniche

1. **Numero WhatsApp dedicato richiesto**
   - Non puoi usare numero personale
   - Serve numero business dedicato
   - Una volta attivato su API, non funziona più su WhatsApp normale
   - **Soluzione:** Prendi nuovo numero business

2. **Template messages per iniziare conversazione**
   - TU non puoi scrivere per primo a cliente (spam prevention)
   - Cliente deve scrivere per primo
   - OPPURE usi template pre-approvati da Meta
   - **Soluzione:** Usa QR code / link wa.me per far scrivere cliente

3. **Media files limit**
   - Immagini: max 5MB
   - Documenti: max 100MB
   - Audio: max 16MB
   - **Soluzione:** Comprimi o usa Google Drive link

4. **Business Verification richiesta**
   - Per volumi >1000 conversazioni/mese
   - Richiede documenti azienda
   - Verifica in 1-3 giorni lavorativi
   - **Soluzione:** Fallo subito, non aspettare

---

## Testing Plan

### Unit Tests

```python
# tests/test_whatsapp_webhook.py

async def test_webhook_signature_verification():
    """Test che signature invalida viene rifiutata"""
    response = await client.post(
        "/webhook/whatsapp",
        json={"test": "data"},
        headers={"X-Hub-Signature-256": "invalid_signature"}
    )
    assert response.status_code == 401


async def test_parse_incoming_message():
    """Test parsing messaggio WhatsApp"""
    webhook_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "6281234567890",
                        "text": {"body": "Ciao, sono Marco"},
                        "timestamp": "1674567890"
                    }]
                }
            }]
        }]
    }

    parsed = parse_whatsapp_webhook(webhook_payload)
    assert parsed["phone"] == "+6281234567890"
    assert "Marco" in parsed["message"]


async def test_ai_extraction():
    """Test AI estrae dati correttamente"""
    result = await extract_client_data(
        message="Hi, I'm John from Australia. Need KITAS help",
        phone="+6287654321"
    )

    assert result["full_name"] == "John"
    assert result["nationality"] == "Australian"
    assert "KITAS" in result["service_interest"]
```

### Integration Tests

```python
async def test_end_to_end_new_client():
    """
    Test completo: messaggio WhatsApp → cliente creato in DB
    """
    # 1. Simula webhook WhatsApp
    webhook_data = create_test_webhook(
        from_number="+6281111111",
        message="Ciao, sono Test User. Info su PT PMA?"
    )

    # 2. Invia a webhook endpoint
    response = await client.post("/webhook/whatsapp", json=webhook_data)
    assert response.status_code == 200

    # 3. Verifica cliente creato
    async with db_pool.acquire() as conn:
        client_id = await conn.fetchval(
            "SELECT id FROM clients WHERE whatsapp = $1",
            "+6281111111"
        )
        assert client_id is not None

        # 4. Verifica messaggio salvato
        message_count = await conn.fetchval(
            "SELECT COUNT(*) FROM whatsapp_messages WHERE client_id = $1",
            client_id
        )
        assert message_count == 1
```

### Manual Testing Checklist

- [ ] Test numero reale: invia messaggio → vedi in CRM
- [ ] Test emoji: "Ciao 🌴" → salvato correttamente
- [ ] Test media: invia foto → URL salvato
- [ ] Test cliente esistente: scrivi di nuovo → appende a timeline
- [ ] Test nome con accenti: "José María" → salvato correttamente
- [ ] Test numero senza +: normalizza a formato internazionale
- [ ] Test 10 messaggi simultanei: nessun lag/errore
- [ ] Test messaggio molto lungo (4000 char) → troncato/gestito

---

## Security Considerations

### 1. Webhook Signature Verification

```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verifica che webhook venga davvero da Meta
    """
    expected_signature = hmac.new(
        key=WHATSAPP_APP_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Signature header format: "sha256=<hash>"
    signature_hash = signature.replace("sha256=", "")

    return hmac.compare_digest(expected_signature, signature_hash)
```

**IMPORTANTE:** Sempre verifica signature! Altrimenti chiunque può inviare fake webhook.

### 2. Access Token Rotation

```python
# Ruota token ogni 60 giorni
# Usa Meta System User per generare long-lived tokens (60gg)
# Reminder automatico per rinnovare

# .env
WHATSAPP_ACCESS_TOKEN=EAAxxxx  # Current token
WHATSAPP_TOKEN_EXPIRES_AT=2026-03-22  # Track expiry
```

### 3. Rate Limiting

```python
# Previeni abusi: max 10 richieste/sec per IP
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/webhook/whatsapp")
@limiter.limit("10/second")
async def whatsapp_webhook(request: Request):
    ...
```

### 4. PII Data Protection

```python
# Cripta numeri telefono sensibili nel database
# Oppure hash per lookup

from cryptography.fernet import Fernet

def encrypt_phone(phone: str) -> str:
    """Cripta numero per privacy"""
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.encrypt(phone.encode()).decode()

def decrypt_phone(encrypted: str) -> str:
    """Decripta per display"""
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted.encode()).decode()
```

**GDPR Compliance:** Clienti possono richiedere cancellazione dati → implementa endpoint DELETE.

---

## Next Steps

### Immediate (This Week)

1. **Decide:** Iniziamo setup Meta Business Account?
2. **Assign:** Chi nel team gestirà numero WhatsApp business?
3. **Budget:** Approva ~$50/mese per API calls (stima conservativa)

### Week 1

- Setup Meta account + app
- Generate tokens
- Deploy webhook endpoint

### Week 2

- Implement AI extraction
- Test con numero reale
- Rollout to 1-2 team members

### Week 3-4

- Full team rollout
- Monitor & optimize
- Training team su nuova feature

---

**Ready to start?** 🚀

Dimmi se:

1. Vuoi che inizi subito con **setup Meta account** (posso guidarti step-by-step)
2. Vuoi che scriva prima il **codice webhook** (così è pronto quando hai credenziali)
3. Hai domande su **costi, sicurezza, o limitazioni**

**Cosa facciamo per primo?**
