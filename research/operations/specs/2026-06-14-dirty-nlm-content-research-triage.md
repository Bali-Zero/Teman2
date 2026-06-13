# Dirty NLM Content Research Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `dirty-nuzantara-nlm-content-research`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_041524.md`
Owner: NLM/content/research pipeline owner
Decision deadline: 2026-06-14 12:00 WITA

## Scope

Resolve the dirty shared-checkout signal in `/Users/nuzantara/Desktop/nuzantara`
without touching Spark LaunchAgents, production systems, or unrelated operator
work.

This triage spec is deliberately decision-only. The shared checkout contains a
mixed NLM pipeline change set, content publishing artifacts, generated research
corpora, operational docs, and local output files. Some untracked paths look
potentially client-sensitive. The safe remediation is to define the ownership,
validation, commit order, and drop/archive boundaries, then leave the dirty files
intact for the owning session or a heavier agent.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`.
- Mini peer check: unreachable from this session, so Pro/Mini sync is
  unverified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260614_044854-spark-dispatch-20260614_041524-scout-dirty-nuzantara-nlm-content-research-20260614_044854`.
- Isolated worktree HEAD:
  `9a87de3ce fix(wa-mirror): deaf-session watchdog rests during quiet hours WITA (W77) (#1408)`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`.
- Shared checkout relation to `origin/main`: ahead 2, behind 161.
  Local unpushed commits:
  - `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
  - `c6d6b85fe feat(articles): add translations for ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms`
- Shared checkout dirty state, verified live at 2026-06-14 04:51 WITA:
  - 17 tracked files modified.
  - Untracked bulk includes 51 files under `outputs/`, 840 files under
    `research/coherence-corpus/`, one multimodal audio artifact, five article
    MDX files, five NB health reports, four regulatory deltas, two operations
    research docs, two scripts, one CRM war-room script, and one
    `research/commercial/` path not present in the Spark snapshot.
- Large untracked directories:
  - `outputs/`: 40M.
  - `research/coherence-corpus/`: 44M.
  - `apps/evaluator/nlm_deep_research/output/multimodal/`: 47M.
  - `research/commercial/`: 16K.
