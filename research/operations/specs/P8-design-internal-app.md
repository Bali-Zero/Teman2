# PEZZO 8 — DESIGN / INTERNAL-APP: agente genera UI dentro il brand (app vs vista)

> **Spec studio (non implementazione).** Ciclo FULL-COUNCIL: reuse-first (disk-state VERIFICATO) +
> council 3-LLM (Gemini red-team / Codex constructive / DeepSeek logic). Pezzo 8 di 9. Buco #2
> ("APERTO, alta incertezza") → full-council giustificato.
>
> **Criterio-cardine (DeepSeek)**: la maggior parte dei bisogni interni NON dovrebbe diventare
> un'**app** (codice permanente da mantenere) ma una **vista** (query/report effimera, zero
> manutenzione). Si merita un'app **solo se** serve mutazione-di-stato o interattività-complessa.
> Questo disinnesca il difetto FATALE del red-team (il "cimitero del codice generato").

---

## 0. La correzione che precede tutto — APP vs VISTA, e MODULO vs APP-NUOVA

Il design iniziale ("l'agente genera internal-app") nasconde due errori che il council ha smontato e
che riformulano tutto.

### 0.1 Il difetto FATALE: generare è facile, mantenere uccide (Gemini #6, DeepSeek #1)

> Il vero collo di bottiglia di un solo-dev non è *scrivere* app, è *mantenerle*. Un agente che genera
> 10 dashboard in un mese produce 10 pezzi di codice che vanno aggiornati quando React/Tailwind/i
> token/lo schema cambiano, quando emerge una CVE. **"Il successo di questa feature ucciderebbe il
> progetto per asfissia ingegneristica."** Il design conta l'utilità (Day 0) e condanna il dev alla
> paralisi di manutenzione (Day 2).

**Risoluzione (DeepSeek)** — il criterio app-vs-vista:

| | **VISTA** | **APP** |
|---|---|---|
| Cos'è | query/report/dashboard generata *on-the-fly* da un motore esistente | codice React permanente, nuova route |
| Manutenzione | **zero** (rigenerabile, nessun codice nuovo) | perpetua (brand/schema/CVE) |
| Quando | lettura, monitoraggio, report (la maggioranza dei bisogni interni) | **solo se** mutazione-di-stato (scrittura DB, workflow, azioni irreversibili) O interattività complessa non esprimibile come vista |

> **Default = vista.** Un'app è l'eccezione, giustificata solo dalla mutazione-di-stato. "Dashboard
> scadenze KITAS" (sola lettura) → **vista**, non app. Questo riduce drasticamente il volume di codice
> permanente → disinnesca il cimitero.

### 0.2 Quando serve un'app, è una ROUTE in un'app esistente, non una NUOVA app (Codex, Gemini #3)

Il red-team #3 (scaffold-trap): un nuovo scaffold aggiunge una 3ª variante alle app esistenti
(admin-dashboard vs admin-dashboard-local già divergono) e standardizza verso la mediocrità.

**Risoluzione (Codex)**: **NON creare una nuova app**. Aggiungere una **route** dentro
`apps/admin-dashboard` (ha già Next.js + Tailwind + Postgres + auth/RBAC). E generare **moduli** da 4
template riusabili, non app isolate:

- `deadline-dashboard`, `queue-monitor`, `table-workbench`, `detail-console`.
- Tutti **importano** token + componenti (mai copia) → un cambio-brand si propaga a tutti.

Così zero nuove app da mantenere; il codice generato vive in un'app che già si mantiene, ed eredita
auth/RBAC/deploy esistenti.

---

## 1. GROUND — reuse-first disk-state VERIFICATO questo turn

Anti-hallucination: file `wc -l`-verificati in questo turn (l'Explore aveva detto "20+ componenti";
reale = 12 + 11 test — sostanza confermata, numero corretto).

### 1.1 L'infrastruttura-brand è REALE ma frammentata

