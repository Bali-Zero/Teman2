# Runtime ownership map — who runs what on Pro

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session
**Reference:** brainstorm 2026-05-02 round 2 § "Runtime ownership matrix"

Per Sprint 0 Track D1, Pro hosts ~200+ automations across 6 distinct
runtimes. This doc maps each runtime to:

- The automations it owns
- Its human owner (escalation path)
- Its maintenance cadence (when does someone touch it?)

## Tree map

```
Pro (single-host operational reality post Air retirement 2026-04-24)
│
├── OpenClaw (gateway 18789, agents main + coder + claude-code [3rd, undocumented])
│   ├── Telegram channel @Balizerobot — 98 daily conversation files (Feb-May 2026)
│   ├── Lobster workflows (4 production):
│   │   ├── autofix-loop.lobster
│   │   ├── nightly-code-quality.lobster
│   │   ├── weekly-dep-audit.lobster
│   │   └── nuzantara-dev-pipeline.lobster
│   ├── Knowledge Agents v12.1.0 (NOT EXPLOITED — Sprint 0 Track A4 unblocks)
│   ├── Cron scheduler (24 jobs FROZEN since 2026-04-30 — Track A5 disable plan)
│   ├── claude-mem extension (memory-core SQLite + observation feed)
│   └── mcporter integration (13 servers, 208 tools — Track A3 disable plan)
│       ├── nuzantara-mcp (124 tools, KEEP — actively used)
│       ├── nuzantara-mcp-advanced (13 tools, KEEP)
│       ├── filesystem (14 tools, KEEP_FORCE)
│       ├── memory (9 tools, KEEP_FORCE)
│       ├── docker, playwright, perplexity, brave, exa, context7,
│       │   sequential-thinking → recommended DISABLE (idle, not Bali Zero scope)
│       ├── vercel (auth required — leave broken)
│       └── fetch (offline — fix path or remove)
│
├── cron-agent-python (~/.cron-agent-python/, Python 3.11 manager-based dispatch)
│   ├── 18 strategies (LIVE PRODUCTION) — 18/19 stay here per split clean Opzione C:
│   │   ├── fact-checker (every 30min)
│   │   ├── tech-orchestrator (hourly)
│   │   ├── daily-ops (daily 08:00)
│   │   ├── system-doctor (every 4h)
│   │   ├── log-anomaly-detector (every 5min)
│   │   ├── fly-watcher (every 15min)
│   │   ├── intel-feed-processor (every 2h)
│   │   ├── oss-monitor (every 2h)
│   │   ├── pajak-monitor (daily)
│   │   ├── imigrasi-monitor (daily)
│   │   ├── bi-exchange-rate (daily)
│   │   ├── vision-doc (every 6h)
│   │   ├── tdd-pipeline (weekly)
│   │   ├── client-health-monitor (every 60s)
│   │   ├── compliance-ops (every 5min)
│   │   ├── conversation-trainer (weekly)
│   │   ├── translate-articles.py (hourly)
│   │   └── seo-guardian (every 40min observe + daily measure)
│   ├── 1 strategy (intel-radar) — Sprint 8 candidate migrate to OpenClaw + Knowledge Agents
│   └── State: ~/.cron-agent-python/sessions.db (SQLite, 69KB) + JSON state files
│
├── LaunchAgents (Pro launchd ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist)
│   ├── Cell core daemons (6 KeepAlive=true):
│   │   ├── com.cell.organism
│   │   ├── com.nuzantara.cell-observatory
│   │   ├── com.nuzantara.cell-observatory-collector
│   │   ├── organism.supervisor / organism.control-panel
│   │   └── (cell-observatory-prune cron, selfcheck cron — KeepAlive=false)
│   │
│   ├── WR2 Bali Dispatch (16 LA registered live; 13 in repo):
│   │   ├── 9 cognitive backbone:
│   │   │   ├── oracle (L4) — Sun 22:30 WITA
│   │   │   ├── strategos (L3) — Sun 22:00
│   │   │   ├── connector (L1) — daily 04:00
│   │   │   ├── supervisor (L2) — daemon
│   │   │   ├── pg-proxy (L2) — daemon
│   │   │   ├── learner-nightly (L1) — daily 03:00
│   │   │   ├── trend-hunter (L1) — every 2h
│   │   │   ├── measurer (L1) — every 6h
│   │   │   └── dossier-compiler (L1) — daily 04:30
│   │   └── 4-7 operational organelle:
│   │       ├── newsletter — Mon 09:00
│   │       ├── sla-worker — every 30min
│   │       ├── hardening — every 6h
│   │       ├── canva-apply, draft-generator, image-generator, topic-selector (Pro-only, drift)
│   │       └── canva-renderer (orphan in repo, Track B1 verify)
│   │
│   ├── Mata-Garuda 19-pipeline (10+ visible plist com.matagaruda.*):
│   │   └── daily-briefing, intel-bridge, kg-linker, kita-feed, nlm-expander,
│   │       public-channel, reg-alert, weekly-digest, wr-topic, wr2-bridge
│   │
│   ├── Sentinel cluster (12+ plist com.nuzantara.sentinel-* + com.balizero.*):
│   │   ├── nuzantara-sentinel (every 60s)
│   │   ├── sentinel-meta-watchdog (every 60s)
│   │   ├── automap-server / watchdog / telegram (event-driven + every 60s)
│   │   ├── auto_sentinel.sh (daily 03:00)
│   │   ├── intel-scraper-sentinel-bridge (every 5min)
│   │   ├── fly-restart-loop-detector (every 15min) — drive-poll incident antibody
│   │   ├── login-healthcheck (every 30min) — E2E user metric
│   │   ├── pro_heartbeat (hourly)
│   │   ├── dlq-autopilot (every 5min)
│   │   └── zombie-hunter (every 60s)
│   │
│   ├── Observed-shell tier targets (translate, BI, monitors, backups):
│   │   ├── Cron LA: translate-hourly, qdrant-snapshot, fly-pg-backup, etc.
│   │   └── (Sprint 1 emit migration to ObservedShellBus)
│   │
│   ├── Federation Alert Dispatcher (KeepAlive=true):
│   │   └── com.nuzantara.federation-alert-dispatcher (LISTEN federation_alert)
│   │
│   ├── Indexing sweep (daily 00:30 WITA):
│   │   └── com.balizero.indexing-sweep.daily (Phase 1 200 articles + Phase 2 600 KBLI)
│   │
│   └── SOTA M13 sub-cell (4 LA: checkpoint, collect, monthly, weekly)
│
├── mcporter (default disabled post-Track A3 manual; enabled on-demand by OpenClaw/Lobster)
│
├── Dismissed runtimes (per round 2 split-clean Opzione C):
│   ├── Jules — DELETE (no recent activity, dormant)
│   ├── kradle — DELETE (dormant)
│   ├── kimi — DELETE (only stores Kimi API sessions, not a runner)
│   ├── cagent — FREEZE (no autostart, no new automations)
│   └── claude-squad — LIMIT TO git/PR only (no automation runner role)
│
└── Cloud-side (NOT Pro-runtime, listed for completeness):
    ├── GitHub Actions: 29 workflows (CI, deploy, cron-cert-monitor,
    │                  cron-fly-cost-alert, cron-fly-watcher, cron-notifiers,
    │                  cron-practice-auto-create, etc.)
    └── Fly.io: 3 apps × N machines
        ├── nuzantara-rag (FastAPI backend, EventBus, 35+ services)
        ├── nuzantara-postgres (Postgres v0.1.0, backup → Tigris)
        └── nuzantara-qdrant (Qdrant v1.17.0)
```

