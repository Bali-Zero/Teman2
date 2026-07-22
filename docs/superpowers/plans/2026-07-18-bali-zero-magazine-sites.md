# Bali Zero Magazine Sites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and internally host the Bali Zero Magazine as a workspace-restricted OpenAI Site with automatic editorial ingestion from Nuzantara collectors, a Research room, and a guarded Operations room.

**Architecture:** A new Vinext application in `apps/bali-zero-magazine/` owns the internal reading and interaction surface, D1 publication state, and private R2 media. Pro remains the system of record and pushes sanitized, versioned, HMAC-authenticated packets through outbound-only routes; `apps/zantara-media/` owns packet construction, editorial ranking, morning/Breaking dispatch, reconciliation, and external audit anchoring.

**Tech Stack:** Next.js 16.2.6, React 19.2.6, Vinext 0.0.50, TypeScript 5.9, Cloudflare D1/R2, Drizzle ORM, Node test runner, Python 3.11, Pydantic 2, httpx, pytest.

## Global Constraints

- Site access is restricted by the Sites `custom` workspace policy; use `workspace_all` only if the operator explicitly intends the whole workspace.
- Browser identity comes only from `oai-authenticated-user-email`; there is no app-owned authentication stack.
- Pro-to-Sites machine routes require both SIWC dispatcher admission and raw-body HMAC verification.
- D1 and R2 contain only sanitized projections; raw OSINT, NotebookLM UUIDs, client identifiers, KTP, passport, NPWP, credentials, prompts, and model chain-of-thought are denied.
- Morning edition cutoff is 06:15 WITA with publish target 06:30 WITA; Breaking target is within 10 minutes of qualification.
- Breaking requires high/critical impact and either an official primary source or two independent resolved root sources for every material factual or numeric claim.
- Editorial media is private, authenticated, `no-store`, and rechecks rights plus current story visibility on every request.
- Publication uses immutable versions, packet-scoped staging, D1 `batch([...])`, compare-and-swap pointers, and no route reads staging rows.
- Operations actions are allowlisted intents executed on Pro; Sites never receives general shell, SQL, filesystem, LaunchAgent, or arbitrary URL capability.
- TypeScript and Python functions have explicit types; Python I/O is async and uses `httpx`; logging uses `logger`.
- Every task follows test-driven development and ends in an atomic conventional commit.

---

## File Structure

### Site application

- `apps/bali-zero-magazine/.openai/hosting.json` — logical D1/R2 bindings.
- `apps/bali-zero-magazine/app/` — Magazine, story, Research, Operations, and protected API routes.
- `apps/bali-zero-magazine/components/` — editorial layout and room-specific UI.
- `apps/bali-zero-magazine/db/schema.ts` — durable D1 schema.
- `apps/bali-zero-magazine/lib/contracts/` — versioned Zod-free runtime validators and TypeScript types.
- `apps/bali-zero-magazine/lib/server/` — authentication, authorization, HMAC, D1 repositories, publication, media, audit, and security headers.
- `apps/bali-zero-magazine/drizzle/` — generated migrations.
- `apps/bali-zero-magazine/tests/` — contract, repository, route, security, and rendered HTML tests.

### Pro publisher

- `apps/zantara-media/zantara_media/magazine/` — Pydantic contracts, adapters, ranking, composition, signed transport, reconciliation, research, operations, and audit anchoring.
- `apps/zantara-media/zantara_media/cli/magazine_publish.py` — morning and Breaking CLI entrypoint.
- `apps/zantara-media/tests/magazine/` — unit, contract, and mocked integration tests.
- `infra/launchagents/wrappers/bali-zero-magazine-publish.sh` — quota-independent deterministic dispatcher wrapper.
- `infra/launchagents/com.balizero.magazine.morning.plist` — daily morning dispatch after collectors.
- `infra/launchagents/com.balizero.magazine.breaking.plist` — frequent eligible-Breaking drain.

---

### Task 1: Sites scaffold and platform bindings

**Files:**

- Create: `apps/bali-zero-magazine/**` from the bundled Vinext starter
- Modify: `apps/bali-zero-magazine/package.json`
- Modify: `apps/bali-zero-magazine/.openai/hosting.json`
- Modify: `apps/bali-zero-magazine/app/layout.tsx`
- Test: `apps/bali-zero-magazine/tests/rendered-html.test.mjs`

