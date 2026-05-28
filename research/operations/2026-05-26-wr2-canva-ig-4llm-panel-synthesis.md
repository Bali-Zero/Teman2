---
date: 2026-05-26
domain: operations
client_case: WR2-canva-ig-workflow-c5a-pilot
sources:
  - panel: Claude Opus 4.7 (orchestrator) + Gemini 3.1 Pro (agy) + Codex GPT-5.5 (xhigh) + DeepSeek V4 Pro (reasoning_effort=high)
  - empirical: /Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/backend/services/canva_renderer_v2/{orchestrator.py,_canva_mcp.py,_tigris.py}
  - empirical: /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/publisher/ig_publisher.py:106 (max 10 carousel items)
  - pilot: /Users/nuzantara/.claude/skills/bali-zero-brand/_carousels-by-session/c5a-konten-kreator-2026-05-26/
panel_outputs:
  - /tmp/panel-gemini.md (10 + full report ~/.gemini/.../c5a_research_brief.md 100 lines)
  - /tmp/panel-codex.md (345 lines, 24 file citations w/ line numbers)
  - /tmp/panel-deepseek.md (164 lines, max_tokens hit)
brief: /tmp/wr2-canva-ig-brief.md
---

# 4-LLM Panel Synthesis — WR2 → Canva → IG Workflow (C5A Pilot)

## Premesse del brief CHALLENGIATE (empirical override panel)

| Premessa brief                                                                                        | Empirical disk-state 2026-05-26 18:45 WITA                                                                                                                                                                                               | Verdict                                                                                                              |
| ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| "canva_pending.json shipped"                                                                          | File NON esiste in `_carousels-by-session/c5a-konten-kreator-2026-05-26/`                                                                                                                                                                | **WRONG** — brief assumption stale                                                                                   |
| "Production cron edit-transaction su template DAHJS2Iv960 via replace_text"                           | `_canva_mcp.py` espone SOLO `import_design_from_url` + `move_item_to_folder`. Orchestrator flow è HTML→PDF (Playwright)→Tigris→Canva `import-design-from-url` → Drive move. NESSUNA replace_text/start-editing-transaction in produzione | **WRONG** — il flow produttivo è PDF-import, NON edit-transaction. Section B del brief poggia su modello inesistente |
| "Claude Code CLI ha tutti gli MCP Canva tools quindi possiamo eseguire wr2_canva_pdf_apply.py da CLI" | Tools availability ≠ token sharing. `_canva_mcp.py:88` usa proprio `OrchestratorTokenStorage`. CLI MCP usa OAuth Canva separato                                                                                                          | **PARTIAL** — la disponibilità tool è confermata, ma la sessione/auth NON è interoperabile col cron                  |
| "11 slides editorial carousel"                                                                        | IG Graph API max = 10 items per carousel. `ig_publisher.py:106` valida `len(slides)+1 > 10` reject. C5A 11 slides → 12 items con cover → fail                                                                                            | **BLOCKER P0** non menzionato nel brief — non solo Canva è bloccato, anche IG publish                                |

## Executive Summary (4-LLM convergent)

1. **SSOT reale = narrative JSON, non PNG né Canva.** `slides-v2-post-verify-gate.json` (21KB, VERIFY-GATE.md verified, 6 errors corrected from parallel session) è la sorgente. HTML/PNG/Canva sono render target. (Convergence 4/4: Opus, Gemini, Codex, DeepSeek)
2. **Production flow PDF→Canva import è anti-pattern per editabilità.** Canva PDF parser reconstructs text-box approximativamente, perde tracking tipografico e brand template. (Convergence 3/4: Gemini, Codex, DeepSeek esplicito; Opus implicito tramite empirical discovery)
3. **Operator-driven bypass è feature, non smell — ma SOLO se produce contratti equivalenti** (canonical JSON, VERIFY-GATE, CRITIC-GATE, render manifest). Bypass silenzioso senza artifact = smell. (Convergence 3/4: Gemini, Codex, DeepSeek; Opus aggiunge "audit trail required")
4. **Tigris asset = backend proxy endpoint, NON creds-on-Pro.** Cloudflared tunnel è bridge tattico OK per C5A oggi, MAI architettura. (Convergence 4/4)
5. **IG editorial publishing → operator-approved scheduled queue, MAI cron auto-publish.** Auto-publish OK solo per news-flash deterministic con regex check + kill-switch. (Convergence 4/4)
6. **DISCOVERY P0 (Codex only)**: `ig_publisher.py:106` rifiuta C5A 11-slide carousel anche via manual draft creation. **Doppio blocker oltre Canva.**

