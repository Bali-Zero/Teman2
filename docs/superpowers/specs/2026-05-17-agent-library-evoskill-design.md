# Design: agent-library auto-evolving via EvoSkill A2-vendored

**Date**: 2026-05-17
**Status**: v5 (final pre-plan) — 4 rounds 3-LLM panel review. 5/5 v4 Codex finding addressed (HIGH inline, LOW/MEDIUM in "Known limitations v1")
**Next**: writing-plans → vendor + adapt
**Author**: Claude Opus 4.7 (1M context)

## Panel review history

**v1 panel** (Gemini + DeepSeek + Codex) caught 4 substantive findings:

1. CRITICAL — entailment gate missing → fixed v2 (LLM entailment check)
2. HIGH — ChatGPT Pro rate-limit risk → fixed v2 (executor = DeepSeek API)
3. HIGH — Anthropic import strip incomplete → fixed v2 (physical line removal)
4. MEDIUM — symlink fragility → fixed v2 (native write to proposals/)

**v2 re-review** (same panel) returned 3/3 NEEDS_FIX:

- DeepSeek: finding #3 doc contradiction (env-guard still in UPSTREAM.md)
- Gemini: GO with minor cleanup (orphan docs)
- **Codex: NEEDS_FIX severe** — caught 3 NEW structural issues:
  - **A. Doc drift residue**: `evolver.toml provider=codex`, `CHATGPT_PRO_ONLY`,
    open questions still reference Codex CLI despite v2 switch
  - **B. Self-confirming verifier**: DeepSeek does proposer+entailment in same
    pipeline — anti-pattern documented in CoEvoSkills paper (verifier MUST be
    information-isolated)
  - **C. Privacy leak**: mem query + git log + cicatrix internal → DeepSeek API
    without redaction. Violates Symbiosis Law 2 "OSINT blindato" + UU PDP
    Indonesian privacy scope.
  - **D. Entailment URL/commit handling**: spec only describes file:line case
  - **E. Cost cap incoherent**: $0.50/$1.00/$0.15-0.30/$0.10-0.20 sparsi without
    enforcement in wrapper

**v3 fixes applied** (this revision):

- Doc drift removed: all Codex/CHATGPT_PRO_ONLY/symlink references purged
- Verifier isolation: entailment check now uses **Gemini 3.1 Pro free OAuth**
  (different provider from DeepSeek proposer) — cross-vendor info isolation
- Privacy redaction layer added (Step 1.5) before any LLM call
- Entailment check handles file:line, commit hash, URL via explicit cases
- Single cost cap `BUDGET_USD=1.00` env var enforced in wrapper

Panel artifacts:

- v1: `/tmp/evoskill-review-{gemini,deepseek,codex}.txt`
- v2: `/tmp/evoskill-v2-{gemini,deepseek,codex}.txt`

---

## Context

PR #700 ha mergiato 2 file markdown statici (`02-patterns.md`, `03-lessons.md`)
nella `agent-library/`. Già al merge avevano numeri stale (60 NB scritti,
50 reali). Antonello chiede una versione **auto-evolving**:
auto-rifornimento, auto-pensiero, auto-miglioramento.

Research SOTA (3-LLM panel: Gemini killed by 429, DeepSeek + Codex + WebSearch)

- lettura 3 paper (EvoSkill, CoEvoSkills, SkillFoundry — marzo-aprile 2026):

* **EvoSkill** (Sentient AGI, Apache 2.0, github.com/sentient-agi/EvoSkill)
  è il closest match e ha **codice rilasciato**. Loop Executor + Proposer +
  Skill-Builder, frontier top-k, held-out validation.
* **CoEvoSkills**: aggiunge Surrogate Verifier information-isolated (steal
  per evidence gate).
* **SkillFoundry**: aggiunge 3-layer validation + provenance (steal per
  validation pipeline).

