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
  decoded-pixel ceiling, and an atomic 20-assets-per-packet cap. R2 bytes and
  metadata are read back before the D1 row becomes `verified`.
- Added an authenticated media route that rechecks the current published story
  association, latest visibility overlay, latest asset status and rights, D1
  digest, R2 key metadata, and R2 byte digest on every request. Responses are
  `private, no-store`, `nosniff`, same-origin CORP, and declare the verified
  content type and length. Raw R2 keys are never returned.

## TDD evidence

- RED: the focused suite first failed on all missing route and resolver files.
- RED: route stubs then exposed missing manifest persistence, absent singleton
  migration seeds, invalid replay semantics, unbound asset metadata, and media
  overlay failures.
- GREEN: 17 focused ingress/media tests cover dispatcher admission, invalid
  HMAC, nonce replay, exact replay/conflict behavior, closed schemas, atomic
  edition/Breaking publication, unverified asset references, malformed and
  active media, animation, metadata/digest drift, R2 read-back failure,
  concurrent packet limits, authentication, quarantine/revocation, and current
  published association.

## Verification

- `npm test`: Vinext production build passed and all 99 unit tests passed.
- `npm run test:unit -- --test-name-pattern='machine|media'`: passed, 99/99 in
  the current Node runner configuration.
- `npm run lint`: passed with zero diagnostics.
- `npm run db:generate`: reported `No schema changes, nothing to migrate`; the
  scoped schema/migration diff SHA-256 remained identical before and after.
- `git diff --check`: passed.

Standalone `npx tsc --noEmit` still reports only the existing project-level
Cloudflare ambient-type, multiline `.ts` import-suppression, and Task 4
read-model diagnostics. Task 5's body type, import, and parser diagnostics were
removed; the production Vinext build is clean.

## Preserved workspace state

The pre-existing `INDEX.md`, `README.md`, and `.husky/_` changes were neither
modified nor included in the Task 5 staging set.
