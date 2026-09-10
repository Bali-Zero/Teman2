# S3 — ARM THE AUDITORS

**One line:** proprioception has no schedule, the daily cost guard sits in canon unloaded, and the scar census feeds a runner that no workflow calls, while CI reads a different registry.

**Wave 2 · Pro · runs in parallel with S4.** Writes no plist until PR #6101 (one tree on Pro) has merged or closed. Built from C5, plus C6 (payload redirected to `verify_the_verifiers_gates.yaml`) and one probe from C7. Operator items: 3. Cap: 5 PRs.

## Mandate prompt — paste everything below this line into a fresh `claude` session

SEAT AND CONTRACT
You are a Fable 5.1 session that Zero chose manually, running at max effort on Pro (`nuzantara@Nuzantara`, repo `~/nuzantara`). You own this mandate end to end: review → merge → arm → deploy → prove-live. The codeowner does not merge, review or deploy. Pin every subagent's model in the Agent call: `sonnet` for readers and implementers, `haiku` for grunt work, `opus` only for a final on-disk gate. An unpinned subagent inherits your model. Builder Contract: every PR gets its own worktree from `scripts/agent_start.py`, cut from a fresh origin/main. One PR, one concern, ≤~400 net lines. Every PR body carries a `Bites:` line naming the consumer and the observation that proves the change is live. Arm auto-merge when you open the PR; from then on the branch is frozen. Push, create and merge are three separate commands. Never rerun a red check until you know why it is red. Three reds for the same cause → suspend and write the spec. A fix-of-a-fix stops at depth 1. Reaching a Claude model through a paid per-token Anthropic endpoint is banned as an entity: use the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` only, and refuse any tool, MCP server or cron that needs `ANTHROPIC_API_KEY`, `from anthropic import Anthropic`, a renamed variable, a wrapper or a Bedrock/Vertex route. PII is an output boundary: no PR body, log, alert, memory, ledger row or report carries client PII or OSINT in cleartext. Off-limits files: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Never edit Zero's own files: `~/.claude/CLAUDE.md`, branch protection, required-context lists. File operator items as a PENDING-ARMS row with the exact ask, and never wait on them.

MISSION
Put the organism's auditor on a schedule, load the cost guard, and add the last ten weeks of scars to the registry CI actually reads. Then add ONE advisory probe that re-derives a countable claim, and produce the decommission manifest for frozen organs. Five PRs at most.

GROUND (judge 13:04–13:06Z, red-team about an hour later, re-checked by the board editor at ~13:35Z; re-derive everything, because counts moved during the audit day: repo_divergent went 4→11 and live LaunchAgents went 71→76)
- `ls ~/Library/LaunchAgents | grep -ci propriocep` → 0; `crontab -l | grep -ci propriocep` → 0. The auditor behind the P1 findings in three reports runs only when someone types its name.
- `launchctl list | grep -c cost-advisor-daily-cap` → 0. Canon has TWO copies of its plist, `infra/launchagents/com.nuzantara.cost-advisor-daily-cap.plist` and `apps/backend-rag/deploy/launchd/com.nuzantara.cost-advisor-daily-cap.plist`. Decide which one is canon before you load anything.
- `infra/scar-gates/MANIFEST.json` → generated 2026-06-27, total 66, armed 2, prose_only_debt 64. Its highest entry is W87, while the corpus reaches W131 (`grep -ohE 'W[0-9]+' docs/scars/cicatrix-scars.md docs/scars/cicatrix-scars-archive.md | sed 's/W//' | sort -n | tail -1`).
- THE CORRECTION THAT SHAPES THIS SESSION: `grep -rln run_scar_gates .github/workflows/ | wc -l` → 0, and the same grep over `~/Library/LaunchAgents/` → 0, while `grep -c scar_test scripts/verify_the_verifiers_gates.yaml` → 11. The only consumer of MANIFEST.json is orphaned; CI reads `verify_the_verifiers_gates.yaml`. Don't spend the session regenerating MANIFEST.json.
- INDEX.md:71 lists fifteen "core tables". Six of them (articles, crm_clients, crm_practices, messages, routing_stats, failed_queries) return exists=false against prod (`./scripts/pg.sh` with a query on `information_schema.tables`).
- PR #6101 (at 13:35Z: open, DIRTY, armed, 35 files) repoints 18 LaunchAgents from `/Users/nuzantara/nuzantara-deploy` to `/Users/nuzantara/nuzantara`. Its body records the healer's home-fork refresh copying repo canon over a live plist edit within six minutes. The canon is the change; the installers and the healer are what put it into effect.
- PR #6054 (open) modifies `scripts/proprioception.py` (child calibration receptor).
- `python3 scripts/lint_plist_keepalive.py` → exit 4 (PARTIAL), from two ExpatError plists: `infra/launchagents/_snapshot-live/com.nuzantara.daily-gsc-indexing-sweep.plist` and `.../com.nuzantara.intake-proposal-health-sentinel.plist`. Neither organ is loaded any more; their live copies sit under `.removed-20260611/` and `.disabled-codex-cleanup-20260708/`. `com.nuzantara.plist-snapshot.daily` (loaded) copies every LOADED live plist over `_snapshot-live/`, one way.

DISEASE
Superscar #2, three organs deep. Building the sensor gets treated as the deliverable and wiring it as someone else's job. So the census never runs, the cost guard never loads, and the scar registry's generator feeds a script nothing calls. Every countable claim in the doors is hand-written for the same reason.

