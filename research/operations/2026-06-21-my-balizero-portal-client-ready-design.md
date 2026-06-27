---
date: 2026-06-21
domain: compliance
client_case: portal-readiness
sources:
  - research/operations/S11-portal-FROZEN.json (TAC portal 2026-06-03)
  - 4-LLM panel: Gemini 3.1 Pro (UX SOTA) + Codex GPT-5.5 (architettura) + DeepSeek V4 Pro (red-team) + Claude Opus (sintesi+gate)
  - Live verification: my/kita/prime.balizero.com HTTP + 3 orphan routers (401, fixed)
  - Codebase grounding: apps/mouth/src/app/portal/ (28 pagine) + apps/backend-rag/backend/services/portal/
author: claude-opus-4-8 (M5, opus-mythos)
status: design-blueprint — esecuzione gated su GO Zero
---

# my.balizero.com — Portal cliente client-ready: Design + Architettura

> **Mandato (Zero, 2026-06-21):** rendere `my.balizero.com` pronto a ospitare i clienti.
> Il portal è **luogo cliente, non operativo** — più visivo, ma anche luogo d'incontro di Bali Zero
> con i suoi clienti: docs + pratiche AI-smart con recap, e news dal nostro mondo.
>
> **Decisioni Zero (3 questions, 2026-06-21):**
> 1. Scope = **fix + redesign incrementale** (riusa ~80% già costruito)
> 2. News = **newsroom/blog esistente** proiettato come feed cliente
> 3. AI = **recap AI di documenti/pratiche** (sfrutta RAG backend esistente)

---

## §0 — Executive summary

