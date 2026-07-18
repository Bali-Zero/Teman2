// Node's type-stripping test runner executes the TypeScript source directly.
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import { constantTimeEqualHex, hmacSha256Hex, sha256Hex } from "./security.ts";

export const MACHINE_SIGNATURE_HEADERS = {
  timestamp: "x-magazine-timestamp",
  nonce: "x-magazine-nonce",
  keyId: "x-magazine-key-id",
  audience: "x-magazine-audience",
  signature: "x-magazine-signature",
} as const;

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

export type MachineHmacKey = Readonly<{ id: string; secret: string }>;

export interface MachineNonceStore {
  insertUnique(
    keyId: string,
    nonce: string,
    expiresAt: number,
  ): Promise<boolean>;
}

export type MagazineEnv = Readonly<{
  audience: string;
  currentKey: MachineHmacKey;
  nextKey?: MachineHmacKey;
  maxClockSkewSeconds?: number;
  maxBodyBytes?: number;
  allowedContentTypes?: readonly string[];
  nonceStore: MachineNonceStore;
  now?: () => number;
}>;

export type VerifiedMachineRequest = Readonly<{
  body: Uint8Array;
  bodySha256: string;
  keyId: string;
  nonce: string;
  timestamp: number;
  audience: string;
}>;

export type MachineSigningOptions = Readonly<{
  timestamp: string;
  nonce: string;
  keyId: string;
  audience: string;
  secret: string;
}>;

const DEFAULT_ALLOWED_CONTENT_TYPES = [
  "application/json",
  "image/jpeg",
  "image/png",
  "image/webp",
] as const;
const DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300;
const DEFAULT_MAX_BODY_BYTES = 13 * 1024 * 1024;

function requireHeader(headers: Headers, name: string): string {
  const value = headers.get(name);
  if (value === null || value.length === 0)
    throw new TypeError(`missing ${name} header`);
  if (/[^\x20-\x7e]/.test(value)) throw new TypeError(`invalid ${name} header`);
  return value;
}