**Interfaces:**

- Consumes: bundled Sites Vinext starter.
- Produces: buildable worker application with logical bindings `DB` and `MEDIA`.

- [ ] **Step 1: Initialize the app**

Run the Sites initializer once from the empty target:

```bash
mkdir -p apps/bali-zero-magazine
cd apps/bali-zero-magazine
/Users/balizero/.codex/plugins/cache/openai-bundled/sites/0.1.30/scripts/init-site.sh "$PWD"
```

Expected: dependencies install and no second `.git` directory is retained inside the monorepo.

If the initializer created `apps/bali-zero-magazine/.git`, first verify `pwd` is exactly the target and the parent worktree contains `.git`, then remove only that generated nested metadata directory so the app remains owned by the monorepo.

- [ ] **Step 2: Write the failing binding test**

Add to `tests/rendered-html.test.mjs`:

```js
test("declares magazine persistence bindings", async () => {
  const hosting = JSON.parse(
    await readFile(new URL("../.openai/hosting.json", import.meta.url), "utf8"),
  );
  assert.equal(hosting.d1, "DB");
  assert.equal(hosting.r2, "MEDIA");
});
```

- [ ] **Step 3: Run the test and verify failure**

Run: `cd apps/bali-zero-magazine && node --test tests/rendered-html.test.mjs`

Expected: FAIL because bindings are `null`.

- [ ] **Step 4: Configure the app**

Set `.openai/hosting.json` exactly to:

```json
{
  "d1": "DB",
  "r2": "MEDIA"
}
```

Rename the package to `bali-zero-magazine`, set `test:unit` to `node --experimental-strip-types --test tests/*.test.mjs`, set `test` to `npm run build && npm run test:unit`, remove the starter preview dependency after replacing its page, and set metadata title `Bali Zero Magazine` and description `Internal intelligence, research, and operations for Bali Zero.`.

- [ ] **Step 5: Verify scaffold**

Run: `cd apps/bali-zero-magazine && npm run build && node --test tests/rendered-html.test.mjs`

Expected: build succeeds and all tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/bali-zero-magazine
git commit -m "feat(magazine): scaffold internal Sites application"
```

### Task 2: Versioned contracts, identity, authorization, and HMAC

**Files:**

- Create: `apps/bali-zero-magazine/lib/contracts/publication.ts`
- Create: `apps/bali-zero-magazine/lib/contracts/collector.ts`
- Create: `apps/bali-zero-magazine/lib/server/identity.ts`
- Create: `apps/bali-zero-magazine/lib/server/authorization.ts`
- Create: `apps/bali-zero-magazine/lib/server/hmac.ts`
- Create: `apps/bali-zero-magazine/lib/server/security.ts`
- Test: `apps/bali-zero-magazine/tests/contracts.test.mjs`
- Test: `apps/bali-zero-magazine/tests/hmac.test.mjs`
- Test: `apps/bali-zero-magazine/tests/authorization.test.mjs`

**Interfaces:**

- Produces: `parseEditionPacket(raw: unknown): EditionPacketV1`, `parseStoryPacket(raw: unknown): StoryPacketV1`, `requireViewer(headers: Headers): Viewer`, `authorize(viewer: Viewer, permission: Permission): AuthorizationDecision`, and `verifyMachineRequest(request: Request, env: MagazineEnv): Promise<VerifiedMachineRequest>`.

- [ ] **Step 1: Write contract rejection tests**

```ts
test("rejects a packet containing raw OSINT", () => {
  assert.throws(
    () => parseEditionPacket({ ...validEdition, raw_payload: "secret" }),
    /unknown field raw_payload/,
  );
});

test("rejects an unsupported schema version", () => {
  assert.throws(
    () => parseStoryPacket({ ...validBreaking, schema_version: "story.v2" }),
    /unsupported schema_version/,
  );
});
```

- [ ] **Step 2: Implement closed contract parsers**

Define exact readonly TypeScript types for `ClaimV1`, `EvidenceRefV1`, `StoryVersionV1`, `StoryPacketV1`, `EditionPacketV1`, `CollectorRunProjectionV1`, and `AssetUploadMetadataV1`. Parsers must reject unknown keys, missing evidence for factual/numeric claims, malformed hashes, non-monotonic versions, and Breaking claims without a valid gate.

- [ ] **Step 3: Write identity and role tests**

```ts
test("defaults an authenticated workspace user to reader", async () => {
  const headers = new Headers({
    "oai-authenticated-user-email": "reader@example.com",
  });
  const viewer = await requireViewer(headers, testSecrets);
  assert.equal(viewer.role, "reader");
  assert.notEqual(viewer.actorKey, "reader@example.com");
});

