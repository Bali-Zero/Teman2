export const AUDIT_PUBLICATION_STREAM = "magazine-publication.v1";
export const AUDIT_ZERO_HASH = "0".repeat(64);

export type PublicationOperation = "edition.publish" | "breaking.publish";

export type AuditAnchorBodyV1 = Readonly<{
  schema_version: "audit-anchor.v1";
  anchor_id: string;
  stream_id: typeof AUDIT_PUBLICATION_STREAM;
  stream_seq: string;
  event_hash: string;
  previous_anchor_hash: string;
  observed_at: string;
  key_id: string;
}>;

export type AuditAnchorReceiptV1 = Readonly<{
  body: AuditAnchorBodyV1;
  signature: string;
  anchor_hash: string;
}>;

export type AuditFeedQueryV1 = Readonly<{
  stream_id: typeof AUDIT_PUBLICATION_STREAM;
  after_seq: string;
  checkpoint_hash: string;
  limit: number;
  operation: PublicationOperation;
  packet_id: string;
}>;

const SHA256 = /^[a-f0-9]{64}$/;
const IDENTIFIER = /^[A-Za-z0-9._~-]{1,128}$/;
const UNSIGNED_DECIMAL = /^(?:0|[1-9]\d*)$/;
const MILLISECOND_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
const BASE64URL = /^[A-Za-z0-9_-]{86}$/;
const SIGNATURE_DOMAIN = new TextEncoder().encode("BZM-AUDIT-ANCHOR-V1\0");
const RECORD_DOMAIN = new TextEncoder().encode("BZM-AUDIT-ANCHOR-RECORD-V1\0");

type JsonPrimitive = null | boolean | number | string;
type JsonValue = JsonPrimitive | readonly JsonValue[] | JsonObject;

interface JsonObject {
  readonly [key: string]: JsonValue;
}

function canonicalJson(value: JsonValue): string {
  if (value === null || typeof value === "boolean") return String(value);
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("non-finite JSON number");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(value)
    .sort()
    .map(
      (key) =>
        `${JSON.stringify(key)}:${canonicalJson(
          (value as Readonly<Record<string, JsonValue>>)[key],
        )}`,
    )
    .join(",")}}`;
}

function closedRecord(
  value: unknown,
  keys: readonly string[],
  label: string,
): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${label} must be an object`);
  }
  const record = value as Record<string, unknown>;
  if (Object.keys(record).sort().join(",") !== [...keys].sort().join(",")) {
    throw new TypeError(`${label} has an invalid shape`);
  }
  return record;
}

function stringField(value: unknown, label: string): string {
  if (typeof value !== "string") throw new TypeError(`${label} is invalid`);
  return value;
}

function sequence(value: unknown, allowZero: boolean): string {
  const text = stringField(value, "stream sequence");
  if (!UNSIGNED_DECIMAL.test(text))
    throw new TypeError("invalid stream sequence");
  const number = Number(text);
  if (!Number.isSafeInteger(number) || (!allowZero && number === 0)) {
    throw new TypeError("invalid stream sequence");
  }
  return text;
}

function digest(value: unknown, label: string): string {
  const text = stringField(value, label);
  if (!SHA256.test(text)) throw new TypeError(`${label} is invalid`);
  return text;
}

function exactInstant(value: unknown, label: string): string {
  const text = stringField(value, label);
  if (!MILLISECOND_UTC.test(text) || new Date(text).toISOString() !== text) {
    throw new TypeError(`${label} is invalid`);
  }
  return text;
}

function u64be(value: number): Uint8Array {
  if (!Number.isSafeInteger(value) || value < 0)
    throw new RangeError("invalid U64");
  const bytes = new Uint8Array(8);
  new DataView(bytes.buffer).setBigUint64(0, BigInt(value), false);
  return bytes;
}

function concatenate(parts: readonly Uint8Array[]): Uint8Array {
  const result = new Uint8Array(
    parts.reduce((total, part) => total + part.byteLength, 0),
  );
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.byteLength;
  }
  return result;
}

function ownedBytes(bytes: Uint8Array): Uint8Array<ArrayBuffer> {
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  return copy;
}

function hex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export function decodeBase64Url(
  value: string,
  expectedBytes: number,
): Uint8Array {
  if (value.includes("=") || !/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new TypeError("invalid unpadded base64url");
  }
  let decoded: string;
  try {
    decoded = atob(
      value.replaceAll("-", "+").replaceAll("_", "/") +
        "=".repeat((4 - (value.length % 4)) % 4),
    );
  } catch {
    throw new TypeError("invalid unpadded base64url");
  }
  const canonical = btoa(decoded)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
  if (canonical !== value) throw new TypeError("invalid unpadded base64url");
  const bytes = Uint8Array.from(decoded, (character) =>
    character.charCodeAt(0),
  );
  if (bytes.byteLength !== expectedBytes)
    throw new TypeError("invalid decoded length");
  return bytes;
}

