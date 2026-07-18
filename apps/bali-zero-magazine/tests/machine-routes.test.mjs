import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import test from "node:test";

import { runWithMagazineBindings } from "../lib/server/runtime-bindings.ts";
import { readStoryDetail } from "../lib/server/magazine-read-model.ts";
import {
  MemoryR2Bucket,
  MALFORMED_JPEG,
  MALFORMED_PNG,
  MALFORMED_WEBP,
  SqliteD1Database,
  VALID_JPEG,
  VALID_PNG,
  VALID_PNG_VARIANT,
  VALID_WEBP,
  breakingPacket,
  collectorRun,
  editionPacket,
  instrumentSingleBodyRead,
  runtimeBindings,
  seedSourceSystem,
  signedMachineRequest,
  storyVersion,
  validAssetMetadata,
} from "./helpers/task-5-fixtures.mjs";

const routePaths = {
  collector: new URL(
    "../app/api/machine/collector-runs/route.ts",
    import.meta.url,
  ),
  edition: new URL(
    "../app/api/machine/publications/editions/route.ts",
    import.meta.url,
  ),
  breaking: new URL(
    "../app/api/machine/publications/breaking/route.ts",
    import.meta.url,
  ),
  asset: new URL("../app/api/machine/assets/route.ts", import.meta.url),
};
const routesExist = Object.values(routePaths).every(existsSync);

test("machine ingress exposes all four protected routes", () => {
  for (const [name, path] of Object.entries(routePaths)) {
    assert.ok(existsSync(path), `missing ${name} machine route`);
  }
});

async function loadRoutes() {
  const [collector, edition, breaking, asset] = await Promise.all([
    import(routePaths.collector),
    import(routePaths.edition),
    import(routePaths.breaking),
    import(routePaths.asset),
  ]);
  return {
    collector: collector.POST,
    edition: edition.POST,
    breaking: breaking.POST,
    asset: asset.POST,
  };
}

async function invoke(handler, request, bindings) {
  return runWithMagazineBindings(bindings, () => handler(request));
}

test(
  "machine route requires dispatcher admission before HMAC verification",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    seedSourceSystem(db);
    const routes = await loadRoutes();
    const missingAdmission = await signedMachineRequest({
      path: "/api/machine/collector-runs",
      body: JSON.stringify(collectorRun()),
      admission: false,
    });
    const response = await invoke(
      routes.collector,
      missingAdmission,
      runtimeBindings(db),
    );
    assert.equal(response.status, 401);
    assert.deepEqual(await response.json(), {
      ok: false,
      error: "unauthorized",
    });
    assert.equal(
      db.get("SELECT count(*) AS count FROM ingest_nonces").count,
      0,
    );
  },
);

test(
  "machine route rejects invalid HMAC and repeated nonce without state leakage",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    seedSourceSystem(db);
    const routes = await loadRoutes();
    const invalid = await signedMachineRequest({
      path: "/api/machine/collector-runs",
      body: JSON.stringify(collectorRun()),
      signingSecret: "wrong-machine-secret",
    });
    const invalidResponse = await invoke(
      routes.collector,
      invalid,
      runtimeBindings(db),
    );
    assert.equal(invalidResponse.status, 401);
    assert.deepEqual(await invalidResponse.json(), {
      ok: false,
      error: "unauthorized",
    });

    const nonce = "task-5-replayed-nonce";
    const accepted = await signedMachineRequest({
      path: "/api/machine/collector-runs",
      body: JSON.stringify(collectorRun()),
      nonce,
    });
    assert.equal(
      (await invoke(routes.collector, accepted, runtimeBindings(db))).status,
      201,
    );
    const replayedNonce = await signedMachineRequest({
      path: "/api/machine/collector-runs",
      body: JSON.stringify(collectorRun()),
      nonce,
    });
    const replayResponse = await invoke(
      routes.collector,
      replayedNonce,
      runtimeBindings(db),
    );
    assert.equal(replayResponse.status, 401);
    assert.deepEqual(await replayResponse.json(), {
      ok: false,
      error: "unauthorized",
    });
  },
);

