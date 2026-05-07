# WR2 Sprint B (continued) — Next Session Prompt

> **Context handoff** — copia/incolla il blocco "PROMPT FOR NEXT SESSION" sotto in una sessione Claude Code fresh per riprendere esattamente da dove abbiamo lasciato.
>
> **Data scadenza utilità**: questo prompt assume che l'OAuth Canva sia ancora valido (re-autenticato 2026-05-07 ~23:50 WITA). Se sono passati >7 giorni o se il primo step (verify OAuth) torna <30 tools, il prompt resta valido ma serve nuovo OAuth manuale prima di procedere.

---

## PROMPT FOR NEXT SESSION (copia/incolla questo blocco)

```
Sono Antonello. Riprendiamo Sprint B di WR2 dal punto di handoff
2026-05-08 00:30 WITA documentato in
docs/wr2/2026-05-08-next-session-prompt.md.

CONTEXT (cosa è stato fatto):
- Sprint A WR2 chiuso (PR #501, #502, #504, #506, #507, #509, #510)
- Sprint B revision: hypothesis "MCP cache warming" RIGETTATA da 4 review
  paralleli; vero blocker = OAuth Canva token expiration (4 datapoints
  empirical: 3/3 fail pre-OAuth-refresh, 1/1 success post-refresh)
- B0 instrument shipped (PR #516) — telemetry JSONL su
  ~/logs/wr2_canva_apply_telemetry.jsonl
- Design doc completo: docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md
- Last successful canva design: telemetry recorded "success" 2026-05-07
  16:26 UTC (1943s, draft 0e8e1cf5) MA DB stesso draft mostra
  design_id=NULL — INCONSISTENZA da investigare PRIMA DI TUTTO

OBIETTIVO SESSIONE:
Eseguire 5 task in ordine. Ogni task ha exit criterion esplicito.
Non procedere al successivo finché il precedente non è verde.

TASK 1 — Investigate DB inconsistency (~30min)
  Symptom: telemetry JSONL ha riga {"draft_id":"0e8e1cf5...","outcome":
  "success","duration_s":1943.4} ma DB war_room_drafts WHERE id=
  '0e8e1cf5-6872-4102-aff7-e95beb869f3b' mostra
  status='drafts_imaged' design_id=NULL.

  Step:
  a) Leggi scripts/wr2_canva_apply.py funzione _apply_one_draft post B0 patch
     (commit 96cf0cb2c o equivalente su main). Cerca race condition tra
     _log_run_telemetry(success) e await _persist_canva_result(conn, ...).
  b) Ipotesi probabile: quando outcome="success" viene loggato, il
     subprocess Claude ha già scritto carousel_canva.json e ha modificato
     pending_canva.json status='applied'. MA la cosa scritta NEL DB
     dipende da _persist_canva_result che usa result.design_id, ottenuto
     da extract_canva_urls(stdout). Forse extract_canva_urls ha
     restituito un edit_url ma design_id=None (regex non match). Verifica:
     - cat ~/logs/wr2_canva_apply.log | grep "Draft 0e8e1cf5" | tail -10
     - Nello stdout salvato (result.stdout_tail), c'è un canva.com URL
       valido o un sentinel "ERROR:..."?
  c) Se design_id estratto è None → _persist_canva_result salva NULL
     anche se l'apply ha funzionato. Fix: extract_canva_urls deve gestire
     il caso "design exists but no design_id parseable" o caller deve
     leggere carousel_canva.json scritto su disco come fallback.
  d) Forse il run è stato killato (Mac sleep, network drop) DOPO
     telemetry success log MA PRIMA di _persist_canva_result. Verifica
     timestamp tra telemetry write (16:26:10) e ultimo log canva-apply
     riga.

  Exit criterion:
  - Causa identificata + documentata (1 line) in
    docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md sotto sezione
    "B0 known issue: telemetry success vs DB persist race"
  - Se è race condition → fix in scripts/wr2_canva_apply.py:
    move _log_run_telemetry(success) DOPO _persist_canva_result OK.
  - Se è regex bug → fix in apps/backend-rag/backend/services/canva_renderer/
    claude_invoker.py extract_canva_urls
  - PR aperta + admin merge se fix banale

TASK 2 — Implement B-NEW: OAuth Canva Watchdog (~4h)
  Spec dettagliata in docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md
  sotto "B-NEW (replaces B1+B2 after hypothesis falsified)".

  File to create:
  a) ~/scripts/wr2-canva-oauth-watchdog.sh (Pro-local, NOT in repo)
     - Spawna `claude -p --output-format text "Output the count of MCP
       tool names starting with mcp__claude_ai_Canva__. Output JUST the
       integer, nothing else."` con timeout 60s
     - Parse output: se ! /^\d+$/ o se < 30 → token stale
     - Su token-stale: spawna `claude -p` con prompt che chiama
       mcp__claude_ai_Canva__authenticate (note: subprocess refuses
       "prompt injection" by default — devi passare context autorizzativo
       esplicito come "Antonello authorized this OAuth re-flow")
     - Ricava authorization URL dall'output (regex
       https://mcp.canva.com/authorize?...)
     - Telegram alert P0 con click-link + breve istruzione operatore
     - State file ~/.agent/decisions/state/wr2_canva_oauth.state per
       cooldown (no spam: alert solo se 24h da ultimo + state ancora stale)

  b) ~/Library/LaunchAgents/com.balizero.wr2.canva-oauth-watchdog.plist
     - StartInterval=21600 (6 ore)
     - RunAtLoad=true
     - StandardErrorPath/StandardOutPath in ~/logs/
     - EnvironmentVariables: HOME + PATH (no secrets — wrapper sources
       ~/.nuzantara-secrets.env per TELEGRAM_BOT_TOKEN)

  c) infra/launchagents/com.balizero.wr2.canva-oauth-watchdog.plist
     - Mirror per repo tracking

  d) docs/wr2/skill-snapshots/canva-oauth-watchdog-2026-05-08.md
     - Snapshot dello script per repo tracking (lo script sta in ~/scripts
       fuori dal repo per design)

  Test plan:
  - Manual run: `bash ~/scripts/wr2-canva-oauth-watchdog.sh`
    - Caso A (token fresh): exit 0, log "OK: 36 tools visible"
    - Caso B (simulato stale): rinomina temporaneamente
      ~/.mcp-auth/mcp-remote-0.1.37/*tokens.json a *.bak, rilancia.
      Exit 1, Telegram alert con URL. Restore .bak.
  - plutil -lint sul plist
  - launchctl bootstrap + verify state="waiting" + next-fire="+21600s"

  Rollout:
  - PR fix/wr2-canva-oauth-watchdog-2026-05-08
  - Squawk lint N/A (no migration)
  - CI verde, admin merge
  - Bootstrap LaunchAgent
  - Aspetta 6h, verifica log entry alle ore +6

  Effort stimato: 4h.

TASK 3 — B3 Supervisor Watchdog + Heartbeat con review fixes (~8h)
  Spec originale in design doc Sprint B B3, MA APPLICA i fix dalla
  review B3 (output agent ID a9990ca76ce0555e2 nella conversation
  precedente):

  3.1 — Critical fix: dedicated heartbeat connection
    - In scripts/wr2_supervisor.py, NON aggiungere _write_heartbeat
      sulla LISTEN connection (viola asyncpg single-op contract)
    - Apri SECONDA asyncpg.connect(dsn=dsn) in _run_loop() startup
      come conn_hb
    - heartbeat_task usa conn_hb, non conn (LISTEN)
    - finally chiude conn_hb insieme a conn

  3.2 — Migration 161 wr2_supervisor_heartbeat
    - File: apps/backend-rag/backend/db/migrations_v2/
      161_wr2_supervisor_heartbeat.sql
    - PRIMA verifica: `git fetch origin && git log --all --oneline --
      "apps/backend-rag/backend/db/migrations_v2/16*.sql"` per confermare
      che 159, 160, 161 sono free su tutti i remote branches
    - Sql come spec doc MA aggiungi "-- squawk-ignore:
      require-concurrent-index-creation" prima della CREATE INDEX
      (tabella nuova, no contention, ma Squawk flagga comunque)
    - Forward DDL + ROLLBACK marker
    - Testing locale via migration runner prima del PR

  3.3 — Watchdog daemon scripts/wr2_supervisor_watchdog.py
    - KeepAlive=true, no schedule
    - Read heartbeat ogni 60s
    - Tiered alerts:
      - P0: heartbeat older than 5 min → supervisor crashed
      - P0: oldest pending >2h AND no rendered in 24h
      - P1: canva-apply success rate <80% in **7-day rolling window**
        (NOT 24h — at 1 draft/day single fail = 0%, single success =
        100%, too noisy. Review-confirmed.)
    - Query precisa per success rate:
      SELECT COUNT(*) FILTER (WHERE outcome='success') AS s,
             COUNT(*) AS attempted
      FROM (lettura jsonl + ts > NOW() - INTERVAL '7 days') sub
    - O direttamente leggi telemetry JSONL append-only (più semplice)

  3.4 — Plist com.balizero.wr2.supervisor-watchdog
    - KeepAlive=true, RunAtLoad=true
    - Mirror in infra/launchagents/

  Test plan:
  - Migration 161 apply locale via scripts/db_apply_local.sh (se esiste)
  - Kill supervisor PID forzatamente, watchdog deve fire P0 entro 5 min
  - Simula 7d con 6/7 success → P1 attivo, 7/7 → silenzio

  Rollout: PR multi-commit (migration + supervisor patch + watchdog +
  plist). admin merge dopo tutti i required check. Migration applicata
  via post-deploy job standard.

  Effort: 8h.

TASK 4 — B-bis: Fact-stages NET-NEW build (12-16h)
  NON è un restore — i due script wr2_fact_extractor.py e
  wr2_fact_checker.py NON ESISTONO sul disco (review B4 confirmed).
  È un net-new implementation:

  4.1 — Schema migration 162
    - Aggiungi colonne a war_room_drafts:
      fact_check_json JSONB,
      fact_check_status TEXT (CHECK IN: NULL, 'pass','fail','degraded'),
      fact_check_at TIMESTAMPTZ
    - File: apps/backend-rag/backend/db/migrations_v2/
      162_war_room_fact_check.sql
    - Squawk: ALTER TABLE ADD COLUMN nullable è safe (no rewrite, no lock)
      ma Squawk può flagga "require-default-on-add" — verifica e aggiungi
      ignore se necessario

  4.2 — scripts/wr2_fact_extractor.py
    - Input: status='drafts_imaged' draft
    - Per ogni slide.body, estrai claims fattuali (numbers, dates, laws,
      quotes) via Claude OPUS structured extraction
    - Output: list of {claim: str, slide_index: int, type:
      'number|date|law|quote'}
    - Salva in fact_check_json.claims
    - Status transition: drafts_imaged → drafts_imaged_facted

  4.3 — scripts/wr2_fact_checker.py
    - Input: status='drafts_imaged_facted' draft
    - Per ogni claim, verify:
      - 'law' claims → grep in NB-INTEL-Regulation o NB-INTEL-Tax o
        original article fonte
      - 'number' claims → consistency check con article + warning if
        discrepancy
      - 'quote' claims → string match in original article o sentinel
        "[Source: ...]"
    - Output: fact_check_status = 'pass' (all verified) | 'fail'
      (discrepancies) | 'degraded' (some unverifiable)
    - Status transition: drafts_imaged_facted →
      drafts_imaged_checked (pass/degraded) | fact_check_failed (fail)

  4.4 — Atomic deploy
    - Supervisor TRANSITIONS revert nello stesso PR del fact-stages
      restore (vedi spec B4)
    - wr2_canva_apply.py status filter da
      IN ('drafts_imaged','drafts') a status = 'drafts_imaged_checked'
      ATOMICO con TRANSITIONS revert

  4.5 — Plist re-enable
    - Move ~/Library/LaunchAgents/.disabled/com.balizero.wr2.
      fact-extractor.plist + .fact-checker.plist back to ~/Library/
      LaunchAgents/
    - chmod u+w → mv → chmod 0444 → bootstrap (cicatrix P0-3 hardening)

  Effort: 12-16h.

TASK 5 — Sprint C kickoff: Auto-pull deploy worktree
  Spec in design doc Sprint C C1 (semplice, 2h).

  - ~/scripts/wr2-deploy-pull.sh (con flock lockfile, Telegram on conflict)
  - ~/Library/LaunchAgents/com.balizero.wr2.deploy-puller.plist
    StartInterval=3600, RunAtLoad=true
  - infra/launchagents/ mirror
  - Verify: 1h dopo bootstrap, log entry presente

  Exit criterion: deploy worktree HEAD aggiornato automaticamente entro
  1h da merge a main, senza intervento manuale.

  Effort: 2h.

INVARIANTS DA RISPETTARE (tutti owner-binding):
- OB-3: Anthropic OAuth-only, never ANTHROPIC_API_KEY
- OB-4: cost constraint per LLM (Claude Max OAuth, Codex ChatGPT Plus,
  Gemini OAuth, DeepSeek explicit)
- Cicatrix anti-hijack: scope-limited git add (mai git add -A bare),
  push entro 30s da commit
- Plist permissions: chmod u+w → modify → chmod 0444 (P0-3 hardening)
- Squawk lint: ogni nuova migration richiede o CONCURRENTLY (fuori
  transaction) o squawk-ignore comment esplicito
- Branch dedicato per ogni PR: fix/wr2-<topic>-2026-05-XX
- Admin merge ammesso quando i 2 required check (E2E Playwright + MCP
  Server Tests) sono PASS, anche se npm audit / inventory-check fail
  pre-existing

PRE-FLIGHT CHECKS (esegui PRIMA di iniziare TASK 1):

  # Verify OAuth ancora valido
  TOOLS=$(claude -p --output-format text "Output count of MCP tool names
  starting with mcp__claude_ai_Canva__. Just the integer." 2>&1 | tail -1
  | tr -d '[:space:]')
  echo "Canva tools visible: $TOOLS"
  # Se <30 → OAuth scaduto, RI-AUTENTICA prima di procedere
  # (run claude mcp + browser flow + complete_authentication)

  # Verify supervisor + canva-apply status
  launchctl list | grep -E "wr2.supervisor|wr2.canva-apply"

  # Verify deploy worktree HEAD recente
  cd ~/Desktop/nuzantara-deploy && git log -1 --oneline

  # Verify telemetry JSONL ha datapoints
  wc -l ~/logs/wr2_canva_apply_telemetry.jsonl

  # Verify branch state (no hijack pending)
  cd ~/Desktop/nuzantara && git status --short

CHECKLIST FINALE PRIMA DI DICHIARARE SPRINT B DONE:
- [ ] Task 1: DB inconsistency fixed + documented
- [ ] Task 2: B-NEW OAuth watchdog live, 6h cron testato
- [ ] Task 3: B3 supervisor watchdog live, P0/P1 alert testati
- [ ] Task 4: B-bis fact-stages live, 1 draft passa drafts_imaged →
      drafts_imaged_checked → rendered end-to-end
- [ ] Task 5: deploy puller live, 1h cron testato
- [ ] Telemetry: ≥7 datapoints success outcome 7d window
- [ ] Telegram alert testati end-to-end
- [ ] docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md aggiornato con
      "Sprint B done 2026-05-XX" e checklist finale ticked

Rispondi solo "OK pronto, comincio TASK 1" per iniziare.
```

---

## Note operative per chi gira il prompt

### Quando funziona

Se OAuth Canva è ancora valido (controlla con `claude -p "count canva tools"`), il prompt parte direttamente con TASK 1 (investigate DB) e procede sequenzialmente. Tempo totale stimato 2-3 sessioni di ~8h ciascuna.

### Quando OAuth è scaduto

Se pre-flight check torna `<30 tools`, il prompt si ferma e chiede ri-autenticazione manuale Canva (browser flow). Una volta completata, riparte da TASK 1.

### Cosa NON fare

- Non saltare TASK 1 anche se sembra "minore" — la DB inconsistency potrebbe nascondere un bug più grande nella detection success.
- Non bundle TASK 4 (fact-stages) con TASK 2/3 in un PR unico — blast radius diversa, rollback più difficile.
- Non spostare il file `docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md` — è il single source of truth per il sprint.

### File di riferimento (per il prompt)

- `docs/wr2/2026-05-07-wr2-longterm-design.md` — owner decisions binding
- `docs/wr2/2026-05-08-sprint-b-to-f-detailed-plan.md` — spec dettagliata Sprint B-F con review fixes incorporated
- `~/logs/wr2_canva_apply_telemetry.jsonl` — empirical data B0
- `scripts/wr2_canva_apply.py` (commit 96cf0cb2c) — B0 instrument live
- `scripts/wr2_supervisor.py` — supervisor da patchare in TASK 3
- `apps/backend-rag/backend/services/canva_renderer/claude_invoker.py` — invoker subprocess