## Sezione A — Workflow Integrity

### A1 — HTML→PNG→Canva vs HTML→Canva direct

| LLM      | Verdict                                                                                        | Reasoning chiave                                   |
| -------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Opus     | PNG preserve regulatory verbatim — Canva-direct OK solo con role schema stabile                | Anti-template-coupling (W50/W51 family)            |
| Gemini   | Canva-direct strictly superior PER EDITABILITÀ; PNG OK solo per news-flash bypass              | Canva PDF parser frammenta text-box, perde kerning |
| Codex    | Né l'uno né l'altro — SSOT è narrative JSON, render è variabile per scopo                      | "PNG è derivato, NON sorgente"                     |
| DeepSeek | Per regulatory verbatim → PNG vince (lock legal text esatto). Per editing → Canva-direct vince | Trade-off su lifecycle del carosello               |

**Verdict synth**: Gemini overreach ("strictly superior"). Codex framing è il più corretto. **Per C5A regulatory editorial: HTML→PNG come QA artifact deterministico + Canva editable copy via edit-transaction su copia (NON template content-bearing) per ultima manuale Antonello + PNG finale export IG.**

### A2 — Cost del bypass wr2-storyboarder + wr2-critic

Convergence 4/4: bypass NON è smell per regulatory editorial high-stakes con manual VERIFY-GATE. È smell se ripetuto senza contratti equivalenti.

**Cost concreti identificati** (Codex):

- Pilot JSON `slides-v2-post-verify-gate.json` ha schema `{n, heading, layout_family}` mentre `pending_builder.py` legacy si aspetta `{slide_number, headline, body, is_hero_image, image_url}` → adapter mancante
- Brand drift: 11 slides eccede range 4-10 storyboarder
- Critic GATE.md ha PASSATO PNG locale ma stato Canva/PDF/IG è pending — critic vero deve ispezionare deliverable finale, non preview

**Fix structural (Codex P1)**: `WR2_OPERATOR_MODE=true` deve produrre:

1. Normalized canonical slide JSON
2. VERIFY-GATE.md o machine-readable verify summary
3. CRITIC-GATE.md o CRITIC-GATE.json
4. Render manifest con SHA/file paths
5. `canva_pending.json` o direct Canva transaction ops

### A3 — Tigris asset hosting (3 options)

| Option                                                          | Cleanness                                                                                     | Convergence                               |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------- |
| (a) Creds in `~/.nuzantara-secrets.env` Pro-side                | **Dirty** — violates "no secrets in Pro shell", secret sprawl, machine-specific               | 4/4 reject                                |
| (b) Fly backend endpoint proxy `POST /api/assets/upload`        | **Cleanest** — Fly container creds native, single audit boundary, works manual+cron identical | 4/4 recommend                             |
| (c) Cloudflared tunnel Pro HTTP + Canva `upload-asset-from-url` | **Hack** — fragile, URL ephemeral, NO cron-automatable                                        | 2/4 OK solo come tactical bridge C5A oggi |

**Verdict synth**: Opzione (b) è il fix structural. Opzione (c) è il ponte oggi se backend endpoint non esiste ancora.

## Sezione B — Canva Apply Layer

### B1 — Assumptions latent del cron che NON tengono in CLI

Opus + Codex aggiungono dettagli che Gemini e DeepSeek non vedono:

| Assumption                                                               | Source code                                                            | Trap                                                                              |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| PDF import (non edit-transaction)                                        | `orchestrator.py:162` `import_design_from_url(pdf_url, ...)`           | Brief sezione B parla di replace_text — NON è il flow produttivo                  |
| LaunchAgent sources `~/.nuzantara-secrets.env` da `~/Desktop/nuzantara/` | `com.balizero.wr2.canva-renderer.plist:7`                              | Anche copy in `~/Desktop/nuzantara-deploy/` → SSOT wrapper drift (W50/W51 family) |
| 60s HTTP timeout MCP client                                              | `_canva_mcp.py:88+`                                                    | 35-op edit + asset upload + thumbnail + export può eccedere                       |
| `MAX_DRAFTS_PER_RUN=3`                                                   | `orchestrator.py`                                                      | OK per PDF import; rischio per transaction-many-op                                |
| Exit codes kill-switch/missing-token marked SuccessfulExit               | LaunchAgent plist                                                      | Operationally quiet by design — può maskare token revoked silent                  |
| pg-proxy WG idle drop ~10s                                               | W47/W49 cicatrix family                                                | Wrappers force `DATABASE_URL_LOCAL` + retry — pattern obbligatorio                |
| Token storage non condiviso con CLI MCP                                  | `_canva_mcp.py` `OrchestratorTokenStorage` vs CLI Canva OAuth distinto | "CLI ha i tools" NON = "CLI può rieseguire il cron"                               |

