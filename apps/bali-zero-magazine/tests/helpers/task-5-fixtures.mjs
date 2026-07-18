import { readFileSync, readdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

import { machineSignatureHeaders } from "../../lib/server/hmac.ts";
import { sha256Hex } from "../../lib/server/security.ts";

export const MACHINE_AUDIENCE = "bali-zero-magazine";
export const MACHINE_KEY_ID = "task-5-current";
export const MACHINE_SECRET = "task-5-machine-hmac-secret";

class SqliteD1Statement {
  constructor(owner, sql, values = []) {
    this.owner = owner;
    this.sql = sql;
    this.values = values;
  }

  bind(...values) {
    return new SqliteD1Statement(this.owner, this.sql, values);
  }

  runSync() {
    const result = this.owner.sqlite.prepare(this.sql).run(...this.values);
    return {
      success: true,
      results: [],
      meta: { changes: Number(result.changes) },
    };
  }

  async run() {
    return this.runSync();
  }

  async first() {
    return this.owner.sqlite.prepare(this.sql).get(...this.values) ?? null;
  }

  async all() {
    return {
      success: true,
      results: this.owner.sqlite.prepare(this.sql).all(...this.values),
      meta: { changes: 0 },
    };
  }
}

export class SqliteD1Database {
  constructor() {
    this.sqlite = new DatabaseSync(":memory:");
    this.sqlite.exec("PRAGMA foreign_keys = ON");
    const migrationDirectory = new URL("../../drizzle/", import.meta.url);
    for (const filename of readdirSync(migrationDirectory)
      .filter((name) => /^\d+.*\.sql$/.test(name))
      .sort()) {
      const migration = readFileSync(
        new URL(filename, migrationDirectory),
        "utf8",
      ).replaceAll("--> statement-breakpoint", "");
      this.sqlite.exec(migration);
    }
  }

  prepare(sql) {
    return new SqliteD1Statement(this, sql);
  }

  async batch(statements) {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const results = statements.map((statement) => statement.runSync());
      this.sqlite.exec("COMMIT");
      return results;
    } catch (error) {
      this.sqlite.exec("ROLLBACK");
      throw error;
    }
  }

  execute(sql, ...values) {
    return this.sqlite.prepare(sql).run(...values);
  }

  get(sql, ...values) {
    return this.sqlite.prepare(sql).get(...values) ?? null;
  }
}

function cloneMetadata(metadata) {
  return metadata === undefined ? undefined : { ...metadata };
}

export class MemoryR2Bucket {
  constructor() {
    this.objects = new Map();
    this.putCalls = [];
    this.corruptReadBack = false;
  }

  async put(key, value, options = {}) {
    if (options.onlyIf?.etagDoesNotMatch === "*" && this.objects.has(key)) {
      return null;
    }
    const bytes = new Uint8Array(
      value instanceof ArrayBuffer
        ? value
        : await new Response(value).arrayBuffer(),
    );
    this.putCalls.push(key);
    this.objects.set(key, {
      bytes: Uint8Array.from(bytes),
      httpMetadata: cloneMetadata(options.httpMetadata),
      customMetadata: cloneMetadata(options.customMetadata),
    });
    return this.head(key);
  }

  async head(key) {
    const stored = this.objects.get(key);
    if (stored === undefined) return null;
    return {
      key,
      size: stored.bytes.byteLength,
      httpMetadata: cloneMetadata(stored.httpMetadata),
      customMetadata: cloneMetadata(stored.customMetadata),
    };
  }

  async get(key) {
    const stored = this.objects.get(key);
    if (stored === undefined) return null;
    const bytes = Uint8Array.from(stored.bytes);
    if (this.corruptReadBack && bytes.length > 0) bytes[bytes.length - 1] ^= 1;
    return {
      key,
      size: bytes.byteLength,
      httpMetadata: cloneMetadata(stored.httpMetadata),
      customMetadata: cloneMetadata(stored.customMetadata),
      async arrayBuffer() {
        return bytes.buffer.slice(
          bytes.byteOffset,
          bytes.byteOffset + bytes.byteLength,
        );
      },
    };
  }
}