- Spark lifecycle is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1025`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
  - `com.nuzantara.codex-overnight-runner`: `state = running`, `pid = 18380`.
- Current `launchctl list` no longer shows a non-zero
  `com.nuzantara.mcp-integrity`; it is `- 0`. Remaining non-Codex bad exits
  include `com.matagaruda.redis-split-brain.check`,
  `com.matagaruda.consumer-lag.check`, `com.balizero.wr2.plist-watchdog`, and
  `com.balizero.domain-mesh.foundations.daily`.

## Root-Cause Classification

Primary cluster: an NLM/content/research working set was left in the shared
checkout while `main` itself is stale and contains two local unpushed commits.

The LaunchAgent evidence does not support a Spark lifecycle repair. The
actionable signal is repo hygiene and handoff risk: executable changes, generated
outputs, content files, and potentially sensitive CSV artifacts are mixed in the
same dirty checkout with no owner-visible commit plan.

## File Plan

| Path or cluster | Current state | Plan | Owner | Acceptance criteria |
| --- | --- | --- | --- | --- |
| `apps/evaluator/nlm_deep_research/*` notebook ID changes | Tracked modifications | Keep only if these new NotebookLM IDs are current and reachable. Commit separately as NLM config rotation. | NLM pipeline owner | Verify each new notebook ID with `nlm` using the intended profile. Run focused import/compile checks for the touched modules. No hardcoded secret changes. |
| `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Tracked modification | Keep only after confirming `--profile default` is the production profile for the feeder. Do not bundle with content artifacts. | Mata Garuda/NLM feeder owner | Run a dry-run or mocked feeder validation proving URL and text source add commands build with the expected profile. If `zero` remains canonical, revert or parameterize profile via env. |
| `scripts/curiosity_loop.sh` | Tracked modification | Keep as a separate ops fix only if py3.11.11 path exists on Pro and backend venv fallback is valid. | Ops automation owner | Run `bash -n scripts/curiosity_loop.sh` and a non-destructive smoke path. Confirm no system Python fallback is selected during normal Pro execution. |
| `docs/AUTOMATIONS_REFERENCE.md` | Tracked generated modification | Keep only if regenerated from the canonical script and current live state. | Ops documentation owner | Re-run `scripts/generate_automations_reference.py` or the documented generator. Commit generated docs separately from behavior changes. |
| `apps/bali-intel-scraper/data/published_articles.json` | Tracked generated data modification | Keep only with the articles/content batch that consumed these URLs. | Content pipeline owner | JSON validates, entries correspond to actual published or intentionally queued article artifacts, and duplicates are checked. |
| `apps/mouth/src/content/articles/**/*.mdx` new files | Untracked content artifacts | Keep in a content PR only after editorial/source review. | Mouth/content owner | Frontmatter validates, source claims are reviewed, localization variants match, and `apps/mouth` build or focused content validation passes. |
| `shared/escalations_pro.jsonl` | Tracked append | Review before commit. This may contain operational or private context. | Ops owner | JSONL validates and no private/client material is exposed beyond the intended internal log boundary. Commit separately or archive locally. |
| `research/nb-health/*.md`, `research/regulatory/*.json`, `research/operations/*.md`, `research/commercial/` | Untracked research artifacts | Keep only if they are durable research deliverables. Otherwise archive outside git or fold summaries into a single reviewed report. | Research owner | Each retained artifact has provenance, no secrets/client raw data, and belongs in the repo rather than runtime storage. |
| `research/coherence-corpus/` | Untracked generated corpus, 840 files, 44M | Do not commit by default. Archive or move to runtime/output storage unless a corpus owner explicitly promotes it. | Research corpus owner | If retained, add a manifest, size justification, privacy review, and targeted validation. Otherwise leave ignored/archived outside the repo. |
| `apps/evaluator/nlm_deep_research/output/multimodal/` | Untracked audio artifact, 47M | Do not commit to repo. Move to artifact storage if it is needed. | NLM multimodal owner | Artifact storage location recorded; repo remains free of large generated media. |
| `outputs/` | Untracked local output, 51 files, 40M, including client CSV names | Treat as local-sensitive output. Do not commit. | Operator/data owner | Confirm whether files contain client data. Archive or delete locally only after owner approval. If recurrence is expected, add a separate ignore-policy PR. |
| `apps/crm-cell/war-room/interactive_cli.sh` | Untracked script | Review as a separate CRM tool change, not part of NLM/content batch. | CRM cell owner | Shellcheck or `bash -n`, owner review for data boundaries, and commit with CRM-specific tests/docs. |
| `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py` | Untracked scripts | Review with corpus ownership decision. | Research/NLM owner | Use project venv, type/import checks, no raw OSINT export to repo, and explicit output directory policy. |

## Recommended Commit Order

1. Preserve the dirty shared checkout before any branch switch:
   create a normal patch or local stash from `/Users/nuzantara/Desktop/nuzantara`
   without rewriting history or resetting.
2. Rebase or recreate the working branch from current `origin/main`; the shared
   checkout is behind by 161 commits.
3. NLM configuration rotation:
   `chore(nlm): rotate notebook ids`
4. NLM feeder profile change, only if validated:
   `fix(mata-garuda): use canonical nlm feeder profile`
5. Curiosity loop Python runtime fix:
   `fix(ops): pin curiosity loop to python 3.11`
6. Generated automation reference refresh:
   `docs(ops): refresh automations reference`
7. Content publishing batch:
   `feat(articles): publish june regulatory articles`
8. Durable research reports:
   `docs(research): add notebook health and regulatory deltas`
9. Explicitly archive or ignore generated media/corpus/output directories only
   after owner review. Do not sneak them into any commit above.

Do not mix executable behavior, generated docs, content, and large outputs into
one commit. Each category has a different owner and validation surface.

## Minimal Validation Commands

Run from an isolated worktree, not from an unrelated shared checkout cleanup:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -m compileall ../../apps/evaluator/nlm_deep_research
```

```bash
bash -n scripts/curiosity_loop.sh
bash -n apps/crm-cell/war-room/interactive_cli.sh
```

```bash
python -m json.tool apps/bali-intel-scraper/data/published_articles.json >/dev/null
python - <<'PY'
import json
from pathlib import Path
for path in Path("research/regulatory").glob("2026-06-*-delta.json"):
    json.loads(path.read_text())
print("OK")
PY
```

```bash
cd apps/mouth
npm run lint
npm run build
```

Only run external `nlm` calls in the owner session after confirming the intended
profile and NotebookLM account. Do not export raw WhatsApp, OSINT, or client data
to the repo.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean, reset, or stage the shared checkout from this isolated overnight
  branch.
- Do not commit `outputs/`, generated multimodal media, or corpus bulk without
  explicit owner review.
- Do not use `--no-verify`, force push, or bypass branch protections.

## Next Step

Assign the NLM/content/research owner to split the shared checkout by the file
plan above. If no owner has acted by 2026-06-14 12:00 WITA, preserve the dirty
state with a normal patch or stash, then remove or ignore only local generated
outputs after confirming they are not needed for publication or audit evidence.