**Bottom line**: CLI ha i Canva MCP tools, ma cron e CLI hanno auth/lifecycle/timeout assumptions diverse. NON è drop-in replacement.

### B2 — Transaction granularity per 35-op edit

| LLM      | Recommendation                                                                                           |
| -------- | -------------------------------------------------------------------------------------------------------- |
| Opus     | Single transaction su COPIA, fallback per-page-range solo su timeout                                     |
| Gemini   | Per-page transactions per recovery partial                                                               |
| Codex    | Single big su copia + pre-flight element-ID validation + fallback split 2 transactions (pages 1-6, 7-11) |
| DeepSeek | Single big — Canva atomicity prevents mid-state                                                          |

**Verdict synth**: 3/4 = single atomic transaction on COPY (mai master). Pre-flight: `_get_design_content` per validare element IDs prima di start-transaction. Fallback split 2 transazioni solo dopo timeout empirico.

### B3 — Template DAHJS2Iv960 content-bearing

**Convergence 4/4**: template ESISTENTE con contenuto Bali deportation = NON empty shell = è un design, NON un brand template con dataset schema.

| Strategy                                           | Verdict                                                                                                          |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `replace_text` su DAHJS2Iv960 esistente            | **Brittle** — vincolato a text-box size/position/char-count del topic precedente, rischia overflow C5A bilingual |
| `create-design-from-brand-template` con `dataset`  | **NON applicabile** finché DAHJS2Iv960 non ha placeholder/dataset schema                                         |
| Copy-first + role remap + transaction edit su copy | **Pattern corretto v1.5** (Codex, conferma Opus)                                                                 |
| Empty role-based shell custom                      | **Target v1.5** dopo C5A ship                                                                                    |

## Sezione C — IG Publisher Layer

### C1 — Editorial publishing manual vs cron

Convergence 4/4: editorial regulatory MAI auto-publish. News-flash sì con kill-switch + regex check.

**Right wiring** (Codex più dettagliato):

- Auto-render, auto-stage, auto-generate caption/alt-text/first-comment
- Scheduled queue con peak engagement windows suggested
- Operator approval required PRIMA `media_publish`
- Record approval actor, timestamp, asset SHA, caption version, source gate version

**Two-lane queue** (DeepSeek):

- Fast lane: news-style → auto-publish se passa regex (no forbidden phrases, citations present)
- Editorial lane: status `pending-review`, schedulable solo dopo human stamp `approved`

### C2 — Caption + alt-text + first-comment

| LLM      | Hook style                                                               | Length    |
| -------- | ------------------------------------------------------------------------ | --------- |
| Opus     | Short hook + 3-5 factual bullets + soft CTA                              | <500 char |
| Gemini   | "Konten Kreator in Bali: nuova direttiva C5A" + bullets + link-in-bio    | Compact   |
| Codex    | Hook + bullets + operational implication + soft CTA + 5-8 hashtag mirati | Compact   |
| DeepSeek | Hook + value bullets 3-4 + CTA link-in-bio                               | Compact   |

**Convergence 4/4**: short hook + bullets + soft CTA. NO long-form regulatory text in caption. **Hashtag**: 5-8 mirati, mix broad + niche (`#VisaIndonesia #C5A #KontenKreator #IndonesiaImmigration #BaliBusiness #BaliZero`).

**First comment** (Codex): sources + caveat verbatim, NON hashtag stuffing.

**DISCOVERY GAP**: `DraftPayload` + `ig_publisher.py` NON modellano alt-text né first-comment. Code extension needed prima di automated staging support.

## Sezione D — Alternative Workflows

### D1 — Path X/Y/Z per carousel type

| Carousel type                       | Best path                                                                                              | Convergence               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------- |
| **Regulatory editorial** (C5A-like) | **Path Z hybrid** — HTML sandbox + Canva editable master + PNG IG dispatch                             | 4/4                       |
| **News flash** (intel-bridge)       | **Path X** — HTML→PNG→IG direct, speed prevails                                                        | 4/4                       |
| **Evergreen explainer**             | **Path Y** — Canva native generation, MA solo dopo brand-template dataset esiste. Oggi NON applicabile | 3/4 (DeepSeek meno netto) |

