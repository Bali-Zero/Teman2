# Independent Journal read-boundary review

Date: 2026-09-07 WITA. Status: **PASS for the bounded local development proof**.

Reviewer: `/root/local_transport_consumer`, a separate Codex agent from
`/root/magazine_producer`, who authored the reviewed server/contract changes.
The reviewer authored the unrelated bounded Services/Team/home/404 UI changes.
This is an independent code and local-test review of Track A, not an independent
Claude visual review, production admission review or deployment authorization.

Worktree: `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`.
Expected branch: `codex/website-pro-continuation`.
No server implementation, authentication policy, production credential, loader
or fixture was changed by this reviewer. Review artifacts stay in this directory.

## Scope and current decision

The new work is an explicitly local proof: Magazine authority factory → two
actual loopback HTTP surfaces → Website transport factory → the existing v2
decoder and Journal renderer. It is not attached to the default Journal loader
or a production/public server route. Current R19 preview remains the existing
explicit fixture until the separately coordinated rebuild.

The independent review found a concrete HTTP framing gap and required an explicit
framework server-only boundary. Both were corrected by the author, reread by the
reviewer and exercised by the final independent 46-test run. The 15 reviewed
source/config files remained byte-identical before and after that run. No open
blocking finding remains within this local scope. No production enablement is
approved by this review.

## Finding and follow-up

**BR-1 — CLOSED: Local HTTP adapter discarded incoming request bytes.** The first
`httpSurface` implementation constructed a bodyless Fetch Request for incoming
Node HTTP requests. A request signed for an empty GET could arrive with a
one-byte body while the authority observed an empty body, weakening the claim
that the actual HTTP proof binds exactly the bytes received. Existing HMAC
body validation itself was not the cause. This is a local test-adapter issue;
there is no new production adapter attached.

The corrected adapter rejects Transfer-Encoding and any present Content-Length
other than `0` before constructing the Request, with a matching authority
admission check. Actual Node HTTP tests send fixed-length and chunked signed GET
bodies: the adapter returns 400 before invoking the handler; the direct authority
returns 401 for framed requests. The final independent run passed these tests.

Additional requested negatives now pass: modified current-response bytes retaining
the original signature, wrong audience/path, declared oversize, truncation and
missing length. The wrong-audience test includes the otherwise valid content type
and HMAC headers, so rejection is not caused by an unrelated missing MIME header.

**BR-2 — CLOSED: Explicit server-only misuse barrier.** The initial transport
relied on Node imports and file naming without an explicit Next marker. It now
starts with `import "server-only"`. The proof environment alone aliases that
marker to installed Next’s server empty module. A negative test transpiles the
actual transport and resolves its first import with installed Next 16.3.1’s
`createServerOnlyClientOnlyAliases(false)`: the client error module throws before
any transport dependency executes. The positive server alias loads successfully.
The reviewer read the installed data-security guide and compiler/webpack alias
implementation. This is an installed compiler-alias guard-semantics proof, **not
a complete negative Next client build**.

## Source findings

