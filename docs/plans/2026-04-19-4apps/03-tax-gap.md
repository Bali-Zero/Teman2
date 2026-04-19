# Build Plan 03 — Tax Gap

**Prerequisito:** `00-shared-infrastructure.md`

## Idea

Tool che accetta upload SPT tahunan (o input manuale) → produce report "Your numbers vs your peers" con scorecard 5-dimension + 3-5 red flag + recommendations. Il CTA non vende una "paid review" ma porta a **free 30-min call** con il tax team. Il vero prodotto è l'**outsourcing tax ongoing** (LTV 12-24 mesi, IDR 2,5M-10M/mese), non un one-shot report.

Il moat: benchmark aggregato da 5,000+ clienti Bali Zero (nessun competitor ha questo dataset). Unico (no rami) perché il segmento è ben definito: chi ha una PT PMA attiva e ha presentato SPT.

## User flow

```
[Homepage section tax]
  └─▶ <TaxGapHero />
      └─▶ "We audit your last SPT in 48 hours. Free."
          ├─▶ Option A: Drag-drop PDF SPT/bukti potong
          │   └─▶ [POST /api/tax/gap/upload] → OCR extract
          │       └─▶ Confirmation page: user verifica numeri estratti
          │           └─▶ Analisi + redirect /tax/gap/[hash]
          └─▶ Option B: Manual form (5 campi)
              └─▶ [POST /api/tax/gap/analyze]
                  └─▶ /tax/gap/[hash] (scorecard 5-dim + red flags + free call CTA)
```

## Ramo upload

**File accettati:** PDF SPT tahunan (1771), bukti potong PPh 21, CoreTax export CSV. Max 10MB.

**OCR pipeline:** tesseract con Indonesian support (già installato backend). Pattern match su keyword SPT 1771 ("Peredaran Usaha" → revenue, "PPh Terutang" → PPh, ecc.).

**Privacy protocol (critico):**

1. Upload ricevuto → OCR in-memory
2. Estrazione numeri → save in DB
3. **DELETE pdf_bytes immediatamente** da memoria/tmp (privacy)
4. Confirmation page: user verifica numeri estratti, può correggerli prima di submit
5. Mai persistere il file originale su disco

**Privacy frame UI** — prominent card sopra form, NON nel footer:

```
How we handle your SPT:
1. You upload (or type)
2. We extract numbers → compare to peer median
3. Your upload is deleted within 2 minutes
4. Numbers stay anonymized — aggregable into future benchmarks only if you opt in

We never store the PDF. We never show your numbers to another client.
Read our privacy rule: balizero.com/privacy/tax-gap
```

## Ramo manual

Form 5 campi (fallback se user non si fida upload):

- Revenue annuale IDR
- PPh pagato IDR
- PPN pagato IDR
- BPJS pagato IDR
- LKPM filed? (toggle)
- Sector KBLI (autocomplete, optional)

Submit → analisi diretta senza OCR intermedio.

## Output: result page `/tax/gap/[hash]`

**Scorecard 5 dimensioni** (ognuna rossa/gialla/verde):

1. **Revenue category** — informational, no status (solo posiziona nella fascia)
2. **PPh efficiency** — ratio PPh/revenue vs p25-p75 peer
   - < p25: green "tax-efficient"
   - p25-p75: yellow "in range"
   - > p75: red "higher than peers — review"
3. **PPN health** — stessa logica su ratio PPN/revenue
4. **BPJS compliance** — absolute check (paid > 0, amount reasonable vs n. dipendenti se noto)
5. **LKPM filing** — binary: filed yes/no

**Red flags section** (se presente): bulleted list con descrizione + impact.

**Recommendations**: 3-5 azioni prioritizzate.

**Benchmark label esplicito** (no-bias):
_"Compared to 5,247 foreign-owned PT PMA clients of Bali Zero (not nationwide Indonesia average). Quarterly refresh."_

## CTA: free 30-min call

**Non** prezzo inventato, **non** paid review. Il CTA primario è:

> **"3 red flag detected. Book a free 30-min call con Asya + tax team. Portiamo il tuo SPT + benchmark settore, ti spieghiamo cosa cambierebbe. No commitment."**
>
> **[Start WhatsApp →]** (messaggio precompilato: "Ciao, ho fatto il Tax Gap check [link]. 3 red flags. Vorrei la free 30-min call.")

**Alternative CTA:**

- Se 0 red flags: _"Your numbers look aligned with peers. Want a quarterly digest? We email you when your sector's median shifts >10%."_ → email subscribe, no WA handoff push
- Se 5+ red flags: _"5 red flags is a lot. Book a priority call — this week. Start WhatsApp →"_

