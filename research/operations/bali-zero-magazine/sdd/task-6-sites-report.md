---
adversarial_review: codex
adversarial_review_date: 2026-07-21
---

# Task 6 Sites audit-anchor ingress report

## Scope

Implemented the Sites-owned half of the publication audit-anchor handshake for
Bali Zero Magazine. No Python publisher files are part of this lane.

## Delivered

- Protected `POST /api/machine/audit-anchor` with dispatcher admission, exact
  raw-body HMAC verification, single body read, closed receipt parsing, private
  no-store responses, Ed25519 verification, and record-hash verification.
- Protected `GET /api/machine/audit-events/v1` with a closed, HMAC-bound query,
  exact checkpoint validation, canonical event-chain projection, explicit
  operation/packet target, and no raw event IDs or packet payloads.
- RFC 8785 canonical anchor body and byte-exact domain-separated signature and
  record-hash preimages.
- Closed, versioned `AUDIT_ANCHOR_KEY_REGISTRY_JSON` contract with active and
  retained raw Ed25519 public keys and validity intervals.
- Durable D1 publication-event bindings, anchor heads, exact-target promotion
  permits, and a persistent global promotion block.
- Atomic receipt/head/permit/unblock acceptance with uniqueness constraints for
  stream sequence and previous-anchor linkage.
- Two-phase edition and Breaking publication: stage and emit candidate, return
  `promotion_blocked`, accept the exact anchor, then promote on an identical
  retry. Published replays remain idempotent.
- Publisher handoff documentation at
  `apps/bali-zero-magazine/docs/task-6-audit-anchor.md`.

## TDD evidence

RED began with missing audit contract and route modules. GREEN is covered by
`tests/audit-anchor-route.test.mjs` and the updated machine-route integration
suite. The focused audit suite exercises admission/HMAC, cursor binding,
closed feed projection, exact-target unlock, replay/conflict behavior,
persistent blocking, registry retention, and leakage prevention.

## Verification

- `node --experimental-strip-types --test tests/audit-anchor-route.test.mjs`:
  9 passed, 0 failed.
- `node --experimental-strip-types --test tests/machine-routes.test.mjs`:
  15 passed, 0 failed.
- `npm run test:unit`: 122 passed, 0 failed.
- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `npm run build`: passed; the vinext manifest contains both audit routes.
- Production runtime smoke via `npm start` and the audit-feed URL returned the
  expected `401 unauthorized` with `Cache-Control: private, no-store`.
- A signed end-to-end production-runtime smoke was not run because the local
  runtime has no migrated D1 plus injected SIWC and secret bindings. The signed
  path is exercised end to end by the focused integration suite with SQLite
  D1 semantics and Web Crypto Ed25519.
- `git diff --check`: passed.

## Reuse review

The cryptographic wire format follows RFC 8785 JCS and the Cloudflare Workers
Web Crypto Ed25519 surface. No reusable in-repository audit-anchor ingress
existed; the implementation extends the existing audit-chain, machine-HMAC,
publication-repository, and runtime-binding primitives.

## Adversarial review

Codex challenged whether focused SQLite and Web Crypto tests establish
production-runtime readiness. They establish the signed protocol behavior, but
the missing migrated-D1 and injected-binding smoke remains a deployment risk.
The report already discloses that limitation; it survives review as a required
post-deployment verification.
