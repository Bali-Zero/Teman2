---
date: 2026-08-25
domain: operations
client_case: none
sources:
  - live `ssh pro` census, `nuzantara@Nuzantara`, repo `~/nuzantara` at commit `31a2547db36021a6e4f5e45d6bc439335382db8a` (== `origin/main`, verified `git rev-parse HEAD`, no local drift)
  - `python3 scripts/lint_home_fork.py --discover --json` (default, user-domain LaunchAgents only)
  - `python3 scripts/lint_home_fork.py --discover --system --json` (adds `/Library/LaunchAgents` + `/Library/LaunchDaemons`)
  - `infra/home-fork/declared-pairs.json` at commit `31a2547db3...`, 156 declared pairs. The sibling commit `8ee9f322b` on this same branch (already merged onto it, ahead of `31a2547db3...`) takes `pairs_declared` to 158 — verified by diffing the file at both commits. The 126 `discover_undeclared` count in this census is unaffected by that change, because the 2 newly-declared files were already structurally invisible to `--discover` (§2) before they were declared.
adversarial_review: codex
---

# HOME-fork undeclared-payload census — Pro, 2026-08-25

> **126 HOME-executed payloads are UNDECLARED against 156 that ARE declared** in
> `infra/home-fork/declared-pairs.json`, measured on Pro with `lint_home_fork.py --discover`. 123 of
> the 126 are visible with the tool's default (user-domain) scan alone — `--system` adds only 3.
> **126 counts findings — one per (path, consuming plist) pair, the tool's own literal unit — not
> distinct payload artifacts, and the two numbers are not directly comparable against the 156 declared
> PAIRS.** 25 of the 126 are a single interpreter binary (`~/.pyenv/versions/3.11.11/bin/python3`)
> flagged once per plist that names it directly, so ONE declaration for that one path closes 25 of the
> 126 findings at once (§4) — the true count of distinct payload paths behind 126 is measurably
> smaller, though this document does not compute that smaller number precisely (see Adversarial
> review). This document is the raw census: the number, how to reproduce it, the payloads grouped by
> organ, and two structural facts about the tool itself that anyone acting on this list needs before
> touching it. No priority ordering and no effort estimate are given — this is a measurement, not a
> plan.

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

**To re-measure whether the number has moved**: re-run the two commands above on Pro at a later date.
§4 below is grouped and brace-compressed for readability, not a one-to-one array of the raw
`discover_undeclared` output — an exact diff against a future run requires saving the raw `--json`
array at each measurement, which this census did not do (see Adversarial review). A shrinking count
usually means pairs got declared, and a growing one usually means a new payload started running
without ever being registered — but either can also follow from a plist/crontab edit, a removal, a
permissions change, or a change in the lint tool itself; a moved number is a prompt to check WHY, not
a self-explaining verdict.

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

**Consequence: there is more invisible fork-risk on top of the 126 already visible.** 126 is what
`--discover` can see today — and, per the headline note above, 126 counts findings, not distinct
artifacts, so it is not by itself a clean baseline to add more findings onto. What holds regardless of
that unit question: any organ below whose entry point is a wrapper script (shell, not a bare
interpreter+module invocation directly in ProgramArguments) may have its own internal `exec`/`import`
chain that this census — and the tool that produced it — cannot see AT ALL, whether or not it is
already among the 126. Whether any given organ in §4 has that shape was not checked here; checking it
means reading each wrapper, which is exactly the kind of work this document deliberately does not
scope or prioritize.

## 3. The `__init__.py` trap, generalized

Also found while closing the `wa-codex-broker` gap, and worth stating as a class because it will bite
whoever works through any part of §4 that involves a Python package tree deployed outside the repo
checkout (a `RUNTIME_DIR` under `/usr/local/lib/...`, a venv-adjacent copy under `~/scripts/...`, etc.):

