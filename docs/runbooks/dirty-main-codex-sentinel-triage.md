# Dirty Main Codex Sentinel Triage

Last verified: 2026-06-15 00:50 WITA on Pro (`nuzantara@Nuzantara`)

## Classification

Status: `blocked-human-ownership`

The actionable signal is the shared checkout at `~/Desktop/nuzantara`, not the
Spark lifecycle. Spark itself was healthy at verification time:

- `com.nuzantara.codex-spark-loop` had an active PID and `state = running`.
- `com.nuzantara.codex-spark-alarm` and `com.nuzantara.codex-spark-harvester`
  were idle timer jobs with last exit `0`.
- Codex state files for spark loop/alarm/harvester had fresh mtimes around the
  current overnight run window.

The shared checkout was still dirty and stale:

- `git status --short --branch` in `~/Desktop/nuzantara` reported
  `## main...origin/main [ahead 2, behind 175]`.
- The checkout had broad unstaged edits across rules, NLM pipelines, docs,
  sentinels, escalations, published article metadata, research outputs, and
  generated article files.
- Two files were staged in the shared checkout:
  - `scripts/dlq_autopilot.py`
  - `scripts/nuzantara-sentinel.py`

## Script Diff Verdict

Do not move the staged script changes into a new branch as-is.

Live comparison showed the staged changes are not new work waiting for a Codex
PR. They are old W70 sentinel/autopilot edits on a stale local `main` base:

- `scripts/dlq_autopilot.py` staged `requeue_terminal(...)`.
- `scripts/nuzantara-sentinel.py` staged W70 real-stderr enrichment,
  recovered-terminal resurrection, and blind-heal-loop alerting.
- The clean overnight branch based on `origin/main` already contains these
  symbols.
- `origin/main` includes the merged W70/W81 follow-ups, including:
  - `6938d3883 fix(sentinel): close the blind heal-loop... (#1413)`
  - `c454afb3d fix(sentinel): bound enrich tail (OOM)... (#1418)`

Therefore the staged script diffs are a stale-residue/dirty-main problem, not a
fresh code defect. A follow-up agent must not recommit them blindly.

## Safe Operator Path

Use this sequence from a human-controlled terminal or a single explicitly-owned
cleanup agent. Do not run it from a generic overnight agent unless that agent is
assigned ownership of the shared checkout cleanup.

1. Preserve evidence outside the repo before touching `main`:

   ```bash
   mkdir -p ~/Desktop/nuzantara-main-triage/20260615
   cd ~/Desktop/nuzantara
   git status --porcelain=v1 > ~/Desktop/nuzantara-main-triage/20260615/status.txt
   git diff --cached > ~/Desktop/nuzantara-main-triage/20260615/staged.patch
   git diff > ~/Desktop/nuzantara-main-triage/20260615/unstaged.patch
   git log --oneline --left-right --cherry-pick main...origin/main \
     > ~/Desktop/nuzantara-main-triage/20260615/divergence.txt
   ```

2. Handle the two local commits first. At verification time `main` was ahead of
   `origin/main` by two commits. At least one was an article-translation commit.
   Cherry-pick any still-needed local commit onto a dedicated branch and open a
   normal PR before attempting to fast-forward shared `main`.

3. For the staged script files, compare against current `origin/main`. If there
   is no semantic delta beyond already-merged W70/W81 code, unstage and discard
   only those script hunks after the evidence bundle exists and the checkout
   owner explicitly approves cleanup:

   ```bash
   git diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
   git diff origin/main -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
   ```

4. Triage broad unstaged changes by ownership bucket, not all at once:

   - Rule/cicatrix docs: `.claude/rules/*`
   - NLM research pipeline edits: `apps/evaluator/nlm_deep_research/*`
   - Generated/publication outputs: `apps/mouth/src/content/articles/*`,
     `apps/bali-intel-scraper/data/published_articles.json`, `outputs/`
   - Research snapshots: `research/*`
   - Ops docs and escalation logs: `docs/*`, `shared/escalations_pro.jsonl`

5. Only after owned work is preserved or intentionally discarded should the
   shared checkout be fast-forwarded to `origin/main`.

## Non-Goals

- Do not deploy.
- Do not run `git reset --hard`.
- Do not force-push.
- Do not commit from `~/Desktop/nuzantara` until the owner of the broad dirty
  work is known.
- Do not re-open the W70 sentinel/autopilot changes as a new PR unless a fresh
  delta against `origin/main` is demonstrated.
