# Journal local read contract — Track A

Status: implemented and locally verified; production remains unarmed. The current Website loader continues to use the existing explicitly enabled fixture. It does not import this transport. No production data, credential, access policy, route, deployment binding, or publishing operation was changed.

## Scope and interfaces

All work belongs to the existing worktree /Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro on branch codex/website-pro-continuation, based on b740b2cc3e94b1a46c9e9811bb369289fc21ea3d plus the inherited overlay. Other site edits are outside this Track A receipt.

- Magazine contracts/website-read.ts defines the local v1 envelope, approved v2 article shape, bounded media descriptor, strict public text/date/URL validators, and path/signature construction.
- Magazine server/website-read-authority.ts exports readWebsiteSnapshot(db, approval), publicApprovalDigest(publicProjection), and createLocalWebsiteReadAuthority(options). Its only database interface is prepare().first(); it never writes the publication database.
- Magazine server/verified-media-bytes.ts extracts the existing storage descriptor, metadata and digest verification without changing their behavior. Existing media.ts imports these helpers; its public exports and publication/media resolver behavior remain intact.
- Website src/lib/server/magazine-transport.ts exports createLocalMagazineTransport(options), returning read() and serveMedia(request). It is an unarmed Node factory using node:crypto and an explicit server-only import marker; it is not a registered Next route.
- Website vitest.architecture.config.ts maps server-only to the installed Next server implementation only inside these Node architecture proofs.
- proofs/architecture/magazine/http-fixture.ts supplies deterministic SQLite/R2 data and two ephemeral loopback HTTP listeners. Tests close both listeners and their in-memory database.

The factories require mode=local-proof, exact http://127.0.0.1 origins with ports, and an ephemeral key injected through server-side options. Public responses remain provenance=fixture and canonicalAccess=unverified. The local authority serves /v1/edition and scoped /v1/story-media/{slug}/{version}/{digest}?snapshot={digest}. The Website mediator exposes only the corresponding /api/journal-media path on its own origin. There is no arbitrary URL proxy or public digest-only lookup.

## Evidence-supported guarantees

### Consistent publication read

One prepared SELECT joins the actual Magazine current edition pointer, edition entries, current story versions, latest quarantine events, published claim/evidence links, revision history and latest asset eligibility. The fixture uses the real migration schemas and actual repository stage/finalize operations. A historical edition placement cannot revive an older current story. Duplicate placements are deduplicated. Building outputs are not published output. Missing current records, missing placements, invalid dates, superseded current heads and inconsistent pointers fail closed. Valid empty, unpublished, withdrawn, malformed and unavailable results remain distinct.

The snapshot digest includes the captured authority pointer and observed visibility/asset-status sequences. A later observed withdrawal, rights revocation, amendment or finalized edition change invalidates previous scoped image URLs. The tests explicitly preserve an already captured statement result across a later mutation and require the next read to observe that mutation.

This proves local SQLite statement behavior against the canonical schemas. It does not prove live D1 runtime parity, multi-query transaction semantics, database-plus-R2 atomicity, universal freshness, immediate revocation of already delivered responses, or recall of an already open page.

### Authentication and public projection

The local transport reuses Magazine's existing HMAC request contract: method, exact path/query, content type, body digest, timestamp, nonce, key identifier and intended audience. The authority keeps a bounded ephemeral nonce store. Requests with missing/invalid/expired/replayed credentials fail before database access. The proof HTTP adapter rejects non-GET requests and unexpected GET body framing before constructing a Fetch Request; the authority also rejects such framing.

Responses are authenticated against the exact current request nonce, path, status, MIME and bytes. The Website enforces the declared and observed size bounds, timeout, exact origin, required media security headers and no redirects. No stale or demo fallback is used after transport failure; exception text is never serialized.

Origin approval alone does not release text. PublicReadApproval contains explicit digests of independently reviewed exact article projections, including all public prose, canonical URL, evidence publisher/citation/URL and revision dates. The deterministic test approvals are hand-authored synthetic records, not derived from a database read. Changed prose or a private-looking path at an approved origin is rejected unless that exact projection is separately approved. Schema checks reject controls/markup, unsupported shapes, unsafe URL credentials/query/fragment and unapproved origins. This is exact projection approval, not a semantic PII detector; a future approval process must review the content it authorizes. Internal claim IDs, root IDs, notes, source fields, jobs and exceptions are absent from the public envelope.