export function runtimeBindings(db, media = new MemoryR2Bucket()) {
  const nowSeconds = Math.floor(Date.now() / 1000);
  return {
    DB: db,
    MEDIA: media,
    ACTOR_KEY_SECRET: "task-5-actor-key-secret",
    ROLE_ALLOWLIST_JSON: JSON.stringify({
      version: "roles.task-5.v1",
      analysts: [],
      operators: [],
    }),
    MACHINE_HMAC_AUDIENCE: MACHINE_AUDIENCE,
    MACHINE_HMAC_CURRENT_KEY_JSON: JSON.stringify({
      id: MACHINE_KEY_ID,
      secret: MACHINE_SECRET,
      notBefore: nowSeconds - 300,
      notAfter: nowSeconds + 3_600,
    }),
  };
}

let nonceSequence = 0;

export async function signedMachineRequest({
  path,
  body,
  contentType = "application/json",
  admission = true,
  metadata,
  nonce,
  signingSecret = MACHINE_SECRET,
}) {
  const headers = new Headers({ "content-type": contentType });
  if (admission) {
    headers.set("oai-sites-authorization", "Bearer task-5-dispatch-token");
  }
  if (metadata !== undefined) {
    headers.set("x-magazine-asset-metadata", JSON.stringify(metadata));
  }
  const request = new Request(`https://magazine.example${path}`, {
    method: "POST",
    headers,
    body,
  });
  nonceSequence += 1;
  const signedHeaders = await machineSignatureHeaders(request, {
    timestamp: String(Math.floor(Date.now() / 1000)),
    nonce: nonce ?? `task-5-nonce-${String(nonceSequence).padStart(8, "0")}`,
    keyId: MACHINE_KEY_ID,
    audience: MACHINE_AUDIENCE,
    secret: signingSecret,
    signedHeaderNames:
      metadata === undefined ? [] : ["x-magazine-asset-metadata"],
  });
  for (const [name, value] of Object.entries(signedHeaders)) {
    request.headers.set(name, value);
  }
  return request;
}

export const VALID_PNG = Uint8Array.from(
  Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  ),
);

export const VALID_JPEG = Uint8Array.from(
  Buffer.from(
    "/9j/4AAQSkZJRgABAQAASABIAAD/4QBMRXhpZgAATU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAAB//8AAKACAAQAAAABAAAAAaADAAQAAAABAAAAAQAAAAD/7QA4UGhvdG9zaG9wIDMuMAA4QklNBAQAAAAAAAA4QklNBCUAAAAAABDUHYzZjwCyBOmACZjs+EJ+/8AACwgAAQABAQERAP/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/bAEMAAgICAgICAwICAwUDAwMFBgUFBQUGCAYGBgYGCAoICAgICAgKCgoKCgoKCgwMDAwMDA4ODg4ODw8PDw8PDw8PD//dAAQAAf/aAAgBAQAAPwD8A6//2Q==",
    "base64",
  ),
);

export const VALID_WEBP = Uint8Array.from(
  Buffer.from("UklGRhoAAABXRUJQVlA4TA4AAAAvAAAAEM1VICIC0f+IBA==", "base64"),
);

function pngCrc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function pngVariant(bytes) {
  const type = new TextEncoder().encode("tEXt");
  const data = new TextEncoder().encode("Comment\0task-5-variant");
  const chunk = new Uint8Array(12 + data.byteLength);
  new DataView(chunk.buffer).setUint32(0, data.byteLength);
  chunk.set(type, 4);
  chunk.set(data, 8);
  new DataView(chunk.buffer).setUint32(
    8 + data.byteLength,
    pngCrc32(chunk.subarray(4, 8 + data.byteLength)),
  );
  const variant = new Uint8Array(bytes.byteLength + chunk.byteLength);
  variant.set(bytes.subarray(0, bytes.byteLength - 12));
  variant.set(chunk, bytes.byteLength - 12);
  variant.set(
    bytes.subarray(bytes.byteLength - 12),
    bytes.byteLength - 12 + chunk.byteLength,
  );
  return variant;
}

