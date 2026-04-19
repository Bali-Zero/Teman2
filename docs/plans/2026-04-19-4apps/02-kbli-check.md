# Build Plan 02 — KBLI Check (2 rami: Decoder + Builder)

**Prerequisito:** `00-shared-infrastructure.md`

## Idea

Come Visa Check, 2 rami per coprire 2 segmenti:

- **Decoder** — chi ha già una PT PMA e deve verificare/migrare i suoi codici KBLI (deadline 18 giugno 2026)
- **Builder** — chi sta aprendo una PT PMA nuova e vuole sapere quali codici prendere + quanto capitale serve

Prima domanda in homepage: **"Hai già una PT PMA?"** → 2 card, 2 flow diversi.

Il segmento "apro nuova PMA" è più ricco del "audit codici esistenti": setup PMA medio IDR 18,5M/cliente vs amendment IDR 4,5M. Ignorarlo è lasciare soldi per terra.

## User flow

```
[Homepage section kbli]
  └─▶ <KbliCheckHero />
      └─▶ Domanda: "Hai già una PT PMA?"
          ├─▶ YES → /kbli/decode (input: codici o NIB)
          │         └─▶ /kbli/decode/[hash] (scorecard per codice + PDF + regulation subscribe)
          └─▶ NO, STO APRENDO → /kbli/builder (wizard 4 step)
                  └─▶ /kbli/builder/[hash] (2-3 KBLI suggeriti + capitale + timeline + cost setup)
```

## Ramo A — KBLI Decoder

**Input:** textarea con codici (es. `56101, 47911, 70209`) OR campo NIB (fetch via OSS adapter con cache 7gg, fallback graceful a manual).

**Output:** pagina `/kbli/decode/[hash]` con:

- **Summary**: issues_count, risk breakdown, deadline KBLI 2025 countdown
- **Per-code table**: code | title | status (✓/⚠/✗) | risk_level | action needed | pasal reference
- **Recommendations**: 3-5 azioni ordinate per priorità
- **PDF download** (`@react-pdf/renderer`): report stampabile A4, valore equivalente audit consulente 500 EUR
- **Email opt-in**: "Avvisami quando esce una regulation che tocca i miei codici" → cross-reference con `war-room` publisher
- **WhatsApp CTA** (se issues ≥ 1): _"2 codici da correggere. Akta amendment + OSS refile IDR [PricingTool]. Start WhatsApp →"_
- **WhatsApp CTA alternativo** (se zero issues): _"Your codes look clean. Want a quarterly audit? Free check via email."_

**Engine compatibility:**

1. Lookup in `kbli_codes_2025` table (base dati `apps/kbli-navigator`)
2. Code 2020-only → status=AMEND + suggest 2025 equivalent via KG
3. Risk level 4 + PMA restricted → status=HIGH_RISK
4. Pair conflict (KG relationships): es. 56101 + 47911 → warning
5. Semantic similarity input business description vs code `judul` (opzionale, V2)

**Disclaimer obbligatorio** nel header result: _"This triage detected X issues. Our notaris team verifies every recommendation before filing. Free 15-min review includes verification."_ L'escalation è la conversione.

## Ramo B — KBLI Builder

**Wizard 4 step:**

1. **Business type** — text libero "Cosa fa la tua azienda?" (es. "Restaurant with delivery", "Consulting studio strategia", "Villa rental short-term"). Embedding similarity su `kbli_codes_2025.judul` per suggerire match candidate.
2. **Investment band** — 3 tier: IDR 10B (minimum PMA) / 10-50B / 50B+
3. **Ownership structure** — 100% foreign / joint venture con partner locale / unclear
4. **Bali area** — Canggu / Ubud / Seminyak / Uluwatu / Denpasar / Other (influenza risk zoning + PMA eligibility per alcune attività)

**Output:** pagina `/kbli/builder/[hash]` con:

