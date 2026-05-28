---
date: 2026-05-29
domain: operations
type: spec
status: iter-2-panel-amended-pending-impl
panel_verdict: APPROVE_WITH_AMENDMENTS 3/3 (Gemini + Codex GPT-5.5 + DeepSeek V4 Pro), 2026-05-29
panel_artifacts: /tmp/canva-headless-panel/{gemini,codex,deepseek}.md
feasibility_study: research/operations/2026-05-29-wr2-canva-headless-feasibility.md
target_files:
  - scripts/wr2_canva_desktop_apply.py
  - ~/.claude/skills/canva-apply.md (+ infra/claude-skills/canva-apply.md mirror)
  - infra/launchagents/com.balizero.wr2.canva-apply.plist
---

# SPEC — Sostituire l'attuatore AppleScript-GUI con `claude -p` headless

## Obiettivo

Eliminare la fragilità AppleScript+app-GUI-aperta da `wr2_canva_desktop_apply.py`, sostituendo il
blocco di automazione GUI con una subprocess `claude -p` headless che invoca lo skill `/canva-apply`.
Il `canva_pending.json` e lo skill restano invariati nel ruolo; cambia solo **come** lo skill viene
eseguito. Fondamenta empiriche: feasibility study 2026-05-29 (4 fasi di test isolati).

## Cosa NON cambia

- `pending_builder.build_canva_pending()` — invariato.
- Lo schema `canva_pending.json` — invariato.
- Il flusso DB (fetch drafts → build pending → persist result → status=rendered) — invariato.
- Il pattern "inietta skill-body come prompt naturale" (righe 391-416) — già corretto, il test
  headless usa esattamente questo (Claude non riceve `/canva-apply` ma il body dello skill).

## Cosa cambia (3 modifiche)

### M1 — `wr2_canva_desktop_apply.py`: sostituire il blocco GUI con subprocess headless

ELIMINARE: `_run_applescript`, `_claude_is_running`, `_launch_claude`, `_focus_claude_and_send_command`,
il retry-envelope 5×, `PRE_KEYSTROKE_GRACE_SEC`, tutta la logica pbcopy/pbpaste/frontmost-verify
(righe ~201-315 + 428-457).

SOSTITUIRE con una funzione `_run_canva_apply_headless(command_text) -> bool` che lancia:

```
claude -p "<command_text>" --dangerously-skip-permissions --output-format stream-json --verbose
```

con `subprocess.run(..., timeout=WR2_HEADLESS_TIMEOUT_SEC)`, stdin chiuso (`</dev/null` o
`stdin=DEVNULL`), stdout catturato su file JSONL per audit. Niente app GUI, niente focus, niente grace.

### M2 — skill `/canva-apply`: step-0 ToolSearch + rinforzo no-AskUserQuestion

- **Step -2 ToolSearch idempotente** all'inizio: "Se i tool `mcp__claude_ai_Canva__*` non sono già
  disponibili, caricali via `ToolSearch select:mcp__claude_ai_Canva__<lista>`. In interattivo è no-op."
  (In headless i tool sono deferred, non auto-load — verificato Test 1.)
- **Rinforzo no-AskUserQuestion**: lo STEP 0 di validazione attuale può chiamare `AskUserQuestion`
  su input "sospetti" (folder bogus, topic "do not publish", slides vuoto). In headless questo
  **blocca tutto** (D3 pass-1). Aggiungere direttiva hard: "NEVER call AskUserQuestion. On any
  ambiguity: pick the safe default, log it, proceed. The existence of canva_pending.json with
  status=pending is full consent."

### M3 — Allineare il contratto di output (carousel_canva.json)

DISCREPANZA da risolvere: lo skill v3 attuale persiste solo nel `canva_pending.json` (`status=applied`

- `design_id`), NON scrive più `carousel_canva.json`. Ma `wr2_canva_desktop_apply.py` polla
  `carousel_canva.json` (righe 323-349, 460). Due opzioni (decisione panel):

