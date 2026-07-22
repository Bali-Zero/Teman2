import assert from "node:assert/strict";
import {
  createHash,
  generateKeyPairSync,
  sign as signEd25519,
} from "node:crypto";
import { existsSync } from "node:fs";
import test from "node:test";

import {
  buildAnchorHashPreimage,
  buildAnchorSignaturePreimage,
  canonicalizeAnchorBody,
  decodeBase64Url,
} from "../lib/contracts/audit-anchor.ts";
import { machineSignatureHeaders } from "../lib/server/hmac.ts";
import { verifyAuditAnchorReceipt } from "../lib/server/audit-chain.ts";
import { runWithMagazineBindings } from "../lib/server/runtime-bindings.ts";
import {
  MACHINE_AUDIENCE,
  MACHINE_KEY_ID,
  MACHINE_SECRET,
  SqliteD1Database,
  breakingPacket,
  editionPacket,
  runtimeBindings,
  signedMachineRequest,
  storyVersion,
} from "./helpers/task-5-fixtures.mjs";

const ZERO_HASH = "0".repeat(64);
const STREAM_ID = "magazine-publication.v1";
const anchorRoutePath = new URL(
  "../app/api/machine/audit-anchor/route.ts",
  import.meta.url,
);
const feedRoutePath = new URL(
  "../app/api/machine/audit-events/v1/route.ts",
  import.meta.url,
);
const editionRoutePath = new URL(
  "../app/api/machine/publications/editions/route.ts",
  import.meta.url,
);
const breakingRoutePath = new URL(
  "../app/api/machine/publications/breaking/route.ts",
  import.meta.url,
);
const routesExist = [
  anchorRoutePath,
  feedRoutePath,
  editionRoutePath,
  breakingRoutePath,
].every(existsSync);

const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const publicJwk = publicKey.export({ format: "jwk" });
const KEY_ID = "pro-anchor-2026-07";

function bindings(db) {
  return {
    ...runtimeBindings(db),
    AUDIT_ANCHOR_KEY_REGISTRY_JSON: JSON.stringify({
      schema_version: "audit-anchor-key-registry.v1",
      registry_version: "2026-07-19.1",
      keys: [
        {
          key_id: KEY_ID,
          public_key: publicJwk.x,
          not_before: "2026-07-01T00:00:00.000Z",
          not_after: "2027-07-01T00:00:00.000Z",
          status: "active",
        },
      ],
    }),
  };
}

async function loadRoutes() {
  const [anchor, feed, edition, breaking] = await Promise.all([
    import(anchorRoutePath),
    import(feedRoutePath),
    import(editionRoutePath),
    import(breakingRoutePath),
  ]);
  return {
    anchor: anchor.POST,
    feed: feed.GET,
    edition: edition.POST,
    breaking: breaking.POST,
  };
}

async function invoke(handler, request, runtime) {
  return runWithMagazineBindings(runtime, () => handler(request));
}

async function signedFeedRequest({
  afterSeq = "0",
  checkpointHash = ZERO_HASH,
  limit = "100",
  operation,
  packetId,
  admission = true,
}) {
  const query = new URLSearchParams({
    stream_id: STREAM_ID,
    after_seq: afterSeq,
    checkpoint_hash: checkpointHash,
    limit,
    operation,
    packet_id: packetId,
  });
  const request = new Request(
    `https://magazine.example/api/machine/audit-events/v1?${query.toString()}`,
    {
      method: "GET",
      headers: {
        "content-type": "application/json",
        ...(admission
          ? { "oai-sites-authorization": "Bearer task-6-dispatch-token" }
          : {}),
      },
    },
  );
  const signed = await machineSignatureHeaders(request, {
    timestamp: String(Math.floor(Date.now() / 1000)),
    nonce: `task-6-feed-${crypto.randomUUID()}`,
    keyId: MACHINE_KEY_ID,
    audience: MACHINE_AUDIENCE,
    secret: MACHINE_SECRET,
  });
  for (const [name, value] of Object.entries(signed)) {
    request.headers.set(name, value);
  }
  return request;
}

