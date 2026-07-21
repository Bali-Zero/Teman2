# Task 6 publisher handoff: audit anchoring

Publication is a two-phase operation. A packet is staged first, its canonical
publication event is read from the Sites-owned audit feed, and the packet is
promoted only after Sites accepts a valid Ed25519 anchor receipt for that exact
event.

All three machine calls use the existing SIWC dispatcher admission and exact
raw-body HMAC protocol. Use `Content-Type: application/json`, sign the exact
request target, and use a fresh nonce for every call. Responses are private and
`no-store`.

## Required sequence

1. Upload and verify every canonical asset.
2. POST the closed publication packet to `/api/machine/publications/editions`
   or `/api/machine/publications/breaking`.
3. The first valid call stages the packet, appends its canonical publication
   event, and returns `409` with the following exact body:

   ```json
   {
     "ok": false,
     "error": "promotion_blocked",
     "operation": "edition.publish",
     "packet_id": "edition-2026-07-19"
   }
   ```

4. GET the Sites-owned feed at `/api/machine/audit-events/v1`. The GET has an
   empty raw body. Its query is closed and must contain each field exactly once:

   ```text
   stream_id=magazine-publication.v1
   after_seq=<unsigned decimal>
   checkpoint_hash=<lowercase 64-character SHA-256>
   limit=<1..100>
   operation=<edition.publish|breaking.publish>
   packet_id=<URL-encoded public packet id>
   ```

   The initial cursor is `after_seq=0` and `checkpoint_hash=` followed by 64
   zeroes. Later calls must use the exact `next_cursor` returned by Sites.
   A cursor hash that is not bound to the requested sequence fails closed.

5. Locate the exact `promotion_target`, verify the returned hash chain, create
   an anchor receipt, and POST it to `/api/machine/audit-anchor`.
6. Retry the identical publication packet. It returns `201 created`; later
   identical retries return `200 replay`.

The feed response is a closed `audit-feed.v1` object:

```json
{
  "schema_version": "audit-feed.v1",
  "stream_id": "magazine-publication.v1",
  "checkpoint": {
    "stream_seq": "0",
    "event_hash": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "head": { "stream_seq": "1", "event_hash": "<sha256>" },
  "events": [
    {
      "schema_version": "audit-event.v1",
      "stream_id": "magazine-publication.v1",
      "stream_seq": "1",
      "previous_event_hash": "<sha256>",
      "event_hash": "<sha256>",
      "payload": {
        "schema_version": "publication-operation.v1",
        "operation": "edition.publish",
        "packet_id": "edition-2026-07-19"
      }
    }
  ],
  "promotion_target": {
    "operation": "edition.publish",
    "packet_id": "edition-2026-07-19",
    "stream_seq": "1",
    "event_hash": "<sha256>"
  },
  "next_cursor": { "after_seq": "1", "checkpoint_hash": "<sha256>" },
  "has_more": false
}
```

The projection deliberately excludes internal event IDs, raw packet payloads,
credentials, and client data. Do not add them to logs, journals, or anchor
receipts.

## Anchor receipt contract

The POST body is closed at both levels:

```json
{
  "body": {
    "schema_version": "audit-anchor.v1",
    "anchor_id": "anchor-2026-07-19-0001",
    "stream_id": "magazine-publication.v1",
    "stream_seq": "1",
    "event_hash": "<feed event sha256>",
    "previous_anchor_hash": "<prior anchor sha256 or 64 zeroes>",
    "observed_at": "2026-07-19T04:00:00.000Z",
    "key_id": "publisher-2026-01"
  },
  "signature": "<unpadded base64url Ed25519 signature, 64 decoded bytes>",
  "anchor_hash": "<lowercase sha256>"
}
```

Canonicalize `body` with RFC 8785 JSON Canonicalization Scheme and encode it as
UTF-8. Sign this byte sequence:

```text
"BZM-AUDIT-ANCHOR-V1\0"
|| U64BE(length(JCS(body)))
|| JCS(body)
```

Compute `anchor_hash` over:

```text
SHA-256(
  "BZM-AUDIT-ANCHOR-RECORD-V1\0"
  || U64BE(length(JCS(body)))
  || JCS(body)
  || raw_64_byte_signature
)
```

An exact receipt replay returns `200 replay`. Reuse of an anchor identity,
sequence, hash, or previous-anchor link with changed content is a conflict and
persists the global promotion block. Invalid signatures, record hashes,
registries, and malformed authorized anchor attempts also fail closed.

## Retained key registry

Sites reads `AUDIT_ANCHOR_KEY_REGISTRY_JSON` from its Worker environment. The
registry is closed, explicitly versioned, and keeps both current and retained
verification keys so historical receipts remain verifiable:

```json
{
  "schema_version": "audit-anchor-key-registry.v1",
  "registry_version": "2026-07-19.1",
  "keys": [
    {
      "key_id": "publisher-2026-01",
      "public_key": "<unpadded base64url raw Ed25519 public key, 32 decoded bytes>",
      "not_before": "2026-01-01T00:00:00.000Z",
      "not_after": "2027-01-01T00:00:00.000Z",
      "status": "active"
    }
  ]
}
```

Rotate by publishing a new registry version and retaining the old public key
with status `retained` until every receipt in its validity interval no longer
needs verification. Never expose private key material to Sites.

## Persistence and failure semantics

The D1 migration creates immutable publication-to-event bindings, one anchor
head per stream, exact promotion permits, and a persistent singleton promotion
block. Receipt insertion, head advancement, exact-target permit creation, and
block clearing execute in one D1 batch. Unique stream-sequence and
previous-anchor constraints make concurrent forks fail closed. A permit is
bound to one operation and packet ID and is consumed after successful
promotion; an already-published exact replay remains idempotent.

Run these gates before handoff:

```bash
npm run typecheck
npm run lint
npm run test:unit
npm run build
```
