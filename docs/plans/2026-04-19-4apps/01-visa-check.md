# Build Plan 01 — Visa Check (2 rami: Clock + Match)

**Prerequisito:** `00-shared-infrastructure.md`

## Idea

Un'unica app "Visa Check" con **2 rami**, per coprire entrambi i segmenti del traffico visa:

- **Clock** — chi è già in Indonesia con visto attivo
- **Match** — chi sta pianificando di venire

Prima domanda in homepage: **"Are you already in Indonesia?"** → 2 card, 2 flow diversi, stesso pattern output (URL condivisibile + email opt-in + WhatsApp CTA).

## User flow

```
[Homepage section visa]
  └─▶ <VisaCheckHero />
      └─▶ Domanda: "Are you already in Indonesia?"
          ├─▶ YES → /visa/clock (form: visa_type + entry_date)
          │         └─▶ /visa/clock/[hash] (countdown + timeline + reminder D-60/30/14/7/1)
          └─▶ NO / PLANNING → /visa/match (wizard 4 step)
                  └─▶ /visa/match/[hash] (visto consigliato + cost + pre-arrival steps)
```

Entrambi i rami terminano con:

- URL condivisibile
- Email opt-in
- WhatsApp CTA con context precompilato

## Ramo A — Visa Clock

**Input:** tipo visto (8 options: B211A / C1 / C2 / C7 / C7A / C7B / E23 / E28A / E33G / E33F) + data ingresso.

**Output:** pagina `/visa/clock/[hash]` con:

- Countdown live al giorno di scadenza
- Timeline 5 checkpoint (D-60 inizia pratiche / D-30 docs / D-14 kantor imigrasi / D-7 pickup / D-0 scade)
- Email opt-in per reminder ai 5 checkpoint
- Share button
- WhatsApp CTA: _"Your E33G expires in 43 days. Want our team to file the renewal? IDR [PricingTool fee] fixed, 14 days. Start WhatsApp →"_

**Email reminders:** cron daily, trigger 60/30/14/7/1 giorni prima scadenza. Sender `zantara@balizero.com`. Template X_BRAND_VOICE (no "we hope", grounded tone).

## Ramo B — Visa Match

**Wizard 4 step** (progressive disclosure, non form unico):

1. **Nationality** — ISO 3166-1 alpha-3 dropdown, autocomplete top paesi
2. **Purpose** — 7 cards:
   - Work remotely for a foreign employer
   - Invest in / open a PT PMA
   - Be hired by an Indonesian company
   - Join family (dependent)
   - Long tourism / explore
   - Retirement (55+)
   - Study at an Indonesian university
3. **Duration** — slider 1-60 mesi
4. **Budget band** — 3 tier (under IDR 50M / 50M-500M / 500M+)

**Output:** pagina `/visa/match/[hash]` con:

- **Hero**: "For you, E33G Investor KITAS fits"
- **Reason**: 2-3 frasi X_BRAND_VOICE, no jargon
- **Cost**: da `PricingTool.get_visa_price(visa_type)` — breakdown fee Bali Zero + gov fees, NO hardcoded
- **Timeline**: processing days + quando iniziare
- **Pre-arrival steps**: 4-6 action items con checkbox (state locale, user spunta mentre prepara)
- **Alternatives**: se caso borderline, 1-2 visa secondari con one-liner differenza
- **WhatsApp CTA**: _"E33G fits your case. Start the application with us? Start WhatsApp →"_ (context: nationality + purpose + visa_type raccomandato)

**Email pre-arrival nudge:** se user fornisce optional `expected_arrival_date`, email singola 7gg prima: recap documenti + CTA "file with us on arrival".

**Decision tree** (visible, no ML):

- duration ≤ 2 mesi + LONG_TOURISM → C1
- duration ≤ 6 mesi + LONG_TOURISM → B211A
- WORK_REMOTE + budget ≥ IDR 50M → E33G (Digital Nomad)
- INVESTOR + budget ≥ IDR 500M → E28A (Investor 2yr)
- INVESTOR + budget IDR 50M-500M → E33G
- WORK_EMPLOYEE → E23 (richiede RPTKA dal datore di lavoro)
- FAMILY → dependent visa (richiede sponsor KITAS)
- RETIREMENT + nationality eligible → E33F
- STUDENT → E30A
- **Catch-all "Other / not sure"** → NON wizard, CTA diretto _"Your case has specifics. Free 15-min review with our visa team. Start WhatsApp →"_

Se borderline (es. INVESTOR + budget under IDR 50M), result mostra alternatives + disclaimer: _"Based on patterns. Your case may have nuances. We verify before filing."_

## API

```python
POST /api/visa/clock
  Body: { visa_type, entry_date, in_country_now=True, client_fp }
  Response: { hash, expiry_date, timeline, result_url }

POST /api/visa/match
  Body: { nationality, purpose, duration_months, budget_band, expected_arrival_date?, client_fp }
  Response: { hash, recommended_visa, reason, estimated_cost_idr, processing_days, pre_arrival_steps, alternatives, result_url }

GET /api/visa/clock/{hash}    # view result
GET /api/visa/match/{hash}    # view result

POST /api/visa/check/start    # analytics: which branch selected
  Body: { in_country_now }
  Response: { branch: "clock" | "match" }
```