export const VALID_PNG_VARIANT = pngVariant(VALID_PNG);

function corruptPngCompressedPayload(bytes) {
  const corrupted = Uint8Array.from(bytes);
  let offset = 8;
  while (offset < corrupted.byteLength) {
    const view = new DataView(
      corrupted.buffer,
      corrupted.byteOffset,
      corrupted.byteLength,
    );
    const length = view.getUint32(offset);
    const type = new TextDecoder().decode(
      corrupted.subarray(offset + 4, offset + 8),
    );
    if (type === "IDAT") {
      corrupted[offset + 8] ^= 0xff;
      view.setUint32(
        offset + 8 + length,
        pngCrc32(corrupted.subarray(offset + 4, offset + 8 + length)),
      );
      return corrupted;
    }
    offset += 12 + length;
  }
  throw new Error("PNG fixture has no IDAT chunk");
}

export const MALFORMED_PNG = corruptPngCompressedPayload(VALID_PNG);
export const MALFORMED_JPEG = Uint8Array.from([
  0xff, 0xd8, 0xff, 0xc0, 0x00, 0x0b, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01, 0x01,
  0x11, 0x00, 0xff, 0xd9,
]);
export const MALFORMED_WEBP = (() => {
  const corrupted = Uint8Array.from(VALID_WEBP);
  corrupted[25] ^= 0xff;
  return corrupted;
})();

export async function validAssetMetadata(overrides = {}, bytes = VALID_PNG) {
  return {
    schema_version: "asset-upload.v1",
    packet_id: "asset-packet-task-5",
    asset_id: "asset-task-5",
    sha256: await sha256Hex(bytes),
    byte_count: bytes.byteLength,
    mime_type: "image/png",
    width: 1,
    height: 1,
    captured_at: "2026-07-18T01:00:00Z",
    alt_text: "A verified editorial image",
    source: "Bali Zero editorial desk",
    source_url: null,
    rights_basis: "internal-owned",
    rights_status: "approved",
    usage_status: "approved",
    dlp_status: "passed",
    sanitization_status: "passed",
    perceptual_dedup_status: "unique",
    ...overrides,
  };
}

export function seedSourceSystem(db) {
  db.execute(
    `INSERT INTO source_systems(
       system_id, display_name, expected_cadence_seconds, readiness, health,
       updated_at
     ) VALUES (?, ?, ?, ?, ?, ?)`,
    "intel-lake",
    "Intel Lake",
    300,
    "required",
    "healthy",
    "2026-07-18T01:00:00Z",
  );
}

export function collectorRun(overrides = {}) {
  return {
    schema_version: "collector-run.v1",
    run_id: "collector-run-task-5",
    system_id: "intel-lake",
    collector_id: "routing",
    started_at: "2026-07-18T00:00:00Z",
    completed_at: "2026-07-18T00:05:00Z",
    status: "healthy",
    freshness: "fresh",
    items_seen: 42,
    items_eligible: 7,
    source_count: 18,
    unreachable_source_count: 2,
    watermark: "task-5-watermark",
    verified_at: "2026-07-18T00:05:02Z",
    ...overrides,
  };
}

