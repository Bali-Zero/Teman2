---
date: 2026-05-29
domain: operations
client_case: bali-zero-internal-wr2-pipeline
type: feasibility-study
sources:
  - empirical test runs (this session, instrumented stream-json captures)
  - .claude/rules/cicatrix-scars.md (2026-05-13 wr2_canva_apply decommission entry)
  - infra/claude-skills/canva-apply.md + ~/.claude/skills/canva-apply.md (v3)
  - scripts/wr2_canva_desktop_apply.py (current AppleScript actuator)
  - apps/backend-rag/backend/services/canva_renderer/pending_builder.py
  - infra/eventbus/meta_dispatcher.py
---

# WR2 Canva apply — headless `claude -p` feasibility (replace AppleScript-GUI actuator)

## Problema

L'attuatore di produzione del carosello WR2 (`scripts/wr2_canva_desktop_apply.py`) applica le
operazioni del `canva_pending.json` via **AppleScript che pilota l'app Claude Desktop GUI**:
focus app → incolla `/canva-apply` → polling 10 min su `carousel_canva.json`. Fragile per design:
3 punti di rottura in fila (app deve essere aperta, lo skill deve essere registrato nell'app,
l'AppleScript deve rispondere). Operator report: "si rompe sempre".

La cicatrix `2026-05-13` aveva decommissionato il path headless `wr2_canva_apply.py` con la
motivazione: _"`claude -p` subprocess doesn't load the Canva MCP server reliably (project-scoped
OAuth doesn't survive the spawn); Canva Connect REST API doesn't support element-level text
replacement"_. Da lì la GUI desktop era l'unica via.

## Tesi verificata

Il muro 2026-05-13 **è caduto**. Il Canva MCP oggi è `claude.ai`-hosted (`mcp__claude_ai_Canva__*`),
non più project-scoped. In headless NON è auto-caricato, MA è raggiungibile come **deferred tool via
ToolSearch**. Con uno step-0 `ToolSearch select:mcp__claude_ai_Canva__*` lo skill `/canva-apply`
gira end-to-end in `claude -p` headless — zero AppleScript, zero GUI, zero app aperta.

## Metodo

Tutti i test in **isolamento totale** su copie throwaway (`copy-design`), zero contatto con prod.
Run instrumentati con `--output-format stream-json --verbose`, tool-call reali parsate dal JSONL
(NON l'auto-narrazione del modello). Ogni esito verificato sul disk-state Canva reale via MCP
interattivo (disciplina anti-allucinazione).

## Risultati (tutti verificati empiricamente)

| #   | Test                                                        | Esito                              | Evidenza                                                                                 |
| --- | ----------------------------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------- |
| 1   | tool Canva visibili in headless                             | deferred/ToolSearch (no auto-load) | `claude -p` → "NO CANVA MCP" diretto, ma ToolSearch li carica                            |
| 2   | read headless (`get-design`)                                | OK                                 | title "C5A — Content creator…" pages=11                                                  |
| 3   | write+commit headless                                       | OK                                 | copy→transaction→replace_text→commit, slide 11 = "HEADLESS WRITE TEST OK" verificato     |
| 4   | skill `/canva-apply` reale headless isolato                 | 3/3 PULITO                         | 10/13/16 tool-call, 0 errori, testo sugli slot giusti by-role                            |
| —   | allucinazione-ID (sospetto del primo run non-instrumentato) | NON riproducibile                  | 0/3 run instrumentati; era auto-narrazione, non evidenza                                 |
| D1  | immagini (upload + update_fill + insert_fill overlay)       | OK 248.6s                          | 3 asset caricati, 3 fill piazzati; `fills[]` pp.2/8 verificati su disk                   |
| D3  | Phase B move su folder invalido                             | graceful-degrade                   | 2 retry → "server error"+RequestID → procede → Phase D completa, dup creato non-spostato |
| D4  | sibling-race: 2 run headless sullo stesso master            | **CLOBBER**                        | master `DAHK9-hjkMM` p2 = `D4B P2D4A P2`, p3 = `D4B P3D4A P3` (verificato su disk)       |

## 5 finding load-bearing per la produzione

1. **Headless funziona** — `claude -p /canva-apply` con step-0 ToolSearch esegue l'intero ciclo
   (testo + immagini + overlay + duplicate + reset). L'AppleScript-GUI è eliminabile.

2. **Budget ≥ 900s** — il ciclo completo (11 slide + immagini) è ~250s a regime, ma il primo run
   non-instrumentato è morto a 540s con `start-editing-transaction` in volo (cold-start + SessionStart
   hook overhead). Un timeout a metà transazione lascia una **transaction dangling**. Lo skill è già
   idempotente (Phase -1 valida + transaction fresca supersede), ma serve budget ≥900s e idealmente
   un cleanup/watchdog della transaction orfana.

3. **`upload-asset-from-url` NON segue redirect 302** — picsum (302→fastly) ha dato `fetch_failed`
   per 3 tentativi, poi il modello ha ri-risolto l'URL diretto. In produzione il pipeline deve passare
   **URL immagine diretti** (no shortener/redirect) agli upload.

4. **No-`AskUserQuestion` in headless** — nel D3 pass-1 il modello ha trattato folder bogus + topic
   "do not publish" + `slides[]` vuoto come problemi STEP-0 bloccanti → ha chiamato `AskUserQuestion` →
   nessuna risposta headless → **abort prima di toccare Canva**. Lo skill headless DEVE avere direttiva
   esplicita "never AskUserQuestion, safe default + log". (Lo skill v3 attuale ha già "No follow-up
   questions" nelle hard rules, ma il pre-flight STEP 0 l'ha aggirata: va rinforzato.)

5. **Lease OBBLIGATORIO contro sibling-race** — Canva NON serializza le transazioni concorrenti: due
   run headless sullo stesso master aprono transazioni sovrapposte, committano entrambe, e il testo si
   **concatena nello stesso elemento** (`D4B P2D4A P2`). Salvezza fragile: `resize-design` snapshotta
   il master al commit di ciascun run, quindi i **duplicati** sono puliti — ma il master resta corrotto.
   Questo **valida empiricamente la cicatrix lease-watchdog WR2** (`wr2_canva_lease_watchdog.py`).
   L'attuatore headless DEVE acquisire il lease sul master prima di toccarlo.

## Implicazione architetturale

Il `canva_pending.json` resta (buon messaggero, operazioni 1:1, zero giudizio). Lo skill `/canva-apply`
resta (deterministico, già installato). Cambia **solo l'attuatore**: il blocco AppleScript+focus-app+
polling dentro `wr2_canva_desktop_apply.py` viene sostituito da una subprocess `claude -p /canva-apply
--dangerously-skip-permissions --output-format stream-json` con timeout ≥900s, preceduta da
acquisizione lease. Lo skill va patchato con step-0 ToolSearch idempotente + rinforzo no-AskUserQuestion.

## A4 probe result (2026-05-29) — dangling-transaction behaviour → **FRESH OK**

Verdetto del gate bloccante Task 0: **Canva NON blocca `start-editing-transaction` dopo
un kill mid-transaction.** Procedura: copia throwaway → `claude -p` apre la transazione e
inizia a editare → kill esterno del processo appena `transaction_id` compare nello stream
(transazione dangling per kill esterno, non per istruzione) → subito dopo un nuovo `claude -p`
apre una transazione fresca sullo stesso design. Esito: `CONFIRMED: transaction was open when
process was killed` poi `FRESH OK 6424889517177594611 CANCELLED`. Una transazione orfana viene
superseded da una fresca; nessun avvelenamento del design, nessun transaction-quarantine
necessario. L'attuatore headless è viabile come specificato; lo skill idempotente (Phase -1
validate read-only + transazione fresca sul working copy) copre il caso.

### Debugging del probe (4 fix, root cause finale non-tecnico)

Il probe ha dato `INVALID` per 4 run prima del verdetto. Lezione: il root cause NON era
nessuno dei sospetti tecnici (sleep timing / pipe-buffer / regex escaping — tutti reali ma
secondari). Il vero root cause: **il modello headless RIFIUTA un prompt che chiede di aprire
una transazione e lasciarla dangling** ("Non eseguo questa sequenza così com'è — abbandonare
una transazione mid-flight è azione difficile da reversare su stato condiviso"). Fix: dare un
task LEGITTIMO (open + edit reale + commit) e creare il dangling col **kill esterno** del
processo, non con un'istruzione al modello. Fix tecnici secondari applicati lungo la strada:
(a) stream-json bufferizza su pipe → redirigere su FILE e pollare (no `subprocess.PIPE`+thread
deadlock); (b) `transaction_id` nello stream è ESCAPED (`\"transaction_id\":\"...\"`) dentro un
tool_result serializzato → regex tollerante ai backslash; (c) kill on-transaction-open, non a
tempo fisso.

## Cavie throwaway create (cestinare a mano — Canva MCP non ha delete-design)

`DAHK9luj4-A` `DAHK9p-P0v8` `DAHK97ryHHg` `DAHK9xRiTZw` `DAHK98r-2Y0` `DAHK91MYSzE` `DAHK9z9Nomg`
`DAHK90FE9w4` `DAHK91laEUQ` `DAHK90bdQRU` `DAHK92qeIIQ` `DAHK92ORK9Q` `DAHK96s1EGY` `DAHK94b76GA`
`DAHK9-hjkMM` (master D4 CLOBBERATO) `DAHK9yIGWQM` `DAHK95Q7v1Q`
A4 probe cavie (2026-05-29): `DAHK-O9EwAs` `DAHK-MattYA` `DAHK-JKzDJ4` `DAHK-ZNiVBc` `DAHK-dgrCIs`
`DAHK-Tj6iLA` `DAHK-DIBVKA`

## Scar candidate (per .claude/rules/cicatrix-scars.md — da inserire dopo spec+impl)

> **ℹ️ INFO + REVERSAL: il muro "Canva MCP OAuth non sopravvive a `claude -p`" (cicatrix 2026-05-13)
> è caduto — headless canva-apply fattibile via step-0 ToolSearch (2026-05-29)**
>
> TRAUMA originale: 2026-05-13 decommissionato `wr2_canva_apply.py` headless perché project-scoped
> OAuth non si propagava allo spawn. Ripiego su AppleScript-GUI fragile.
> REVERSAL: Canva MCP ora claude.ai-hosted, raggiungibile in headless come deferred tool. 4 fasi di
> test isolati (read/write/commit + skill reale 3/3 + D1 immagini + D3 move + D4 race) provano il ciclo
> completo headless. 5 hardening richiesti (budget 900s, URL diretti, no-AskUserQuestion, graceful move,
> lease anti-race). D4 ha RICONFERMATO la cicatrix lease-watchdog: senza lease, 2 run mashano il master
> (`D4B P2D4A P2` verificato su disk).
> Reference: questo file + scripts/wr2_canva_desktop_apply.py + wr2_canva_lease_watchdog.py.
