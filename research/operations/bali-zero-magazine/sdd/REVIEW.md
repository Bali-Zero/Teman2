---
date: 2026-07-21
adversarial_review: kimi
---

# Umbrella adversarial review — Bali Zero Magazine SDD task reports

## Adversarial review

- **Generator:** Codex/Sonnet fleet (the SDD task reports and the magazine
  implementation were produced by that fleet).
- **Grader:** Kimi (this review; independent seat, != generator).
- **Scope:** umbrella spot-check of the seven SDD task reports in this
  directory (task-3, task-4, task-5, task-6, task-6-sites, task-7, task-8)
  against the actual PR diff (`origin/main...HEAD`, 171 files changed, ~56k
  insertions). This is explicitly **NOT a full review** of the ~300-file
  magazine feature: no test suites were executed, no runtime was started, and
  the majority of the diff was not read line by line. I read all seven reports
  in full and verified a selection of load-bearing claims directly against the
  code in this branch, citing file:line for each.

### Verified claims (spot-checked against the PR diff)

1. **Task 3 — audit chain domain separator.** The `BZM-AUDIT-EVENT-V1`
   domain separator exists and feeds the event-hash preimage.
   `apps/bali-zero-magazine/lib/server/audit-chain.ts:114` (`const DOMAIN_TAG =
   new TextEncoder().encode("BZM-AUDIT-EVENT-V1")`), consumed at
   `audit-chain.ts:242-243` in `buildAuditEventPreimage`.
2. **Task 3 — RFC 8785 canonical JSON for audit payloads.** A recursive
   canonical serializer (`canonicalValue`, `audit-chain.ts:129`) backs
   `canonicalizeAuditPayload` (`audit-chain.ts:231-233`), which is what the
   event hash and the stored `payload_json` use (`audit-chain.ts:240, 280`).
   The unit test pins byte-exact RFC 8785 JCS semantics (key ordering, `-0`
   normalization, unescaped non-ASCII) at
   `apps/bali-zero-magazine/tests/audit-chain.test.mjs:99-102`.
3. **Task 3 — replay accepts only the same packet ID plus manifest hash.**
   `checkReplay` (`apps/bali-zero-magazine/lib/server/publication-repository.ts:796-811`)
   re-reads the packet by ID and throws `replay hash mismatch for packet
   <id>` when the stored `manifest_hash` or `packet_kind` differs; only an
   exact match returns replay.
4. **Task 3 — single D1 batch with CAS preconditions in finalization.**
   Edition finalization builds one statement list — story head CAS
   (`UPDATE stories ... WHERE story_id = ? AND current_version = ?`,
   `publication-repository.ts:1227-1237`), edition pointer CAS
   (`... WHERE singleton_id = 1 AND current_revision = ?`, lines 1238-1251),
   Breaking pointer CAS (lines 1252-1264), packet state transition gated on
   `publication_state = 'building'` (lines 1265-1274) — then executes all of
   it in one `db.batch(statements)` (line 1277) with per-statement
   change-count assertions (`assertChangedExactly`, line 1278) and rollback
   recovery on conflict (line 1280).
5. **Task 5 — HMAC binds the claimed fields.** `canonicalizeMachineSignature`
   (`apps/bali-zero-magazine/lib/server/hmac.ts:208-243`) signs exactly
   method, normalizedPath, contentType, bodySha256, timestamp, nonce, keyId,
   audience (plus sorted optional signed headers) — matching the report's
   list verbatim.
6. **Task 5 — R2 writes are immutable.** New canonical objects are written
   with the atomic create-only condition `onlyIf: { etagDoesNotMatch: "*" }`
   at `apps/bali-zero-magazine/lib/server/media.ts:440-444`; the existing-key
   path verifies and returns without a `put` (lines 436-439).
