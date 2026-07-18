import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import test from "node:test";

import { parseStoryPacket } from "../lib/contracts/publication.ts";
import { readStoryDetail } from "../lib/server/magazine-read-model.ts";
import { createPublicationRepository } from "../lib/server/publication-repository.ts";
import { runWithMagazineBindings } from "../lib/server/runtime-bindings.ts";
import {
  MemoryR2Bucket,
  SqliteD1Database,
  VALID_PNG,
  breakingPacket,
  runtimeBindings,
  storyVersion,
  validAssetMetadata,
} from "./helpers/task-5-fixtures.mjs";

const routePath = new URL(
  "../app/api/media/[digest]/route.ts",
  import.meta.url,
);
const mediaModulePath = new URL("../lib/server/media.ts", import.meta.url);
const routeExists = existsSync(routePath) && existsSync(mediaModulePath);

test("authenticated media route and resolver exist", () => {
  assert.ok(existsSync(routePath), "missing authenticated media route");
  assert.ok(existsSync(mediaModulePath), "missing media resolver");
});

async function loadRoute() {
  return (await import(routePath)).GET;
}

async function publishVisibleAsset({
  status = "verified",
  rightsStatus = "approved",
  secondApprovedSource = false,
} = {}) {
  const db = new SqliteD1Database();
  const media = new MemoryR2Bucket();
  const metadata = await validAssetMetadata();
  const key = `assets/sha256/${metadata.sha256}.png`;
  await media.put(key, VALID_PNG, {
    httpMetadata: { contentType: "image/png" },
    customMetadata: {
      sha256: metadata.sha256,
      mimeType: "image/png",
      byteCount: String(metadata.byte_count),
      width: String(metadata.width),
      height: String(metadata.height),
    },
  });
  db.execute(
    `INSERT INTO assets(sha256, r2_key, mime_type, byte_count, width, height)
     VALUES (?, ?, ?, ?, ?, ?)`,
    metadata.sha256,
    key,
    "image/png",
    metadata.byte_count,
    metadata.width,
    metadata.height,
  );
  db.execute(
    `INSERT INTO asset_sources(
       asset_id, packet_id, canonical_sha256, source_sha256,
       source_byte_count, source_mime_type, source_width, source_height,
       alt_text, source, source_url, rights_basis, rights_status,
       usage_status, dlp_status, sanitization_status, perceptual_dedup_status,
       status, captured_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    metadata.asset_id,
    metadata.packet_id,
    metadata.sha256,
    metadata.source_sha256,
    metadata.source_byte_count,
    metadata.source_mime_type,
    metadata.source_width,
    metadata.source_height,
    "Task 5 editorial image",
    "Bali Zero editorial desk",
    metadata.source_url,
    metadata.rights_basis,
    rightsStatus,
    metadata.usage_status,
    metadata.dlp_status,
    metadata.sanitization_status,
    metadata.perceptual_dedup_status,
    status,
    metadata.captured_at,
  );
  const secondAssetId = `${metadata.asset_id}-second-source`;
  if (secondApprovedSource) {
    db.execute(
      `INSERT INTO asset_sources(
         asset_id, packet_id, canonical_sha256, source_sha256,
         source_byte_count, source_mime_type, source_width, source_height,
         alt_text, source, rights_basis, rights_status, usage_status,
         dlp_status, sanitization_status, perceptual_dedup_status, status,
         captured_at
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      secondAssetId,
      metadata.packet_id,
      metadata.sha256,
      "b".repeat(64),
      metadata.source_byte_count,
      metadata.source_mime_type,
      metadata.source_width,
      metadata.source_height,
      "Second approved editorial source",
      "Independent approved provenance",
      metadata.rights_basis,
      "approved",
      "approved",
      "passed",
      "passed",
      "unique",
      "verified",
      metadata.captured_at,
    );
  }
  const story = storyVersion({ assetDigest: metadata.sha256 });
  const repository = createPublicationRepository(db, {
    now: () => "2026-07-18T01:30:00.000Z",
  });
  const packet = parseStoryPacket(breakingPacket(story));
  const bodyHash = "f".repeat(64);
  await repository.stageBreaking(packet, bodyHash);
  await repository.finalizeBreaking(packet.packet_id);
  return { db, media, metadata, secondAssetId, story };
}

async function getMedia(handler, digest, bindings, authenticated = true) {
  const headers = authenticated
    ? { "oai-authenticated-user-email": "reader@balizero.com" }
    : {};
  const request = new Request(`https://magazine.example/api/media/${digest}`, {
    headers,
  });
  return runWithMagazineBindings(bindings, () =>
    handler(request, { params: Promise.resolve({ digest }) }),
  );
}

