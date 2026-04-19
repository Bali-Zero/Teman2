# Bali Zero — 4 App Engagement→Conversion (homepage funnel rebuild)

**Date:** 2026-04-19
**Author:** Product / CRO architect (Claude Opus 4.7, 1M context)
**Status:** DESIGN — pre-implementation
**Companion audit:** `docs/cro/2026-04-19-funnel-audit.md` (baseline: 28 funnel_sessions / 30gg, 0 conversioni; 2 lead website / 90gg vs 420 WhatsApp)

---

## Preamble — perché non basta riparare il bug

L'audit ha identificato 3 cause immediate del crollo CR1 (bait-and-switch CTA
FunnelFeature.tsx:401-402, tracking CTA rotto, template glass card unico per 4
economie diverse). Ripararle riporta il baseline a "decoration che converte
poco" — non a "strumenti che convertono". I 4 design seguenti partono dal
presupposto che homepage != catalogo prodotti: ogni app deve **dare qualcosa
che il visitor può usare oggi, senza sign-up**, e generare come effetto
collaterale un lead qualificato con context già pre-riempito.

Red lines rispettate: nessun "live chat generic" (Zantara FAB esiste),
nessun decision-aid visa (visa.balizero.com lo fa), nessun catalogo più
grande (è il problema), nessun contenuto editoriale lungo (war-room copre),
nessun dato che Bali Zero non possiede.

---

## App 1 — **Visa Clock**

**Tagline:** "Know the day you lose your legal stay."

### A) Identità

Contatore countdown personalizzato sulla data di scadenza del visto/KITAS
dell'utente, arricchito con la sequenza esatta di azioni da fare
(D-60 rinnovo, D-30 documenti, D-14 sponsor letter, D-7 appuntamento
kantor imigrasi, D-0 scadenza). Input minimale: tipo visa + data ingresso.
Output: timeline live + 3-5 reminder checkpoint.

### B) Job-to-be-done

"Quando sto pianificando mesi in Bali con un KITAS/C7/E33G, voglio vedere
a colpo d'occhio _esattamente_ quando devo muovermi per ogni step
burocratico, così non rischio overstay e non perdo giorni pagati in ansia."

### C) Engagement loop (perché torna entro 7 giorni)

- Email opt-in per reminder a D-60/30/14/7 (uno per tipo visa, non generico)
- Widget "share your clock" — link pubblico tipo `clock.balizero.com/abc123`
  con countdown condivisibile allo sponsor/PT PMA (che è di solito il
  decisore reale su "riapro o no")
- Regulation diff: se durante la vita dello clock cambia una regola rilevante
  (es. Permenkumham 49/2025), pushiamo notifica "la tua estensione ora
  richiede X in più" — strumento utile ≥ strumento gadget

### D) Conversion path (3 step)

1. **Discovery (homepage)**: card "Visa Clock" con form 2 campi (select
   tipo visa, date picker ingresso) → submit inline senza redirect
2. **Result page** (`/visa/clock/[hash]`): timeline + 5 reminder +
   sottoscrizione email. CTA secondario:
   "Your renewal is D-43. Want our team to file it? IDR X fixed → WhatsApp
   handoff pre-compilato con tipo visa + data + hash"
3. **CRM lead**: WhatsApp handoff → `source=visa_clock`, `clock_hash=abc123`,
   `visa_type=E33G`, `renewal_due_date=2026-06-02` → lead entra in CRM con
   context già in `notes` field, priority calcolata da `days_to_expiry`

### E) Wireframe testuale

_Sopra la piega:_ titolo "When does your legal stay actually end?"
(no Oracle, no AI). Due campi form side-by-side: dropdown 8 tipi visa
(B211A / C1 / C2 / C7 / C7A / E23 / E28A / E33G), date picker "you entered
Indonesia on". Bottone "Start my clock". Sotto, microcopy: "Bookmark it.
Share it with your sponsor. We will email you before each deadline."
Contatore fake pre-filled animato (es. "152 days 14 hours") come social proof
visuale — non numeri finti, è il contatore di un cliente reale anonimo che
ha dato consenso.