SCOPE IN (five PRs, in this order; loading the cost guard is an ops step, not a PR)
1. PR: schedule proprioception with a canon plist under `infra/launchagents/` whose ProgramArguments name `/Users/nuzantara/nuzantara/scripts/proprioception.py` (the #6101 rule). Load it and kickstart it once, so a run started by launchd lands in its log today.
2. Ops step: load the cost guard from whichever copy is canon, after checking that its exec path names the main checkout, and force one run into its log today. If the canon itself needs a fix, that fix takes item 3's PR slot and the linter fix moves to the grunt lane.
3. PR: make the plist linter exit 0. First run `launchctl list | grep -i <label>` for each broken plist. These organs are dead, so retire their snapshot copies (or fix the XML). The rule for every future case: if a `_snapshot-live` plist IS loaded, the fix goes into the live canon or its declared pair, never only into the snapshot, or tomorrow's snapshot reverts it.
4. PR: executable scar gates in `scripts/verify_the_verifiers_gates.yaml` (NOT MANIFEST.json) for recurring scar chains that grep shows have no coverage. At least two, each proven to FAIL when its disease is synthetically re-introduced and to pass once it is removed. Advisory only; no promotion.
5. PR: ONE advisory re-derivation probe. `scripts/check_autonomous_ops_staleness.py` already proves the pattern for one file; generalize it into a probe that re-derives a countable claim and reports red on drift. Exactly one consumer: INDEX.md's core-table list, diffed against `information_schema.tables`. It reports; it doesn't block. Correct INDEX.md in the same PR, as the proof that the probe bites.
6. PR: the decommission manifest for frozen organs, meaning the mechanism plus per-organ evidence, generated by a script. Evidence per organ is limited to organ id/label, heartbeat age and log error CLASS (e.g. `ModuleNotFoundError`, `Operation not permitted`). Never log lines, payloads, message bodies or identifiers. Include `com.balizero.intel.nightly` (a ~4-month zombie whose copy step fails with Operation not permitted).

SCOPE OUT
- Regenerating MANIFEST.json, building a census generator, and regenerating `scripts/automation_catalog.json`: all cut to the grunt lane.
- Root-causing individual frozen organs, retiring any organ, promoting anything to REQUIRED.
- The legacy conversation tables. Conversation data has a five-year never-delete retention (Zero, 2026-08-08), so the manifest may mark a writer as dead but never proposes dropping a conversation table.
- The 95 zero-row prod tables (Zero's triage), the daemon count in `~/.claude/CLAUDE.md` (report the derivation only), and arsenal seat re-authentication.
- `queue_shepherd.py` (S1); PENDING-ARMS structure, the escalation bus and `tg_notify.py` (S4); memory.db (S5). Also the internals of `scripts/proprioception.py` while #6054 is open.

OPERATOR BOUNDARY
Three items, filed, none blocking: sign-off on organ retirement in the manifest; promotion of the new gates to REQUIRED; the daemon-count correction in Zero's global door.

METHOD
First hour:
1. Run `python3 scripts/agent_start.py --help`, then create one worktree per PR, e.g. `--lane ops --task-id auditors-proprioception-plist` (branch `agent/nuzantara/ops/...`).
2. Run `gh pr view 6101 --json state,mergeStateStatus`. If it's still open, ship items 4, 5 and 6 first and write no plist until it lands; then align every plist with the canon it established.
3. Re-run every GROUND command, plus `python3 scripts/launchagent_reconcile.py --json`, `python3 scripts/launchd_liveness_detector.py --json`, `python3 scripts/organism_stale_detector.py --dir ~/.organism/last_seen` and `python3 scripts/lint_plist_keepalive.py`. If a flag errors, run `--help` rather than guessing. Write down YOUR numbers.
4. Run `gh pr list --state open --search 'scar-gates OR proprioception OR launchagent'` and coordinate with every hit rather than racing it.
Land the gates advisory-only and watch a full day of runs before you propose promotion.

BITES (each with its proving command)
- Bite 1. Consumer: launchd. `launchctl list | grep -i propriocep` shows the loaded label, proprioception's own report shows a run from today started by launchd, and `launchctl print gui/501/<label> | grep -A3 'arguments = {'` names the main checkout.
- Bite 2. Consumer: the cost guard. `launchctl list | grep -c cost-advisor-daily-cap` → 1, and a forced run appears in its log today.
- Bite 3. Consumer: the linter. `python3 scripts/lint_plist_keepalive.py; echo $?` → 0 instead of 4.
- Bite 4. Consumer: CI. `python3 scripts/verify_the_verifiers.py --json --no-signal --scope repo` shows the armed gate count up by the number you added; paste two re-injections failing and then passing.
- Bite 5. Consumer: INDEX.md's readers. The probe names the six missing tables, corrupting one derived number turns it red, and INDEX.md is corrected.
- Bite 6. Consumer: the manifest. Running its generator twice leaves `git diff` empty, and every entry carries only the allowed fields.
- Bite 7. Consumer: canon. `python3 scripts/launchagent_reconcile.py --json` shows no new divergence from your plists.

RISK CONTROLS
Re-baseline every count within the session. Never `launchctl unload` anything you didn't just load yourself. Never blind-rerun a red check. No client PII or OSINT in any manifest, report or ledger row: organ ids only. Plist exec paths name the main checkout, never a `.worktrees/` path (worktrees are torn down after merge) and never `nuzantara-deploy`. S2 may add a LaunchAgent in the same window, so never edit crontab; one plist file per job. PENDING-ARMS appends: use a branch cut from a fresh origin/main, check for a +N/-0 diff, and never hand-resolve or rebase onto it.

STOP CONDITIONS
Stop and file a row if a gate would touch a REQUIRED context, if retiring an organ starts to look like a business decision (it is one), if you get three reds for the same cause, or if another session has an open PR on `scripts/proprioception.py` or a broad `infra/launchagents/**` repoint that your change would contradict.
