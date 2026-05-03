# v2 Subdomain Rollout — 3-Layer SOTA Design

> **Status:** design (pre-plan)
> **Date:** 2026-04-17
> **Author:** Claude Opus 4.7 (Pro), brainstorming w/ Zero
> **Scope:** portare `packages/core` v2 + nav unificata + session bridge + analytics funnel-view ai 3 layer del sistema Bali Zero. Sostituisce il brief "8 subdomain" con modello 3-layer (Funnel Hub · Client App · Team Ops).

---

## 0. Decisione architetturale di base

Il brief originale chiedeva "mappare 7 subdomain restanti dopo balizero.com v2". Analisi di prod + MOS + ricerca SOTA ha mostrato che **11 target attivi** (homepage + 4 funnel L1 · 3 route L2 · 2 target L3 · 1 entry point mail/calendar/drive/knowledge redirect-only) + **1 legacy SEO redirect** (kbli-navigator) sono in realtà **3 layer** con responsabilità diverse, ognuno con la sua persona-theme:

| Layer             | Subdomain / route                                                                             | Persona              | Theme                                 |
| ----------------- | --------------------------------------------------------------------------------------------- | -------------------- | ------------------------------------- |
| **L1 Funnel Hub** | `balizero.com`, `visa.`, `balizero.com/kbli`, `tax.` (nuovo), `balizero.com/property` (nuovo) | 🟢 prospect non-auth | editorial (light, serif, copper)      |
| **L2 Client App** | `my.balizero.com/portal/*`, `prime.balizero.com/proposal/[token]`, `zantara.balizero.com`     | 🟡🔵 client auth     | operative-light (light+copper accent) |
| **L3 Team Ops**   | `kita.balizero.com/(workspace)`, `prime.balizero.com`                                         | team auth            | operative-dark (dark+copper glow)     |

I 4 subdomain `mail/calendar/drive/knowledge.balizero.com` restano redirect-only verso kita (middleware già lo fa). Le 4 app orfane `apps/{mail,calendar,drive,knowledge}/` vanno rimosse dal monorepo in sprint 5 (non servono, non raggiungibili, 0 uso di `@balizero/core`).

---

## 1. Subdomain map — stato → gap → priorità

| #   | Subdomain/Route                              | Layer | Stato oggi                                                                                      | Gap v2                                                                                                    | Priorità |
| --- | -------------------------------------------- | ----- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------- |
| 1   | `balizero.com`                               | L1    | v2 LIVE (commit `ea33987d9`, 2026-04-17)                                                        | FunnelFeature oggi linka `/services/{funnel}` invece dei tool reali                                       | P0 S1    |
| 2   | `visa.balizero.com`                          | L1    | v1, 181 pagine, 27 bug fixati 2026-04-13, 90pts Qdrant enrichiti                                | nav standalone, design isolato, no cross-funnel session, handoff non SOTA                                 | P0 S2    |
| 3   | `balizero.com/kbli` + `/kbli/[code]`         | L1    | v1, 1,563 SSG, `kbli-theme.css`                                                                 | theme frammentato, manca compare 2 codici, FAQ tax per codice, gap visivo layout                          | P0 S2    |
| 4   | `tax.balizero.com`                           | L1    | **non esiste** (DNS `code=000`); solo `docs/design-palettes/funnels/03-tax-calendar.html`       | crea domain + route group + iCal export + WA opt-in + upsell SPT                                          | P0 S2    |
| 5   | `balizero.com/property`                      | L1    | **non esiste** come tool pubblico                                                               | crea wrapper pubblico su `/api/prime/v2/analyze` (rate-limit 10/min già in prod) + eligibility F3 backend | P1 S2    |
| 6   | `my.balizero.com/portal/*`                   | L2    | v1 fase 3-5 UX parity (commit `742b4a306`, `24e87ebb7`, `4db627f5a`)                            | feature-tabs non matter-first; no WA push; no 3 hero cards; no family route                               | P1 S3    |
| 7   | `prime.balizero.com/proposal/[token]`        | L2    | live (3D + Prime Nexus Ultra 2026-04-06, 1629 entità geocodate, 53K RDTR poligoni)              | design isolato, no link a my., theme da riallineare                                                       | P2 S3    |
| 8   | `zantara.balizero.com`                       | L2    | live (rewrite `/` → `/chat`)                                                                    | chat v1, no matter-context pane                                                                           | P2 S3    |
| 9   | `kita.balizero.com/(workspace)`              | L3    | v1 dark-only, 17 route, `AppSidebar` + Header                                                   | no inbox-hub default, no Cmd+K, no context panel dx, no Prime toggle                                      | P2 S4    |
| 10  | `prime.balizero.com` (team)                  | L3    | Prime Nexus Ultra 7 feature 3D, CRM mode già completo (commits `97761e1`, `3820143`, `b1b0ba7`) | standalone, va esposto come `View as map` in /kita/clients                                                | P2 S4    |
| 11  | `mail/calendar/drive/knowledge.balizero.com` | L3    | redirect middleware → /email /calendar /documents /knowledge dentro kita                        | cleanup 4 app orfane in `apps/` (0 uso `@balizero/core`, irraggiungibili)                                 | P3 S5    |
| 12  | `balizero.com/kbli-navigator`                | L1    | 301 → /kbli (SEO legacy)                                                                        | keep redirect, no porting                                                                                 | —        |