EvoSkill upstream viola la nostra hard rule (Anthropic SDK in deps + import
`anthropic.AsyncAnthropic`), ma:

- Tutti gli import sono **lazy** (dentro funzioni, non top-of-module)
- Provider è config-driven; supporta OpenAI/Codex/DeepSeek nativamente
- Branching `if provider == "anthropic"` permette skip totale via config

Scelta architetturale: **A2-vendored** — vendor copia in `vendor/evoskill/`,
strip Anthropic deps da pyproject, executor = DeepSeek V4 Pro API
($0.10-0.30/run, evita Pro rate-limit), entailment verifier = Gemini 3.1 Pro
free OAuth (cross-vendor isolation).

---

## Decisions locked

| Decision                    | Choice                                                                    | Rationale                                                                                                             |
| --------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Vendor strategy             | `vendor/evoskill/` git-tracked copy                                       | Auditable, no submodule fragility                                                                                     |
| Upstream source             | github.com/sentient-agi/EvoSkill @ v1.1.0                                 | Apache 2.0, active maintenance                                                                                        |
| LLM executor (v3)           | **DeepSeek V4 Pro API** (proposer + skill-builder)                        | Pro rate-limit/CAPTCHA risk on autonomous loops (v1 finding #2). Cost $0.10-0.20/run.                                 |
| LLM critic (entailment, v3) | **Gemini 3.1 Pro free OAuth**                                             | Cross-vendor isolation from proposer (v2 Codex finding B "self-confirming verifier" — CoEvoSkills paper anti-pattern) |
| Privacy redaction (v3)      | Python regex layer pre-LLM                                                | Strips PII/internal data before any external API call (v2 Codex finding C — Symbiosis Law 2 + UU PDP)                 |
| Banned deps stripped        | `claude-agent-sdk`, `anthropic` (physical lines deleted, NOT env-guarded) | CLAUDE.md hard rule + v1 finding #3 + v2 finding A confirms no env-guard residue                                      |
| Cost cap (v3)               | Single `BUDGET_USD=1.00` env var enforced in wrapper                      | v2 Codex finding E — incoherent caps removed                                                                          |
| Pattern surface             | `agent-library/proposals/YYYY-MM-DD/*.md`                                 | Separato da live `02-patterns.md` / `03-lessons.md`                                                                   |
| Promotion gate              | Draft PR auto-opened by cron, human merge                                 | L2 autonomous ops compliant                                                                                           |
| Trigger cadence             | Weekly cron Sunday 03:00 WITA                                             | After wr2 Reflexion 02:30, before Mon SessionStart                                                                    |
| Anti-hallucination          | Evidence-linter: ogni proposal richiede `file:line` o commit hash         | Hard rule globale                                                                                                     |
| Skill folder format         | EvoSkill standard: `SKILL.md` + helper scripts                            | Compatible con upstream tools                                                                                         |
| Preflight enforcement       | Out-of-scope v1                                                           | Aggiungere in v2 dopo evolver stabile                                                                                 |

---

## Out of scope (v1)

- **CoEvoSkills Surrogate Verifier**: design importante ma 15-20h extra impl.
  v2 aggiunge il pattern di information-isolation al nostro 3-LLM panel.
- **SkillFoundry 3-layer validation**: layer 1 (execution smoke) lo facciamo;
  layer 2 (utility measured) + layer 3 (novelty vs external) → v2.
- **Preflight SessionStart hook**: query library prima dell'azione. v2.
- **Knowledge tree taxonomy**: scope tags semplici v1, tree v2.
- **Multi-skill co-evolution**: EvoSkill upstream evolve single agent
  program; multi-skill batch → v2.

v1 = **minimum viable evolver**: weekly cron che produce proposals + draft PR.
Validità test: dopo 4 settimane, se le proposals sono utili → v2 expand.

---

## Files (target tree)

```
vendor/evoskill/                          # NEW vendored upstream (~2.5MB)
  src/                                    # EvoSkill source, modified
  pyproject.toml                          # MODIFIED: no anthropic/claude-agent-sdk
  README.md                               # MODIFIED: header with our adaptation notes
  LICENSE                                 # KEPT: Apache 2.0 verbatim
  UPSTREAM.md                             # NEW: tracking what we changed vs upstream
agent-library/
  proposals/                              # NEW: pending pattern/lesson proposals
    .gitkeep
    2026-05-17-example/                   # First example dir for testing
      SKILL.md
      provenance.json
  config/                                 # NEW
    evolver.toml                          # EvoSkill config (provider=deepseek)
    evidence-rules.yaml                   # Rules for evidence-linter
    redaction-rules.yaml                  # v3: PII/internal patterns to strip pre-LLM
config/
  agent-library-evolver-secrets.env.example  # NEW: env template (no real keys)
scripts/
  agent-library-evolver-run.sh            # NEW: wrapper invoked by launchd
  agent-library-evolver-propose-pr.sh     # NEW: gh pr create from proposals
~/Library/LaunchAgents/
  com.balizero.agent-library-evolver.weekly.plist  # NEW: Sunday 03:00 WITA
docs/superpowers/specs/
  2026-05-17-agent-library-evoskill-design.md  # THIS FILE (already)
```

---

## Architecture (v1 — minimum viable)

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRIGGER: launchd weekly Sunday 03:00 WITA                          │
│  Script: scripts/agent-library-evolver-run.sh                       │
└──────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. CONTEXT GATHERING (60s)                                          │
│     - mem query "recent successes/failures last 7 days"             │
│     - git log --since=7days --oneline                               │
│     - read agent-library/02-patterns.md + 03-lessons.md             │
│     - read recent cicatrix-scars.md additions                       │
│     → /tmp/agent-library-evolver/context-raw-YYYY-MM-DD.md          │
└──────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1.5. PRIVACY REDACTION (v3, 2-5s, MANDATORY)                       │
│     scripts/_redact_pii.py                                           │
│     Strips per `agent-library/config/redaction-rules.yaml`:          │
│     - Indonesian: NPWP, NIB, passport numbers, IMTA, KTP, KITAS IDs │
│     - Personal: client names (CRM table), team emails, phone numbers│
│     - Internal: cicatrix entries flagged STRUCTURAL (keep arch       │
│       lessons, redact specific filenames/IPs)                        │
│     - Symbiosis Law 2: OSINT data NEVER leaves Pro → redact tag      │
│       `[osint-internal]` entries entirely                            │
│     → /tmp/agent-library-evolver/context-redacted-YYYY-MM-DD.md     │
│     v2 Codex finding C — UU PDP + Symbiosis Law 2 compliance        │
└──────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. EVOSKILL RUN (3-15min, depends on T iterations)                 │
│     uv run evoskill run --config agent-library/config/evolver.toml │
│     - Executor: DeepSeek V4 Pro API ($0.05-0.10 per run)            │
│     - Proposer: DeepSeek V4 Pro API                                  │
│     - Skill-Builder: DeepSeek V4 Pro API                             │
│     - Frontier k=3, T=10 max iterations                              │
│     - Prompt budget: ~30 prompts/run (capped, panel finding #2)     │
│     - Held-out validation: 20% of context (rotated)                 │
│     - Output written DIRECTLY to agent-library/proposals/            │
│       YYYY-MM-DD/ (no symlink — panel finding #4)                    │
└──────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3a. EVIDENCE LINTER — EXISTENCE (Python, 5-10s)                     │
│     scripts/_evidence_lint.py                                        │
│     - Reject any SKILL.md without ≥1 of:                            │
│       * commit hash matching git rev-parse                          │
│       * file:line resolving to real disk path                       │
│       * memory file path that exists                                │
│       * external URL (verified via HEAD request, 2s timeout)       │
│     - Reject duplicates: FTS5 BM25 against 02-patterns/03-lessons,  │
│       reject if BM25 score < 1.5 (top match too similar)             │
│                                                                      │
│  3b. ENTAILMENT CHECK — Gemini 3.1 Pro free OAuth (30-90s)           │
│     scripts/_entailment_check.py                                     │
│     v3: cross-vendor isolation from DeepSeek proposer (v2 Codex      │
│     finding B — self-confirming verifier anti-pattern)               │
│     v4: ALL evidence payloads MUST pass redaction layer (_redact_pii)│
│         BEFORE Gemini call. Privacy gate fail-closed: redaction      │
│         missing/empty → reject proposal (v3 Codex finding 2 HIGH).   │
│     For each candidate that passed 3a, by citation type:             │
│       a) file:line → Read snippet ±10 lines → REDACT → Gemini       │
│       b) commit hash → `git show <hash>` → REDACT → Gemini          │
│       c) URL → curl -s (5s timeout) → text-only → REDACT → Gemini   │
│       d) memory path → Read first 50 lines → REDACT → Gemini        │
│     - Reject if NO + log rationale to telemetry                      │
│     - Gemini quota fallback: NotebookLM Bali Zero NB-1                │
│       v5 fix (Codex round-4 HIGH): NB query payload (claim + evidence│
│       snippet) MUST also pass _redact_pii. Even though NB content    │
│       is on-prem, the QUERY we send contains the same evidence       │
│       snippet that Gemini would see — privacy gate applies            │
│       unconditionally to any LLM call (Gemini OR NB).                │
│     → agent-library/proposals/YYYY-MM-DD/ (verified)                 │
└──────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. PROMOTION PR (10-20s, only if ≥1 candidate passed)              │
│     scripts/agent-library-evolver-propose-pr.sh                     │
│     - mv passed-lint/* → agent-library/proposals/YYYY-MM-DD/        │
│     - git add + commit on branch auto/agent-library-YYYY-MM-DD      │
│     - gh pr create --draft with synthesis of proposals               │
│     - Telegram alert to Antonello                                    │
└──────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼ (HUMAN GATE)
                              ┌──────────────────┐
                              │ Antonello review │
                              │ Merge or close   │
                              └──────────────────┘
```

---

## What gets vendored vs what stays upstream-tracked

```
vendor/evoskill/UPSTREAM.md tracks:
- Source: github.com/sentient-agi/EvoSkill
- Vendored commit: <SHA at vendoring time>
- Vendored date: 2026-05-17
- Modifications applied (DIFF list, v3 PHYSICAL not env-guard):
  1. pyproject.toml — remove `claude-agent-sdk`, `anthropic` (+sdk) deps.
     Add: `openai-codex-sdk` (already there), `httpx` (already there).
  2. src/harness/claude/ — DELETED entire directory (rm -rf, not rename).
     Replaced with stub `src/harness/claude/__init__.py` raising
     `ImportError("Claude SDK disabled per CLAUDE.md hard rule")` to make
     accidental import paths fail loud.
  3. src/cli/shared.py — `import anthropic` line + entire `if provider ==
     "anthropic"` block DELETED (lines verified by AST scan post-edit).
  4. src/harness/codex/ — DELETED entire directory (we use DeepSeek API,
     not Codex CLI — v2 Codex finding A doc drift cleanup).
  5. src/harness/deepseek/ — NEW directory, executor implementation per
     DeepSeek V4 Pro Chat Completions API.
- Verification post-edit (CI gate, blocks merge):
  - `python3 -c "import ast; <walk src> assert no 'import anthropic' nor
    'import claude_agent_sdk' top-level"`
  - `grep -r 'anthropic\|claude_agent_sdk' vendor/evoskill/src/` must
    return empty (or only comments)
- Upstream refresh policy: manual quarterly review of upstream diff.
  If upstream adds breaking changes, decide:
  (a) cherry-pick fixes only, (b) re-vendor whole, (c) stay frozen.
```

---

## Anti-pattern mitigation

| Risk                                                  | Mitigation                                                                                                                                                                                                                                           |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hallucinated pattern citations (existence)            | Evidence linter rejects unverifiable refs (HEAD request URL, file:line disk check)                                                                                                                                                                   |
| Hallucinated claims with valid citations (entailment) | **NEW v2**: LLM entailment check (DeepSeek $0.01/proposal): rejects if cited content does not support claim. Panel finding #1 CRITICAL.                                                                                                              |
| Drift (proposals never merged accumulate)             | `proposals/` dir auto-pruned after 30 days (cron daily)                                                                                                                                                                                              |
| Library bloat                                         | Promotion gate dedup via FTS5 BM25 score < 1.5 against existing 02/03 entries (v3 Codex finding 4 unification — was inconsistent FTS5 vs cosine 0.85). Sliding 30-day proposal/rejected ratio tracked.                                               |
| Reflection loop (cron creates trigger for cron)       | Single-flight via PG advisory lock; if previous run still active, skip                                                                                                                                                                               |
| Self-confirming verifier                              | **v3 fix**: cross-vendor isolation — proposer=DeepSeek V4 Pro, entailment-verifier=Gemini 3.1 Pro free OAuth (different provider, different bias). Existence linter=Python pure logic (no LLM). v2 Codex finding B (CoEvoSkills paper anti-pattern). |
| Privacy leak to external LLM (v3)                     | Redaction layer step 1.5 mandatory before any LLM call. Symbiosis Law 2 + UU PDP. Telemetry validates redacted-only payload sent.                                                                                                                    |
| Cost runaway                                          | Budget cap T=10 iterations max per weekly run + single `BUDGET_USD=1.00` env-var ceiling (v3 fix, see LLM routing). **v4**: budget is fail-closed — if telemetry JSON missing/null/parse-fail, abort + Telegram alert (v3 Codex finding 5).          |
| Untracked Anthropic SDK auto-install                  | `vendor/evoskill/pyproject.toml` deps explicit, no upstream `pip install evoskill` allowed. **NEW v2**: physical strip of `import anthropic` and `import claude_agent_sdk` lines from vendored source (NOT env-guard, panel finding #3 HIGH).        |
| Worktree fragility                                    | NO symlink. EvoSkill config modificato per writing nativo a `agent-library/proposals/YYYY-MM-DD/` (panel finding #4)                                                                                                                                 |

---

## LLM routing

Per CLAUDE.md ChatGPT Pro lane:

| Phase                               | Model                         | Cost                            | Why                                                               |
| ----------------------------------- | ----------------------------- | ------------------------------- | ----------------------------------------------------------------- |
| Context gathering                   | None (pure shell + mem CLI)   | $0                              | No LLM                                                            |
| Privacy redaction                   | None (Python regex)           | $0                              | Mandatory pre-LLM, Symbiosis Law 2                                |
| Executor / Proposer / Skill-Builder | DeepSeek V4 Pro API           | ~$0.10-0.20/run, 30 prompts cap | v1 finding #2: avoid Pro rate-limit                               |
| Existence linter                    | None (Python)                 | $0                              | Pure regex + file existence + URL HEAD                            |
| **Entailment check (v3)**           | **Gemini 3.1 Pro free OAuth** | $0 (free tier)                  | v2 Codex finding B: cross-vendor isolation from DeepSeek proposer |
| Entailment fallback (v3)            | NotebookLM Bali Zero NB-1     | $0 (free)                       | If Gemini quota-exhaust, NB-1 as ground-truth                     |
| Synthesis (PR body)                 | DeepSeek V4 Pro `$0.01/q`     | ~$0.01/run                      | Summarization, cost trivial                                       |

**Total weekly cost**: ~$0.11-0.21 (DeepSeek executor + synthesis; Gemini free).

**Single hard cap** (v3 Codex finding E fix): `BUDGET_USD=1.00` env var
enforced in `scripts/agent-library-evolver-run.sh` with **per-iteration check
(NOT just post-run)** + **fail-closed on missing telemetry** (v3 Codex finding 5):

```bash
# Per-iteration check during T=10 loop (NOT only post-run)
for iter in $(seq 1 10); do
    run_evoskill_iteration $iter

    if [ ! -f /tmp/.../telemetry.json ]; then
        abort_with_telegram "telemetry missing post-iter $iter — fail-closed"
    fi

    RUN_COST=$(jq -r '.usage.total_cost_usd // "null"' /tmp/.../telemetry.json)
    if [ "$RUN_COST" = "null" ] || [ -z "$RUN_COST" ]; then
        abort_with_telegram "telemetry parse fail iter $iter — fail-closed"
    fi

    if (( $(echo "$RUN_COST > $BUDGET_USD" | bc -l) )); then
        abort_with_telegram "budget exceeded mid-run: $RUN_COST > $BUDGET_USD"
    fi
done
```

**Historical note — why we ruled out Codex CLI**: v1 spec considered Codex CLI
(ChatGPT Pro $0 marginal). v1 panel finding #2 HIGH ruled it out: autonomous
loops trigger Cloudflare protections + 500-msg/3h quota risk locks Antonello's
daily Pro access. v3 chose DeepSeek API ($0.10-0.20/run) as cheap insurance.
This is design decision rationale, NOT active config — Codex is fully removed
from pipeline (no `provider=codex` anywhere; src/harness/codex/ DELETED in
UPSTREAM.md vendoring step).

---

## Promotion gate criteria (v1)

A proposal in `proposals/YYYY-MM-DD/` is **eligible for merge** if ALL gates pass:

1. **Existence linter PASS** (step 3a): ≥1 verifiable reference (file:line OR commit OR URL OR memory path) that resolves
2. **Entailment check PASS** (step 3b, v3 MANDATORY): Gemini "claim supported by cited content?" → YES
3. **NOT duplicate** (v4 unified): FTS5 BM25 score vs all current `02-patterns.md` + `03-lessons.md` entries — top match score ≥ 1.5 (lower = more similar = reject). NO cosine/embedding (deterministic, no embedding model needed).
4. **Not deprecated topic**: scope not in `agent-library/deprecated.yaml` (v2)
5. **Antonello manual approval**: PR draft must be marked `ready-for-review` then merged

Any gate FAIL → proposal moved to `agent-library/proposals/YYYY-MM-DD/rejected/` with rationale logged.

Single-incident proposals stay in `watchlist/` for 2 weeks; if pattern recurs
(detected by next weekly run), elevated to `proposals/`.

---

## Telegram alert format

```
🌱 agent-library-evolver weekly run completed (Sun 03:00 WITA)

Iterations: T=<n> (frontier top-3)
Candidates raw: <total>
Passed existence linter: <passed_3a>
Passed entailment (Gemini): <passed_3b>
Rejected: <rejected> (reasons: <hallucinated_ref|claim_not_entailed|dup|...>)

PR draft: <URL or "no proposals this run">

Cost: $<n> DeepSeek (executor+synthesis) + $0 Gemini free (entailment)
Budget: $<n> / $1.00 cap
```

---

## Verification & rollout

### Phase 0 — Smoke (this PR)

- Vendor evoskill, strip Anthropic, write config
- Run `uv run evoskill --help` → no anthropic import error
- Run dry-run on dummy task → produces SKILL.md + helper

### Phase 1 — First live run (Sunday after merge)

- Manual trigger first run via `launchctl start ...`
- Observe Telegram alert + PR draft
- Antonello reviews proposal quality

### Phase 2 — 4 weekly runs auto

- Cron self-running
- Track in MEMORY.md: proposals/PRs/merged ratio
- If merge rate < 20% after 4 weeks → revisit design

### Phase 3 — v2 expansion (separate spec)

- Add CoEvoSkills surrogate verifier
- Add SkillFoundry 3-layer validation
- Add preflight enforcement hook

---

## Open questions (for 4-LLM panel review)

1. **DeepSeek V4 Pro structured output**: EvoSkill uses Pydantic schemas for
   proposal output. DeepSeek API supports JSON mode via `response_format`.
   Smoke test required to verify EvoSkill harness/deepseek/ adapter we write
   handles schema validation correctly.

2. **Redaction completeness**: `redaction-rules.yaml` patterns are written by
   me — am I missing PII classes (e.g., bank account numbers in invoices,
   PT PMA shareholders names in CRM)? Smoke test: run redaction on 1-week
   of real mem queries + git log, manually inspect output for leak before
   first production run.

3. **Gemini free OAuth quota for entailment**: Gemini 3.1 Pro free has daily
   limits. ~30 entailment calls/run × 4 runs/month = 120/month, well within
   free quota. But concurrent use (wr2-design-architect, regulatory-watcher
   cascade) could exhaust. Fallback NB-1 must be wired.

4. **Event-driven trigger (v2 expansion)**: weekly cron sufficient for v1.
   v2 considers eventbus `task.completed` events — schema in
   `apps/backend-rag/.../events_outbox` channels per PG_CHANNEL_MAP.

5. **Backup / disaster recovery**: vendored evoskill source is git-tracked.
   If upstream releases critical bug fix, refresh policy is manual quarterly.
   Acceptable risk for v1?

6. **DeepSeek API unavailability**: no fallback documented for executor.
   v2 add Ollama local fallback (qwen3.5:9b for proposals, lower quality
   acceptable per CLAUDE.md Tier-4 graceful degradation)?

---

## Known limitations v1 (accepted, documented for implementation phase)

These are v4-Codex-flagged LOW/MEDIUM findings accepted as v1 limitations.
Implementation phase must address each as smoke test or follow-up issue.

| Limitation                                                                                         | Severity | Plan-phase action                                                                                                |
| -------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `openai-codex-sdk` still in pyproject (used by EvoSkill internals even if we don't call Codex CLI) | LOW      | Document in UPSTREAM.md why kept. If safe to remove → strip in vendor step.                                      |
| Budget cap is per-iter NOT cumulative across iters                                                 | MEDIUM   | Add cumulative `BUDGET_TOTAL_USD=$RUN_COST_SUM` tracking. Smoke test multi-iter run.                             |
| FTS5 BM25 threshold `< 1.5` not calibrated on real corpus                                          | MEDIUM   | Phase 0 smoke: run dedup on 50 synthetic candidates vs current 02/03, measure false reject rate, tune threshold. |
| Doppia redazione idempotency not tested                                                            | LOW      | Add unit test `test_redact_pii_idempotent` (apply twice → same output).                                          |
| Telemetry async timing could trigger false fail-closed                                             | LOW      | Add 2s sleep + retry-once before abort. Gemini v4 observation.                                                   |

These are tracked in `agent-library/proposals/.known-limitations-v1.md` for
post-merge follow-up.

## References

- Parent spec: `docs/superpowers/specs/2026-05-17-agent-library-patterns-lessons-design.md`
- Research output: `/tmp/research-{deepseek,codex,gemini}.txt` (this session)
- Upstream: github.com/sentient-agi/EvoSkill @ v1.1.0
- Papers: arxiv 2603.02766 (EvoSkill), 2604.01687 (CoEvoSkills), 2604.03964 (SkillFoundry)
- ChatGPT Pro fact: `~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/fact_chatgpt_pro_subscription.md`
- L2 autonomous ops: `AUTONOMOUS_OPS.md`