**The real criterion is whether the live and repo bytes are EXPECTED to match — "created" vs "copied" is
a proxy for that, not the rule itself, and the proxy can be wrong at the edges** (a provisioning step
that deterministically generates byte-identical content, or an always-empty repo counterpart, would
pass even though it was "created" not "copied" — this document does not claim the created/copied
distinction holds in general). For the specific case that surfaced this, proxy and rule agree, verified
against the actual script: `scripts/provision_zantara_codex.sh` lays down four `__init__.py` files under
its runtime tree with a bare `touch`, guarded by `[ -f "$init" ] || { touch "$init"; ...; }` — `touch`
only ever fires on the absent-file branch, so it never overwrites existing content and always leaves
these four files empty — while the repo's own `__init__.py` counterparts carry real content (docstrings,
package-level imports — 3 to 56 lines each in the `wa-codex-broker` case, per `declared-pairs.json`'s own
note on this pair). Empty will never sha256-match non-empty. If you declare a `{live, repo}` pair for a
file like that, `lint_home_fork.py --check` will report `DIVERGED` on that pair for as long as the
provisioning script keeps producing empty files against a non-empty repo counterpart — the current,
verified state, with no planned change on either side. The way out is real, just not free: change the
provisioning script to copy or generate the real content, or — where an empty marker is genuinely
sufficient — change the repo counterpart to match what's generated; either fixes it going forward, but
neither un-diverges an already-declared pair retroactively without one of those two changes actually
landing first.

Before declaring any pair whose live side sits in a directory a provisioning/install script assembles
(rather than a plain `cp`/`rsync`/`install` of the exact repo file), read that script's install step
first. If it constructs content that does not — and structurally cannot be expected to — match the repo
file byte-for-byte, don't declare that pair yet; fix the mismatch (script or repo side) first, or leave
it undeclared with a note, rather than declaring a pair you already know will read as diverged forever.

## 4. The 126, grouped by organ

Grouping is mechanical (path/plist-name substring on the `--system` run's `discover_undeclared` array);
group sizes sum to exactly 126 by simple addition
(27+25+14+12+10+6+3+3+5+4+4+3+3+2+2+2+1 = 126, independently re-verified during adversarial review).
Ungrouped items too small or too varied to cluster meaningfully are listed under **misc / single-purpose**
rather than forced into a family they don't belong to.

**One claim this section originally made does not hold: the partition is not "no overlap and no drop".**
The plist `com.nuzantara.verify-the-verifiers` appears in both the **misc / single-purpose** row's plist
list and the **nuzantara-deploy governance** row's — paired there with the real path
`scripts/verify_the_verifiers.py`, which does not appear anywhere in the misc row's path list. A
LaunchAgent label is expected to be unique, so this is either a genuine double-count of one real finding
across two rows (the true total would be 125, not 126) or a transcription slip in one row's plist column
(126 would then stand, with a different, uncaptured plist actually belonging in the misc row). This
document cannot tell which from its own text, and the raw `discover_undeclared` JSON array that would
settle it was not saved at census time (see Adversarial review) — re-running
`--discover --system --json` on Pro and diffing the saved array against a fresh one is the only way to
resolve it. Treat 126, and the misc/governance row counts specifically, as carrying this one open,
unresolved discrepancy until that re-run happens.

Separately — not an error, a documentation-consistency gap worth naming so a future editor closes it:
the **observatory** and **automap** rows below explicitly flag that their own plists also carry a
bare-interpreter finding counted under the pyenv row (`+3 bare-interpreter rows above`). The identical
shape — one plist consuming both the shared pyenv interpreter and a `.py` script, each an independent
finding — plausibly also applies to `machine-boot-report`, `redis-liveness`, and `session-orphan-reaper`
in **monitors/watchdogs**, to `wa-mirror-auto-promote` and `wa-mirror-auto-promote-selfheal` in
**wa-mirror**, and to both plists in **cron-agent-python-adjacent** (all six also appear in the pyenv
row's plist list) — but those three rows carry no equivalent annotation. This does not change any of
those rows' own stated counts (each already reconciles against its own listed paths without needing the
pyenv-row overlap), so it is a missing courtesy note, not a new double-count.

One more per-row note, because a reviewer's specific claim that it was arithmetically impossible turned
out to be wrong, though the underlying ambiguity it pointed at is real: the **nuzantara-deploy
governance** row's 14 payload paths and 14 plists (2 `agent-library-evolver.{daily,weekly}` +
`intake-worker` (1) + the 9-item `com.nuzantara.{...}` group + `log-size-watchdog` (1) +
`intake-blob-retention` (1) = 14) reconcile exactly on a clean one-path-per-plist basis — nothing in
this row requires, or is disproved by, one path being consumed by two plists. Which of the two paths
outside that clean group (`scar-replay-run.sh`, `agent-library-evolver-run.sh`) pairs with which of the
two `agent-library-evolver` plists is not stated by this document — unlike the **restic-backup** row
below, which explicitly annotates its one-path-two-plists case — a cosmetic gap, not an arithmetic one,
since the row's total holds either way.