## Per-runtime escalation paths

| Runtime | Human owner | Maintenance cadence | Escalation |
|---|---|---|---|
| OpenClaw | Antonello | Sprint 0 Track A4 upgrade plan; reactive on Telegram BOT_COMMANDS_TOO_MUCH | reload via `launchctl kickstart -k gui/501/ai.openclaw.gateway` |
| cron-agent-python | Antonello/Asya | weekly review of sessions.db growth | restart via plist or systemd-style |
| LaunchAgents (cell core) | Antonello | reactive on Sentinel telemetry | KeepAlive=true → auto-respawn 10s |
| LaunchAgents (WR2) | Antonello | weekly review (newsletter Mon, oracle Sun) | per-LA `launchctl unload/load` |
| LaunchAgents (Mata-Garuda) | Antonello | weekly review | per-LA `launchctl` |
| LaunchAgents (Sentinel) | Antonello | reactive on alerts | per-LA `launchctl` |
| Federation Alert Dispatcher | Antonello | reactive | LISTEN reconnect via supervisor |
| GitHub Actions | Antonello | reactive on CI failures | re-trigger via gh CLI |
| Fly.io services | Antonello/Asya | fly-watcher 15min telemetry | machine restart |

## Action items

### Sprint 0 follow-up (post-merge by Antonello)

1. Apply Track A2 (Telegram skill disable) on Pro
2. Apply Track A5 (24 frozen jobs disable) on Pro
3. Apply Track A3 (mcporter idle disable) on Pro
4. Apply Track A4 (OpenClaw upgrade v2026.4.29) on Pro

### Sprint 1+

5. Dismiss Jules + kradle + kimi (rm directories, no impact)
6. Freeze cagent (don't accept new strategies; existing 19 stay archived)
7. Limit claude-squad to git/PR scope (document the boundary)
8. Verify all 4 Pro-only WR2 plist exist (rsync to repo if missing)
9. Decide fate of `canva-renderer` orphan (rename or delete)

## References

- `docs/automations/runtime-register.md` (200+ row catalog)
- `docs/audits/sprint0/openclaw-{telegram-skills,upgrade-plan,frozen-jobs,claude-code-agent}.md`
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/06_openclaw_ecosystem_audit.md` § 10-12 (competitor runtimes)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § "Dismissione runtime morti"