export function parseAuditAnchorReceipt(value: unknown): AuditAnchorReceiptV1 {
  const receipt = closedRecord(
    value,
    ["body", "signature", "anchor_hash"],
    "audit anchor receipt",
  );
  const rawBody = closedRecord(
    receipt.body,
    [
      "schema_version",
      "anchor_id",
      "stream_id",
      "stream_seq",
      "event_hash",
      "previous_anchor_hash",
      "observed_at",
      "key_id",
    ],
    "audit anchor body",
  );
  if (rawBody.schema_version !== "audit-anchor.v1") {
    throw new TypeError("unsupported audit anchor schema");
  }
  if (rawBody.stream_id !== AUDIT_PUBLICATION_STREAM) {
    throw new TypeError("unsupported audit stream");
  }
  const anchorId = stringField(rawBody.anchor_id, "anchor id");
  const keyId = stringField(rawBody.key_id, "key id");
  if (!IDENTIFIER.test(anchorId) || !IDENTIFIER.test(keyId)) {
    throw new TypeError("invalid anchor identity");
  }
  const signature = stringField(receipt.signature, "signature");
  if (!BASE64URL.test(signature))
    throw new TypeError("invalid anchor signature");
  decodeBase64Url(signature, 64);
  return {
    body: {
      schema_version: "audit-anchor.v1",
      anchor_id: anchorId,
      stream_id: AUDIT_PUBLICATION_STREAM,
      stream_seq: sequence(rawBody.stream_seq, false),
      event_hash: digest(rawBody.event_hash, "event hash"),
      previous_anchor_hash: digest(
        rawBody.previous_anchor_hash,
        "previous anchor hash",
      ),
      observed_at: exactInstant(rawBody.observed_at, "observed at"),
      key_id: keyId,
    },
    signature,
    anchor_hash: digest(receipt.anchor_hash, "anchor hash"),
  };
}

export function parseAuditFeedQuery(url: URL): AuditFeedQueryV1 {
  const keys = [...url.searchParams.keys()];
  const expected = [
    "stream_id",
    "after_seq",
    "checkpoint_hash",
    "limit",
    "operation",
    "packet_id",
  ];
  if (
    keys.length !== expected.length ||
    new Set(keys).size !== expected.length ||
    [...keys].sort().join(",") !== [...expected].sort().join(",")
  ) {
    throw new TypeError("invalid audit feed query shape");
  }
  const operation = url.searchParams.get("operation");
  if (operation !== "edition.publish" && operation !== "breaking.publish") {
    throw new TypeError("invalid publication operation");
  }
  const packetId = url.searchParams.get("packet_id") ?? "";
  if (!IDENTIFIER.test(packetId)) throw new TypeError("invalid packet id");
  const limitText = url.searchParams.get("limit") ?? "";
  if (!/^(?:[1-9]|[1-9]\d|100)$/.test(limitText)) {
    throw new TypeError("invalid feed limit");
  }
  if (url.searchParams.get("stream_id") !== AUDIT_PUBLICATION_STREAM) {
    throw new TypeError("invalid feed stream");
  }
  return {
    stream_id: AUDIT_PUBLICATION_STREAM,
    after_seq: sequence(url.searchParams.get("after_seq"), true),
    checkpoint_hash: digest(
      url.searchParams.get("checkpoint_hash"),
      "checkpoint hash",
    ),
    limit: Number(limitText),
    operation,
    packet_id: packetId,
  };
}

export function canonicalizeAnchorBody(body: AuditAnchorBodyV1): Uint8Array {
  return new TextEncoder().encode(canonicalJson(body as unknown as JsonValue));
}

export function buildAnchorSignaturePreimage(
  canonicalBody: Uint8Array,
): Uint8Array {
  return concatenate([
    SIGNATURE_DOMAIN,
    u64be(canonicalBody.byteLength),
    canonicalBody,
  ]);
}

export function buildAnchorHashPreimage(
  canonicalBody: Uint8Array,
  signature: Uint8Array,
): Uint8Array {
  if (signature.byteLength !== 64)
    throw new TypeError("invalid signature length");
  return concatenate([
    RECORD_DOMAIN,
    u64be(canonicalBody.byteLength),
    canonicalBody,
    signature,
  ]);
}

export async function hashAnchorRecord(
  canonicalBody: Uint8Array,
  signature: Uint8Array,
): Promise<string> {
  return hex(
    await crypto.subtle.digest(
      "SHA-256",
      ownedBytes(buildAnchorHashPreimage(canonicalBody, signature)),
    ),
  );
}
