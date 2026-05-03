# nuzantara-send-email

**Per:** Claude Code, Gemini CLI, OpenClaw
**Versione:** 1.0.0
**Attivazione:** quando si deve inviare email, configurare email, debug email, o lavorare su servizi che mandano email

---

## Quick Reference

### Inviare una email

```bash
# Via MCP tool (modo più semplice)
mcp__nuzantara-mcp__send_email(to="dest@email.com", subject="Oggetto", body="<p>HTML body</p>")

# Via curl (da script/cron)
curl -X POST https://nuzantara-rag.fly.dev/api/notifications/send-email \
  -H "X-API-Key: zantara-secret-2024" \
  -H "Content-Type: application/json" \
  -d '{"to":"dest@email.com","subject":"Oggetto","body":"<p>HTML body</p>"}'

# Con CC
-d '{"to":"dest@email.com","subject":"Oggetto","body":"<p>Body</p>","cc":"cc1@email.com,cc2@email.com"}'
```

### Routing automatico (non devi scegliere)

| Destinatario    | Canale primario | Fallback  | Perché                                                           |
| --------------- | --------------- | --------- | ---------------------------------------------------------------- |
| `@balizero.com` | Zoho SMTP       | Brevo     | Zoho rifiuta email intra-dominio da Brevo (554 policy violation) |
| Tutti gli altri | Brevo HTTP API  | Zoho SMTP | Brevo ha migliore deliverability e tracking                      |

**Sender sempre:** `zantara@balizero.com` (alias di `damar@balizero.com` in Zoho Mail)
**Display name:** "Zantara"

---

## Architettura

### Endpoint centrale

`POST /api/notifications/send-email` — **UNICO punto di invio.** Tutti i servizi CRM lo usano.

File: `backend/app/modules/notifications/router.py`

### Provider

1. **Brevo** (ex SendGrid/Sendinblue)
   - API key: `SENDGRID_API_KEY` (inizia con `xkeysib-`)
   - URL: `https://api.brevo.com/v3/smtp/email`
   - Account: `zero@balizero.com`, free plan, 300 email/giorno
   - Dominio `balizero.com` autenticato (DKIM + DMARC + SPF)

2. **Zoho SMTP**
   - Host: `smtppro.zoho.com:587` (STARTTLS)
   - User: `zero@balizero.com`
   - Password: App Password in `ZOHO_SMTP_PASSWORD` (NON la password di login)
   - Può mandare come `zantara@balizero.com` (alias configurato in Zoho Mail)

3. **Zoho OAuth** (per ZohoEmailService — usato da invoice con allegati)
   - Self Client ID: `1000.PRPSP7KG3NZU9KYCVMZHGSGFXYSJMZ`
   - Tokens in tabella `zoho_email_tokens`
   - Se scade: api-console.zoho.com → Self Client → genera code → scambia via API

---

## Email automatiche attive

### Trigger da cambio status practice (in `crm_practices.py`)

| Status                | Email               | Destinatario          | Servizio                     |
| --------------------- | ------------------- | --------------------- | ---------------------------- |
| → `waiting_documents` | Richiesta documenti | Cliente + Team leader | WaitingDocumentsService      |
| → `sending_invoice`   | Invoice PDF         | Cliente + Asya        | InvoiceAutomationService     |
| → `on_process`        | Conferma inizio     | Cliente + Team leader | ProcessAutomationService     |
| → `completed`         | Congratulazioni     | Cliente + Team leader | CompletedProcessService      |
| → `completed`         | HR Bonus pending    | asya@balizero.com     | `_notify_hr_bonus_pending()` |

### Trigger da creazione

| Evento         | Email               | Destinatario | Note                                                                   |
| -------------- | ------------------- | ------------ | ---------------------------------------------------------------------- |
| Nuovo cliente  | Welcome email       | Cliente      | 30min delay (APScheduler) — **ATTENZIONE: non funziona con auto_stop** |
| Nuova practice | Kickoff + checklist | Cliente      | Immediata via BackgroundTasks                                          |

### Cron notifiers

```bash
# Tutti e 3 insieme
curl -X POST https://nuzantara-rag.fly.dev/api/cron/notifiers/all \
  -H "X-API-Key: zantara-secret-2024"

# Singoli
/api/cron/notifiers/visa-expiry        # Scadenze visa/KITAS/passaporto → team leader + zero@
/api/cron/notifiers/unpaid-invoices    # Fatture non pagate 7+ giorni → asya@
/api/cron/notifiers/stale-practices    # Pratiche ferme 7+ giorni → team leader + zero@
```