7. **Task 6 (Sites) — Ed25519 receipt verification.** The audit-anchor route
   calls `verifyAuditAnchorReceipt`
   (`apps/bali-zero-magazine/app/api/machine/audit-anchor/route.ts:31-34`),
   which imports the raw 32-byte registry key and verifies via Web Crypto
   Ed25519 (`audit-chain.ts:632-645`).
8. **Task 6 (Sites) — two-phase publication returns `promotion_blocked`.**
   The blocked response is emitted by the machine ingress at
   `apps/bali-zero-magazine/lib/server/machine-ingress.ts:187-193` and
   asserted by the route tests
   (`apps/bali-zero-magazine/tests/audit-anchor-route.test.mjs:192-198`).
9. **Task 7 — Notebook client is subprocess-exec, no shell.** The production
   `nlm` client uses `asyncio.create_subprocess_exec` with a fixed argv
   (`apps/zantara-media/zantara_media/magazine/research_runtime.py:87-92`),
   and the test double asserts no `shell` kwarg is ever passed
   (`apps/zantara-media/tests/magazine/test_research_runtime.py:754-755`).
10. **Task 8 — exactly five intent kinds, and the 4 KiB machine body cap.**
    The closed vocabulary `rerun_collector, rebuild_edition, quarantine_story,
    release_story, refresh_research_job` is enforced as a SQL CHECK in both
    the migration (`apps/bali-zero-magazine/drizzle/0006_operations_control_plane.sql:13`)
    and the Drizzle schema (`apps/bali-zero-magazine/db/schema.ts:884`).
    `OPERATIONS_MACHINE_MAX_BODY_BYTES = 4 * 1024` is defined at
    `apps/bali-zero-magazine/lib/server/machine-ingress.ts:107`.

### UNVERIFIED claims (not checked in this review — stated plainly)

- **All test-count and gate-output claims** in every report (e.g. "47/47",
  "124 passed", "160 passed", "85 passed in 1.76s", lint/typecheck/build
  exits). I did not install dependencies or run any suite; these are trusted
  from CI plus the generator's logs, not independently reproduced here.
- **Task 5 live `wrangler dev` smoke** (signed PNG upload → `201` then
  `200 replay` with pinned digests) — a historical runtime claim that cannot
  be re-derived from the diff.
- **Task 6 Python publisher internals** (durable outcome journal, `flock`
  serialization, pending/accepted receipt ledgers, Ed25519 receipt signing
  on the Pro side). I verified the Sites half of the handshake (claims 7-8)
  and the shared wire format, not the Python implementation.
- **DLP boundary claims** (Tasks 6, 7, 8: recursive key/value rejection,
  indeterminate-classifier quarantine, content-free failure receipts) — the
  DLP modules were not opened in this pass.
- **Task 4 presentation claims** (locked palette values, robots metadata,
  lead-placement selection) — not spot-checked; the front-page layer is
  lower-risk than the publication/crypto core I concentrated on.

### Objections raised

1. The reports make strong correctness claims whose only evidence is
   generator-run test output; none of it was reproduced by an independent
   runner in this review. Mitigation: CI on the PR runs the suites; the
   spot-check above confirms the *mechanisms* exist as described, which is
   the part test-counts alone cannot show.
2. The audit-anchor signed end-to-end smoke was admittedly not run against a
   real migrated D1 + secret bindings (task-6-sites report, Verification
   section) — the strongest form of that claim remains unproven in-repo.
3. No surviving objections against the verified mechanisms themselves; the
   code matches the reports' descriptions at every point I checked.

### Verdict

**PASS (spot-check).** Within the stated umbrella scope, every load-bearing
claim I probed (10/10, spanning publication CAS/replay, audit-chain crypto,
HMAC binding, R2 immutability, Ed25519 anchor verification, promotion
blocking, no-shell subprocess, closed intent vocabulary, body caps) is
accurately described by the reports and present in the diff at the cited
locations. Claims listed as UNVERIFIED are unverified, not contradicted;
they should be covered by CI execution, which this review deliberately did
not duplicate.
