import type { D1DatabaseLike, D1ResultLike } from "./publication-repository.ts";

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

const DOMAIN_TAG = new TextEncoder().encode("BZM-AUDIT-EVENT-V1");
const SHA256 = /^[a-f0-9]{64}$/;
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
