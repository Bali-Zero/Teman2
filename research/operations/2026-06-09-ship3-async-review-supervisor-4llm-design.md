---
date: 2026-06-09
domain: operations
client_case: none
subject: "Ship #3 — async review supervisor: 4-LLM design panel verdict + V1 plan"
status: "DESIGN APPROVED (4-LLM panel) — V1 label-only/block mode building; Pro daemon NOT armed (M5 is dev, daemon runs on Pro)"
sources:
  - 4-LLM panel (Gemini red-team, Codex constructive, DeepSeek logic/cost, Claude synthesis) — all 3 tiers health-checked LIVE
  - STADIO-0 grounding (this session) — all facts verified on disk
  - scripts/codex_tri_llm_review.py (the ~70% that already exists)
  - scripts/branch_graveyard_cleanup.sh (existing pruning, dry-run, cat.1-only)
  - scripts/dlq_autopilot.py (proven autonomous-agent-on-Pro pattern)
  - .github/workflows/auto-merge-whitelist.yml (existing PR signal)
  - cicatrix W59/W62 (sibling-race), W64 (exists≠armed), W69 (runs≠gates), branch-cleanup invariant
panel:
  - Gemini 3.1 Pro (agy) — red-team — LIVE (PONG)
  - Codex GPT-5.5 — constructive — LIVE (PONG)
  - DeepSeek V4 Pro (reasoning_effort=high) — logic/cost — LIVE
  - Claude Opus 4.8 — synthesis
---

# Ship #3 — Async Review Supervisor: 4-LLM design verdict

## 0. What the panel KILLED (2 of Claude's prior assumptions)

1. **`deepseek-r1` local on the Pro — KILLED (unanimous).** A yak-shave. PII in CODE diffs is rare;
   pulling+maintaining a new Ollama model is a permanent decay surface (W64) for a near-zero-probability
   case. The prior ship #3 premise ("deepseek-r1 local on Pro") was FALSE on disk (not installed anywhere)
   AND unnecessary. Replacement: per-path PII gate (skip `kb/`, `fixtures/`, `crm/`); clean diffs → DeepSeek
   cloud (pre-authorized non-PII); PII-risk diffs → degraded panel using EXISTING local Ollama (gemma3:27b
   / qwen3.5:9b), no new model.

2. **Auto-revert / auto-close — KILLED (unanimous).** Gemini's fatal failure mode: the **Infinite Agent
   Death-Loop** — if the supervisor auto-reverts a bad PR, the originating AI agent loses context, assumes
   a git failure, regenerates the work on a NEW branch → endless loop → hundreds of orphan branches, zero
   features, exhausted quota. The W59/W62 sibling-race scars multiply exponentially.

## 1. The approved design