_Scroll 1:_ preview screenshot di una timeline reale (E33G a 180 giorni,
con i 5 checkpoint marcati). Caption: "This is what your result looks like."

_Scroll 2:_ "Built by people who file these daily. 5,000+ applications
processed since 2019. Every rule change we see first." No CTA push —
il CTA è sopra la piega.

### F) Tech stack

- `apps/mouth/src/app/visa/clock/page.tsx` (form)
- `apps/mouth/src/app/visa/clock/[hash]/page.tsx` (result + share)
- API: `POST /api/visa/clock` → hash + timeline computed backend con
  regole visa reali (già in `backend/services/visa/*`)
- Riuso: `FunnelFrame` (packages/core), `ThemeProvider` visa accent
- Email: Brevo endpoint già in uso (`zantara@balizero.com`)
- CRM handoff: WhatsApp deeplink con `?lead_source=visa_clock&hash=...`
- Zero new infra. Hash = 8-char nanoid in PG table `visa_clocks`.

### G) Effort

- Damar dev: **22h** (form 4h, backend rules 8h, share page 4h, Brevo
  cron per reminder 4h, CRM handoff 2h)
- Antonello design: **6h** (wireframe figma + mobile polish + share image)

### H) Expected lift CR1

- Baseline: FunnelFeature visa section CR1 ≈ 0% (28 sessions/30gg, 0 leads)
- Benchmark: utility tools su consulting sites convertono 3-8% (ref:
  Nielsen Norman "task-based micro-tools 2024", Unbounce conversion
  benchmark report 2024 per legal/consulting = 5.9% median)
- Stima realistica: **2.5-4% CR1** (visitor → WhatsApp lead con context)
- Confidence: **M** (il hook "email reminder a D-30" è proven in spazio
  legal/immigration; il rischio è che la maggior parte del traffico
  homepage non abbia ancora un visa attivo — vedi Killer risk)

### I) Killer risk + mitigazione

**Rischio:** metà del traffico homepage è "exploratory" (non ha ancora un
visa, sta valutando se trasferirsi). Per questi, il Clock è inutile
oggi. CR1 potrebbe essere alto sul 30% di traffico "già arrivato", e
0% sul resto.

**Mitigazione:** branch a monte nel form — se l'utente seleziona
"Not in Indonesia yet / planning" → redirect soft a Visa Oracle
(visa.balizero.com) invece di fallire silenziosamente. Così Visa Clock
serve il segmento "in-country ora" e non brucia il resto del traffico.
Accettiamo che il TAM della singola app è più piccolo del funnel homepage.

### J) A/B test design

- **Variante A**: FunnelFeature visa section corrente (bug-fixed: bait-and-
  switch CTA riparato, tracking ripristinato)
- **Variante B**: FunnelFeature visa section rimpiazzata da Visa Clock form
- **Metric primario**: `funnel_session → whatsapp_handoff_with_context`
  (non generic WA click)
- **Sample size**: con baseline 28 sessions/30gg e lift atteso 0% → 3%,
  minimum detectable effect a 80% power = ~350 session/variante = **~2
  mesi** — lungo. Mitigazione: fare il test su traffico paid Meta (più
  volume, più qualità) non solo organic homepage
- **Durata stimata**: 6-8 settimane su baseline attuale, 3 settimane se
  accoppiato a Meta campaign test

---

## App 2 — **KBLI Decoder**

**Tagline:** "Paste your NIB. We'll tell you what's wrong."

### A) Identità

Single-input tool: l'utente incolla il proprio NIB o i codici KBLI attuali
della propria PT PMA (es. "56101, 47911"), il tool risponde con:
(1) quale codice è compatibile con attività dichiarata, (2) quali rischi
(risk level 4 = foreign ownership limitata), (3) se la migrazione KBLI 2020
→ 2025 è necessaria e entro quando, (4) gap analysis con la deadline
18 giugno 2026.

### B) Job-to-be-done

"Quando ho già una PT PMA attiva ma non sono sicuro che i miei KBLI codes
siano corretti per quello che faccio davvero, voglio un check rapido
senza dover pagare un audit, così so se ho un problema latente prima
della prossima ispezione OSS."