test(
  "collector ingress reads once and returns created, replay, then conflict",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    seedSourceSystem(db);
    const routes = await loadRoutes();
    const bindings = runtimeBindings(db);
    const body = JSON.stringify(collectorRun());
    const created = await signedMachineRequest({
      path: "/api/machine/collector-runs",
      body,
    });
    const reads = instrumentSingleBodyRead(created);
    const createdResponse = await invoke(routes.collector, created, bindings);
    assert.equal(createdResponse.status, 201);
    assert.equal(reads(), 1);
    assert.deepEqual(await createdResponse.json(), {
      ok: true,
      status: "created",
    });

    const replay = await signedMachineRequest({
      path: "/api/machine/collector-runs",
      body,
    });
    const replayResponse = await invoke(routes.collector, replay, bindings);
    assert.equal(replayResponse.status, 200);
    assert.deepEqual(await replayResponse.json(), {
      ok: true,
      status: "replay",
    });

    const conflict = await signedMachineRequest({
      path: "/api/machine/collector-runs",
      body: JSON.stringify(collectorRun({ items_seen: 43 })),
    });
    const conflictResponse = await invoke(routes.collector, conflict, bindings);
    assert.equal(conflictResponse.status, 409);
    assert.deepEqual(await conflictResponse.json(), {
      ok: false,
      error: "conflict",
    });
    assert.equal(
      db.get(
        "SELECT items_seen FROM collector_runs WHERE run_id = ?",
        "collector-run-task-5",
      ).items_seen,
      42,
    );
  },
);

test(
  "collector ingress rejects closed-schema violations and unknown systems",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    seedSourceSystem(db);
    const routes = await loadRoutes();
    const bindings = runtimeBindings(db);
    for (const payload of [
      collectorRun({ raw_payload: "forbidden" }),
      collectorRun({ system_id: "unknown-system", run_id: "unknown-run" }),
    ]) {
      const request = await signedMachineRequest({
        path: "/api/machine/collector-runs",
        body: JSON.stringify(payload),
      });
      const response = await invoke(routes.collector, request, bindings);
      assert.ok([400, 409].includes(response.status));
      assert.equal(
        db.get("SELECT count(*) AS count FROM collector_runs").count,
        0,
      );
    }
  },
);

test(
  "edition and Breaking routes publish atomically and replay idempotently",
  { skip: !routesExist },
  async () => {
    const routes = await loadRoutes();
    for (const target of ["edition", "breaking"]) {
      const db = new SqliteD1Database();
      const story = storyVersion({ suffix: target });
      const packet =
        target === "edition" ? editionPacket(story) : breakingPacket(story);
      const path =
        target === "edition"
          ? "/api/machine/publications/editions"
          : "/api/machine/publications/breaking";
      const body = JSON.stringify(packet);
      const created = await signedMachineRequest({ path, body });
      const createdResponse = await invoke(
        routes[target],
        created,
        runtimeBindings(db),
      );
      assert.equal(createdResponse.status, 201, target);
      assert.deepEqual(await createdResponse.json(), {
        ok: true,
        status: "created",
      });

      const replay = await signedMachineRequest({ path, body });
      const replayResponse = await invoke(
        routes[target],
        replay,
        runtimeBindings(db),
      );
      assert.equal(replayResponse.status, 200, target);
      assert.deepEqual(await replayResponse.json(), {
        ok: true,
        status: "replay",
      });
    }
  },
);

test(
  "publication routes reject invalid packets, conflicts, and unverified assets",
  { skip: !routesExist },
  async () => {
    const routes = await loadRoutes();

    const invalidDb = new SqliteD1Database();
    const invalid = await signedMachineRequest({
      path: "/api/machine/publications/breaking",
      body: JSON.stringify({
        ...breakingPacket(storyVersion()),
        unknown: true,
      }),
    });
    const invalidResponse = await invoke(
      routes.breaking,
      invalid,
      runtimeBindings(invalidDb),
    );
    assert.equal(invalidResponse.status, 400);

    const conflictDb = new SqliteD1Database();
    const conflictStory = storyVersion({ suffix: "conflict" });
    const initialPacket = breakingPacket(conflictStory);
    const first = await signedMachineRequest({
      path: "/api/machine/publications/breaking",
      body: JSON.stringify(initialPacket),
    });
    assert.equal(
      (await invoke(routes.breaking, first, runtimeBindings(conflictDb)))
        .status,
      201,
    );
    const changed = await signedMachineRequest({
      path: "/api/machine/publications/breaking",
      body: JSON.stringify({
        ...initialPacket,
        verified_at: "2026-07-17T21:02:00Z",
      }),
    });
    assert.equal(
      (await invoke(routes.breaking, changed, runtimeBindings(conflictDb)))
        .status,
      409,
    );

    const assetDb = new SqliteD1Database();
    const digest = "a".repeat(64);
    const assetStory = storyVersion({ suffix: "asset", assetDigest: digest });
    const unverified = await signedMachineRequest({
      path: "/api/machine/publications/breaking",
      body: JSON.stringify(breakingPacket(assetStory)),
    });
    const unverifiedResponse = await invoke(
      routes.breaking,
      unverified,
      runtimeBindings(assetDb),
    );
    assert.equal(unverifiedResponse.status, 409);
    assert.equal(
      assetDb.get(
        "SELECT current_version FROM stories WHERE story_id = ?",
        assetStory.story_id,
      ),
      null,
    );
  },
);

