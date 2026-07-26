const encoder = new TextEncoder();

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
}

export function hexToBytes(hex: string): Uint8Array {
  if (!/^(?:[a-f0-9]{2})+$/.test(hex))
    throw new TypeError("invalid lowercase hex");
  const bytes = new Uint8Array(hex.length / 2);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    Uint8Array.from(bytes).buffer,
  );
  return bytesToHex(new Uint8Array(digest));
}

export async function hmacSha256Hex(
  secret: string,
  value: string,
): Promise<string> {
  if (secret.length === 0) throw new TypeError("HMAC secret is required");
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(value),
  );
  return bytesToHex(new Uint8Array(signature));
}

export function constantTimeEqualHex(left: string, right: string): boolean {
  let leftBytes: Uint8Array;
  let rightBytes: Uint8Array;
  try {
    leftBytes = hexToBytes(left);
    rightBytes = hexToBytes(right);
  } catch {
    return false;
  }
  const maximumLength = Math.max(leftBytes.length, rightBytes.length);
  let difference = leftBytes.length ^ rightBytes.length;
  for (let index = 0; index < maximumLength; index += 1) {
    difference |= (leftBytes[index] ?? 0) ^ (rightBytes[index] ?? 0);
  }
  return difference === 0;
}

export function normalizeHttpsEvidenceUrl(value: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new TypeError("evidence URL must use HTTPS");
  }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password) {
    throw new TypeError("evidence URL must use HTTPS without credentials");
  }
  return parsed.href;
}

export function privateNoStoreHeaders(initial?: HeadersInit): Headers {
  const headers = new Headers(initial);
  headers.set("Cache-Control", "private, no-store");
  headers.set("X-Content-Type-Options", "nosniff");
  return headers;
}

export function mediaSecurityHeaders(initial?: HeadersInit): Headers {
  const headers = privateNoStoreHeaders(initial);
  headers.set("Cross-Origin-Resource-Policy", "same-origin");
  return headers;
}

export function protectedPageSecurityHeaders(initial?: HeadersInit): Headers {
  const headers = privateNoStoreHeaders(initial);
  headers.set(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      "object-src 'none'",
      "base-uri 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "script-src 'self'",
      "style-src 'self'",
      "img-src 'self'",
      "font-src 'self'",
      "connect-src 'self'",
    ].join("; "),
  );
  return headers;
}