function normalizeContentType(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (!/^[a-z0-9!#$&^_.+-]+\/[a-z0-9!#$&^_.+-]+$/.test(normalized)) {
    throw new TypeError("invalid content type");
  }
  return normalized;
}

function normalizeRequestPath(url: string): string {
  const parsed = new URL(url);
  return `${parsed.pathname}${parsed.search}`;
}

function assertCanonicalField(value: string, name: string): void {
  if (value.length === 0 || value.includes("\n") || value.includes("\r")) {
    throw new TypeError(`invalid machine signature ${name}`);
  }
}

export function canonicalizeMachineSignature(
  input: MachineSignatureInput,
): string {
  const fields = [
    input.method,
    input.normalizedPath,
    input.contentType,
    input.bodySha256,
    input.timestamp,
    input.nonce,
    input.keyId,
    input.audience,
  ];
  const names = [
    "method",
    "normalizedPath",
    "contentType",
    "bodySha256",
    "timestamp",
    "nonce",
    "keyId",
    "audience",
  ];
  fields.forEach((field, index) => assertCanonicalField(field, names[index]));
  return fields.join("\n");
}

async function requestBody(
  request: Request,
  maximumBytes: number,
): Promise<Uint8Array> {
  const declaredLength = request.headers.get("content-length");
  if (declaredLength !== null) {
    if (
      !/^\d+$/.test(declaredLength) ||
      Number(declaredLength) > maximumBytes
    ) {
      throw new TypeError("machine request body exceeds size limit");
    }
  }
  const body = new Uint8Array(await request.clone().arrayBuffer());
  if (body.byteLength > maximumBytes)
    throw new TypeError("machine request body exceeds size limit");
  return body;
}

function signatureInput(
  request: Request,
  contentType: string,
  bodySha256: string,
  options: Omit<MachineSigningOptions, "secret">,
): MachineSignatureInput {
  return {
    method: request.method.toUpperCase(),
    normalizedPath: normalizeRequestPath(request.url),
    contentType,
    bodySha256,
    timestamp: options.timestamp,
    nonce: options.nonce,
    keyId: options.keyId,
    audience: options.audience,
  };
}

export async function machineSignatureHeaders(
  request: Request,
  options: MachineSigningOptions,
): Promise<Record<string, string>> {
  const contentType = normalizeContentType(
    requireHeader(request.headers, "content-type"),
  );
  const body = await requestBody(request, DEFAULT_MAX_BODY_BYTES);
  const bodySha256 = await sha256Hex(body);
  const canonical = canonicalizeMachineSignature(
    signatureInput(request, contentType, bodySha256, options),
  );
  return {
    [MACHINE_SIGNATURE_HEADERS.timestamp]: options.timestamp,
    [MACHINE_SIGNATURE_HEADERS.nonce]: options.nonce,
    [MACHINE_SIGNATURE_HEADERS.keyId]: options.keyId,
    [MACHINE_SIGNATURE_HEADERS.audience]: options.audience,
    [MACHINE_SIGNATURE_HEADERS.signature]: await hmacSha256Hex(
      options.secret,
      canonical,
    ),
  };
}

export async function verifyMachineRequest(
  request: Request,
  env: MagazineEnv,
): Promise<VerifiedMachineRequest> {
  const contentType = normalizeContentType(
    requireHeader(request.headers, "content-type"),
  );
  const allowedContentTypes =
    env.allowedContentTypes ?? DEFAULT_ALLOWED_CONTENT_TYPES;
  if (!allowedContentTypes.includes(contentType))
    throw new TypeError("unsupported content type");

  const timestamp = requireHeader(
    request.headers,
    MACHINE_SIGNATURE_HEADERS.timestamp,
  );
  const nonce = requireHeader(request.headers, MACHINE_SIGNATURE_HEADERS.nonce);
  const keyId = requireHeader(request.headers, MACHINE_SIGNATURE_HEADERS.keyId);
  const audience = requireHeader(
    request.headers,
    MACHINE_SIGNATURE_HEADERS.audience,
  );
  const suppliedSignature = requireHeader(
    request.headers,
    MACHINE_SIGNATURE_HEADERS.signature,
  );

  if (!/^\d{10,}$/.test(timestamp))
    throw new TypeError("invalid machine timestamp");
  const timestampSeconds = Number(timestamp);
  if (!Number.isSafeInteger(timestampSeconds))
    throw new TypeError("invalid machine timestamp");
  const nowSeconds = Math.floor((env.now?.() ?? Date.now()) / 1000);
  const maximumSkew = env.maxClockSkewSeconds ?? DEFAULT_MAX_CLOCK_SKEW_SECONDS;
  if (
    maximumSkew <= 0 ||
    Math.abs(nowSeconds - timestampSeconds) > maximumSkew
  ) {
    throw new TypeError("machine timestamp outside allowed window");
  }
  if (!/^[A-Za-z0-9._~-]{16,128}$/.test(nonce))
    throw new TypeError("invalid machine nonce");
  if (audience !== env.audience) throw new TypeError("invalid audience");

  const matchingKey = [env.currentKey, env.nextKey].find(
    (candidate) => candidate?.id === keyId,
  );
  if (!matchingKey) throw new TypeError("unknown key ID");
  if (!/^[a-f0-9]{64}$/.test(suppliedSignature))
    throw new TypeError("invalid signature");

  const body = await requestBody(
    request,
    env.maxBodyBytes ?? DEFAULT_MAX_BODY_BYTES,
  );
  const bodySha256 = await sha256Hex(body);
  const canonical = canonicalizeMachineSignature(
    signatureInput(request, contentType, bodySha256, {
      timestamp,
      nonce,
      keyId,
      audience,
    }),
  );
  const expectedSignature = await hmacSha256Hex(matchingKey.secret, canonical);
  if (!constantTimeEqualHex(expectedSignature, suppliedSignature)) {
    throw new TypeError("invalid signature");
  }

  const expiresAt = (timestampSeconds + maximumSkew) * 1000;
  if (!(await env.nonceStore.insertUnique(keyId, nonce, expiresAt))) {
    throw new TypeError("nonce already used");
  }
  return {
    body,
    bodySha256,
    keyId,
    nonce,
    timestamp: timestampSeconds,
    audience,
  };
}
