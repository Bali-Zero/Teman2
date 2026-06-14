# Dirty Main NLM Research Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `dirty-main-nlm-research-triage`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_155349.md`
Source prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260614_155349.prompt.md`
Owner: next ops or research agent touching `/Users/nuzantara/Desktop/nuzantara`
Decision deadline: 2026-06-14 20:00 WITA

## Scope

Resolve the broad dirty-checkout signal in `/Users/nuzantara/Desktop/nuzantara`
without changing Spark LaunchAgents, deploying, or cleaning files from an
unrelated isolated worktree.

This spec is deliberately a coordination artifact. The confirmed issue is not a
Codex/Spark lifecycle failure; it is a shared checkout with mixed executable
changes, generated research outputs, publishable article content, operational
docs, and likely archive or ignore candidates. The safe remediation is to
preserve the live evidence and define a controlled triage plan for the agent
that owns the dirty checkout.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`. The peer `mini` was unreachable
  during the session-start sync check, so cross-machine sync was not verified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260614_155505-spark-dispatch-20260614_155349-scout-dirty-main-nlm-research-triage-20260614_155505`.
- Spark lifecycle is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 2066`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `runs = 89`, `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `runs = 58`, `last exit code = 0`, `run interval = 180 seconds`.
- Codex state files under `/Users/nuzantara/.agent/decisions/state` are fresh
  around 15:54-15:56 WITA for Spark loop, alarm, harvester, overnight runner,
  bad exits, and related sentinels. Stale Codex state is not supported by the
  live evidence.
- Fresh non-zero LaunchAgent exits are outside the Spark/Codex lifecycle cluster:
  `com.matagaruda.redis-split-brain.check`, `com.matagaruda.consumer-lag.check`,
  `com.balizero.wr2.plist-watchdog`, `com.balizero.wr2.sla-worker`, and
  `com.balizero.wr2.html-apply`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` remains broadly dirty
  with modified NLM pipeline files, sentinel/autopilot scripts, docs, generated
  research deltas, article MDX files, `outputs/`, and `apps/crm-cell/war-room/`.

## Root-Cause Classification

Primary cluster: mixed NLM/research/content work left in the shared `main`
checkout.

The LaunchAgent evidence does not justify restarting, unloading, rewriting, or
otherwise remediating `com.nuzantara.codex-spark-*`. The actionable signal is
that multiple ownership domains are dirty in the root checkout and need explicit
classification before any commit, archive, or cleanup.

## Triage Buckets

| Bucket | Paths from live status | Default action | Required validation |
| --- | --- | --- | --- |
| Executable NLM pipeline changes | `apps/evaluator/nlm_deep_research/*.py`, `apps/evaluator/nlm_deep_research/*.json`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Inspect diffs first; split by behavioral owner before commit. | Focused Python compile or tests for touched modules; no new provider API-key dependency or credential path. |
| Automation and sentinel code | `scripts/curiosity_loop.sh`, `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Commit only if the diff has a single operational purpose; otherwise split or park. | Shell syntax for `.sh`; Python compile/tests for `.py`; verify no launchd restart is required. |
| Generated research/output artifacts | `apps/evaluator/nlm_deep_research/output/multimodal/`, `outputs/`, `research/coherence-corpus/`, `research/commercial/`, `research/nb-health/*.md`, `research/regulatory/*-delta.json`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `apps/research/sota-social-2026-v1/kpi_timeline.csv` | Classify as keep, archive, or ignore candidate by provenance and reproducibility. Do not blanket-add. | JSON validity for deltas; size inventory; provenance note for generated folders. |
| Publishable content | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json` | Treat as editorial publish package, not pipeline code. Commit separately from executable changes. | Frontmatter/MDX parse or existing content validation; verify `published_articles.json` is valid JSON and matches slugs. |
| Ops docs and escalation records | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `shared/escalations_pro.jsonl`, `research/operations/*.md`, `apps/crm-cell/war-room/` | Keep only if the docs reflect current live state; split client-sensitive material from internal ops records. | JSONL validity for escalation records; manual privacy scan for CRM/client content. |

## Handoff Procedure

Run these from the shared checkout only after confirming no other operator is
actively editing the same files:

```bash
cd /Users/nuzantara/Desktop/nuzantara
git status --short --branch
git diff --name-only
git diff --cached --name-only
find apps/evaluator/nlm_deep_research/output outputs research/coherence-corpus research/commercial -maxdepth 2 -type f 2>/dev/null | sort | head -200
```

Then produce `/tmp/dirty-main-nlm-triage-20260614.md` with one row per dirty path:

| Path | State | Bucket | Owner | Action | Validation | Notes |
| --- | --- | --- | --- | --- | --- | --- |

Use these action labels:

- `commit-code`: executable behavior change with focused tests.
- `commit-content`: publishable MDX/data package with content validation.
- `commit-docs`: internal docs or ops records with privacy scan.
- `archive-generated`: generated research output that should move to an archive
  or storage location instead of the repo.
- `ignore-generated`: reproducible local output that should be added to ignore
  rules only after confirming no published workflow depends on it.
- `park-followup`: unclear ownership or insufficient validation.

## Commit Order

1. Executable NLM pipeline changes, split by module owner.
2. Sentinel/autopilot script changes, split from NLM pipeline behavior.
3. Publishable content package, including `published_articles.json` only if it
   matches the MDX slugs.
4. Ops docs and escalation records after privacy review.
5. Generated output archival or ignore-rule changes after provenance review.

Never mix these into one commit. The current checkout spans code, generated
data, editorial content, and operational records; a single commit would erase
the ownership boundary that the triage is meant to restore.

## Non-Goals

- Do not restart, unload, rewrite, or kickstart `com.nuzantara.codex-spark-*`.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  `secrets/*`.
- Do not change `backend/app/dependencies.py` unless the full import-chain check
  is run.
- Do not clean the shared checkout from an unrelated isolated worktree.
- Do not use `git add -A`, `--no-verify`, force push, or reset the shared
  checkout.

## Acceptance Criteria

- Spark/Codex lifecycle remains classified as non-actionable unless a new live
  check shows a stopped loop or fresh non-zero Spark alarm/harvester exit.
- Every dirty path in `/Users/nuzantara/Desktop/nuzantara` is assigned one of
  the bucket/action labels above.
- Executable changes have focused validation before commit.
- Generated outputs are either archived, ignored with a documented rationale, or
  deliberately committed with provenance.
- Publishable content is committed separately from code and generated output.
- No secrets, raw WhatsApp/OSINT exports, or client-private content are copied
  into the repo as part of triage.

## Next Step

Assign the next heavier agent to produce the triage matrix in the shared
checkout and then process one bucket at a time. If no owner can be established
for a file by the decision deadline, mark it `park-followup` and leave the file
untouched rather than silently deleting or committing it.
