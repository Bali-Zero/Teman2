# Resume prompt — EvoSkill Phase 1 wiring (Tasks #21-#27)

## Contesto in 30 secondi

Phase 0 EvoSkill auto-evolving agent-library è SHIPPED su main 2026-05-18:

- **PR #736 MERGED** (rebase, merge SHA `a1f383ced`). 4 round panel review
  Gemini+Codex+DeepSeek. Cicatrix lesson "Codex empirical grep > altri
  panelist" applicata 5 volte (3 BLOCKING R3 + 2 BLOCKING R4 tutti catched).

- **Phase 1 branch già aperto**: `feat/agent-library-evoskill-phase1-2026-05-18`
  in worktree `~/Desktop/nuzantara-wt-evoskill-phase1/`. Base `origin/main`
  HEAD `42d375e8f`. 2 commit già pushati:
  - `3e23e418e` Task #19 `.known-limitations-v1.md` (24 row L1-L24)
  - `73b096ac0` Task #20 redactor + tests (35/35 PASS in 0.30s)

- **Spec v5** già su main via PR #734 mergiata separatamente.

## Cosa fare in questa sessione

Eseguire le 7 task Phase 1 rimanenti (#21-#27). Ordine logico ottimizzato
per dipendenze:

### Task #21 — `agent-library/config/evolver.toml` con schema CORRETTO

**Critical** — Panel R2 Codex caught: l'`evolver.toml` v5-spec draft
usava sezioni `[provider][loop][budget]` ma upstream EvoSkill
`load_config()` (`vendor/evoskill/src/cli/config.py:159`) richiede
`[harness][evolution][dataset][scorer]`. Template upstream init:
`vendor/evoskill/src/cli/commands/init.py:98+110+125+140`.

Pre-flight obbligatorio:

```bash
cd ~/Desktop/nuzantara-wt-evoskill-phase1/vendor/evoskill && \
  cat src/cli/config.py | sed -n '155,220p'  # load_config + Config dataclass
cat src/cli/commands/init.py | sed -n '90,170p'  # template default sections
```

Decisioni da prendere:
- `[harness]`: `name = "deepseek"` (sanctioned per CLAUDE.md)
- `[scorer]`: `model = "deepseek-v4-pro"`, NON `claude-sonnet-4-6` (L9 fix)
- `[evolution]`: `max_iterations=10`, `frontier_k=3`, `holdout_fraction=0.2`
- `[dataset]`: TBD — Phase 1 first-run usa dataset sintetico (esempi
  da agent-library/02-patterns.md + 03-lessons.md come seed) OPPURE
  un dataset placeholder che produce zero proposals al primo run

Effort: ~1h. NO test unit (è config, smoke = `uv run evoskill run --config
... --dry-run` per validare load_config accetta).

### Task #22 — patch `cli/shared.py` `call_llm` + `infer_provider` deepseek branch

**Critical** — Panel R2 + R3: `infer_provider("deepseek-v4-pro")` cade
nel fallback `return "anthropic"` (line 58); `call_llm()` ha branch per
anthropic/openai/openrouter/google ma NON deepseek.

Files target:
- `vendor/evoskill/src/cli/shared.py:41-58` — `infer_provider`: aggiungi
  `if model.startswith("deepseek"): return "deepseek"` PRIMA del
  fallback anthropic
- `vendor/evoskill/src/cli/shared.py:77-148` — `call_llm`: aggiungi
  branch `if provider == "deepseek":` con httpx async POST a
  `https://api.deepseek.com/v1/chat/completions`, max_tokens=16,
  response.choices[0].message.content

Aggiorna `vendor/evoskill/UPSTREAM.md` §4 per documentare la patch.
Aggiorna `vendor/evoskill/SMOKE.md` Gate 4c (test infer_provider("deepseek-v4-pro") == "deepseek" + call_llm("deepseek", ...) raises no ImportError, just NotImplementedError for missing API key in test env).

Effort: ~1.5h. Test unit: scripts/test_call_llm_deepseek.py (mock httpx
async respond).

### Task #23 — real DeepSeek executor (Phase 0 stub → real impl)

**Most complex task** — Phase 0 lascia `vendor/evoskill/src/harness/deepseek/executor.py`
come `NotImplementedError` stub. Phase 1 implementa:

1. `execute_query(options, query)` async — POST
   `api.deepseek.com/v1/chat/completions` con messages list
   `[{role:system, content:options["system"]}, {role:user, content:query}]`,
   max_tokens=options.get("max_tokens", 8000), `reasoning_effort` da
   options, `response_format` JSON schema via Pydantic
   `options["schema"]`. Retry 30s→60s→120s pattern (vedi
   `src/harness/agent.py:_run_with_retry` linee ~198-232).

2. `parse_response(messages, response_model, get_options)` — estrae
   `messages[0]["choices"][0]["message"]["content"]`, valida via
   `response_model.model_validate_json(content)`, ritorna dict
   AgentTrace-compatible: `uuid, session_id, model, duration_ms,
   total_cost_usd (da response.usage), num_turns=1, usage dict,
   result, is_error, output, parse_error, raw_structured_output,
   messages`.

Riferimento contract: leggi
`vendor/evoskill/src/harness/agent.py:AgentTrace` (line ~43) + qualsiasi
existing executor (goose/executor.py o opencode/executor.py) per il
shape esatto.

Aggiorna UPSTREAM.md §7 (deepseek harness): "Phase 0 stub → Phase 1
real impl, commit `<sha>`".

Aggiorna SMOKE.md Gate 6: ora deepseek `execute_query` deve RAISE su
missing `DEEPSEEK_API_KEY` env (chiaro errore, non NotImplementedError).

Effort: ~2h. Test unit con httpx mock async.

### Task #24 — `scripts/agent-library-evolver-run.sh` wrapper

Wrapper invocato dal LaunchAgent Sunday 03:00 WITA. Pipeline:

1. Source `SECRETS_FILE` (default `~/.nuzantara-secrets.env`).
   **Reject `/dev/null` o file vuoto** (L20 panel finding R1).
2. Verifica `DEEPSEEK_API_KEY` non vuoto, altrimenti fail-closed.
3. PG advisory lock single-flight (`pg_try_advisory_lock`).
4. Context gathering: `mem query "successo|failure" --last 7days` +
   `git log --since=7days` + cat `.claude/rules/cicatrix-scars.md`.
5. **MANDATORY pipe `python3 scripts/_redact_pii.py`** (Symbiosis Law 2).
6. `uv run evoskill run --config agent-library/config/evolver.toml`
   con `BUDGET_USD` env exported.
7. Post-run parse `telemetry.json`: `total_cost_usd <= BUDGET_USD`,
   else fail-closed + Telegram alert.
8. Run `_evidence_lint.py` (Task #25) su proposals dir.
9. Run `_entailment_check.py` (Task #25) su passed evidence.
10. Se ≥1 proposal passed both gates, esegui
    `scripts/agent-library-evolver-propose-pr.sh` (creato in Phase 0,
    non necessita modifiche).
11. Telegram alert chat_id 1125336968 con summary.

File template: `vendor/evoskill/SMOKE.md` Phase 0 wrapper era stub —
Phase 1 lo rimpiazza completamente. Riferimento spec §"Architecture
(v1 — minimum viable)" linee ~145-241 del design doc.

Effort: ~1.5h. NO test unit (bash). Smoke: `BUDGET_USD=0.10 bash
scripts/agent-library-evolver-run.sh --dry-run` (aggiungere flag dry-run).

### Task #25 — `scripts/_evidence_lint.py` + `_entailment_check.py`

**Evidence linter (Step 3a spec)**:
- Legge `agent-library/config/evidence-rules.yaml` (creato in Phase 0
  ma scope-narrow merge l'ha droppato — ricrealo).
- Per ogni SKILL.md in proposals/YYYY-MM-DD/, applica ogni rule:
  - `file_line_ref`: regex match → check file exists + line in range
    (`os.path.exists` + `wc -l`)
  - `commit_hash`: `git rev-parse <hash>` returncode == 0
  - `external_url`: httpx HEAD 2s timeout, status 2xx/3xx
  - `memory_file_ref`: file existence
  - `cicatrix_scar_ref`: grep `.claude/rules/cicatrix-scars.md`
- **FTS5 BM25 dedup** vs `agent-library/02-patterns.md` +
  `03-lessons.md`. Reject if top match score < 1.5.
- Output: `proposals/YYYY-MM-DD/passed-existence/` vs `rejected/`.

**Entailment checker (Step 3b spec, cross-vendor isolation)**:
- Per ogni proposal che ha passato 3a, estrai citation snippets,
  applica `_redact_pii.py` (MANDATORY — panel R3 L21 fix), poi POST a
  `gemini --print "Does the cited content support the claim? YES/NO"`.
- Fallback NB-1 (UUID `38a99d22-c2ec-4d18-9bbc-86fa4c1d72cb`) via
  `mcp__notebooklm-mcp__notebook_query` se Gemini 429.
- Output: `proposals/YYYY-MM-DD/passed/` (passed both gates).

Effort: ~2h. Test unit: mock httpx + mock subprocess `git` / `gemini`.

L10 fix in evidence-rules.yaml: `file_line_ref` regex
`\.[a-zA-Z0-9]+` → `(?:\.[a-zA-Z0-9]+)?` per supportare
`Makefile:12` e `Dockerfile:5` extensionless.

### Task #26 — bootstrap LaunchAgent plist + smoke first run

Phase 0 ha scritto `infra/launchd/com.balizero.agent-library-evolver.weekly.plist`
ma NON bootstrappato. Phase 1:

1. **Copy from repo to ~/Library/LaunchAgents/** (repo è source of truth
   per cicatrix scar 2026-04-29 plist corruption — eviti drift).
2. `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.agent-library-evolver.weekly.plist`
3. **Smoke manual trigger**: `BUDGET_USD=0.10 launchctl start
   com.balizero.agent-library-evolver.weekly`. Observe Telegram alert
   + telemetry.json + PR draft (se Phase 1 wiring funziona end-to-end).
4. Se Phase 1 wiring crashes → bootout, fix, re-bootstrap. Phase 2 (4
   weekly runs auto) dopo questa smoke verde.

L11 fix: cambia default telemetry path da `/tmp/agent-library-evolver`
a `~/.agent/decisions/agent-library-evolver/telemetry` con `mkdir -m 0700`.

Effort: ~0.5h (escluso debug se smoke fail).

### Task #27 — 4-LLM panel pre-merge review

Antonello rule 2026-05-13: panel BEFORE merge di qualunque PR
spec-bearing. Dispatch:

1. Compose bundle `/tmp/pr-phase1-panel-review/` con:
   - 01-spec-v5.md (current main version)
   - 02-known-limitations-v1.md (Task #19 result)
   - 03-redaction-rules.yaml (Task #20)
   - 04-redact_pii.py (Task #20)
   - 05-evolver.toml (Task #21)
   - 06-cli-shared.py patch (Task #22)
   - 07-deepseek-executor.py (Task #23)
   - 08-evolver-run.sh (Task #24)
   - 09-evidence_lint.py (Task #25)
   - 10-entailment_check.py (Task #25)
   - 11-plist + smoke evidence (Task #26)
2. Prompt: "review Phase 1 wiring for Phase 0 known-limits L2-L13 +
   any new BLOCKING regression. Hard rule: NO call_llm via paid
   Anthropic, no anthropic in venv (verify uv pip list), L19 iban
   strict no false-positive on ALL CAPS words, etc."
3. Dispatch Gemini + Codex + DeepSeek parallel via background.
4. Verifica empiricamente OGNI Codex BLOCKING (lesson: Codex empirical
   > altri panel su pattern empirici — verified 5x in Phase 0).
5. Quorum 3/3 MERGE_READY → `gh pr merge --rebase --delete-branch
   --auto`. Quorum 2/3 con Codex BLOCKING empirically vero → fix poi
   re-panel. NO panel R5 sul stesso PR (cicatrix cap).

Effort: ~1.5h+ iterazioni.

## Pre-flight obbligatorio (5 minuti, NON skippare)

```bash
# 1. Machine + git state
echo "Machine: $(whoami)@$(hostname)" && \
  cd ~/Desktop/nuzantara-wt-evoskill-phase1 && \
  git status --short && git log --oneline -5

# 2. Verifica PR Phase 0 ancora MERGED + nessun revert
gh pr view 736 --json state,mergedAt --jq '"\(.state) merged=\(.mergedAt)"'

# 3. Phase 0 artifacts on disk
ls vendor/evoskill/src/harness/deepseek/{__init__,options,executor}.py
ls agent-library/proposals/.known-limitations-v1.md
ls scripts/_redact_pii.py scripts/test_redact_pii.py
ls agent-library/config/redaction-rules.yaml

# 4. Redactor tests still pass
python3 -m pytest scripts/test_redact_pii.py -q --tb=no

# 5. Smoke evoskill --help still OK
cd vendor/evoskill && uv run evoskill --help | head -3 && cd -

# 6. AST scan still 0 violations
python3 -c "
import ast, pathlib
v=[]
for py in pathlib.Path('vendor/evoskill/src').rglob('*.py'):
    t=ast.parse(py.read_text())
    for n in ast.walk(t):
        if isinstance(n,ast.Import):
            for a in n.names:
                if a.name in ('anthropic','claude_agent_sdk'): v.append(str(py))
        elif isinstance(n,ast.ImportFrom):
            if (n.module or '') in ('anthropic','claude_agent_sdk'): v.append(str(py))
print('AST PASS' if not v else 'FAIL: '+str(v))
"

# 7. Memorie chiave
mem query "EvoSkill Phase 1" | head -5
mem query "PR #736" | head -3
mem query "Codex empirical grep" | head -3
```

## Lezioni operative load-bearing (importance 9-10, già in memory)

1. **Errare è umano, allucinare è diabolico** — mai citare tool output
   senza eseguirlo in this turn. Verify-not-trust empiricamente ogni
   panel finding prima di applicare fix. `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/lessons_hallucinating_tool_output_is_diabolical.md`

2. **Commit + push spec/code IMMEDIATAMENTE** al primo write. Anti-
   sibling-cleanup wipeout. Cf. PR #721 worktree-eaten 2 volte mid-
   session.

3. **Codex empirical grep > Gemini+DeepSeek synthesis** su pattern
   empirici. Phase 0 ha confermato 5 volte: R3 (anthropic transitive
   browser-use + call_llm anthropic auth path + spec overpromise) + R4
   (Daytona/Docker env-forward + doc drift). Sempre verify Codex
   BLOCKING empirically, ANCHE quando Gemini+DeepSeek convergono
   MERGE_READY.

4. **Pre-commit hook prettier+ruff è blocker pesante** — esegui
   `npx prettier --write <staged>` prima del commit; ruff su 600+
   file pre-esistenti di main triggers fail per codice non mio →
   usa rebase invece di merge per evitarlo.

5. **Branch dietro main → rebase, NON merge** — il merge commit
   stagea TUTTI i file di main, pre-commit hook li valida tutti
   (ruff fail su 626 file pre-esistenti). Rebase mantiene il branch
   lineare e il pre-commit valida solo i miei commit.

6. **Cap panel review a R3-R4 max** — cicatrix lesson "divergent
   panel = STOP signal". Se R4 ancora NEEDS_FIX su un PR, escalation
   ad Antonello.

7. **NO claude-agent-sdk / anthropic / ANTHROPIC_API_KEY ANYWHERE**:
   no import, no dep transitive (uv pip show controlla Required-by),
   no env forward Daytona/Docker, no auth lookup PRIMA del raise.
   Defense in depth: provider_auth hard-deny + call_llm raise FIRST +
   pyproject removal + AST gate.

## File chiave da leggere PRIMA di iniziare (in quest'ordine)

1. `~/Desktop/nuzantara/CLAUDE.md` — global rules (no Anthropic paid API)
2. `~/.claude/CLAUDE.md` — global user rules + Multi-LLM cascade
3. `~/Desktop/nuzantara-wt-evoskill-phase1/agent-library/proposals/.known-limitations-v1.md`
   — 24-row checklist L1-L24, ogni Phase 1 task addresses 1+ row
4. `~/Desktop/nuzantara-wt-evoskill-phase1/docs/superpowers/specs/2026-05-17-agent-library-evoskill-design.md`
   §"Phase 0" + §"Phase 1" sections (rewritten in commit `e2e950c75`)
5. `~/Desktop/nuzantara-wt-evoskill-phase1/vendor/evoskill/UPSTREAM.md`
   §1-§7 diff list vs upstream v1.1.0
6. `~/Desktop/nuzantara-wt-evoskill-phase1/vendor/evoskill/SMOKE.md`
   — 6 gate Phase 0, ogni Phase 1 task NON deve regressare nessuno
7. `~/Desktop/nuzantara-wt-evoskill-phase1/scripts/_redact_pii.py` —
   il pattern di pass-ordering che TUTTI gli altri Phase 1 script
   devono seguire quando invocano LLM esterni

## Decisioni già locked (NON ri-discutere)

- Worktree path: `~/Desktop/nuzantara-wt-evoskill-phase1/`
- Branch: `feat/agent-library-evoskill-phase1-2026-05-18`
- Executor: DeepSeek V4 Pro API (`deepseek-v4-pro`, NON
  `deepseek-reasoner` deprecated 2026-07-24, NON
  `deepseek-chat` deprecated stesso)
- Entailment verifier: Gemini 3.1 Pro free OAuth (cross-vendor
  isolation), fallback NotebookLM NB-1
- BUDGET_USD prod: 1.00, smoke: 0.10, env override sempre wins
- Telegram chat_id: 1125336968 (owner)
- Schedule: Sunday 03:00 WITA (StartCalendarInterval Weekday=0 Hour=3)
- Telemetry default path: `~/.agent/decisions/agent-library-evolver/telemetry`
  (L11 fix, NOT `/tmp/`)
- Pass ordering redactor: pass1 (identifier+internal+WhatsApp+bank) →
  pass2_team_first (team emails+phone) → pass3_generic (client email+
  IBAN+SWIFT) → pass4_dynamic (CRM names da PG)
- evolver.toml schema: `[harness][evolution][dataset][scorer]` (NOT
  v5-draft `[provider][loop][budget]` — incompatibile con upstream
  `load_config()`)

## Modalità

L2 autonomous ops (commit+push+PR draft OK, NO auto-merge senza
review umana). Lingua italiano colloquiale con Antonello.

## Prompt completo (copia-incolla in nuova sessione)

```
Ciao Claude, riprendiamo Phase 1 EvoSkill da Task #21 (evolver.toml
schema corretta).

Worktree: ~/Desktop/nuzantara-wt-evoskill-phase1/
Branch: feat/agent-library-evoskill-phase1-2026-05-18
2 commit già pushati (Task #19 + #20). 7 task rimanenti (#21-#27).

Leggi PRIMA il file
~/Desktop/nuzantara/docs/sessions/2026-05-19-resume-evoskill-phase1.md
per pre-flight + lezioni operative + ordine task.

Esegui pre-flight (5 step bash), poi inizia da Task #21 a meno che io
indichi diversamente. Modalità L2 autonomous (commit+push OK, NO
auto-merge senza panel pre-merge Task #27).

Lingua italiana colloquiale con me. Hard rule: NO anthropic SDK / API
key / env forward anywhere. Empirical verify ogni Codex panel finding.

Vai.
```

## Cosa NON dimenticare

- `agent-library/config/evolver.toml` deve essere `[harness][evolution]
  [dataset][scorer]` schema (NON v5-draft sections — incompatibile con
  upstream `load_config()`)
- `cli/shared.py:infer_provider` fallback at line 58 ritorna
  `"anthropic"` per default — patch deve mettere deepseek branch
  PRIMA del fallback (L9)
- DeepSeek executor `execute_query` deve replicare il retry pattern
  di `_run_with_retry` (30s→60s→120s) per fairness con altri executor
- Evidence linter `file_line_ref` regex L10 fix: extension optional
- Evolver wrapper `SECRETS_FILE` validation: reject `/dev/null` OR
  empty OR no DEEPSEEK_API_KEY var set
- Phase 0 plist `infra/launchd/...weekly.plist` esiste già — Phase 1
  deve solo `cp + launchctl bootstrap`, NON riscrivere
- Panel R5 vietato sullo stesso PR — Phase 1 è PR nuovo (R1 sul nuovo
  PR), ma cap a R3-R4 sul nuovo PR pure
- `npx prettier --write` su file staged PRIMA del commit (pre-commit
  hook prettier check è blocker recurring)

## Pointers utili

- Phase 0 PR merged: https://github.com/Balizero1987/Teman2/pull/736
- Spec PR merged: https://github.com/Balizero1987/Teman2/pull/734
- EvoSkill upstream: https://github.com/sentient-agi/EvoSkill v1.1.0
- DeepSeek API docs: https://api-docs.deepseek.com/
- Gemini CLI: `gemini -m gemini-3.1-pro-preview -p "..."` (OAuth free)
- NotebookLM MCP: `mcp__notebooklm-mcp__notebook_query` with UUID
  `38a99d22-c2ec-4d18-9bbc-86fa4c1d72cb` (NB-1 General Bali Zero)
- Multi-LLM cascade docs: `~/.claude/CLAUDE.md` §"Multi-LLM cascade"