test(
  "asset upload validates bytes, binds metadata, verifies R2, and replays safely",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    const media = new MemoryR2Bucket();
    const routes = await loadRoutes();
    const bindings = runtimeBindings(db, media);
    const metadata = await validAssetMetadata();
    const created = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: "image/png",
      metadata,
    });
    const createdResponse = await invoke(routes.asset, created, bindings);
    assert.equal(createdResponse.status, 201);
    assert.deepEqual(await createdResponse.json(), {
      ok: true,
      status: "created",
    });
    const row = db.get(
      "SELECT * FROM assets WHERE asset_id = ?",
      metadata.asset_id,
    );
    assert.equal(row.status, "verified");
    assert.equal(row.sha256, metadata.sha256);
    assert.equal(row.r2_key, `assets/sha256/${metadata.sha256}.png`);
    assert.equal(row.captured_at, metadata.captured_at);

    const replay = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: "image/png",
      metadata,
    });
    assert.equal((await invoke(routes.asset, replay, bindings)).status, 200);

    const story = storyVersion({
      suffix: "asset-provenance",
      assetDigest: metadata.sha256,
    });
    const publication = await signedMachineRequest({
      path: "/api/machine/publications/breaking",
      body: JSON.stringify(breakingPacket(story)),
    });
    assert.equal(
      (await invoke(routes.breaking, publication, bindings)).status,
      201,
    );
    const detail = await runWithMagazineBindings(bindings, () =>
      readStoryDetail(story.slug),
    );
    assert.deepEqual(detail?.imageProvenance, {
      altText: metadata.alt_text,
      source: metadata.source,
      sourceUrl: metadata.source_url,
      rightsBasis: metadata.rights_basis,
      rightsStatus: metadata.rights_status,
      usageStatus: metadata.usage_status,
      dlpStatus: metadata.dlp_status,
      sanitizationStatus: metadata.sanitization_status,
      perceptualDedupStatus: metadata.perceptual_dedup_status,
      createdAt: row.created_at,
    });
  },
);

test(
  "asset upload decodes JPEG, PNG, and WebP and rejects malformed compressed payloads",
  { skip: !routesExist },
  async () => {
    const routes = await loadRoutes();
    const fixtures = [
      { mime: "image/jpeg", valid: VALID_JPEG, malformed: MALFORMED_JPEG },
      { mime: "image/png", valid: VALID_PNG, malformed: MALFORMED_PNG },
      { mime: "image/webp", valid: VALID_WEBP, malformed: MALFORMED_WEBP },
    ];
    for (const [index, fixture] of fixtures.entries()) {
      const validDb = new SqliteD1Database();
      const validMetadata = await validAssetMetadata(
        {
          asset_id: `asset-valid-format-${index}`,
          mime_type: fixture.mime,
        },
        fixture.valid,
      );
      const validRequest = await signedMachineRequest({
        path: "/api/machine/assets",
        body: fixture.valid,
        contentType: fixture.mime,
        metadata: validMetadata,
      });
      assert.equal(
        (await invoke(routes.asset, validRequest, runtimeBindings(validDb)))
          .status,
        201,
        `${fixture.mime} valid fixture`,
      );

      const malformedDb = new SqliteD1Database();
      const malformedMetadata = await validAssetMetadata(
        {
          asset_id: `asset-malformed-format-${index}`,
          mime_type: fixture.mime,
        },
        fixture.malformed,
      );
      const malformedRequest = await signedMachineRequest({
        path: "/api/machine/assets",
        body: fixture.malformed,
        contentType: fixture.mime,
        metadata: malformedMetadata,
      });
      assert.equal(
        (
          await invoke(
            routes.asset,
            malformedRequest,
            runtimeBindings(malformedDb),
          )
        ).status,
        400,
        `${fixture.mime} malformed fixture`,
      );
      assert.equal(
        malformedDb.get("SELECT count(*) AS count FROM assets").count,
        0,
      );
    }
  },
);