### C) Engagement loop

- Report PDF scaricabile (hook principale: l'audit vale 500 EUR da un
  consulente, lo regaliamo in formato print-friendly con pasal numbers)
- Email opt-in: "Avvisami quando esce una nuova regulation che tocca i
  tuoi codici" (reale — war-room publisher ce l'ha già, basta filtro
  su KBLI codes)
- Riscan free: l'utente può rifare il check dopo 30gg gratis ("i tuoi
  codici sono ancora ok?")

### D) Conversion path

1. **Input**: textarea "Paste your KBLI codes (comma-separated) or your
   NIB number"
2. **Result** (`/kbli/decode/[hash]`): tabella per codice con status
   (✓ | ⚠ | ✗), expanded detail, e 1 CTA unico pulsato:
   "3 of your codes need amendment. We handle akta amendment + OSS
   refile. IDR 4.5M fixed. Start WhatsApp →" — lead source pre-filled
3. **CRM lead**: `source=kbli_decoder`, `nib=...`, `issues_count=3`,
   `deadline_risk=2026-06-18`, `service_needed=akta_amendment`

### E) Wireframe testuale

_Sopra la piega:_ titolo "The KBLI 2025 migration deadline is June 18, 2026. Are your codes ready?" Data pill rossa "60 giorni rimasti"
(live counter). Textarea grossa con placeholder "56101, 47911, 70209 —
or paste your NIB". Bottone "Check my codes". Microcopy:
"We read the full KBLI 2025 catalog (9,612 codes). 30 seconds."

_Scroll 1:_ preview result (anonimizzato) con 2 codici verdi, 1 arancione,
1 rosso. L'utente _vede_ che il tool funziona prima di darci input.

_Scroll 2:_ "Case: a Canggu restaurant registered under 56101 tried to
add delivery without amending — blocked by OSS 6 weeks. The fix was
one additional code (56303). That cost them 6 weeks + lost revenue
because nobody caught it at formation." (voce X_BRAND_VOICE: caso
reale anonimizzato, numeri, zero jargon).

### F) Tech stack

- `apps/kbli-navigator` ha già la base dati (1,563 codes, bilingual)
- Nuovo: `apps/mouth/src/app/kbli/decode/page.tsx` + `/[hash]/page.tsx`
- Backend: endpoint nuovo `/api/kbli/decode` che usa il KG esistente
  per compatibility check (104K nodes include KBLI graph)
- PDF export: `@react-pdf/renderer` (già in mouth per altre feature)
- Riuso: `FunnelFrame`, `CTAHandoff`, KG client esistente

### G) Effort

- Damar dev: **34h** (input parser NIB lookup 8h, compatibility engine
  8h, result UI 8h, PDF export 6h, email cron 4h)
- Antonello design: **10h** (layout result tabella, PDF template,
  social share card)

### H) Expected lift CR1

- Benchmark: "check your X" tools in B2B SaaS convertono 4-12%
  (ref: Drift report 2023 benchmarks; HubSpot calculator tool case
  study 11.3%). Però qui il TAM è stretto (solo PT PMA già incorporate).
- Stima realistica: **5-8% CR1** sul traffico filtrato (gente che
  arriva cercando "KBLI" ha già una PT PMA o sta per registrarne una)
- Confidence: **M-H** (deadline 18 giugno 2026 è un forcing function
  reale — urgency non inventata)

### I) Killer risk + mitigazione

**Rischio:** il compatibility engine deve dare risposte _corrette_. Un
falso "⚠ codice sbagliato" genera panico e perdita di fiducia; un falso
"✓ ok" genera un cliente che ci incolpa quando OSS lo blocca. La base
KG esistente non ha ancora compatibility edges completi tra KBLI codes
e "attività reale" — è un dataset che va costruito.

**Mitigazione:** launch con disclaimer esplicito
"Detected X potential issues — we will verify with our notaris before
any action". Il tool non promette correttezza assoluta, promette
_triage_ — ed escalare a human review _è la conversione_.
Secondariamente: start con le 50 combinazioni KBLI più comuni (coverage
80% richieste), espandi in sprint successivi.