---

## Regole IMPORTANTI

1. **MAI mandare email direttamente** — usa sempre l'endpoint `/api/notifications/send-email` o il MCP tool `send_email`
2. **MAI usare `SendGridProvider` direttamente** — la key è Brevo, non SendGrid. L'endpoint gestisce tutto
3. **Sender SEMPRE `zantara@balizero.com`** — mai `zero@`, `nuzantara@`, `notifications@`
4. **HTML nel body** — l'endpoint accetta HTML. `\n` viene convertito in `<br>` solo nei servizi CRM che mandano testo
5. **Per allegati PDF** — usa `ZohoEmailService` (invoice_service.py pattern) con `upload_attachment()` + `send_email()`

---

## Debug

### Verificare delivery Brevo

```python
# Sul server Fly.io
fly ssh console -a nuzantara-rag -C "python3 -c '
import os, json, urllib.request
key = os.environ.get(\"SENDGRID_API_KEY\", \"\")
url = \"https://api.brevo.com/v3/smtp/statistics/events?limit=5&sort=desc&email=DEST@EMAIL\"
req = urllib.request.Request(url, headers={\"api-key\": key})
resp = urllib.request.urlopen(req)
print(json.dumps(json.loads(resp.read()), indent=2))
'"
```

### Verificare token Zoho

```sql
SELECT email_address, substring(access_token,1,20), token_expires_at, updated_at
FROM zoho_email_tokens;
```

### Rinfrescare token Zoho (se scaduto)

1. Vai su `api-console.zoho.com` → Self Client
2. Scope: `ZohoMail.messages.ALL,ZohoMail.accounts.READ`
3. Duration: 10 min → Generate
4. Scambia il code:

```bash
curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
  -d "code=IL_CODE&client_id=1000.PRPSP7KG3NZU9KYCVMZHGSGFXYSJMZ&client_secret=0fc67df092df8659dccd4e833beb2a90c8d9e20b18&grant_type=authorization_code"
```

5. Salva access_token e refresh_token nella tabella `zoho_email_tokens`

### Errori comuni

| Errore                             | Causa                                 | Fix                                                        |
| ---------------------------------- | ------------------------------------- | ---------------------------------------------------------- |
| `554 5.7.7 Email policy violation` | Brevo manda a @balizero.com           | Il routing lo gestisce — usa Zoho SMTP                     |
| `535 Authentication Failed`        | SMTP password sbagliata               | Rigenerare App Password in Zoho                            |
| `553 Sender not allowed to relay`  | from_email non è alias dell'SMTP user | Alias `zantara@` deve essere su `zero@` in Zoho Mail admin |
| `invalid_code` (Zoho OAuth)        | Code scaduto o client_id sbagliato    | Usa Self Client ID, genera code nuovo                      |

---

## Credenziali (rif: NUZANTARA_ENV_KEYS.env)

| Chiave               | Valore                | Note                         |
| -------------------- | --------------------- | ---------------------------- |
| `ZOHO_SMTP_PASSWORD` | App Password          | NON la password di login     |
| `SENDGRID_API_KEY`   | `xkeysib-...`         | In realtà è Brevo            |
| `NUZANTARA_API_KEY`  | `zantara-secret-2024` | Auth per endpoint send-email |
| `ZOHO_CLIENT_ID`     | Self Client ID        | Per OAuth refresh            |
| `ZOHO_CLIENT_SECRET` | Self Client Secret    | Per OAuth refresh            |

---

## File chiave

| File                                                       | Ruolo                                               |
| ---------------------------------------------------------- | --------------------------------------------------- |
| `backend/app/modules/notifications/router.py`              | Endpoint centrale + smart routing                   |
| `backend/app/modules/notifications/service.py`             | SMTPProvider, SendGridProvider, NotificationService |
| `backend/services/integrations/zoho_email_service.py`      | Zoho OAuth email (per allegati)                     |
| `backend/services/crm/welcome/welcome_email_service.py`    | Welcome client email                                |
| `backend/services/crm/welcome/welcome_practice_service.py` | Practice kickoff email                              |
| `backend/app/routers/crm_practices.py`                     | Tutti i trigger status-change (L.1085-1141)         |
| `backend/app/routers/cron_notifiers.py`                    | Endpoint cron per i 3 notifier                      |
