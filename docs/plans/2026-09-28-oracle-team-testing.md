# VISA ORACLE INTERNAL TEST CAMPAIGN

Approved outcome: a simple online Kita dashboard, not a local-only form. BLUE external builder prepares; independent Claude review and release owner remain required. No Oracle rule changes or stopped product-count investigation.

## INTEGRATION

Route: `/intelligence/visa-oracle/testing` beneath the existing workspace/session gate. Reuse Kita R19 primitives and the same-origin API client. Existing Visa Oracle intelligence page reviews regulatory updates, not tests; add a link and preserve it. Existing feedback stores conversation ratings; existing intake review contains client documents. Neither is a suitable test record store.

Use the current JWT/session dependency plus active human staff verification in `team_members`. Two focused PostgreSQL tables: six configurable tester slots and one immutable-expectation execution record per assignment. No client records are accessed. Owner configures staff identities and reviewers; no roster inferred from Portal Champions. Review cannot approve the reviewer's own test. The current global intake gate is preserved.

## CAMPAIGN AND WORKFLOW

28 September–2 October 2026, Asia/Makassar; six slots; five assigned cases daily; 25 per tester; 150 planned. One shared reference per day plus four controlled contrasting cases per slot is the proposed experimental allocation. This is a sample, not exhaustive legal/product coverage. Cases are synthetic and versioned; no prefilled legal gold answers.

Start records the expectation, its evidence basis, browser/device and observed version before the result form is enabled. Server timestamps the start and refuses expectation replacement. Tester saves a draft then submits exact steps, actual result, sources/uncertainty, an actionable comment, severity and certainty. One optional private PNG/JPEG/WebP evidence attachment or an evidence reference; no public marketing uploader. Submitted observations are immutable; their image can be removed with an audit marker if it was attached accidentally. Reviewer-testers cannot see peers' content until all five personal expectations for that day are locked. New cases can only start on their assigned Bali day, preserving date-sensitive fixtures. Review records a disposition and reproduction evidence. All counts derive from persisted records; blocked attempts are distinct from paths reaching a result. No accuracy score, prizes or automatic external sends.

## ACCEPTANCE

- 150 unique assignments, five per slot/day, shared references equal, contrasting profiles controlled.
- Anonymous, client, service-account and inactive staff rejected server-side; forged actor/slot cannot edit another tester; expectation replacement and self-review rejected.
- Drafts survive reload; idempotent identical submissions do not duplicate; conflicting submissions fail. Slot reassignment after work is prevented.
- Staff-only durable evidence; image type/size validated; no submitted payload in logs. Shared counters and review/export reflect server truth.
- UI renders in Bahasa Indonesia, handles failures without fabricated success, uses existing Kita components and leaves existing intelligence/Portal Champions behavior intact.
- Tests, independent review, migration dry-run and authorized deployment/live proof before claiming the requested online outcome delivered.

## REVIEW CORRECTION CONTRACT

The CI connection guard accepts only PostgreSQL URLs on localhost, 127.0.0.1 or postgres, with database nuzantara_test or its exact xdist worker derivative nuzantara_test_gw[0-9]+. Query/fragment overrides and all other databases/hosts are rejected. Acceptance must run the six real integration scenarios with xdist workers; a serial base-database pass does not satisfy this criterion.

Every tester locks all five personal expectations for a day before recording any result or opening the Oracle link in this dashboard. The API enforces this for drafts and submissions; the UI explains the two phases. Identical reviewer retries preserve the first review timestamp; a conflicting review remains rejected.

The authorized dates were 28 September–2 October 2026. Release missed the first two days, and on 30 September 2026 the owner rescheduled the campaign to three early mornings, 30 September–2 October, running the themes of days 1–3 (90 planned, 15 per tester); the day 4–5 fixtures stay in the generator for a later extension. Database storage does not hard-code those dates or campaign IDs; the application enforces the assigned plan. Slots remain configurable and unassigned until the owner supplies identities. If release misses the first day, rescheduling requires the owner's decision rather than fabricated completed tests. The staff testing window must be excluded or annotated when interpreting production funnel analytics.

Evidence images are decoded and re-encoded without EXIF/text metadata before storage, still bounded at 600 KiB. The purpose-prerequisite fixture declares its deliberately unmet investment condition and includes family sponsorship facts only for relevant branches.
