# Protected-data boundary — Intel Lake / MATA GARUDA consolidation

This document is itself part of the boundary it describes: nothing below quotes a real
`intel_items`/`intel_observations` row, a real MATA GARUDA OSINT payload, or any client/CRM
record. Every example is a schema shape, a code comment already on disk, or a synthetic
placeholder explicitly marked as such.

## 1. Two different boundaries, easy to conflate

The dispatch prompt names one rule ("PII: absolutely no real Intel Lake rows anywhere"). Reading
the actual code this session surfaced that there are **two distinct boundaries** in play, with
different owners and different current enforcement, and Packet 05's design must not collapse
them into one:

1. **Client/CRM PII** (SYMBIOSIS Law 2 / UU PDP, the whole-repo rule) — does not apply to Intel
   Lake's own domain directly (Intel Lake ingests public news/regulatory items, not client
   records), but applies absolutely to this lane's own conduct and to any object this packet
   designs that might later carry a client-facing field.
2. **MATA GARUDA's OSINT-blindato boundary** (`apps/mata-garuda/CLAUDE.md`, its own, stricter,
   pre-existing rule, read in full this session) — governs *raw collected OSINT content itself*,
   independent of whether any of it happens to be PII. Its own stated flow: `cloud → Mata Garuda
   (IN)`, then only `Mata Garuda → Nuzantara (business)` or `Mata Garuda → Zero TG (OUT)`. This
   is narrower than "no PII" — it restricts raw *content*, including public-source article text,
   from ever reaching `apps/mouth/`, any frontend, clients, the Bali Zero team, any cloud
   provider, or any public repo/gist/pastebin.

Packet 05's consolidation crosses both organs. A design that only checks "is this a client
record" and clears MATA GARUDA content for wider circulation because it is "just news" would
violate rule 2 even though it never touches rule 1.

## 2. What MATA GARUDA already permits to leave, and the exact shape of the exception

`apps/mata-garuda/CLAUDE.md` §1.4, "Eccezione Pillar 3 SYMBIOSIS — KG metadata sharing," is the
**one** named, Zero-authorized (2026-05-06) carve-out. Read verbatim this session:

- **Permitted payload** across the Tailscale-loopback-only KG bridge: `name`, `type`,
  `source_count`, `last_seen`, `neighbor_names`, `observation_count`, and
  `observation.source_url` (explicitly noted: "sempre URL pubblico, mai body content" — always a
  public URL, never body content).
- **Forbidden payload**, same bridge, same sentence: `observation.value` (may contain raw
  title/snippet OSINT), any content field, full article text.

This is the ceiling for any Cohort-B design touching MATA GARUDA-sourced data. Concretely, for
Packet 05's `IntelEvent` mapping (CONTRACT-MAP.md §5.1): an `IntelEvent` whose `source` traces
back to a MATA GARUDA producer and whose `classification.sensitivity` is `restricted_osint` may
carry `source.canonical_url` (a public URL — permitted by analogy to `observation.source_url`)
but its `payload_ref` must be a `DurablePayloadReference`, never an `InlinePublicPayload` — the
frozen contract's own validator already forbids inline payloads for any sensitivity other than
`public` (`intel_event.py:278-287`, read this session), which happens to line up with MATA
GARUDA's own stricter rule for the same case. Where the two rules would conflict (none found
this session — MATA GARUDA's rule is uniformly stricter than the frozen contract's default), the
stricter rule governs; SYMBIOSIS Law 2 is explicit that internal minimization policy can exceed
what the frozen contract's structural validator alone would require.

## 3. Where the classification actually lives today: nowhere in the shared schema

CONTRACT-MAP.md §5.1 already flags this as a modeling gap; restated here as a boundary
consequence. `intel_items`/`intel_observations` (migration `168`) have **no** `sensitivity`,
`classification`, or `tlp` column. The only place a TLP-like axis exists in this pipeline is
`asset_provenance.tlp` (migration 154, consumed via `cell_adapter.py`, `TLP_VALUES = {"white",
"green", "amber", "red", "black"}`) — a **different** table, reachable only through
`apps/backend-rag/backend/services/mata_garuda/cell_adapter.py`, not through Intel Lake's own
API (`routers/intel_lake.py`) at all.

Practical consequence for whoever builds Packet 05 for real: today, nothing stops a producer
from POSTing MATA-GARUDA-sourced OSINT content as an ordinary `intel_items` row via
`POST /api/intel/lake/observations` (the only server-side rejection is a 50KB payload-size cap
and a static bearer token — `intel_lake_service.py:57`, `intel_lake_router.py`
auth dependency) — the boundary is enforced entirely by *which producer chooses to call which
endpoint*, not by any structural constraint in the receiving schema. A `classification.
sensitivity` field cannot be retrofitted onto Intel Lake as a courtesy default; it needs to be a
`NOT NULL` column with the producer required to declare it, or the gap this paragraph describes
persists unchanged regardless of how rich the new object model is upstream.

## 4. What this session did and did not touch, in service of the boundary

- **Did**: read code, comments, migration DDL, and two `CLAUDE.md` files. Ran aggregate-only
  SQL (attempted; the query tool failed before returning any result — see UNKNOWNS.md §1, so in
  practice **zero rows of any kind, aggregate or otherwise, were read from any live Intel
  Lake/MATA GARUDA table this session**).
- **Did not**: read any `raw_payload` JSONB content, any `intel_items.title`/`summary` value, any
  `asset_provenance` row, any MATA GARUDA Redis stream entry, or any file under a `.gitignore`d
  MATA GARUDA data directory (`apps/mata-garuda/CLAUDE.md` §"OSINT blindato" lists these as
  blindato-by-design; this bundle's grep/read commands were scoped to tracked source files only
  — no `feedback/`, `logs/`, or gitignored data path was opened).
- **Did not** call any external LLM (cloud or local) with any content from this pipeline. This
  entire bundle was produced by direct file reads and greps against tracked source, not by
  summarization of retrieved content through a model.

## 5. Standing requirement for the eventual build (not this lane's job to close, but its job to name)

Any real Packet-05 implementation needs, at minimum, before shadow-writing a single MATA
GARUDA-sourced `IntelEvent` into `research_os_objects`:

1. A `classification.sensitivity` value assigned by the **producer**, not inferred downstream —
   consistent with the frozen contract's own declared limit (`intel_event.py:64-75`, read this
   session: "That responsibility belongs to whichever component assigns
   `classification.sensitivity` in the first place... not to this structural validator").
2. A hard rule (test, not just a docstring) that any event whose producer is a MATA GARUDA agent
   defaults to `restricted_osint` unless explicitly and auditably downgraded — mirroring the
   `apps/mata-garuda/CLAUDE.md` default of `tlp DEFAULT 'red'` (already flagged in
   `cell_adapter.py`'s own docstring as "a *safe default*, NOT enforcement").
3. Confirmation (not assumed here) that the eventual object-storage backend for
   `DurablePayloadReference.uri` (`https://` or `s3://` only, per `intel_event.py:110`'s pattern)
   is Tigris (this repo's existing S3-compatible store, per the `tigris` skill) and not a bucket
   reachable outside the OSINT-blindato boundary — this bundle did not verify Tigris bucket ACLs
   and does not claim to.