---

## 2. Design system extension (`packages/core/`)

Stato attuale (verificato 2026-04-17):

```
packages/core/
├── tokens/
│   ├── primitives.css, semantic.css, index.css
│   └── themes/ { light, dark, editorial, graphite, ink, jungle, aubergine }.css
├── components/ { BZLogo, NavShell, ThemeProvider, WhatsAppFAB }.tsx
├── effects/ { grain, shimmer }.css
├── fonts/inter.ts
└── utils/
```

Estensione richiesta:

| File                                | Tipo                   | Scopo                                                                                       |
| ----------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------- |
| `tokens/themes/operative-light.css` | **nuovo** (non rename) | persona portal — creato duplicando `light.css` poi estendendo. `light.css` resta per compat |
| `tokens/themes/operative-dark.css`  | **nuovo** (non rename) | persona workspace + prime — idem vs `dark.css`                                              |
| `tokens/themes/editorial.css`       | extend                 | persona funnel (aggiungere tokens ads-free serif headline)                                  |
| `components/MatterCard.tsx`         | nuovo                  | card per pratica cliente (progress ring + deadline + pending docs)                          |
| `components/ProgressRing.tsx`       | nuovo                  | SVG ring 0-100% con stato colorato                                                          |
| `components/FunnelFrame.tsx`        | nuovo                  | wrapper layout 4 funnel (header+step+main+TrustBand+CTAHandoff)                             |
| `components/TrustBand.tsx`          | nuovo                  | 5000+ clienti · review · response time                                                      |
| `components/CTAHandoff.tsx`         | nuovo                  | 3-level CTA: PDF download · Zantara chat · WA deeplink                                      |
| `components/CommandPalette.tsx`     | nuovo                  | Cmd+K palette per kita                                                                      |
| `components/ContextPanel.tsx`       | nuovo                  | panel laterale dx workspace                                                                 |
| `components/DeadlineBadge.tsx`      | nuovo                  | countdown conic ring + status color                                                         |
| `components/NavShell.tsx`           | extend                 | aggiungere `persona` prop ∈ {funnel, portal, workspace}                                     |
| `components/ThemeProvider.tsx`      | extend                 | persona + light/dark selector                                                               |
| `auth/session-bridge.ts`            | nuovo                  | lead `bz_session` cookie ↔ SSO `nz_access_token` dopo login                                 |
| `analytics/funnel-view.ts`          | nuovo                  | GA4 + Postgres dual-track, attribution lead→client                                          |
| `utils/ical.ts`                     | nuovo                  | export iCal per Tax Calendar + portal deadlines                                             |
| `utils/wa-deeplink.ts`              | nuovo                  | costruttore deeplink `wa.me/628213107363?text=...` context-aware                            |

**Import discipline:** tutti i 10 target (fuori kita tab-interne) importano `NavShell` con `persona` prop; eliminare le 5 nav hand-rolled esistenti (`(marketing)`, `(blog)`, `(workspace)`, `portal`, `(visa-oracle)`).

---

## 3. Layer 1 — Funnel Hub

### 3.1 Cross-funnel session

- Cookie `bz_session` **pre-auth lead tracker**, distinto da `nz_access_token` (httpOnly SSO auth, già in prod): UUID v4, 30gg, `SameSite=Lax`, `domain=.balizero.com`, `httpOnly=false` (deve essere leggibile client-side per propagare cross-funnel). Non contiene PII — solo ID anonimo che indicizza `funnel_sessions.step_state`/`lead_profile` lato server.
- Table `funnel_sessions` (generalizzazione di `visa_oracle_sessions` già in prod — nuova migration Alembic `101_funnel_sessions`)
  - `session_id uuid PK`, `funnel ENUM('visa','kbli','tax','property','home')`, `step_state jsonb`, `lead_profile jsonb`, `started_at`, `last_touched_at`, `converted_to_client_id uuid NULL`