**Codex pushback**: "Path Y per C5A oggi è wrong abstraction finché brand+source constraints non sono machine-enforced". Concordo.

**DeepSeek pushback** sulla domanda: "Non sono mutually exclusive — sono render targets per la stessa narrative spec".

### D2 — SOTA comparison NYT/Bloomberg/Pudding/Rest of World

| Outlet              | Production tooling                                                   |
| ------------------- | -------------------------------------------------------------------- |
| NYT Opinion         | In-house artists Figma → PNG, custom illustrations                   |
| Bloomberg Originals | Mix template + in-house fonts/spacing, render pipeline HTML→PNG-like |
| The Pudding         | Web-native interactive scrollytelling, IG = screenshots di queste    |
| Rest of World       | Templated minimalist, likely Canva/Figma                             |
| Quartz              | High-contrast text-over-image, mix Canva + AfterEffects              |

**Convergence**: high-end editorial NON usa Canva come SSOT. Usano Figma/Adobe/HTML in-house. **Canva è strongest per team accessibility + fast operator edits, NON per deeply controlled legal rendering**.

**Swipe retention**: format è secondario rispetto a narrative compression + slide-to-slide curiosity. Tool choice secondaria, unless tool causes overflow/stale text/weak hierarchy.

## Sezione E — C5A Pilot SPECIFIC (TODAY)

### E1 — Single best operational path under 30min

**Codex path (più dettagliato, raccomandato)**:

1. **NON** abilitare `wr2_canva_renderer_enabled` (v2 cron). Aspetta stato DB/Tigris/PDF non soddisfatto per pilot locale.
2. **Copy** `DAHJS2Iv960` via Canva `_copy_design`. Lavora solo sulla copia.
3. `_get_design_content` sulla copia → mappa text-box esistenti deportation a posizioni page/role. NO stale IDs.
4. `_start_editing_transaction` sulla copia.
5. `_perform_editing_operations` con `replace_text`/`find_and_replace_text` + formatting/position dove serve. Apply C5A text dal narrative JSON.
6. Delete page 12 inside transaction se tool espone page-level op; altrimenti export solo pages 1-11.
7. **Hero images strategy**:
   - **Priority A (text-editability now)**: ship Canva text-editable copy oggi, keep local PNGs come visual reference. Hero upload deferred.
   - **Priority B (exact hero today)**: temporary cloudflared tunnel → serve 4 JPG → `_upload_asset_from_url` → `update_fill`/`insert_fill`. Tactical bridge.
   - **NEVER**: Tigris from Pro senza backend boundary o senza secrets intentionally added.
8. `_commit_editing_transaction`.
9. QA: `_get_design_pages` + `_get_design_thumbnail` o export. Se fail pre-commit → cancel + retry split 2 ranges.

**Expected failure modes + recovery**:

- Ambiguous text mapping → cancel transaction, remap from actual content, avoid broad find/replace
- Text overflow C5A bilingual → resize targeted box o mark editable draft per manual designer
- Hero upload blocked → ship text-editable Canva + local PNG attached
- Transaction timeout → split pages 1-6 / 7-11
- Accidental master mutation → **prevented by copy-first (non-negotiable)**

**Codex blunt**: "exact pixel-perfect + full editable + no hosted hero = NOT clean 30min target". Clean 30min = copied design + correct editable text + known hero-image gap, OR tunnel-assisted tactical hero upload.

### E2 — Minimum structural fix WR2 v1.5

**Convergence Codex + Gemini**:

1. **WR2 `operator_driven` mode**: accept `slides-v2-post-verify-gate.json` → emit canonical WR2 slide JSON
2. **Schema adapter** Bali Zero brand session JSON → WR2 fields (`slide_number`, `layout_family`, `headline`, `subhead`, `body`, `bullets`, `is_hero_image`, `asset_path`, `image_url`, `source_refs`, `regulatory_claims`)
3. **canva_pending.json builder** o direct Canva transaction ops da normalized JSON
4. **Backend asset upload service** (option b A3): Pro sends bytes/paths to protected backend endpoint → backend writes Tigris content-addressed
5. **Drop PDF→Canva-import** in `orchestrator.py:162` per editable carouseli → replace con copy-first + edit-transaction su copia di brand-template (when shell exists)
6. **Publisher extensions**: caption/alt-text/first-comment models, 10-item carousel cap aware
7. **Approval gate preserved**: regulatory MAI auto-publish

