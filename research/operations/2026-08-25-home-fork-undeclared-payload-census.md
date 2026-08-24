---
date: 2026-08-25
domain: operations
client_case: none
sources:
  - live `ssh pro` census, `nuzantara@Nuzantara`, repo `~/nuzantara` at commit `31a2547db36021a6e4f5e45d6bc439335382db8a` (== `origin/main`, verified `git rev-parse HEAD`, no local drift)
  - `python3 scripts/lint_home_fork.py --discover --json` (default, user-domain LaunchAgents only)
  - `python3 scripts/lint_home_fork.py --discover --system --json` (adds `/Library/LaunchAgents` + `/Library/LaunchDaemons`)
  - `infra/home-fork/declared-pairs.json` at the same commit, 156 declared pairs (before the 2 pairs added by the sibling commit on `agent/mini-pro2/ops/forkpair`, which do not change this count — see §2)
---

# HOME-fork undeclared-payload census — Pro, 2026-08-25

> **126 HOME-executed payloads are UNDECLARED against 156 that ARE declared** in
> `infra/home-fork/declared-pairs.json`, measured on Pro with `lint_home_fork.py --discover`. 123 of
> the 126 are visible with the tool's default (user-domain) scan alone — `--system` adds only 3. This
> document is the raw census: the number, how to reproduce it, the payloads grouped by organ, and two
> structural facts about the tool itself that anyone acting on this list needs before touching it. No
> priority ordering and no effort estimate are given — this is a measurement, not a plan.

## Why this exists

Found while closing a narrow, unrelated mandate: declaring the `wa-codex-broker` daemon's own payload
tree in `declared-pairs.json` (sibling commit on this same branch, `agent/mini-pro2/ops/forkpair`). That
daemon's wrapper and seat-probe were already declared — the pair list read as "this daemon is covered" —
while the two Python modules the daemon actually executes were not. Running `--discover --system` to
check for other instances of the same shape surfaced this count. It is unrelated to the mandate that
produced it and is reported here as its own artifact, per the team lead's instruction, so it survives
past this session's transcript.

## 1. The number, and how to reproduce it

Machine: **Pro** (`nuzantara@Nuzantara`), because the tool's `--discover` reads THIS machine's
`~/Library/LaunchAgents` (+ `/Library/LaunchAgents` and `/Library/LaunchDaemons` under `--system`) and
`crontab -l` — it is not a repo-content scan, it is a census of what THIS host is actually configured to
run. The same commands on Mini or M5 will read a different, disjoint set of plists/crontab and are
expected to produce a different number — this document makes no claim about those two machines.

```
cd ~/nuzantara   # repo root, not a worktree — see scripts/lint_home_fork.py's
                 # _canonical_repo_root() note on why a worktree run is deliberately
                 # redirected to the main checkout
git rev-parse HEAD
# 31a2547db36021a6e4f5e45d6bc439335382db8a

python3 scripts/lint_home_fork.py --discover --json
# "pairs_declared": 156, len(discover_undeclared) == 123

python3 scripts/lint_home_fork.py --discover --system --json
# "pairs_declared": 156, len(discover_undeclared) == 126
```