test("revocation is effective on the next request", () => {
  assert.equal(authorize(operator, "ops:create", allowlistV1).allowed, true);
  assert.equal(authorize(operator, "ops:create", allowlistV2).allowed, false);
});
```

- [ ] **Step 4: Implement identity and authorization**

Normalize email, derive `actorKey = HMAC-SHA256(ACTOR_KEY_SECRET, normalizedEmail)`, discard raw email before audit persistence, default to Reader, and load Analyst/Operator membership from a server-only versioned allowlist on every request.

- [ ] **Step 5: Write HMAC negative tests**

Cover altered raw bytes, changed path, wrong content type, stale timestamp, repeated nonce, unknown key ID, wrong audience, and invalid signature. Assert each request is rejected before handler execution.

- [ ] **Step 6: Implement HMAC verification**

Canonicalize exactly:

```ts
export type MachineSignatureInput = Readonly<{
  method: string;
  normalizedPath: string;
  contentType: string;
  bodySha256: string;
  timestamp: string;
  nonce: string;
  keyId: string;
  audience: string;
}>;
```

Verify raw received bytes, a bounded timestamp window, constant-time signature equality, audience equality, and unique nonce insertion. Support current/next HMAC keys only.

- [ ] **Step 7: Verify and commit**

Run: `cd apps/bali-zero-magazine && npm run test:unit -- --test-name-pattern='contract|HMAC|authorization'`

Expected: all new tests pass.

```bash
git add apps/bali-zero-magazine/lib apps/bali-zero-magazine/tests
git commit -m "feat(magazine): add secure projection contracts"
```

### Task 3: D1 schema and atomic publication repository

**Files:**

- Modify: `apps/bali-zero-magazine/db/schema.ts`
- Create: `apps/bali-zero-magazine/lib/server/publication-repository.ts`
- Create: `apps/bali-zero-magazine/lib/server/audit-chain.ts`
- Create: `apps/bali-zero-magazine/drizzle/0000_magazine_core.sql`
- Test: `apps/bali-zero-magazine/tests/publication-repository.test.mjs`
- Test: `apps/bali-zero-magazine/tests/audit-chain.test.mjs`

**Interfaces:**

- Produces: `stageEdition(packet, manifestHash)`, `finalizeEdition(packetId)`, `stageBreaking(packet, manifestHash)`, `finalizeBreaking(packetId)`, `getCurrentEdition()`, `getPublishedEdition(id)`, `getCurrentStory(slug)`, `getActiveBreaking()`, and `appendAuditEvent(event)`.

- [ ] **Step 1: Write schema invariants tests**

Assert unique `(story_id, version)`, `(stream_id, stream_seq)`, packet ID plus manifest-hash replay semantics, a single current-edition head, a single active-Breaking head, and publication-state checks.

- [ ] **Step 2: Define D1 schema**

Create the entities from the approved design: source systems, collector runs, stories, story versions, claims, evidence, story-evidence links, editions, edition entries, Breaking pointer/entries, assets/status events, research jobs/results, operations intents/receipts, nonces, audit events/heads, release attestations, and audit-anchor receipts.

- [ ] **Step 3: Generate and inspect migration**

Run: `cd apps/bali-zero-magazine && npm run db:generate`

Expected: one migration with one SQL statement per prepared execution boundary and all required unique indexes/check constraints.

- [ ] **Step 4: Write publication fault tests**

```ts
test("a failed edition CAS exposes no staged row", async () => {
  await repository.stageEdition(packet, manifestHash);
  await assert.rejects(
    repository.finalizeEdition(packet.packet_id),
    /CAS conflict/,
  );
  assert.equal(await repository.getCurrentEdition(), null);
  assert.equal(await repository.getCurrentStory(packet.stories[0].slug), null);
});

