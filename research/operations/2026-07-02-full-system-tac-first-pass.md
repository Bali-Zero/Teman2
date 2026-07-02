# Full-System TAC — First Pass (deep analysis of the entire organism)

---
date: 2026-07-02
domain: operations
mandate: "prima analisi profonda del nostro intero sistema → elenco ulteriori analisi" (Zero)
gear: 3 (modus PROFONDO — TAC by anatomy)
method: 9 read-only Sonnet organ-readers (apps, backend, M5-automation, Pro, Mini, Fly/public, CI/git, security, knowledge) + ~30 direct Fable probes (prod DB via readonly MCP, live health endpoints, real RAG query, ssh Pro/Mini, ledgers) + generator≠grader verification of every load-bearing claim
sources: live probes this session; no state mutated (diagnostic-only; only artifacts written: this report, memory, PENDING-ARMS bookkeeping)
---

## 0 · Scorecard (organ → status)

| Organ | Status | One line |
|---|---|---|
| Prod Fly (nuzantara-rag + postgres) | **GREEN** | v3689 deployed today, 4 machines started, PG HA 3/3, zero 5xx in log window |
| Public surface (10 domains) | **GREEN** | all respond with expected codes; latency 2–8 s single-sample (needs baseline) |
| Prod data layer (303 tables, 2.4 GB) | **GREEN\*** | readonly role live, olympus heartbeat health=100, outbox 1,488 ev/24h — \*but client-message ingest silent since 06-30 (P1 below) |
| Backend-rag codebase | **YELLOW** | architecture solid (3-process split, ban enforced, embedding frozen); docs lie 2–2.6×; dual abstain-threshold still open; 2,200-line router god-files |
| Apps constellation (36) | **YELLOW** | 6 truly active; 4 empty Vercel shells; 1 dead (kb); 1 app invisible to git; undeclared wa-dashboard migration |
| Automation M5 (10 launchd jobs) | **YELLOW** | live W84 TCC recurrence (heartbeat side-channel); 1 diverged HOME-fork carrying an unported incident fix; repomap + branch-cleanup crons absent/impossible on M5 |
| Fleet Pro | **YELLOW-RED** | redis NOAUTH kills heartbeat writes every 30 s (5,470+ errors, live); 2 crons armed at a reaped worktree (exit 127 ×10 days); main checkout 51 behind + dirty (active work) |
| Fleet Mini | **GREEN** | clean tree, same-day HEAD, services listening, no active TCC issue; pulls Pro-first by design |
| CI / PR / branches | **YELLOW** | 14/14 recent runs green, 18 required checks armed, force-push off; 31-run queue backlog; 27 open PRs (auto-merge armed on today's wave); 85 remote branches with tail to March |
| Security hygiene | **GREEN** | 0600 discipline on live secrets, zero tracked secrets, Anthropic-ban enforced (0 hits), ssh clean; minor: inline token in 0600 plist |
| Knowledge / intel | **YELLOW** | KB + runbooks solid, NLM integration broad; regulatory ALERT path alive (ran today) but ARCHIVE path broken 14 d; repo not self-bootstrapping (skills/agents live user-level only) |

## 1 · Findings by severity (each verified this session)

### P1 — live disease, actively corrupting
1. **Redis NOAUTH on Pro corrupts the organism's self-monitoring in real time.** `requirepass` is set (2026-06-29 hardening) but ≥3 daemons (meta-dispatcher, research-sentinel, intel-dedup-gateway) connect without the password → `AuthenticationError` on every 30 s heartbeat. Verified firsthand: 5,470 occurrences in the *current* meta-dispatcher.log alone; the daemon restarted at 17:17 during the probe (bouncing). Live organ detector run: **2 not-breathing / 5 breathing-but-failed** (incl. `pro.federation_alert_dispatcher` stale 22.6 d with `status=ok` — the green that lies). This is the memory-recorded "requirepass 29/6 senza sweep" scar, still uncured. *(family #2 + #9)*
2. **Client-message ingest silent since 2026-06-30.** 0 rows/24 h in `conversation_messages` + `meta_inbox_messages` + 0 active WA conversations, while every autonomic table keeps writing (funnel_sessions, crm_guardian, wa_lid_phone_resolution analyzed 08:57 today). Either a dead Meta webhook or these aren't the live ingest tables — for an agency, 48 h of zero inbound is a lost-lead-grade signal either way. **Needs its own audit (top of the further-analyses list).**
3. **Regulatory-watcher: alert path ALIVE, archive path DEAD 14 days.** Verified on Pro: ran today 07:04 WITA, produced `2026-07-02-delta.json` (2,702 B), Telegram sent (message_id 77403), delta = PMK 37/2025. But the repo's `research/regulatory/` stops at 06-18 — deltas strand on Pro, never promoted/committed. The plist lives only in Pro's `~/Library/LaunchAgents/` (not in repo `infra/launchagents/`). *(family #1: armed-live, invisible-to-SSOT; promotion gap recurring per the 06-15/06-17 "promote orphaned delta" PRs)*
4. **Prod `/health/detailed` lies-critical.** Reports search/ai/router "unavailable-critical" while a real KBLI search returns correct scored results and `/health` says healthy ("RAG handled by rag process group"). The endpoint introspects the *api* process registry and speaks for the whole app. Any monitor/agent consuming it inherits a false P0. *(family #2, inverted sign)*
5. **W84 TCC recurrence LIVE on M5.** `agent-worktree-cleanup.daily` stdout works but stderr shows `heartbeat.sh: Operation not permitted` — the 2026-06-16 cure moved the *wrapper* out of `~/Desktop` while the payload still sources from `~/Desktop/nuzantara` → heartbeat side-channel dead today. TCC re-grant needed (operator). Mini: no active TCC issue (stale hits only).

### P2 — structural defects, will bite
6. **Pro: 2 launchd agents point at a reaped worktree** (`ops-autonomous-runner`) → exit 127 every cycle for 10 days (`com.balizero.autonomous-lab{,-runner}`). Third 127 (`intake-proposal-health-sentinel`) has a real path — separate cause, undiagnosed. *(#1×#5)*
7. **`.gitignore:474` bare `main.py` pattern hides source from git.** Two files currently invisible: `apps/remediator/main.py` (the ENTIRE app — a real asyncio/redis/sqlite self-repair daemon) and `apps/graph-engine/src/nuzantara_graph/main.py` (entry point of a tracked app). The two `!` exceptions right below prove it already bit twice and was patched per-file. Fix: anchor to `/main.py`, add the 2 files, drop exceptions.
8. **HOME-fork divergence carrying an unported incident fix.** `~/.fly/bin/fly_pg_tunnel_supervisor.sh` (live, M5) contains a FLY_ACCESS_TOKEN hoist (inline scar-comment 2026-06-25, cured a 1,401-run KeepAlive storm) — repo copy has **zero** references. 8 days at risk of silent loss on next repo-side deploy. Also: 2 cron scripts with no repo counterpart at all (`mlx-server-run.sh`, `bz-nlm-autodownload.sh`); dead symlink `apps/war-room/APPLICA_WAR_ROOM.md` → `/Users/nuzantara/...`; stray `apps/ingestion_tier1_gaps.log` with Pro-path evidence.
9. **Cron parity broken by construction on M5.** `com.nuzantara.branch-cleanup.weekly` plist hardcodes `/Users/nuzantara/logs/...` (Pro-only) → cannot run on M5; repomap cron absent entirely on M5 (no plist, no `~/.nuzantara-repomap.txt`) while CLAUDE.md documents both as active. M5 also lacks the documented stop_verify / dispatch_nudge / organism_alert / memory-load hooks (checked user+local+project settings) — the safety net documented in CLAUDE.md §7 is partially Pro-only, one month after M5 became the primary machine.
10. **Docs lie next to machine-verified truth (W86 class).** `docs/AI_ONBOARDING.md`: DOCSYNC block is fresh (329/635/1104 verified) but the prose 100 lines below says 88 routers (actual 158 files), 244 services (actual 635), 385 tests (actual 1104), 7 channels (actual 4 live) — ungated. "12 Qdrant collections" inside the green block = *live* count vs **20 defined** in `collection_manager.py` (8 defined-but-not-live to reconcile). Root CLAUDE.md is a docs_sync target with zero markers (dead target). CLAUDE.md also points sessions at `shared/escalations.json`; reality is `escalations_pro.jsonl`.
11. **Observability instruments answering the wrong question.** `get_collection_stats` (MCP advanced) returns op-counters instead of the promised collection inventory; 2 M5 launchd jobs have decoy log paths (declared out/err empty; real log elsewhere); Mini's `homebrew.mxcl.redis` shows launchctl exit 1 while Redis listens fine (stale red). Escalations receptor is silent both when healthy-empty and when broken (no self-test).
12. **Prod features scaffolded but never run.** The 3 tier-1 "autonomous agents" (Conversation Trainer, LTV Predictor, KG Builder): `total_runs=0`, never executed. Arm or remove.
13. **CI/PR hygiene.** 31-run queue backlog at probe time; 6+ `codex/auto-fix-ci-*` PRs suggesting a re-trigger-without-closing loop; PR #1683 blocked 9 days (everything else is same-week churn); 2 dependabot PRs dormant 30 d; branch protection `strict:false` (merge can land against a stale base) — structural, not a live bug; 85 remote branches incl. `origin/air` (decommissioned machine) with tail to 2026-03-28. Worktrees: 44 on M5 but **healthy churn** (33/44 from the last 3 days), not a graveyard.
14. **Apps constellation debt.** wa-dashboard vs wa-dashboard-m1 = undeclared migration (m1 newer/growing, original untouched 5+ weeks); 4 empty Vercel shells (calendar/drive/mail/knowledge = logo + skeleton); `apps/kb` frozen since 03-31 (87 visa .txt — superseded by backend kb?); repo-root clutter (10 QA screenshots ~4 MB; 5 overlapping temp dirs: scratch/tmp/tmp_notebooklm/output/outputs); mlx-server crash-looping under KeepAlive (Abort trap 6); `verify-connectome` itself reports REGRESSED m5→pro-lan + Telegram send timeouts (the guardian fails honestly — but its findings are unconsumed).

### GREEN worth naming (so we don't fix what isn't broken)
Deploy pipeline clean (5 releases today, no rollback churn) · PG HA healthy · public surface all up · security hygiene genuinely good (0600 discipline, no tracked secrets, ANTHROPIC ban = 0 hits, ssh sane) · embedding freeze intact everywhere (`text-embedding-3-small` 100%) · 18 required checks armed, force-push off · W81 deploy-worktree on Pro alive and fresher than Pro's main checkout · Mini healthy as a server · escalations board empty with receptor registered · opus-mythos banner independently re-proven armed on all 3 machines this session (ledger line already closed upstream by #1914) · olympus + wr2-supervisor heartbeats live in prod DB.

**15. Fleet main-checkout lag (found while landing this report).** ALL three MAIN checkouts trail origin/main right now: M5 **17 behind** (at 3509f3e2ab), Pro **51 behind + dirty**, Mini **14 behind** (pulls Pro-first by design, so it inherits Pro's lag). This TAC's own TRIAGE read a stale PENDING-ARMS from M5's main and "re-discovered" an item closed upstream hours earlier (#1914) — a live demo of the meta-pattern below. Worktrees (created from origin/main) carry fresher truth than any main checkout today.

## 2 · §Meta-pattern (the malattia-delle-malattie)

**Unreconciled boundaries.** Every P1/P2 above is the same defect wearing different clothes: a boundary exists — api-process ↔ rag-process, repo ↔ $HOME, M5 ↔ Pro ↔ Mini, defined ↔ live, declared-log ↔ real-log, alert-path ↔ archive-path, wrapper ↔ payload — and a signal emitted on ONE side is trusted as truth for BOTH sides, with no reconciliation ever probing across:

- `/health/detailed` (api side) speaks for the rag side → false-critical.
- launchd exit-0 (wrapper side) speaks for the heartbeat payload → false-healthy while redis auth fails 5,470×.
- The repo view (M5 side) speaks for Pro's runtime → "watcher dead 14 d" when it ran this morning.
- M5's main checkout (17 behind) speaks for repo state → this very TAC's TRIAGE read an already-closed ledger line as open.
- `requirepass` (server side) changed without sweeping the client side.
- The fix (live side) never returns to the repo side; the plist (HOME side) never enters the repo side.
- DOCSYNC's "12 collections" (live side) sits unlabeled next to counts from the code side.

The organism's own doctrine already names the cure — "probe the work, not the proxy" (modus), W81 reconciliation, launchagent-reconcile #1926 — but the cure is deployed **per-scar**, not **per-boundary**. The single highest-leverage structural move available: a **boundary-reconciliation receptor per boundary class** (fleet-cron parity, repo↔HOME cmp, produced↔promoted, defined↔live, per-process health provenance), each a read-only reporter in the style already proven by PENDING-ARMS. Half of the further-analyses below are instances of exactly this.

Secondary pattern, method-level: **4 of 9 organ readers returned a materially wrong central claim** (world-readable that was 0600; "stale 12" that was live-vs-defined; "untracked" that was ignored-by-landmine; "watcher dead" that ran today). All four caught only because the orchestrator re-probed firsthand. Generator≠grader is not optional at TAC scale — expected ~30-40% false-sick rate confirmed at 44%.

## 3 · §Solo-operatore (physical / strategic / operator-only)

1. **TCC re-grant on M5** (System Settings → Privacy & Security → Full Disk Access): the launchd context lost `~/Desktop` again (W84, iTerm auto-update root cause); verify `SUEnableAutomaticChecks=0` survived.
2. **Redis password propagation on Pro**: the fix needs the secret value handled into 3-4 daemon envs — operator or a guarded Pro session (never via chat/cleartext).
3. **DeepSeek balance top-up or seat retirement** (PENDING-ARMS, 2× dead at council time).
4. **Product decisions**: wa-dashboard vs wa-dashboard-m1 (consolidate?); 4 empty Vercel shells (build or retire); `apps/kb` archive; never-run tier-1 agents (arm or delete).
5. **Policy decision**: branch protection `strict:false` — keep (fast merges) or enable + merge-queue (safe bases).
6. **Fleet main-checkout alignment**: Pro 51 behind with live dirty work (mata-garuda/wa-mirror — pull only after that lane parks; PENDING-ALIGN:Pro already on the ledger); M5 17 behind (interactive pull when convenient); Mini follows Pro by design.
7. **Token rotation** consideration for any credential that ever sat world-readable historically (audit found present-state clean).

## 4 · §Ulteriori analisi da fare (the prioritized list — deliverable)

| # | Analysis | Why now | Method (sketch) | Size |
|---|---|---|---|---|
| **A1** | **WhatsApp/IG inbound end-to-end audit** | 0 client messages in prod tables since 06-30; possible silent lead loss | Trace Meta webhook → Fly request logs → channel handlers → table writes; verify webhook subscription state with Meta; diff wa-mirror (Pro, raw) vs prod ingest for the same 72 h window | 1 session (P1) |
| **A2** | **"Who watches the watchers" observability truth audit** | 5 instruments proven lying/misanswering this flight | Inventory every monitor (health endpoints, sentinels, watchdogs, receptors, exit codes); probe each against the state it claims; add provenance (host/process/path) to each signal; fix redis-auth consumers; re-scope `/health/detailed` per process group; wire `verify-connectome` findings to a consumer | 1–2 sessions (P1) |
| **A3** | **Fleet boundary-reconciliation sweep (HOME-fork lint, all 3 machines)** | Confirmed diverged fix (fly-tunnel), repo-less crons, Pro-path plists on M5; Pro has 238 jobs never linted | For every plist/cron on M5+Pro+Mini: `cmp` live script vs repo, path-audit for wrong-user paths, log-path liveness; port back fly-tunnel fix + regulatory plist; make it a weekly reconcile REPORT (extend #1926) | 1–2 sessions (P1) |
| **A4** | **Regulatory delta promotion pipeline** | Alert path alive, archive path dead 14 d; agency's compliance memory has a hole 06-19→07-02 | Define promotion mechanism (Pro cron commit / PR bot); backfill the 14 stranded deltas; receptor: "delta produced but not promoted >48 h" | ½ session (P1) |
| **A5** | **Prod data-layer deep TAC** | 303 tables never censused; events_outbox 73k inserts; cell_* 46k episodes unknown ROI; schema-drift precedent (W-#9) | Dead-table census (writes since stats reset); outbox consumer lag; biggest-table growth curves; live schema vs migrations_v2 drift check; bloat via olympus data | 1 session (P2) |
| **A6** | **Qdrant estate audit** | 20 defined vs 12 live collections; host unknown (not Mini:6333); tool that should report it answers wrong | Locate the running Qdrant (Fly app? cloud?); enumerate live collections + vector counts vs the 104,154 claim; delta the 8 missing; fix `get_collection_stats` wiring | ½–1 session (P2) |
| **A7** | **Router registration parity + god-file split plan** | Historical silent-404 class (PRs #54/#55/#60); 2,243/2,149-line routers | Run `test_manifest_registration_parity` live; diff light vs heavy router sets; cohesion review of crm_practices/crm_clients for a split plan | ½ session (P2) |
| **A8** | **CI queue + auto-fix loop audit** | 31 queued runs; 6 codex auto-fix PRs possibly re-triggering; 2 dormant dependabot 30 d; #1683 aging | Runner capacity check; auto-fix loop close-out logic; triage the 3 stale PRs; strict:false recommendation with data | ½ session (P2) |
| **A9** | **Branch/worktree graveyard pass (W88 blob-verified)** | 85 remote branches, tail to March, origin/air zombie; cleanup cron can't run on M5 | Run `branch_graveyard_cleanup.sh` (content_on_main, blob-per-file) from a machine where it works; fix its plist paths; delete only content-on-main | ½ session (P2) |
| **A10** | **Apps constellation rationalization dossier** | 36 apps, ~25 stale by commit-age; duplications and shells confuse every future session | Per-app: keep/merge/archive recommendation with evidence (incl. remediator-vs-organism overlap, kb supersession grep, temp-dir policy, root clutter purge list) → operator decision sheet | 1 session (P2-P3) |
| **A11** | **M5 receptor/hook parity** | Documented safety net (stop_verify, org-alert, repomap…) absent on the PRIMARY machine | Decide per-hook: port to M5 / declare Pro-only and fix CLAUDE.md; add receptor self-test mode (distinguish silent-empty from silent-broken) | ½ session (P3) |
| **A12** | **Docs truth pass** | AI_ONBOARDING prose 2.6× wrong; CLAUDE.md drift (escalations path, hooks list, dead docs_sync target) | Put the prose block under DOCSYNC or delete it; label live-vs-defined metrics; correct CLAUDE.md refs; extend check-docs-sync to gate prose | ½ session (P3) |
| **A13** | **Autonomic-layer cost/ROI audit** | cell_* churns 19k critiques / 46k episodes; mlx-server crash-loops; 3 agents never ran; unknown quota burn | Map every always-on/cron LLM consumer → tokens/day per tier; kill/fix crash-loops; arm-or-remove the never-run; verify cron tier-1 Sonnet-5 migration state | 1 session (P3) |
| **A14** | **Security follow-ups (small)** | Present-state clean, but 3 loose ends | Move inline Telegram token from plist to sourced 0600 env; chmod 0600 the `.env.pre-*` backups; enumerate which other plists embed secrets (names found by o8 grep) | ¼ session (P3) |

**Suggested order: A1 → A4 → A2 → A3 (this week, P1) · A5–A9 (next) · A10–A14 (hygiene backlog).**

## 5 · Method notes & limits
- Diagnostic-only: nothing mutated except this report and one memory. PENDING-ARMS needed no edit: the banner line this TAC set out to close was already closed upstream (#1914) — independently re-proven here (grep = 2 on M5/Pro/Mini). Flowkit sibling lane in M5's working tree left untouched (leave-dirty).
- Not probed this pass: Vercel project state, Brevo/email channel, Telegram bot end-to-end, GA4/GSC, NotebookLM MCP liveness (not connected in this session — 5 of 10 configured MCP servers absent here), LangSmith traces, Tailscale health beyond symptom level, Qdrant host, actual token-spend telemetry.
- Reader corrections log (W65 in action): o8 "world-readable plist" → 0600; o2 "12 stale" → live-vs-defined; o1 "untracked, not gitignored" → ignored by `.gitignore:474`; o10 "watcher dead 14 d" → ran today, promotion dead. Four of nine.