Il portal **non parte da zero**: esistono già 28 pagine, un design system condiviso (GARUDA), e
i 3 router backend P0 (`dashboard/summary`, `family`, `notifications/prefs`) — segnalati rotti nel
FROZEN del 3 giugno — **risultano già fixati e LIVE** (verificato: rispondono 401, non 404; PR #1296).

Il vero lavoro per "client-ready" **non è tecnico-strutturale ma di INTENZIONE DI PRODOTTO**: oggi
my.balizero.com è una **proiezione del backoffice kita** (stesso AppSidebar, stessa palette, nessuna
distinzione cliente-vs-team, 28 voci di menu indifferenziate). Il panel 4-LLM converge su una tesi:

> **Un portal cliente non è un backoffice con meno permessi. È un luogo con una psicologia diversa:
> riduce l'ansia invece di massimizzare il throughput operatore.**

Il redesign incrementale ruota su **4 mosse**, in quest'ordine di impatto:
1. **Surface identity** — dare al portal un'identità visiva calma e distinta da kita (theming `data-surface`)
2. **"Your Turn / Our Turn"** — il pattern UX singolo più importante: ogni pratica dichiara chi ha la palla
3. **AI recap source-bound** — riassunti sicuri (evidence-gated, abstain, disclaimer), MAI free-summary
4. **Gerarchia brutale** — 4 pagine core in evidenza, le altre 24 in progressive disclosure

---

## §1 — Cosa è ORA il portal (e il suo specchio kita)

### my.balizero.com — `apps/mouth/src/app/portal/`
- 28 pagine cliente, Next.js App Router (mouth v5.2.0), deploy Vercel.
- **Pagine ricche** (riuso alto): dashboard (hero passport/visa + case manager), visa, company/[id]
  (layout editoriale), vault (CRUD documenti completo), process (timeline + checklist documenti).
- **Pagine thin/stub**: companies (lista), taxes, billing, lkpm, messages.
- **Login**: 2-step email→PIN, `login-upgraded` (cinematic, Candi Bentar SVG, framer-motion),
  "PRIVATE CLIENT PORTAL". Recovery via forgot-password (NON SMS-2FA → già evita un'anti-pattern).
- **Design system GARUDA** (`globals.css:242-313`): base `#0f1419`, accent-warm `#c9a96e` (oro
  sabbia), accent `#d4845a` (terracotta), testo `#edeae4`. Dark "warm anthracite". Glass cards.
- **Componenti riusabili** (40+): StatusBadge, ProcessStepper, CountdownChip, PortalHeader,
  PortalBottomNav (mobile 4-tab), vault/* (6), process/* (8), company/* (10), settings/* (6).

### kita.balizero.com — `apps/mouth/src/app/(workspace)/` (lo "specchio grande")
- 19 sezioni operative team: clients, process, hr, inbox, intelligence, omnichannel, revenue,
  whatsapp, terminal, analytics, review, partners, lkpm, settings, team…
- È il backoffice pieno: griglie dense, code, SLA, assigned-agent, confidence-score.

### La relazione (load-bearing)
Stesso codebase, stesso `AppSidebar`, stessa palette. **Oggi il portal riusa l'app-shell del
backoffice** (`portal/(authenticated)/layout.tsx` importa `AppSidebar` da `@/components/workspace/`
con `isPortal={true}`, ma senza differenza visiva reale). Il portal eredita la *densità operativa*
di kita — è il problema-radice da curare.

---

## §2 — Sintesi research 4-LLM (giugno 2026)

### Convergenze (Gemini + Codex, alta confidenza)
- **Digital Concierge, non dashboard.** I migliori portal 2026 (Mercury, Deel/Atlas, Linear, Attio)
  in settori high-trust/high-anxiety sono "concierge digitali": calma editoriale + efficienza fintech.
- **"Your Turn / Our Turn"** (Gemini) = il pattern singolo più importante per portal legali. Ogni
  pratica dichiara esplicitamente chi tiene la palla: *Your Turn* (accent vibrante, azione richiesta)
  vs *Our Turn* (colori muti, "stiamo lavorando", il cliente si rilassa).
- **Subway-map progress, non % bar** (Gemini). I processi legali non sono lineari; nodi-milestone con
  micro-step interni evitano il "feeling stuck".
- **AI come Summary Layer invisibile** (Gemini) + **typed recap contract** (Codex): recap come oggetti
  strutturati (summary + nextClientAction + blockers + evidence[] + confidence + disclaimer), NON chat.
- **Shared design foundation, distinct shell** (Codex): riusa token/tipografia/primitive UI, MA shell,
  sidebar e label diverse. Theming semantico via `:root[data-surface="portal"]`.
- **News interleaved, non in tab separata** (Gemini): editorial feed come rail laterale contestuale al
  caso del cliente. **Content manifest da MDX esistente** (Codex), filtrato server-side per
  servizi/pratiche attive del cliente — niente secondo CMS, niente LLM nel request-path.
- **RSC-first** (Codex): server components per le viste dati autenticate, client-island solo per
  interazione. Mobile-primary (i clienti usano il telefono).

### Il refuter (DeepSeek) — gli attacchi che cambiano il design
DeepSeek **contraddice** parzialmente Gemini — ed è il contributo più prezioso:
- **AP1 "Dead Portal"**: un portal che è un archivio passivo viene ignorato. Il driver di ritorno NON
  è l'estetica né le news: è la **hard dependency** — un'azione tracciata con conseguenza temuta
  ("conferma indirizzo entro venerdì o la KITAS non viene stampata"). → rafforza "Your Turn".
- **AP2 "WhatsApp wedge"**: il cliente è addestrato a chiedere su WhatsApp e avere risposta umana in
  60s. Il portal perde se duplica WhatsApp. → il portal deve **possedere il record definitivo**:
  notifiche WA con deeplink "azione richiesta — solo sul portal", MAI allegare documenti sensibili in chat.
- **AP3 "Hallucinated Lawyer"** (il più critico): un recap AI che inventa una scadenza visa →
  overstay → deportazione → causa legale. **Guardrail non-negoziabili**: source-gate solo su campi
  strutturati audited (status enum, deadline con sorgente human-verified), MAI free-summary da case
  notes; confidence stamp + disclaimer permanente; log immutabile dei data-point usati + bottone
  "report inaccuracy" che mette in pausa l'AI per quel caso; MAI inferire stato finanziario/proprietà.
- **AP4 "28-page graveyard"**: il cliente usa 4 pagine, le altre 24 sono rumore che dice "non è per me".
  Le 4 che trattengono: (1) azione+scadenza, (2) timeline pratica, (3) upload documento one-tap mobile,
  (4) messaggi in-portal. News, community, gamification = vanity (la gamification su una residenza a
  rischio è *insultante*).
- **AP5 "Document graveyard"**: gestire passaporto/KTP/NPWP/akta è un contratto di fiducia. Distruttori
  istantanei: upload senza feedback di cifratura, nessuna visibilità su chi-vede-cosa (access-log),
  delete senza conferma/recovery, allegati email non cifrati, richiesta documenti senza spiegare
  *perché* + retention policy. (Verificato: il vault attuale NON mostra access-log/encryption → gap.)
- **AP6 "Login purgatory"**: expat perde SIM → SMS-2FA morto. (Già mitigato: login è email→PIN, non
  SMS.) Aggiungere biometria mobile + magic-link resiliente a Wi-Fi lento.
- **AP7 "Black-box status"**: "in process" per settimane = "non succede nulla / mi nascondono qualcosa".
  Serve event-log timestampato ("ricevuto da immigrazione il 14 feb 10:32") + spiegazione ritardi
  ("coda immigrazione ~7 giorni lavorativi").

### Risoluzione del conflitto news (Zero-vuole ⟷ DeepSeek-furniture)
Zero vuole le news; DeepSeek dice che non sono il motore di ritorno. **Entrambi hanno ragione su assi
diversi**: le news vanno incluse (mandato) ma come **contesto secondario contestuale**, MAI come hero
o landing. L'interleaving di Gemini (rail laterale filtrato sul caso) soddisfa entrambi.

---

## §3 — DESIGN del portal client-ready

### 3.1 Principio guida
> **Il portal risponde a UNA domanda nel cervello del cliente: "cosa devo assolutamente fare ORA
> perché la mia vita non si complichi?"** Tutto il resto è contesto. Se il portal non è la risposta,
> lo è WhatsApp.

### 3.2 Identità visiva — "Tactile Editorial", distinta da kita
- **Theming semantico**: `:root[data-surface="portal"]` con palette **più calma e luminosa** di kita.
  Opzione raccomandata: attivare il light theme "Rumah Putih" già presente in `globals.css:799-1061`
  (carta calda `#f7f6f2`, ink `#16213a`) per il portal, lasciando kita dark. Il cliente entra in uno
  spazio "lounge", non in una sala-macchine. (Decisione finale dark-vs-light → §Solo-operatore.)
- **Split tipografico** (Gemini): serif editoriale (es. Newsreader) per contenuti narrativi (welcome,
  recap AI, news) + sans (Inter, già in uso) per dati/status/numeri. Delinea "leggere" da "gestire".
- **Motion "settling"**: ease-in/out 300-400ms, niente bounce. Trasmette peso e permanenza.

### 3.3 Information architecture — gerarchia brutale (cura AP4)
**Tier 1 — sempre visibile (le 4 che trattengono):**
1. **Today / Next Action** — il blocco "Your Turn": azione richiesta + scadenza + conseguenza.
2. **Le mie pratiche** — timeline subway-map per visa/company/tax/property con stato Your/Our Turn.
3. **Documenti** — upload one-tap mobile (auto-crop), con feedback cifratura + access-log + purpose.
4. **Messaggi** — thread in-portal, ancorati all'oggetto (pratica/documento), non global inbox.

**Tier 2 — progressive disclosure (le altre, accessibili ma non urlate):**
companies/company detail, billing/invoices, family/dependenti, taxes, lkpm, partner, settings, profile.

**Tier 3 — contesto laterale (non nel menu principale):**
- **The Bali Zero Dispatch** — rail editoriale filtrato sul caso del cliente (news dal nostro mondo).

### 3.4 "Your Turn / Our Turn" — il pattern centrale (cura AP1, AP7)
Ogni pratica e ogni documento dichiara lo stato del testimone:
- **Your Turn** → accent vibrante, CTA chiara, conseguenza esplicita. È la hard-dependency che fa
  tornare il cliente.
- **Our Turn** → colori muti, "Bali Zero sta lavorando", event-log timestampato dell'ultima attività.
- Mai "in process 60%" senza dire *cosa* manca al 100% e *chi* tiene la palla.

### 3.5 AI recap — source-bound, mai hallucinated lawyer (cura AP3)
Recap come **oggetto strutturato** mostrato accanto a pratica/documento, MAI testo libero da case notes:
- Solo da campi strutturati audited (status enum, deadline human-verified).
- `confidence: normal | cautious | abstain` — se la sorgente è ambigua, **astiene** (non rassicura falsamente).
- Evidence-binding: ogni claim materiale linka il record sorgente (+ updatedAt).
- Disclaimer permanente: "Riepilogo generato da AI sui dati Bali Zero — non è consulenza legale.
  Conferma sempre con il tuo case officer."
- Bottone "segnala imprecisione" che **mette in pausa l'AI per quel caso** finché un umano rivede.
- MAI inferire stato finanziario/proprietà.

### 3.6 Trust UX sui documenti (cura AP5)
- Upload con indicatore cifratura visibile + virus-scan ack.
- Access-log per documento (chi/quando ha visto) + matrice permessi (View/Download/Share).
- Delete con conferma + cestino/recovery.
- "Purpose statement" prima dell'upload ("Richiesto per registrazione fiscale; cifrato, cancellato
  90gg dopo chiusura caso").
- Watermark sul viewer.

### 3.7 Il portal possiede il record (cura AP2)
- Notifiche WhatsApp/email = **deeplink al portal**, non contenuto duplicato; mai documenti in allegato chat.
- Ogni update dato dall'agente in chat si riflette timestampato nell'audit-trail del portal.

---

## §4 — ARCHITETTURA

### 4.1 Shell separata, fondazione condivisa
```
apps/mouth/src/app/
  layout.tsx              # root minimale: html, font, providers globali
  (workspace)/layout.tsx  # shell kita (admin, dark, denso)
  portal/layout.tsx       # shell my (cliente, calmo, data-surface="portal")
```
- Riusa: token, scala tipografica, Button/Input/Badge/Avatar/Toast/Dialog/Skeleton/EmptyState.
- Riusa con cautela: card, status-pill, document-row, timeline-primitive.
- **NON riusare**: AppSidebar admin, tabelle dense, command palette, inbox interno, widget operativi.
- Theming: `:root[data-surface="portal"]` vs `="workspace"` (Codex pattern). Sostituire l'attuale
  `AppSidebar` riusato con una nav portal dedicata (Tier-1 prominente).

### 4.2 AI recap — pipeline server-bound
```
RSC page / server action
  -> portal BFF (Next.js)
  -> backend-rag endpoint autenticato (riusa agentic_rag.py + portal services con summary)
  -> RAG retrieval + validator deterministici
  -> recap strutturato PERSISTITO (tabella backend, non solo cache Next.js)
  -> render nel portal
```
- **Contratto tipato** `PracticeRecap` (clientId, practiceId, scope, summary, nextClientAction,
  blockers[], evidence[], confidence, generatedAt, sourceVersion, disclaimer).
- **Cache versionata, non solo TTL**: key = `clientId+practiceId+sourceVersion+promptVersion+modelVersion+locale`.
  `sourceVersion` da max(updated_at) / checksum documenti / versione pratica CRM.
- Invalidazione a tag dopo upload/CRM-update/note/cambio-stato: `client:{id}:portal`, `practice:{id}:recap`.
- **Cost control**: pre-generazione batch notturna per clienti attivi; rigenerazione event-driven solo
  su cambio sourceVersion; modello piccolo per estrazione, grande per sintesi; mai rigenerare a ogni page-view.
- **PII boundary (Law 2)**: il recap tocca dati cliente → processing **locale** (Ollama) o backend-Fly
  autenticato, MAI prompt PII verso LLM cloud nei path di sviluppo/test. Riuso esistente: `agentic_rag.py`.

### 4.3 News feed — manifest MDX, zero secondo CMS
- Frontmatter articoli: `tags`, `clientStages`, `jurisdictions`, `services`, `urgency`, `evergreen`.
- Build-time: genera content-manifest dal newsroom MDX esistente.
- Request-time: server component filtra il manifest sui servizi/pratiche attive del cliente
  (deterministico, NO LLM nel request-path). Microcopy "perché vedi questo" basato su tag.
- Public article = static + cache globale; ranking di rilevanza = server-side post-auth.

### 4.4 Next.js patterns
- RSC default per viste autenticate; client-island per tabs/filtri/upload/optimistic.
- `loading.tsx` route-level + `Suspense` panel-level (status/docs/recap/news in streaming indipendente).
- Server Actions per azioni documenti / read-state / refresh recap; `revalidateTag` post-mutazione.
- Mobile-primary: bottom-nav (già esiste), touch target larghi, single-column, CTA next-action sticky,
  upload tollerante a rete instabile, biometria + magic-link resiliente (cura AP6).
- Optimistic OK per "mark read"/"save pref"/"upload started"; lo stato legale finale riconcilia sempre col server.

### 4.5 Metriche dal day-1 (la metrica che conta, DeepSeek)
- **% clienti che completano l'azione settimanale richiesta nel portal** (target >60% a 3 mesi).
- Recap cache hit-rate, recap age, abstention rate, validator failure reasons.
- Mobile LCP/INP per route, document upload failure rate, news CTR per tag.

---

## §5 — META-PATTERN (il vero topic)

> **La malattia-delle-malattie: il portal cliente è stato costruito come PROIEZIONE del backoffice,
> non come LUOGO con una psicologia propria.**

Tre evidenze trasversali:
1. **Struttura**: il portal importa `AppSidebar` da `@/components/workspace/` — eredita la shell admin.
2. **Visivo**: nessuna distinzione palette/tipografia cliente-vs-team; stesso GARUDA dark denso.
3. **IA**: 28 voci di menu indifferenziate (densità operatore) invece di 4-core + progressive disclosure
   (calma cliente).

È la versione "prodotto" del meta-pattern d'organismo **"Esiste ≠ Armato"** (superscar #2): il portal
*esiste* (28 pagine, router live) ma non è *armato come prodotto cliente* — manca l'intenzione di
prodotto che lo distingue dal backoffice. Il fix non è aggiungere feature; è **sottrarre densità e
aggiungere identità**.

Contromisura strutturale: un **lint/check "surface-fitness"** — il portal non deve importare componenti
da `components/workspace/` marcati admin-only; un test che il portal layout usi `data-surface="portal"`.

---

## §6 — TERAPIA: piano di esecuzione (incrementale, fix→redesign)

> Ordine per impatto/rischio. Ogni fase = PR atomica, worktree isolato, verifica live post-merge.

**FASE 0 — verifica baseline (FATTA in questa sessione):**
- ✅ 3 router orphan già fixati e live (401, non 404).
- ✅ Inventario riuso (40+ componenti) mappato.

**FASE 1 — Surface identity (alto impatto, basso rischio):**
- Nav portal dedicata (sostituisce AppSidebar admin riusato) con IA Tier-1/2/3.
- Theming `data-surface="portal"` (decisione dark-vs-Rumah-Putih → Zero).
- Split tipografico serif/sans.

**FASE 2 — "Your Turn / Our Turn" + subway-map (il cuore):**
- Componente `PracticeBaton` (Your/Our Turn) su dashboard + ogni pratica.
- Subway-map progress (estende ProcessStepper esistente).
- Event-log timestampato (cura AP7).

**FASE 3 — AI recap source-bound:**
- Servizio backend `practice_recap` (riusa agentic_rag + portal summary services) con contratto tipato,
  confidence/abstain, evidence-binding, cache versionata, disclaimer, "report inaccuracy".
- Render recap-card accanto a pratica/documento.

**FASE 4 — News feed contestuale:**
- Content-manifest da newsroom MDX + frontmatter esteso + rail "Bali Zero Dispatch" filtrato.

**FASE 5 — Trust UX documenti:**
- Vault: indicatore cifratura, access-log, purpose-statement, delete-con-recovery, watermark.

**FASE 6 — Hardening login mobile:**
- Biometria + magic-link resiliente Wi-Fi lento (cura AP6).

---

## §7 — SOLO-OPERATORE (confine, decisioni Zero)

1. **Dark vs Rumah-Putih (light) per il portal** — decisione estetica/brand di Zero. Raccomando light
   "carta calda" per la sensazione lounge cliente, ma è prerogativa tua.
2. **Ordine/scope delle 6 fasi** — quante shippare per il "go-live clienti". Raccomando FASE 1+2+3
   come MVP client-ready (identità + Your/Our Turn + recap), poi 4+5+6.
3. **AI recap = PII cliente** → conferma GO prima di cablare qualsiasi pipeline che tocca dati cliente
   (Law 2: processing locale/Fly-auth, mai cloud cleartext).
4. **Onboarding nuovi clienti** — il portal non ha walkthrough empty-state per il primo accesso; vale
   un mini-flow? (decisione prodotto).
5. **Metrica nord** — confermi "% azione settimanale completata nel portal >60%@3mesi" come KPI?

---

## Appendice — fonti panel
- Gemini 3.1 Pro: SOTA portal UX 2026 (Mercury/Deel/Linear/Attio, Tactile Editorial, Your/Our Turn,
  subway-map, AI Summary Layer, editorial interleaving).
- Codex GPT-5.5: architettura (shared foundation + data-surface, typed PracticeRecap, cache versionata,
  content-manifest MDX, RSC-first, metriche).
- DeepSeek V4 Pro: red-team 7 anti-pattern (dead portal, WhatsApp wedge, hallucinated lawyer, feature
  graveyard, document graveyard, login purgatory, black-box status).
- Claude Opus: sintesi + gate scettico (risoluzione conflitto news, verifica live router, grounding codebase).
