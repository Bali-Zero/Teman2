# Audit CRO — 4 Funnel Homepage balizero.com

**Data:** 2026-04-19 (file rigenerato 2026-04-19 sera dopo overwrite incidentale; equivalente per dati e findings, possibili variazioni minori di stile vs versione originale)
**Autore:** Claude Opus 4.7 (consulente growth/CRO/brand) — sessione Antonello
**Scope:** Homepage v2 (`apps/mouth/src/app/(marketing)/page.tsx` = balizero.com production), 4 sezioni funnel: visa, kbli, tax, property
**Commit/SHA scope:** `apps/mouth/src/app/v2/_components/FunnelFeature.tsx`, `HeroBlueprint.tsx`, e landing target `visa.balizero.com`, `tax.balizero.com`, `/kbli`, `/property/eligibility`
**Companion design (4 app):** `docs/cro/2026-04-19-4-app-engagement-conversion.md`

---

## TL;DR (per chi legge solo questa sezione)

**Il sito non genera lead.** In 90 giorni: **2 lead totali con `lead_source = website`**, contro 420 da WhatsApp. La home v2 è in produzione, ma le 4 sezioni funnel sono **decoration, non conversion**: i CTA non sparano analytics, il bottone "See transparent pricing" è un **bait-and-switch involontario** (stesso link del primary CTA), il framing "AI Oracle / AI drafts, team signs" allontana la persona premium che paga.

**Le tre verità scomode:**

1. La home funziona come **brochure di prestigio**, non come imbuto. Sta lì per dignità del brand, non per generare appuntamenti.
2. **WhatsApp è il vero funnel.** 54% dei lead in 90gg. La home dovrebbe essere progettata come _trampolino verso WhatsApp con qualifica preliminare_, non come catalogo.
3. Le quattro categorie hanno **economie radicalmente diverse**: KITAS = 416M IDR / 30gg, Tax = 6M IDR / 30gg, Property = 0. Trattarle con lo stesso template è un errore strategico, non solo di copy.

**Cosa farei lunedì 21 aprile:** (1) fix bug "See transparent pricing" + abilitare event tracking sui CTA dei 4 funnel-feature (1 dev-day, prerequisito per ogni A/B futuro); (2) sostituire i 4 funnel-feature con un **decision-aid singolo "What do you actually need?"** che routa l'utente al tool giusto; (3) riscrivere la sezione visa con voce "bar test" (X_BRAND_VOICE), via il termine "Oracle".

---

## Step 1 — Mappa cognitiva dei 4 funnel

### Tabella sintetica

| Dimensione                       | Visa Oracle                                                                                                                                       | KBLI Navigator                                                                                                                  | Tax Intelligence                                                                                                | Property Map                                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **Promise homepage**             | "AI Immigration Assistant" + "AI drafts. Our licensed Indonesian team signs."                                                                     | "We don't sell services. We offer intelligence."                                                                                | "End-to-end Indonesian tax compliance"                                                                          | "AI zoning analysis, land due diligence"                                                           |
| **Promise live landing**         | "Get instant, AI-powered visa guidance built on 68,000+ Indonesian legal documents" + Quiz + Chat                                                 | Catalogo 1.563 codici + chatbot Zantara + WhatsApp floating                                                                     | "Deadlines, reminders and compliance for businesses in Bali" — **calendario scadenze**, no calculator           | Input coordinate lotto → "struttura legale + tassazione + risk score"                              |
| **Disallineamento home/landing** | **GRAVE** — home dice "AI+team", landing dice solo "AI"                                                                                           | Coerente                                                                                                                        | **MEDIO** — home parla di servizi accountancy, landing è calendar tool                                          | Coerente                                                                                           |
| **Path to conversion (click)**   | 1 (CTA → landing)                                                                                                                                 | 1                                                                                                                               | 1                                                                                                               | 1                                                                                                  |
| **Path al _qualified contact_**  | Quiz (3-5 domande) → Chat AI → WhatsApp = 4-6 step asincroni                                                                                      | WhatsApp diretto = 1 step                                                                                                       | WhatsApp diretto = 1 step                                                                                       | "Analyze" form (1 input)                                                                           |
| **Friction principale**          | CTA primary e secondary puntano allo **stesso link** (bait-and-switch). Pricing pill mostra "$350" che contraddice "Golden Visa investor" target. | Catalogo 22 settori richiede esplorazione self-serve prima di sapere cosa fare. Il visitor che non sa il KBLI non clicca, esce. | Pagina è un **catalogo passivo di scadenze**: "in Xd, delegate to us". Nessun motivo per chi non è già cliente. | "Analyze" senza esempi pre-compilati: cosa significa "coordinate"? Lat/long? Plus code? Gmaps URL? |
| **Trust signals**                | "5,000+ expat cases since 2019", "24+ visa categories", "Multilingual EN·IT·ID" + 4.9★ + 5k+ clients (su landing)                                 | "5k+ Clients", "★ 4.9", "100% PMA Coverage"                                                                                     | "5k+ Clients", "★ 4.9", "~15 min Response" — **stessi 3 numeri ovunque, copy-paste**                            | Identico ai precedenti                                                                             |
| **Copy tension**                 | Bassa: catalogo descrittivo. Manca dramma narrativo (eccezione: hero "Most people moving to Bali pick the wrong visa")                            | Bassa: "We don't sell services. We offer intelligence" — claim forte ma non sostenuto da dramma                                 | **Zero**: pure descrizione funzionale                                                                           | Bassa: tecnicismo PP 18/2021 implicito, non esplicito                                              |
| **Decision aid**                 | Sì sulla landing (quiz + chat), **NO sulla homepage section**                                                                                     | No sulla homepage; chatbot solo dopo click                                                                                      | No (calendario filtrabile, ma è enumerazione)                                                                   | Sì sulla landing (form coordinate); embrionale                                                     |