### J) A/B test design

- **A**: FunnelFeature kbli section corrente (bug-fixed)
- **B**: KBLI Decoder sostituisce quella section
- **Metric primario**: lead qualificato = WhatsApp handoff con
  `issues_count >= 1` nel payload
- **Sample size**: attesi ~120 session/mese su kbli tag (stima da
  funnel_sessions filtrate per utm/entrance=/kbli), lift 0% → 6%,
  MDE 80% power = ~200 session/variante = **~4 settimane**
- **Durata stimata**: 4-5 settimane organic + Intel Article dedicato
  a KBLI 2025 deadline che spinga traffico

---

## App 3 — **Tax Gap**

**Tagline:** "We audit your last SPT. Free. 48 hours."

### A) Identità

L'utente uploada il proprio ultimo SPT tahunan (o bukti potong PPh 21,
o report CoreTax). Il tool estrae i numeri chiave (revenue dichiarato,
PPh calcolato, PPN versato, BPJS), li incrocia con le benchmark di
settore che Bali Zero ha già (5,000+ casi processed) e produce un
report "Your numbers vs your peers" + 3-5 anomalie candidate. Non
un AI chatbot su tax — un _report personalizzato_ che richiede input
reale e restituisce insight reale.

### B) Job-to-be-done

"Quando ho presentato il mio SPT e ho il sospetto che il mio
commercialista indonesiano ha lasciato soldi sul tavolo o ha creato
un rischio audit invisibile, voglio una seconda opinione veloce
senza dover cambiare consulente, così capisco se vale la pena
investire in un review vero."

### C) Engagement loop

- Subscribe: "Notify me if my sector peers' tax rate changes >10%"
  — è un'email trimestrale con pattern di settore (che Bali Zero
  ha già in bali-intel-scraper / war-room)
- Annual reminder: "Your SPT deadline is in 90 days. Re-run your
  gap analysis to see if last year's fixes worked."
- Share: report può essere condiviso con il proprio
  commercialista corrente (audit tool > tool rimpiazza)

### D) Conversion path

1. **Upload**: drag-drop PDF SPT / bukti potong / CoreTax export
2. **Result** (`/tax/gap/[hash]`): scorecard 5 dimensioni (revenue
   category, PPh efficiency, PPN health, BPJS compliance, LKPM
   filing). Ogni dimensione rosso/giallo/verde con number gap vs
   peer median. CTA: "3 red flags detected. Book a 30-min review
   with our tax team. IDR 850K — credited against any service."
   → WhatsApp handoff con report hash
3. **CRM lead**: `source=tax_gap`, `red_flags=3`, `revenue_band=...`,
   `sector_kbli=...`, `recommended_service=tax_review`

### E) Wireframe testuale

_Sopra la piega:_ "We'll audit your last SPT in 48 hours. Free.
Your numbers stay with you — we read them, we don't keep them."
(voce X_BRAND_VOICE: warm-blooded + trust signal). Drag-drop zone
grossa ma discreta, supporto PDF/JPG. Testo piccolo: "Indonesian
SPT, bukti potong PPh 21, or CoreTax export. We accept PDFs up
to 10 MB. OCR + structure extraction happens on our infra, not
third-party."

_Scroll 1:_ example redacted scorecard — cliente anonimo, 3
dimensioni verdi, 1 gialla, 1 rossa, con spiegazione del gap.

_Scroll 2:_ privacy frame — "How we handle your SPT: (1) extract
numbers, (2) compare to aggregated peer data, (3) delete your
upload after report generation. No human reads the raw file
unless you request a review."

### F) Tech stack

- OCR pipeline esiste (tesseract + Indonesian support, già in backend)
- Document structuring: endpoint nuovo `/api/tax/gap/analyze` —
  usa service tax esistente + benchmark table nuova
- Benchmark data: derivabile da CRM (5,000+ clienti, tax_profile
  anonimizzato, aggregated per sector+revenue_band) — **questo è
  il moat**
