import type { NextRequest } from "next/server";

export const COCKPIT_SESSION_MAX_AGE_SECONDS = 12 * 60 * 60;

const VERSION = 1;
const CLOCK_SKEW_SECONDS = 60;
const MIN_SECRET_CHARACTERS = 32;
const encoder = new TextEncoder();

interface SessionPayload {
  v: number;
  iat: number;
  exp: number;
  nonce: string;
}

interface CreateSessionOptions {
  nowMs?: number;
  maxAgeSeconds?: number;
  nonce?: string;
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new Error("invalid base64url");
  }
  const padded = value
    .replace(/-/g, "+")
    .replace(/_/g, "/")
    .padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function assertSecret(secret: string): void {
  if (secret.trim().length < MIN_SECRET_CHARACTERS) {
    throw new Error("cockpit HMAC key is missing or too short");
  }
}

async function importHmacKey(secret: string): Promise<CryptoKey> {
  assertSecret(secret);
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

async function signPayload(
  secret: string,
  encodedPayload: string,
): Promise<Uint8Array> {
  const key = await importHmacKey(secret);
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(encodedPayload),
  );
  return new Uint8Array(signature);
}

function randomNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return bytesToBase64Url(bytes);
}

export function readCockpitHmacKey(): string | null {
  const secret = process.env.COCKPIT_HMAC_KEY?.trim() ?? "";
  return secret.length >= MIN_SECRET_CHARACTERS ? secret : null;
}

export async function createCockpitSessionToken(
  secret: string,
  options: CreateSessionOptions = {},
): Promise<string> {
  const nowSeconds = Math.floor((options.nowMs ?? Date.now()) / 1000);
  const maxAgeSeconds =
    options.maxAgeSeconds ?? COCKPIT_SESSION_MAX_AGE_SECONDS;
  if (maxAgeSeconds <= 0 || maxAgeSeconds > COCKPIT_SESSION_MAX_AGE_SECONDS) {
    throw new Error("invalid cockpit session lifetime");
  }

  const payload: SessionPayload = {
    v: VERSION,
    iat: nowSeconds,
    exp: nowSeconds + maxAgeSeconds,
    nonce: options.nonce ?? randomNonce(),
  };
  const encodedPayload = bytesToBase64Url(
    encoder.encode(JSON.stringify(payload)),
  );
  const signature = await signPayload(secret, encodedPayload);
  return `${encodedPayload}.${bytesToBase64Url(signature)}`;
}

function isSessionPayload(value: unknown): value is SessionPayload {
  if (!value || typeof value !== "object") return false;
  const payload = value as Partial<SessionPayload>;
  return (
    payload.v === VERSION &&
    Number.isInteger(payload.iat) &&
    Number.isInteger(payload.exp) &&
    typeof payload.nonce === "string" &&
    payload.nonce.length >= 16 &&
    payload.nonce.length <= 64
  );
}

export async function verifyCockpitSessionToken(
  token: string | null | undefined,
  secret: string,
  nowMs: number = Date.now(),
): Promise<boolean> {
  if (!token) return false;
  try {
    const parts = token.split(".");
    if (parts.length !== 2) return false;
    const [encodedPayload, encodedSignature] = parts;
    const payload = JSON.parse(
      new TextDecoder().decode(base64UrlToBytes(encodedPayload)),
    ) as unknown;
    if (!isSessionPayload(payload)) return false;

    const nowSeconds = Math.floor(nowMs / 1000);
    if (payload.iat > nowSeconds + CLOCK_SKEW_SECONDS) return false;
    if (payload.exp <= nowSeconds) return false;
    if (payload.exp <= payload.iat) return false;
    if (payload.exp - payload.iat > COCKPIT_SESSION_MAX_AGE_SECONDS) {
      return false;
    }

    const key = await importHmacKey(secret);
    return await crypto.subtle.verify(
      "HMAC",
      key,
      base64UrlToBytes(encodedSignature),
      encoder.encode(encodedPayload),
    );
  } catch {
    return false;
  }
}

export function readCockpitBearerToken(request: NextRequest): string | null {
  const authorization = request.headers.get("authorization");
  if (!authorization || authorization.includes(",")) return null;
  const match = /^Bearer ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$/.exec(authorization);
  return match?.[1] ?? null;
}

export async function hasValidCockpitSession(
  request: NextRequest,
  nowMs: number = Date.now(),
): Promise<boolean> {
  const secret = readCockpitHmacKey();
  if (!secret) return false;
  return verifyCockpitSessionToken(
    readCockpitBearerToken(request),
    secret,
    nowMs,
  );
}