Also worth flagging precisely: the **monitors/watchdogs** row's path list uses `.{sh,py}` shorthand —
`~/scripts/{...10 basenames...}.{sh,py}` — to mean "one of these two extensions per basename" (10 files,
matching the row's own count), not the 20 a literal brace-expansion would produce. Which extension
applies to which basename is not preserved in this census; a reader who needs the exact 10 paths should
re-run `--discover` rather than guess from this shorthand.

A separate note below the table explains the **bare-interpreter** rows (25 of the 126): these are the
same external interpreter binary (`~/.pyenv/versions/3.11.11/bin/python3`) flagged once per plist that
names it directly as `Program` — not 25 different fork candidates, but 25 separate UNDECLARED findings
by the tool's own literal definition, because it never special-cases an interpreter binary from a
payload script.

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

## Adversarial review

**Method.** A fenced cross-family refuter (`codex`, model `gpt-5.6-sol`, effort `xhigh`, sandbox
`read-only`) was given ONLY this document's text as an extracted artifact — forbidden from exploring
the repository or running commands, told explicitly that "not checkable from this artifact" is a valid
finding — and instructed to attack five things: table arithmetic/completeness, whether "126 is a
floor" is established or asserted, reproducibility, the `__init__.py` generalisation, and material
omissions. Its full transcript is preserved in this branch's session record. Separately, the current
session (which DOES have repo access, unlike the fenced refuter) independently re-derived every
arithmetic claim from the document's own text and cross-checked two of the refuter's "not checkable"
claims against the actual repo. Findings below are ranked by severity; each carries a verdict and, where
the document was wrong, the specific correction applied above.

### CONFIRMED, and corrected in the document body

1. **[CRITICAL — found independently, not by the refuter] The partition is not "no overlap, no drop".**
   The plist `com.nuzantara.verify-the-verifiers` appears in both the misc/single-purpose row and the
   nuzantara-deploy governance row's plist lists — verified by brace-expanding every row's plist cell in
   Python and diffing for cross-row collisions, not by eyeballing. This directly contradicts §4's
   original claim. Corrected: the "no overlap and no drop" claim is removed and replaced with an
   explicit description of the anomaly, its two possible resolutions (true total 125, or a transcription
   slip elsewhere), and why this document cannot adjudicate between them (no raw JSON preserved — see
   finding 3 below). This is a materially stronger and more specific finding than anything the fenced
   refuter raised on this axis; its own "verified to partition... is not checkable from this artifact"
   was appropriately hedged, but it did not attempt the cross-row token diff that would have found the
   actual anomaly.

2. **[HIGH, refuter] The headline conflates "126 payloads" with "126 findings".** The refuter's argument
   (25 pyenv findings = 1 real path; the wa-mirror-enrichment-wrapper and restic-backup rows show the
   same multiply-counted-path shape at smaller scale; the refuter's own attempted recount of ~98
   distinct paths, though it flagged its own uncertainty on the monitors row) is sound in its core claim
   even though its exact alternate number is not something this document can independently confirm.
   Corrected: the headline blockquote now states explicitly that 126 counts (path, plist) findings, not
   distinct artifacts, and surfaces the pyenv 25-of-126 multiplicity at the TOP of the document instead
   of leaving it buried in §4 — this was also the team lead's specific instruction, checked
   independently: before this fix, a reader who read only the headline blockquote (not §4) would not
   have seen the caveat at all.

3. **[HIGH, refuter] No raw JSON snapshot was preserved.** True, and it is the reason finding 1 above
   cannot be fully resolved from this document. Not fixable retroactively (the live Pro state at census
   time is gone); the document now says so explicitly in three places (§1, §4, and here) instead of
   implying §4's grouped table is an adequate diff baseline.

4. **[HIGH, refuter] §4 cannot serve as an exact diff baseline for future re-runs.** Same root cause as
   3 (grouped/brace-compressed, not a 1:1 array; `crontab:N` line references also shift if earlier
   crontab lines are edited). §1's "to re-measure" paragraph is corrected to say this plainly.

5. **[HIGH, refuter] The shrinking/growing interpretation was presented as exhaustive.** Corrected — §1
   now says "usually" and lists the other causes (plist/crontab edit or removal, permission change, lint
   tool change) the refuter named.

6. **[MEDIUM, refuter] The `crontab:N` and `.{sh,py}` shorthands are ambiguous.** For the monitors row
   specifically, `.{sh,py}` literally brace-expands to 20 paths where the row claims 10 findings — the
   refuter caught this correctly. Corrected with an explicit footnote in §4 stating the shorthand means
   "one of the two extensions per basename, not preserved here" rather than leaving a reader to guess or
   assume literal brace-expansion.

7. **[HIGH, refuter] The `__init__.py` "created vs copied" rule is over-broad as a general principle,**
   and the "forever"/"never" language claims more than is defensible. Both corrected: §3 now states the
   real criterion (expected byte-equality; "created vs copied" is a proxy that can be wrong at the
   edges) and softens "forever"/"never" to describe the current, verified state rather than a
   logical impossibility, while naming the two real (if not free) ways out.

8. **[MEDIUM, refuter] The `156` vs `158` declared-pairs framing was ambiguous** about which count "does
   not change". Resolved with a repo check the fenced refuter could not perform (it had no repo access):
   `git show 31a2547db3...:infra/home-fork/declared-pairs.json` has 156 pairs;
   `git show 8ee9f322b:infra/home-fork/declared-pairs.json` (the sibling commit, already merged onto
   this branch) has 158. The frontmatter source line is corrected to state both numbers and which one
   (`discover_undeclared`, 126) is actually unaffected, and why.

### CONFIRMED but only partially actionable — noted, not fully correctable

9. **[LOW, refuter] "Empty namespace-package markers" is imprecise terminology** — a namespace package
   conventionally OMITS `__init__.py`; a present-but-empty `__init__.py` makes a regular package. Correct
   as far as it goes. Note: the identical phrase already exists, committed, in
   `infra/home-fork/declared-pairs.json`'s own note on this exact pair (out of scope for this PR — that
   file was not touched here). This document's own wording was rewritten in §3 to describe the mechanism
   without repeating the imprecise term, but the source note it was echoing was not corrected.