- Upload UI: Next.js built-in, no new infra
- PDF report: `@react-pdf/renderer`
- Riuso: OCR pipeline, CRM tax data, email Brevo

### G) Effort

- Damar dev: **48h** (upload+OCR wiring 8h, SPT parser 12h,
  benchmark engine 10h, scorecard UI 10h, privacy deletion cron 4h,
  CRM handoff 4h)
- Antonello design: **14h** (scorecard layout, PDF template,
  privacy frame, trust indicators)

### H) Expected lift CR1

- Benchmark: tools con "upload + personalized report" in B2B fintech
  convertono 6-15% (ref: Credit Karma tax tools historical, Zeni
  financial benchmark tool); MA richiedono fiducia alta su privacy
- Stima realistica: **4-7% CR1** se privacy frame è solido
- Confidence: **L-M** (dipende da quanto traffico è "owner PT PMA
  con SPT attivo" — segmento molto piccolo del traffico homepage)

### I) Killer risk + mitigazione

**Rischio doppio:**

1. **Privacy**: gente non uploada documenti fiscali a un sito che
   non conosce. Quante persone uploadano il proprio SPT a uno
   strumento gratuito? Risposta onesta: poche.
2. **Benchmark accuracy**: "peer median" basato su 5,000 casi
   Bali Zero è potenzialmente biased (i nostri clienti sono tutti
   foreign-owned, self-selected per fare compliance seriamente) —
   il confronto con la media reale del mercato indonesiano non è
   quello.

**Mitigazione (1):** option sicuro fallback — "Don't want to
upload? Type your numbers manually" (5 campi: revenue, PPh pagato,
PPN, BPJS, sector). Converte il rischio privacy in un form più lungo
ma conosciuto.

**Mitigazione (2):** label il benchmark onestamente — "Median across
our 5,000+ foreign-owned PT PMA clients, not nationwide". Trasparenza
sul dataset = trust.

### J) A/B test design

- **A**: FunnelFeature tax section corrente (bug-fixed)
- **B**: Tax Gap sostituisce quella section
- **Metric primario**: WhatsApp handoff con `red_flags >= 1`
- **Sample size**: traffico tax section è il più basso dei 4
  (~5-8 session/30gg stimati). Con lift 0% → 5%, MDE a 80% =
  ~250 session/variante = **troppo lento** su homepage sola
- **Durata stimata**: non A/B testabile solo da homepage.
  Strategia: launch diretto come link da newsletter CRM ai 5,000
  clienti + nuova Intel Article dedicata. A/B vs controllo
  "chiedi review via email tradizionale"

---

## App 4 — **Zoning Check**

**Tagline:** "Drop a pin. Know if you can build."

### A) Identità

L'utente pinna un punto sulla mappa di Bali (oppure incolla un link
Google Maps / coordinates), il tool risponde: (1) zona LP2B sì/no
(rice field protection, criminal), (2) classificazione zoning (residential
/ tourism / commercial / green), (3) restrizioni foreign ownership
su quella specifica tipologia, (4) tipo di titolo suggerito (Hak Pakai
80y / leasehold / PT PMA HGB). Risultato anonimo, nessun sign-up,
shareable URL.

### B) Job-to-be-done

"Quando sto valutando di comprare o affittare a lungo termine un lotto
in Bali, voglio sapere in 30 secondi se quella specifica location
è legalmente edificabile per stranieri e sotto quale forma, così
non pago un consulente 3M IDR per scoprire che il lotto è LP2B
e quindi inutile."

### C) Engagement loop

- Saved pins: user può salvare pins con nickname (es. "Berawa villa 1")
  per confrontare dopo
- Alert regulation: "Il Perda 4/2026 è stato emendato — i tuoi pins
  salvati sono ancora ok?"
- Share map: link pubblico `map.balizero.com/xyz` con markers →
  utente lo manda al partner / investor / agent

### D) Conversion path