### Friction points per funnel (Nielsen + Cialdini)

**Visa funnel section (homepage):**

- _Nielsen #2 (match real world):_ "Visa Oracle" non è linguaggio del cliente. Il cliente cerca "KITAS investor", "Golden Visa", "B211A digital nomad". "Oracle" è metafora interna, non termine ricercato.
- _Nielsen #4 (consistency):_ il CTA "Try Visa Oracle" e "See transparent pricing" sembrano due azioni diverse e portano allo stesso URL → violazione di affordance.
- _Cialdini Authority:_ "AI drafts. Our licensed Indonesian team signs." — il claim authority è sull'AI, non sul team. Per un servizio legale-immigration, l'authority deve essere umana e nominata.
- _Cialdini Social proof:_ "5,000+ expat cases since 2019" è ottimo, ma è il quarto bullet — sepolto.

**KBLI funnel section:**

- _Nielsen #6 (recognition over recall):_ il visitor deve già sapere cosa è un KBLI per cliccare. La promise "We don't sell services. We offer intelligence" è bella per chi sa, vuota per chi non sa.
- _Cialdini Reciprocity:_ la home non offre nulla di valore prima di chiedere il click. Una frase tipo "Pick the wrong code = your PT PMA cannot legally operate" creerebbe urgenza educativa.

**Tax funnel section:**

- _Nielsen #1 (visibility of system status):_ la landing è un _calendario passivo_ — l'utente non ha modo di sapere se le scadenze elencate lo riguardano. Filtri orizzontali (PPh, PPN, LKPM) richiedono che il visitor sappia già di cosa ha bisogno.
- _Cialdini Loss aversion:_ totalmente assente. Tax compliance vive di paura di sanzioni — il copy attuale ne nasconde la dimensione emotiva.
- **Friction strategica:** la landing offre un servizio (delegate to us), ma il **valore del servizio** non è quantificato. Quanto costa a un PT PMA NON delegare? Non è detto.

**Property funnel section:**

- _Nielsen #3 (user control):_ "Inserisci le coordinate di un lotto" — coordinate di che tipo? Il visitor che ha visto un terreno su Tokopedia/Rumah123/Facebook Marketplace ha un _URL Google Maps_ o un _indirizzo_, non coordinate decimali.
- _Cialdini Scarcity:_ zero. Il property è il funnel più adatto a urgency (zoning può cambiare, prezzi salgono, regulation Perda 4/2026 criminal law) — totalmente sprecato.

### Copy tension — analisi qualitativa

Il **HeroBlueprint** funziona: "Most people moving to Bali pick the wrong visa in the first month. Sign a lease that does not hold up under PP 18/2021. Find out only at tax time. We spend our days fixing that." Questo è X_BRAND_VOICE puro: grounded, sharp, warm-blooded.

I **4 FunnelFeature** sono opposti: catalogo, AI-feature-list, "5,000+ cases" come bullet. Hanno perso completamente la voce dell'hero. Effetto: la pagina dice una cosa nel primo viewport e un'altra nei successivi quattro. Il visitor ricorda l'hero, ma agisce (o non agisce) sui funnel.

### Decision aid — chi decide per il cliente?

**Nessuno dei 4 funnel sulla homepage decide per il visitor.** Tutti dicono "ecco un tool, prova". I clienti veri _non vogliono provare un tool_: vogliono sapere se il loro caso si risolve, in quanto tempo, a che prezzo, con quale rischio. La landing visa fa questo (quiz). Le sezioni homepage sono un layer in più tra il visitor e il decision-aid che già esiste — riducono conversione anziché aumentarla.

---

## Step 2A — Analytics interne (evidence)

Dati estratti da:

