import type { D1DatabaseLike, D1ResultLike } from "./publication-repository.ts";
import {
  AUDIT_PUBLICATION_STREAM,
  AUDIT_ZERO_HASH,
  buildAnchorSignaturePreimage,
  canonicalizeAnchorBody,
  decodeBase64Url,
  hashAnchorRecord,
  type AuditAnchorReceiptV1,
  type AuditFeedQueryV1,
  type PublicationOperation,
} from "../contracts/audit-anchor.ts";

export type AuditPayload =
  | null
  | boolean
  | number
  | string
  | readonly AuditPayload[]
  | Readonly<{ [key: string]: AuditPayload }>;

export type AuditEventInput = Readonly<{
  event_id: string;
  stream_id: string;
  payload: AuditPayload;
}>;

export type AuditEvent = Readonly<{
  event_id: string;
  stream_id: string;
  stream_seq: number;
  payload_json: string;
  previous_event_hash: string;
  event_hash: string;
}>;

export type AuditHashInput = Readonly<{
  streamId: string;
  streamSeq: number;
  previousEventHash: string;
  payload: AuditPayload;
}>;

type AuditHead = Readonly<{
  stream_seq: number;
  event_hash: string;
}>;

type PublicationBindingRow = Readonly<{
  operation: PublicationOperation;
  packet_id: string;
  event_id: string;
  stream_id: string;
  stream_seq: number;
  event_hash: string;
  previous_event_hash?: string;
}>;

export type PublicationAuditEvent = Readonly<{
  schema_version: "audit-event.v1";
  stream_id: typeof AUDIT_PUBLICATION_STREAM;
  stream_seq: string;
  previous_event_hash: string;
  event_hash: string;
  payload: Readonly<{
    schema_version: "publication-operation.v1";
    operation: PublicationOperation;
    packet_id: string;
  }>;
}>;

export type AuditFeed = Readonly<{
  schema_version: "audit-feed.v1";
  stream_id: typeof AUDIT_PUBLICATION_STREAM;
  checkpoint: Readonly<{ stream_seq: string; event_hash: string }>;
  head: Readonly<{ stream_seq: string; event_hash: string }>;
  events: readonly PublicationAuditEvent[];
  promotion_target: Readonly<{
    operation: PublicationOperation;
    packet_id: string;
    stream_seq: string;
    event_hash: string;
  }> | null;
  next_cursor: Readonly<{ after_seq: string; checkpoint_hash: string }>;
  has_more: boolean;
}>;

type AnchorHeadRow = Readonly<{
  stream_seq: number;
  event_hash: string;
  anchor_hash: string;
}>;

type AnchorReceiptRow = Readonly<{
  anchor_id: string;
  stream_id: string;
  stream_seq: number;
  event_hash: string;
  previous_anchor_hash: string;
  observed_at: string;
  key_id: string;
  signature: string;
  anchor_hash: string;
}>;

type AnchorRegistryKey = Readonly<{
  key_id: string;
  public_key: string;
  not_before: string;
  not_after: string;
  status: "active" | "retained";
}>;

const DOMAIN_TAG = new TextEncoder().encode("BZM-AUDIT-EVENT-V1");
const SHA256 = /^[a-f0-9]{64}$/;
const ANCHOR_IDENTIFIER = /^[A-Za-z0-9._~-]{1,128}$/;
const MILLISECOND_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
const ZERO_HASH = "0".repeat(64);
const LONE_SURROGATE =
  /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:^|[^\uD800-\uDBFF])[\uDC00-\uDFFF]/u;

function canonicalString(value: string): string {
  if (LONE_SURROGATE.test(value)) {
    throw new TypeError("audit payload contains an invalid Unicode string");
  }
  return JSON.stringify(value);
}