test(
  "media route serves only an authenticated visible current association",
  { skip: !routeExists },
  async () => {
    const handler = await loadRoute();
    const { db, media, metadata } = await publishVisibleAsset();
    const bindings = runtimeBindings(db, media);
    const anonymous = await getMedia(handler, metadata.sha256, bindings, false);
    assert.equal(anonymous.status, 401);
    assert.equal((await anonymous.text()).includes(metadata.sha256), false);

    const response = await getMedia(handler, metadata.sha256, bindings);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("content-type"), "image/png");
    assert.equal(
      response.headers.get("content-length"),
      String(VALID_PNG.byteLength),
    );
    assert.equal(response.headers.get("cache-control"), "private, no-store");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(
      response.headers.get("cross-origin-resource-policy"),
      "same-origin",
    );
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), VALID_PNG);
  },
);

test(
  "media route rejects malformed digest and never exposes raw R2 keys",
  { skip: !routeExists },
  async () => {
    const handler = await loadRoute();
    const { db, media, metadata } = await publishVisibleAsset();
    const bindings = runtimeBindings(db, media);
    for (const digest of ["not-a-digest", metadata.sha256.toUpperCase()]) {
      const response = await getMedia(handler, digest, bindings);
      assert.equal(response.status, 404);
      assert.equal((await response.text()).includes("assets/sha256"), false);
    }
  },
);

test(
  "media route denies the next request after story quarantine or asset revocation",
  { skip: !routeExists },
  async () => {
    const handler = await loadRoute();
    const { db, media, metadata, story } = await publishVisibleAsset();
    const bindings = runtimeBindings(db, media);
    assert.equal(
      (await getMedia(handler, metadata.sha256, bindings)).status,
      200,
    );

    db.execute(
      `INSERT INTO audit_events(
         event_id, stream_id, stream_seq, payload_json,
         previous_event_hash, event_hash
       ) VALUES (?, ?, ?, ?, ?, ?)`,
      "audit-media-quarantine",
      `story-visibility:${story.story_id}`,
      1,
      "{}",
      "0".repeat(64),
      "a".repeat(64),
    );
    db.execute(
      `INSERT INTO story_visibility_events(
         story_id, visibility_seq, story_version, intent_id,
         desired_quarantined, audit_event_id
       ) VALUES (?, ?, ?, ?, ?, ?)`,
      story.story_id,
      1,
      story.version,
      "intent-media-quarantine",
      1,
      "audit-media-quarantine",
    );
    assert.equal(
      (await getMedia(handler, metadata.sha256, bindings)).status,
      404,
    );
    assert.equal(
      await runWithMagazineBindings(bindings, () =>
        readStoryDetail(story.slug),
      ),
      null,
    );

    db.execute(
      `INSERT INTO audit_events(
         event_id, stream_id, stream_seq, payload_json,
         previous_event_hash, event_hash
       ) VALUES (?, ?, ?, ?, ?, ?)`,
      "audit-media-release",
      `story-visibility:${story.story_id}`,
      2,
      "{}",
      "a".repeat(64),
      "b".repeat(64),
    );
    db.execute(
      `INSERT INTO story_visibility_events(
         story_id, visibility_seq, story_version, intent_id,
         desired_quarantined, audit_event_id
       ) VALUES (?, ?, ?, ?, ?, ?)`,
      story.story_id,
      2,
      story.version,
      "intent-media-release",
      0,
      "audit-media-release",
    );
    db.execute(
      `INSERT INTO asset_status_events(
         asset_id, status_seq, status, rights_status, reason_code
       ) VALUES (?, ?, ?, ?, ?)`,
      metadata.asset_id,
      1,
      "revoked",
      "denied",
      "rights-revoked",
    );
    assert.equal(
      (await getMedia(handler, metadata.sha256, bindings)).status,
      404,
    );
    const revokedDetail = await runWithMagazineBindings(bindings, () =>
      readStoryDetail(story.slug),
    );
    assert.equal(revokedDetail?.imageProvenance, null);
    assert.ok(revokedDetail?.story.imageAlt.trim());
  },
);

test(
  "canonical media remains eligible while any frozen source provenance is safe",
  { skip: !routeExists },
  async () => {
    const handler = await loadRoute();
    const fixture = await publishVisibleAsset({ secondApprovedSource: true });
    const bindings = runtimeBindings(fixture.db, fixture.media);
    fixture.db.execute(
      `INSERT INTO asset_status_events(
         asset_id, status_seq, status, rights_status, reason_code
       ) VALUES (?, ?, ?, ?, ?)`,
      fixture.metadata.asset_id,
      1,
      "revoked",
      "denied",
      "first-source-revoked",
    );
    assert.equal(
      (await getMedia(handler, fixture.metadata.sha256, bindings)).status,
      200,
    );
    const detail = await runWithMagazineBindings(bindings, () =>
      readStoryDetail(fixture.story.slug),
    );
    assert.equal(
      detail?.imageProvenance?.source,
      "Independent approved provenance",
    );

    fixture.db.execute(
      `INSERT INTO asset_status_events(
         asset_id, status_seq, status, rights_status, reason_code
       ) VALUES (?, ?, ?, ?, ?)`,
      fixture.secondAssetId,
      1,
      "quarantined",
      "approved",
      "second-source-quarantined",
    );
    assert.equal(
      (await getMedia(handler, fixture.metadata.sha256, bindings)).status,
      404,
    );
  },
);