| Boundary | Observed implementation | Limit of the conclusion |
| --- | --- | --- |
| Local admission | Both factories require `local-proof`, exact HTTP loopback origin with explicit port, and a 64-character hexadecimal key. No public host configuration is accepted. | Loopback is a development boundary, not production authentication architecture. |
| Request authentication | Existing HMAC binds method, normalized path/query, MIME, body digest, timestamp, nonce, key ID and audience. The read authority uses a separate audience, bounded key validity and 30-second skew. | The proof adapter now rejects unsupported body framing; see closed BR-1. |
| Replay | Authority uses a bounded 2,048-entry in-memory nonce map and consumes authenticated nonces once. | This is process-local. Restart and multiple authority instances do not share replay state; each proof creates a fresh ephemeral key. |
| Response binding | Response HMAC binds contract, request path/query, request nonce, HTTP status, MIME and exact body digest. Transport uses a new nonce and rejects redirects. | Does not add TLS or remote-host identity; all current transport is loopback. |
| Secret handling | Keys exist in factory options and temporary proof memory. Website returns only parsed public feed or verified bytes; no request signature headers are forwarded to public media responses. | The explicit Next `server-only` marker and installed client alias rejection are tested. The factory remains unwired; no production secret loading/rotation or live key integration was exercised. |
| Snapshot | One prepared SELECT captures current edition pointer/revision/state, current story versions, quarantine state, exact-version evidence links and current eligible asset descriptors. There are no writes in that statement. | Local SQLite migrations exercise consistency. Live D1 runtime/statement behavior and deployment parity remain unverified. |
| Public text | Exact keys, text/date/URL syntax, evidence and revision constraints are applied, then the full per-slug/per-version public projection must match an independently supplied approval digest. | Syntax validation is not PII detection. The digest authorizes reviewed bytes; an unsafe approval source would invalidate that guarantee. Proof approvals are handwritten synthetic records, not generated from the database read. |
| Evidence | Claims/evidence join on packet, story, version and claim ID; published links only. Public fields are publisher, citation and URL. HTTPS origin allowlisting is supplemented by the full projection digest, with query/fragment/userinfo rejection. | Origin or URL shape alone does not prove public accessibility, independent factual truth or legal accuracy. |
| Canonical identity | Canonical URL remains the existing Magazine `/stories/<slug>` identity. `canonicalAccess` is explicitly `unverified`; fixture provenance makes article links development-only and inert. | The local metadata simulation is not the deployed dispatcher/middleware/public-access stack, and no new duplicate article system is created. |
| Media selection | Existing asset eligibility SQL requires allowed rights basis, latest verified/approved rights state, publication/version association, usage/DLP/sanitization/dedup checks and alt/source metadata. Exact public descriptor/byte digest also needs approval. | A separately reviewed byte digest is essential; a database status alone does not establish safe image content. |
| Stored bytes | Shared existing verifier checks canonical storage key, size, MIME, exact custom metadata and byte hash. The extraction from `media.ts` preserves the checks. | Real R2 and the original Photon ingress decoder are outside this local proof. |
| Media mediation | Only a current snapshot's exact story/version/digest path is accepted; authority rechecks a new snapshot after asynchronous object retrieval. Website verifies byte count/hash and PNG signature/IHDR dimensions. | Header/dimension checks are not a complete PNG decoder. The proof serves an exact reviewed raster. It does not validate newly ingested arbitrary images. |
| Revocation/cache | Observed later withdrawal/rights/approval changes invalidate the snapshot URL; responses use no-store, same-origin CORP and nosniff, without CORS permission. | A change after the final check or bytes already delivered cannot be recalled. There is no DB-plus-object-storage distributed transaction, global cache purge or zero-race claim. |
| Existing consumer | Transport calls `readMagazineFeed` v2 before attaching only validated same-origin media. Signed terminal states are retained; transport failures return unavailable with no stale/sample fallback. | Network/envelope/signature failures deliberately collapse to unavailable; application-level signed malformed state remains distinct. |

## Executed independent checks

- Existing HMAC tests: `node --experimental-strip-types --test tests/hmac.test.mjs`
  from `apps/bali-zero-magazine`: **14 passed, 0 failed**, 519ms. This includes
  raw bytes, method, path, content type, audience, current/next key validity,
  timestamps and atomic concurrent nonce insertion.
- Source review read the new contract/authority/transport/verifier, the complete
  new test/helper, existing HMAC/security/asset-eligibility/decoder interfaces,
  and the actual `media.ts` extraction diff.
- Frozen HTTP proof: `npm run test:architecture -- proofs/architecture/magazine-transport.test.tsx`
  from `apps/website`: **46 passed in 1 file**, 1.83s, exit 0. Started
  `2026-09-06T19:05:57.025Z`, finished `2026-09-06T19:05:59.350Z`.
  All 15 selected source/config files matched before and after execution.
  Exact hashes and command metadata: [boundary-evidence.json](boundary-evidence.json).
  Complete captured output: [boundary-tests.log](boundary-tests.log).
- Existing Journal loader, visual fixture, decoder and JournalIndex hashes also
  match the previous 224-entry checkpoint manifest exactly. This proof does not
  silently attach the new factory to the default UI.
- The Vite native config-loader future compatibility notice was nonfatal.
  Shared full-suite/build/typecheck and rebuilt browser validation are separate
  integration gates, authorized after this review; this verdict does not claim
  they have already run.

## Required interpretation at handoff

PASS means this bounded local development proof behaves as tested.
It does not mean production readiness, deployed canonical access, approval of
new legal/editorial claims, live D1/R2 parity, image ingress validation, durable
cross-process replay protection, or authorization to attach credentials and
publish the factory. Current loader and original visual fixture remain intact.