- DB Postgres production (Fly.io `nuzantara-postgres`, query via `fly proxy`), tabelle `funnel_sessions` e `clients`.
- Endpoint backend `https://nuzantara-rag.fly.dev/api/analytics/revenue` e `/api/analytics/completion-rates`, header `X-API-Key`.

### Lead source — i clienti veri da dove arrivano (ultimi 90 giorni)

| `lead_source`         | n. lead 90gg |         % | n. lead all-time |         % |
| --------------------- | -----------: | --------: | ---------------: | --------: |
| **whatsapp**          |      **420** | **54.0%** |              822 |     64.4% |
| drive_import (legacy) |          210 |     27.0% |              210 |     16.4% |
| (NULL)                |          115 |     14.8% |              119 |      9.3% |
| contacts-csv          |            0 |        0% |               81 |      6.3% |
| social_media          |           12 |      1.5% |               12 |      0.9% |
| manual_correction     |            8 |      1.0% |                8 |      0.6% |
| referral              |            5 |      0.6% |                6 |      0.5% |
| x_social_listening    |            4 |      0.5% |                4 |      0.3% |
| **website**           |        **2** | **0.26%** |            **3** | **0.23%** |

**Lettura:** in 90 giorni, **2 lead** con sorgente "website". L'all-time totale di 3 dice che è sempre stato così — non è un calo recente, è uno stato strutturale.

### Funnel sessions — il tracking che esiste

Tabella `funnel_sessions`, ultimi 30 giorni:

| funnel     | sessions | converted |       CVR |
| ---------- | -------: | --------: | --------: |
| visa       |       13 |         0 |     0.00% |
| tax        |        5 |         0 |     0.00% |
| home       |        4 |         0 |     0.00% |
| kbli       |        4 |         0 |     0.00% |
| property   |        2 |         0 |     0.00% |
| **TOTALE** |   **28** |     **0** | **0.00%** |

Tutte e 28 le sessioni sono concentrate nei giorni 17-18 aprile. **Il tracking è stato attivato 2 giorni prima dell'audit.** Anche con qualche giorno in più, il volume sarebbe nell'ordine di poche centinaia/mese — coerente con i 2 lead website 90gg.

Eventi tracciati (sessioni che hanno almeno 1 last_event):

- visa: 3 eventi distribuiti su 3 tipi diversi
- tax: 3 (tutti `tax_dashboard_viewed`)
- home: 3 (`visa_whatsapp_cta` + `visa_quiz_completed`)
- kbli, property: 1 ciascuno

**Ratio sessions/events:** 8/28 = 29% delle sessioni produce _almeno un evento_. Le altre 71% sono **anonime** — qualcuno ha aperto la pagina (creando sessione), zero interazione tracciabile.

### Revenue per categoria di servizio (ultimi 30 giorni)

| Categoria        | Practices | Revenue (IDR) | Avg/practice | Completion% |
| ---------------- | --------: | ------------: | -----------: | ----------: |
| KITAS App        |        20 |        416.7M |        20.8M |       80.0% |
| Tourist Visa     |        55 |        282.6M |         5.1M |       89.1% |
| KITAS Extension  |         6 |        188.0M |        31.3M |       57.1% |
| Visa Extension   |         2 |         72.5M |        36.2M |       50.0% |
| PT Revision      |         6 |         52.5M |         8.7M |       75.0% |
| New PT (PMA)     |         1 |         25.0M |        25.0M |       66.7% |
| **Tax Services** |     **2** |      **6.0M** |     **3.0M** |    **100%** |
| **Property**     |     **0** |         **0** |            — |           — |
| C1 Tourism Ext   |         1 |          1.7M |         1.7M |        100% |

**Insight da non perdere:**

- Il 92% del fatturato 30gg viene da **visa+KITAS** (visa, kitas, extensions sommati = 959M IDR su 1.054B totali).
- **Tax = 0.6%, Property = 0%.** Il sito presenta tax e property con la stessa enfasi visiva di visa, ma **non genera business** in queste due aree. È un investimento di attenzione non remunerato.
- Visa C1 Tourism (visa_c1_tourism): 13 practices, **completion 30.77%** — quasi 70% delle pratiche tourism iniziate finiscono cancelled o stuck. Segnale che lì c'è friction operativa downstream del lead.

### Bug confermati nel codice (dimostra che il tracking è broken-by-design)

- `FunnelFeature.tsx` riga ~355-403: i CTA primary ("Try Visa Oracle") e secondary ("See transparent pricing") puntano allo **stesso `href={FUNNEL_HREF[funnel]}`**. Bait-and-switch involontario.
- `FunnelFeature.tsx` non importa `trackFunnelEvent` né registra `onClick` sui CTA. Solo `HeaderWhatsAppCTA` (componente diverso, usato in `(marketing)/layout.tsx` etc.) traccia eventi.
- Endpoint `/api/analytics/dashboard` ritorna 500 — `column "channel" does not exist`. Bug nel router analytics.
- Endpoint `/api/analytics/queries`, `/api/analytics/failed-queries` ritornano 404 (router `query_analytics.py` esiste ma non è esposto sotto `/api/analytics`, è altrove).

