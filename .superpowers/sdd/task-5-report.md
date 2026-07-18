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
- Added content-addressed R2 image storage for non-animated JPEG, PNG, and WebP.
  Upload validation enforces exact MIME, magic/container structure, digest,
  byte count, dimensions, 12 MiB size, 8,192-pixel dimensions, the independent
  decoded-pixel ceiling, and a real image decode through
  `@cf-wasm/photon@0.3.7`. Valid fixtures for all three formats decode, while a
  CRC-correct malformed PNG, a 17-byte SOF-only JPEG, and a structurally valid
  WebP with corrupt compressed payload all fail closed.
- Made R2 writes immutable. An existing canonical object is fully verified and
  replayed without a `put`; inconsistent existing bytes or metadata return a
  conflict without overwrite. New writes also use an atomic
  `etagDoesNotMatch: "*"` condition, then are read back and verified before the
  D1 asset row can become `verified`.
- Made provenance mandatory in `asset-upload.v1`: non-empty `alt_text` and
  `source`, nullable validated `source_url`, `rights_basis`, approved rights and
  usage, passed DLP and sanitization, and an approved perceptual-dedup verdict.
  Every field is persisted, included in replay comparison, and projected by the
  read model. Publication and media reads fail closed when any required
  attestation is absent or unsafe.
- Added D1 migration `0001_thick_virginia_dare.sql`. Existing rows are migrated
  with explicit legacy defaults (`unknown`, `pending`, and `unreviewed`) so they
  cannot become publication-eligible accidentally.
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
- GREEN: the focused ingress/media command below passes all 19 tests, including
  valid and malformed three-format decode coverage, no-overwrite replay and
  conflict behavior, full provenance round-trip, and canonical-key drift.

## Verification

- `node --experimental-strip-types --test tests/machine-routes.test.mjs tests/media-route.test.mjs`:
  19 passed, 0 failed.
- `npm test`: Vinext production build passed; 101 tests passed, 0 failed.
- `npm run lint`: passed with zero diagnostics.
- `npm run typecheck`: `tsc --noEmit` passed with zero diagnostics.
- `npx --prefix apps/bali-zero-magazine --no-install prettier --check <changed files>`:
  all changed app files use Prettier style.
- `npm run db:generate`: reported `No schema changes, nothing to migrate`.
- `git diff --check`: passed.

`@cf-wasm/photon` publishes separate Node and `workerd` implementations. The
Node unit suite exercises the same decoder API, while the Vinext production
build verifies that the Worker export bundles successfully.

No Python `asset-upload.v1` parser or producer exists in this worktree
(`rg -n "asset-upload\\.v1" --glob '*.py' .` returned no matches), so there was
no Python implementation to patch. The TypeScript contract is the current
single source of truth; any future Python producer must supply the complete
required provenance projection before integration.

## Preserved workspace state

The pre-existing `INDEX.md`, `README.md`, and `.husky/_` changes were neither
modified nor included in the Task 5 staging set.