test(
  "content-addressed upload never overwrites an existing R2 object",
  { skip: !routesExist },
  async () => {
    const routes = await loadRoutes();
    const metadata = await validAssetMetadata();
    const key = `assets/sha256/${metadata.sha256}.png`;

    const identicalDb = new SqliteD1Database();
    const identicalR2 = new MemoryR2Bucket();
    await identicalR2.put(key, VALID_PNG, {
      httpMetadata: { contentType: metadata.mime_type },
      customMetadata: {
        sha256: metadata.sha256,
        byteCount: String(metadata.byte_count),
        width: String(metadata.width),
        height: String(metadata.height),
      },
    });
    identicalR2.putCalls.length = 0;
    const identicalRequest = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: metadata.mime_type,
      metadata,
    });
    assert.equal(
      (
        await invoke(
          routes.asset,
          identicalRequest,
          runtimeBindings(identicalDb, identicalR2),
        )
      ).status,
      201,
    );
    assert.deepEqual(identicalR2.putCalls, []);

    const inconsistentDb = new SqliteD1Database();
    const inconsistentR2 = new MemoryR2Bucket();
    inconsistentR2.objects.set(key, {
      bytes: Uint8Array.of(1, 2, 3),
      httpMetadata: { contentType: metadata.mime_type },
      customMetadata: {
        sha256: metadata.sha256,
        byteCount: String(metadata.byte_count),
        width: String(metadata.width),
        height: String(metadata.height),
      },
    });
    const before = Uint8Array.from(inconsistentR2.objects.get(key).bytes);
    const inconsistentRequest = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: metadata.mime_type,
      metadata,
    });
    assert.equal(
      (
        await invoke(
          routes.asset,
          inconsistentRequest,
          runtimeBindings(inconsistentDb, inconsistentR2),
        )
      ).status,
      409,
    );
    assert.deepEqual(inconsistentR2.putCalls, []);
    assert.deepEqual(inconsistentR2.objects.get(key).bytes, before);
    assert.equal(
      inconsistentDb.get("SELECT count(*) AS count FROM assets").count,
      0,
    );
  },
);

test(
  "asset metadata is HMAC-bound and read-back mismatch fails closed",
  { skip: !routesExist },
  async () => {
    const routes = await loadRoutes();
    const metadata = await validAssetMetadata();
    const tampered = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: "image/png",
      metadata,
    });
    tampered.headers.set(
      "x-magazine-asset-metadata",
      JSON.stringify({ ...metadata, width: 2 }),
    );
    const tamperedDb = new SqliteD1Database();
    assert.equal(
      (await invoke(routes.asset, tampered, runtimeBindings(tamperedDb)))
        .status,
      401,
    );
    assert.equal(
      tamperedDb.get("SELECT count(*) AS count FROM assets").count,
      0,
    );

    const corruptDb = new SqliteD1Database();
    const corruptR2 = new MemoryR2Bucket();
    corruptR2.corruptReadBack = true;
    const request = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: "image/png",
      metadata,
    });
    const response = await invoke(
      routes.asset,
      request,
      runtimeBindings(corruptDb, corruptR2),
    );
    assert.equal(response.status, 409);
    assert.equal(
      corruptDb.get("SELECT count(*) AS count FROM assets").count,
      0,
    );
  },
);

