# Welcome Communication System — Design Spec

**Date:** 2026-03-26
**Status:** Approved
**Author:** Claude Code (brainstorming session)

---

## Overview

Automated welcome communications triggered at two CRM lifecycle moments:

1. `create_client` — WhatsApp (immediate) + Email (30 min delay)
2. `create_practice` — WhatsApp + Email (practice-specific content)

Goal: reduce buyer's remorse in the first 5 minutes, establish human+AI identity, deliver the brochure.

---

## Architecture

```
create_client ──┬──► WelcomeWhatsAppService.send_client_welcome()    T+0s (max 60s)
                └──► WelcomeEmailService.send_client_welcome()        T+30min

create_practice ──► WelcomePracticeService.send_practice_kickoff()   T+0s
```

All three services live in `backend/services/crm/welcome/`:

- `welcome_whatsapp_service.py`
- `welcome_email_service.py`
- `welcome_practice_service.py`
- `brochure_generator.py` (one-time static PDF builder, not runtime)

Triggered from the existing CRM router via `BackgroundTasks.add_task()` — non-blocking, no new scheduler.

Idempotency: checked via `activity_log` table (existing). Action keys:

- `welcome_whatsapp_sent`
- `welcome_email_sent`
- `practice_kickoff_whatsapp_sent`
- `practice_kickoff_email_sent`

---

## Trigger 1a — WhatsApp on `create_client`

### Guard conditions (skip silently if any fail)

- `client.phone` is not NULL and not empty
- No existing `activity_log` record with action=`welcome_whatsapp_sent` for this client
- `WHATSAPP_PHONE_NUMBER_ID` is configured on Fly.io

### Language resolution

```python
from backend.services.crm.birthday_notifier_service import NATIONALITY_LANGUAGE_MAP
lang = NATIONALITY_LANGUAGE_MAP.get(client.nationality, "en")
```

### Message templates (5 languages)

**EN (248 chars):**

```
Hi {first_name} ✅

Welcome to Bali Zero. {advisor_name} is your dedicated advisor and will reach out within 2 hours.

What's the best time for a quick call this week?
```

**IT (244 chars):**

```
Ciao {first_name} 👋

Benvenuto in Bali Zero. {advisor_name} è il tuo punto di riferimento — ti contatterà entro 2 ore.

Quando sei disponibile per una breve chiamata?
```

**RU (no emoji, formal):**

```
Здравствуйте, {first_name}.

Добро пожаловать в Bali Zero. {advisor_name} — ваш персональный консультант и свяжется с вами в течение 2 часов.

Когда вам удобно поговорить на этой неделе?
```

**UK:**

```
Вітаємо, {first_name} 👋

Ласкаво просимо до Bali Zero. {advisor_name} — ваш особистий консультант і зв'яжеться з вами протягом 2 годин.

Коли вам зручно поговорити цього тижня?
```

**ID:**

```
Halo {first_name} 👋

Selamat datang di Bali Zero. {advisor_name} adalah konsultan pribadi Anda dan akan menghubungi Anda dalam 2 jam.

Kapan waktu yang tepat untuk panggilan singkat minggu ini?
```

### Variables

- `{first_name}` = first word of `client.full_name`
- `{advisor_name}` = `client.assigned_to` first name, fallback: "our team" / "il nostro team" / "наша команда" / "наша команда" / "tim kami"

### Phone format

Strip `+` prefix: `phone.lstrip("+")` — Meta API requires no `+`.

### Meta API template requirement

These are **Marketing category** templates. Must be pre-approved in Meta Business Manager before going live. Template names: `balizero_welcome_en`, `balizero_welcome_it`, `balizero_welcome_ru`, `balizero_welcome_uk`, `balizero_welcome_id`.

**IMPORTANT:** The trigger code is implemented but the `_ACTIVE = False` flag prevents sending until templates are approved and the flag is manually flipped to `True`. This is the activation gate.

---

## Trigger 1b — Email on `create_client` (30-min delay)

### Implementation of delay

`BackgroundTasks` cannot natively delay. Use `asyncio.sleep(1800)` inside the background task, or schedule via APScheduler with `run_date=now+30min`. Use APScheduler since the scheduler is already running.

### Guard conditions

- `client.email` is not NULL
- No existing `activity_log` with action=`welcome_email_sent`

### Subject lines (per language)

- EN: `You're in good hands — Bali Zero`
- IT: `Sei in buone mani — Bali Zero`
- RU: `Вы в надёжных руках — Bali Zero`
- UK: `Ви в надійних руках — Bali Zero`
- ID: `Anda dalam tangan yang baik — Bali Zero`

### Email structure (HTML, inline styles, Brevo-compatible)

**Block 1 — Emotional opening (3 lines)**
Speaks to the client's moment, not the company. "You've just made a courageous decision." Not "Thank you for choosing us."
Per language, acknowledges the courage/boldness of choosing to build a life/business in Indonesia.

**Block 2 — Who we really are (80 words)**
Honest story: born as a traditional consulting firm, evolved into a hybrid human+AI system. Today: team of human experts supported by specialized AI agents. The vast majority of our processes are deterministic (rules, checklists, regularly updated legal databases) — AI is surrounded by rigid guardrails and never invents regulatory data or prices.

**Block 3 — How it works (2-column visual)**
| Deterministic System | Human Intelligence |
|---|---|
| Prices from a verified database | Strategy and judgment |
| Deadlines from a legal calendar | Client relationships |
| Documents from official registries | Complex negotiations |
| Status tracking and alerts | Problem solving |

**Block 4 — Our services (4 cards)**