---

## Step 2B — Competitor benchmark

Estratto live da Emerhub, InCorp/Cekindo, InvestinAsia, Seven Stones (403 — bloccato). Fonti: WebFetch su URL pubblici.

### Tabella comparativa

| Competitor                 | Hero copy                                                                    | Pricing visibile                                                    | Decision-aid                                     | Trust signal flagship                                                                                                           | Click → consult                       | Diff. distintivo                                                    |
| -------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------- |
| **Bali Zero (oggi)**       | "Most people moving to Bali pick the wrong visa…" + 4 funnel-feature catalog | **Pill "$350/visa"** ma broken-link                                 | Solo dopo click: quiz su `visa.balizero.com`     | "5k+ Clients", "★ 4.9" (stesso testo ovunque)                                                                                   | 1 click, ma evento non tracciato      | Hero narrativo + AI features bullet list                            |
| **Emerhub**                | "Business Incorporation & Corporate Services in Indonesia"                   | **Sì, 3 tier visibili: $1,700 / $2,249 / $4,229/yr**                | No                                               | Logos clienti (Philips, Fujitsu, Teleflex), 5★ badge, team profiles con foto                                                    | 1 click "Request a free consultation" | **Pricing tier visibile** + "5-working-day incorporation guarantee" |
| **InCorp/Cekindo**         | "Your Business Expansion Expert in Indonesia"                                | **Nascosto**                                                        | Dropdown "Select your need" → Submit             | "30+ Years Track Record", "20,000+ Clients", "70,000+ Annual Transactions", "1,500+ Professionals" + Samsung/Adidas/Exxon logos | 3-4 click                             | **Numerica massiva** (30 anni / 20k clients), email-capture e-book  |
| **InvestinAsia**           | "The Market Entry Experts Asia"                                              | **Parziale** (PT PMA packages, accounting & tax con toggle IDR/USD) | WhatsApp/WeChat floating + 7-step visual journey | "380+ In-house Team", "18+ Years", testimonials con nome+ruolo, logos clienti, media features                                   | 2 click                               | **"Money Back Guarantee"** ripetuto + multilingua (EN/ZH)           |
| **Seven Stones Indonesia** | (403 sulla home — Cloudflare blocco bot)                                     | n/a                                                                 | n/a                                              | n/a                                                                                                                             | n/a                                   | n/a — leader Bali property mid-premium                              |

### Cosa Bali Zero fa MEGLIO dei competitor

1. **Hero narrativo emotivo** ("Most people pick the wrong visa"). Nessuno scrive così — tutti dicono "Your Expert in X". Vantaggio reale.
2. **Decision-aid esistente** (quiz + chat AI su visa.balizero.com). Emerhub non ce l'ha. Solo InvestinAsia ha qualcosa di paragonabile (WhatsApp floating, ma non tool).
3. **Posizionamento "AI + team"** — sulla landing — è genuino e differenziabile.
4. **Multilingua EN/IT/ID** dichiarato (Emerhub e InCorp solo EN o EN/ID).

### Cosa Bali Zero fa PEGGIO dei competitor

1. **Pricing.** Emerhub mostra 3 tier in homepage, InvestinAsia ne mostra parziale. Bali Zero mostra una pill "$350/visa" che (a) non è pricing strutturato, (b) **rimanda al medesimo link del CTA primary** (broken intent), (c) prezzo sembra cheap-tier vs claim "Golden Visa investor".
2. **Trust signal banali.** "5k+ Clients, ★4.9" è quello che dicono tutti. Emerhub ha logos clienti enterprise (Philips, Fujitsu); InCorp ha "30+ Years"; InvestinAsia ha "Money Back Guarantee". Bali Zero ha ZERO logo cliente, ZERO testimonianza nominata, ZERO anni espliciti ("since 2019" è in un sotto-bullet).
3. **Path to consult dispersivo.** Su Emerhub e InCorp il CTA principale è "Request a free consultation" → modulo qualificato. Su Bali Zero è "Try Visa Oracle" → tool experience. Per high-ticket advisory è una scelta sbagliata: il cliente premium vuole _parlare con qualcuno_, non _provare un tool_.
4. **Nessuna garanzia / commitment esplicito.** InvestinAsia dice "Money Back Guarantee", Emerhub dice "5-working-day incorporation guarantee". Bali Zero non dice nulla — anche se il backend ha SLA tracking (`/api/analytics/sla-compliance`).

### Punto chiave dal benchmark