### Media bytes and delivery

Eligibility uses Magazine's existing assetEligibilitySql predicate, including the latest status/rights events. A separately approved media descriptor binds the precise digest, dimensions, byte count, MIME, alt text, slug and current version. Storage reads use only the canonical assets/sha256/{digest}.png key. The shared existing verifier checks object key, object size, MIME, exact metadata, actual byte count and actual SHA-256. After the asynchronous object read, the authority reads a new statement snapshot and suppresses bytes if that state or approval changed.

The Website checks the returned bytes again against the descriptor and PNG signature/IHDR dimensions, rejecting SVG content even when its database MIME and approved digest say PNG. The positive fixture is the existing Magazine 1x1 PNG test image. Delivery is mediated on the Website origin with no-store, Cross-Origin-Resource-Policy: same-origin and nosniff. This resolves the local browser-origin delivery design without claiming the Magazine's same-origin-only public media URL can be embedded cross-origin.

This reader does not perform a complete PNG decode or re-encode. That remains the original ingest responsibility. The worktree lacks @cf-wasm/photon; the existing media resolver regression executes its actual module with a narrowly stubbed unused encoder, not a Photon ingress test. Full decoding, browser raster rendering and production storage/CDN behavior were not demonstrated by this Track A suite. There is also a final response-delivery race after the last state check; no distributed snapshot or absolute recall guarantee is asserted.

### Actual consumer and canonical route proof

The actual Website transport begins with an explicit server-only import. A bounded negative proof transpiles that actual module and resolves the marker through the installed Next createServerOnlyClientOnlyAliases(false) map; the installed client guard throws before any transport dependency is evaluated. The corresponding installed server alias loads. Installed Next documentation and implementation define this marker as a client-import build error. This proves the installed guard semantics and source marker, not a separate full negative Next client build.

The happy path travels through two real local HTTP listeners, request/response authentication and the Website's existing readMagazineFeed v2 decoder, then renders the existing JournalIndex. It demonstrates current amended version 2 with dated history, evidence, no-image fallback, scoped mediated PNG bytes and unavailable states. It does not wire the current preview loader to this new factory.

Canonical access is tested only through a deterministic local public-route simulation. The test executes the actual Magazine story page module's generateMetadata function and its notFound path, replacing the read model with its actual getCurrentStory repository contract. A published current story returns matching title/canonical metadata; withdrawn, building and missing stories return 404. Next dispatch, middleware, the complete read model and production host admission were not exercised. Production canonical links remain unverified and fixture links remain inert in the rendered Journal.

## Verification and review handoff

Commands were executed with cwd=/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro:

- npm --prefix apps/website run test:architecture -- magazine-transport.test.tsx — 46/46 passing; latest run 11.75 seconds. The wrong-audience HTTP test preserves the valid content-type so the rejection isolates audience validation.
- npm --prefix apps/website run typecheck — exit 0 after the explicit server-only marker and guard proof changes.

The 46 cases include current amendments, authenticated HTTP, GET framing, wrong audience/path, replay, single-statement reads, withdrawal/rights/public-approval races, finalized quiet edition transition, stale superseded pointer, missing records, invalid timestamps, building claims/evidence, exact public approval, unsafe source URLs, empty/unpublished/withdrawn distinctions, storage key/MIME/digest changes, arbitrary lookup rejection, SVG rejection, existing media resolver compatibility, canonical metadata/notFound simulation, signed-response tampering, redirects, size/truncation failures, timeout/no-leak behavior and the installed Next server-only client guard.

The independent reviewer owns its own execution/verdict. Its result is not self-certified here. The source/test byte receipt is journal-contract-receipt.json in this directory. Shared Website build and full-site checks belong to the parent review.

## Before any production proposal

Production activation is a separate authorized change. It would require an explicit server route/loader integration with the existing server-only marker retained and its real integration verified; production-grade key delivery/rotation and replay admission; independently approved public projections and media bytes with a revocable approval lifecycle; live D1 schema/query/runtime validation; production canonical route admission checks; a complete existing ingress decode/rights verification path; and measured Website-origin media cache/CORP/CDN behavior. Any chosen freshness objective must be scoped to what the deployed read/revalidation path can actually prove. None of these prerequisites is configured or implied by this local proof.