Both runs exit 2 (bit 2 = undeclared findings present, per the tool's exit contract). The `--system`-only
delta (3 findings) is exactly:

- `~/adguard-home/AdGuardHome/AdGuardHome` — `plist:com.nuzantara.adguardhome.plist`
- `~/Desktop/OSINT-Nexus/.venv/bin/python` — `plist:com.osint-nexus.h24.plist`
- `~/Desktop/OSINT-Nexus/scripts/nexus_h24_supervisor.py` — `plist:com.osint-nexus.h24.plist`

i.e. `com.nuzantara.adguardhome` and `com.osint-nexus.h24` are the only two of these findings whose
plist lives in the system LaunchAgent/LaunchDaemon domain rather than `~/Library/LaunchAgents`.

**To re-measure whether the number has moved**: re-run the two commands above on Pro at a later date and
diff the `discover_undeclared` arrays against §4 below (or against a fresh save of this census). A
shrinking list means pairs got declared; a growing one means a new payload started running without ever
being registered.

## 2. This count is a floor, not the size of the gap

`--discover` can only flag a HOME-rooted path that appears as `Program`/`ProgramArguments` in a plist, or
as a bare token in a crontab line (`scripts/lint_home_fork.py`'s `discover_undeclared`, reading
Program/ProgramArguments + `crontab -l` text). It has **no visibility into what a shell wrapper does
after it starts** — an `exec` line, a `python -m package.module` invocation, or any payload one level
below the thing the plist directly names is structurally invisible to it, by construction, not by an
oversight that a future `--discover` run could fix.

This is exactly the shape the sibling commit on this branch closed for `wa-codex-broker`: the plist names
only `/usr/local/libexec/wa-codex-broker-wrapper.sh` (declared, and correctly reported clean), while the
wrapper's own `exec $VENV_PY -m backend.services.integrations.wa_codex_daemon` line — the thing that
actually runs the daemon's code, and the only place a behaviour-changing edit could land — was invisible
to `--discover` and undeclared for an unknown period before this session. The existing
`cron-agent-python/agent_job.py` entry in `declared-pairs.json` documents the identical shape for a
different organ ("an imported module is never an entry point").

**Consequence: the true fork-risk surface is larger than 126.** 126 is what `--discover` can see today.
Any organ below whose entry point is a wrapper script (shell, not a bare interpreter+module invocation
directly in ProgramArguments) may have its own internal `exec`/`import` chain that this census — and the
tool that produced it — cannot see at all. Whether any given organ in §4 has that shape was not checked
here; checking it means reading each wrapper, which is exactly the kind of work this document
deliberately does not scope or prioritize.

## 3. The `__init__.py` trap, generalized

Also found while closing the `wa-codex-broker` gap, and worth stating as a class because it will bite
whoever works through any part of §4 that involves a Python package tree deployed outside the repo
checkout (a `RUNTIME_DIR` under `/usr/local/lib/...`, a venv-adjacent copy under `~/scripts/...`, etc.):

**A file that a provisioning script *creates* is not the same thing as a file it *copies*, and only the
second kind can be declared as a pair.** `scripts/provision_zantara_codex.sh` lays down four
`__init__.py` files under its runtime tree with a bare `touch` (empty namespace-package markers) while
the repo's own `__init__.py` counterparts carry real content (docstrings, package-level imports — 3 to 56
lines each in the `wa-codex-broker` case). If you declare a `{live, repo}` pair for a file like that,
`lint_home_fork.py --check` will report `DIVERGED` on that pair **forever** — not because anything drifted,
but because the two sides were never meant to match sha256-for-sha256 in the first place. There is no
`--check` run, present or future, that would pass; the fix is never "realign the live copy" or "update the
repo", because doing either doesn't change what the provisioning script writes next time it runs.

Before declaring any pair whose live side sits in a directory a provisioning/install script assembles
(rather than a plain `cp`/`rsync`/`install` of the exact repo file), read that script's install step
first. If it constructs the file's content instead of copying it byte-for-byte, that file cannot be a
`{live, repo}` pair under this tool's model — full stop, not "declare it and see".

## 4. The 126, grouped by organ

Grouping is mechanical (path/plist-name substring on the `--system` run's `discover_undeclared` array,
verified to partition all 126 entries with no overlap and no drop — group sizes sum to exactly 126).
Ungrouped items too small or too varied to cluster meaningfully are listed under **misc / single-purpose**
rather than forced into a family they don't belong to. A separate note below the table explains the
**bare-interpreter** rows (25 of the 126): these are the same external interpreter binary
(`~/.pyenv/versions/3.11.11/bin/python3`) flagged once per plist that names it directly as `Program` — not
25 different fork candidates, but 25 separate UNDECLARED findings by the tool's own literal definition,
because it never special-cases an interpreter binary from a payload script.