10. **[CRITICAL, refuter] "Blind spots do not make 126 a lower bound on fork risk"** — logically valid:
    false negatives (wrapper-internal execs) and the pyenv-style overcounting are separate propositions,
    and only the former supports "the true surface is larger". Addressed by the same headline/units fix
    as finding 2 plus a tightening of §2's own "Consequence" sentence to stop implying 126 is a clean
    baseline to add onto, while keeping the (still true, still unaddressed) point that wrapper-internal
    chains are invisible regardless of how the 126 is counted.

11. **[HIGH, refuter] "A census of what THIS host is actually configured to run" / "started running"
    conflates plist presence with loaded/active state.** Partially valid — §1's main phrasing ("configured
    to run") was already careful; the "started running" clause in the same section's closing sentence was
    not, and is now folded into the finding-5 correction above (soft-pedaling the shrink/grow claim also
    removes the loose "started running" phrasing). Not fully addressed: this document still does not
    report `launchctl` load state, and does not claim to — that remains true and is not a new gap this
    review is closing.

### REFUTED — the refuter's specific claim does not hold, checked against the document's own text or the repo

12. **[HIGH, refuter — REFUTED] "The governance row cannot reconcile with its stated count (14 vs
    15)."** The refuter's own math assumed `agent-library-evolver-run.sh` is necessarily consumed by
    BOTH `.daily` and `.weekly` plists. Nothing in the row requires that: independently brace-expanding
    both cells gives exactly 14 distinct paths and 14 distinct plists, which reconcile 1:1 with no
    double-counted path needed at all (`scar-replay-run.sh` and `agent-library-evolver-run.sh` cleanly
    match the two `agent-library-evolver` plists in some order). The refuter's claim that 14 is
    "impossible under the document's own counting rule" is wrong — a clean bijection exists. What IS
    real: the document does not state which of the two paths maps to which plist (unlike the
    restic-backup row, which explicitly annotates its one-path-two-plists case) — §4 now carries that
    narrower, correctly-scoped observation instead of the refuter's overstated one.