## RECOMMENDATION TIER (4-LLM convergent)

### P0 ship-blocker (TODAY)

| Item                                                                                         | Source                                   | Action                                                                                                   |
| -------------------------------------------------------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| NON abilitare cron `wr2_canva_renderer_enabled` per C5A                                      | Codex+Opus                               | Lascia kill-switch OFF                                                                                   |
| NON mutare DAHJS2Iv960 direttamente                                                          | 4/4                                      | Copy-first sempre                                                                                        |
| C5A 11 slides eccede IG max 10 (`ig_publisher.py:106`)                                       | **Codex only — empirical verified Opus** | Decidi: drop 1 slide OR split in 2 carouseli OR manual IG publish (UI accetta max 10 → comunque blocker) |
| Hero asset hosting: NO Tigris creds locali → cloudflared tunnel OR ship Canva text-only oggi | Codex+Gemini                             | Tactical bridge                                                                                          |
| Regulatory editorial NO auto-publish                                                         | 4/4                                      | Operator approval gate                                                                                   |

### P1 next iteration (questa settimana)

| Item                                                                              | Source                |
| --------------------------------------------------------------------------------- | --------------------- |
| WR2 `operator_driven` mode formal + schema adapter                                | Codex+Gemini+DeepSeek |
| Backend `/api/assets/upload` proxy endpoint Tigris                                | 4/4                   |
| Drop PDF→import flow in orchestrator.py per editable; copy-first transaction edit | Codex+Gemini          |
| Empty role-based Canva shell OR real brand template con dataset                   | Codex+DeepSeek        |
| `DraftPayload` + `ig_publisher.py` extend per caption/alt-text/first-comment      | Codex empirical gap   |
| IG carousel 10-item cap awareness in canonical schema                             | Codex                 |

### P2 nice-to-have

| Item                                                           | Source       |
| -------------------------------------------------------------- | ------------ |
| Performance metrics swipe retention per archetype/slide count  | Codex        |
| Scheduled publishing recommendations (approval still required) | Codex+Gemini |
| Visual diff HTML render vs Canva export                        | Codex        |
| Automatic hashtag linting + forbidden-phrase checks            | Codex        |
| Brand-template autofill solo dopo dataset schema stable        | Codex        |

## DISAGREEMENT FLAGS

### Disagreement 1 — Gemini overreach "HTML→Canva direct strictly superior"

Codex + Opus contestano: superior SOLO con role schema stabile. DAHJS2Iv960 content-bearing = direct replace fragile. Gemini è troppo netto. **Verdict synth**: Codex/Opus right.

### Disagreement 2 — Brief sezione B premise

Brief tratta "replace_text su 35-op edit transaction" come flow produttivo. Empirical: NON è il flow produttivo (`_canva_mcp.py` espone solo `import_design_from_url`). **Verdict**: brief premise stale, sezione B answers vanno re-framed come "alternative path proposal" non "audit current path".

### Disagreement 3 — DeepSeek su PNG editorial master

DeepSeek: "per regulatory verbatim PNG vince (lock legal text)". Codex pushback: PNG perde alt-text derivability, localization, late corrections. **Verdict synth**: Codex right per lifecycle completo. DeepSeek right per single-shot publish snapshot — ma editorial regulatory ha sempre lifecycle (corrections, localization, reuse).

### Disagreement 4 — "CLI ha tools = WR2 ready"

Premessa brief: empirical audit 2026-05-26 conferma CLI Canva MCP tools availability. Codex pushback: tool availability ≠ auth/session/lifecycle interoperability con cron. **Verdict**: CLI può eseguire MCP Canva operations manuali; CLI NON è drop-in replacement per `wr2_canva_pdf_apply.py` cron.

### Disagreement 5 — 11 slides treatment

Brief implica 11 slides è OK. Codex empirical: IG Graph max 10 + `ig_publisher.py:106` enforce. Editorialmente: 11 slide heavy unless retention arc strong. **Verdict synth**: P0 blocker NOT solo Canva — anche IG publish. Decisione architetturale: drop 1 slide (slide 10 status-list o slide 8 PNBP-extension-sponsor candidate per merge) OR split in 2 carouseli sequenziali OR accept manual UI Instagram (che comunque rifiuta >10).

## CITATIONS (cross-LLM cross-referenced)

**Empirical Nuzantara codebase** (verified disk-state 2026-05-26 18:45 WITA):