function canonicalValue(value: AuditPayload): string {
  if (value === null || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "string") {
    return canonicalString(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new TypeError("audit payload numbers must be finite");
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    const items: string[] = [];
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.hasOwn(value, index)) {
        throw new TypeError("audit payload arrays must not contain holes");
      }
      items.push(canonicalValue(value[index]));
    }
    return `[${items.join(",")}]`;
  }
  if (typeof value === "object") {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new TypeError("audit payload must contain only JSON values");
    }
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) =>
          `${canonicalString(key)}:${canonicalValue(
            (value as Readonly<Record<string, AuditPayload>>)[key],
          )}`,
      )
      .join(",")}}`;
  }
  throw new TypeError("audit payload must contain only JSON values");
}

function normalizedStreamId(streamId: string): string {
  const normalized = streamId.normalize("NFC");
  if (normalized.length === 0) {
    throw new TypeError("audit stream id must not be empty");
  }
  if (LONE_SURROGATE.test(normalized)) {
    throw new TypeError("audit stream id contains invalid Unicode");
  }
  return normalized;
}

function rawHash(hash: string): Uint8Array {
  if (!SHA256.test(hash)) {
    throw new TypeError("audit hashes must be lowercase SHA-256 digests");
  }
  const bytes = new Uint8Array(32);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(hash.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

function u32be(value: number): Uint8Array {
  if (!Number.isSafeInteger(value) || value < 0 || value > 0xffff_ffff) {
    throw new RangeError("audit byte length exceeds U32");
  }
  const bytes = new Uint8Array(4);
  new DataView(bytes.buffer).setUint32(0, value, false);
  return bytes;
}

function u64be(value: number): Uint8Array {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new RangeError("audit sequence or payload length exceeds safe U64");
  }
  const bytes = new Uint8Array(8);
  new DataView(bytes.buffer).setBigUint64(0, BigInt(value), false);
  return bytes;
}

function concatenate(parts: readonly Uint8Array[]): Uint8Array {
  const length = parts.reduce((total, part) => total + part.byteLength, 0);
  const result = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.byteLength;
  }
  return result;
}

function hex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function changedExactlyOnce(result: D1ResultLike | undefined): boolean {
  return result?.meta?.changes === 1;
}

export function canonicalizeAuditPayload(payload: AuditPayload): string {
  return canonicalValue(payload);
}

export function buildAuditEventPreimage(input: AuditHashInput): Uint8Array {
  const streamBytes = new TextEncoder().encode(
    normalizedStreamId(input.streamId),
  );
  const payloadBytes = new TextEncoder().encode(
    canonicalizeAuditPayload(input.payload),
  );
  return concatenate([
    DOMAIN_TAG,
    new Uint8Array([0]),
    u32be(streamBytes.byteLength),
    streamBytes,
    u64be(input.streamSeq),
    rawHash(input.previousEventHash),
    u64be(payloadBytes.byteLength),
    payloadBytes,
  ]);
}

export async function hashAuditEvent(input: AuditHashInput): Promise<string> {
  const preimage = buildAuditEventPreimage(input);
  const digestInput = new Uint8Array(preimage.byteLength);
  digestInput.set(preimage);
  return hex(await crypto.subtle.digest("SHA-256", digestInput));
}

export function createAuditChain(db: D1DatabaseLike): Readonly<{
  appendAuditEvent(input: AuditEventInput): Promise<AuditEvent>;
}> {
  async function appendAuditEvent(input: AuditEventInput): Promise<AuditEvent> {
    if (input.event_id.length === 0) {
      throw new TypeError("audit event id must not be empty");
    }
    const streamId = normalizedStreamId(input.stream_id);
    const head = await db
      .prepare(
        `SELECT stream_seq, event_hash
         FROM audit_stream_heads
         WHERE stream_id = ?`,
      )
      .bind(streamId)
      .first<AuditHead>();
    const expectedSequence = head?.stream_seq ?? 0;
    const previousEventHash = head?.event_hash ?? ZERO_HASH;
    const streamSequence = expectedSequence + 1;
    const payloadJson = canonicalizeAuditPayload(input.payload);
    const eventHash = await hashAuditEvent({
      streamId,
      streamSeq: streamSequence,
      previousEventHash,
      payload: input.payload,
    });

    const insertEvent = db
      .prepare(
        `INSERT INTO audit_events(
           event_id, stream_id, stream_seq, payload_json,
           previous_event_hash, event_hash
         ) VALUES (?, ?, ?, ?, ?, ?)`,
      )
      .bind(
        input.event_id,
        streamId,
        streamSequence,
        payloadJson,
        previousEventHash,
        eventHash,
      );
    const compareAndSwapHead = db
      .prepare(
        `INSERT INTO audit_stream_heads(stream_id, stream_seq, event_hash)
         VALUES (?, ?, ?)
         ON CONFLICT(stream_id) DO UPDATE SET
           stream_seq = CASE
             WHEN audit_stream_heads.stream_seq = ?
              AND audit_stream_heads.event_hash = ?
             THEN excluded.stream_seq
             ELSE 0
           END,
           event_hash = CASE
             WHEN audit_stream_heads.stream_seq = ?
              AND audit_stream_heads.event_hash = ?
             THEN excluded.event_hash
             ELSE audit_stream_heads.event_hash
           END`,
      )
      .bind(
        streamId,
        streamSequence,
        eventHash,
        expectedSequence,
        previousEventHash,
        expectedSequence,
        previousEventHash,
      );

    let results: readonly D1ResultLike[];
    try {
      results = await db.batch([insertEvent, compareAndSwapHead]);
    } catch (error) {
      throw new Error(
        `CAS conflict: audit stream ${streamId} event and head rolled back`,
        { cause: error },
      );
    }
    if (!changedExactlyOnce(results[0]) || !changedExactlyOnce(results[1])) {
      throw new Error(
        `CAS conflict: audit stream ${streamId} affected an unexpected row count`,
      );
    }

    return {
      event_id: input.event_id,
      stream_id: streamId,
      stream_seq: streamSequence,
      payload_json: payloadJson,
      previous_event_hash: previousEventHash,
      event_hash: eventHash,
    };
  }

  return { appendAuditEvent };
}

function publicationPayload(
  operation: PublicationOperation,
  packetId: string,
): AuditPayload {
  return {
    schema_version: "publication-operation.v1",
    operation,
    packet_id: packetId,
  };
}

function publicationEventId(
  operation: PublicationOperation,
  packetId: string,
): string {
  return `publication:${operation}:${packetId}`;
}

async function findPublicationBinding(
  db: D1DatabaseLike,
  operation: PublicationOperation,
  packetId: string,
): Promise<PublicationBindingRow | null> {
  return db
    .prepare(
      `SELECT b.operation, b.packet_id, b.event_id, b.stream_id,
              b.stream_seq, b.event_hash, e.previous_event_hash
       FROM publication_audit_bindings b
       JOIN audit_events e ON e.event_id = b.event_id
       WHERE b.operation = ? AND b.packet_id = ?`,
    )
    .bind(operation, packetId)
    .first<PublicationBindingRow>();
}

export async function ensurePublicationAuditCandidate(
  db: D1DatabaseLike,
  operation: PublicationOperation,
  packetId: string,
): Promise<PublicationBindingRow> {
  const existing = await findPublicationBinding(db, operation, packetId);
  if (existing !== null) return existing;
  const eventId = publicationEventId(operation, packetId);
  let event = await db
    .prepare(
      `SELECT event_id, stream_id, stream_seq, event_hash
       FROM audit_events WHERE event_id = ?`,
    )
    .bind(eventId)
    .first<AuditEvent>();
  if (event === null) {
    try {
      event = await createAuditChain(db).appendAuditEvent({
        event_id: eventId,
        stream_id: AUDIT_PUBLICATION_STREAM,
        payload: publicationPayload(operation, packetId),
      });
    } catch (cause) {
      event = await db
        .prepare(
          `SELECT event_id, stream_id, stream_seq, event_hash
           FROM audit_events WHERE event_id = ?`,
        )
        .bind(eventId)
        .first<AuditEvent>();
      if (event === null) throw cause;
    }
  }
  await db
    .prepare(
      `INSERT OR IGNORE INTO publication_audit_bindings(
         operation, packet_id, event_id, stream_id, stream_seq, event_hash
       ) VALUES (?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      operation,
      packetId,
      eventId,
      AUDIT_PUBLICATION_STREAM,
      event.stream_seq,
      event.event_hash,
    )
    .run();
  const winner = await findPublicationBinding(db, operation, packetId);
  if (
    winner === null ||
    winner.event_id !== eventId ||
    winner.event_hash !== event.event_hash
  ) {
    throw new Error("publication audit binding conflict");
  }
  return winner;
}

