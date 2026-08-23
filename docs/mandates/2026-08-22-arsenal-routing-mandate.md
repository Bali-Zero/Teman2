# MANDATE — Arsenal routing: make the orchestrator build with the whole arsenal, not only Sonnet 5

> **Per Zero (IT):** questa è la spec finale. Lanciala in una sessione **Opus 5** (`claude-opus-5`, effort `xhigh`) con:
> _"Esegui `docs/mandates/2026-08-22-arsenal-routing-mandate.md` con modus, Gear 2 per lane, regola 8 attiva."_
> Il workflow (modus → GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM → PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE) **resta valido**: le cure del 22/8 (PR #4573: regola 8, boot senza overdue) lo emendano, non lo sostituiscono.
>
> Author: Fable 5 session on M5, 2026-08-22. Grounded on disk the same day (every path below was `ls`/`grep`-verified at `e952cd17e`). Status: **SPEC — awaiting Zero's GO to dispatch.**

---

## 0. One line

The orchestrator already _convokes_ the cross-family arsenal (Kimi/Codex/agy/Qwen/GLM) — but only to get opinions. Every build goes to Sonnet 5. Remove the friction, then enforce a floor, then measure it in CI. **No new registry, no conductor, no broker.**

## 1. Ground truth (measured 2026-08-22, M5 transcripts 18–22/8 + origin/main)

| Fact                        | Value                                                                                                                                                                                                                                                      | Source                                                |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `Agent` dispatches by model | Sonnet **355** · Haiku 25 · Opus 24 (+29 inherit)                                                                                                                                                                                                          | transcripts                                           |
| `Agent` roles               | 292 read/explore · **62 build** · 79 review                                                                                                                                                                                                                | descriptions                                          |
| External seats via Bash     | Kimi 281 (K3 119) · Codex 91 `exec` · agy 29 · Qwen 20 · GLM 12                                                                                                                                                                                            | transcripts                                           |
| Codex sandbox mode          | **63 read-only (review) · 7 workspace-write (build)** · 21 other                                                                                                                                                                                           | transcripts                                           |
| Codex model / effort        | sol 51 · terra 2 · luna 0 · spark 6 / xhigh 38 · default 38 · high 13 · ultra 2                                                                                                                                                                            | transcripts                                           |
| Roster doc                  | `MODEL_ROSTER.md` 34 KB, 256 lines — referenced from `CLAUDE.md` §5, **not injected** at boot                                                                                                                                                              | repo                                                  |
| Live-seat probe             | `scripts/arsenal_probe.py` writes `~/.organism/arsenal/last.json`; `scripts/organism_digest.py::arsenal_seats()` already reads it at SessionStart — **M5 has no report** (`--read-last` → `{"findings": []}`)                                              | repo + M5                                             |
| Routing hook                | `~/.claude/hooks/model_routing_gate.py` (PreToolUse `Agent`): denies `Agent` without explicit `model`; **no repo canon** (`infra/claude-hooks/` has `orchestrate_gate.py` with a declared pair in `infra/home-fork/declared-pairs.json:414`, not this one) | HOME + repo                                           |
| Evidence pack               | `scripts/evidence_pack_lint.py`: `RECEIPT_REQUIRED_FIELDS` and `DISSENT_REQUIRED_FIELDS` already carry `seat`                                                                                                                                              | repo                                                  |
| Existing Codex builders     | only cron-specific: `scripts/codex/codex-nightly-autofix-ci.sh`, `scripts/supervisor_autofix_tier2.sh`, `scripts/dlq_autopilot.py`, `scripts/ai-dispatch.sh::run_codex()` (line 409) — **no general-purpose build wrapper**                                | repo                                                  |
| Doctrine already says it    | `CLAUDE.md` §5: "a multi-PR campaign should route at least one lane through a non-Anthropic builder" — prose, unmeasured, unfollowed (7 vs 355)                                                                                                            | repo                                                  |
| The failed alternative      | Pro 21–22/8: `codex resume` fan-out, 281 rollouts/day, 81 `infra/conductor/endpoint_profiles/*.json` cards + broker — consumed by nothing live (only `scripts/conductor/*`, `scripts/kbli_filiera/emit_batch_calibration*.py`, tests)                      | memory `discovery_codex_resume_fan_out_loop_on_pro_…` |

**Why Sonnet wins today:** `Agent(model:"sonnet")` is one call, parallel, worktree-less, structured output. `codex exec` is a blocking Bash call that needs a worktree, `< /dev/null`, a timeout, output parsing, and the model-slug/effort flags. The easy path wins every time; prose cannot beat it.

**What this buys (be honest in the report):** quota headroom and resilience (builds move from the Claude MAX/Team window to flat subscriptions) and parallelism across pools — **not fewer tokens**. Every cross-family build still gets an Anthropic verification pass (generator≠grader), so net relief ≈ 60–70% of the lane, never 100%.

## 2. Non-goals (hard)

- No new model registry, JSON card set, broker, attestation, or "conductor" organ. `MODEL_ROSTER.md` + `FLEET_TOPOLOGY.json` stay the SSOT. Do not touch `infra/conductor/`.
- No change to the final on-disk gate (Opus 5, never cascades), to PII routing (Ollama/local), or to hot-zone/migration lanes (Sonnet/Opus remain correct there).
- No doctrine rewrite. `CLAUDE.md` gets at most the lines in D3.
- Not a token-saving project. Do not claim one in any PR body.

## 3. Deliverables (4 PRs, one concern each, in this order)

### D1 — `scripts/seat_build.sh` — the friction killer (Gear 2)

A single entry point that gives Codex / Kimi / Qwen / GLM the same call shape as `Agent`:

```
scripts/seat_build.sh --seat codex|kimi|qwen \
  --worktree <path>  --task-file <path>  [--tests "<cmd>"] \
  [--effort low|medium|high|xhigh] [--timeout 1800] [--out <report.json>]
```

- Original 2026-08-22 instruction (superseded 2026-08-24): run the seat CLIs with their
  quirks pre-solved — Codex `exec --sandbox workspace-write --skip-git-repo-check -c
model_reasoning_effort=… < /dev/null`; Kimi `-m kimi-code/kimi-for-coding`; Qwen with
  `< /dev/null` + watchdog kill; GLM used the then-current z.ai shim and accepted file paths.
  Reuse `scripts/ai-dispatch.sh::run_codex()` and
  `infra/launchagents/wrappers/regulatory-watcher-run.sh` cascade-detection
  (`out of extra usage|quota|429`) — do not re-invent.
- **Superseding note 2026-08-24 (Zero ruling 2026-08-23):** the z.ai seat and shim are retired.
  GLM survives only through Alibaba TP1 seat `tp1-glm-5.2`; there is no replacement binary
  (`no door: line in roster`). Use the OpenAI-compatible base
  `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`; the key is loaded by
  `load_tp1_settings_key()` from `~/.qwen/settings.json`.
- Always in a worktree (`scripts/agent_start.py`), never in a main checkout. Refuses to start if `--worktree` is a main checkout or is dirty.
- Output contract (`--out`): `{seat, model, effort, rc, duration_s, diff_stat, tests: {cmd, rc}, quota_exhausted: bool}` — exactly the fields an evidence-pack receipt needs (`claim, cmd, exit, ts, seat`).
- **Never merges, never arms, never pushes.** The orchestrating session verifies the diff (generator≠grader) and ships.
- Secrets: the seat inherits the session env — strip `CLAUDE_CODE_OAUTH_TOKEN*`, `*_API_KEY`, `*_TOKEN` from the child env except the seat's own credential (memory: external CLIs inherit the session env).
- Tests: `scripts/tests/test_seat_build.sh` — guilt (dirty worktree refused, main checkout refused, quota string → `quota_exhausted:true` + rc≠0) and innocence (a 1-file task on a fixture worktree round-trips through `--seat codex` in `--dry-run` without calling the network).
- Acceptance: from a fresh Opus 5 session, one Bash call builds a 1-file fix on a worktree via Codex and returns the JSON; the session then runs the tests itself and ships.

### D2 — `model_routing_gate.py`: a measured floor, not prose (Gear 2 — hook = auto-merge OFF, session merges after its own gate)

- First give the hook a **repo canon**: `infra/claude-hooks/model_routing_gate.py` + a declared pair in `infra/home-fork/declared-pairs.json` (like `orchestrate_gate.py` line 414) so `scripts/lint_home_fork.py` sees drift. Installing the live copy under `~/.claude/hooks/` is `operator[control-plane]` on each machine — ledger it; the repo PR ships the canon and the installer line.
- New rule (in addition to "explicit model required"): count BUILD-shaped `Agent` calls (description matches `implement|build|fix|write|add|cure|ship`, model ∈ {sonnet, haiku, opus}) per session transcript. On the **3rd consecutive** Anthropic build dispatch with **0** `seat_build.sh` invocations in the same transcript → `permissionDecision: "deny"` with the exact `seat_build.sh` line to use. Override: `ROUTING_FLOOR_OK=<reason>` in the Agent prompt or env (logged, never silent — same audibility discipline as `orchestrate_gate.py`'s DISARM notice).
- Exemptions cabled in code, not judged: task description or worktree path matching hot-zone patterns (`scripts/evidence_pack_lint.py::HOTZONE_PATTERNS`), migrations, anything with `pii|client|ktp|passport|npwp` → no floor.
- Tests: `infra/claude-hooks/test_model_routing_gate_floor.py` — guilt (3 Sonnet builds, 0 seats → deny), innocence (2 builds → allow; 3 builds after one `seat_build.sh` → allow; hot-zone → allow; explicit override → allow + notice). Mutation: flip the threshold and the exemption regex; each mutant must be killed. `PYTHONDONTWRITEBYTECODE=1` (memory: poisoned bytecode).
- Acceptance: live in an Opus 5 session on M5, the 3rd Sonnet build is denied with a usable message; after one `seat_build.sh` call it passes.

### D3 — Evidence-pack lint: seats per lane (Gear 2)

- `evidence/pack.yml` contract gains an optional `lanes:` list `{lane, role: build|review|read, seat}`; for Gear ≥ 2 packs with ≥ 2 `build` lanes and 0 non-Anthropic build seats → **NOTICE** for 14 days, then FAIL (date the flip in the lint, not in a ledger). Anthropic seat names: `claude-*`, `sonnet`, `opus`, `haiku`.
- `CLAUDE.md` §5: replace the prose "should route at least one lane…" with one sentence pointing at the lint and the hook (≤ 3 lines). Nothing else in doctrine moves.
- Tests in `scripts/tests/test_evidence_pack_lint_lanes.py`, guilt + innocence, including "single-lane pack is exempt".

### D4 — The orchestrator _knows_ at boot (Gear 1)

- Arm `scripts/arsenal_probe.py` on **M5** (today it has no report): a LaunchAgent is overkill — run it from `scripts/hooks/organism_digest_sessionstart.sh` when `~/.organism/arsenal/last.json` is missing or > 24 h old, with `--timeout` ≤ 20 s total and never blocking boot (background it, read the _previous_ report this boot). Pro/Mini already produce a report — verify, don't assume (`ssh pro 'ls -la ~/.organism/arsenal/last.json'`).
- Boot card: `organism_digest.py` renders one line per seat from `last.json` + a static 8-row role map (seat → role → exact invocation) derived from `MODEL_ROSTER.md` at build time (a tiny generated block with a `check` test that fails when the roster's seat set changes). ≤ 12 lines total — this file is injected into every session; bytes here are paid by the whole fleet.
- Acceptance: a fresh M5 session's SessionStart output shows `seats: kimi ✓ codex ✓ glm ✓ qwen ✗(401) agy ✓` (or whatever is true) and the 8 invocation lines.

## 4. Routing for THIS mandate (dogfood it)

| Lane            | Builder                                                                                                                     | Grader (≠ builder)                               |
| --------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| D1 wrapper      | **Codex** (`workspace-write`, effort xhigh) — the wrapper builds itself through `ai-dispatch.sh::run_codex` until D1 exists | Opus 5 session + Kimi K3 refuter                 |
| D2 hook + canon | Sonnet 5 (hook code, needs the repo's test idioms)                                                                          | Codex sol read-only red-team + Opus 5 final grep |
| D3 lint         | **Kimi kimi-for-coding** or GLM counter-build                                                                               | Sonnet 5 review + Opus 5                         |
| D4 boot         | Sonnet 5                                                                                                                    | Opus 5                                           |

At least two of the four build lanes must be non-Anthropic, or this mandate fails its own acceptance.

## 5. Loop discipline (binding — PR #4573, rule 8)

- Gear 2 per lane. No council (divergent priors won't change these answers). One spalla per PR.
- **Three reds on the same cause ⇒ SUSPEND** that lane with a PENDING-ARMS line; move to the next lane. A fix-of-a-fix stops at depth 1.
- Stop-loss for the whole mandate: **~12 subagent/seat dispatches and one working day**. Past that, ship what is green and write the rest as PENDING-ARMS — do not open PR 5.
- Arm `gh pr merge --auto` nude at PR-open for D1/D3/D4 (after the spalla verdict is in); **D2 is a hook → auto-merge OFF**, the session merges after its own gate, then installs the live copy only where it is not `operator[control-plane]`.
- Every number in a PR body names the command and the SHA it was measured at.
- Do not read or "fix" anything under `infra/conductor/`, the 8 `infra-conductor-*` worktrees on Pro, or PR #4569 — Zero's decision, not this mandate's.

## 6. PROVE-LIVE checklist (done = all five, run, not recalled)

1. `scripts/seat_build.sh --seat codex …` on a throwaway worktree returns the JSON contract and a real diff.
2. Live hook deny observed in an Opus 5 session on M5 (screenshot or transcript line), and pass after one wrapper call.
3. `python3 scripts/evidence_pack_lint.py` on a fixture pack with 2 Sonnet build lanes prints the NOTICE; with one `codex` lane it is silent.
4. Fresh M5 SessionStart shows the seat line with a report < 24 h old.
5. `scripts/lint_home_fork.py` sees the new `model_routing_gate.py` pair and reports the live copy in sync on the machine(s) where it was installed; the others are ledgered `PENDING-ALIGN:<machine>`.

## 7. Solo-operatore (Zero)

- Installing/refreshing the live hook copy under `~/.claude/hooks/` on Pro and Mini (`operator[control-plane]`).
- Whether the D3 NOTICE becomes a FAIL after 14 days (Legge 5 — it changes how every session is allowed to work).
- Fate of the conductor artifacts on Pro (PR #4569, 8 worktrees, `~/logs/conductor-endpoint-profiles-uncommitted-20260822-2127.patch`).

## 8. Capture

On completion: one memory (`project`), one AMENDMENTS line only if the loop itself misfired, and re-measure the dispatch mix after one week with the same transcript script used for §1 — that number, not the PR count, says whether the mandate worked.
