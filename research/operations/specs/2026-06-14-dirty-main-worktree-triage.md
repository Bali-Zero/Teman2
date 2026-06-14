# Dirty Main Worktree Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `nuzantara-dirty-main-worktree`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_225513.md`
Intervention branch: `codex-overnight/spark-alarm-20260614_225545-spark-dispatch-20260614_225513-scout-nuzantara-dirty-main-worktree-20260614_225545`
Owner: next ops/heavy agent taking custody of `/Users/nuzantara/Desktop/nuzantara`
Decision deadline: 2026-06-15 12:00 WITA
Status: triage handoff, no cleanup performed

## Scope

Resolve the shared-checkout dirty/stalled signal in
`/Users/nuzantara/Desktop/nuzantara` without touching Spark LaunchAgents or
discarding operator/agent work in the main checkout.

This spec is intentionally a handoff document. The current overnight intervention
ran from an isolated worktree and did not edit, stash, unstage, reset, or clean
the shared checkout. The confirmed root cause is broad shared-checkout WIP plus
branch divergence, not a Spark lifecycle failure.

## Live Evidence

- Machine: Pro, `nuzantara@Nuzantara`.
- Session-start peer check: `mini` was unreachable, so peer git sync is
  unverified for this run.
- Root `AGENTS.md` was read. No path-specific `AGENTS.md` exists under
  `apps/backend-rag/`, `scripts/`, or `apps/backend-rag/backend/llm/`.