- `/Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/backend/services/canva_renderer_v2/orchestrator.py:162` — `mcp_client.import_design_from_url(pdf_url, ...)` (production flow)
- `/Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/backend/services/canva_renderer_v2/orchestrator.py:281` — `ExitCode.KILL_SWITCH_OFF` line
- `/Users/nuzantara/Desktop/nuzantara-deploy/apps/backend-rag/backend/services/canva_renderer_v2/_canva_mcp.py:88+` — `CanvaMcpClient` class, expose `import_design_from_url` + `move_item_to_folder` SOLO
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/publisher/ig_publisher.py:106` — `if len(draft.slides) + 1 > 10: ... max 10` IG validation **(C5A 11 slides P0 blocker)**
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/canva_renderer_v2/_tigris.py:1+` — Tigris bucket public-read prefix `wr2-pdf/`, env credential dependency
- `/Users/nuzantara/Desktop/nuzantara/infra/launchagents/com.balizero.wr2.canva-renderer.plist:7` — LaunchAgent working dir + secret sourcing

**Pilot artifacts**:

- `~/.claude/skills/bali-zero-brand/_carousels-by-session/c5a-konten-kreator-2026-05-26/slides-v2-post-verify-gate.json` (21KB, v2, supersedes v1 6 errors)
- `~/.claude/skills/bali-zero-brand/_carousels-by-session/c5a-konten-kreator-2026-05-26/VERIFY-GATE.md` (10.9KB, NB-2 ground truth corrections)
- `~/.claude/skills/bali-zero-brand/_carousels-by-session/c5a-konten-kreator-2026-05-26/CRITIC-GATE.md` (8.5KB, local PNG state PASS)
- `~/.claude/skills/bali-zero-brand/_carousels-by-session/c5a-konten-kreator-2026-05-26/slides/*.html` + `*.png` (11+11=22 files, 4 hero JPG)
- `canva_pending.json` — **NOT YET CREATED** (brief premise wrong)

**Brand cortex / agent definitions**:

- `~/.claude/agents/wr2-storyboarder.md` (4-10 narrative contract)
- `~/.claude/agents/wr2-critic.md:109` (final deliverable PDF/Canva inspection rule)
- `~/.claude/skills/wr2-carousel-pipeline.md:220` (Canva apply authorization + mandatory review gate)
- `docs/wr2/canonical-bypass-prevention-2026-05-15.md:54` (false-pass lesson)
- `docs/wr2/pipeline-architecture-2026-05-10.md:51` (DB canonicality, JSON ephemerality)

**Panel raw outputs preserved**:

- `/tmp/panel-codex.md` (345 lines + 24 citations w/ line numbers — most thorough)
- `/tmp/panel-gemini.md` (10 line summary, full report `~/.gemini/antigravity-cli/brain/f2b8963b-44ed-4972-8ba9-14610ccbe153/c5a_research_brief.md` 100 lines)
- `/tmp/panel-deepseek.md` (164 lines, troncato max_tokens=8000)
- `/tmp/wr2-canva-ig-brief.md` (brief originale)

## Operational decision matrix (sintesi per Antonello)

| Decisione                         | Opzioni                                                                                                  | Raccomandazione panel                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| C5A oggi: ship Canva o defer?     | A) Ship oggi tunnel-assisted / B) Defer fino backend asset proxy / C) Ship PNG-only no Canva             | **A se Antonello vuole editare; C se non gli serve editing**   |
| 11 slides IG blocker              | A) Drop 1 slide (s10 status-list candidato) / B) Split 2 carouseli / C) Manual UI (anche IG rifiuta >10) | **A** — drop slide 10 status-list (è la più ridondante con s8) |
| Hero hosting                      | A) Cloudflared tunnel oggi / B) Backend proxy P1 / C) Pro creds (sporco)                                 | **A oggi + B questa settimana**                                |
| Cron `wr2_canva_renderer_enabled` | A) Tieni OFF / B) Riabilita per C5A / C) Refactor copy-first                                             | **A oggi, C in P1**                                            |
| Auto-publish IG editorial         | A) Sempre operator-approved / B) Auto su regex pass / C) Auto con kill-switch                            | **A 4/4 panel**                                                |

---

**Generated**: 2026-05-26 18:46 WITA
**Panel cost**: ~$0.02 (Gemini OAuth + Codex ChatGPT Pro + DeepSeek $0.01/q)
**Panel wall-time**: ~9 min (Gemini 3min, DeepSeek 5min, Codex 9min parallel)
**Empirical verification**: 8 file checked via Read/Grep disk-state during panel run