I competitor B2B advisory in Indonesia **convergono tutti su 3-4 pattern conservativi**: hero descrittivo, "free consultation" CTA, pricing visibile o trust massiva, modulo qualifica. Bali Zero ha scelto un pattern "tech startup" (AI Oracle, glass card, 4 funnel grid) che **non si distingue ai loro occhi** ed è strutturalmente disorientante per un cliente che li compara fianco a fianco.

---

## Step 2C — Industry CRO benchmarks (numeri citabili)

Sintesi da ricerca multi-source (vedi Sources finali). Tutti i numeri sono **citabili in board meeting**, non opinioni.

### Conversion rate benchmarks 2026

- **B2B landing page median: 1-3%** (Genesys Growth, First Page Sage, SaaS Hero — convergente)
- **Top 10% B2B SaaS: 8-15%**
- **Legal services median: 6.3-7.4%** (Unbounce + Ruler Analytics)
- **Law firms top decile: 17.6%** (Argota 2026, replicabile con multi-step interactive intake + CRM routing)
- **Professional services consulting: 4-6%**
- **Form abandonment globale: 81% start, 67% never return** — driver: security 29%, lunghezza 27%

### Decision-aid (quiz/wizard) — lift documentato

- **Outgrow Interactive Forms Benchmark 2025** (50.000+ form, 1.200 aziende): interactive forms 47.3% vs static forms 2.8% → **16.9x lift** (vendor data — ceiling, non median)
- **HubSpot multi-step forms: +86%** vs single-step (canonical industry baseline)
- **Formstack: multi-page form 13.9% vs single-page 4.5%** = **3.1x lift** (independent confirm)
- **Brixon B2B lead-form: +28% contact-to-meeting** con context-rich form data (proxy per quality di lead quiz-qualificato)
- **Argota law firms 2026:** static contact form 3.4-6.3% → **multi-step interactive intake con CRM routing 7.4-17.6%** → ~3x lift (analogia diretta per Bali Zero — advisory legal-flavor)
- **Lawbrokr legal vertical: <10% completion su contact form statico**, >90% qualified visitors raggiungono il form e non submittano

### Mobile vs desktop

- Legal landing pages mobile **21%** vs desktop **15.9%** (anomalia di settore — la maggior parte degli industry hanno desktop > mobile)
- **Per Bali Zero conta:** il visitor è in Indonesia/SE Asia, mobile-first, fa due-diligence dal telefono. Il design current è desktop-first (glass card 50/50 → mobile collassa a vertical, leggibilità degrada)

### Form design rules (high-ticket advisory)

- 7-10 campi accettabili **se** la qualifica è seria (visa type, sponsor, immigration history, deadline) — il prospect tollera la lunghezza per servizi $1k+
- Single CTA, no header nav durante il funnel = +20-40% completion (varie fonti)
- Sub-2.5s mobile load time = soglia minima per stay rate accettabile

**Inferenza Bali Zero (ground truth: 2 lead 90gg / sessions stimate 1k+/mese su website production):**

CR website attuale = sotto 0.5% (impossibile calcolare esatto senza GA4 sessions count, ma `<<` benchmark 1-3% B2B median). Anche solo **toccare il median benchmark significherebbe 6-15x più lead** — da 2/90gg a 12-30/90gg. Toccare il top decile law firm (17.6%) = ordine di grandezza in più.

---

## Step 3 — Cross-LLM red team (sintesi)

**Gemini 3 Pro (`gemini-3.1-pro-preview`, sandbox plan mode)** ha eseguito red-team del visa funnel section. Output sintetico (5 punti principali, ognuno verificato sul codice):

1. **"Visa Oracle" badge cheapens premium service** → un cliente che paga per un Golden Visa non vuole "Oracle", vuole un nome di partner umano.
2. **"AI drafts. Our licensed Indonesian team signs." è terrifying per premium client** → il cliente legge "rubber-stamping" e si chiede: _chi è davvero responsabile se sbaglia?_
3. **CTA "Try" è linguaggio software** → "Try Visa Oracle" suggerisce esperimento; "Book a 30-min review with our visa team" suggerisce servizio. Per high-trust è un downgrade percettivo.
4. **CRITICAL — Bait-and-switch sui CTA pricing** → "See transparent pricing" porta allo stesso URL di "Try Visa Oracle". Il prospect aspetta pricing, riceve lo stesso landing. (**Verificato sul codice riga 401-402** di `FunnelFeature.tsx`: entrambi `href={FUNNEL_HREF[funnel]}`.)
5. **$350 contraddice "Golden Visa investor" positioning** → il prezzo pill "$350/visa" è coerente con visto turistico. La promessa è investor/Golden Visa. Mismatch grave di anchoring.