| Organ | Findings | Payload paths (deduped) | Plists / crontab lines |
|---|---|---|---|
| **misc / single-purpose** | 27 | `~/.claude/scripts/{archive-empty-sessions,mos-maintenance,sync-memory-ruslana,sync-memory-to-nlm,zombie-hunter}.sh`, `~/.claude/venvs/mos-plus/bin/python`, `~/.nuzantara-cron/modus_autoloop_cron.sh`, `~/Desktop/nuzantara-deploy/scripts/{auto_kb_ingest,cron-wrapper}.sh`, `~/adguard-home/AdGuardHome/AdGuardHome`, `~/nuzantara-deploy/apps/backend-rag/.venv/bin/python`, `~/scripts/bz-daily-visual-pipeline.sh`, `~/scripts/cicatrix-rotation.py`, `~/scripts/claude-max-usage-watcher.sh`, `~/scripts/crm-guardian-cli-worker.sh`, `~/scripts/domain-mesh-foundations-cron.sh`, `~/scripts/fly-cost-alert.sh`, `~/scripts/fly_logs_accumulator.sh`, `~/scripts/generate-automations-all.sh`, `~/scripts/mos-plus-qdrant-indexer.py`, `~/scripts/nb-intel-delta-watcher.sh`, `~/scripts/nuzantara-drive-sync.sh`, `~/scripts/ollama-single-manager.sh`, `~/scripts/organism-supervisor-wrapper.sh`, `~/scripts/qdrant-daemon-wrapper.sh`, `~/venvs/nlm-bridge/bin/uvicorn` | `com.nuzantara.archive-empty-sessions.daily`, `crontab:34/35/70/71/176`(×2), `com.nuzantara.zombie-hunter`, `com.balizero.mos-plus.qdrant-indexer`, `com.balizero.modus.autoloop.nightly`, `com.nuzantara.adguardhome`, `com.nuzantara.verify-the-verifiers`, `com.balizero.bz-daily-visual-pipeline`, `com.balizero.cicatrix-rotation.monthly`, `com.nuzantara.claude-max-usage-watcher`, `com.balizero.crm-guardian-cli-worker`, `com.balizero.domain-mesh.foundations.daily`, `com.balizero.fly-cost-alert.weekly`, `com.nuzantara.fly-logs-accumulator`, `com.nuzantara.automations-reference`, `com.nuzantara.nb-intel-delta-watcher.hourly`, `com.balizero.nuzantara-drive-sync`, `com.nuzantara.ollama`, `com.nuzantara.organism.supervisor`, `com.balizero.qdrant.daemon`, `com.balizero.nlm-bridge` |
| **`~/.pyenv` bare interpreter** (see note) | 25 | `~/.pyenv/versions/3.11.11/bin/python3` (single path, flagged once per consuming plist) | `crontab:18`, `com.balizero.{competitor-signal-router.weekly,cron-log-sentinel,intel-dedup-gateway,intel-lake.outbox-drain.minute,intel-radar-daily-digest,meta-dispatcher,mos-plus.compression,observatory-export,observatory-server,observatory,research-sentinel,wa-mirror-auto-promote-selfheal,wa-mirror-auto-promote}`, `com.nuzantara.{automap-server,automap-telegram,automap-watchdog,launchagent-state-bridge,machine-boot-report,organism.scheduled-tick,redis-liveness,sentinel-aggregate,sentinel,session-orphan-reaper,vector-reindex-check}` |
| **nuzantara-deploy governance** (cost-breaker, merge-train, review-gate, verify-*, agent-library-evolver, intake) | 14 | `~/nuzantara-deploy/{agent-library/scar_replay/scar-replay-run.sh, apps/backend-rag/backend/services/intake/intake-worker-run.sh, scripts/{agent-library-evolver-run,cost_breaker_deadman,cost_breaker_run,lead_intent_matcher_run,log_size_watchdog,merge_train_run,review_gate_run,verify_connectome_run,verify_mcp_integrity,web_lead_funnel_report_run}.sh, scripts/verify_the_verifiers.py}`, `~/scripts/intake-blob-retention-run.sh` | `com.balizero.agent-library-evolver.{daily,weekly}`, `com.nuzantara.intake-worker`, `com.nuzantara.{cost-breaker-deadman,cost-breaker,lead-intent-matcher,merge-train,review-gate,verify-connectome,mcp-integrity,verify-the-verifiers,web-lead-funnel}`, `com.balizero.nuzantara.log-size-watchdog`, `com.nuzantara.intake-blob-retention` |
| **openclaw** (bridge/tunnel, wr3 sub-binaries, `openclaw-cron/*`) | 12 | `~/.openclaw/bin/{run_openclaw_whatsapp_bridge,run_openclaw_whatsapp_tunnel}.sh`, `~/.openclaw/bin/wr3/{wr3-editorial-bench-run,wr3-supervisor-wrapper}.sh`, `~/scripts/openclaw-children-watchdog.sh`, `~/scripts/openclaw-cron/{client-value-predictor,conversation-trainer,knowledge-graph-builder,renewal-alerts,seo-cell-28d-check,seo-cell-daily}.sh`, `~/scripts/openclaw-state-bridge.py` | `com.nuzantara.openclaw-{whatsapp-bridge,whatsapp-tunnel,children-watchdog}`, `com.balizero.wr3.{editorial-bench.monthly,supervisor}`, `com.balizero.{client-value-predictor,renewal-alerts,seo-cell.28d-check,seo-cell.daily}`, `crontab:16/17/18` |
| **monitors/watchdogs (standalone)** | 10 | `~/scripts/{audit_trail_cleanup,cert-monitor,cpu-monitor,disk-monitor,gh-auth-healthcheck,intel-scraper-sentinel-bridge,machine_boot_report,redis_liveness_check,session_orphan_reaper,worktree-cleanup}.{sh,py}` | `crontab:13/72/212/274`, `com.nuzantara.{cpu-monitor,disk-monitor,gh-auth-healthcheck.weekly,machine-boot-report,redis-liveness,session-orphan-reaper}` |
| **wa-mirror** (attention pipeline + auto-promote) | 6 | `~/scripts/wa-mirror-{auto-promote-leads,auto-promote-selfheal,strategic-recap-updater}.py`, `~/scripts/wa-mirror-enrichment-wrapper.sh` (×3 plists) | `com.balizero.wa-mirror-{auto-promote,auto-promote-selfheal,strategic-recap}`, `com.balizero.wa-mirror-attention-{classifier,digest,realtime}` |
| **observatory** (`~/agents/.observatory/`) | 3 | `~/agents/.observatory/{observatory,observatory_export,serve}.py` | `com.balizero.observatory{,-export,-server}` (+3 bare-interpreter rows above) |
| **automap** | 3 | `~/scripts/automap/automap_{server,telegram,watchdog}.py` | `com.nuzantara.automap-{server,telegram,watchdog}` (+3 bare-interpreter rows above) |
| **osint-nexus** | 5 | `~/Desktop/OSINT-Nexus/{.venv/bin/python, scripts/nexus_h24_supervisor.py, scripts/nexus_session_retention.sh, ui-v2/node_modules/.bin/next}`, `~/scripts/osint-nexus-synapse-monitor-run.sh` | `com.osint-nexus.{h24,ui,synapse-monitor}`, `com.balizero.nexus-session-retention.daily` |
| **intel-lake** | 4 | `~/scripts/intel-lake-{nb-pusher,probe,router}-cron.sh`, `~/scripts/intel-lake-shadow-validate.sh` | `com.balizero.intel-lake{-nb-pusher.15min,.e2e-probe.6h,-router.5min,.shadow-validate.6h}` |
| **codex nightly automations** | 4 | `~/scripts/codex/{daily-research-actor,nightly-coverage-improver,openclaw-analysis,spalla-calibrate}.sh` | `com.nuzantara.codex-{research-actor,coverage-improver,openclaw-analysis}`, `com.balizero.codex-spalla-calibrate` |
| **mini-setup sync scripts** | 3 | `~/scripts/mini-setup/{claude-config-sync,memory-sync-bidirectional,secrets-sync-cron}.sh` | `com.nuzantara.{claude-config-sync,memory-sync-bidirectional,secrets-sync-mini}` |
| **wr2/wr3 (outside openclaw bin)** | 3 | `~/nuzantara-deploy/scripts/wr2_plist_watchdog.sh`, `~/scripts/wr2-{pg-queue-sync,probe-cron}.sh` | `com.balizero.wr2.{plist-watchdog,pg-queue-sync,e2e-probe.daily}` |
| **mata-garuda** | 2 | `~/scripts/mata-garuda-watcher.sh`, `~/scripts/mata_garuda/mata_garuda_invalidation_sweep_wrapper.sh` | `com.matagaruda.{watcher.daily,invalidation-sweep}` |
| **restic-backup** | 2 | `~/scripts/restic-backup-pro.sh` (one script, two consuming plists) | `com.nuzantara.restic-{backup-pro,prune-pro}` |
| **cron-agent-python-adjacent** (`scripts/eventbus/`, same shape as the already-declared `cron-agent-python/` tree, different directory, never promoted) | 2 | `~/scripts/eventbus/{competitor_signal_router,cron_log_sentinel}.py` | `com.balizero.{competitor-signal-router.weekly,cron-log-sentinel}` |
| **flowkit** | 1 | `~/flowkit/venv/bin/python` | `ai.flowkit.gateway` |

Total: 27+25+14+12+10+6+3+3+5+4+4+3+3+2+2+2+1 = **126**.