test(
  "asset upload rejects active formats, polyglots, animation, mismatches, and limits",
  { skip: !routesExist },
  async () => {
    const routes = await loadRoutes();
    const cases = [
      {
        name: "SVG",
        bytes: new TextEncoder().encode(
          "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        ),
        mime: "image/png",
      },
      {
        name: "HTML",
        bytes: new TextEncoder().encode("<!doctype html><html></html>"),
        mime: "image/png",
      },
      {
        name: "XML",
        bytes: new TextEncoder().encode("<?xml version='1.0'?><image/>"),
        mime: "image/png",
      },
      {
        name: "PNG polyglot",
        bytes: Uint8Array.from([
          ...VALID_PNG,
          ...new TextEncoder().encode("<script/>"),
        ]),
        mime: "image/png",
      },
      {
        name: "animated WebP",
        bytes: Uint8Array.from([
          0x52, 0x49, 0x46, 0x46, 0x16, 0, 0, 0, 0x57, 0x45, 0x42, 0x50, 0x56,
          0x50, 0x38, 0x58, 0x0a, 0, 0, 0, 0x02, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ]),
        mime: "image/webp",
      },
    ];
    for (const [index, fixture] of cases.entries()) {
      const db = new SqliteD1Database();
      const metadata = await validAssetMetadata({
        asset_id: `asset-rejected-${index}`,
        sha256: await crypto.subtle
          .digest("SHA-256", fixture.bytes)
          .then((digest) => Buffer.from(digest).toString("hex")),
        byte_count: fixture.bytes.byteLength,
        mime_type: fixture.mime,
      });
      const request = await signedMachineRequest({
        path: "/api/machine/assets",
        body: fixture.bytes,
        contentType: fixture.mime,
        metadata,
      });
      const response = await invoke(routes.asset, request, runtimeBindings(db));
      assert.equal(response.status, 400, fixture.name);
      assert.equal(db.get("SELECT count(*) AS count FROM assets").count, 0);
    }

    const mismatchDb = new SqliteD1Database();
    const mismatch = await validAssetMetadata({ width: 2 });
    const mismatchRequest = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: "image/png",
      metadata: mismatch,
    });
    assert.equal(
      (await invoke(routes.asset, mismatchRequest, runtimeBindings(mismatchDb)))
        .status,
      400,
    );

    const oversizedDb = new SqliteD1Database();
    const oversizedBytes = new Uint8Array(12 * 1024 * 1024 + 1);
    const oversizedMetadata = await validAssetMetadata({
      asset_id: "asset-oversized",
      sha256: "b".repeat(64),
      byte_count: oversizedBytes.byteLength,
    });
    const oversizedRequest = await signedMachineRequest({
      path: "/api/machine/assets",
      body: oversizedBytes,
      contentType: "image/png",
      metadata: oversizedMetadata,
    });
    assert.equal(
      (
        await invoke(
          routes.asset,
          oversizedRequest,
          runtimeBindings(oversizedDb),
        )
      ).status,
      413,
    );
  },
);

test(
  "asset packet cap remains atomic under concurrent uploads",
  { skip: !routesExist },
  async () => {
    const db = new SqliteD1Database();
    for (let index = 0; index < 19; index += 1) {
      db.execute(
        `INSERT INTO assets(
           asset_id, packet_id, sha256, r2_key, mime_type, byte_count, width,
           height, alt_text, source, rights_status, status, captured_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        `seed-${index}`,
        "asset-packet-task-5",
        index.toString(16).padStart(64, "0"),
        `assets/sha256/${index.toString(16).padStart(64, "0")}.png`,
        "image/png",
        1,
        1,
        1,
        "",
        "",
        "approved",
        "verified",
        "2026-07-18T01:00:00Z",
      );
    }
    const routes = await loadRoutes();
    const media = new MemoryR2Bucket();
    const bindings = runtimeBindings(db, media);
    const firstMetadata = await validAssetMetadata({ asset_id: "race-first" });
    const secondMetadata = await validAssetMetadata({
      asset_id: "race-second",
      sha256: await crypto.subtle
        .digest("SHA-256", VALID_PNG_VARIANT)
        .then((digest) => Buffer.from(digest).toString("hex")),
      byte_count: VALID_PNG_VARIANT.byteLength,
    });
    const first = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG,
      contentType: "image/png",
      metadata: firstMetadata,
    });
    const second = await signedMachineRequest({
      path: "/api/machine/assets",
      body: VALID_PNG_VARIANT,
      contentType: "image/png",
      metadata: secondMetadata,
    });
    const results = await Promise.all([
      invoke(routes.asset, first, bindings),
      invoke(routes.asset, second, bindings),
    ]);
    assert.equal(
      results.filter((response) => response.status === 201).length,
      1,
    );
    assert.equal(
      results.filter((response) => response.status === 409).length,
      1,
    );
    assert.equal(
      db.get(
        "SELECT count(*) AS count FROM assets WHERE packet_id = ?",
        "asset-packet-task-5",
      ).count,
      20,
    );
  },
);