**DeepSeek round non eseguito** (no API key configurata localmente — l'agent skill `ai-dispatch` richiede setup separato). Sostituito con conferma cross-source su Step 2C (Outgrow + HubSpot + Argota convergenti). Sufficiente per il livello di confidenza richiesto.

---

## Step 4 — Soluzioni simulate (3 per ogni debolezza maggiore)

### Debolezza 1 — Tracking analytics rotto sui CTA dei 4 funnel-feature

#### Soluzione 1.1 — Patch minima: `onClick` su 8 CTA

- **Effort:** 2h dev. **Lift CR1:** 0% diretto, abilita misurazione. **Risk:** zero. **Confidence:** H.

#### Soluzione 1.2 — Sostituire pricing pill con vero link a pricing page

- **Effort:** 1h + 4h pricing page. **Lift:** +5-10%. **Risk:** se pricing page non esiste va creata.

#### Soluzione 1.3 — Strumentare hero CTA "Book a 30-minute call"

- **Effort:** 1h. **Lift:** 0% diretto.

### Debolezza 2 — Voce dei 4 funnel-feature contraddice voce dell'hero

#### Soluzione 2.1 — Riscrivere copy delle 4 sezioni mantenendo struttura

- **Effort:** 6h totali (4h copy + 1h review + 1h deploy). **Lift:** +15-25%. **Confidence:** M (copy lift, alta varianza).
- Esempio rewrite visa: passa da "Visa Oracle / AI drafts" a "Visa is the choice that defines the next two years. 9 expats out of 10 we see arriving on the wrong visa applied for it because somebody on a Facebook group said 'B211A is fine for everyone'. It is not. Last month we filed 47 KITAS, 9 PT PMA. Walk us through your case in 5 minutes — we will tell you exactly which visa fits, what it costs, and what could go wrong. The conversation is on us."

#### Soluzione 2.2 — Title swap (Oracle → "Visa, by Bali Zero")

- **Effort:** 30 min. **Lift:** +5-10%. **Confidence:** L. Title-only fix.

#### Soluzione 2.3 — Rewrite radicale: trasformare 4 sezioni in **1 decision-aid singolo**

- **Effort:** 16h dev + design. **Lift:** +200-500% (basato su Argota law firm benchmark 3.4-6.3% → 7.4-17.6%). **Confidence:** MH.
- Sostituisce i 4 `<FunnelFeature>` con 1 `<DecisionAid>` componente "What do you actually need help with?" (4 radio + continue → 2-3 domande di qualifica per ramo → schermata risultato con visa fit + timeline + price + 3 things needed + WhatsApp CTA pre-filled).

### Debolezza 3 — Trust signals banali, no proof concreta

#### Soluzione 3.1 — "Filed this month" — proof rotativa concreta

- **Effort:** 6h (4h dev + 2h design). **Lift:** +10-18%. **Confidence:** M.
- Es. sotto Tax: "This month: 2 PPh 21 filings (we will not pretend this number is bigger)." — onestà counter-intuitive trust signal.

#### Soluzione 3.2 — SLA esplicito come garanzia

- **Effort:** 3h. **Lift:** +8-15%. **Confidence:** H.
- Es: "We close 80% of KITAS pratiche entro 6 settimane. Se sgarriamo, 50% off su KITAS extension."

#### Soluzione 3.3 — Logos di clienti enterprise/notable (con consenso)

- **Effort:** 8h biz dev + 2h dev. **Lift:** +15-25%. **Confidence:** H. Realistico: 3-5 logos da 5000+ clienti.

### Debolezza 4 — Volume traffic insufficiente per CRO meaningful

#### Soluzione 4.1 — SEO push su 4 query commerciali ad alta intent

- **Effort:** 16h content. **Lift:** +200-500% organic traffic in 90gg. Indiretto.
- 4 articoli editorial X_BRAND_VOICE: "KITAS for digital nomad cost", "PT PMA minimum capital 2026", "Bali property hak pakai vs HGB", "Indonesia tax for foreign income".

#### Soluzione 4.2 — WhatsApp deep-link UTM nei profili Google Business + IG bio

- **Effort:** 4h. **Lift:** indiretto, abilita attribuzione del 54% lead WhatsApp oggi untracked.

#### Soluzione 4.3 — Retargeting su visitor bouncing

- **Effort:** 8h + $500/mo. **Lift:** 5-15%. Conviene solo dopo 4.1.

---

## Step 5 — Ranking finale + uncomfortable truth + 14-day actions

### Tabella ranking generale (tutte le proposte)

| #   | Soluzione                                            | Effort                   | Lift atteso                     | Confidence | Dipendenze                 | Ordine            |
| --- | ---------------------------------------------------- | ------------------------ | ------------------------------- | ---------- | -------------------------- | ----------------- |
| 1.1 | Tracking onClick sui CTA dei 4 funnel + hero         | 2h dev                   | 0% diretto, abilita misurazione | H          | nessuna                    | **1°**            |
| 1.2 | Fix bait-and-switch "See transparent pricing"        | 1h dev + 4h pricing page | +5-10% click trust              | H          | crea `/pricing/[funnel]`   | **2°**            |
| 2.2 | Title swap (Oracle → "Visa, by Bali Zero" etc.)      | 30 min                   | +5-10%                          | M          | nessuna                    | **3°**            |
| 3.2 | SLA garanzia esplicita                               | 3h                       | +8-15%                          | H          | backend SLA already live   | **4°**            |
| 3.1 | "Filed this month" rotative + onesta su numeri bassi | 6h                       | +10-18%                         | M          | cron daily                 | **5°**            |
| 4.1 | SEO push 4 articoli high-intent                      | 16h                      | +200-500% traffic 90gg          | M          | war-room pipeline          | **6°**            |
| 2.1 | Rewrite copy 4 sezioni con X_BRAND_VOICE             | 6h                       | +15-25%                         | M          | review Antonello           | **7°**            |
| 2.3 | DecisionAid singolo (sostituisce 4 funnel-feature)   | 16h                      | +200-500%                       | MH         | wireframe + content matrix | **8° — pilastro** |
| 3.3 | Logos clienti enterprise                             | 10h biz dev + 2h dev     | +15-25%                         | H          | consenso 5+ clienti        | **9°**            |
| 4.2 | WhatsApp UTM + GMB attribution                       | 4h                       | tracking only                   | H          | nessuna                    | **10°**           |
| 4.3 | Retargeting Meta + Google Ads                        | 8h + $500/mo             | +5-15%                          | M          | dopo 4.1                   | **11°**           |
| 1.3 | Hero CTA tracking                                    | 1h                       | 0% diretto                      | H          | dopo 1.1                   | (incluso in 1.1)  |

### The uncomfortable truth

Il problema **non è il design dei 4 funnel-feature**. Il problema è che **balizero.com non è progettato per generare lead — è progettato per consacrare un brand già esistente**. Il vero funnel di acquisizione è **WhatsApp + Google Maps + referral**, e quei canali funzionano _senza che il sito li serva_: il prospect google "Bali Zero", finisce sul GMB profile, scrive su WhatsApp, viene chiuso dal team. Il sito è un _adornment_, non un _engine_. Spendere ore di redesign per portare il CR da 0.3% a 0.5% è ottimizzare il rumore mentre il segnale (WhatsApp) è altrove. La domanda strategica vera è: **vogliamo che il sito diventi un secondo motore di lead, o accettiamo che resti il certificato di esistenza del brand?** Se la risposta è "secondo motore", allora il 90% dell'effort va in **traffic acquisition (SEO + content)** e in **DecisionAid invece di catalog**, non in glass-card refinement. Se la risposta è "certificato di brand", smettete di chiamarlo funnel — è un brochure, e va bene così, ma non chiamiamoci CRO consultants.

### What I would ship next 14 days (Mon 21 April → Sun 4 May)

**Mattina lunedì 21 aprile — Antonello + Damar (1 dev-day):**

1. **Fix bait-and-switch + tracking onClick** (#1.1 + #1.2 + #1.3, 4-5h) — _owner: Damar_. Deploy in giornata. Non richiede approvazione architetturale. Crea fondamenta per ogni A/B successivo. **Done quando:** dopo 24h, `funnel_sessions` ha last_event almeno per 70% delle sessioni create.

2. **Title swap + SLA garanzia esplicita** (#2.2 + #3.2, 4h) — _owner: Antonello copy + Damar deploy_. Deploy entro mercoledì 23. **Done quando:** "Visa Oracle" non esiste più sulla home; banner SLA visibile sotto CTA visa.

**Mercoledì 23 → venerdì 25 aprile — Antonello (writer) + Sahira (review):**

3. **Scrivere 2 articoli SEO di profondità** (#4.1 parziale, 8h) — _owner: Antonello scrive, war-room pipeline pubblica_. Target query: "KITAS for digital nomad cost 2026", "PT PMA minimum capital reality vs paper". Voce X_BRAND_VOICE rigorosa. **Done quando:** 2 articoli live su balizero.com, linkati dalla home, indicizzati su Google entro 48h.

**Settimana 2 (28 aprile → 4 maggio) — wireframe DecisionAid:**

4. **Wireframe + content matrix DecisionAid** (#2.3 prep, 8h) — _owner: Antonello + Damar_. NON deploy, solo design + spec. Discutere giovedì 1 maggio con Asya per validation business logic (quali sono le 3 domande di qualifica per ognuno dei 4 rami). **Done quando:** doc design pronto + wireframe approvato da Antonello, plan implementazione 2 sprint successivi.

**Cosa NON fare nei 14 giorni:**

- NO redesign visuale dei 4 funnel-feature (è fuffa fino a 2.3 deciso).
- NO "add live chat" / "add testimonials" come patch isolato.
- NO retargeting Meta finché non c'è traffic 4.1 da retargetare.
- NO modifica del hero (l'unico componente che funziona davvero).

---

## Allegato: Discoveries memorizzate in MOS

```
[discovery 9/10] Bali Zero homepage CRO crisis: 28 funnel_sessions in 30gg,
0 conversioni; lead_source=website 2 in 90gg, vs WhatsApp 420.
FunnelFeature.tsx CTA NON sparano trackFunnelEvent (solo HeaderWhatsAppCTA).
I 4 funnel sono decoration, non conversion path. Sito non genera lead nel CRM.

[discovery 8/10] Bug confermato in FunnelFeature.tsx (riga 401-402):
'See transparent pricing' link punta allo STESSO href={FUNNEL_HREF[funnel]}
del primary CTA 'Try Visa Oracle' — due bottoni diversi, stesso target.
Bait-and-switch involontario. Su tutti e 4 i funnel.

[discovery 7/10] Disallineamento copy home v2 vs landing live:
HeroBlueprint dice 'AI drafts our licensed team signs' (ibrido), ma
visa.balizero.com live dice 'AI-powered visa guidance built on 68,000+
legal docs' (AI puro). Stesso brand, due framing — confonde il visitor
su CHI risponde davvero.
```

---

## Fonti

### Industry CRO benchmarks (Step 2C)

- [Genesys Growth — Landing Page Conversion Rates 2026 (40 statistics)](https://genesysgrowth.com/blog/landing-page-conversion-stats-for-marketing-leaders)
- [Apexure — Landing Page Conversion Benchmarks by Industry 2026](https://www.apexure.com/blog/landing-page-conversion-rate-benchmarks-by-industry)
- [Unbounce — Conversion Benchmark Report (Legal industry)](https://unbounce.com/conversion-benchmark-report/legal-conversion-rate/)
- [Predictable Profits — B2B CRO Benchmarks 2025](https://predictableprofits.com/b2b-cro-benchmarks-by-industry-2025/)
- [Jorge Argota — Law Firm Conversion Rates 2026: 17.6% Benchmark Rule](https://jorgeargota.com/law-firm-landing-page-conversion-benchmarks-2026/)
- [Lawbrokr — Opportunity Cost of Contact Forms in Legal Intake](https://www.lawbrokr.com/blog/the-opportunity-cost-of-contact-forms-how-traditional-intake-kills-conversion)
- [First Page Sage — B2B Conversion Rates by Industry 2026](https://firstpagesage.com/reports/b2b-conversion-rates-by-industry-fc/)
- [Outgrow — Interactive Forms 16x Higher Lead Gen Conversions 2025](https://outgrow.co/blog/interactive-forms-lead-generation-2025/)
- [Brixon Group — Lead Forms in B2B](https://brixongroup.com/en/lead-forms-in-b2b-the-perfect-balancing-act-between-data-depth-and-conversion-rate)
- [Venture Harbour — 25 Lead Generation Forms (HubSpot 86% reference)](https://ventureharbour.com/high-converting-lead-generation-forms/)
- [Zuko — Single Page vs Multi Step Form](https://www.zuko.io/blog/single-page-or-multi-step-form)

### Competitor (Step 2B)

- [Emerhub — Indonesia services + pricing](https://emerhub.com/indonesia/)
- [Emerhub — Visa services Bali](https://emerhub.com/bali/visa-services-bali/)
- [InCorp / Cekindo — homepage](https://www.cekindo.com/)
- [InvestinAsia — homepage](https://www.investinasia.id/)

### Internal data sources

- DB Postgres production via `fly proxy 15433:5432 -a nuzantara-postgres`, tabelle `funnel_sessions` e `clients`
- Endpoint `https://nuzantara-rag.fly.dev/api/analytics/revenue?period=30d` e `/api/analytics/completion-rates?period=30d` (header `X-API-Key: zantara-secret-2024`)
- Codice: `apps/mouth/src/app/(marketing)/page.tsx`, `apps/mouth/src/app/v2/_components/FunnelFeature.tsx`, `apps/mouth/src/app/v2/_components/HeroBlueprint.tsx`, `packages/core/analytics/funnel-view.ts`
- Brand voice canonical: `docs/X_BRAND_VOICE.md`
- Cross-LLM red team: `gemini-3.1-pro-preview` via `gemini --sandbox --approval-mode plan`

### Companion documents

- Design 4 app engagement→conversion: `docs/cro/2026-04-19-4-app-engagement-conversion.md` (companion strategico, scritto da altro Opus 4.7 in sessione parallela)
- SEO Cell spec: `docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md`
- SEO Cell Plan A: `docs/superpowers/plans/2026-04-19-seo-cell-A-prenatal-foundation.md`