- Bridge: quando user completa login SSO, `converted_to_client_id` popolato → attribution analytics.

### 3.2 FunnelFrame pattern

Applicato a visa / kbli / tax / property:

- Header minimal: `BZLogo` + "Bali Zero" + persona lang switcher (9 lingue già supportate)
- Step bar (`Step X / Y` + progress bar)
- Main (tool content, sostituibile per funnel)
- Sticky bottom `CTAHandoff` — 3 livelli: `Scarica report PDF` (lead magnet gratis) → `Chatta con Zantara` (self-service) → `Parla su WhatsApp` (vero conversion CTA, deeplink canonico `+628213107363` con context pre-riempito)
- Footer `TrustBand` (5000+ clienti, review, tempo risposta)

### 3.3 I 4 funnel

**Visa Oracle (`visa.balizero.com`):**

- Port su FunnelFrame mantenendo 181 SSG pages
- Session state salvato in `funnel_sessions` (già fa `visa_oracle_sessions` — migration rinomina)
- Timeline planner inline (60+60+60 per C-series, regola memoria `reference_visa_c_duration_rules.md`)
- Document checklist pre-filled scaricabile PDF
- Handoff WA in ≤3 click (oggi serve scroll)

**KBLI Navigator (`balizero.com/kbli`):**

