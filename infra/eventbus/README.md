# infra/eventbus — Bali Zero Event Bus (W1-W4)

Multi-week event-driven architecture deployed 2026-05-09 → 2026-05-10.

## Live location (Pro)

`~/scripts/eventbus/` — symlink-equivalent of this directory. Daemons run from
that path via LaunchAgent labels:

- `com.balizero.meta-dispatcher`
- `com.balizero.intel-dedup-gateway`
- `com.balizero.research-sentinel`
- `com.balizero.cron-log-sentinel`
- `com.balizero.observatory` (~/agents/.observatory/observatory.py — separate dir)

This `infra/eventbus/` directory is the **snapshot in git** for backup +
peer-machine sync. The authoritative runtime path is still `~/scripts/eventbus/`.

## Architecture

- **Bus**: Redis Streams (`bz:*` namespace) on Mini Tailscale `100.93.236.6:6379`
- **Schema**: 10 event types declared in `schema.py` with required keys + enum guards
- **Publisher**: `publisher.py` — ULID generation + redis-py XADD with MAXLEN approximation
- **Subscriber**: `subscriber.py` — consumer groups + PEL drain on boot + DLQ park after 3 retries
- **Heartbeat**: `heartbeat.py` — background thread, Redis SET with TTL, list_all_heartbeats() probe
- **Dispatcher**: `meta_dispatcher.py` — central router, declarative ROUTING_RULES dict
- **Gateways**: `intel_dedup_gateway.py` (sha256 dedup), `research_sentinel.py` (volume + DLQ watchdog), `cron_log_sentinel.py` (tail -F log files)
- **Runner**: `devils_advocate_runner.py` — wraps DA sub-agent invocation, sniffs JSON, publishes `redteam.completed`

## Event types

| Event | Producer | Consumer(s) |
|---|---|---|
| `intel.collected` | scrapers, cron-log-sentinel | intel-dedup-gateway, observatory |
| `intel.deduped` | intel-dedup-gateway | meta-dispatcher → kickstart topic-selector |
| `regulatory.delta.detected` | regulatory-watcher | meta-dispatcher → Telegram if urgency≥high |
| `topic.candidate.created` | topic-selector | meta-dispatcher → kickstart wr2-supervisor |
| `content.draft.ready` | wr2-design-architect | meta-dispatcher → spawn DA (high-stakes) or canva-apply |
| `redteam.completed` | devils-advocate-runner | meta-dispatcher → spawn canva-apply (PASS) / Telegram (BLOCK/NEEDS_FIX) |
| `human.review.completed` | damar queue UI | observatory (audit) |
| `publish.completed` | canva-apply / IG channel | observatory, ig-metrics-scraper schedule |
| `engagement.measured` | ig-metrics-scraper | reflexion (weekly batch) |
| `learning.updated` | reflexion / voyager / ig-metrics-analyst / competitor-monitor / devils-advocate | meta-dispatcher → Telegram digest |

## Live status (snapshot 2026-05-10 06:12 WITA)

5/5 daemon ALIVE. 11 streams active. DLQ size = 0. Pre-publish gate
end-to-end live-tested with both PASS and BLOCK verdict paths.