test("standalone Breaking commits both heads or neither", async () => {
  await repository.stageBreaking(breaking, manifestHash);
  await repository.finalizeBreaking(breaking.packet_id);
  assert.equal(
    (await repository.getCurrentStory(breaking.story.slug))?.version,
    2,
  );
  assert.deepEqual(await repository.getActiveBreaking(), [
    breaking.story.story_id,
  ]);
});
```

- [ ] **Step 5: Implement staging and batch finalization**

Use prepared statements and one D1 `batch([...])`. Count all expected affected rows and CAS pointer updates; any mismatch returns a conflict and leaves the packet staging. Publication queries always include `publication_state = 'published'` and follow explicit heads.

- [ ] **Step 6: Implement byte-exact audit chaining**

Use RFC 8785 canonical JSON payload bytes, the `BZM-AUDIT-EVENT-V1` domain separator, big-endian lengths/sequences, raw 32-byte prior hashes, and lowercase 64-character D1 hashes. Update the event row and stream head in one tested batch.

- [ ] **Step 7: Verify and commit**

Run: `cd apps/bali-zero-magazine && npm run test:unit -- --test-name-pattern='publication|audit'`

Expected: all repository, concurrency, replay, and audit fixtures pass.

```bash
git add apps/bali-zero-magazine/db apps/bali-zero-magazine/drizzle apps/bali-zero-magazine/lib/server apps/bali-zero-magazine/tests
git commit -m "feat(magazine): add atomic D1 publication model"
```

### Task 4: Front Page Editoriale and story experience

**Files:**

- Modify: `apps/bali-zero-magazine/app/page.tsx`
- Modify: `apps/bali-zero-magazine/app/globals.css`
- Create: `apps/bali-zero-magazine/app/stories/[slug]/page.tsx`
- Create: `apps/bali-zero-magazine/app/editions/[editionId]/page.tsx`
- Create: `apps/bali-zero-magazine/components/magazine-shell.tsx`
- Create: `apps/bali-zero-magazine/components/front-page.tsx`
- Create: `apps/bali-zero-magazine/components/story-card.tsx`
- Create: `apps/bali-zero-magazine/components/evidence-drawer.tsx`
- Create: `apps/bali-zero-magazine/components/system-status-strip.tsx`
- Test: `apps/bali-zero-magazine/tests/magazine-render.test.mjs`

**Interfaces:**

- Consumes: repository read models.
- Produces: `/`, `/stories/:slug`, and `/editions/:editionId` protected editorial routes.

- [ ] **Step 1: Write rendered hierarchy tests**

Assert the homepage renders masthead, edition date, hero, Breaking strip when nonempty, five domain sections, curiosity rail, source-system status, partial/quiet labels, and no raw identifiers.

- [ ] **Step 2: Implement server-rendered protected shell**

Set `export const dynamic = "force-dynamic"`, require the workspace viewer, emit `private, no-store`, and render navigation for Magazine, Research, and Operations.

- [ ] **Step 3: Implement the selected editorial direction**

Use Playfair Display-style editorial hierarchy with a sober grotesk fallback, Bali Zero near-black/ivory/antique-gold palette, asymmetric newspaper grid, restrained rules, generous whitespace, and no generic dashboard-card chrome. The first viewport leads with the issue, not system controls.

- [ ] **Step 4: Implement story and archive routes**

Story pages show title, deck, why it matters, system contributors, claim-level evidence, amendment/supersession labels, and current visibility overlay. Edition archive pages resolve their immutable published revision while applying current quarantine and rights overlays.

- [ ] **Step 5: Verify and commit**

Run: `cd apps/bali-zero-magazine && npm run build && npm run test:unit -- --test-name-pattern='magazine'`

Expected: build and rendered hierarchy tests pass.

```bash
git add apps/bali-zero-magazine/app apps/bali-zero-magazine/components apps/bali-zero-magazine/tests
git commit -m "feat(magazine): build editorial front page"
```

### Task 5: Protected ingestion and media routes

**Files:**

- Create: `apps/bali-zero-magazine/app/api/machine/collector-runs/route.ts`
- Create: `apps/bali-zero-magazine/app/api/machine/publications/editions/route.ts`
- Create: `apps/bali-zero-magazine/app/api/machine/publications/breaking/route.ts`
- Create: `apps/bali-zero-magazine/app/api/machine/assets/route.ts`
- Create: `apps/bali-zero-magazine/app/api/media/[digest]/route.ts`
- Create: `apps/bali-zero-magazine/lib/server/media.ts`
- Test: `apps/bali-zero-magazine/tests/machine-routes.test.mjs`
- Test: `apps/bali-zero-magazine/tests/media-route.test.mjs`

**Interfaces:**

- Consumes: machine HMAC verifier and publication repository.
- Produces: idempotent machine ingress and authenticated media reads.

- [ ] **Step 1: Write route rejection tests**

Assert missing SIWC admission context, invalid HMAC, replayed nonce, invalid packet schema, oversized asset, bad magic bytes, animated media, SVG/HTML/XML, digest mismatch, and unverified asset references all fail closed.

- [ ] **Step 2: Implement machine publication handlers**

Read `await request.arrayBuffer()` exactly once, verify the raw bytes and signed digest, parse the closed schema, stage idempotently, finalize, and return `201`, `200 replay`, or `409 conflict` without leaking internal state.

- [ ] **Step 3: Implement asset upload**

Accept only non-animated JPEG/PNG/WebP up to 12 MiB, 8,192 pixels per dimension, 20 assets per packet, and the decoded-pixel ceiling. Derive `assets/sha256/<digest>.<ext>`, verify R2 read-back metadata, then mark the D1 asset row `verified`.

- [ ] **Step 4: Implement media serving**

Require authenticated viewer, published visible story association, current allowed rights/status, and matching digest. Emit `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`, and `Cross-Origin-Resource-Policy: same-origin`.

- [ ] **Step 5: Verify and commit**

Run: `cd apps/bali-zero-magazine && npm run test:unit -- --test-name-pattern='machine|media'`

Expected: positive fixtures pass and every negative fixture is rejected.

```bash
git add apps/bali-zero-magazine/app/api apps/bali-zero-magazine/lib/server apps/bali-zero-magazine/tests
git commit -m "feat(magazine): add signed publication ingress"
```

### Task 6: Pro editorial publisher and automatic cadence

**Files:**

- Create: `apps/zantara-media/zantara_media/magazine/contracts.py`
- Create: `apps/zantara-media/zantara_media/magazine/adapters.py`
- Create: `apps/zantara-media/zantara_media/magazine/ranking.py`
- Create: `apps/zantara-media/zantara_media/magazine/composer.py`
- Create: `apps/zantara-media/zantara_media/magazine/transport.py`
- Create: `apps/zantara-media/zantara_media/magazine/reconciler.py`
- Create: `apps/zantara-media/zantara_media/magazine/audit_anchor.py`
- Create: `apps/zantara-media/zantara_media/cli/magazine_publish.py`
- Modify: `apps/zantara-media/pyproject.toml`
- Test: `apps/zantara-media/tests/magazine/`

**Interfaces:**

- Consumes: sanitized outputs from Intel Lake, MATA GARUDA, Regulatory Watcher, NotebookLM health/insight manifests, and other registered collectors.
- Produces: `EditionPacketV1`, `StoryPacketV1`, `CollectorRunProjectionV1`, signed HTTP requests, reconciliation receipts, and Pro-local anchor ledger entries.

- [ ] **Step 1: Write Pydantic contract parity tests**

Load shared JSON fixtures and assert Python accepts/rejects exactly the same packets as TypeScript. Use `ConfigDict(extra="forbid", frozen=True)` on every model.

- [ ] **Step 2: Implement sanitized adapters**

Define one adapter per source system returning `list[StoryCandidate]` and `CollectorRunProjectionV1`. Strip denylisted fields before a candidate reaches the composer; log only public run IDs and counts.

- [ ] **Step 3: Write deterministic ranking tests**

```python
def test_official_high_impact_candidate_qualifies_breaking() -> None:
    result = score_candidate(official_high_impact_candidate)
    assert result.breaking_eligible is True
    assert result.breaking_reason == "official-primary"

