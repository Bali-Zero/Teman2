# Main Dirty NLM Research Content Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `main-dirty-nlm-research-content`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_090651.md`
Source prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260614_090651.prompt.md`
Intervention branch:
`codex-overnight/spark-alarm-20260614_090723-spark-dispatch-20260614_090651-scout-main-dirty-nlm-research-content-20260614_090724`

## Scope

Resolve the Spark-dispatched dirty-checkout signal for
`/Users/nuzantara/Desktop/nuzantara` without touching the shared checkout from
this isolated overnight worktree.

This is a triage and handoff spec. The verified actionable cluster is repo
hygiene and commit grouping for NLM/research/content artifacts. The Spark
LaunchAgents do not need repair.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`.
- Peer check: Mini was unreachable during the session-start SSH probe, so
  peer git sync is unverified. This run stayed on Pro.
- Overnight worktree branch is correct and clean before this spec:
  `codex-overnight/spark-alarm-20260614_090723-spark-dispatch-20260614_090651-scout-main-dirty-nlm-research-content-20260614_090724`.
- Spark lifecycle is healthy:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1025`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer idle, `runs = 208`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer idle, `runs = 136`,
    `last exit code = 0`, `run interval = 180 seconds`.
  - `com.nuzantara.codex-overnight-runner`: `state = running`,
    `pid = 48654`.
- `~/.agent/decisions/state/launchd_bad_exits.json` at
  `2026-06-14 09:09:15` contained no `codex` labels. Current bad exits were
  non-Codex labels such as WR2, Matagaruda, OpenClaw, and domain-mesh jobs.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f451eedeedd05a21477570be3149e644a3`, with
  `origin/main...HEAD = 170 behind / 2 ahead`.
- The two ahead commits are local Mouth article translation commits:
  - `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
  - `c6d6b85fe feat(articles): add translations for ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms`
- Dirty surface in the shared checkout:
  - 2 staged tracked modifications:
    `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py`
  - 19 unstaged tracked modifications.
  - 914 untracked paths.
- Tracked files whose working-tree content matches `origin/main` byte-for-byte:
  - all modified `apps/evaluator/nlm_deep_research/*` NotebookLM ID files.
  - `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`.
  - `scripts/dlq_autopilot.py`.
  - `scripts/nuzantara-sentinel.py`.
- Tracked files that differ from `origin/main` and need separate review:
  - `apps/bali-intel-scraper/data/published_articles.json`
  - `apps/research/sota-social-2026-v1/kpi_timeline.csv`
  - `docs/AUTOMATIONS_REFERENCE.md`
  - `docs/DOCS_INVENTORY.md`
  - `scripts/curiosity_loop.sh`
  - `shared/escalations_pro.jsonl`
- Untracked comparison against `origin/main`:
  - 3 paths match `origin/main` byte-for-byte:
    `apps/mouth/src/content/articles/immigration/indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists.mdx`,
    `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.id.mdx`,
    `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.it.mdx`.
  - 2 paths exist on `origin/main` but differ locally:
    `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.id.mdx`,
    `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.it.mdx`.
  - 909 paths have no path on `origin/main`.
- Largest untracked/generated surfaces:
  - `apps/evaluator/nlm_deep_research/output/multimodal`: 47 MB.
  - `outputs`: 40 MB, including base64 chunks and client CSV exports.
  - `research/coherence-corpus`: 44 MB, 840 JSON files plus manifests.
  - `research/regulatory`: 68 KB, five daily delta JSON files.
  - `research/nb-health`: 144 KB, five daily health markdown files.

## Root-Cause Classification

Primary cluster: stale shared `main` checkout plus broad generated output.

The Spark report is actionable, but not because Spark is broken. The verified
problem is that the shared checkout is simultaneously:

1. 170 commits behind `origin/main`.
2. 2 commits ahead with local article translations.
3. Dirty with tracked files that mostly already match `origin/main`.
4. Carrying a large untracked NLM/research/content output surface.

The staged `scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py`
changes should not be committed from the shared checkout as new work: their
current content already matches `origin/main`. They are likely residue from
attempting to bring a stale checkout forward.

## File Plan

| Group | Paths | Current evidence | Plan | Validation before commit |
| --- | --- | --- | --- | --- |
| Spark and Codex LaunchAgents | `com.nuzantara.codex-spark-*`, `com.nuzantara.codex-overnight-*` | Spark loop running, timers idle exit 0, no Codex bad exits | Do not restart or modify LaunchAgents | `launchctl print` remains healthy |
| Staged remote-matching scripts | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | staged in shared checkout, content matches `origin/main` | Do not create a new commit for these from stale `main`; preserve status, then unstage only during owner-approved main cleanup | `cmp` against `origin/main` and focused script tests if changed again |
| Remote-matching NLM IDs | `apps/evaluator/nlm_deep_research/*`, `apps/mata-garuda/.../nlm_feeder.py` | content matches `origin/main` | Treat as stale-checkout residue, not new source work | byte comparison against `origin/main`; no behavior commit needed |
| Local-only generated corpus | `research/coherence-corpus/` | 840 JSON files, 44 MB, manifests started 2026-06-13 | Commit only if this corpus is intentionally versioned; otherwise archive or ignore in a dedicated generated-artifact decision | `jq -e .` on manifests and sampled JSON; privacy review |
| NLM multimodal artifact | `apps/evaluator/nlm_deep_research/output/multimodal/nb6/audio/20260611_nb6.m4a` | 47 MB output tree | Do not mix with source commits; store as artifact or commit under explicit media policy | file opens locally; no client/private content leak |
| Local outputs | `outputs/_b64chunks/`, `outputs/clients_all.csv`, `outputs/clients_master_clean.csv`, `outputs/_clients_b64.txt` | 40 MB, includes client CSV/base64 exports | Do not commit without privacy review. These may be client/CRM exports and must stay local unless sanitized | explicit owner approval plus sanitized-field check |
| Mouth content | new and differing `apps/mouth/src/content/articles/**/*.mdx` | 5 untracked MDX; 3 match origin, 2 differ from origin | Split content branch from generated data; discard duplicate remote copies only after preservation | frontmatter parse, content build or `npm run lint` in `apps/mouth` |
| Generated docs snapshots | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` | unstaged large generated diffs | Commit separately as generated docs only if produced by the canonical generator | rerun or identify generator; compare timestamp/source |
| Research deltas | `research/regulatory/*.json`, `research/nb-health/*.md`, `research/commercial/*.md`, SOTA weekly report | no path on `origin/main` | Candidate research artifact commit, separate from code and client exports | JSON validity, no secrets, no raw client data |
| Small code/data deltas | `scripts/curiosity_loop.sh`, `apps/research/sota-social-2026-v1/kpi_timeline.csv`, `shared/escalations_pro.jsonl` | differ from `origin/main` | Review as their own commit group; do not mix with NLM ID residue | focused script check; CSV/JSONL validity |

