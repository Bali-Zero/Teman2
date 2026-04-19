# WR2 Bridge Publisher — GENOME

## Mission
Forward enriched Mata Garuda items for the 3 business-critical domains
(immigration_visa, tax_fiscal, investment_licensing) to WR2 via the existing
bridge infrastructure. Layer 5 — Distribuzione.

## Inputs
- Redis stream `garuda:enriched` (read-only)
- Cursor file `~/.agent/decisions/wr2_bridge_cursor.json`

## Output
- Envelope on Redis stream `bridge:outbound` with:
  - `type = "intel.research_dossier"`
  - `source = "mata-garuda/wr2_bridge_publisher"`
  - `priority = 2`
  - `payload = {dossier_id, title, summary, url, domain, relevance_score,
               source_agent, raw_timestamp, tags}`

## Filter
Items are forwarded only if:
- `domain ∈ {immigration_visa, tax_fiscal, investment_licensing}`
- at least one of `title`, `content` non-empty

No public_safe gating — these are internal feeds for WR2, not the public
channel.

## Success criteria
- No duplicates (cursor advances only after successful XADD).
- Ordering preserved (oldest-first publication inside a cycle).
- On first publish failure in a batch, cycle stops and cursor is retained
  for retry — at-least-once, at-most-once-per-cycle semantics.
- WR2 code untouched (this agent only produces stream payloads).

## Known gotchas
- WR2 has its own consumer on `bridge:outbound`. If it's down, items
  accumulate on the stream — check `XLEN bridge:outbound`.
- `intel.research_dossier` is NOT in MG bridge `PUSH_ROUTING`; messages
  are consumed by WR2 directly, not pushed to the Fly.io backend.
- Envelope payload is capped at 2000 chars for `summary`; longer bodies
  are truncated — WR2 can re-fetch via `url` if needed.

## Mutations history
_(empty at creation)_