function evidence(suffix = "task-5") {
  return {
    evidence_id: `evidence-${suffix}`,
    root_source_id: `root-${suffix}`,
    canonical_url: "https://example.go.id/regulation",
    publisher: "Example Authority",
    document_citation: "Regulation 1/2026",
    published_at: "2026-07-17T20:00:00Z",
    retrieved_at: "2026-07-17T21:00:00Z",
    source_type: "official",
    primary_document_status: "verified",
    root_resolution_status: "resolved",
    independence_verdict: "independent",
    evidence_note: "The authority published the effective date.",
    upstream_root_source_ids: [],
    syndication_group_fingerprint: `sg-${suffix}`,
    independence_ruleset_version: "independence.v1",
    independence_reason: "issuing-authority-primary-document",
    counts_toward_breaking: true,
  };
}

export function storyVersion({
  suffix = "task-5",
  version = 1,
  expectedCurrentVersion = 0,
  assetDigest,
} = {}) {
  return {
    story_id: `story-${suffix}`,
    version,
    expected_current_version: expectedCurrentVersion,
    slug: `important-regulation-${suffix}`,
    language: "en",
    domain: "compliance",
    severity: "high",
    lifecycle_state: "verified",
    first_seen_at: "2026-07-17T20:00:00Z",
    event_occurred_at: "2026-07-17T19:30:00Z",
    updated_at: "2026-07-17T21:00:00Z",
    title: "An important regulation changed",
    deck: "The official source confirms the effective date.",
    summary: "A concise sanitized summary.",
    why_it_matters: "Operators should review affected deadlines.",
    curiosity_text: null,
    score_components: {
      editorial: 0.9,
      impact: 0.9,
      freshness: 0.8,
      evidence: 1,
      diversity: 0.5,
    },
    claims: [
      {
        claim_id: `claim-${suffix}`,
        claim_kind: "fact",
        normalized_text: "The regulation has an effective date.",
        numeric_value: null,
        numeric_unit: null,
        as_of: "2026-07-18",
        evidence_ids: [`evidence-${suffix}`],
        breaking_gate: "official-primary",
      },
    ],
    evidence_refs: [evidence(suffix)],
    contributing_system_ids: ["regulatory-watcher"],
    coverage_state: "full",
    confidence: "high",
    asset_digests: assetDigest === undefined ? [] : [assetDigest],
    adapter_version: "adapter.v1",
    ruleset_version: "rules.v1",
  };
}

export function breakingPacket(story, overrides = {}) {
  return {
    schema_version: "story.v1",
    packet_id: `packet-breaking-${story.story_id}`,
    publication_target: "breaking",
    expected_breaking_revision: 0,
    publication_state: "building",
    verified_at: "2026-07-17T21:01:00Z",
    story,
    ...overrides,
  };
}

export function editionPacket(story, overrides = {}) {
  return {
    schema_version: "edition.v1",
    packet_id: `packet-edition-${story.story_id}`,
    edition_date: "2026-07-18",
    edition_revision: 1,
    expected_current_revision: 0,
    expected_breaking_revision: 0,
    edition_kind: "standard",
    publication_state: "building",
    coverage_state: "complete",
    readiness_cutoff: "2026-07-18T00:15:00Z",
    verified_at: "2026-07-18T00:16:00Z",
    editor_version: "editor.v1",
    ruleset_version: "rules.v1",
    collector_run_ids: [],
    stories: [story],
    placements: [
      {
        story_id: story.story_id,
        version: story.version,
        section: "compliance",
        order: 1,
        lead: true,
      },
    ],
    breaking_story_ids: [],
    referenced_claim_ids: story.claims.map((claim) => claim.claim_id),
    referenced_evidence_ids: story.evidence_refs.map(
      (item) => item.evidence_id,
    ),
    asset_digests: story.asset_digests,
    coverage_gaps: [],
    reader_notices: [],
    ...overrides,
  };
}

export function instrumentSingleBodyRead(request) {
  const originalArrayBuffer = request.arrayBuffer.bind(request);
  let reads = 0;
  request.arrayBuffer = async () => {
    reads += 1;
    return originalArrayBuffer();
  };
  request.clone = () => {
    throw new Error("machine route must not clone the request body");
  };
  return () => reads;
}