- Port su FunnelFrame + rimuovere `kbli-theme.css` (merge con tokens)
- Fix gap visivo layout tra descrizione e licensing (bug pre-existing, memoria #480)
- Nuovo: compare 2 codici side-by-side
- Nuovo: "Le 10 domande più frequenti al tax team per questo codice" (query cached da CRM `crm_practices.notes` filtrato per kbli_code)
- CTA pricing PT setup già fixato 2026-04-13

**Tax Compliance Calendar (`tax.balizero.com`) — NUOVO:**

- DNS + Vercel domain aggiunto (pattern uguale a `visa.balizero.com`, memoria #97)
- Route group `(tax-calendar)/tax-calendar/` dentro mouth, middleware rewrite pattern visa-oracle
- Feature: segmented pill tabs (PPh/PPN/LKPM/PB1), conic ring countdown, filter per reggenza Bali, iCal export (`utils/ical.ts`), WA opt-in reminder, upsell "delega SPT a Bali Zero" (lead → CRM)
- Design base: HTML offline esistente (`docs/design-palettes/funnels/03-tax-calendar.html`, memoria #455) riportato in React con tokens
- PB1 varia per reggenza (research memoria #455), deadline mensile 15 (era 10, JCSS 2025), SPT individuale 2026 estesa a 30 aprile

**Property Eligibility (`balizero.com/property`) — NUOVO:**

- Wrapper pubblico su `/api/prime/v2/analyze` (rate-limit 10/min già in prod, memoria #81/119)
- Input: indirizzo/coordinate Bali
- Output: (a) struttura legale eligible — Hak Pakai / HGB via PMA / Rental 30y (F3 backend, memoria #262), (b) tassazione PBB 0.1-0.3% + BPHTB 5% (F2), (c) risk score (F4: tsunami 35% + flood 25% + saturation 20% + erosion 20%)
- CTA "Vedi zona su Prime 3D" → link firmato token temp per utenti non auth (pattern `/prime/proposal/[token]`)
- Upsell "Bali Zero ti segue l'acquisto" → WA handoff

### 3.4 Homepage balizero.com

- `apps/mouth/src/app/v2/_components/FunnelFeature.tsx`: cambiare `href={`/services/${funnel === "kbli" ? "company" : funnel}`}` → link reali:
  - visa → `https://visa.balizero.com/`
  - kbli → `/kbli`
  - tax → `https://tax.balizero.com/`
  - property → `/property`
- session_id propagato via query param prima del cookie.

---

## 4. Layer 2 — Client App

### 4.1 Home `/portal` — 3 hero cards SEMPRE

```
┌──────────────────────┬──────────────────────┬──────────────────────┐
│  Card A              │  Card B              │  Card C              │
│  Azioni aperte       │  Deadline 30 giorni  │  Messaggi team       │
│  (pending_from_client)│  (visa_exp, lkpm,   │  (unread count from  │
│  [3 items]           │   tax)               │   conversations)     │
│  → click CTA         │  → iCal export       │  → open thread       │
└──────────────────────┴──────────────────────┴──────────────────────┘
```

Zero-state: "Tutto a posto ✓ — prossimo rinnovo `{date}`" (mai pagina vuota).

### 4.2 MatterCard

Sostituisce le tab feature-first. Ogni cliente ha N matter (es. "KITAS Marco", "PT Setup Bali Villa Srl", "SPT Tahunan 2025"). Ogni MatterCard espande:

- ProgressRing %
- Lista docs (required/received/validated)
- Chat thread inline (WA bridge bidirezionale)
- Invoice status (unpaid/partial/paid)
- Prossimo step
- Deadline badge

### 4.3 WA push

- Tabella `notification_prefs` (user_id, email_enabled, wa_enabled, both) — migration `102_notification_prefs`
- Cron esistente `drive_token_watchdog.py` pattern → nuovo `portal_deadline_watchdog.py` (ogni 6h): scansiona `lkpm_reports.due_date`, `clients.visa_expiry_date`, `matters.next_deadline`; se pref `wa_enabled` → template WA via adapter Fly.io
- Endpoint `/api/portal/notifications/prefs` GET+PUT

### 4.4 Family profile

Regola confermata memoria `feedback_minori_drive.md`: minori nella sezione family del genitore, maggiorenni profilo proprio.

- Nuova route `/portal/family` per user con `family_members[]`
- CRM: join query su `crm_clients.family_parent_id`

### 4.5 Prime proposal theme riallineato

- `/prime/proposal/[token]/page.tsx` — wrap in `ThemeProvider persona="portal"` + aggiungere banner "richiedi call WA" (CTAHandoff)

### 4.6 zantara.balizero.com

- Chat pulita (no distrazioni) + matter-context pane collassabile dx (riutilizza `ContextPanel`)

### 4.7 Bundle audit portal

Memoria `project_next_session_bundle_audit.md`: ERR_INSUFFICIENT_RESOURCES da ~35 chunk paralleli.

- Abilitare `ANALYZE=true` build → route `/portal/(authenticated)/clients`
- Dynamic import per i panel heavy (Prime, charts, richtext editor)
- Target: < 300KB initial bundle portal

---

## 5. Layer 3 — Team Operations

### 5.1 Nuova default route `/kita/inbox`

- Timeline omnichannel unificata: WA + TG + IG + email + web chat in un unico feed
- Filtri: canale, team (RBAC), stato (unread/pending/resolved), cliente
- Sorting: last_message desc
- Redirect `/kita/` → `/kita/inbox` (era `/kita/dashboard`)

### 5.2 CommandPalette Cmd+K

Azioni iniziali:

- assegna pratica a tax/visa/business/property team
- crea pratica KITAS / PT Setup / SPT
- invia checklist docs a cliente (template per tipo pratica)
- esporta LKPM Q1 per PT X (già scripting in prod)
- apri Prime zona {name}
- cerca cliente / pratica / messaggio (fuzzy)

### 5.3 ContextPanel dx

Al click su messaggio/cliente, panel dx con tab lazy-load:

- Info (dati base cliente)
- Matter (lista pratiche)
- Visa (status + expiry)
- Tax (overview da `lkpm_receipts`, `crm_clients.tax_summary`)
- Docs (drive index cliente)
- Prime (zona + KBLI compliance)

### 5.4 Zantara inline suggestions

Ogni messaggio inbound ha tile "Zantara suggerisce:" con 3 reply accept/edit/reject. Endpoint `/api/zantara/suggest` già esiste (backend `backend/app/routers/zantara.py`). Frontend: hook + UI tile.

### 5.5 Prime toggle in `/kita/clients`

Tre viste: `List | Map | Pipeline`. Map = `PrimeNexusLayout` preset `mode=crm`. Pipeline = Kanban by status.

### 5.6 Cleanup satellite apps

Verificati irraggiungibili in prod (middleware intercetta `mail/calendar/drive/knowledge.balizero.com` → redirect a kita). Zero uso di `@balizero/core`. Decisione: **rimuovere** `apps/{mail,calendar,drive,knowledge}/` in S5 dopo verifica `gemini explore` che non ci siano import esterni.

---

## 6. Cross-cutting — analytics funnel-view

- GA4 ha già 11 eventi su 4 tool (memoria #473)
- Backend dual-track (`backend/services/analytics/`) registra eventi
- **Manca** la **funnel view**: lead (bz_session) → funnel steps → WA handoff → client created → first revenue
- Nuova route `/kita/analytics/funnel` con visualizzazione:
  - Top: conversion funnel classico (homepage → funnel → quiz complete → WA click → client created)
  - Bottom: per funnel type (visa/kbli/tax/property), split per lingua, split per fonte
- Tabella `funnel_attributions` (session_id, client_id, touchpoints jsonb, first_touch, converted_at)

---

## 7. QA, sicurezza, constraints

- Browser QA obbligatoria post-deploy con `mcp__claude-in-chrome__*` (CLAUDE.md §10 + `.claude/rules/frontend-nextjs.md`). **Mai** `mcp__playwright__*`.
- Screenshot per ogni persona-theme (editorial, operative-light, operative-dark) su ogni deploy.
- Lighthouse budget: 95+ performance L1 (SEO), 85+ L2/L3.
- **Off-limits** (rules): `zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`.
- **Federation** (CLAUDE.md §2): refactor L3 (17 route workspace) → `gemini explore` prima di toccare; pre-deploy Fly → `gemini redteam`; fix `dependencies.py` → `codex sandbox`.
- **Review checkpoints**: dopo S1, S2, S3 — `/ai-dispatch.sh claude-redteam` o `codex sandbox` sulla spec implementata.
- Rimuovere `className="dark"` hardcoded in `src/app/layout.tsx` (memoria `project_redesign_next.md`) — ora gestito da `ThemeProvider` con persona.

---

## 8. Rollout plan

| Sprint                 | Target                                                                         | Durata | Output principale                                                                                                                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **S1 — foundation**    | `packages/core` extension + migrations 101/102 + session-bridge                | 3gg    | 8 nuovi componenti, 2 utility, 2 migration                                                                                                                                                        |
| **S2 — L1 Funnel Hub** | visa port + kbli port + **tax.** nuovo + property nuovo + homepage link fix    | 5gg    | 4 funnel su FunnelFrame, cross-session, 2 DNS nuovi                                                                                                                                               |
| **S3 — L2 Client App** | my. matter-first (3 hero cards + MatterCard) + prime proposal theme + zantara. | 4gg    | Hero cards, MatterCard, WA push, family route, bundle < 300KB                                                                                                                                     |
| **S4 — L3 Team Ops**   | kita inbox-first + Cmd+K + ContextPanel + Prime toggle + cleanup satellite     | 5gg    | /kita/inbox default, Prime CRM view, delete 4 app orfane. **Nota:** S4 tocca 17 route workspace — possibile split in S4a (inbox+palette+panel) + S4b (Prime toggle+cleanup) durante writing-plans |
| **S5 — polish**        | analytics funnel-view + remove `dark` hardcoded + Lighthouse audit             | 2gg    | `/kita/analytics/funnel` live, tokens puliti                                                                                                                                                      |

Totale ~19gg lavoro; budget +30% = ~25gg elapsed con review checkpoint.

---

## 9. Riferimenti

- Brief sessione: user prompt 2026-04-17
- Memoria MOS usate: #439 (roadmap Zero), #455 (Tax Calendar HTML), #459 (3D vision Waypoint, deferred), #461 (world models survey), #473 (GA4 11 eventi), #480 (bug visivi funnel), #484 (checkpoint 27+ bug fix), #1036/#1042/#1051 (portal UX parity fasi 3-5), #1424/#1469 (Visa Oracle enrichment), #96 (satellite apps WAVE 2), #97 (visa. DNS), #178/#183/#251 (Prime Nexus Ultra), #262 (Prime F3 eligibility)
- Memoria file: `reference_visa_c_duration_rules.md`, `feedback_minori_drive.md`, `project_redesign_next.md`, `project_next_session_bundle_audit.md`, `reference_nuzantara_repo_paths.md`
- Repo paths: Pro `~/Desktop/nuzantara/` (verificato HEAD `ea33987d9`)
- SOTA research (2026-04-17):
  - SmartVault — 4 Client Portal Best Practices
  - Moxo — file sharing portal UX patterns
  - LegistAI — immigration client portal tracking
  - VisaTrax · Docketwise — case tracking
  - Fungies / Financial Cents — SaaS tax compliance 2026
  - Tars / OpenSphere / Visas.AI — immigration chatbot eligibility
  - Visual Craft / Prophetic — proptech zoning GIS

---

## 10. Out of scope (YAGNI)

- Visione 3D Waypoint (memoria #459) — PoC rimandato a post-rollout; prima il 2D SOTA.
- Riportare in vita `apps/{mail,calendar,drive,knowledge}/` come domini indipendenti — il redirect a kita è la scelta giusta, delete.
- Education platform, real estate listing, banking advisory — esplicitamente esclusi dalla roadmap Zero (memoria #439).
- `tax.balizero.com` in lingue oltre IT/EN prima del launch — i18n resta su visa/kbli già fatto, tax e property partono bilingue.