function makeReceipt(target, overrides = {}) {
  const body = {
    schema_version: "audit-anchor.v1",
    anchor_id: `anchor-${target.stream_seq}`,
    stream_id: target.stream_id,
    stream_seq: target.stream_seq,
    event_hash: target.event_hash,
    previous_anchor_hash: ZERO_HASH,
    observed_at: "2026-07-19T03:00:00.000Z",
    key_id: KEY_ID,
    ...overrides.body,
  };
  const canonical = canonicalizeAnchorBody(body);
  const signatureBytes = signEd25519(
    null,
    buildAnchorSignaturePreimage(canonical),
    privateKey,
  );
  const signature = signatureBytes.toString("base64url");
  return {
    body,
    signature,
    anchor_hash: createHash("sha256")
      .update(buildAnchorHashPreimage(canonical, signatureBytes))
      .digest("hex"),
    ...overrides.receipt,
  };
}

async function stageAndReadTarget(
  routes,
  db,
  runtime,
  kind = "edition",
  packetOverrides = {},
) {
  const story = storyVersion({
    suffix: `audit-${kind}-${crypto.randomUUID()}`,
  });
  const packet =
    kind === "edition"
      ? editionPacket(story, packetOverrides)
      : breakingPacket(story, packetOverrides);
  const operation = kind === "edition" ? "edition.publish" : "breaking.publish";
  const body = JSON.stringify(packet);
  const request = await signedMachineRequest({
    path:
      kind === "edition"
        ? "/api/machine/publications/editions"
        : "/api/machine/publications/breaking",
    body,
  });
  const staged = await invoke(routes[kind], request, runtime);
  assert.equal(staged.status, 409);
  assert.deepEqual(await staged.json(), {
    ok: false,
    error: "promotion_blocked",
    operation,
    packet_id: packet.packet_id,
  });
  const feedRequest = await signedFeedRequest({
    operation,
    packetId: packet.packet_id,
  });
  const feed = await invoke(routes.feed, feedRequest, runtime);
  assert.equal(feed.status, 200);
  const projection = await feed.json();
  assert.equal(projection.schema_version, "audit-feed.v1");
  assert.equal(projection.stream_id, STREAM_ID);
  assert.deepEqual(projection.checkpoint, {
    stream_seq: "0",
    event_hash: ZERO_HASH,
  });
  assert.ok(projection.events.length >= 1);
  const targetEvent = projection.events.find(
    (event) =>
      event.payload.operation === operation &&
      event.payload.packet_id === packet.packet_id,
  );
  assert.ok(targetEvent);
  assert.deepEqual(targetEvent.payload, {
    schema_version: "publication-operation.v1",
    operation,
    packet_id: packet.packet_id,
  });
  assert.deepEqual(projection.promotion_target, {
    operation,
    packet_id: packet.packet_id,
    stream_seq: targetEvent.stream_seq,
    event_hash: targetEvent.event_hash,
  });
  assert.equal("event_id" in targetEvent, false);
  return { packet, body, operation, target: projection.promotion_target };
}

test("audit ingress routes exist", () => {
  assert.ok(existsSync(anchorRoutePath));
  assert.ok(existsSync(feedRoutePath));
});

test("anchor binary fields require canonical unpadded base64url", () => {
  const alphabet =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  const canonical = publicJwk.x;
  const lastIndex = alphabet.indexOf(canonical.at(-1));
  const alias = `${canonical.slice(0, -1)}${alphabet[lastIndex + 1]}`;
  assert.deepEqual(
    Buffer.from(alias, "base64url"),
    Buffer.from(canonical, "base64url"),
  );
  assert.throws(() => decodeBase64Url(alias, 32), /invalid unpadded base64url/);
});

test(
  "feed requires SIWC and exact HMAC and rejects an unbound checkpoint",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const unauthorized = await signedFeedRequest({
      operation: "edition.publish",
      packetId: "packet-x",
      admission: false,
    });
    assert.equal(
      (await invoke(routes.feed, unauthorized, runtime)).status,
      401,
    );
    const invalidCheckpoint = await signedFeedRequest({
      afterSeq: "1",
      checkpointHash: "a".repeat(64),
      operation: "edition.publish",
      packetId: "packet-x",
    });
    assert.equal(
      (await invoke(routes.feed, invalidCheckpoint, runtime)).status,
      409,
    );
  },
);

