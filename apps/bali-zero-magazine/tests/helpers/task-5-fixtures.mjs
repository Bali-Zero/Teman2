import { readFileSync, readdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { deflateSync } from "node:zlib";

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

function concatBytes(...parts) {
  const combined = new Uint8Array(
    parts.reduce((total, part) => total + part.byteLength, 0),
  );
  let offset = 0;
  for (const part of parts) {
    combined.set(part, offset);
    offset += part.byteLength;
  }
  return combined;
}

function activeMetadataPayload(prefix) {
  return concatBytes(
    new TextEncoder().encode(prefix),
    new TextEncoder().encode("a".repeat(1300)),
    new TextEncoder().encode("<script>alert(1)</script>"),
  );
}

function pngChunk(typeName, data) {
  const type = new TextEncoder().encode(typeName);
  const chunk = new Uint8Array(12 + data.byteLength);
  const view = new DataView(chunk.buffer);
  view.setUint32(0, data.byteLength);
  chunk.set(type, 4);
  chunk.set(data, 8);
  view.setUint32(
    8 + data.byteLength,
    pngCrc32(chunk.subarray(4, 8 + data.byteLength)),
  );
  return chunk;
}

function withPngMetadata(typeName, data) {
  const chunk = pngChunk(typeName, data);
  return concatBytes(
    VALID_PNG.subarray(0, VALID_PNG.byteLength - 12),
    chunk,
    VALID_PNG.subarray(VALID_PNG.byteLength - 12),
  );
}

export const PNG_WITH_ZTXT = withPngMetadata(
  "zTXt",
  concatBytes(
    new TextEncoder().encode("Comment\0\0"),
    new Uint8Array(deflateSync("Bali Zero editorial metadata")),
  ),
);

export const PNG_WITH_ICCP = withPngMetadata(
  "iCCP",
  concatBytes(
    new TextEncoder().encode("sRGB IEC61966-2.1\0\0"),
    new Uint8Array(deflateSync("representative-icc-profile")),
  ),
);

export const PNG_WITH_CABX = withPngMetadata(
  "caBX",
  new TextEncoder().encode("representative-c2pa-assertion"),
);

export const ACTIVE_PNG_TEXT = withPngMetadata(
  "tEXt",
  activeMetadataPayload("Comment\0"),
);

function withJpegMetadata(marker, prefix) {
  const data = activeMetadataPayload(prefix);
  const segment = new Uint8Array(data.byteLength + 4);
  segment.set([0xff, marker], 0);
  new DataView(segment.buffer).setUint16(2, data.byteLength + 2);
  segment.set(data, 4);
  return concatBytes(
    VALID_JPEG.subarray(0, 2),
    segment,
    VALID_JPEG.subarray(2),
  );
}

export const ACTIVE_JPEG_APP = withJpegMetadata(0xe1, "Exif\0\0");
export const ACTIVE_JPEG_COMMENT = withJpegMetadata(0xfe, "Comment\0");
export const JPEG_WITH_XMP = withJpegMetadata(
  0xe1,
  "http://ns.adobe.com/xap/1.0/\0<?xpacket benign?>",
);
export const JPEG_WITH_ICC = withJpegMetadata(
  0xe2,
  "ICC_PROFILE\0\u0001\u0001representative-srgb-profile",
);
export const JPEG_WITH_C2PA = withJpegMetadata(
  0xeb,
  "JUMBF\0representative-c2pa-claim",
);

function riffChunk(typeName, data) {
  const chunk = new Uint8Array(8 + data.byteLength + (data.byteLength & 1));
  chunk.set(new TextEncoder().encode(typeName), 0);
  new DataView(chunk.buffer).setUint32(4, data.byteLength, true);
  chunk.set(data, 8);
  return chunk;
}

function withWebpMetadata(typeName, featureFlag, prefix) {
  const extendedHeader = new Uint8Array(10);
  extendedHeader[0] = featureFlag;
  const body = concatBytes(
    new TextEncoder().encode("WEBP"),
    riffChunk("VP8X", extendedHeader),
    VALID_WEBP.subarray(12),
    riffChunk(typeName, activeMetadataPayload(prefix)),
  );
  const result = new Uint8Array(8 + body.byteLength);
  result.set(new TextEncoder().encode("RIFF"), 0);
  new DataView(result.buffer).setUint32(4, body.byteLength, true);
  result.set(body, 8);
  return result;
}

export const ACTIVE_WEBP_EXIF = withWebpMetadata("EXIF", 0x08, "Exif\0\0");
export const ACTIVE_WEBP_XMP = withWebpMetadata("XMP ", 0x04, "<?xpacket ");

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
  const {
    byte_count: sourceByteCount,
    mime_type: sourceMimeType,
    width: sourceWidth,
    height: sourceHeight,
    ...v2Overrides
  } = overrides;
  delete v2Overrides.sha256;
  const metadata = {
    schema_version: "asset-upload.v2",
    packet_id: "asset-packet-task-5",
    asset_id: "asset-task-5",
    source_sha256: await sha256Hex(bytes),
    source_byte_count: sourceByteCount ?? bytes.byteLength,
    source_mime_type: sourceMimeType ?? "image/png",
    source_width: sourceWidth ?? 1,
    source_height: sourceHeight ?? 1,
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
    ...v2Overrides,
  };
  return Object.defineProperties(metadata, {
    sha256: { value: metadata.source_sha256, enumerable: false },
    byte_count: { value: metadata.source_byte_count, enumerable: false },
    mime_type: { value: metadata.source_mime_type, enumerable: false },
    width: { value: metadata.source_width, enumerable: false },
    height: { value: metadata.source_height, enumerable: false },
  });
}

export async function validAssetMetadataV2(overrides = {}, bytes = VALID_PNG) {
  return validAssetMetadata(
    {
      packet_id: "asset-packet-task-5-v2",
      asset_id: "asset-task-5-v2",
      captured_at: "2026-07-17T20:00:00Z",
      alt_text: "Bali Zero editorial image",
      source_url: "https://balizero.com/editorial/source",
      ...overrides,
    },
    bytes,
  );
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
        legal_effect: "changes-legal-effect",
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