* (a) ripristinare la scrittura di `carousel_canva.json` come Phase D dello skill (retro-compat), oppure
* (b) cambiare il reader: leggere il risultato dal `canva_pending.json` aggiornato (`status=applied`
  - `design_id`), eliminando il file separato.
    Raccomandazione PRELIMINARE: (b) — single source of truth, meno file, meno race.
    **MA grep 2026-05-29 trova altri consumer reali di `carousel_canva.json`**: `scripts/wr2_canva_reconcile.py`
    (+ `scripts/tests/test_wr2_canva_reconcile.py`) e `apps/war-room/scripts/upload_waste_to_tigris.py`.
    Quindi (b) NON è gratis — eliminare il file romperebbe reconcile + upload-waste. Opzione (a) ripristino
    scrittura è il path low-risk. Decisione finale al panel; se (b), serve anche refactor di quei 2 consumer.

## 5 hardening (dai finding empirici del feasibility study)

| #   | Finding                                                                         | Requisito nella spec                                                                                                                                                                                                                                                                                           |
| --- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H1  | ciclo ~250s ma cold-start può sforare 540s, lascia transaction dangling         | `WR2_HEADLESS_TIMEOUT_SEC` default **900** (margine 3.6×). Su timeout: log + Telegram + NON marcare draft come rendered.                                                                                                                                                                                       |
| H2  | `upload-asset-from-url` non segue redirect 302                                  | `pending_builder` / image_generator devono produrre **URL diretti** (no shortener). Verificare a monte.                                                                                                                                                                                                        |
| H3  | AskUserQuestion blocca headless                                                 | M2 — direttiva hard no-AskUserQuestion.                                                                                                                                                                                                                                                                        |
| H4  | move su folder invalido → graceful-degrade (2 retry, procede, dup non spostato) | Già OK nello skill. Il reader deve accettare un draft `rendered` anche se il dup non è nella folder (warn, non fail).                                                                                                                                                                                          |
| H5  | **sibling-race corrompe il master** (D4: `D4B P2D4A P2` su disk)                | **LEASE OBBLIGATORIO**: prima di lanciare headless, acquisire lease sul `template_design_id` via il registry `wr2_canva_lease_watchdog`. `MAX_DRAFTS_PER_RUN=1` (già presente) NON basta — protegge intra-run, non cross-run/cross-machine. Senza lease, due cron tick (o Pro+Mini) possono mashare il master. |

## Cutover graduale (no big-bang)

1. Aggiungere `WR2_CANVA_ACTUATOR` env: `desktop` (default, AppleScript attuale) | `headless` (nuovo).
2. Shippare M1/M2/M3 dietro il flag `headless`, lasciando il path `desktop` intatto come fallback.
3. Validare `headless` in shadow su qualche draft reale (operator-supervised).
4. Quando stabile: flip default a `headless`, deprecare il blocco AppleScript in una PR successiva.

## Rischi residui da chiedere al panel

- M3: ci sono altri consumer di `carousel_canva.json`? (grep richiesto pre-impl)
- H5: il lease registry copre cross-machine (Pro+Mini)? il TTL del lease (>900s) vs durata run?
- Il `--dangerously-skip-permissions` headless: accettabile in cron? (lo skill è deterministico,
  pre-autorizzato dal pending; ma è un `--dangerously-` flag — il panel deve pesarlo).
- Idempotenza su crash a metà: se headless muore dopo Phase A (master editato) ma prima del duplicate,
  il prossimo run trova il pending ancora `pending`? Phase -1 valida + transaction fresca supersede,
  ma il master resta editato (non blank) → Phase 0 lo ripulisce. Verificare il caso con un test.

## Emendamenti panel 4-LLM (iter-2, 2026-05-29) — APPROVE_WITH_AMENDMENTS 3/3

Gemini + Codex GPT-5.5 + DeepSeek V4 Pro. 6 emendamenti in convergenza piena (3/3) + 2 unici.
TUTTI obbligatori prima dell'implementazione. Sostituiscono/rinforzano gli hardening H1-H5 sopra.