| Mattone | Stato | Evidenza verificata |
|---|---|---|
| Design tokens formali | **GIÀ-PRONTO** | `~/.claude/skills/bali-zero-brand/tokens.json` (151 righe, JSON WCAG AAA, namespace="closed"). Letto dal renderer WR2. |
| CSS tokens mirror | **GIÀ-PRONTO** | `packages/design-system/tokens/bz-tokens.css` (5.4k, custom-properties, dark-default+light) |
| Componenti React | **PARZIALE** | `packages/core/components/` = **12 .tsx + 11 test** (BZLogo, CommandPalette, ContextPanel, CTAHandoff, DeadlineBadge, FunnelFrame, MatterCard, NavShell…). TypeScript, testati, usati. MA scattered, nessun registry parsabile. |
| App interne esistenti | **GIÀ-PRONTO (template implicito)** | `apps/admin-dashboard` (Next.js+Tailwind+Postgres+auth), `mouth`, `kbli-navigator`. App finite, non scaffold. |
| Renderer agente→visivo | **GIÀ-PRONTO (locked a WR2)** | `wr2_carousel_orchestrator.py` + Playwright HTML→PNG. Brand-coerente, ma per caroselli (Playwright+ReportLab+Canva, non Next.js). |

### 1.2 I 3 abilitatori MANCANTI per la generazione-da-agente

1. **Component-discovery**: NO Storybook (verificato: zero `.stories`, zero `.storybook`). L'agente non
   sa "quali componenti ho + props + quando-usarli".
2. **Template/scaffold di modulo**: le app esistenti sono finite, non template riusabili.
3. **Fonte-di-verità unificata**: tokens isolato + componenti scattered + surface (concetto in
   constitution.md, ZERO codice) + layout (hardcoded in wr2) + image-modes (costanti). L'agente
   dovrebbe grep 7 file.

---

## 2. I 6 DIFETTI DEL RED-TEAM → risoluzione (Codex + DeepSeek)

| # | Difetto (Gemini) | Sev | Risoluzione |
|---|---|---|---|
| 1 | brand-api.json God-object → deriva (=decadimento-spec P5) | **CRITICA** | §3.1: la fonte unificata è un **BUILD-ARTIFACT GENERATO** dai 7 sorgenti (come OpenAPI da FastAPI), NON un file scritto-a-mano. Non può divergere: si rigenera a ogni build. Codex+DeepSeek convergono. |
| 2 | component-registry ≠ design-capability (Frankenstein-UI) | ALTA | §3.3: discovery (registry) + **reference-pattern** (le app esistenti come esempi di composizione) + **critic-di-design** (modello critic-WR2) che valuta gerarchia/allineamento prima del deploy. Discovery è necessaria non sufficiente. |
| 3 | scaffold-trap (3ª variante, mediocrità) | MEDIA | §0.2: NON nuova app → **route in admin-dashboard** + 4 moduli-template che importano (non copiano). |
| 4 | cecità-interattiva (PNG = polaroid → verde-ma-rotto) | **CRITICA** | §3.4: Playwright produce **stati multipli** (loading/empty/overdue/filtered/detail-open) + **trace/video del click-flow** + report HTML. Antonello valuta il *comportamento*, non solo l'estetica. + lint/test/build devono passare (non solo lo screenshot). |
| 5 | paradosso-PII-runtime ("porta blindata, muri dimenticati") | **BLOCCANTE** | §3.5: separare **generazione** (sandbox P3, fixture REDATTE, zero righe-clienti) da **runtime** (dentro admin-dashboard, auth/RBAC esistenti, dati server-side, localhost-Pro o Tailscale-only). L'app generata eredita il confine P2. |
| 6 | cimitero-codice-generato (asfissia manutenzione) | **FATALE** | §0.1: criterio **app-vs-vista** (default=vista, zero manutenzione). + moduli che importano (cambio-brand si propaga). + ogni tool ha `tool.manifest.json` per tracciabilità. |

**Convergenza 3/3**: build-artifact-generato (non God-object), riuso-non-rigenerazione, separazione
generazione/runtime. Red-team trova, Codex dà il "come", DeepSeek dà il "criterio".

---

## 3. DESIGN — il loop "v0 locale" dentro il brand, app-vs-vista-aware

