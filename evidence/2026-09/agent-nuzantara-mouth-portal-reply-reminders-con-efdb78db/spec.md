# Portal reply reminders and client message email

## 1. Mandate

PORTAL-REPLY-REMINDERS-20260925, BLUE. Gear 3 due to additive message-source schema.
External Codex builder prepares; independent Claude Opus 5.5 xhigh gate and release owner.
Pro current worktree: /Users/nuzantara/nuzantara/.worktrees/mouth-portal-reply-reminders-contract.
Base: e0b18b8bac. Goal: reading a client message must not erase a reminder to reply; a manual team message must enqueue a generic client email.

## 2. Owned perimeter

Portal message router, notification service and message-source migration; team alert/query/API and thread invalidation; targeted tests; existing email integration and consumer only where required. No auth-policy changes, credentials, real client rows, actual test sends, memory writes or owner real-name attribution. Preserve other work.

## 3. Sibling contract

Retain current unread-count fields and assignment filtering. Add total_pending (conversation count) and pending_by_client to the same response. New client can fall back to the old unread payload during rolling deployment. Pending means a client message without a later manual team message, independent of read_at. Automatic profile/document/practice notices must be explicitly identified and cannot clear future pending replies. The historical inbound profile-update writer's non-email sent_by='portal' sentinel is excluded without modifying data. The historical limitation includes the rolling-replacement window while old automatic-notice producers remain active; release proof waits for every producer to replace. Other historical rows lack reliable source provenance; old automated team notices may count as replies. Do not invent a backfill or claim complete historical reconstruction.
Client-side unread banner stays unchanged. Team reminder remains visible, has a subtle reduced-motion-aware indicator, and clears only following a successfully saved manual reply. Preserve stale pending counts and visible retry on load failure. A failed pending lookup must fail the poll rather than return a successful unread-only payload: unread=0 must never erase a cached unanswered conversation. Legacy-payload fallback applies only when the backend does not yet expose pending fields.
Email uses the existing Brevo transport and sender Zantara <zantara@balizero.com>, generic copy and fixed portal link, no message contents or client names. A unique message-keyed outbox row is committed atomically with each manual reply. A dedicated consumer uses PostgreSQL claims and a two-minute lease, a stable UUID provider key, at most three provider attempts (including reclaimed leases), explicit accepted/rejected/uncertain outcomes, and no second email-audit retry owner. Keyed transport stays on Brevo and checks response success even on HTTP 200. After 14 minutes from first attempt, uncertain jobs stop for review because provider deduplication expires at 15 minutes; no indefinite exactly-once claim. The existing DISABLE_BACKGROUND_WORKERS switch remains authoritative and must be checked at release. Provider acceptance and actual inbox receipt are separate evidence. Sources: https://developers.brevo.com/changelog/2021/11/10 and https://tailwindcss.com/docs/animation .

## 4. Acceptance

Synthetic tests: read does not clear pending; automatic notice does not clear pending; manual reply clears earlier incoming messages; a later incoming message reopens; failed send retains pending; staff see only assigned clients. Email is enqueued only after successful manual message persistence and repeated delivery attempts do not deliberately enqueue duplicates. Existing portal tests, backend targeted tests, typecheck and build remain green. Browser fixture at mobile and desktop widths, reduced-motion respected. Prove deployed code and backend schema/consumer separately; no fake real email delivery claims.

## 5. Team

Root external builder; portal_notification_ground read-only investigator. Independent cross-family Claude reviewer and fresh BLUE final gate, both via subscription OAuth. Actual session IDs recorded when invoked. Release only by authorized Claude role.

## 6. Stop-loss

No calendar/token ceiling imposed by owner. One correction depth, suspend repeated same-cause failures. No paid API installation, no bypass of checks, no published-history rewrites.

## 7. Evidence and release

Evidence path from scripts/ci/evidence_paths.py: evidence/2026-09/agent-nuzantara-mouth-portal-reply-reminders-con-efdb78db/.
Bites: authorized workspace users retain an actionable unanswered-message reminder, and an independently running email consumer observes a persisted message notification.
No overlapping open PR paths in the initial 50-PR probe; leases inspected, native agents inspected. The initial remote-self mailbox probe failed; the corrected local probe succeeded with 93 session entries. No messages sent.
Scar antidotes: #2 prove downstream state, not producer logs; #5 dedicated worktree; #9 preserve consumers during schema rollout.

## Evidence-pack correction

The first local pack lint omitted changed-file inputs and therefore did not exercise the CRM-seat and Gear-3 council requirements. The release pre-push correctly stopped before publishing. Complete two genuine qualifying council reviews (Sol and Kimi K3 subscription), retain their timestamped journal, and attest the already synthetic/diff-only data boundary. No seat override or client-data exception. The corrected candidate must pass the exact contract preflight and a fresh BLUE final gate.

## CI bootstrap cure after PR7306

Required Backend Tests failed deterministically before tests: the fresh CI bootstrap and migrations_v2 did not create portal_messages, which production already has from legacy migration_031_client_portal.py. All three shards hit migration321 UndefinedTable; no rerun occurred. Auto-merge was disabled; nothing merged or deployed. Same-cause red count: 1.

The successor starts from refreshed origin/main 469c301f32. It adds only the canonical table and three index DDL statements to the CI bootstrap, after SQLModel create_all provides clients/practices. Production SQL321 and application code remain byte-identical. Acceptance is the exact CI setup sequence on an empty database, full apply-all, repeated bootstrap/apply-all with stable table OIDs, canonical indexes/FKs and unchanged321 checksum. PostgreSQL15 CI remains mandatory; local reproduction is PostgreSQL17.8. The actual CI failure is the regression gate, so no duplicate string-snapshot test is introduced.

Evidence erratum: the initial Kimi REWORK remains genuine. The earlier follow-up was a narrower stateless review, not an informed withdrawal; its initial findings were independently adjudicated by BLUE gate v3. New CI-cure council judgements are separately recorded and carry no claim to re-review unchanged runtime. The brief now scopes automatic-notice attribution to new writers after complete producer replacement.

## OpenAPI contract cure after PR7310

The release-owner cure spec /tmp/portal-reply-ci-openapi-pin-cure.md is the assigned bounded delta. PR7310 remains frozen and disarmed after required Backend Shard2 reported1failed/11444passed; all three PostgreSQL15 bootstrap and migration stages passed. This is a distinct original-candidate omission that was hidden before tests ran on PR7306. Regenerate schema.d.ts and its OpenAPI hash using npm run contract:visa-oracle, then repository Prettier. Exactly two generated properties are added in seven declaration lines; no runtime, generator, test or CI-bootstrap source changes. The expected pin is6593a8afa56c310de94a9edcabe785adea3366191a1e86ffc81f408cbf9599ef. If this same pin cause recurs, suspend and write a spec rather than another fix. Root receipt timestamps record receipt creation, not test start time.