export async function readPublicationAuditFeed(
  db: D1DatabaseLike,
  query: AuditFeedQueryV1,
): Promise<AuditFeed> {
  const afterSequence = Number(query.after_seq);
  if (afterSequence === 0) {
    if (query.checkpoint_hash !== AUDIT_ZERO_HASH) {
      throw new Error("audit checkpoint conflict");
    }
  } else {
    const checkpoint = await db
      .prepare(
        `SELECT event_hash FROM audit_events
         WHERE stream_id = ? AND stream_seq = ?`,
      )
      .bind(query.stream_id, afterSequence)
      .first<{ event_hash: string }>();
    if (checkpoint?.event_hash !== query.checkpoint_hash) {
      throw new Error("audit checkpoint conflict");
    }
  }
  const head = await db
    .prepare(
      `SELECT stream_seq, event_hash FROM audit_stream_heads
       WHERE stream_id = ?`,
    )
    .bind(query.stream_id)
    .first<AuditHead>();
  const result = await db
    .prepare(
      `SELECT b.operation, b.packet_id, b.stream_id, b.stream_seq,
              b.event_hash, e.previous_event_hash
       FROM publication_audit_bindings b
       JOIN audit_events e ON e.event_id = b.event_id
       WHERE b.stream_id = ? AND b.stream_seq > ?
       ORDER BY b.stream_seq
       LIMIT ?`,
    )
    .bind(query.stream_id, afterSequence, query.limit)
    .all<PublicationBindingRow>();
  const rows = result.results ?? [];
  const events = rows.map(
    (row): PublicationAuditEvent => ({
      schema_version: "audit-event.v1",
      stream_id: AUDIT_PUBLICATION_STREAM,
      stream_seq: String(row.stream_seq),
      previous_event_hash: row.previous_event_hash ?? AUDIT_ZERO_HASH,
      event_hash: row.event_hash,
      payload: {
        schema_version: "publication-operation.v1",
        operation: row.operation,
        packet_id: row.packet_id,
      },
    }),
  );
  const target = events.find(
    (event) =>
      event.payload.operation === query.operation &&
      event.payload.packet_id === query.packet_id,
  );
  const last = events.at(-1);
  const headSequence = head?.stream_seq ?? 0;
  return {
    schema_version: "audit-feed.v1",
    stream_id: AUDIT_PUBLICATION_STREAM,
    checkpoint: {
      stream_seq: query.after_seq,
      event_hash: query.checkpoint_hash,
    },
    head: {
      stream_seq: String(headSequence),
      event_hash: head?.event_hash ?? AUDIT_ZERO_HASH,
    },
    events,
    promotion_target:
      target === undefined
        ? null
        : {
            operation: target.payload.operation,
            packet_id: target.payload.packet_id,
            stream_seq: target.stream_seq,
            event_hash: target.event_hash,
          },
    next_cursor: {
      after_seq: last?.stream_seq ?? query.after_seq,
      checkpoint_hash: last?.event_hash ?? query.checkpoint_hash,
    },
    has_more:
      (last === undefined ? afterSequence : Number(last.stream_seq)) <
      headSequence,
  };
}

