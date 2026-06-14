# Main Worktree Large Dirty Snapshot Triage - 2026-06-15

Date: 2026-06-15
Dispatch key: `main-worktree-large-dirty-snapshot`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_050517.md`
Spark prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260615_050517.prompt.md`
Spark JSONL: `/Users/nuzantara/logs/codex-spark-loop/scout-20260615_050517.jsonl`
Shared checkout: `/Users/nuzantara/Desktop/nuzantara`
Decision owner: next heavier ops agent or human checkout owner

## Scope

Classify and drain the dirty shared checkout without repairing Spark, restarting
LaunchAgents, deploying, or normalizing unrelated files.

This is a decision-only remediation. The shared checkout has multi-surface WIP,
staged executable changes, large generated artifacts, and likely client-facing
or client-derived output. The safe action from an isolated overnight worktree is
to record a triage plan and leave the shared checkout untouched.

## Live Evidence

- Machine: Pro, `nuzantara@Nuzantara`.
- Peer check: `mini` was unreachable during the session-start SSH check, so
  peer git sync is unverified for this run.
- Overnight runner worktree:
  `codex-overnight/spark-alarm-20260615_050636-spark-dispatch-20260615_050517-scout-main-worktree-large-dirty-snapshot-20260615_050636`,
  clean before this spec was created.
- Spark lifecycle is not the actionable cluster:
  - `launchctl list` shows `1212 0 com.nuzantara.codex-spark-loop`.
  - `launchctl list` shows idle timer jobs with exit `0` for
    `com.nuzantara.codex-spark-alarm` and
    `com.nuzantara.codex-spark-harvester`.
  - `launchctl list` shows `com.nuzantara.codex-overnight-feeder` at exit `0`
    and the overnight runner active for this intervention.