test(
  "staged publication emits a closed canonical feed and remains blocked",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    await stageAndReadTarget(routes, db, bindings(db));
    assert.equal(
      db.get(
        "SELECT publication_state FROM publication_packets WHERE packet_id = ?",
        db.get("SELECT packet_id FROM publication_packets LIMIT 1").packet_id,
      ).publication_state,
      "building",
    );
  },
);

test(
  "valid signed receipt unlocks only its operation and exact packet",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const staged = await stageAndReadTarget(routes, db, runtime);
    const receipt = makeReceipt({
      ...staged.target,
      stream_id: STREAM_ID,
    });
    const anchor = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(receipt),
    });
    const accepted = await invoke(routes.anchor, anchor, runtime);
    assert.equal(accepted.status, 201);
    assert.deepEqual(await accepted.json(), { ok: true, status: "created" });

    const retry = await signedMachineRequest({
      path: "/api/machine/publications/editions",
      body: staged.body,
    });
    const published = await invoke(routes.edition, retry, runtime);
    assert.equal(published.status, 201);
    assert.deepEqual(await published.json(), { ok: true, status: "created" });
  },
);

test(
  "concurrent staged editions finalize in audit order from the prior checkpoint",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const firstStory = storyVersion({
      suffix: `audit-concurrent-a-${crypto.randomUUID()}`,
    });
    const secondStory = storyVersion({
      suffix: `audit-concurrent-b-${crypto.randomUUID()}`,
    });
    const firstPacket = editionPacket(firstStory);
    const secondPacket = editionPacket(secondStory, {
      edition_revision: 2,
      expected_current_revision: 1,
      expected_breaking_revision: 1,
    });
    const firstBody = JSON.stringify(firstPacket);
    const secondBody = JSON.stringify(secondPacket);

    for (const [packet, body] of [
      [firstPacket, firstBody],
      [secondPacket, secondBody],
    ]) {
      const request = await signedMachineRequest({
        path: "/api/machine/publications/editions",
        body,
      });
      const response = await invoke(routes.edition, request, runtime);
      assert.equal(response.status, 409);
      assert.deepEqual(await response.json(), {
        ok: false,
        error: "promotion_blocked",
        operation: "edition.publish",
        packet_id: packet.packet_id,
      });
    }

    const firstFeedRequest = await signedFeedRequest({
      operation: "edition.publish",
      packetId: firstPacket.packet_id,
    });
    const firstFeedResponse = await invoke(
      routes.feed,
      firstFeedRequest,
      runtime,
    );
    assert.equal(firstFeedResponse.status, 200);
    const firstFeed = await firstFeedResponse.json();
    assert.equal(firstFeed.events.length, 2);
    assert.deepEqual(firstFeed.promotion_target, {
      operation: "edition.publish",
      packet_id: firstPacket.packet_id,
      stream_seq: firstFeed.events[0].stream_seq,
      event_hash: firstFeed.events[0].event_hash,
    });

    const secondBeforeFirstAnchor = await signedMachineRequest({
      path: "/api/machine/publications/editions",
      body: secondBody,
    });
    assert.equal(
      (await invoke(routes.edition, secondBeforeFirstAnchor, runtime)).status,
      409,
    );

    const firstReceipt = makeReceipt({
      ...firstFeed.promotion_target,
      stream_id: STREAM_ID,
    });
    const firstAnchorRequest = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(firstReceipt),
    });
    assert.equal(
      (await invoke(routes.anchor, firstAnchorRequest, runtime)).status,
      201,
    );
    const firstFinalizeRequest = await signedMachineRequest({
      path: "/api/machine/publications/editions",
      body: firstBody,
    });
    assert.equal(
      (await invoke(routes.edition, firstFinalizeRequest, runtime)).status,
      201,
    );

    const secondBeforeOwnAnchor = await signedMachineRequest({
      path: "/api/machine/publications/editions",
      body: secondBody,
    });
    const stillBlocked = await invoke(
      routes.edition,
      secondBeforeOwnAnchor,
      runtime,
    );
    assert.equal(stillBlocked.status, 409);
    assert.deepEqual(await stillBlocked.json(), {
      ok: false,
      error: "promotion_blocked",
      operation: "edition.publish",
      packet_id: secondPacket.packet_id,
    });

    const secondFeedRequest = await signedFeedRequest({
      afterSeq: firstFeed.promotion_target.stream_seq,
      checkpointHash: firstFeed.promotion_target.event_hash,
      operation: "edition.publish",
      packetId: secondPacket.packet_id,
    });
    const secondFeedResponse = await invoke(
      routes.feed,
      secondFeedRequest,
      runtime,
    );
    assert.equal(secondFeedResponse.status, 200);
    const secondFeed = await secondFeedResponse.json();
    assert.equal(secondFeed.events.length, 1);
    assert.deepEqual(secondFeed.promotion_target, {
      operation: "edition.publish",
      packet_id: secondPacket.packet_id,
      stream_seq: secondFeed.events[0].stream_seq,
      event_hash: secondFeed.events[0].event_hash,
    });
    const secondReceipt = makeReceipt(
      { ...secondFeed.promotion_target, stream_id: STREAM_ID },
      { body: { previous_anchor_hash: firstReceipt.anchor_hash } },
    );
    const secondAnchorRequest = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(secondReceipt),
    });
    assert.equal(
      (await invoke(routes.anchor, secondAnchorRequest, runtime)).status,
      201,
    );
    const secondFinalizeRequest = await signedMachineRequest({
      path: "/api/machine/publications/editions",
      body: secondBody,
    });
    assert.equal(
      (await invoke(routes.edition, secondFinalizeRequest, runtime)).status,
      201,
    );

    for (const packet of [firstPacket, secondPacket]) {
      assert.equal(
        db.get(
          "SELECT publication_state FROM publication_packets WHERE packet_id = ?",
          packet.packet_id,
        ).publication_state,
        "published",
      );
    }
    assert.equal(
      db.get(
        "SELECT current_revision FROM edition_pointer WHERE singleton_id = 1",
      ).current_revision,
      2,
    );
  },
);

