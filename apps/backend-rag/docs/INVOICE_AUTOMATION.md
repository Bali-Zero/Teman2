# Invoice Automation System

> **Stato:** ✅ ATTIVO E FUNZIONANTE (Feb 2026)

## Panoramica

Sistema automatizzato per la generazione e invio di fatture quando una pratica CRM cambia stato in `sending_invoice`.

### Workflow Automatico

Quando una pratica viene impostata su **"Sending Invoice"**:

1. ✅ **Genera PDF fattura** localmente
2. ✅ **Invia email al cliente** con PDF allegato (via SMTP Zoho)
3. ✅ **Notifica Asya** (asya@balizero.com) via email
4. ✅ **Carica backup su Google Drive** nella cartella del cliente
5. ✅ **Aggiorna pratica** con dettagli fattura

---

## Configurazione

### Zoho Invoice API

| Parametro      | Valore                                |
| -------------- | ------------------------------------- |
| Client ID      | `1000.PRPSP7KG3NZU9KYCVMZHGSGFXYSJMZ` |
| Account        | zero@balizero.com                     |
| Scope          | `ZohoInvoice.fullaccess.all`          |
| Token Scadenza | Auto-refresh (refresh token valido)   |

### SMTP Configuration (Zoho Mail Pro)

| Parametro    | Valore              |
| ------------ | ------------------- |
| Host         | `smtppro.zoho.com`  |
| Port         | `587`               |
| Encryption   | STARTTLS            |
| Username     | `zero@balizero.com` |
| Sender Name  | `Bali Zero AI`      |
| Sender Email | `zero@balizero.com` |

**Environment Variables:**

```bash
SMTP_HOST=smtppro.zoho.com
SMTP_PORT=587
SMTP_USER=zero@balizero.com
SMTP_PASSWORD=Balizero2020!
SMTP_FROM=zero@balizero.com
```

---

## Fallback System

L'email ha un sistema di fallback a due livelli:

1. **Primario:** Zoho Mail API (via OAuth)
   - Usa token OAuth con scope `ZohoMail.messages.ALL`
   - Richiede configurazione API in Zoho Mail (non attualmente attiva)
2. **Fallback:** SMTP Zoho Pro
   - Attivato automaticamente se Zoho API fallisce
   - Funziona con configurazione SMTP standard
   - ✅ **Attualmente in uso**

---

## Destinatari Email

### Email al Cliente

- **Da:** Bali Zero AI <zero@balizero.com>
- **A:** [Email cliente dalla pratica]
- **Oggetto:** Invoice [NUMERO] from Bali Zero AI
- **Allegato:** PDF Fattura

### Email a Asya (Notifica)

- **Da:** Bali Zero AI <zero@balizero.com>
- **A:** asya@balizero.com
- **Oggetto:** 🎉 New Invoice [NUMERO] - [Nome Cliente]
- **Allegato:** PDF Fattura
- **Contenuto:** Dettagli pratica + prossimi step

---

## Google Drive Backup

I PDF delle fatture vengono caricati automaticamente nella cartella Google Drive del cliente:

- **Location:** `{client_drive_folder_id}`
- **Filename:** `Invoice_INV-YYYYMMDD-XXXXX.pdf`
- **Link:** Disponibile nel campo `drive_link` della pratica

---

## Utilizzo

### Tramite API

Cambia stato di una pratica a `sending_invoice`:

```bash
curl -X PUT https://nuzantara-rag.fly.dev/api/crm/practices/123 \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "sending_invoice"}'
```

L'automazione parte automaticamente in background.

### Tramite Interfaccia CRM

1. Apri una pratica
2. Cambia lo stato a "Sending Invoice"
3. Il sistema genera e invia automaticamente la fattura

---

## Test e Verifica

### Test SMTP

```bash
fly ssh console --app nuzantara-rag
python3 -c "
import asyncio
from backend.app.modules.notifications.service import SMTPProvider
smtp = SMTPProvider()
asyncio.run(smtp.send_email(
    to_email='test@example.com',
    subject='Test',
    html_body='<h1>Test</h1>',
    from_email='zero@balizero.com',
    from_name='Bali Zero AI'
))
"
```

### Test Automazione Completa

```bash
# Via SSH su Fly.io
python3 << 'PYEOF'
import asyncio
import asyncpg
import os
from backend.services.invoicing.invoice_service import InvoiceAutomationService

async def test():
    pool = await asyncpg.create_pool(os.environ.get("DATABASE_URL"))
    service = InvoiceAutomationService(pool)
    result = await service.trigger_on_sending_invoice(123, "test@balizero.com")
    print(result)
    await pool.close()

asyncio.run(test())
PYEOF
```

---

## Troubleshooting

### Errore "Authentication Failed"

- Verificare che SMTP_PASSWORD sia corretta
- Per Zoho: usare la password normale dell'account (non App Password)
- Verificare che l'account non abbia 2FA che blocca SMTP

### Errore "URL_RULE_NOT_CONFIGURED"

- Normale se Zoho Mail API non è configurata
- Il sistema passa automaticamente a SMTP fallback

### Email non arrivano

1. Controllare SPAM/Junk folder
2. Verificare che l'email del cliente esista
3. Controllare i log: `fly logs --app nuzantara-rag`

---

## Stato Token OAuth

| Servizio         | Stato              | Scadenza     |
| ---------------- | ------------------ | ------------ |
| Zoho Invoice API | ✅ Attivo          | Auto-refresh |
| Zoho Mail API    | ⚠️ Non configurato | N/A          |
| SMTP Zoho        | ✅ Attivo          | Permanente   |

---

## Note Tecniche

- **Servizio:** `InvoiceAutomationService` in `backend/services/invoicing/invoice_service.py`
- **SMTP Provider:** `SMTPProvider` in `backend/app/modules/notifications/service.py`
- **Database Token:** Tabella `zoho_email_tokens`
- **Deploy:** Rolling deploy su Fly.io

---

## Ultimo Aggiornamento

**22 Febbraio 2026**

- ✅ Configurazione SMTP Zoho Pro completata
- ✅ Fallback SMTP attivato
- ✅ Test invio email riuscito
- ✅ Sistema pronto per produzione