## Safe Cleanup Sequence For A Heavier Agent

Run from a fresh isolated worktree or with an explicit owner-approved recovery
session. Do not perform these from this overnight triage branch.

1. Preserve the shared checkout before changing anything:
   - record `git status --short --branch`.
   - save `git diff --cached` and `git diff` to `/tmp`.
   - record `git log --oneline origin/main..HEAD`.
2. Protect the two ahead article commits:
   - create a backup branch or PR for the two local commits before any
     synchronization step.
   - verify whether equivalent translated MDX already exists on `origin/main`.
3. Separate residue from real work:
   - files matching `origin/main` are not new commits.
   - duplicate untracked files matching `origin/main` are not new content.
4. Handle privacy-sensitive outputs first:
   - `outputs/clients_all.csv`, `outputs/clients_master_clean.csv`,
     `_clients_b64.txt`, and `_b64chunks/` need explicit privacy review.
   - do not push raw CRM/client exports.
5. Commit in small groups only after validation:
   - article/content branch.
   - research delta branch.
   - generated docs branch.
   - generated corpus/artifact branch only if policy says to version it.
   - code behavior branch for `curiosity_loop.sh` only if it still differs after
     rebasing the checkout to `origin/main`.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*`.
- Do not clean, reset, or unstage the shared checkout from this isolated branch.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not use `--no-verify`, force push, or direct `main` pushes.
- Do not commit raw OSINT, WhatsApp, CRM, or client exports without explicit
  sanitized-field review.

## Recommended Next Step

Dispatch a heavier cleanup agent with the exact objective:

> Preserve `/Users/nuzantara/Desktop/nuzantara` as-is, protect the two ahead
> article commits, then split the dirty surface into remote-matching residue,
> content, research artifacts, generated docs, and privacy-sensitive local
> outputs. Do not revert or delete anything until each group has an owner and
> validation result.

The first practical action should be preservation, not cleanup. The main
checkout is behind 170 commits and contains remote-matching staged files, so a
normal local commit from that checkout would create noisy duplicate history.