- **Hero**: "Per il tuo business (Restaurant + delivery) ti servono 2 codici KBLI: 56101 + 56303"
- **Why these codes**: 2-3 frasi X_BRAND_VOICE che spiegano il match
- **PMA eligibility**: foreign ownership % permesso per questi codici
- **Minimum capital**: IDR stated investment + paid-up capital requirements
- **Setup cost estimate**: da `PricingTool.get_service_price("pt_pma_setup")` — breakdown: notaris fee + OSS registration + gov fees + Bali Zero fee
- **Timeline**: 6-8 settimane tipiche con gantt chart semplificato
- **Pre-setup checklist**: 5-7 items (passport validity, bank statement, sponsor docs, address, ecc.)
- **WhatsApp CTA**: _"PT PMA setup completo per il tuo business. IDR [PricingTool fee], 6-8 settimane. Start WhatsApp →"_ (context: business_type + KBLI codes raccomandati + investment_band)

**Catch-all**: se business*type non matcha nessun codice con confidence >0.6 (similarity threshold) → CTA diretto *"Your business is specific. Free 15-min call per capire insieme quali codici servono. Start WhatsApp →"\_

## API

```python
POST /api/kbli/decode
  Body: { codes_input | nib_input, business_description?, client_fp }
  Response: { hash, results[], issues_count, high_risk_count, migration_2025_needed, result_url }

POST /api/kbli/builder
  Body: { business_type, investment_band, ownership_structure, bali_area, client_fp }
  Response: { hash, recommended_codes[], pma_eligibility, min_capital_idr, setup_cost_idr, timeline_weeks, pre_setup_checklist[], result_url }

GET /api/kbli/decode/{hash}
GET /api/kbli/builder/{hash}
GET /api/kbli/decode/{hash}/pdf    # PDF report download

POST /api/kbli/check/start         # analytics: which branch
  Body: { has_pma }
  Response: { branch: "decoder" | "builder" }
```

## Migration 120 — `kbli_checks`

Tabella unica per 2 rami:

```sql
CREATE TABLE kbli_checks (
  hash          VARCHAR(20) PRIMARY KEY,
  branch        VARCHAR(8)  NOT NULL,  -- 'decoder' | 'builder'
  client_fp     VARCHAR(32),
  view_count    INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at    TIMESTAMPTZ NOT NULL,
  -- Decoder
  codes_input   TEXT,
  codes_parsed  TEXT[],
  nib_input     VARCHAR(32),
  results       JSONB,
  issues_count  INT DEFAULT 0,
  high_risk_count INT DEFAULT 0,
  migration_2025_needed BOOLEAN,
  pdf_downloads INT DEFAULT 0,
  -- Builder
  business_type TEXT,
  investment_band VARCHAR(16),
  ownership_structure VARCHAR(16),
  bali_area     VARCHAR(16),
  recommended_codes TEXT[],
  pma_eligibility TEXT,
  min_capital_idr BIGINT,
  setup_cost_idr BIGINT,
  timeline_weeks INT,
  pre_setup_checklist JSONB
);

CREATE INDEX idx_kbli_checks_branch ON kbli_checks(branch, created_at DESC);
CREATE INDEX idx_kbli_checks_issues ON kbli_checks(issues_count) WHERE branch='decoder' AND issues_count > 0;
```

## Acceptance criteria

### Functional

- [ ] Branch selector `/kbli/check`: YES→decoder, NO→builder
- [ ] **Decoder**: submit "56101, 47911, 70209" → 3 codes analizzati con status
- [ ] **Decoder**: obsolete 2020 codes → AMEND + 2025 suggestions valide (no hallucination)
- [ ] **Decoder**: invalid code "99999" → INVALID status, no crash
- [ ] **Decoder**: NIB lookup (o fallback graceful)
- [ ] **Decoder**: PDF download funziona cross-browser
- [ ] **Decoder**: email subscribe + unsubscribe link funziona
- [ ] **Decoder**: 50 common code combinations → 100% status corretto (test table-driven)
- [ ] **Decoder**: WA CTA context include codes_checked + issues_count
- [ ] **Builder**: wizard 4 step con progress + back
- [ ] **Builder**: 10 business types reali → recommendation appropriata (validated by Asya)
- [ ] **Builder**: setup_cost SEMPRE da PricingTool (no hardcoded)
- [ ] **Builder**: catch-all "business non matcha" → CTA diretto
- [ ] **Builder**: WA CTA context include business_type + KBLI codes + investment_band

### Performance

