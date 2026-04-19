# Build Plan 00 — Shared Infrastructure

**Prerequisito per tutti i file 01-04.**

## Cosa fa

Le 4 app condividono 5 componenti infrastrutturali. Si costruiscono una volta qui, si referenziano da 01-04 senza reimplementare.

1. **CRM Lead Handoff** — `POST /api/lead/capture` → record `lead_intents` + genera URL WhatsApp precompilato
2. **WhatsApp deeplink** — schema messaggio con context per app
3. **Analytics tracking** — eventi standard cross-app (`app_viewed`, `app_form_submitted`, `app_cta_clicked`, `app_whatsapp_handoff`)
4. **Shared UI components** — 8 componenti in `packages/core/components/apps/` (AppFrame, AppHeroForm, AppResultScorecard, ecc.)
5. **Email Brevo infrastructure** — template engine + scheduler cron + unsubscribe tokens

## Migrations

### 117 — `lead_intents`

```sql
CREATE TABLE lead_intents (
  id          VARCHAR(20) PRIMARY KEY,  -- li_<nanoid>
  source      VARCHAR(32) NOT NULL,     -- visa_clock | visa_match | kbli_decoder | kbli_builder | tax_gap | zoning_check
  context     JSONB NOT NULL,           -- app-specific payload
  utm         JSONB,
  fingerprint VARCHAR(32),
  whatsapp_url TEXT NOT NULL,
  matched_client_id VARCHAR(20),        -- filled by cron quando CRM match
  matched_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at  TIMESTAMPTZ NOT NULL      -- 7-day TTL
);
```

### 118 — `email_subscriptions`

```sql
CREATE TABLE email_subscriptions (
  id           SERIAL PRIMARY KEY,
  email        VARCHAR(255) NOT NULL,
  app          VARCHAR(32) NOT NULL,
  context_hash VARCHAR(20) NOT NULL,
  trigger_type VARCHAR(32) NOT NULL,
  next_fire_at TIMESTAMPTZ,
  fired_count  INT NOT NULL DEFAULT 0,
  unsubscribed BOOLEAN NOT NULL DEFAULT FALSE,
  unsubscribe_token VARCHAR(32) NOT NULL UNIQUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## API: `POST /api/lead/capture`

```json
Request:
{
  "source": "visa_clock | visa_match | kbli_decoder | kbli_builder | tax_gap | zoning_check",
  "context": { /* app-specific */ },
  "utm": { "utm_source": "homepage_v2", "utm_campaign": "<app>" },
  "client_fingerprint": "<nanoid16>"
}

Response 201:
{
  "lead_intent_id": "li_abc123",
  "whatsapp_url": "https://wa.me/6281XXX?text=<encoded>",
  "expires_at": "2026-04-26T00:00:00Z"
}
```

## WhatsApp deeplink schema

```
Hi Bali Zero — I just used [APP_NAME] on your site.

Context:
• [Key 1]: [Value 1]
• [Key 2]: [Value 2]
• [Key 3]: [Value 3]

Reference: <balizero.com/<app>/<hash>>
Lead ID: li_abc123
```

Builder Python: `backend/services/lead_capture/whatsapp_deeplink.py`.

## Cron sync `lead_intent → clients`

`*/5 * * * *` Air OpenClaw. Ogni 5min:

1. Legge `lead_intents` non matched + WhatsApp messages arrivati negli ultimi 30min
2. Match by phone + time window
3. UPDATE `lead_intents.matched_client_id` + `clients.lead_source` + `clients.lead_metadata`

## Analytics events standard

```typescript
type FunnelAppEvent =
  | { type: "app_viewed"; app: AppName }
  | { type: "app_branch_selected"; app: AppName; branch: string }
  | { type: "app_form_started"; app: AppName; field: string }
  | { type: "app_form_submitted"; app: AppName; payload_keys: string[] }
  | {
      type: "app_wizard_step_completed";
      app: AppName;
      step: number;
      total: number;
    }
  | { type: "app_wizard_abandoned"; app: AppName; last_step: number }
  | { type: "app_result_viewed"; app: AppName; result_hash: string }
  | {
      type: "app_cta_clicked";
      app: AppName;
      cta_label: string;
      destination: string;
    }
  | { type: "app_whatsapp_handoff"; app: AppName; lead_intent_id: string }
  | { type: "app_share_clicked"; app: AppName; channel: string }
  | { type: "app_pdf_downloaded"; app: AppName }
  | { type: "app_email_subscribed"; app: AppName; trigger_type: string };
```

Hook: `packages/core/analytics/useFunnelApp.ts`.

## Shared UI components

In `packages/core/components/apps/`:

- `AppFrame` — container mobile-first 2-col desktop
- `AppHeroForm` — form above-the-fold (1-3 campi)
- `AppBranchSelector` — 2-card branch picker per app multi-ramo
- `AppWizard` — multi-step form con progress bar + back button
- `AppResultScorecard` — grid scorecard (Tax Gap, KBLI)
- `AppResultTimeline` — timeline (Visa Clock)
- `AppResultMap` — mappa result (Zoning)
- `AppShareBar` — copy-link + social share
- `AppWhatsAppCTA` — primary CTA → `/api/lead/capture` → `wa.me`
- `AppPreview` — "what your result looks like" embed
- `AppTrustStrip` — 3 numeri concreti (no "5k+ clients ★4.9")
- `AppCoverageDisclaimer` — usato da Zoning per fuori-coverage case

## Email Brevo

Template dir: `backend/services/notifications/funnel_email/templates/`. Sender `zantara@balizero.com` (regola CLAUDE.md §14). Unsubscribe token in ogni email, one-click dereg.

## Env vars

- `WA_BUSINESS_NUMBER` (da settare)
- `SENDGRID_API_KEY` (già presente — chiave Brevo `xkeysib-...`)
- `NEXT_PUBLIC_GOOGLE_MAPS_KEY` (già presente)

## Acceptance criteria

- [ ] `POST /api/lead/capture` ritorna 201 + WhatsApp URL entro 200ms
- [ ] Cron matcher `lead_intent → clients` match rate ≥ 80% entro 30min
- [ ] `useFunnelApp` hook importabile da tutte le app
- [ ] 11 shared UI components con snapshot test Vitest
- [ ] Email Brevo test arriva a `antonellosiano@gmail.com`
- [ ] Unsubscribe token one-click funziona
- [ ] Migration 117 + 118 appliable senza data loss

## Dependencies gate per sbloccare 01-04

- [ ] Shared infra deployata staging
- [ ] `lead_intents` + `email_subscriptions` live
- [ ] E2E test mock-app → WA → CRM verde
