# MG → WR2 Bridge Envelope Schema

> **Owner:** W4 Distribuzione vertical (Layer 5).
> **Agent:** `mata_garuda/agents/wr2_bridge_publisher.py`
> **Status:** Producer online (this PR). WR2 consumer side unchanged.

## Overview

Mata Garuda's Layer 5 `wr2_bridge_publisher` emits research-dossier
envelopes onto the shared Redis stream `bridge:outbound`. WR2 already has a
connector that consumes `bridge:outbound` — we do not touch WR2 code.

This doc nails down the envelope contract so the two organs can evolve
independently.

## Transport

- **Stream:** `bridge:outbound` (Redis Streams, XADD/XREADGROUP).
- **Encoding:** Envelope `to_redis_dict()` → flat string fields
  (`id`, `type`, `source`, `timestamp`, `priority`, `payload`).
- **Payload encoding:** JSON-encoded UTF-8 inside the `payload` field.

## Envelope header

| Field | Value | Notes |
|-------|-------|-------|
| `type` | `intel.research_dossier` | Fixed for this publisher |
| `source` | `mata-garuda/wr2_bridge_publisher` | Producer identifier |
| `priority` | `2` | 1–5 scale; 2 = medium-high |
| `timestamp` | ISO 8601 WITA | Set by Envelope default |
| `id` | UUID4 | Envelope idempotency key |

## Payload schema

```json
{
  "dossier_id": "<redis stream id of source garuda:enriched item>",
  "title": "<human readable title>",
  "summary": "<body excerpt, max 2000 chars>",
  "url": "<canonical source URL>",
  "domain": "immigration_visa | tax_fiscal | investment_licensing",
  "relevance_score": 0-5,
  "source_agent": "<upstream harvester id>",
  "raw_timestamp": "<original item timestamp, ISO>",
  "tags": ["tag1", "tag2"]
}
```

### Field notes

- `dossier_id` is stable across retries (uses the source stream id, not a
  new UUID). WR2 can dedup on this alone.
- `summary` is truncated at 2000 chars. For longer bodies, WR2 can
  re-fetch via `url`.
- `domain` is restricted to the 3 WR2-relevant domains. Other enriched
  items are filtered out client-side by the publisher.
- `tags` is best-effort; empty list if upstream did not tag.

## Filter rules (producer side)

Items are forwarded only if ALL:

- `domain ∈ {immigration_visa, tax_fiscal, investment_licensing}`
- At least one of `title`, `content` is non-empty.

Unlike the public TG channel, `public_safe` is NOT checked here — WR2 is
an internal consumer.

## Delivery semantics

- **At-least-once:** Cursor advances only after `XADD` returns a stream id.
- **Ordered within cycle:** The publisher sorts fresh items oldest-first
  before XADD.
- **Backpressure-friendly:** On XADD failure the cycle stops and the
  cursor is retained, so the next cycle replays from the same position.

## Cursor

- Path: `~/.agent/decisions/wr2_bridge_cursor.json`
- Format: `{"last_id": "<redis stream id>"}`
- Reset: delete the file to re-emit the last N items on next cycle.

## Backward compatibility

- Envelope `type` is versioned by convention. If the payload schema
  changes, bump to `intel.research_dossier.v2` rather than mutating v1.
- This contract is one-way (MG → WR2). Feedback from WR2 (e.g. "dossier
  accepted") is out of scope here and would arrive via `bridge:inbound`.

## Operational notes

- Plist: `infra/launchagents/com.matagaruda.wr2-bridge.hourly.plist`
  (every 3600s).
- Observability: included in the `mata-garuda health` CLI stream section
  (bridge:outbound length).
- If WR2 consumer is down, items accumulate on `bridge:outbound` — check
  `redis-cli XLEN bridge:outbound` for backlog.
