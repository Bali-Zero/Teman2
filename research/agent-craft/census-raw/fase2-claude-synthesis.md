---
date: 2026-06-02
phase: FASE 2 — Claude synthesis of adversarially-verified SOTA findings
scope: agentic SOTA 2026, calibrated on real Nuzantara problems
inputs: 2 fully-detailed areas (browser-agents, predictive) from deep-research, adversarially verified
confidence_legend: HIGH = primary-source verbatim + repo-confirmed this turn; MED = real technique, citation/number caveat; LOW = plausible/unmeasured estimate
discipline: only verified facts retained — vendor marketing numbers and mis-pinned source claims explicitly flagged or dropped
---

# FASE 2 — Sintesi SOTA agentico 2026 × Nuzantara

> Nota di metodo: i findings in input coprono in profondità **2 aree** (browser-agents, predictive). Le sintetizzo integralmente con i caveat adversarial già emersi. Le altre 11 aree promesse dal titolo del task **non sono presenti nel payload**; non le invento (anti-hallucination, regola #1). La sezione TOP 8 è quindi costruita sulle opportunità realmente fondate dalle 2 aree verificate, decomposte per impatto×fattibilità.

---

## AREA 1 — Browser Agents (computer-use / gov-portal automation)

### SOTA findings chiave (verificati)

1. **Computer-use ha raggiunto la parità umana su OSWorld, e Anthropic è leader.** OSWorld-Verified (rilasciato 2026-02-17): Claude Sonnet 4.6 = 72.5%, Opus 4.6 = 72.7%, baseline umano ~72%, GPT-5.2 = 38.2% (Sonnet quasi raddoppia GPT-5.2). _Confidenza: HIGH sui numeri Anthropic (system card + news post); MED sul numero esatto GPT-5.2, corroborato da aggregatori non da una singola fonte primaria._

2. **Il vero collo di bottiglia è WRITE, non READ — gap ~28 punti.** Web Bench (Halluminate+Skyvern, ~5.750 task / 500+ siti): il miglior agente **fully-automated** arriva solo al **46,6% su task WRITE** (login, form-fill, file ops, 2FA) contro **>75% su task READ/extract**. Blocchi confermati: auth, CAPTCHA, traiettorie lunghe, long-context. _Confidenza: HIGH sul gap READ/WRITE; il sub-numero "66% all-tasks CUA leads" è MED (non riconfermato verbatim)._

3. **La verticalizzazione stretta sfonda il floor del 46,6%.** Claude Sonnet 4.6 ha fatto **94%** su un benchmark reale assicurativo (Pace): form web multi-step + spreadsheet + app desktop legacy, end-to-end, senza API custom. Conferma empirica che **narrow-vertical batte il generico**. _Confidenza: HIGH._

4. **Lo stealth JS (StealthPlugin) è strutturalmente obsoleto per il 2026.** Le patch JS user-space non possono nascondere il fingerprinting del protocollo CDP, non sistemano TLS/JA3-JA4, né reputazione IP/ASN. SOTA 2026 = driver direct-CDP (nodriver/patchright) + profili persistenti + IP residenziale. _Confidenza: HIGH (convergenza multi-fonte indipendente)._ **Corollario chiave: per i portali governativi first-party — che NON hanno WAF anti-bot aggressivi — lo stealth è semplicemente lo strumento sbagliato; serve un profilo autenticato persistente.**

5. **Pattern di produzione 2026 per portali regolati/gov: human-in-the-loop obbligatorio + self-correction loop.** Anthropic Agent SDK (verbatim): "Agents that can check and improve their own output are fundamentally more reliable—they catch mistakes before they compound, self-correct when they drift". HITL + notifica-a-umano-su-fallimento + demos/traiettorie apprese per resilienza a UI-drift. _Confidenza: HIGH sul pattern; la sub-clausola "Managed Agents in sandbox customer-controlled" era mis-citata → scartata._

### Fit-Nuzantara (verificato in repo questo turn)

- `packages/browser-core/browser_core/stealth.py` **confermato riga-per-riga**: le 5 patch del profilo 2026-obsoleto ci sono esattamente (webdriver, chrome.runtime, navigator/plugins/languages, permissions, canvas-noise).
- MCP `nuzantara-browser` presente, skill `browser` presente. Stack = **read/scrape + deploy-QA**.
- **GAP confermato empiricamente**: grep per form-fill Playwright (`.fill`/`.type`) su qualsiasi portale gov (oss/pajak/ahu/evisa/imigrasi/lkpm/nib/spt) = **ZERO match** in `apps/`. I 38 file che citano oss.go.id/pajak.go.id/ahu.go.id sono **liste di domini per READ-scraping intel** (`apps/bali-intel-scraper`), NON form-filling.
- `scripts/federation_orchestrator.py` grep checkpointer/PostgresSaver/MemorySaver = **EMPTY** → il self-correction loop è strutturalmente assente (coerente con MOS p2_19).

**Verdetto fit:** Nuzantara siede esattamente nel quadrante difficile (46,6% write-heavy + auth/CAPTCHA) con **zero agente costruito**, mentre **possiede già gli asset del lato READ** (dati CRM, OCR qwen2.5vl) che l'evidenza (75%+ read-accuracy, 94% vertical-narrow) indica come ingredienti vincenti per un copilot draft-fill.

### Opportunità + ROI

**Gov-Portal Copilot (assistito, NON autonomo)** sui 5 portali core indonesiani (OSS/BKPM, evisa imigrasi, DJP/coretax, AHU, LKPM):
- **Pattern**: DRAFT-FILL human-in-the-loop — Claude/Gemini-CU pre-compila da CRM+Drive-OCR, l'operatore clicca submit. Sfrutta il 75%+ read-accuracy verificato e **aggira** il floor 46,6% write.
- **Mappa pulita su Symbiosis Law 5** (propose-not-decide): il gate umano elimina il rischio di submission errata — questa è la parte **strutturalmente più solida** dell'argomento.
- **Scope narrow per portale** (replica il 94% assicurativo verificato), **abbandona stealth.py** per i gov-portal (profili autenticati persistenti), **chiudi il self-correction loop** (aggiungi checkpointer a federation_orchestrator — prerequisito repo-confermato mancante).
- **Costo marginale ~zero** (Claude MAX OAuth + Gemini AI Ultra già pagati, nessuna API metered — coerente con la hard-rule no-paid-API). _Confidenza: HIGH._
- **ROI ore-uomo** ("centinaia ore/mese", "60% pratiche standard"): _Confidenza LOW — stime non riderivate questo turn._ Trattare come ordine di grandezza, NON misurato.
- **Pilot raccomandato**: 1 portale (evisa renewal — il più ripetitivo) × 10 pratiche reali in shadow-mode con operatore, **dopo** il fix checkpointer, con baseline misurata (minuti-operatore reali/pratica) prima di impegnarsi sui numeri ROI.

---

## AREA 2 — Predictive (churn / upsell / deadline-sentinel)

### SOTA findings chiave (verificati)

1. **Su churn tabellare il SOTA produzione 2026 è gradient-boosting, NON gli LLM.** Verbatim: XGBoost AUC-ROC 0.932, LightGBM 0.930, GradientBoosting 0.926; soft-voting ensemble F1 0.84. Pipeline: SMOTE post-split, StandardScaler, Optuna 5-fold, isotonic calibration, threshold 0.528, cost-sensitive C_FN=5/C_FP=1. _Confidenza: HIGH sui numeri. **Correzione fonte**: il paper è Frontiers in AI (DOI 10.3389/frai.2026.1748799 = PMC12929532), NON Scientific Reports/nature — citazione di rivista errata nel finding originale, da non propagare._

2. **L'explainability (SHAP TreeExplainer) è parte del SOTA, non solo accuracy.** Top feature per |SHAP|: contract_type 0.284, tenure 0.198 (rischio crolla dopo ~24 mesi). Pattern actionable: "electronic check" ~45% churn vs auto-pay 18-20% → azione = migrazione a auto-pay. _Confidenza: HIGH sul pattern; un singolo numero (monthly_charges) incerto, ranking regge._

3. **L'uplift modeling è il salto su upsell/retention.** Stima l'effetto causale incrementale del trattamento (CATE per-cliente), non la propensity. `causalml` (Uber) confermato; arXiv 2308.09066 (Booking.com, CIKM'23) confermato. Terminologia "sleeping dogs"/"lost causes" standard → evita spam ai clienti che si convertirebbero comunque. _Confidenza: HIGH._

4. **Deadline-sentinel proattivo 2026 = telemetria/event-driven + escalation con context-summary, NON cadenza calendario.** Verbatim (temporal.io): durable execution, workflow stateful "unlimited duration", signals/timers per HITL ("wait up to 24 hours for approval"), auto-save state. _Confidenza: HIGH sull'ancora tecnica Temporal; i blog vendor parloa/mindstudio sono peso probatorio basso._

5. **Architettura agente Anthropic orchestrator-worker** (verbatim): "a central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results". Managed Agents: sandboxed exec + checkpointing (append-only session log) + credential scoping. _Confidenza: HIGH sulle primitive; 2 esempi colorati ("daily business review", "tens-to-hundreds agents") erano mis-pinnati → scartati._

> **Numeri vendor da depennare (NON propagare)**: Agentforce "18.500 clienti" = in realtà 18.500 **deal/use-case** (~9.500 paganti); HubSpot "4x-7x" e "279K clienti" non trovati (reale ~2x response rate); riduzione churn "10-25%" = marketing, non studio indipendente. La tesi direzionale (reattivo→proattivo) regge; i numeri no.

### Fit-Nuzantara (confermato via lettura diretta questo turn)

- **ClientValuePredictor è una somma pesata HARDCODED**, non ML: `client_scoring.py` → `ltv_score = engagement*0.3 + sentiment*0.2 + recency*0.2 + quality*0.2 + practice*0.1`, ogni componente = `min(count*K,100)`. **ZERO training, ZERO label churn, ZERO XGBoost/SHAP.**
- Risk-level (`client_segmentation.py:calculate_risk`) = **if/else a 4 rami** con costanti hardcoded. Gap vs SOTA **abissale, confermato**.
- **Deadline-sentinel esiste MA è BLOCCATO**: `cron_notifiers.py:56-60` legge flag DB `visa_expiry_notifier_enabled` e logga "BLOCKED — awaiting owner approval" (verbatim). LKPM deadline presente. Coerente con Law 5.
- **Scheduling gap confermato**: `client-value-predictor` è in `config/job-ownership.yaml:58` MA `run_daily_nurturing` compare SOLO in 2 file di test — **ZERO cron/scheduler reale**. Identico al fallimento auto-improvement di FASE 1.
- **Asset ML**: scikit-learn 1.8.0 nel `.venv`; **lightgbm/xgboost/shap/causalml TUTTI ASSENTI**. 11.699 clienti CRM corroborato da 2 doc audit.

### Opportunità + ROI

- **OPP-A (deadline-sentinel visa/KITAS)** — _Confidenza ALTA._ Codice già scritto, BLOCKED solo da flag DB. Basta `true` + cron reale + review-gate Telegram (Law 5). Per agenzia immigration il KITAS scaduto = perdita cliente + multa overstay = **IL** revenue-protection event. **ROI ALTISSIMO a costo ~zero**, ~2-3gg.
- **OPP-B (churn-model gradient-boosting)** — _Confidenza ALTA su tecnica, MED su data-readiness._ Sostituisce le 5 costanti a naso con AUC backtestabile. Baseline a costo zero con `GradientBoostingClassifier` (sklearn 1.8.0 già presente); LightGBM da installare per il salto. SHAP per il "perché" per-cliente. **CAVEAT**: serve verificare che esista una label di churn estraibile (pratica non-rinnovata) prima di promettere AUC 0.93 — il 0.93 è su telco pulito, non garantito sul CRM Bali Zero. ~2-3 settimane.
- **OPP-C (upsell-agent uplift)** — _Confidenza MED._ causalml (da installare); clienti visa-only = target cross-sell PT-PMA/tax/property; uplift evita spam ai "sleeping dogs". DOPO OPP-B, dietro review umana. Richiede dati di trattamento storici (campagne con outcome) da verificare esistano. ~1 mese.
- **NOTA TRASVERSALE (ALTA)**: cablare PRIMA lo scheduler — senza, qualunque modello resta un endpoint mai chiamato.

---

## TOP 8 OPPORTUNITÀ (rankate per impatto × fattibilità)

> Ranking = impatto-business × fattibilità-tecnica, penalizzando le opportunità con confidenza-dati bassa o dipendenze non verificate. Le prime alimentano la FASE 3 game-changer.

| # | Opportunità | Impatto | Fattibilità | Confidenza | Effort | Note load-bearing |
|---|---|---|---|---|---|---|
| **1** | **Sbloccare deadline-sentinel visa/KITAS** (flag DB → true + cron reale + gate Telegram) | ALTISSIMO | ALTISSIMA | ALTA | ~2-3gg | Codice GIÀ scritto e BLOCKED (`cron_notifiers.py:60`). Revenue-protection event diretto per agenzia immigration. Costo ~zero. **Quick win #1.** |
| **2** | **Cablare lo scheduler reale per i predictor** (`run_daily_nurturing` oggi solo nei test) | ALTO | ALTA | ALTA | ~1-2gg | Prerequisito strutturale: senza, ogni modello è un endpoint mai chiamato. Sblocca OPP #1 e #5. Replica il fix del fallimento auto-improvement FASE 1. |
| **3** | **Chiudere il self-correction loop** (checkpointer PostgresSaver in `federation_orchestrator.py`) | ALTO | ALTA | ALTA | ~2-3gg | Repo-confermato EMPTY. Anthropic verbatim: self-correction = leva di affidabilità #1. **Prerequisito** del Gov-Portal Copilot e di ogni agente che deve imparare dai fallimenti. |
| **4** | **Gov-Portal Copilot draft-fill HITL — pilot evisa renewal** (1 portale × 10 pratiche shadow-mode) | ALTISSIMO | MEDIA | ALTA (direzione) / LOW (ROI €) | ~2-4 sett. | Sfrutta 75%+ read-accuracy, aggira 46,6% write-floor, replica 94% narrow-vertical, mappa su Law 5. **Dopo #3.** Misurare baseline operatore prima di promettere ROI. **Game-changer candidate.** |
| **5** | **Churn-model gradient-boosting + SHAP** (sostituisce somma pesata hardcoded) | ALTO | MEDIA | ALTA tecnica / MED dati | ~2-3 sett. | Baseline costo-zero con sklearn 1.8.0 già presente; LightGBM da installare. **Gate**: verificare label churn estraibile prima di promettere AUC. SHAP dà il "perché" per-cliente. |
| **6** | **Abbandonare stealth.py per i gov-portal → profili autenticati persistenti** | MEDIO | ALTA | ALTA | ~1 sett. | Le 5 patch JS sono strutturalmente obsolete 2026; per portali first-party (no WAF) sono lo strumento sbagliato. Abilitatore tecnico di #4. Riduce fragilità. |
| **7** | **Upsell-agent con uplift modeling** (causalml; visa-only → cross-sell PT-PMA/tax/property) | MEDIO-ALTO | MEDIA | MED | ~1 mese | Differenziante. **Dopo #5.** Richiede dati di trattamento storici (campagne con outcome) da verificare. Evita spam ai "sleeping dogs". |
| **8** | **Deadline-sentinel event-driven durable** (da cadenza-calendario a telemetria + escalation context-summary, stile Temporal) | MEDIO | MEDIA | MED | ~2-3 sett. | Evoluzione architetturale di #1. Workflow stateful unlimited-duration + HITL 24h. Da fare dopo che #1 prova il valore con il pattern semplice. |

### Sintesi per FASE 3

I **game-changer** più solidi sono **#4 (Gov-Portal Copilot)** e **#5 (churn-model)** — alto impatto, fondati su SOTA verificato, mappati su Law 5. Ma entrambi poggiano su **#2 (scheduler)** e **#3 (checkpointer)** come prerequisiti strutturali a basso costo/alta-fattibilità. **#1 (deadline-sentinel KITAS)** è il quick-win immediato a ROI sproporzionato. Pattern ricorrente confermato da entrambe le aree: **Nuzantara possiede gli asset (CRM 11.699, OCR, dati read-side) ma non ha cablato la pipeline che li attiva** — il valore è nello sblocco/cablaggio, non in nuove acquisizioni.

### Avvertenze trasversali (anti-hype)

- **ROI in €/ore**: tutti LOW-confidence finché non si misura una baseline operatore reale.
- **AUC 0.93**: è su dataset telco pulito; il CRM Bali Zero richiede prima verifica di una label di churn estraibile.
- **Numeri vendor** (Agentforce/HubSpot/Salesforce): depennati, non usare in FASE 3.
- **11 aree mancanti**: il payload conteneva solo 2 aree dettagliate; le altre non sono state inventate.