- Spark lifecycle is healthy and not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, active PID, `runs = 1`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: StartInterval job, `state = not running`,
    `runs = 26`, `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: StartInterval job,
    `state = not running`, `runs = 17`, `last exit code = 0`,
    `run interval = 180 seconds`.
  - `com.nuzantara.codex-overnight-runner`: `state = running`, active PID.
- `launchctl list` shows non-zero exits for non-Codex services such as
  `cost-breaker`, `mcp-integrity`, `intake-worker`, WR2/WR3 supervisors, and
  WA workers. These are secondary to this dispatch key.
- Shared checkout state:
  - path: `/Users/nuzantara/Desktop/nuzantara`
  - branch: `main`
  - divergence: `main...origin/main [ahead 2, behind 175]`
  - recent local HEAD: `e2b355f45 feat(articles): add translations for
    indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`

## Root-Cause Classification

Primary cluster: shared checkout is being used as durable WIP storage across
multiple agent/product streams.

The dirty state is not one atomic change. It contains at least five independent
clusters:

1. Staged operational code changes for the DLQ/sentinel heal loop.
2. Unstaged NotebookLM/NLM notebook ID and profile changes.
3. Generated or exported artifacts, including media output and client/export
   files.
4. Public content and research deliverables.
5. Auto-generated operations documentation drift.

Because the checkout is also `behind 175`, committing directly from main would
mix stale-base local commits with unrelated WIP. The safe path is to split
custody into dedicated worktrees and PRs.

## File Plan

| Path or cluster | Current state | Classification | Plan | Acceptance criteria |
| --- | --- | --- | --- | --- |
| `scripts/dlq_autopilot.py` | Staged modification, 55 added lines | Intentional operational code candidate | Move into a dedicated `ops` worktree/branch as its own patch. Keep separate from docs and NLM work. | Patch applies cleanly to current `origin/main`; `python -m py_compile scripts/dlq_autopilot.py` passes; manual CLI behavior for `clear` and `requeue` is documented or tested with a temp DLQ fixture before PR. |
| `scripts/nuzantara-sentinel.py` | Staged modification, 152 added / 2 changed lines | Intentional operational code candidate | Move into the same heal-loop PR as `dlq_autopilot.py` only if both describe the same W70 remediation. | Patch applies cleanly to current `origin/main`; `python -m py_compile scripts/nuzantara-sentinel.py` passes; focused sentinel status/DLQ dry-run validation is captured. |
| `apps/evaluator/nlm_deep_research/*.py`, `persona_definitions.json`, `t4_nb5_config.json` | Unstaged modifications | NotebookLM ID/profile rotation candidate | Move into a separate `nlm` or `ops` worktree/branch. Do not mix with W70 heal-loop code. | New notebook IDs are verified against the NLM source of truth; all hardcoded replacements are complete; `python -m compileall apps/evaluator/nlm_deep_research` passes from the appropriate virtualenv. |
| `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Unstaged modification from `--profile zero` to `--profile default` | Runtime behavior change candidate | Keep with the NLM profile branch only after confirming the intended NotebookLM CLI profile. | A live lightweight `nlm` profile check or documented operator confirmation exists; no fallback silently changes the profile for production jobs. |
| `scripts/curiosity_loop.sh` | Unstaged Python interpreter pin | Runtime environment fix candidate | Move into its own small ops PR unless it is proven to be part of the same DLQ incident. | `bash -n scripts/curiosity_loop.sh` passes; the selected Python path exists on Pro; fallback behavior is documented. |
| `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` | Unstaged generated docs drift | Generated docs | Commit only if regenerated from current live state after the code/runtime changes are settled. | Generator command, timestamp, and source state are recorded; docs are not manually edited. |
| `apps/bali-intel-scraper/data/published_articles.json` | Unstaged scraper state append | Generated data/state | Do not commit with code. Either regenerate in the owning scraper workflow or park as a data snapshot if the site pipeline requires it. | Owner confirms this file is expected in git; JSON validates; duplicate URL policy is checked. |
| `shared/escalations_pro.jsonl` | Unstaged JSONL append | Runtime/local state | Do not commit until reviewed for private content and operational relevance. | JSONL validates; no raw private/secret content; owner decides if this belongs in repo or local state. |
| `apps/mouth/src/content/articles/**` | Untracked MDX articles/translations | Public content candidate | Move to a content PR only after editorial/source review. | MDX builds; slugs are unique; source dates and translations are verified; no unpublished private notes included. |
| `research/nb-health/2026-06-10..14-health.md`, `research/regulatory/2026-06-10..14-delta.json`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `research/commercial/2026-W24-yield-opportunities.md` | Untracked research outputs | Research deliverables | Move into one research/archive PR after owner review. | Files are scrubbed for private raw content; JSON files validate; markdown has source/provenance notes. |
| `apps/evaluator/nlm_deep_research/output/multimodal/` | Untracked generated media, 167 MB, 8 files | Generated heavy artifact | Do not commit to git by default. Move to external artifact storage or a deliberate asset PR only if required. | Owner confirms retention location; repo size impact is checked before any commit. |
| `outputs/` | Untracked root exports, 40 MB, includes `_clients_b64.txt`, `_b64chunks/`, `clients_master_clean.csv`, `clients_all.csv` | Sensitive/generated export | Do not commit. Treat as local export until owner explicitly approves a sanitized derivative. | No raw client/export data enters git; if recurring, add a narrow ignore rule in a separate hygiene PR after owner review. |
| `research/coherence-corpus/` | Untracked JSON corpus, 44 MB | Generated/curated corpus candidate | Do not commit until data governance is decided. | Owner decides whether this is derived-safe; schema and privacy review pass; storage target is explicit. |
| `apps/crm-cell/war-room/interactive_cli.sh` | Untracked script | Code candidate | Inspect in a dedicated `cell` worktree before adding. | `bash -n` passes; script has no secrets or local-only absolute paths; ownership is clear. |

## Extraction Procedure

Use this only from a fresh dedicated worktree. Do not mutate the shared checkout
except to export read-only patches.

1. Create an owner worktree from current `origin/main`:

   ```bash
   cd /Users/nuzantara/Desktop/nuzantara
   python scripts/agent_start.py --lane ops --task-id w70-heal-loop-triage
   ```

2. Export the staged W70 code patch read-only:

   ```bash
   git diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py \
     > /tmp/w70-heal-loop-main-staged.patch
   ```

3. Apply only in the dedicated worktree:

   ```bash
   cd /Users/nuzantara/Desktop/nuzantara/.worktrees/ops-w70-heal-loop-triage
   git apply --check /tmp/w70-heal-loop-main-staged.patch
   git apply /tmp/w70-heal-loop-main-staged.patch
   ```

4. Validate, commit, push, and PR that branch before returning to any other
   cluster.

5. Repeat with a new worktree per cluster. Suggested lanes:
   - `ops`: W70 heal-loop scripts and `curiosity_loop.sh` if related.
   - `ops` or `mata-garuda`: NotebookLM ID/profile rotation.
   - `mouth`: MDX articles.
   - `intel` or `docs`: generated automation docs and research reports.
   - `cell`: `apps/crm-cell/war-room/interactive_cli.sh`.

## Commit Order

1. W70 heal-loop operational code:
   `fix(ops): restore dlq heal-loop diagnostics`
2. NotebookLM ID/profile rotation:
   `fix(nlm): refresh notebook ids and cli profile`
3. Python interpreter pin, if still needed and independently validated:
   `fix(ops): pin curiosity loop python runtime`
4. Public MDX content:
   `feat(articles): add june regulatory article translations`
5. Research/doc generated outputs:
   `docs(ops): refresh automation and research snapshots`
6. Ignore-rule hygiene, only after owner approval:
   `chore(gitignore): ignore local export artifacts`

Do not combine generated artifacts with executable code.

## Validation Matrix

| Cluster | Minimum validation |
| --- | --- |
| W70 heal-loop scripts | `python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py`; focused temp-fixture test for `requeue`; sentinel dry-run or status fixture proving enriched log-tail behavior. |
| NLM/NotebookLM changes | Activate the relevant venv; `python -m compileall apps/evaluator/nlm_deep_research`; verify the intended `nlm` profile and notebook IDs from source of truth. |
| `curiosity_loop.sh` | `bash -n scripts/curiosity_loop.sh`; `test -x "$HOME/.pyenv/versions/3.11.11/bin/python3" || test -x "$HOME/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3"`. |
| MDX articles | `cd apps/mouth && npm run lint` or the smallest existing content/MDX validation if full lint is too broad. |
| JSON/JSONL state | `python -m json.tool` for JSON files; line-by-line JSON parse for JSONL. |
| Heavy/generated artifacts | `du -sh`; privacy review; storage decision before git add. |

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*`.
- Do not deploy.
- Do not use `--no-verify`, force push, or reset the shared checkout.
- Do not commit directly from `/Users/nuzantara/Desktop/nuzantara` while it is
  divergent and dirty.
- Do not stage `outputs/` or raw client/export material.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not treat Mini peer unreachability as proof that local-only cleanup is safe.

## Next Step

The next heavy agent should start with the W70 staged code because it is already
curated in the index and has the clearest operational intent. If it cannot apply
cleanly to current `origin/main`, stop that PR and write a conflict note rather
than normalizing the main checkout.

Only after the W70 patch has its own PR should the NLM/profile changes and
generated outputs be triaged. The main checkout should remain untouched until an
owner explicitly decides whether to preserve, migrate, or discard each cluster.
