# Dirty Main Worktree Triage - 2026-06-15

Date: 2026-06-15 00:15 WITA
Dispatch key: `dirty-main-worktree-triage-2026-06-14`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_001218.md`
Source prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260615_001218.prompt.md`
Owner: next heavier Ops/worktree-triage agent
Decision deadline: 2026-06-15 12:00 WITA

## Scope

Resolve the dirty shared checkout signal in `/Users/nuzantara/Desktop/nuzantara`
without modifying that checkout from an unrelated isolated worktree.

This spec is a decision and handoff artifact. The safe remediation for this
overnight run is to classify the dirty surfaces and define validation gates. It
does not unstage, clean, stash, commit, or delete files in the shared checkout.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`. Mini SSH returned unreachable during
  session start, so peer git sync is unverified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260615_001316-spark-dispatch-20260615_001218-scout-dirty-main-worktree-triage-2026-06-14-20260615_001316`.
- Path-specific `AGENTS.md` search under `apps/backend-rag/`, `scripts/`, and
  `apps/backend-rag/backend/llm/` found no additional files beyond the root
  `AGENTS.md`.
- Spark lifecycle is not the actionable failure:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `runs = 67`, `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `runs = 42`, `last exit code = 0`, `run interval = 180 seconds`.
  - `com.nuzantara.codex-overnight-runner`: `state = running`, `pid = 4174`,
    `last exit code = 0`.
- Spark and runner state files under `/Users/nuzantara/.agent/decisions/state`
  were updated around 2026-06-15 00:12-00:13 WITA, including dispatched,
  promoted, harvester, and runner-active records.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45`. It is `ahead 2, behind 175` relative to `origin/main`.
- Shared checkout status has:
  - 2 staged modified files: `scripts/dlq_autopilot.py`,
    `scripts/nuzantara-sentinel.py`.
  - 21 unstaged modified tracked files.
  - 27 untracked status paths that expand to 919 untracked files via
    `git ls-files --others --exclude-standard`.
- Largest untracked generated/output surfaces observed:
  - `apps/evaluator/nlm_deep_research/output`: 171 MB.
  - `research/coherence-corpus`: 44 MB, 840 files.
  - `outputs`: 40 MB, 51 files.

## Root-Cause Classification

Primary cluster: dirty shared `main` checkout with mixed ownership and mixed
artifact types.

The confirmed actionable signal is not Spark launchd repair. It is the shared
checkout state: staged script changes, many unstaged code/docs/data changes,
large generated outputs, and a `main` branch that has diverged significantly
from `origin/main`. The risk is accidental loss or accidental commit of someone
else's staged work, generated artifacts, or sensitive local data.

## Triage Buckets

| Bucket | Paths | Required decision |
| --- | --- | --- |
| Commit-ready candidates after validation | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | These are already staged. Treat them as owned WIP, not automation debris. Inspect diffs, identify owner/context, run focused script validation, then commit together only if they belong to the same remediation. Otherwise split with partial staging. |
| Commit-ready candidates after content/build validation | `apps/mouth/src/content/articles/**/*.mdx`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `research/operations/2026-06-11-*.md`, `research/commercial/2026-W24-yield-opportunities.md`, `.claude/rules/cicatrix-superscar.md` | Review factual claims and client/internal boundary, then commit as content/research docs only if sanitized. Run the smallest affected frontend/content validation before committing MDX. |
| Generated output or archive candidate | `apps/evaluator/nlm_deep_research/output/multimodal/`, `outputs/`, `research/coherence-corpus/`, `research/regulatory/2026-06-*-delta.json`, `research/nb-health/2026-06-*-health.md`, `apps/bali-intel-scraper/data/published_articles.json`, `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` | Do not bulk commit. Decide whether each surface is canonical source data, generated cache, or operator artifact. If generated, either archive outside Git or add/adjust ignore rules in a separate reviewed PR. |
| Investigate before touch | `apps/evaluator/nlm_deep_research/*.py`, `apps/evaluator/nlm_deep_research/*.json`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`, `scripts/curiosity_loop.sh`, `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py`, `scripts/scar_query.py`, `apps/crm-cell/war-room/interactive_cli.sh`, `shared/escalations_pro.jsonl`, `.claude/rules/cicatrix-scars*.md` | These cross executable logic, local ops, rules, and possible sensitive data. Require owner/context and focused validation before staging. Never include raw `shared/escalations_pro.jsonl` or client/OSINT-derived data in a broad cleanup commit. |

## Handoff Procedure

1. Freeze a fresh status snapshot from the shared checkout:
   `git status --short --branch`,
   `git diff --cached --name-status`,
   `git diff --name-status`, and
   `git ls-files --others --exclude-standard`.
2. Confirm branch divergence before any branch switch or pull:
   `git rev-list --left-right --count origin/main...main`.
3. Preserve staged script ownership:
   inspect `scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py` first.
   Do not unstage or overwrite them unless the owner explicitly chooses that.
4. Split decisions by bucket:
   one commit or follow-up PR per ownership cluster. Do not combine executable
   NLM changes, generated corpus files, MDX content, and local escalation data.
5. For generated output, prefer an ignore/archive decision over adding large
   untracked directories to Git. If a generated artifact is intended to be
   canonical, include its generator command and checksum in the commit message
   or accompanying docs.
6. For any file that may contain client, WhatsApp, CRM, OSINT, or escalation
   material, review locally on Pro only and commit only sanitized derived fields.

## Minimal Validation Matrix

| Surface | Suggested validation before commit |
| --- | --- |
| Staged scripts | `python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py`; then run any existing focused tests or dry-run flags found in those scripts. |
| NLM evaluator code | Activate the relevant venv and run the narrow NLM/evaluator tests or smoke commands. If no tests exist, document the missing coverage before committing. |
| MDX articles | Run the affected frontend/content lint or build check from `apps/mouth` before PR. |
| Generated inventories/docs | Re-run the generator that owns the file, then confirm the diff is reproducible. |
| Large untracked outputs | Validate file type and retention need; do not commit b64 chunks, local CSV extracts, or audio outputs without explicit ownership. |

## Recommended Commit Order

1. Staged scripts, only after focused validation:
   `fix(ops): harden dlq and sentinel automation`.
2. Sanitized docs/research deliverables:
   `docs(ops): add June worktree research artifacts`.
3. Public content articles, after frontend/content validation:
   `feat(articles): add June immigration and tax updates`.
4. Generated-output policy or ignore updates:
   `chore(repo): classify generated research outputs`.

If a bucket cannot be validated by the deadline, leave it untouched and write a
follow-up spec rather than committing it opportunistically.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean, stash, unstage, or commit the shared checkout from this isolated
  overnight worktree.
- Do not force-push, use `--no-verify`, bypass branch protection, or push
  directly to `main`.

## Next Step

Assign a heavier owner to run the handoff procedure directly from
`/Users/nuzantara/Desktop/nuzantara` on Pro. The first safe action is not
cleanup; it is ownership confirmation for the two staged scripts, followed by a
bucketed decision on generated outputs and sensitive local artifacts.