function parseRegistry(raw: string | undefined): Readonly<{
  registryVersion: string;
  keys: readonly AnchorRegistryKey[];
}> {
  if (raw === undefined) throw new TypeError("anchor key registry is required");
  const parsed: unknown = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new TypeError("invalid anchor key registry");
  }
  const record = parsed as Record<string, unknown>;
  if (
    Object.keys(record).sort().join(",") !==
      "keys,registry_version,schema_version" ||
    record.schema_version !== "audit-anchor-key-registry.v1" ||
    typeof record.registry_version !== "string" ||
    !/^[A-Za-z0-9._~-]{1,64}$/.test(record.registry_version) ||
    !Array.isArray(record.keys) ||
    record.keys.length === 0 ||
    record.keys.length > 16
  ) {
    throw new TypeError("invalid anchor key registry");
  }
  const keys = record.keys.map((value): AnchorRegistryKey => {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      throw new TypeError("invalid anchor registry key");
    }
    const key = value as Record<string, unknown>;
    if (
      Object.keys(key).sort().join(",") !==
        "key_id,not_after,not_before,public_key,status" ||
      typeof key.key_id !== "string" ||
      !ANCHOR_IDENTIFIER.test(key.key_id) ||
      typeof key.public_key !== "string" ||
      typeof key.not_before !== "string" ||
      typeof key.not_after !== "string" ||
      (key.status !== "active" && key.status !== "retained")
    ) {
      throw new TypeError("invalid anchor registry key");
    }
    decodeBase64Url(key.public_key, 32);
    const notBefore = new Date(key.not_before);
    const notAfter = new Date(key.not_after);
    if (
      !MILLISECOND_UTC.test(key.not_before) ||
      !MILLISECOND_UTC.test(key.not_after) ||
      Number.isNaN(notBefore.valueOf()) ||
      Number.isNaN(notAfter.valueOf()) ||
      notBefore.toISOString() !== key.not_before ||
      notAfter.toISOString() !== key.not_after ||
      notAfter <= notBefore
    ) {
      throw new TypeError("invalid anchor registry key lifetime");
    }
    return {
      key_id: key.key_id,
      public_key: key.public_key,
      not_before: key.not_before,
      not_after: key.not_after,
      status: key.status,
    };
  });
  if (new Set(keys.map((key) => key.key_id)).size !== keys.length) {
    throw new TypeError("duplicate anchor key id");
  }
  return { registryVersion: record.registry_version, keys };
}

