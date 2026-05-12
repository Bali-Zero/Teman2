# Bali Zero Event Bus — Schema v1

**Version**: 1.0 · **Date**: 2026-05-09 · **Backbone**: Redis Streams (Mini-Pro2 100.93.236.6:6379)

## Stream namespace

All Bali Zero eventbus streams use prefix `bz:` to avoid collision with existing `garuda:*` (OSINT) streams.

## Event types (8 base)

| Event type                  | Stream key                     | Producer(s)                                                | Consumer(s)                                                                  | Payload required keys                                                                                                                  |
| --------------------------- | ------------------------------ | ---------------------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `intel.collected`           | `bz:intel.collected`           | bali-intel-scraper, regulatory-watcher, competitor-monitor | matagaruda.intel-bridge (dedup), Meta-Dispatcher                             | `event_id, source, citation_or_url, raw_payload, collected_at, agent_name`                                                             |
| `intel.deduped`             | `bz:intel.deduped`             | matagaruda.intel-bridge (dedup gate)                       | wr2-topic-selector, regulatory-watcher consumer                              | `event_id, original_event_id, content_hash, dedup_key, normalized_payload, deduped_at`                                                 |
| `regulatory.delta.detected` | `bz:regulatory.delta.detected` | regulatory-watcher                                         | wr2-topic-selector, email-template-builder, Meta-Dispatcher (Telegram alert) | `event_id, citation, regulation_type, service_lines[], summary, urgency: low\|medium\|high\|critical, source, detected_at`             |
| `topic.candidate.created`   | `bz:topic.candidate.created`   | wr2-topic-selector                                         | wr2-supervisor                                                               | `event_id, topic_slug, domain, audience_segment, score, source_intel_event_id, key_facts[], created_at`                                |
| `content.draft.ready`       | `bz:content.draft.ready`       | wr2-design-architect (Step 6)                              | damar-queue-server, canva-apply                                              | `event_id, topic_slug, slides_path, brief_path, critic_report_path, slide_count, hero_count, status: pass\|needs_human_edit, ready_at` |
| `human.review.completed`    | `bz:human.review.completed`    | damar-queue-server                                         | wr2-reflexion (weekly batch), Meta-Dispatcher                                | `event_id, item_id, action: published\|rejected\|edited, designer_override_diff, reason_tag, completed_at, instagram_post_url?`        |
| `publish.completed`         | `bz:publish.completed`         | canva-apply, damar-queue-server                            | wr2-ig-scraper.daily (queues for metrics scrape)                             | `event_id, item_id, canva_design_url, instagram_post_url?, published_at, channel: instagram\|telegram\|email`                          |
| `engagement.measured`       | `bz:engagement.measured`       | wr2-ig-scraper.daily                                       | wr2-reflexion.weekly, wr2-ig-metrics-analyst                                 | `event_id, item_id, instagram_post_url, likes, comments, save_count?, reach?, scraped_at, hours_since_publish`                         |
| `learning.updated`          | `bz:learning.updated`          | wr2-reflexion.weekly, wr2-voyager.weekly                   | Meta-Dispatcher (Telegram digest), nb-curator                                | `event_id, source: reflexion\|voyager\|ig-metrics-analyst, lessons[], proposed_amendments[], updated_at`                               |

## Common envelope (all events)

Every event MUST include these fields:

```json
{
  "event_id": "ULID",
  "event_type": "<dot.notation>",
  "version": 1,
  "emitted_at": "ISO 8601 UTC",
  "emitted_by": "<agent_name>",
  "trace_id": "ULID (correlation across causal chain)",
  "payload": { ... event-specific keys ... }
}
```

## Causality (trace_id propagation)

When agent B consumes event from agent A and emits a derived event, B MUST propagate A's `trace_id` (NOT generate new). This lets the observability dashboard reconstruct the full causal chain (e.g., "PMK 28 collected → deduped → topic created → carousel drafted → reviewed → published → engagement measured" all share same trace_id).

If event is root-emitted (no causal parent), generate fresh `trace_id == event_id`.

## Idempotency

Consumers MUST be idempotent on `event_id`. Same event delivered twice = noop on second.

Implementation: each consumer maintains a small recent-event cache (Redis SET, TTL 24h) keyed `bz:consumer:<agent_name>:seen`. Before processing, `SISMEMBER`; after processing, `SADD`.

## Stream retention

- `bz:intel.collected` → 30 days (high volume)
- `bz:intel.deduped` → 30 days
- `bz:regulatory.delta.detected` → 90 days (low volume, audit value)
- `bz:topic.candidate.created` → 30 days
- `bz:content.draft.ready` → 30 days
- `bz:human.review.completed` → 365 days (training signal)
- `bz:publish.completed` → 365 days
- `bz:engagement.measured` → 365 days (long-tail learning)
- `bz:learning.updated` → 365 days

Use `XADD ... MAXLEN ~ N` with approximate trimming.

## Consumer groups

Each consumer agent MUST use a named consumer group: `bz:cg:<agent_name>`. This enables:

- At-least-once delivery semantics
- `XREADGROUP` for pull-based read with auto-ack on success
- `XPENDING` to inspect stuck messages
- Multiple consumer instances can share group (load-balance) — though Bali Zero uses single instance per agent typically

## Dead-letter queue

Failed events (consumer raised exception or skipped via taboo) → republished to `bz:dlq` with extra fields `failure_reason`, `original_stream`, `failed_at`, `retry_count`. Manual inspection via Damar UI or Meta-Dispatcher report.

## Cross-LLM/cross-host portability

All payloads are pure JSON. Consumers can be Python (preferred), shell (`redis-cli`), or any language with Redis client. No Python pickle, no Avro, no Protobuf — KISS.

Mini Redis IP `100.93.236.6:6379` reachable from Pro+Mini via Tailscale `balizero` net. Outside tailnet = unreachable (private OSINT scope, intentional).

## Out of scope (explicit non-events)

- File system events (use `fs_usage` if needed, separate channel)
- Process liveness (System Reliability Supervisor handles, separate channel)
- LaunchAgent state changes (launchctl events, separate)
- HTTP requests (direct to FastAPI/queue server, no event indirection)
