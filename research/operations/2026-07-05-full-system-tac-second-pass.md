# Full-System TAC — Second Pass (re-scan with live proofs + A2-A14 burn-down)

---
date: 2026-07-05
domain: operations
mandate: "TAC-2 full-system + burn-down A2-A14" (Zero, ~/.fable-mandates/tac2.md — autonomous Fable 5 session, Mini-Pro2, tmux fable-tac2)
gear: 3 (modus PROFONDO)
method: every TAC-1 P1/P2 finding re-proven LIVE this session (proprioception local+fleet, launchctl print + log CONTENT, prod HTTP probes with real payloads, read-only ssh to Pro, live Qdrant census via /health/collections); 2 Sonnet read-subagents (A6/A13) whose every load-bearing claim was re-proven first-hand (W65); repo-side cures shipped from worktree infra-tac2-burndown
sources: live probes this session; TAC-1 = research/operations/2026-07-02-full-system-tac-first-pass.md
---

## 0 · Delta table — TAC-1 finding → today, one fresh proof per row

| # | TAC-1 finding | Today | Fresh evidence (2026-07-05) |
|---|---|---|---|
| P1-1 | Redis NOAUTH corrupts Pro self-monitoring (5,470 AuthErr) | **HEALED** | meta-dispatcher.log: 0 AuthenticationError in last 300 lines, "PEL drained"; ALL 129 Pro sidecars fresh ≤5 min (federation_alert_dispatcher 17:10, was 22.6d stale); zero sidecars >7d |
| P1-2 | Client-message ingest silent since 06-30 | **WA HEALED (first-inbound proof) · IG STILL DEAD** | omnichannel thread `channels=[whatsapp]` created 2026-07-05T07:02:52Z — proves the path works again, not sustained health (that needs the channel-sidecar self-probe, §1-N8); newest IG thread 2026-06-23 (Meta panel = operator-only, per mandate not attempted) |
| P1-3 | Regulatory: alert alive, archive dead | **PARTIALLY HEALED + NEW DISEASE** | 06-28→07-02 deltas on main (#1945); 07-03 delta was stranded on Pro (backfilled this PR, sha-verified); 07-04 run left no log trace; **07-05 run produced NOTHING** — see §1-N1 |
| P1-4 | /health/detailed lies-critical | **STILL SICK** | live curl: `status=critical`, search/ai/router "unavailable" while /health=healthy and real searches work |
| P1-5 | W84 TCC on M5 | **CLOSED per ledger + NEW VECTOR ON PRO** | M5 re-granted 07-04, Mini 07-05 (ledger, proven-by-session); NEW: Pro post-reboot-07-04 — see §1-N2 |
| P2-6 | 3 crons exit-127 on Pro | **STILL SICK** | launchctl today: `com.balizero.autonomous-lab`, `-runner`, `com.nuzantara.intake-proposal-health-sentinel` all last-exit 127 |
| P2-7 | .gitignore:474 bare `main.py` hides sources | **CURED THIS PR** | pattern anchored to `/main.py`; remediator + graph-engine main.py fetched from Pro, secrets-grepped, tracked; `git check-ignore` now clean |
| P2-8 | fly-tunnel HOME fork carries unported fix | **HEALED (repo side)** | repo `scripts/fly_pg_tunnel_supervisor.sh` now carries the FLY_ACCESS_TOKEN hoist; M5 blob-proof = PENDING-ALIGN (M5 untouchable, 2 sister sessions live) |
| P2-9 | Cron parity broken on M5 (Pro-path plists) | **NOT RE-PROBED (fence)** | repo plist still hardcodes `/Users/nuzantara` paths (branch-cleanup.weekly:12,37,44,47) — A11 lane, operator |
| P2-10 | Docs lie 2-2.6× next to DOCSYNC | **CURED THIS PR** | AI_ONBOARDING prose no longer carries its own counts; channels = 4 live + 3 quarantined; CLAUDE.md escalations path fixed to the file that exists |
| P2-11 | Observability instruments answer wrong | **PARTLY HEALED UPSTREAM + 2 CURES THIS PR** | stale-detector already machine-gated (hostname residency, on disk today); `pro.sentinel.json` EXISTS fresh (the 07-04 backlog claim was overtaken); cures: machine-aware cleanup organ-id + W84 marker freshness gate |
| P2-12 | 3 Tier-1 agents never ran | **STILL TRUE — istruttoria done** | live API: `total_runs=0, next_run=null` ×3; root causes + decision sheet in docs/runbooks/autonomous-agents-decision-sheet.md (§1-N5) |
| P2-13 | CI/PR hygiene | **IMPROVED** | gh on Mini healed (auth valid, push OK — the 07-02 "token invalid" memory is stale); queue moving (#1961/#1962 merged today); deeper CI audit = A8, not run |
| P2-14 | Apps constellation debt | **OPERATOR LANE + 1 NEW** | new: wr2 deploy-clone frozen (§1-N3); rest unchanged, operator decision sheet still pending (A10) |
| 15 | Fleet main checkouts behind | **HEALED** | Mini == Pro == origin/main `67bcf78ef` at probe time; Pro dirty 47 files = live operator work (left alone) |

## 1 · New findings (not in TAC-1)

1. **Regulatory watcher run-shape failure (P1, cured this PR).** The 07-05 tier-1 run:
   sonnet-5 in `--print` spawned its 6-step work as a *background task*; the CLI terminated
   it at the 600s print ceiling ("Background tasks still running after 600s; terminating"),
   exited 0, and the wrapper declared SUCCESS with no file. The wrapper's own
   anti-hallucination guard caught it — but only to log a WARNING: the cascade never fired
   because "exit 0 + no quota marker" was the success test. Cures shipped: 30-min BG
   ceiling + inline-only prompt directive + `ensure_delta()` per tier (file ∨ worktree
   recovery ∨ stdout-JSON extraction — tiers 2-4 were text-out alert-theater before) +
   W84 fail-fast probe (exit 78). **HOME copies on Pro/M5 must be re-synced** (ledger).
2. **W84 new vector on Pro: interpreter-level TCC split (operator-only).** Since Pro's
   2026-07-04 reboot, the launchd job rooted at `/bin/zsh` (regulatory watcher) gets
   `Operation not permitted` reading `~/Desktop/.../heartbeat.sh`, while the job rooted at
   `/bin/bash` (wr2-deploy-pull) reads `~/Desktop` fine at 17:06 the same day. TCC grants
   survive per-binary, not per-user: the reboot killed zsh's grant only. Cure = operator
   re-grant; the wrapper now fails fast instead of half-running.
3. **wr2 deploy-clone frozen dirty (Pro, read-only fence — ledger).** PR #1958 removed the
   retired canva-token-watchdog plist from canon; the deploy clone
   `~/Desktop/nuzantara-deploy` had the same file locally deleted → tree dirty → the
   deploy-puller refuses to pull, `error:dirty` hourly, clone stuck 4 commits behind
   (8e62ccfaf). One-liner cure for a Pro session: `git -C ~/Desktop/nuzantara-deploy
   checkout -- infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist`, then
   the next pull deletes it as canon does.
4. **Mini prod-DB access-wall (W87 family, operator).** Keychain entry
   `nuzantara-postgres-readonly` absent on Mini → `pg.sh` dead AND the postgres MCP dies at
   first query (SASL "password must be a string") while the flyctl tunnel itself is alive
   and proxying on :15432. Bonus: Mini's untracked `.mcp.json` is a stale M5 copy
   (`cwd=/Users/balizero/...`) and its nuzantara-mcp key gets HTTP 401 from prod — the
   whole MCP layer on Mini is Esiste≠Armato. (Keychain via ssh on Pro is also locked —
   interactive-session grants don't extend to ssh principals.)
5. **Tier-1 "autonomous" agents: the migration that never happened (A13).** Root cause
   pinned (subagent lead, every line re-verified first-hand): the ENTIRE
   AutonomousScheduler never starts — its call-site is commented out in
   `service_initializer.py` since commit 8dec12830 (2026-02-11, "omnichannel
   stabilization"); even if re-enabled, the trainer is hardcoded `enabled=False` and the
   other two were never `register_task`-ed at all. The claimed "migrated to OpenClaw
   cron" never materialized (OpenClaw cron itself retired on Pro). Extra: execution stats
   live in an in-memory dict — `/status` resets at every deploy — and the
   `chain_daily_ops_autopilot` docstring promises "restart stale agents" while the code
   only reads `/status` (theater). Decision sheet shipped (arm-or-retire per agent).
6. **Qdrant estate: worse than TAC-1 said (A6).** Live census (14 collections · 113,818
   docs) vs the manager's 20 definitions: only **6** overlap; **14** definitions are dead
   names; **8** live collections — including the two biggest (81k, 15k points) — have no
   definition. Deeper (subagent lead, re-verified): there are TWO parallel registries —
   `core/collection_registry.py` (~20 alias keys folding to ~10 canonical names; the
   likely source of TAC-1's "20") and the manager's own dict with 6 names the registry
   never saw — never reconciled with each other, let alone with the live estate. The
   DOCSYNC "12 · 104,154" is a frozen cache (QDRANT_URL/KEY unset on Mini AND Pro — it
   can never refresh). Documented-as-known this PR; regeneration needs a maintainer run
   with Qdrant env. Flags: `garuda_assets` live-but-empty; `visa_oracle` 90 live points
   vs 1,612 annotated.
7. **Watcher source degradation (report-only).** The backfilled 07-03 delta itself records:
   NB-INTEL-Regulation query auth-failed, and 5/5 web sources 403/404 (hukumonline, ortax,
   muc, ikpi, peraturan.bpk). The watcher's evidence base is thinning while its pipeline
   was also broken — compliance memory is running on NB-INTEL-Tax/Immigration/Press only.
8. **channel.\* heartbeats are vacuous green.** All four channel sidecars say `status:ok`
   with `last_event_seen_at: null, queue_depth: 0` — a receptor that has never seen an
   event reports healthy. W84-in-costume; needs a self-probe (healthy-silent vs dead).
9. **Minor (Mini):** `overlap-detector.daily` exit 1; `local-livekit-server` exit -15;
   gsc-indexing plist had unescaped `&` (XML-invalid since creation — fixed this session,
   left DISARMED for the operator to decide).

## 2 · Burn-down ledger (what this session shipped)

| Lane | State | Artifacts |
|---|---|---|
| A2 observability truth | **DONE** (scoped) | machine-aware organ-id in `agent_worktree_cleanup_cron.sh`; W84 marker freshness gate in `launchd_liveness_detector.py` (+4 unit tests, 6/6 pass); 07-04 backlog items verified already-cured upstream (documented, not re-cured) |
| A4 regulatory promotion | **DONE** | 07-03 delta backfilled (sha-verified from Pro); wrapper canon: 4 cures (§1-N1); HOME re-sync = ledger |
| A6 Qdrant estate | **DONE** (document-as-known) | live census + reconciliation runbook + dated warning in collection_manager.py; regeneration = next PR with Qdrant env |
| A13 autonomic ROI | **DONE** (istruttoria) | decision sheet docs/runbooks/autonomous-agents-decision-sheet.md; runtime untouched |
| A12 docs truth | **DONE** | AI_ONBOARDING prose de-numbered (counts live only in DOCSYNC); channels 4-live; CLAUDE.md escalations path; docs_sync regens in-commit (W86) ×2 |
| A3 Mini reconcile | **DONE** | 19 plists scanned; mlx wrapper canon-paired (canon log-path fixed first, HOME synced cmp-clean, kickstarted, `/v1/models` answers = PROVEN LIVE); 2 junk .bak >30d deleted (re-run: 0 eligible); gsc plist XML fixed, disarmed; Pro's 101 = report-only per fence |
| P2-7 gitignore | **DONE** (cure-while-diagnosing) | anchored pattern + 2 sources surfaced |
| Stretch A5/A7/A9 | **NOT RUN** | time went to the new P1s (N1-N4); A9 graveyard needs `content_on_main()` blob-per-file — next session |

## 3 · §Meta-pattern (the malattia-delle-malattie, second order)

TAC-1 named **unreconciled boundaries** — a signal on one side of a boundary trusted as
truth for both sides. TAC-2 confirms it and sharpens it one level down: the organism's
**own cures create the next boundary**. Every new disease found today is yesterday's cure
half-armed:

- The redis `requirepass` hardening (06-29) → the NOAUTH storm (cured 07-03) → **today
  proven healed** — the only fully-closed loop in the set, and it took three sessions.
- The sonnet-5 cron migration (07-03, probed per-agent) → the 07-05 watcher failure: the
  new model's new *behavior* (backgrounding work) broke the one-shot contract the probe
  never tested. A migration probe that checks "answers correctly" but not "honors the
  run-shape" is a proxy.
- The TCC re-grants (07-04 M5, 07-05 Mini) → Pro's reboot silently revoked a *different*
  binary's grant the same week. The grant is per-principal state that decays per-machine,
  per-binary, per-reboot — and nothing inventories it (the liveness detector sees the
  corpse, not the revocation).
- The canva watchdog retirement (#1958, "ritiro-non-propagato scar honored" in its own
  ledger line!) → still froze the deploy clone, because the clone's *working tree* was a
  third copy nobody's reconciliation listed.
- The hybrid-collection migration (Qdrant, months ago) → 14 dead definitions + 8
  undocumented live collections; the migration moved the data and never came back for the
  registry.

**Precision (post red-team).** The genus is the organism's known disease — *proxy
substitution*, trusting a cheap observable as the invariant (superscar #2's "green ≠
working"). TAC-2's genuinely NEW second-order finding is its dominant, most actionable
subtype this week: **"a cure is done when the artifact lands."** It is not — a cure is
done when every REPLICA of the state it touched (HOME copy, deploy clone, sidecar cache,
TCC grant, registry entry, DOCSYNC cache) has either followed or been explicitly listed
as pending. The PENDING-ARMS ledger already encodes this for *merge/install* arming;
what's missing is the same discipline for **replica propagation** — a cure's
blast-radius enumeration ("which copies of this state exist?") at SHIP time. The
launchagent_reconcile categories (canon-paired vs fork) are the embryo of exactly that,
applied to one replica class. Generalizing it (deploy clones, sidecar caches, TCC
grants, MCP configs, collection registries) is the highest-leverage structural move
left. Two of today's findings do NOT reduce to replicas and stay filed under the genus:
the sonnet-5 run-shape break (a *contract* the migration probe never tested) and the
watcher's source decay (evidence-base rot, not state drift).

Method note (W65, again): the a13 read-subagent marked its task complete without
delivering its report in time; every claim in §1-N5 was re-proven first-hand before
writing. The a6 subagent went silent; §1-N6 is entirely first-hand. Subagent output is a
lead, never a verdict — twice confirmed by absence this time.

## 4 · §Solo-operatore (physical / strategic / operator-only)

1. **Pro TCC re-grant** for the launchd zsh principal (System Settings → Privacy &
   Security → Full Disk Access) — the regulatory watcher will exit 78 loudly until then.
   While there: verify bash/zsh BOTH granted, and re-check after every reboot (the 07-04
   reboot is what killed zsh's).
2. **Mini keychain**: add `nuzantara-postgres-readonly` (account `nuzantara_readonly`) —
   secret value handling, never via chat. Then Mini's pg.sh + postgres MCP come alive.
3. **Mini `.mcp.json`**: replace the stale M5 copy (`cwd=/Users/balizero/...`, dead
   NUZANTARA_API_KEY) — 10-minute interactive fix on the main checkout (worktree hooks
   block agent writes there by design).
4. **Pro session one-liners** (or next Pro-resident agent session): deploy-clone unfreeze
   (§1-N3); re-sync `~/scripts/regulatory-watcher-run.sh` + `~/scripts/lib/heartbeat.sh`
   from canon; repoint-or-retire the 3 exit-127 crons.
5. **Decisions pending**: A13 arm-or-retire per agent (sheet shipped); gsc-indexing cron
   arm-or-retire (plist now valid, disarmed); Qdrant definitions regeneration PR (needs
   QDRANT_URL/KEY exported once on a canonical machine); IG inbound (Meta panel, DM access
   — ledger line from #1962).
6. **Watcher evidence base**: NB-INTEL-Regulation auth failure + 5 dead web sources need
   a source-list refresh (regulatory-watcher agent spec).

## 5 · Method notes & limits
- Pro touched via read-only ssh only; M5 not touched (2 sister sessions live); Mini HOME
  changes limited to the A3 mandate scope (mlx wrapper sync+kickstart, 2 junk deletions,
  gsc XML fix).
- Not probed: Vercel state, Brevo/email, Telegram bot e2e, GA4/GSC, LangSmith, A5 data
  layer, A7 router parity, A8 CI deep-audit, A9 graveyard (all inherit TAC-1 state).
- Arsenal live-probed: GLM seat DEAD on Mini (single re-probe per mandate — Keychain
  token absent outside GUI) AND agy DEAD on Mini ("authentication failed" — the mandate
  declared it operative; seat-level Esiste≠Armato, ledger line opened). Declared cascade:
  red-team second opinion ran on **Codex GPT-5.5** (read-only sandbox).
- Codex red-team verdicts incorporated: §Meta-pattern narrowed (proxy-substitution genus,
  replica-propagation subtype); P1-2 relabeled first-inbound-proof. Residual risks
  accepted knowingly: `ensure_delta()` validates delta *schema*, not content quality
  (an extracted-but-thin delta still publishes — bounded by the NB/web grounding in the
  agent spec); the redis-heal proof is heartbeat-mediated but DOES cross the auth
  boundary (a sidecar goes fresh only if the daemon's authenticated redis write
  succeeded); the W84 marker freshness gate can hide a failure only if the failing job
  also stops logging — that case is separately surfaced as stale_green.
- PII: zero client identifiers in this report; WA/IG evidence cited as timestamps only.