### 3.1 Fonte unificata GENERATA, non mantenuta (difetto #1 CRITICA)

`packages/design-system/brand-api/` come **build-artifact** (`pnpm bz:brand:api`), derivato da:
- `tokens.json` + `bz-tokens.css` (token),
- i 12 `.tsx` via `react-docgen-typescript` (props automatiche),
- sidecar `Component.usage.json` / JSDoc per `useWhen` + esempio (l'unica parte non-deducibile da un
  parser, scritta accanto al componente — non in un file separato che decade),
- costanti layout dal codice.

Output: `components.json` (per l'agente) + `docs/design/components-catalog.md` (per umani). **Generato
a ogni build** → se i `.tsx` cambiano, si rigenera → non può divergere (a differenza di un
brand-api.json scritto-a-mano = il God-object che il red-team ha ucciso).

```json
{ "name": "DeadlineBadge",
  "import": "@nuzantara/core/components/DeadlineBadge",
  "props": {"status": "overdue | soon | ok", "date": "string"},
  "useWhen": ["deadline","expiry","status urgency"],
  "example": "<DeadlineBadge status=\"soon\" date={item.expiresAt} />" }
```

### 3.2 Il flusso "v0 locale" (Codex) — genera→preview→raffina, senza cloud

```bash
pnpm bz:brand:api                         # rigenera la fonte (build-artifact)
pnpm bz:appgen "dashboard scadenze KITAS" # Claude-CLI/Codex in sandbox P3
pnpm --filter admin-dashboard dev -- -p 4310
pnpm bz:preview /tools/kitas-deadlines    # Playwright: stati multipli + trace
pnpm bz:brand:lint && pnpm test && pnpm build
```

`bz:appgen` invoca il generatore (Claude-CLI o Codex, **no-paid-Anthropic-API**, no v0/Bolt/Lovable
cloud) DENTRO la sandbox P3, ricevendo SOLO: `tokens.json`, `bz-tokens.css`, `components.json`, il
template-modulo, e lo **schema/API-contract REDATTO** (mai righe-clienti reali). Replica il loop di v0
(design-system in context + componenti + genera-preview-raffina) ma locale e PII-safe.

### 3.3 Discovery + design-capability (difetto #2 ALTA)

La discovery (registry §3.1) è necessaria ma non sufficiente. Si colma con:
- **Reference-pattern**: `apps/admin-dashboard` + `mouth` indicizzate come esempi canonici di
  composizione brand-coerente ("ecco come si dispone una dashboard reale").
- **Critic-di-design**: un modulo sul modello del critic-WR2 (già esistente) valuta l'output contro
  regole compositive (gerarchia visiva, allineamento, uso corretto dei componenti) + brand-compliance,
  e dà feedback correttivo prima del deploy. È la **pipeline-giudizio** di P7 applicata alle UI.

### 3.4 Preview interattiva, non polaroid (difetto #4 CRITICA)

Playwright nella sandbox produce, contro un dev-server effimero:
- screenshot desktop + mobile,
- **stati**: loading, empty, overdue, filtered, detail-drawer-open,
- **trace + video** del click-flow,
- report HTML in `artifacts/previews/<tool>/index.html`.

+ `lint && test && build` devono passare. Così Antonello valuta il *comportamento* (l'app funziona),
non solo l'estetica (lo screenshot è bello). Chiude il "verde-ma-rotto".

### 3.5 PII: generazione vs runtime separati (difetto #5 BLOCCANTE)

- **Generazione** (sandbox P3): l'agente riceve fixture **redatte** (`_redact_pii.py` di P2), mai righe
  clienti reali nel prompt/codice/fixture.
- **Runtime** (dentro `apps/admin-dashboard`): auth/RBAC esistenti, dati server-side, gira
  **localhost-Pro o Tailscale-only** (no esposizione pubblica per default). Se mai cloud: solo dietro
  auth forte + audit-log + zero-PII-nel-codice.
- L'app generata **eredita** il confine P2 e il runtime-segregato — non è un nuovo posto dove la PII
  scappa.

### 3.6 Brand-LITE (interno) vs brand-FULL (pubblico) (DeepSeek #4)

| | brand-FULL (pubblico: caroselli, contenuti) | brand-LITE (interno: tool, dashboard) |
|---|---|---|
| Token | obbligatori | **obbligatori** (coerenza visiva minima) |
| WCAG AAA | obbligatorio | **obbligatorio** (accessibilità) |
| Layout | prescrittivo (14 layout-family) | **libero** (funzionale, non compiuto-esteticamente) |
| Componenti | prescrittivi | riusati **dove funzionali**, no vincolo di compiutezza |

Applicare il full-rigor a un cruscotto visto solo dal team è over-engineering. Brand-LITE preserva
coerenza+accessibilità senza imporre rigidità ingiustificata.

### 3.7 Riuso forzato + manutenzione (difetti #2, #6)

- **Riuso a 3 livelli** (Codex): catalogo-in-prompt ("mappa ogni bisogno a un componente esistente") +
  ESLint locale (vieta nuovi `*Card/*Badge/*Shell/Button` se esiste equivalente nel registry) +
  token-lint (vieta `#hex/rgb()/hsl()` nel generato).
- **Manutenzione**: moduli che **importano** token+componenti (mai copiano → cambio-brand si propaga).
  Ogni tool generato include `tool.manifest.json` (template usato, componenti, API-contract, preview-
  states) per tracciabilità + regressione (brand-lint, reuse-score, axe/contrast, Playwright-smoke).

---

## 4. GATE FALSIFICABILI (Symbiosis Law 7)

- **G1 — app-vs-vista** (binario): un bisogno di sola-lettura DEVE essere instradato a vista (zero
  codice nuovo), NON a app. Falsificabile: il gate genera una vista per "mostra le scadenze", un'app
  solo se c'è mutazione-di-stato.
- **G2 — token-compliance** (binario): un modulo generato con `#hex`/`rgb()` hardcoded → lint fallisce.
  Solo token del brand. Falsificabile: grep di hex nel generato = 0.
- **G3 — component-reuse** (numerico): se esiste `<DeadlineBadge>` e l'agente reimplementa un badge →
  ESLint fallisce. Metrica: % bisogni-UI mappati a componenti-esistenti (target alto).
- **G4 — WCAG AAA** (binario): il modulo generato passa axe/contrast AAA (il brand lo richiede anche in
  brand-LITE). Falsificabile: report axe.
- **G5 — preview-comportamentale** (binario): la preview cattura ≥5 stati + il click-flow funziona
  (lint+test+build verdi), NON solo uno screenshot. Falsificabile: la preview senza stati-multipli/test
  è rifiutata. Chiude il verde-ma-rotto.
- **G6 — fonte generata non scritta** (binario): `components.json` è un build-artifact (`bz:brand:api`),
  modificarlo a mano → sovrascritto al prossimo build. Falsificabile: il file ha un header "GENERATED,
  do not edit" e il build lo rigenera.

---

## 5. RESIDUI ONESTI

1. **Design-capability resta parziale (Gemini #2)**: reference-pattern + critic *riducono* le UI brutte
   ma non garantiscono UI *buone* — il giudizio estetico/UX di alto livello resta umano. Il critic
   cattura le violazioni grossolane (gerarchia, allineamento, brand), non l'eccellenza di design. Per un
   tool interno (brand-LITE), "funzionale e coerente" è sufficiente — l'eccellenza non è il target.
2. **Il motore-viste va costruito**: il criterio app-vs-vista presuppone un "motore di interrogazione"
   da cui generare viste effimere senza codice. Oggi NON esiste come tale (le viste sarebbero ancora
   route in admin-dashboard). Mitigazione: iniziare con viste-come-route-parametrizzate-riusabili (1
   template `table-workbench` che prende una query), evolvere verso un motore-viste vero solo se il
   volume lo giustifica. Onestà: il "zero-manutenzione" della vista è pieno solo con un motore-viste
   che ancora non c'è.
3. **PII-runtime su Mac (Gemini #5 residuo)**: "localhost-Pro o Tailscale-only" funziona per un solo-dev,
   ma è un single-point (se il Pro è giù, il tool non c'è). Accettato per la scala attuale; un'app
   critica andrebbe su Fly con auth (costo+superficie maggiori) — decisione caso-per-caso.
4. **Critic-di-design eredita il verifier imperfetto (P1/P7)**: il critic-UI è un LLM → fallibile. È
   pipeline-giudizio (consultiva, P7), il gate finale resta lo screenshot+comportamento giudicato da
   Antonello. Non auto-approva.

---

## 6. DECISIONE (kill gate)

**GO sul loop "v0 locale" app-vs-vista-aware**, con i 3 abilitatori costruiti come **build-artifact +
route-non-app + preview-comportamentale**. Riusa tokens.json + i 12 componenti + admin-dashboard
(l'80% esiste). Generazione in sandbox P3 con fixture redatte; runtime in admin-dashboard con RBAC.

**Priorità (Codex, per leva)**: (1) `components.json` generato (react-docgen) + token-lint
[quick-win, 1 giorno]; (2) 1 modulo-template (`deadline-dashboard`) + 1 route reale in admin-dashboard;
(3) loop generate→preview-multistato→raffina; (4) critic-di-design + brand-LITE; (5) motore-viste solo
se il volume lo giustifica.

**Metrica primaria falsificabile**: G1 (sola-lettura→vista, non app) + G5 (preview cattura il
comportamento, non solo l'estetica). Se ogni bisogno diventa un'app (cimitero) o se si approva su
screenshot-bello-app-rotta (verde-ma-rotto), il pezzo ha fallito i suoi 2 difetti più gravi
(FATALE + CRITICA).

**NON adottato**: v0/Bolt/Lovable (cloud-paid + PII-boundary). Storybook (pesante; sostituito da
`components.json` generato + catalog markdown).

---

## 7. Provenienza

- **Reuse-first**: Explore disk-state (claim ri-verificati; correzione 12 componenti non "20+").
  tokens.json 151, packages/core/components 12+11test, bz-tokens.css, admin-dashboard, Storybook
  confermato assente. Memory importance-8.
- **Council 3-LLM asimmetrico** (FULL — buco aperto, alta incertezza):
  - Red-team: **Gemini 3.1 Pro** — 6 difetti (FATALE cimitero, BLOCCANTE PII-runtime, 2 CRITICA
    God-object+cecità-interattiva). Premiato per distruggere.
  - Constructive: **Codex GPT-5.5** — route-non-app, moduli-template, components.json generato
    (react-docgen), Playwright-stati-multipli, generazione/runtime separati, riuso a 3 livelli.
    Premiato per salvare con concretezza.
  - Logic: **DeepSeek V4 Pro** (`reasoning_effort=high`) — criterio **app-vs-vista** (disinnesca il
    FATALE), build-artifact-non-God-object, reference-pattern+critic, brand-LITE/FULL. I criteri logici.
  - **Convergenza 3/3** su build-artifact-generato, riuso-non-rigenerazione, generazione/runtime separati.
- **Famiglia**: P2 (PII-redact sulle fixture di generazione + confine runtime), P3 (sandbox dove genera),
  P4 (contract API↔frontend con openapi-typescript per la route generata), P7 (critic-di-design =
  pipeline-giudizio; preview-comportamentale = segnale oggettivo). Renderer WR2 (il pattern
  agente→visivo→Playwright già esistente, esteso da PNG-statico a stati-interattivi).

> **Onestà finale**: il pezzo NON dà "un agente che sforna app". Dà "un agente che, davanti a un
> bisogno interno, **prima decide se serve un'app o basta una vista** (e quasi sempre basta una vista,
> zero manutenzione), e quando serve un'app la genera come **route in un'app esistente**, da
> **moduli che importano il brand** (non copiano), con **preview che mostra se funziona** (non solo
> com'è), **dentro la sandbox** con dati redatti, **eredita auth/RBAC** in runtime. Il salto non è
> "generare di più" — è **generare il meno possibile di permanente** (vista > app), e ciò che è
> permanente farlo riusabile e auto-coerente col brand. Generare è facile; il pezzo ottimizza per NON
> dover mantenere.