export async function verifyAuditAnchorReceipt(
  receipt: AuditAnchorReceiptV1,
  registryRaw: string | undefined,
): Promise<void> {
  const registry = parseRegistry(registryRaw);
  if (registry.registryVersion.length === 0)
    throw new TypeError("invalid registry");
  const key = registry.keys.find((item) => item.key_id === receipt.body.key_id);
  if (key === undefined) throw new TypeError("unknown anchor key");
  const observed = new Date(receipt.body.observed_at);
  if (
    observed < new Date(key.not_before) ||
    observed >= new Date(key.not_after)
  ) {
    throw new TypeError("anchor key is outside its retained lifetime");
  }
  const canonicalBody = canonicalizeAnchorBody(receipt.body);
  const signature = new Uint8Array(decodeBase64Url(receipt.signature, 64));
  const rawPublicKey = new Uint8Array(decodeBase64Url(key.public_key, 32));
  const publicKey = await crypto.subtle.importKey(
    "raw",
    rawPublicKey,
    { name: "Ed25519" },
    false,
    ["verify"],
  );
  if (
    !(await crypto.subtle.verify(
      { name: "Ed25519" },
      publicKey,
      signature,
      new Uint8Array(buildAnchorSignaturePreimage(canonicalBody)),
    ))
  ) {
    throw new TypeError("invalid anchor signature");
  }
  if (
    (await hashAnchorRecord(canonicalBody, signature)) !== receipt.anchor_hash
  ) {
    throw new TypeError("invalid anchor hash");
  }
}

function receiptMatches(
  row: AnchorReceiptRow,
  receipt: AuditAnchorReceiptV1,
): boolean {
  const body = receipt.body;
  return (
    row.anchor_id === body.anchor_id &&
    row.stream_id === body.stream_id &&
    row.stream_seq === Number(body.stream_seq) &&
    row.event_hash === body.event_hash &&
    row.previous_anchor_hash === body.previous_anchor_hash &&
    row.observed_at === body.observed_at &&
    row.key_id === body.key_id &&
    row.signature === receipt.signature &&
    row.anchor_hash === receipt.anchor_hash
  );
}

async function findReceiptCollision(
  db: D1DatabaseLike,
  receipt: AuditAnchorReceiptV1,
): Promise<AnchorReceiptRow | null> {
  return db
    .prepare(
      `SELECT anchor_id, stream_id, stream_seq, event_hash,
              previous_anchor_hash, observed_at, key_id, signature, anchor_hash
       FROM audit_anchor_receipts
       WHERE anchor_id = ? OR anchor_hash = ? OR (stream_id = ? AND stream_seq = ?)`,
    )
    .bind(
      receipt.body.anchor_id,
      receipt.anchor_hash,
      receipt.body.stream_id,
      Number(receipt.body.stream_seq),
    )
    .first<AnchorReceiptRow>();
}