test(
  "leapfrog receipt is rejected until every canonical predecessor is anchored",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const first = await stageAndReadTarget(routes, db, runtime, "edition");
    const second = await stageAndReadTarget(routes, db, runtime, "breaking", {
      expected_breaking_revision: 1,
    });
    const firstReceipt = makeReceipt({
      ...first.target,
      stream_id: STREAM_ID,
    });
    const prematureSecondReceipt = makeReceipt({
      ...second.target,
      stream_id: STREAM_ID,
    });

    const prematureSecondRequest = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(prematureSecondReceipt),
    });
    assert.equal(
      (await invoke(routes.anchor, prematureSecondRequest, runtime)).status,
      409,
    );
    assert.equal(
      db.get(
        "SELECT stream_seq FROM audit_anchor_heads WHERE stream_id = ?",
        STREAM_ID,
      ),
      null,
    );
    assert.equal(
      db.get(
        `SELECT status FROM audit_promotion_permits
         WHERE operation = ? AND packet_id = ?`,
        second.operation,
        second.packet.packet_id,
      ),
      null,
    );

    const firstAnchorRequest = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(firstReceipt),
    });
    assert.equal(
      (await invoke(routes.anchor, firstAnchorRequest, runtime)).status,
      201,
    );
    const firstFinalizeRequest = await signedMachineRequest({
      path: "/api/machine/publications/editions",
      body: first.body,
    });
    assert.equal(
      (await invoke(routes.edition, firstFinalizeRequest, runtime)).status,
      201,
    );

    const orderedSecondReceipt = makeReceipt(
      { ...second.target, stream_id: STREAM_ID },
      { body: { previous_anchor_hash: firstReceipt.anchor_hash } },
    );
    const secondAnchorRequest = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(orderedSecondReceipt),
    });
    assert.equal(
      (await invoke(routes.anchor, secondAnchorRequest, runtime)).status,
      201,
    );
    const secondFinalizeRequest = await signedMachineRequest({
      path: "/api/machine/publications/breaking",
      body: second.body,
    });
    assert.equal(
      (await invoke(routes.breaking, secondFinalizeRequest, runtime)).status,
      201,
    );

    for (const packet of [first.packet, second.packet]) {
      assert.equal(
        db.get(
          "SELECT publication_state FROM publication_packets WHERE packet_id = ?",
          packet.packet_id,
        ).publication_state,
        "published",
      );
    }
  },
);