**La call contiene:**

1. Review dettagliata del SPT uploadato (i numeri veri)
2. Spiegazione red flag con pasal specifici
3. Benchmark peer anonimizzato mostrato a schermo (screenshare)
4. 3 domande: chi ti segue oggi? costa quanto? sei soddisfatto?
5. Se cliente unhappy → proposta soft switch a Bali Zero tax outsourcing (IDR 2,5M-10M/mese ricorrente — il VERO prodotto)

**Email post-call:** follow-up automatico con 3 azioni consigliate + eventuale quote tax outsourcing se interessato. Cron trigger 24h dopo call meeting.

## Engagement loop (retention senza conversion-push)

- **Quarterly digest email**: "Your sector's PPh median shifted 12% this quarter. Your numbers still aligned?"
- **Re-audit annuale**: "Your SPT deadline is in 90 days. Re-run your Tax Gap?"
- **Share**: user può condividere report con il proprio commercialista corrente (audit tool > rimpiazzatore)

## API

```python
POST /api/tax/gap/upload     # multipart file upload
  Body: file + sector_kbli?
  Response: { extracted_numbers, extraction_confidence, confirmation_required: true }

POST /api/tax/gap/analyze    # manual or confirmed extracted numbers
  Body: { revenue, pph_paid, ppn_paid, bpjs_paid, lkpm_filed, sector_kbli?, client_fp }
  Response: { hash, scorecard, red_flags[], recommendations[], benchmark_sample_size, result_url }

GET /api/tax/gap/{hash}

POST /api/tax/gap/subscribe
  Body: { hash, email, digest_frequency }
  Response: { subscription_id }
```

## Migration 121 — `tax_gap_reports` + `tax_benchmarks_aggregated`

```sql
CREATE TABLE tax_gap_reports (
  hash          VARCHAR(20) PRIMARY KEY,
  input_method  VARCHAR(16) NOT NULL,       -- upload_spt | upload_bukti_potong | upload_coretax | manual
  sector_kbli   VARCHAR(8),
  revenue_band  VARCHAR(16) NOT NULL,
  revenue_annual_idr BIGINT,
  pph_paid_idr  BIGINT,
  ppn_paid_idr  BIGINT,
  bpjs_paid_idr BIGINT,
  lkpm_filed    BOOLEAN,
  scorecard     JSONB NOT NULL,
  red_flags_count INT NOT NULL DEFAULT 0,
  recommendations TEXT[] NOT NULL,
  extraction_corrected BOOLEAN NOT NULL DEFAULT FALSE,  -- user corrected OCR
  client_fp     VARCHAR(32),
  view_count    INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at    TIMESTAMPTZ NOT NULL          -- 180 days
);

CREATE TABLE tax_benchmarks_aggregated (
  id              SERIAL PRIMARY KEY,
  sector_kbli     VARCHAR(8),                -- null = all sectors
  revenue_band    VARCHAR(16) NOT NULL,
  sample_size     INT NOT NULL,
  pph_over_revenue_median    DECIMAL(5,4),
  ppn_over_revenue_median    DECIMAL(5,4),
  bpjs_over_revenue_median   DECIMAL(5,4),
  lkpm_compliance_rate       DECIMAL(3,2),
  pph_p25 DECIMAL(5,4), pph_p75 DECIMAL(5,4),
  ppn_p25 DECIMAL(5,4), ppn_p75 DECIMAL(5,4),
  data_source     VARCHAR(64) NOT NULL DEFAULT 'bali_zero_crm',
  refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(sector_kbli, revenue_band)
);
```

**Refresh cron:** quarterly (01 gen/apr/lug/ott alle 04:00 UTC). Minimum sample_size ≥ 10 per cluster (altrimenti fallback "all sectors").

## Acceptance criteria

### Functional

- [ ] Upload PDF SPT → OCR extract → confirmation page con numeri estratti
- [ ] Upload fallito (garbled PDF) → graceful fallback a manual form con message
- [ ] Manual form submit → scorecard immediato
- [ ] Scorecard mostra 5 dimensioni + red flags + recommendations
- [ ] Benchmark label visibile e esplicito (no-bias disclosure)
- [ ] Subscribe quarterly digest → email conferma ricevuta
- [ ] WA CTA precompila red_flags_count + link al report
- [ ] Copy CTA adattivo (0 red / 3 red / 5+ red)
- [ ] Data retention cron cancella reports > 180gg
- [ ] Post-call follow-up email cron (24h dopo booking meeting)

### Privacy (critico)