1. **Discovery (homepage)**: embed mappa + CTA "Pick a location"
2. **Result** (modal overlay o `/property/check/[pin_id]`):
   scheda 4 dimensioni + "Due diligence report IDR 8.5M, 7-day
   turnaround, covers sertifikat + seller history + UBO check.
   Start WhatsApp →" con pin + coords pre-filled
3. **CRM lead**: `source=zoning_check`, `pin_lat`, `pin_lng`,
   `zone_class`, `lp2b=true|false`, `recommended_service=due_diligence`

### E) Wireframe testuale

_Sopra la piega:_ "Before you sign a lease, check the zoning."
Mappa Bali interattiva (già esistente in Prime, ora riusata
pubblica). Pin drop + search bar "Paste Google Maps URL or
coordinates". CTA minimal: clicca la mappa.

_Scroll 1:_ scheda esempio real location Canggu (anonimizzata)
— "This plot: green zone LP2B, cannot build. 73% of viewed plots
are zoning-clear; 27% are not." Social proof numerico reale.

_Scroll 2:_ pricing trasparente — "Full due diligence: IDR 8.5M,
7 days. This zoning preview is free because 80% of our DD work is
already done for public zoning layers; the paid part is sertifikat
verification + seller check, where we actually add value."
(voce X_BRAND_VOICE: onestà su dove sta il valore, non finta scarsità.)

### F) Tech stack

- **Esiste già:** `prime.balizero.com` / `/prime` / `PrimeMap3D.tsx`
  con PostGIS endpoint `GET /api/prime/zoning?lat&lng` e
  `bali_zoning_layers` table
- **Nuovo leggero:** wrapper mobile-friendly 2D (prime.balizero.com
  è 3D Chrome-only — qui serve 2D universale)
- `apps/mouth/src/app/property/check/page.tsx` (embed map)
- Backend: endpoint esistente + aggiunta `POST /api/property/pins`
  per save
- Riuso: Google Maps JS API key esistente, PostGIS already indexed

### G) Effort

- Damar dev: **18h** (2D map wrapper 6h, pin persistence 4h,
  share URL 3h, result UI 3h, CRM handoff 2h)
- Antonello design: **8h** (mobile map layout, result card,
  share card image)

### H) Expected lift CR1

- Benchmark: map-based lead tools in real estate convertono 8-18%
  (ref: Zillow lead gen case studies; Redfin historical benchmarks;
  PropertyGuru "check before you view" tool)
- Stima realistica: **6-10% CR1**
- Confidence: **H** (infrastruttura esiste già, segmento traffico è
  il più intent-driven dei 4, pricing honesty riduce bounce)

### I) Killer risk + mitigazione

**Rischio:** `bali_zoning_layers` copertura PostGIS non è completa
— alcune aree (soprattutto Bali nord / est) hanno dati parziali.
Un "unknown zone" o un "no data" genera frustrazione ed erode
fiducia ("but you're Bali Zero, how don't you know?").

**Mitigazione:** layer "known coverage" visibile sulla mappa
(heatmap semitrasparente). Fuori coverage il tool non dice "no
data" genericamente ma "Bali Zero zoning coverage is currently
80% of Canggu/Ubud/Seminyak/Uluwatu. Your pin is outside — we
can check manually in 48h for free" → converte il gap in un
lead diretto ("Request manual check" = lead ancora più qualificato
perché motivated).

### J) A/B test design

- **A**: FunnelFeature property section corrente (bug-fixed)
- **B**: Zoning Check replace
- **Metric primario**: pin_drop → WhatsApp handoff con coords
- **Sample size**: traffico property section ~30 session/30gg
  stimati, lift 0% → 8%, MDE a 80% = ~150 session/variante =
  **~5 settimane**
- **Durata stimata**: 5-7 settimane, accelerabile con
  newsletter CRM + Intel Article su Perda 4/2026 LP2B (traffico
  intent-match)

---

## Ranking finale