- Spark state is fresh enough to avoid stale-state cleanup:
  `/Users/nuzantara/.agent/decisions/state` had Spark, harvester, alarm, and
  runner state files updated around 05:05-05:07 WITA.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is the actionable signal:
  - branch: `main...origin/main [ahead 2, behind 176]`
  - HEAD: `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
  - staged files:
    - `scripts/dlq_autopilot.py`
    - `scripts/nuzantara-sentinel.py`
  - unstaged tracked diff: 22 files, about 2,303 insertions and 1,634 deletions
  - untracked file count: 921
  - large untracked groups observed:
    - `apps/evaluator/nlm_deep_research/output/multimodal/` - 167M
    - `research/coherence-corpus/` - 44M
    - `outputs/` - 40M

## Root-Cause Classification

Primary cluster: shared-checkout work accumulation across multiple owners.

The evidence does not support a Spark LaunchAgent repair. The root issue is that
the shared `main` checkout has become a mixed holding area for operational fixes,
NotebookLM research pipeline changes, generated research/media outputs, Mouth
articles/translations, CRM war-room artifacts, regulatory deltas, docs inventory
updates, and local output files. Because `main` is also behind origin by 176
commits, cleanup must preserve local work before any pull/rebase attempt.

## Category Plan

| Category | Paths | Rationale | Acceptance criteria before action |
| --- | --- | --- | --- |
| `commit-ready` after validation | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Already staged together. The diff appears to be one W70 DLQ/sentinel heal-loop cluster: enrich bare cron failures from real logs, clear recovered terminal DLQ entries, add blind-loop alerting, and add an operator `requeue` path. | Validate with the backend venv Python: `cd /Users/nuzantara/Desktop/nuzantara && apps/backend-rag/.venv/bin/python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py`. Then run the smallest available sentinel/DLQ tests or a read-only dry run. Commit separately as an executable ops fix only if validation passes. |
| `needs-review` | `apps/backend-rag/requirements.txt` | Security bump from `certifi>=2026.4.22` to `certifi>=2026.5.20`; executable dependency surface. | Verify the version exists in the configured package index and run backend import-chain plus focused dependency install/check in a disposable venv or CI branch. Do not bundle with generated outputs. |
| `needs-review` | `apps/evaluator/nlm_deep_research/*.py`, `apps/evaluator/nlm_deep_research/*.json`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`, `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py` | Notebook IDs, NLM CLI profile, and research pipeline behavior changed. These are operationally meaningful and may depend on local logged-in NotebookLM state. | Confirm the notebook IDs and profile are current from the machine that runs the NLM workflows. Compile the changed Python files with the project venv and run a single safe dry-run per pipeline before committing. |
| `needs-review` | `.claude/rules/cicatrix-scars.md`, `.claude/rules/cicatrix-scars-archive.md`, `.claude/rules/cicatrix-superscar.md`, `scripts/scar_query.py` | Memory/rules lifecycle changes affect agent behavior and should be reviewed as one rules-governance cluster. | Review for duplicated scars, accidental private data, and command correctness. Commit as docs/tooling only after `scripts/scar_query.py` compiles if retained. |
| `needs-review` | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json` | Client-facing editorial content and publication ledger changed together. | Run the Mouth content validation/build path, confirm slugs/locales/source citations, and commit article groups atomically by story or campaign. |
| `needs-review` | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `shared/escalations_pro.jsonl` | Automation reference, generated docs inventory, and escalation ledger are operational records. | Confirm generator provenance and timestamp, check for secrets/private client data, then commit docs inventory separately from runtime code. |
| `needs-review` | `apps/crm-cell/war-room/`, `research/commercial/`, `outputs/clients_all.csv`, `outputs/clients_master_clean.csv` | These paths may contain client or commercial data. They must not be bulk-added by an automated cleanup pass. | Inspect locally for privacy, ownership, and intended destination. If retained, move through the sanctioned CRM/commercial artifact flow, not a generic repo commit. |
| `generated-output/archive` | `apps/evaluator/nlm_deep_research/output/multimodal/`, `research/coherence-corpus/`, `research/nb-health/*.md`, `research/nb-monitor/`, `research/regulatory/*-delta.json`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md` | Looks like generated research, media, health, and delta output. Some may be durable evidence, but it should not be mixed into code commits. | Decide per producer whether the artifact belongs in git, object storage, Drive, or local archive. If committed, include manifests/checksums and keep binary media out unless the repo already owns that artifact class. |
| `discard/ignore` candidate | `outputs/_b64chunks/*`, `outputs/_clients_b64.txt` | Chunked/base64 scratch output is likely transport residue and high-risk to commit accidentally. | Do not delete automatically. First verify it is reproducible or already consumed, then remove locally or add a narrow ignore rule in a separate reviewed change if this pattern recurs. |

## Heavier-Agent Procedure

1. Freeze evidence before touching anything:

   ```bash
   cd /Users/nuzantara/Desktop/nuzantara
   git status --short --branch > /tmp/main-dirty-status-20260615.txt
   git diff --cached --stat > /tmp/main-dirty-staged-stat-20260615.txt
   git diff --stat > /tmp/main-dirty-unstaged-stat-20260615.txt
   git ls-files --others --exclude-standard > /tmp/main-dirty-untracked-20260615.txt
   ```

2. Preserve the two local commits on `main` before any sync with origin. Because
   the checkout is `ahead 2, behind 176`, do not `pull`, `rebase`, reset, or
   switch branches until staged/untracked work is either committed to scoped WIP
   branches or saved with path-specific stashes that include untracked files.

3. Drain one category at a time. Prefer separate commits or branches for:
   operational sentinel/DLQ fixes, dependency updates, NLM pipeline changes,
   editorial Mouth content, generated research artifacts, rules/memory tooling,
   and private/commercial outputs.

4. Never use `git add -A` from the shared checkout. Stage explicit paths only.

5. Validate each executable category before commit. Suggested minimums:

   ```bash
   cd /Users/nuzantara/Desktop/nuzantara
   apps/backend-rag/.venv/bin/python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py scripts/scar_query.py
   cd apps/backend-rag && source .venv/bin/activate && python -c "from backend.app.dependencies import get_current_user; print('OK')"
   ```

6. For Mouth content, run the repo's content/build validation after the article
   set is staged, not before unrelated generated outputs are mixed in.

7. Only after the worktree is clean should the owner update `main` from origin.

## Non-Goals

- Do not restart, unload, rewrite, or redeploy `com.nuzantara.codex-spark-*`.
- Do not production deploy.
- Do not modify `backend/prompts/zantara_core.py`.
- Do not modify `fly.toml`, `.env*`, or `secrets/*`.
- Do not copy OSINT, WhatsApp, CRM, or commercial raw data out of the Pro-local
  sanctioned locations.
- Do not discard, reset, clean, or unstage another owner's files without a
  category-specific preservation step.
- Do not use `--no-verify`, force push, or bypass protected-branch approvals.

## Stop Conditions

Stop and write a blocked status instead of mutating the checkout if any of the
following are true:

- The owner of the staged sentinel/DLQ diff cannot be identified.
- A candidate generated-output group contains client raw data, secrets, private
  WhatsApp/OSINT material, or credentials.
- `main` has new local commits or staged files after this spec's evidence freeze.
- Validation for an executable category fails and the fix is not obvious.

## Next Step Recommendation

Start with the staged DLQ/sentinel cluster because it is already isolated in the
index and has an obvious validation path. Then handle private/commercial outputs
and generated artifacts before any branch synchronization, so large or sensitive
files cannot be accidentally swept into a later commit.