**Reuse `scripts/codex_tri_llm_review.py`, build a thin Pro supervisor around it.** (Codex + DeepSeek;
Gemini's "build fresh" dissent was really about the Anthropic-API-ban, addressed below — not a rewrite reason.)

**Compliance status (VERIFIED on disk this session — corrects the panel):** the Claude reviewer backend
in `codex_tri_llm_review.py` is ALREADY `claude` CLI OAuth, NOT the Anthropic API — the file already strips
`ANTHROPIC_API_KEY`/`AWS_BEDROCK_ANTHROPIC_KEY`/`VERTEX_AI_ANTHROPIC_KEY` from the subprocess env (lines
52/288/349/372) and spawns the `claude` binary. Gemini's "it calls Opus directly via API" claim is FALSE
(hallucinated risk). So the "mandatory compliance fix" the panel demanded is ALREADY DONE — no patch needed
on the Claude path. DeepSeek stays cloud for NON-PII diffs (line 453: explicit `deepseek-v4-pro`, not the
legacy alias — cicatrix-aware); the supervisor adds the per-path PII gate on TOP, before invoking.

**Also verified:** `compute_outcome()` (line 536) is already NON-destructive — it returns
`green/red/yellow/inconclusive` only (with the W64 env-down fix from PR #1237, 2026-06-09), and the CALLER
decides the action. The prior "0/3 → revert" was an imprecise description; the real code never reverts. So
LABEL+BLOCK mode = just map the existing outcome to a label + check-status, no change to the review logic.

**Trigger (unanimous): Pro-side cron-poll via `gh`, every 10 min.** NOT a GitHub Action (can't use Pro-local
Claude/Ollama → would expose diffs to cloud), NOT a webhook (always-on ingress surface). Pattern = the proven
`dlq_autopilot.py`: short-lived poll, `fcntl` lock, kill-switch, heartbeat, Telegram escalation.

**SAFE AUTONOMOUS BOUNDARY (the load-bearing constraint — LABEL + BLOCK, NEVER REVERT):**
The supervisor MAY:
- post a PR check-status `nuzantara/async-review-supervisor` (made a required check → blocks merge)
- apply labels: `review:auto-reject`, `review:needs-human`, `review:pii-local-only`, `review:green`
- comment concise findings + Telegram-escalate
- FAIL the required check on bad PRs (= blocks the merge, the legitimate "reject")
- run `branch_graveyard_cleanup.sh --apply` for category 1 (merged-safe) ONLY

The supervisor MUST NOT (v1): auto-merge, auto-revert, auto-close, delete unmerged branches, touch
cat.2/3 branches (zombie/stale stay report-only — the cicatrix invariant).

## 2. The uncomfortable truth (DeepSeek)

A reviewer is ONE bottleneck, not THE bottleneck. The branch/stash hygiene mess (75 branches, 32 stash,
39 dead DLQ) is ORTHOGONAL — a review-gate does not fix it. Ship #3 reduces incoming-PR noise; it does not
clean the backlog. Calibrate expectations accordingly.

## 3. Ship-plan (smallest safe slice first)

1. **V1 (this PR, M5 dev):** `scripts/async_review_supervisor.py` — poll `gh` for open PRs, detect changed
   files, run a PII per-path gate, invoke `codex_tri_llm_review.py`, write **labels + a check-status +
   a comment** (LABEL-ONLY/BLOCK mode — no merge, no revert). fcntl lock + kill-switch (`REVIEW_SUPERVISOR_OFF=1`)
   + heartbeat file. Dry-run default (`--apply` to actually write to GitHub). Unit-tested where logic is pure.
2. **Patch `codex_tri_llm_review.py`:** Claude backend = `claude --print` CLI; DeepSeek behind non-PII gate;
   `--no-auto-merge --no-auto-revert` flags; explicit exit-code → supervisor-action mapping.
3. **Pro daemon (NOT this session — needs a Pro session):** launchd plist every 10 min, logs to ops, Telegram on fail.
4. **Branch protection:** make `nuzantara/async-review-supervisor` a required check (else W69 repeats: runs≠gates).
5. **Branch cleanup wiring:** `--apply` cat.1 only; cat.2/3 report-only (existing invariant).

## 4. V1 scope boundary (what THIS PR does vs defers)

- THIS PR: the supervisor script in dry-run + label-only design, + tests. NO daemon armed, NO branch-protection
  change (those are write-ops on the Pro / GitHub settings → operator/Pro-session decisions).
- DEFERRED to a Pro session: launchd install, required-check wiring, first live `--apply` run.

## 5. Acceptance criteria (falsifiable)

- `python scripts/async_review_supervisor.py --pr <n> --dry-run` prints the intended labels/status/comment
  for a real open PR WITHOUT writing to GitHub. exit 0.
- grep proves: zero Anthropic-API import in the touched code; the Claude path shells out to `claude` CLI.
- PII gate: a diff touching `kb/`/`fixtures/`/`crm/` is routed away from DeepSeek cloud (unit-tested).
- The script NEVER calls `gh pr merge`, `gh pr close`, `git revert`, or `git branch -D` on unmerged branches
  (grep = 0 hits for those in the supervisor).