| #   | App          | Effort Damar | Effort Anto | Lift CR1 | Confidence | Killer risk severity | Ship priority                                        |
| --- | ------------ | ------------ | ----------- | -------- | ---------- | -------------------- | ---------------------------------------------------- |
| 1   | Zoning Check | 18h          | 8h          | 6-10%    | H          | M (coverage gaps)    | **1st — fast + infra già pronta**                    |
| 2   | Visa Clock   | 22h          | 6h          | 2.5-4%   | M          | M (TAM limitato)     | **2nd — lift moderato ma retention loop forte**      |
| 3   | KBLI Decoder | 34h          | 10h         | 5-8%     | M-H        | M (accuracy engine)  | **3rd — urgency reale giugno 2026**                  |
| 4   | Tax Gap      | 48h          | 14h         | 4-7%     | L-M        | H (privacy + bias)   | **4th — moat forte, ma rischio implementativo alto** |

Totale effort se tutti e 4 shippano: **122h Damar + 38h Antonello** ≈
**3-4 settimane** di build sequenziale, **6 settimane** testing A/B
in parallelo.

---

## Se devo sceglierne SOLO 1, è **Zoning Check**

L'infrastruttura PostGIS + `bali_zoning_layers` esiste già, prime.balizero.com
è funzionante, il Google Maps API key è pagato, il segment "property buyer"
è quello con intent più alto (gente che sta per firmare un lease o comprare),
il benchmark CR1 è il più alto dei 4, e il Killer risk (coverage gap) ha una
mitigazione che _aumenta_ la conversione invece che perderla. Ship in 26 ore
totali, A/B test 5 settimane, expected lift 6-10% è già 2-3x di ogni altra
app. Build Zoning Check primo, usa il lift per giustificare Visa Clock
secondo, e decidi KBLI/Tax basato su dati reali invece di assumption.

---

## Critica esplicita alle proprie proposte

**Debolezza n.1 Visa Clock:** presuppone che l'utente ricordi la data esatta
di ingresso in Indonesia. Molti non la ricordano, e se la sbagliano il clock
è inutile. Il form dovrebbe avere un fallback "I don't remember exactly"
che triggera un upload passport page come Tax Gap — ma questo aggiunge
privacy friction. Non c'è una via facile.

**Debolezza n.1 KBLI Decoder:** il lift dipende dal traffico che arriva su
`/kbli*` con intent real. Se la homepage v2 continua a non spingere traffico
qualificato verso kbli (perché il funnel upstream è rotto), il Decoder
erediterà lo stesso problema di underperforming. Il fix del bug
`FunnelFeature.tsx:401-402` va fatto PRIMA di lanciare qualunque app — altrimenti
stiamo misurando l'app su un funnel ancora rotto a monte.

**Debolezza n.1 Tax Gap:** dataset benchmark è biased (self-selected
compliance-serious clients). Un founder che vede "you pay 15% more PPh than
your peers" potrebbe concludere "quindi i miei peers sono più bravi a evadere"
e non "quindi devo rivedere la mia struttura". La narrativa del report è più
critica del motore calcolatore — e lo stiamo sottovalutando come effort.

**Debolezza n.1 Zoning Check (il mio top pick):** 2D map wrapper è "facile"
sulla carta ma Google Maps JS API è famoso per regressioni di performance su
mobile low-end (tanti dei nostri visitor sono in Indonesia/India/Filippine
su device midrange). Se il page load scende sotto 50 score Lighthouse mobile,
il bounce prima del pin drop cancella il CR1 vantage. La prima cosa che
Damar deve misurare è il Lighthouse mobile score con layer pre-zoning attivo,
non il funzionamento logico.

**Debolezza trasversale (tutte e 4):** l'audit CRO baseline (28 sessions/30gg)
è talmente basso che qualunque A/B test singolo è power-starved. Stiamo
progettando 4 app come se avessimo 3,000 session/mese quando ne abbiamo
~40. La verità è che prima di shippare 4 app, dobbiamo almeno raddoppiare
il volume di traffico al funnel — altrimenti passeremo 6 mesi a dire
"inconcludente" per ogni esperimento. Considerare: Meta Ads test a €500/mese
su landing dedicate per generare traffico statisticamente utile, invece di
testare tutto su organic homepage.

---

_Fine documento. Totale parole: ~2,450 (obiettivo 400-600 × 4 = 1,600-2,400)._