| #   | Emendamento                                | Voti           | Cosa cambia rispetto alla spec iter-1                                                                                                                                                                                                                                                                                                                                         |
| --- | ------------------------------------------ | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | **Lease distribuito + fenced**             | 3/3            | NON file locale. `pg_advisory_lock` / `INSERT…ON CONFLICT` su `template_design_id` con `run_id`+`host_id`+fencing token. **TTL breve ~120s + heartbeat** (NON ≥900s: un run morto a 10s bloccherebbe la pipeline 14 min — "lease of the dead"). **Release garantito in `finally` + signal trap** su OGNI exit path. Sostituisce H5.                                           |
| A2  | **Scope MCP ristretto**                    | 3/3            | `--dangerously-skip-permissions` nudo è blast-radius: prompt-injection in alt-text slide → `rm -rf`/`delete_design`. Usare `--mcp-config` override che carica SOLO `mcp__claude_ai_Canva__*`+ToolSearch, O permission-allowlist. + **hash dello skill body** per detectare edit silenziosi. Rinforza M1.                                                                      |
| A3  | **M3 → opzione (c)**                       | 3/3            | L'**attuatore Python** scrive `carousel_canva.json` dal pending aggiornato dopo il successo. Skill invariato, reconcile+upload-waste soddisfatti, zero refactor, zero LLM-writes-file. Risolve M3.                                                                                                                                                                            |
| A4  | **Test dangling-transaction OBBLIGATORIO** | 3/3            | Gap non testato: Canva permette `start-editing-transaction` dopo processo killato mid-transaction? Se lo blocca → timeout cascata in ore di pipeline morta. Test: kill headless mid-transaction → rilancia subito. Su timeout: kill process-group + quarantena template + Telegram. Rinforza H1.                                                                              |
| A5  | **Pre-flight quota-check**                 | 3/3            | $2.49-eq/run su quota MAX. 12/day≈$900/mese-eq, 24/day≈$1800/mese-eq, può esaurire la finestra 5h → outage 3am + locka l'operatore umano. Pre-flight usage-check + defer + backoff. Se sfori → rischio fallback API a pagamento (viola zero-paid-API). NUOVO hardening.                                                                                                       |
| A6  | **Inversione: duplica-poi-edita**          | 3/3            | **Rifondazione skill**: duplicare il master PRISTINO prima, editare sul DUPLICATO. Crash → master intatto, duplicato orfano garbage-collected. Neutralizza in un colpo: corruzione master, parte della sibling-race (ogni run sul proprio duplicato), dangling-transaction sul master condiviso. È il finding più prezioso del panel. Sostituisce le Phase 0/A/C dello skill. |
| A7  | no-AskUserQuestion: default hardcoded      | DeepSeek       | Enumerare i casi D3 (folder bogus/topic/slides vuoto) con fallback ESATTO nel testo skill, non "pick safe default" generico. Rinforza M2/H3.                                                                                                                                                                                                                                  |
| A8  | ToolSearch fail-closed                     | Codex+DeepSeek | Attuatore verifica che i tool Canva compaiano nei primi messaggi stream-json → abort hard, MAI marcare rendered. NUOVO guard.                                                                                                                                                                                                                                                 |

**Nota su A6 (inversione duplica-poi-edita)**: riduce drasticamente il peso di A1. Se ogni run edita un
proprio duplicato e mai il master condiviso, la sibling-race non può più corrompere il master — il lease
serve solo a serializzare la _lettura_ del master pristino per la duplicazione (operazione breve), non
l'intero ciclo di edit. Da valutare in fase di plan se A6 rende A1 un lock leggero invece di un lease lungo.

## Prossimo step

Spec iter-2 panel-amended. Prossimo: `writing-plans` per il piano d'implementazione che incorpora A1-A8,
con il test A4 (dangling-transaction) come PRIMO gate empirico prima di scrivere l'attuatore. Cutover
graduale dietro `WR2_CANVA_ACTUATOR=desktop|headless` confermato dal panel.