- [ ] Branch selector Lighthouse mobile ≥ 92
- [ ] Decoder result page Lighthouse ≥ 85
- [ ] Builder wizard Lighthouse ≥ 90
- [ ] `POST /api/kbli/decode` p95 < 500ms (10 codes)
- [ ] `POST /api/kbli/builder` p95 < 600ms (embedding similarity)
- [ ] PDF generation p95 < 2s

### Engine accuracy (critico)

- [ ] Decoder: 50 combinations → 100% corrette
- [ ] Decoder: false positive rate < 5% (validated by notaris sample 20 casi)
- [ ] Builder: 10 business_type reali (curati da Asya) → recommendation match atteso in 9/10 cases
- [ ] AMEND suggestions puntano a codes 2025 effettivamente esistenti
- [ ] Regulation refs citano pasal reale + URL valido

### Analytics

- [ ] `app_viewed`, `app_branch_selected`, `app_form_submitted`, `app_result_viewed`, `app_cta_clicked`, `app_whatsapp_handoff`
- [ ] Decoder: `app_pdf_downloaded`, `app_regulation_subscribe`
- [ ] Builder: `app_wizard_step_completed`, `app_wizard_abandoned`

### Integration

- [ ] E2E Decoder: entry → yes → form → result → PDF → WA
- [ ] E2E Builder: entry → no → wizard → result → WA
- [ ] War-room integration: Intel Article con KBLI codes → email fires per subscribed users
- [ ] Test 48 casi reali Decoder da CRM history (sample anonimizzato)

## Killer risk + mitigation

**Risk 1:** Decoder dà risposta sbagliata → false positive panic o false negative liability.

- Mitigation: disclaimer prominent "Triage, not final answer — we verify before filing". Launch con 50 combinations comuni (coverage 80%), edge case → status=UNKNOWN + "Chat with us to verify manually". Quarterly red team Asya+Krisna su sample 50 report.

**Risk 2:** Builder recommendation troppo generica (ogni business riceve stesso codice popolare tipo 70209 consulting).

- Mitigation: embedding similarity threshold 0.6. Sotto threshold → catch-all CTA manuale. Monitoring distribuzione `recommended_codes` post-launch: se top 3 codici sono >60% dei recommendation → tree bias, riviewa.

**Risk 3:** Deadline 18 giugno 2026 passa, Decoder perde urgency.

- Mitigation: post-deadline, Decoder swap copy a "KBLI Health Check" (ongoing audit tool). Countdown swap a "Hours since KBLI 2025 enforced: X".

**Risk 4:** PDF report condiviso fuori Bali Zero (viene usato da commercialista competitor).

- Mitigation: PDF include footer "Bali Zero audit report — generated at [URL]". Non è furto se aumenta awareness, ma traccia via view_count su hash pubblico.

## Dependencies

- `apps/kbli-navigator` base dati (1,563 codes) deployed
- KG graph include KBLI nodes (verify: `SELECT COUNT(*) FROM kg_nodes WHERE entity_type='kbli_code'`)
- 50 common code combinations curate da Asya (seed test data)
- PricingTool: `get_service_price("pt_pma_setup")`, `get_service_price("akta_amendment")`, `get_service_price("oss_refile")`

## Post-ship telemetry (30gg)

- Branch split Decoder vs Builder (atteso: ~65/35 verso Decoder inizialmente, più Builder quando SEO PMA)
- Decoder: distribuzione issues_count (target: 30% zero, 50% 1-2, 20% 3+)
- Decoder: PDF download rate (target ≥ 25%)
- Builder: wizard drop-off per step
- Builder: recommendation diversity (no code >50% dei case)
- False positive monitoring Decoder: % `lead_intents` che poi diventano pratiche reali vs flag engine
- CR1 per branch (Decoder target 5%, Builder target 6% — intent più forte)

## V2 roadmap

- Decoder: multi-PT PMA portfolio (user gestisce più aziende)
- Builder: "save my plan" → integrate con `my.balizero.com` dopo signup
- Builder: integrate con NotebookLM per ricerca approfondita su regolamento settore specifico
- Cross-flow: Builder completes → dopo 3 mesi offre Decoder check sui codici effettivamente registrati