13. **[HIGH, refuter — REFUTED] "The claimed concrete proof [wa-codex-broker exec chain] is not present
    [in this artifact]."** True for the fenced refuter (it had no repo access, and correctly said so
    rather than asserting the underlying claim was false). This session DOES have repo access and
    checked it directly: `git log` shows commit `8ee9f322b` "fix(home-fork): declare the wa-codex-broker
    daemon's own payload tree" on this same branch, and `infra/home-fork/declared-pairs.json`'s note on
    that pair confirms, verbatim, exactly the shape §2 describes — the wrapper's `exec $VENV_PY -m
    backend.services.integrations.wa_codex_daemon` line lived inside the wrapper's shell body, invisible
    to `--discover`'s `Program`/`ProgramArguments` parsing, while the wrapper itself was already
    declared and read as "covered". §2's central inference is grounded, not merely asserted — verified,
    not refuted.

14. **[HIGH, refuter — REFUTED] "Bare `touch` does not overwrite the contents of an existing file"
    [therefore the document's claim about the four `__init__.py` files is suspect].** True as a general
    statement about `touch`, but checked against the actual script
    (`scripts/provision_zantara_codex.sh:137-139`): `[ -f "$init" ] || { touch "$init"; ...; }` — the
    `touch` only ever runs on the absent-file branch. It structurally cannot "not overwrite" content it
    never has the opportunity to touch. The document's specific claim (these four files are created
    empty and stay empty) is verified correct for this script; the refuter's general point about `touch`
    semantics does not undermine it. §3's correction keeps the practical claim and cites the exact guard
    that makes it hold.

### Considered, judged not to require a document change

15. **[MEDIUM, refuter] "The invisible-payload boundary is undefined" (imports are transitive, no
    stopping rule).** Correct in the abstract, but the document already explicitly disclaims this exact
    scope ("checking it means reading each wrapper, which is exactly the kind of work this document
    deliberately does not scope or prioritize") — extending that disclaimer to also name "no stopping
    rule for transitive imports" would be true but adds no new actionable information; not applied.

16. **[CRITICAL, refuter] "No eligibility test separates fork candidates from dependencies"
    (`.venv/bin/python`, `node_modules/.bin/next`, etc. are listed alongside real payload scripts).**
    Correct, and the same class of caveat as the `__init__.py` generalisation in §3 — but the document
    already states, in its own opening blockquote and in §2's closing sentence, that no per-item
    validation or triage was performed and that this is a measurement, not a plan. Adding a formal
    "eligibility test" would be scope creep into work the team lead's instructions explicitly withhold
    from this document (no priority, no effort estimate, no per-item validation).

17. **[MEDIUM, refuter] "The reproduction commands verify a commit but do not pin it" /
    `python3` is not version-pinned.** Technically true, low-impact: the exact commit SHA is given, which
    lets a reader `git checkout` it directly if strict reproduction is needed; not applied as a document
    change.

18. **[MEDIUM, refuter] "No validation status is recorded per finding" (existence, executability,
    enabled state).** Same disposition as 16 — correct, already outside this document's declared scope,
    not applied.

### Nothing found

19. The refuter's own audit of the headline family-count addition
    (27+25+14+12+10+6+3+3+5+4+4+3+3+2+2+2+1 = 126) confirmed it sums correctly; this session
    independently re-ran the same addition in Python and confirms it — CONFIRMED, no defect, no fix
    needed. The one genuine discrepancy in this table is the cross-row plist duplicate at finding 1, not
    the headline sum.