test(
  "receipt exact replay survives a fresh route import and changed reuse conflicts",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const staged = await stageAndReadTarget(routes, db, runtime, "breaking");
    const receipt = makeReceipt({ ...staged.target, stream_id: STREAM_ID });
    for (const expected of [201, 200]) {
      const request = await signedMachineRequest({
        path: "/api/machine/audit-anchor",
        body: JSON.stringify(receipt),
      });
      const response = await invoke(routes.anchor, request, runtime);
      assert.equal(response.status, expected);
    }
    const changed = makeReceipt(
      { ...staged.target, stream_id: STREAM_ID },
      {
        body: {
          anchor_id: receipt.body.anchor_id,
          observed_at: "2026-07-19T03:00:00.001Z",
        },
      },
    );
    const conflict = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(changed),
    });
    assert.equal((await invoke(routes.anchor, conflict, runtime)).status, 409);
  },
);

test(
  "bad signature, record hash, and closed-schema violations persist a promotion block",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const staged = await stageAndReadTarget(routes, db, runtime);
    const valid = makeReceipt({ ...staged.target, stream_id: STREAM_ID });
    const invalidReceipts = [
      { ...valid, signature: "A".repeat(86) },
      { ...valid, anchor_hash: "e".repeat(64) },
      { ...valid, extra: true },
    ];
    for (const receipt of invalidReceipts) {
      const request = await signedMachineRequest({
        path: "/api/machine/audit-anchor",
        body: JSON.stringify(receipt),
      });
      assert.equal((await invoke(routes.anchor, request, runtime)).status, 400);
    }
    assert.equal(
      db.get("SELECT blocked FROM audit_promotion_block WHERE singleton_id = 1")
        .blocked,
      1,
    );
  },
);

test(
  "anchor key registry is closed, versioned, retained, and time bounded",
  { skip: !routesExist },
  async () => {
    const verificationReceipt = makeReceipt({
      stream_id: STREAM_ID,
      stream_seq: "1",
      event_hash: "a".repeat(64),
    });
    const registry = JSON.parse(
      bindings(new SqliteD1Database()).AUDIT_ANCHOR_KEY_REGISTRY_JSON,
    );
    registry.keys[0].status = "retained";
    await assert.doesNotReject(
      verifyAuditAnchorReceipt(verificationReceipt, JSON.stringify(registry)),
    );
    registry.keys[0].not_before = "2026-07-01T00:00:00Z";
    await assert.rejects(
      verifyAuditAnchorReceipt(verificationReceipt, JSON.stringify(registry)),
      /invalid anchor registry key lifetime/,
    );

    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const staged = await stageAndReadTarget(routes, db, runtime);
    const receipt = makeReceipt({ ...staged.target, stream_id: STREAM_ID });
    const request = await signedMachineRequest({
      path: "/api/machine/audit-anchor",
      body: JSON.stringify(receipt),
    });
    const malformedRegistry = {
      ...runtime,
      AUDIT_ANCHOR_KEY_REGISTRY_JSON: JSON.stringify({
        schema_version: "audit-anchor-key-registry.v1",
        registry_version: "2026-07-19.1",
        keys: [],
        unexpected: true,
      }),
    };
    assert.equal(
      (await invoke(routes.anchor, request, malformedRegistry)).status,
      409,
    );
  },
);

test(
  "feed cursor advances from an exact checkpoint without leaking raw payload fields",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const routes = await loadRoutes();
    const runtime = bindings(db);
    const first = await stageAndReadTarget(routes, db, runtime, "edition");
    const second = await stageAndReadTarget(routes, db, runtime, "breaking");
    const request = await signedFeedRequest({
      afterSeq: first.target.stream_seq,
      checkpointHash: first.target.event_hash,
      operation: second.operation,
      packetId: second.packet.packet_id,
      limit: "1",
    });
    const response = await invoke(routes.feed, request, runtime);
    assert.equal(response.status, 200);
    const feed = await response.json();
    assert.equal(feed.events.length, 1);
    assert.equal(feed.events[0].previous_event_hash, first.target.event_hash);
    assert.deepEqual(feed.promotion_target, {
      operation: second.operation,
      packet_id: second.packet.packet_id,
      stream_seq: feed.events[0].stream_seq,
      event_hash: feed.events[0].event_hash,
    });
    assert.deepEqual(Object.keys(feed.events[0].payload).sort(), [
      "operation",
      "packet_id",
      "schema_version",
    ]);
  },
);