- [ ] PDF bytes MAI persistiti su disco (verify filesystem audit)
- [ ] OCR buffer wiped dopo extraction (memory audit)
- [ ] Privacy frame visible sopra form (non footer)
- [ ] Unsubscribe one-click funziona
- [ ] Rate limit upload: 3 per fingerprint/ora
- [ ] Upload endpoint reject file > 10MB (413)
- [ ] CSP: `form-action 'self'`

### Engine accuracy

- [ ] 10 SPT format varianti parsed correttamente (test real samples anonimized)
- [ ] Benchmark median robusto a outlier (test 3-sigma noise injection)
- [ ] Scorecard thresholds allineati con manual review 20 casi (validated by tax team)
- [ ] Red flag false positive rate < 30% (manual audit Asya sample 20 reports)

### Performance

- [ ] OCR SPT (3 pagine) p95 < 15s
- [ ] `POST /api/tax/gap/analyze` p95 < 300ms (manual)
- [ ] Form Lighthouse mobile ≥ 90
- [ ] Result Lighthouse mobile ≥ 85

### Analytics

- [ ] `app_viewed`, `app_form_submitted`, `app_result_viewed`, `app_cta_clicked`, `app_whatsapp_handoff`
- [ ] NEW: `app_upload_started`, `app_upload_succeeded`, `app_upload_failed` (con error code)
- [ ] NEW: `app_ocr_extracted` con fields_extracted_count
- [ ] NEW: `app_user_corrected_ocr` (user modified extracted number) — se > 25% → OCR inaffidabile, downgrade UI

### Integration

- [ ] E2E Playwright upload path: drag PDF → confirm → scorecard → WA
- [ ] E2E manual path
- [ ] Privacy test: after upload, verify no PDF on disk (bash audit)
- [ ] Cron quarterly digest: test 3 mock subscriptions

## Killer risk + mitigation

**Risk 1:** Privacy friction blocks upload (traffic iniziale upload rate atteso 20-40%).

- Mitigation: manual form always visible, privacy frame prominente, retention delete trasparente con link al code source parser, no email required per upload (hash anonymous).

**Risk 2:** Benchmark bias (clientela Bali Zero self-selected compliance-serious).

- Mitigation: label esplicito "foreign-owned PT PMA clients, not nationwide average". Quarterly refresh con sample size disclosure. V2: partnership industry association per validation nationwide.

**Risk 3:** OCR false extractions.

- Mitigation: confirmation page OBBLIGATORIA. User può correggere ogni numero. Flag `extraction_corrected=true` in DB se corretto. Se correction rate > 20% → OCR inaffidabile, show manual form first.

**Risk 4:** Free call non converte a outsourcing (il vero prodotto).

- Mitigation: script call standardizzato Asya (3 domande chi/quanto/soddisfatto). KPI track: % free call → quote inviata → deal closed. Se < 15% → script rivisto.

**Risk 5:** Asya overloaded dalle free call.

- Mitigation: Calendly slot limitati (es. max 10 call/settimana). Lista d'attesa con email "Asya is booked this week, you'll get a slot in 7-10 days" — anche quello genera commitment (no-show rate bassi su queste liste).

## Dependencies

- Shared infra 00 DONE
- Tesseract + Indonesian language pack (verify: `tesseract-ocr-ind` installed)
- CRM `clients.tax_profile` column esiste (verify: `\d clients`)
- 10 SPT samples reali anonimizzati per test OCR
- Scorecard thresholds validated by Asya
- Calendly link Asya tax team attivo
- Privacy policy `/privacy/tax-gap` scritta

## Post-ship telemetry (30gg)

- Reports created per day
- Upload vs manual split (target ≥ 40% upload)
- Upload success rate (OCR fields extracted = 5/5)
- User correction rate (quanti modificano numeri OCR)
- Red flags distribution
- Quarterly digest subscribe rate + open rate
- WA handoff rate
- **Free call booked rate** (`app_cta_clicked destination=whatsapp` → calendly slot booked)
- **Call → outsourcing quote rate** (manual tracking Asya)
- **Quote → deal closed rate** (60-90 days lag)

**Alert Telegram:**

- If upload_rate < 20% @ 14gg → privacy frame insufficient
- If user_correction_rate > 25% → OCR degradato
- If red flags false positive > 30% (audit) → downgrade thresholds
- If matched_rate < 30% @ 30gg → WA messaging inaccurate
- If free call → quote conversion < 15% → script rivisto

## V2 roadmap

- CoreTax API integration diretta (no upload friction)
- Benchmark nationwide (industry association partnership)
- Multi-year trend: "PPh shifted vs last year"
- Integration war-room: push notification su tax regulation changes
- Export benchmark report PDF shareabile con commercialista corrente
- Tax outsourcing self-serve quote calculator (conseguenza naturale del flow)
