---
date: 2026-07-21
adversarial_review: exempt-execution-report-umbrella-spot-check-in-sdd/REVIEW.md
---

# Task 5 report: protected ingestion and authenticated media

## Outcome

- Added four protected machine POST routes for collector runs, morning editions,
  standalone Breaking publication, and raw image assets.
- Enforced separate Sites dispatcher admission and application HMAC checks. The
  HMAC binds method, normalized path, content type, exact raw-body digest,
  timestamp, nonce, key ID, audience, and the raw asset metadata header. The
  server consumes the original request body exactly once and records nonces
  atomically in D1.
- Added closed-schema parsing and idempotent D1 ingress. A new manifest returns
  `201`, an exact replay returns `200`, and changed-content or publication
  conflicts return generic `409` responses without internal identifiers.
- Added AssetUploadV2. Its signed manifest binds the exact source digest, byte
  count, MIME, dimensions, capture time, and provenance to the raw request.
  AssetUploadV1 is explicitly unsupported. Source identity is stored separately
  from canonical identity and every field participates in replay comparison.
- Added deterministic Worker-side canonicalization through
  `@cf-wasm/photon@0.3.7`: non-animated JPEG, PNG, and WebP are decoded, then
  re-encoded to browser-safe PNG. Only structural PNG chunks survive; XMP, ICC,
  C2PA, text, EXIF, compressed metadata, and other ancillary source chunks are
  discarded. Canonical bytes, digest, MIME, dimensions, and byte count are
  computed after re-encoding and persisted independently.
- The compatibility corpus accepts and canonicalizes representative XMP, ICC,
  and C2PA JPEGs plus zTXt, iCCP, and caBX PNGs. Active script metadata is
  accepted as source metadata but cannot survive in canonical bytes. CRC-correct
  malformed PNG and structurally plausible malformed JPEG/WebP payloads still
  fail closed at decode.
- Made R2 writes immutable. An existing canonical object is fully verified and
  replayed without a `put`; inconsistent existing bytes or metadata return a
  conflict without overwrite. New writes also use an atomic
  `etagDoesNotMatch: "*"` condition, then are read back and verified before the
  D1 asset row can become `verified`.
- Made provenance mandatory in `asset-upload.v2`: non-empty `alt_text` and
  `source`, nullable validated `source_url`, `rights_basis`, approved rights and
  usage, passed DLP and sanitization, and an approved perceptual-dedup verdict.
  Every field is persisted, included in replay comparison, and projected by the
  read model. Publication and media reads fail closed when any required
  attestation is absent or unsafe.
- Centralized the current asset-eligibility predicate and reused it in
  publication finalization, authenticated media resolution, and the visible
  provenance read model. It requires trimmed alt text and source credit, an
  approved non-unknown rights basis and rights decision, approved usage, passed
  DLP and sanitization, an approved dedup result, verified status, and the latest
  visibility/status overlays.
- Added D1 migration `0002_known_the_hand.sql`. Existing asset rows copy their
  prior canonical identity into the new source columns, while new uploads retain
  separate source and canonical manifests.
- Added an authenticated media route that derives the canonical R2 key from the
  D1 digest and MIME, rejects stored-key drift, and rechecks the current
  published-story association, latest visibility and asset overlays, provenance,
  R2 metadata, byte count, and byte digest on every request. Responses are
  `private, no-store`, `nosniff`, and same-origin CORP; raw R2 keys are never
  returned.

## TDD evidence

- RED: decode-regression tests exercised structurally plausible but undecodable
  JPEG, PNG, and WebP payloads before the decoder-backed validation existed.
- RED: immutability tests exposed the unconditional `put` path for existing
  content-addressed keys and required proof that inconsistent objects remain
  byte-for-byte unchanged.
- RED: provenance round-trip and read-model tests exposed placeholder values and
  missing D1 columns; canonical-key tests exposed trust in the stored `r2_key`.
- RED (second remediation): the focused command produced exactly two expected
  failures. A CRC-correct PNG `tEXt` script beyond byte 1,250 returned `201`, and
  post-publication `alt_text` drift left the media route at `200`.
- RED (final compatibility remediation): AssetUploadV2 corpus tests first failed
  because no canonicalization export existed. Route tests then exposed an extra
  D1 insert placeholder and legacy seed rows exposed the new source-column
  invariants.
- GREEN: the focused ingress/media suites cover valid and malformed
  three-format decode behavior, no-overwrite replay and conflict behavior,
  active PNG/JPEG/WebP metadata probes, full provenance round-trip, every
  eligibility-field drift, latest overlays, and canonical-key drift.
- GREEN (final compatibility remediation): deterministic corpus, route,
  no-overwrite, replay, publication, media, migration, and render tests pass with
  source and canonical digests kept distinct.

## Verification

- `node --experimental-strip-types --test tests/publication-repository.test.mjs tests/asset-upload-v2.test.mjs`:
  36 passed, 0 failed, including the legacy migration and Task 6 fixture.
- `npm test`: Vinext production build passed; 109 tests passed, 0 failed.
- `npm run lint`: passed with zero diagnostics.
- `npm run typecheck`: `tsc --noEmit` passed with zero diagnostics.
- `npx --no-install prettier --check <changed files>`:
  all changed app files use Prettier style.
- `npm run db:generate`: reported `No schema changes, nothing to migrate`.
- `git diff --check`: passed.
- Local D1 applied migrations `0000`, `0001`, and `0002`; then
  `wrangler dev --config dist/server/wrangler.json --port 8792 --local` served
  the real `/api/machine/assets` route. A signed source PNG returned `201`
  with canonical PNG digest
  `eb52dccdcd43a07c59b48944e7dfba6061dc8cdbf9b1d201f10da76cb2a858a3`;
  a second request with the identical manifest and a fresh nonce returned
  `200 replay` with the same digest. The source digest remained separately
  bound as
  `431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460`.

`@cf-wasm/photon` publishes separate Node and `workerd` implementations. The
Node compatibility corpus and the signed Workerd route proof both exercise the
decoder and deterministic PNG encoder.

No Python asset producer exists in this worktree. Task 6 now has a closed JSON
fixture and publisher handoff at
`apps/bali-zero-magazine/docs/task-6-asset-upload-v2.md`: sign the source
manifest and bytes, require the canonical digest from the upload response, and
use only that digest in publication packets.

## Preserved workspace state

The pre-existing `INDEX.md`, `README.md`, and `.husky/_` changes were neither
modified nor included in the Task 5 staging set.