def test_two_mirrors_of_one_wire_story_do_not_form_quorum() -> None:
    result = resolve_independence([mirror_a, mirror_b])
    assert result.independent_root_count == 1
```

- [ ] **Step 4: Implement composer**

Apply the deterministic score components from the spec, claim-level evidence mapping, root-source collapse, five-domain diversity caps, quiet/partial edition states, and readiness cutoff. Never pass private reasoning to the packet.

- [ ] **Step 5: Implement signed async transport and reconciliation**

Use one persistent `httpx.AsyncClient`, raw-byte SHA-256, nonce/timestamp/key/audience headers, idempotent packet IDs, exponential retry with jitter, and outcome-unknown reconciliation before retrying side effects.

- [ ] **Step 6: Implement external audit anchoring**

Verify D1 stream sequences/hashes, create byte-exact Ed25519 receipts, append them to a Pro-local durable ledger, and push the public receipt back to Sites. A mismatch raises a critical alert and blocks later release operations.

- [ ] **Step 7: Verify and commit**

Run: `cd apps/zantara-media && source .venv/bin/activate && pytest tests/magazine -q && ruff check zantara_media/magazine tests/magazine`

Expected: all tests pass and Ruff reports no errors.

```bash
git add apps/zantara-media
git commit -m "feat(media): publish automatic magazine editions"
```

### Task 7: Research room

**Files:**

- Create: `apps/bali-zero-magazine/app/research/page.tsx`
- Create: `apps/bali-zero-magazine/app/research/jobs/[jobId]/page.tsx`
- Create: `apps/bali-zero-magazine/app/api/research/jobs/route.ts`
- Create: `apps/bali-zero-magazine/app/api/research/jobs/[jobId]/route.ts`
- Create: `apps/bali-zero-magazine/components/research-workbench.tsx`
- Create: `apps/bali-zero-magazine/lib/server/research-repository.ts`
- Create: `apps/zantara-media/zantara_media/magazine/research_worker.py`
- Test: `apps/bali-zero-magazine/tests/research.test.mjs`
- Test: `apps/zantara-media/tests/magazine/test_research_worker.py`

**Interfaces:**

- Produces: sanitized asynchronous research jobs with modes `search`, `compare`, `timeline`, and `notebook_insight`.

- [ ] **Step 1: Write authorization and lifecycle tests**

Reader can view published evidence; Analyst can create jobs; Operator adds no extra research privilege. Job lifecycle is `queued -> claimed -> completed|failed|cancelled`, and raw NotebookLM output is never stored.

- [ ] **Step 2: Implement Research UI and API**

Render query, mode, scope, source filters, queued status, labeled synthesis, claim/evidence list, and explicit uncertainty. API stores only sanitized request/result projections and actor key.

- [ ] **Step 3: Implement Pro worker**

Poll outbound, atomically claim jobs, query only allowed local/NB sources, run DLP, map every factual/numeric result to evidence, and post a signed result or safe failure receipt.

- [ ] **Step 4: Verify and commit**

Run site Research tests plus `pytest tests/magazine/test_research_worker.py -q`.

Expected: lifecycle, authorization, redaction, and evidence tests pass.

```bash
git add apps/bali-zero-magazine apps/zantara-media
git commit -m "feat(magazine): add internal research room"
```

### Task 8: Operations room and guarded intents

**Files:**

- Create: `apps/bali-zero-magazine/app/operations/page.tsx`
- Create: `apps/bali-zero-magazine/app/api/operations/intents/route.ts`
- Create: `apps/bali-zero-magazine/app/api/operations/intents/[intentId]/route.ts`
- Create: `apps/bali-zero-magazine/components/operations-board.tsx`
- Create: `apps/bali-zero-magazine/lib/server/operations-repository.ts`
- Create: `apps/zantara-media/zantara_media/magazine/operations_worker.py`
- Test: `apps/bali-zero-magazine/tests/operations.test.mjs`
- Test: `apps/zantara-media/tests/magazine/test_operations_worker.py`

**Interfaces:**

- Produces: read-only system health for all roles and allowlisted Operator intents with durable receipts.

- [ ] **Step 1: Write intent security tests**

Assert Readers/Analysts cannot create intents; arbitrary command/URL/path fields are rejected; only `rerun_collector`, `rebuild_edition`, `quarantine_story`, `release_story`, and `refresh_research_job` schemas are accepted; revoked Operators cannot be claimed; duplicate idempotency keys return the original intent.

- [ ] **Step 2: Implement Operations board**

Show collector freshness, latest successful run, edition state, Breaking queue, research queue, failed intents, audit-anchor freshness, and sanitized error codes. Hide action controls unless current authorization allows them.

- [ ] **Step 3: Implement intent creation**

Persist actor key, effective role, authorization-policy version, typed parameters, idempotency key, reason, and expiry. Re-evaluate authorization before insert and never execute inside Sites.

- [ ] **Step 4: Implement Pro executor**

Use a fixed action-handler map, local journal, per-target fence, claim heartbeat, final pre-effect authorization attestation, and states `queued`, `claimed`, `running`, `succeeded`, `failed`, `cancelled_revoked`, and `outcome_unknown`.

- [ ] **Step 5: Verify and commit**

Run site Operations tests plus `pytest tests/magazine/test_operations_worker.py -q`.

Expected: authorization, idempotency, crash recovery, and outcome-unknown tests pass.

```bash
git add apps/bali-zero-magazine apps/zantara-media
git commit -m "feat(magazine): add guarded operations room"
```

### Task 9: Scheduling, deployed capability proof, and internal hosting

**Files:**

- Create: `infra/launchagents/wrappers/bali-zero-magazine-publish.sh`
- Create: `infra/launchagents/com.balizero.magazine.morning.plist`
- Create: `infra/launchagents/com.balizero.magazine.breaking.plist`
- Create: `docs/runbooks/bali-zero-magazine.md`
- Modify: `docs/AUTOMATIONS_REFERENCE.md`
- Test: `apps/bali-zero-magazine/tests/deployed-platform.test.mjs`

**Interfaces:**

- Produces: deterministic daily and Breaking automation plus a workspace-restricted hosted Site.

- [ ] **Step 1: Write wrapper and plist tests**

Assert absolute Pro paths, no Air-M5 heavy runtime, no secret values in arguments/logs, morning start after collectors, bounded timeouts, overlap prevention, and Breaking cadence.

- [ ] **Step 2: Implement schedules**

Morning wrapper verifies collector manifests, composes at 06:15 WITA, and targets publish by 06:30 WITA. Breaking wrapper drains qualified candidates frequently enough to meet the 10-minute objective. Both use Keychain/runtime secret lookup and structured logs without payload bodies.

- [ ] **Step 3: Run local build and full tests**

Run:

```bash
cd apps/bali-zero-magazine && npm run build && npm test
cd ../../apps/zantara-media && source .venv/bin/activate && pytest tests/magazine -q
```

Expected: all site and publisher suites pass.

- [ ] **Step 4: Execute Phase 0 capability proof**

Initialize D1/R2, deploy an inert probe version, configure `custom` workspace access, verify the effective policy with `get_site`, and test browser auth, D1 batch rollback/CAS, private R2 media, SIWC machine admission, raw-body HMAC, and nonce replay rejection. Do not broaden access on failure.

- [ ] **Step 5: Deploy the validated application**

Use the shared Sites deployment flow only after explicit operator approval for the workspace-visible version. Verify effective access again after deployment and return the internal Site URL.

- [ ] **Step 6: Run deployed acceptance tests**

Test authenticated/no-store headers, custom access denial, edition atomicity, Breaking atomicity, quarantine cascade, rights revocation, role revocation, audit anchors, morning partial/quiet rendering, Research lifecycle, Operations intent lifecycle, keyboard navigation, reduced motion, and mobile layouts.

- [ ] **Step 7: Commit**

```bash
git add infra/launchagents docs apps/bali-zero-magazine/tests
git commit -m "chore(magazine): schedule and document internal rollout"
```

---

## Self-Review

- **Spec coverage:** Tasks 1-5 cover Sites, identity, D1/R2, atomic publication, UI, media, and ingress; Task 6 covers all collector aggregation, morning/Breaking automation, lineage, ranking, reconciliation, and external anchoring; Tasks 7-8 cover Research and Operations; Task 9 covers automation, capability proof, access policy, deployment, and acceptance tests.
- **Privacy coverage:** denylist enforcement exists in both TypeScript ingress and Python adapters; no raw source or OSINT persistence is introduced.
- **Type consistency:** `EditionPacketV1`, `StoryPacketV1`, `CollectorRunProjectionV1`, story/version heads, active-Breaking revision, packet ID, and manifest hash use the same names across publisher and Site.
- **Failure coverage:** packet replay, CAS conflict, D1/R2 split, asset quarantine, rights revocation, worker crash, role revocation, and outcome-unknown states have explicit tests.
- **Placeholders:** the plan contains no deferred implementation markers; every task names concrete files, interfaces, commands, expected outcomes, and commits.