export async function blockAuditPromotions(
  db: D1DatabaseLike,
  reason: string,
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO audit_promotion_block(singleton_id, blocked, reason, updated_at)
       VALUES (1, 1, ?, ?)
       ON CONFLICT(singleton_id) DO UPDATE SET
         blocked = 1, reason = excluded.reason, updated_at = excluded.updated_at`,
    )
    .bind(reason, new Date().toISOString())
    .run();
}

export async function acceptAuditAnchor(
  db: D1DatabaseLike,
  receipt: AuditAnchorReceiptV1,
): Promise<"created" | "replay"> {
  const collision = await findReceiptCollision(db, receipt);
  if (collision !== null) {
    if (receiptMatches(collision, receipt)) return "replay";
    throw new Error("audit anchor identity conflict");
  }
  const head = await db
    .prepare(
      `SELECT stream_seq, event_hash, anchor_hash FROM audit_anchor_heads
       WHERE stream_id = ?`,
    )
    .bind(receipt.body.stream_id)
    .first<AnchorHeadRow>();
  if (
    receipt.body.previous_anchor_hash !==
      (head?.anchor_hash ?? AUDIT_ZERO_HASH) ||
    Number(receipt.body.stream_seq) <= (head?.stream_seq ?? 0)
  ) {
    throw new Error("audit anchor chain conflict");
  }
  const target = await db
    .prepare(
      `SELECT b.operation, b.packet_id, b.event_id, b.stream_id,
              b.stream_seq, b.event_hash
       FROM publication_audit_bindings b
       JOIN audit_events e ON e.event_id = b.event_id
       WHERE b.stream_id = ? AND b.stream_seq = ?
         AND b.event_hash = ? AND e.event_hash = b.event_hash`,
    )
    .bind(
      receipt.body.stream_id,
      Number(receipt.body.stream_seq),
      receipt.body.event_hash,
    )
    .first<PublicationBindingRow>();
  if (target === null) throw new Error("anchor target is not canonical");
  const now = new Date().toISOString();
  await db.batch([
    db
      .prepare(
        `INSERT INTO audit_anchor_receipts(
           anchor_id, stream_id, stream_seq, event_hash,
           previous_anchor_hash, observed_at, key_id, signature, anchor_hash
         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(
        receipt.body.anchor_id,
        receipt.body.stream_id,
        Number(receipt.body.stream_seq),
        receipt.body.event_hash,
        receipt.body.previous_anchor_hash,
        receipt.body.observed_at,
        receipt.body.key_id,
        receipt.signature,
        receipt.anchor_hash,
      ),
    db
      .prepare(
        `INSERT INTO audit_anchor_heads(
           stream_id, stream_seq, event_hash, anchor_hash, updated_at
         ) VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(stream_id) DO UPDATE SET
           stream_seq = excluded.stream_seq,
           event_hash = excluded.event_hash,
           anchor_hash = excluded.anchor_hash,
           updated_at = excluded.updated_at`,
      )
      .bind(
        receipt.body.stream_id,
        Number(receipt.body.stream_seq),
        receipt.body.event_hash,
        receipt.anchor_hash,
        now,
      ),
    db
      .prepare(
        `INSERT INTO audit_promotion_permits(
           operation, packet_id, stream_id, stream_seq,
           event_hash, anchor_hash, status
         ) VALUES (?, ?, ?, ?, ?, ?, 'permitted')`,
      )
      .bind(
        target.operation,
        target.packet_id,
        target.stream_id,
        target.stream_seq,
        target.event_hash,
        receipt.anchor_hash,
      ),
    db
      .prepare(
        `INSERT INTO audit_promotion_block(singleton_id, blocked, reason, updated_at)
         VALUES (1, 0, 'anchor_accepted', ?)
         ON CONFLICT(singleton_id) DO UPDATE SET
           blocked = 0, reason = excluded.reason, updated_at = excluded.updated_at`,
      )
      .bind(now),
  ]);
  return "created";
}

export async function isPromotionAuthorized(
  db: D1DatabaseLike,
  operation: PublicationOperation,
  packetId: string,
): Promise<boolean> {
  const packet = await db
    .prepare(
      `SELECT publication_state FROM publication_packets
       WHERE packet_id = ?`,
    )
    .bind(packetId)
    .first<{ publication_state: string }>();
  // An exact published replay is not a new promotion and remains idempotent.
  if (packet?.publication_state === "published") return true;
  const block = await db
    .prepare("SELECT blocked FROM audit_promotion_block WHERE singleton_id = 1")
    .first<{ blocked: number }>();
  if (block?.blocked === 1) return false;
  const permit = await db
    .prepare(
      `SELECT status FROM audit_promotion_permits
       WHERE operation = ? AND packet_id = ?`,
    )
    .bind(operation, packetId)
    .first<{ status: string }>();
  return permit?.status === "permitted";
}

export async function consumePromotionPermit(
  db: D1DatabaseLike,
  operation: PublicationOperation,
  packetId: string,
): Promise<void> {
  await db
    .prepare(
      `UPDATE audit_promotion_permits
       SET status = 'consumed', consumed_at = ?
       WHERE operation = ? AND packet_id = ? AND status = 'permitted'`,
    )
    .bind(new Date().toISOString(), operation, packetId)
    .run();
}