- Immigration (visas, KITAS, KITAP)
- Business Setup (PT PMA, virtual office)
- Tax & Compliance
- Property

**Block 5 — Your team**
Name + role of `assigned_to`. If not yet assigned: "Your advisor will be assigned by today."

**Block 6 — Single CTA**
"Reply to this email" — reply-based, no external link.

**Block 7 — Footer**
`zantara@balizero.com | wa.me/6281338051876 | www.balizero.com | Canggu, Bali`

### Attachment

Static PDF: `data/assets/brochure_balizero_en.pdf` (one file for all languages — brochure is in English only as the lingua franca for international clients). Attached via Brevo API `attachment` field as base64.

### Sending

Via existing internal endpoint: `POST /api/notifications/send-email` with `X-API-Key: zantara-secret-2024`. Same pattern as `birthday_notifier_service.py`.

---

## Trigger 2 — WhatsApp + Email on `create_practice`

### WhatsApp (practice-specific)

4 variants by `practice_type_code`: `KITAS`, `PT_PMA`, `TAX`, `PROPERTY`.
Template naming: `balizero_practice_kickoff_{type}_{lang}` — however since this grows to 4×5=20 templates, use a single generic template with a variable for the service name instead:

```
balizero_practice_kickoff (single template, all languages):
Hi {first_name} 👋

Your {service_name} case is now open (ID: {practice_id}).
{advisor_name} is your case handler.

Step 1: we'll send you the document checklist today.
Any questions? Reply here.
```

`{service_name}` = human-readable name per language per type:

- KITAS/EN: "KITAS permit", IT: "permesso KITAS", RU: "разрешение KITAS"
- PT_PMA/EN: "PT PMA company", IT: "società PT PMA"
- TAX/EN: "tax registration", IT: "registrazione fiscale"
- PROPERTY/EN: "property service", IT: "servizio immobiliare"

### Email (practice-specific)

Subject: `Your {service_name} — next steps | Bali Zero`

Content:

1. Confirmation of practice opening
2. Estimated timeline for this specific service type
3. Document checklist for this practice type (static per type, from knowledge base)
4. Link to client portal: `https://my.balizero.com`
5. Case handler name + contact

Document checklists per type (static, embedded in service):

- **KITAS:** passport (all pages), recent photos, previous permits/visas
- **PT PMA:** passport, NPWP (if applicable), business plan outline, local partner agreement (if applicable)
- **TAX:** passport, KITAS/KITAP copy, proof of income
- **PROPERTY:** passport, KITAS copy, proof of funds, property details

---

## Brochure PDF

### Generation

One-time script: `scripts/generate_brochure.py`
Uses `reportlab` (already in `requirements-prod.txt`).
Output: `data/assets/brochure_balizero_en.pdf`

### Palette

- Background: `#0c0c0e`
- Primary accent: `#d4845a` (terracotta)
- Secondary accent: `#c9a96e` (antique gold)
- Text: `#edeae4`

### Pages

1. **Cover** — BZ logo + tagline "Guided by humans. Powered by AI." + "Bali Zero — Canggu, Bali"
2. **Who we are** — founding story, human+AI evolution, 5000+ clients, key numbers
3. **Immigration** — visa types with "from Rp X" pricing anchors
4. **Business Setup** — PT PMA, virtual office, key services
5. **Tax & Compliance** — services overview
6. **How we work** — deterministic system infographic + AI guardrails explanation
7. **Contact** — WhatsApp, email, address, QR code to my.balizero.com

### Regeneration

Run `scripts/generate_brochure.py` whenever services/prices change. Commit the new PDF to git.

---

## File Structure

```
backend/services/crm/welcome/
├── __init__.py
├── welcome_whatsapp_service.py     # Trigger 1a
├── welcome_email_service.py        # Trigger 1b
├── welcome_practice_service.py     # Trigger 2
└── welcome_templates.py            # All message strings per lang

data/assets/
└── brochure_balizero_en.pdf        # Static, committed to repo

scripts/
└── generate_brochure.py            # One-time PDF generator

backend/app/routers/clients.py      # Modified: add BackgroundTasks trigger
backend/app/routers/practices.py    # Modified: add BackgroundTasks trigger
```

---

## Activation Gate

```python
# welcome_whatsapp_service.py
_WHATSAPP_WELCOME_ACTIVE = False  # Flip to True after Meta template approval

# welcome_email_service.py
_EMAIL_WELCOME_ACTIVE = True  # Email can go live immediately
```

Email goes live on deploy. WhatsApp only after Meta template approval and manual flag flip.

---

## Error Handling

All welcome services:

- Wrapped in `try/except Exception` — never raise to caller
- Log errors with `logger.error(..., exc_info=True)`
- Failures do NOT block client/practice creation
- No retry logic (first version) — rely on idempotency check: if not in `activity_log`, next manual trigger or cron can retry

---

## Testing

- Unit tests for each service with mocked `db_pool`, mocked WhatsApp/email API
- Test idempotency: calling twice should not send twice
- Test language resolution: Italian client → IT template, unknown nationality → EN
- Test guard conditions: no phone → skip WhatsApp gracefully
- Test `_WHATSAPP_WELCOME_ACTIVE = False` → no send, no error

---

## What is NOT in scope (Phase 1)

- 3-email drip sequence (day 0/3/7) — Phase 2
- ML-based personalization — out of scope
- Analytics dashboard — reuse existing `activity_log` queries
- WhatsApp Quick Reply buttons — requires Meta template with buttons, add in Phase 2
- Multi-language brochure PDF — English only for now