## Migration 119 — `visa_checks`

Tabella unica per i 2 rami (colonne nullable per ramo non applicabile):

```sql
CREATE TABLE visa_checks (
  hash          VARCHAR(20) PRIMARY KEY,
  branch        VARCHAR(8)  NOT NULL,  -- 'clock' | 'match'
  client_fp     VARCHAR(32),
  view_count    INT NOT NULL DEFAULT 0,
  share_count   INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- Clock (nullable se branch='match')
  visa_type     VARCHAR(16),
  entry_date    DATE,
  expiry_date   DATE,
  extensions_possible INT,
  extension_days INT,
  -- Match (nullable se branch='clock')
  nationality   VARCHAR(3),
  purpose       VARCHAR(32),
  duration_months INT,
  budget_band   VARCHAR(16),
  recommended_visa VARCHAR(16),
  recommendation_reason TEXT,
  pre_arrival_steps JSONB,
  expected_arrival_date DATE
);

CREATE INDEX idx_visa_checks_branch_created ON visa_checks(branch, created_at DESC);
CREATE INDEX idx_visa_checks_expiry ON visa_checks(expiry_date) WHERE branch='clock';
```

## Acceptance criteria

### Functional

- [ ] Branch selector: click YES → `/visa/clock`, click NO → `/visa/match`
- [ ] Clock: form E33G + entry_date 2025-10-01 → timeline 5 checkpoint
- [ ] Clock: form con in_country_now=false → redirect a Match (nessuno stuck)
- [ ] Match: wizard 4 step con progress bar + Back button
- [ ] Match: 20 permutazioni testate → recommendation corretta
- [ ] Match: cost SEMPRE da PricingTool (test: `estimated_cost_idr == PricingTool.get_visa_price(visa_type)`)
- [ ] Match: purpose="Other" → CTA diretto (no wizard rumpante)
- [ ] Match: borderline case → alternatives mostrato
- [ ] Entrambi rami: URL shareabile pubblico
- [ ] Entrambi rami: email opt-in funzionante + unsubscribe one-click
- [ ] Entrambi rami: WhatsApp CTA precompila context (vedi 00 deeplink schema)

### Performance

- [ ] Branch selector Lighthouse mobile ≥ 92
- [ ] Clock form Lighthouse mobile ≥ 90
- [ ] Match wizard Lighthouse mobile ≥ 90
- [ ] `POST /api/visa/clock` p95 < 150ms
- [ ] `POST /api/visa/match` p95 < 300ms

### Analytics

- [ ] `app_viewed` su entry page
- [ ] `app_branch_selected` con `{ branch }` payload
- [ ] `app_wizard_step_completed` per ogni step Match
- [ ] `app_wizard_abandoned` quando user esce mid-wizard
- [ ] `app_form_submitted`, `app_result_viewed`, `app_cta_clicked`, `app_whatsapp_handoff`

### Integration

- [ ] E2E Clock: entry → yes → form → result → WA
- [ ] E2E Match: entry → no → wizard 4 step → result → WA
- [ ] E2E abandon wizard step 2 → analytics event
- [ ] PricingTool integration: cost match test su 10 visa types

## Killer risk + mitigation

**Risk 1:** Match decision tree non copre edge case (journalist, religious, etc).

- Mitigation: catch-all "Other / not sure" → CTA diretto WhatsApp, gap diventa lead.

**Risk 2:** Wizard abandon rate alto.

- Mitigation: progress bar visibile, stato locale persistente 1h (se user chiude tab), step 1 < 5s.
- Alert Telegram: se `app_wizard_abandoned` step N > 45% → UX issue su quello step.

**Risk 3:** User "in country" sbaglia e clicca Match.

- Mitigation: step 1 Match wizard chiede conferma: "Just to confirm — you are not in Indonesia, right?" con Back button.

**Risk 4:** Estimated cost obsoleto se PricingTool non aggiornato.

- Mitigation: disclaimer sotto cost "Prices updated {{last_pricing_update}}. Gov fees may vary."

**Risk 5:** Recommendation Match degenerato (tutti E33G).

- Mitigation: monitoring distribuzione `recommended_visa` post-launch. Se >80% single visa → tree bias, quarterly review Asya.

## Post-ship telemetry (30gg)

- Branch split Clock vs Match (target ~30/70)
- Match recommendation distribution (no single visa >80%)
- Wizard drop-off per step
- Email open rate Clock (per checkpoint)
- Email open rate Match (pre-arrival)
- CR1 per branch (Clock target 2.5%, Match target 5%)
- Matched lead rate (target ≥ 80%)

## V2 roadmap

- Clock→Match cross-flow: Clock user near-expiry che vuole switch visa → redirect a Match
- Match multi-persona: partner + children con dependent visa
- Match "upload passport" fallback per nationality autodetect
- Shared "My Visas" portal (richiede auth via `my.balizero.com`)