test(
  "media route fails closed on unverified assets and R2 metadata or digest drift",
  { skip: !routeExists },
  async () => {
    const handler = await loadRoute();
    const fixture = await publishVisibleAsset();
    const bindings = runtimeBindings(fixture.db, fixture.media);
    fixture.db.execute(
      "UPDATE asset_sources SET status = 'pending' WHERE asset_id = ?",
      fixture.metadata.asset_id,
    );
    assert.equal(
      (await getMedia(handler, fixture.metadata.sha256, bindings)).status,
      404,
    );

    fixture.db.execute(
      "UPDATE asset_sources SET status = 'verified' WHERE asset_id = ?",
      fixture.metadata.asset_id,
    );
    const stored = fixture.media.objects.get(
      `assets/sha256/${fixture.metadata.sha256}.png`,
    );
    stored.customMetadata.sha256 = "0".repeat(64);
    assert.equal(
      (await getMedia(handler, fixture.metadata.sha256, bindings)).status,
      404,
    );

    stored.customMetadata.sha256 = fixture.metadata.sha256;
    const canonicalKey = `assets/sha256/${fixture.metadata.sha256}.png`;
    const driftedKey = `assets/sha256/${fixture.metadata.sha256}-drift.png`;
    fixture.media.objects.set(
      driftedKey,
      fixture.media.objects.get(canonicalKey),
    );
    fixture.db.execute(
      "UPDATE assets SET r2_key = ? WHERE sha256 = ?",
      driftedKey,
      fixture.metadata.sha256,
    );
    assert.equal(
      (await getMedia(handler, fixture.metadata.sha256, bindings)).status,
      404,
    );

    fixture.db.execute(
      "UPDATE assets SET r2_key = ? WHERE sha256 = ?",
      canonicalKey,
      fixture.metadata.sha256,
    );
    fixture.media.corruptReadBack = true;
    assert.equal(
      (await getMedia(handler, fixture.metadata.sha256, bindings)).status,
      404,
    );
  },
);

test(
  "media and visible provenance fail closed after every eligibility field drifts",
  { skip: !routeExists },
  async () => {
    const handler = await loadRoute();
    const cases = [
      ["alt_text", "   "],
      ["source", "   "],
      ["rights_basis", "unknown"],
      ["rights_status", "unknown"],
      ["usage_status", "unknown"],
      ["dlp_status", "pending"],
      ["sanitization_status", "pending"],
      ["perceptual_dedup_status", "unreviewed"],
      ["status", "pending"],
    ];
    for (const [column, unsafeValue] of cases) {
      const fixture = await publishVisibleAsset();
      const bindings = runtimeBindings(fixture.db, fixture.media);
      fixture.db.execute(
        `UPDATE asset_sources SET ${column} = ? WHERE asset_id = ?`,
        unsafeValue,
        fixture.metadata.asset_id,
      );
      assert.equal(
        (await getMedia(handler, fixture.metadata.sha256, bindings)).status,
        404,
        `${column} media`,
      );
      const detail = await runWithMagazineBindings(bindings, () =>
        readStoryDetail(fixture.story.slug),
      );
      assert.equal(detail?.imageProvenance, null, `${column} provenance`);
      assert.ok(detail?.story.imageAlt.trim(), `${column} fallback alt`);
    }
  },
);

test(
  "media route requires a published story association",
  { skip: !routeExists },
  async () => {
    const handler = await loadRoute();
    const db = new SqliteD1Database();
    const media = new MemoryR2Bucket();
    const metadata = await validAssetMetadata();
    await media.put(`assets/sha256/${metadata.sha256}.png`, VALID_PNG, {
      httpMetadata: { contentType: "image/png" },
      customMetadata: {
        sha256: metadata.sha256,
        mimeType: "image/png",
        byteCount: String(metadata.byte_count),
        width: "1",
        height: "1",
      },
    });
    db.execute(
      `INSERT INTO assets(sha256, r2_key, mime_type, byte_count, width, height)
       VALUES (?, ?, ?, ?, ?, ?)`,
      metadata.sha256,
      `assets/sha256/${metadata.sha256}.png`,
      "image/png",
      metadata.byte_count,
      1,
      1,
    );
    db.execute(
      `INSERT INTO asset_sources(
         asset_id, packet_id, canonical_sha256, source_sha256,
         source_byte_count, source_mime_type, source_width, source_height,
         alt_text, source, rights_status, status, captured_at
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      metadata.asset_id,
      metadata.packet_id,
      metadata.sha256,
      metadata.source_sha256,
      metadata.source_byte_count,
      metadata.source_mime_type,
      metadata.source_width,
      metadata.source_height,
      "",
      "",
      "approved",
      "verified",
      metadata.captured_at,
    );
    const response = await getMedia(
      handler,
      metadata.sha256,
      runtimeBindings(db, media),
    );
    assert.equal(response.status, 404);
  },
);
