import assert from "node:assert/strict";
import test from "node:test";

import {
  canonicalizeMachineSignature,
  machineSignatureHeaders,
  verifyMachineRequest,
} from "../lib/server/hmac.ts";
import {
  mediaSecurityHeaders,
  normalizeHttpsEvidenceUrl,
  privateNoStoreHeaders,
} from "../lib/server/security.ts";

class MemoryNonceStore {
  #seen = new Set();

  async insertUnique(keyId, nonce) {
    const key = `${keyId}:${nonce}`;
    if (this.#seen.has(key)) return false;
    this.#seen.add(key);
    return true;
  }
}

const key = "machine-hmac-current-secret";

function env(overrides = {}) {
  return {
    audience: "bali-zero-magazine",
    currentKey: { id: "current", secret: key },
    nextKey: { id: "next", secret: "machine-hmac-next-secret" },
    maxClockSkewSeconds: 300,
    nonceStore: new MemoryNonceStore(),
    now: () => 1_721_260_800_000,
    ...overrides,
  };
}

async function signedRequest({
  body = '{"schema_version":"story.v1"}',
  path = "/api/ingest/story",
  contentType = "application/json",
  timestamp = "1721260800",
  nonce = "nonce-1234567890",
  keyId = "current",
  audience = "bali-zero-magazine",
  signingKey = key,
  method = "POST",
} = {}) {
  const request = new Request(`https://magazine.example${path}`, {
    method,
    headers: { "content-type": contentType },
    body,
  });
  const signedHeaders = await machineSignatureHeaders(request, {
    timestamp,
    nonce,
    keyId,
    audience,
    secret: signingKey,
  });
  for (const [name, value] of Object.entries(signedHeaders)) {
    request.headers.set(name, value);
  }
  return request;
}

test("HMAC canonical input has an unambiguous fixed field order", () => {
  assert.equal(
    canonicalizeMachineSignature({
      method: "POST",
      normalizedPath: "/api/ingest/story",
      contentType: "application/json",
      bodySha256: "a".repeat(64),
      timestamp: "1721260800",
      nonce: "nonce-1234567890",
      keyId: "current",
      audience: "bali-zero-magazine",
    }),
    [
      "POST",
      "/api/ingest/story",
      "application/json",
      "a".repeat(64),
      "1721260800",
      "nonce-1234567890",
      "current",
      "bali-zero-magazine",
    ].join("\n"),
  );
});

test("HMAC verifies exact raw bytes with the current key", async () => {
  const request = await signedRequest();
  const verified = await verifyMachineRequest(request, env());
  assert.equal(
    new TextDecoder().decode(verified.body),
    '{"schema_version":"story.v1"}',
  );
  assert.equal(verified.keyId, "current");
  assert.match(verified.bodySha256, /^[a-f0-9]{64}$/);
});

test("HMAC supports only the configured current and next keys", async () => {
  const request = await signedRequest({
    keyId: "next",
    signingKey: "machine-hmac-next-secret",
    nonce: "nonce-next-123456",
  });
  assert.equal((await verifyMachineRequest(request, env())).keyId, "next");

  const unknown = await signedRequest({
    keyId: "old",
    nonce: "nonce-old-123456",
  });
  await assert.rejects(
    () => verifyMachineRequest(unknown, env()),
    /unknown key ID/,
  );
});

test("HMAC rejects altered raw bytes", async () => {
  const request = await signedRequest();
  const altered = new Request(request.url, {
    method: request.method,
    headers: request.headers,
    body: '{"schema_version": "story.v1"}',
  });
  await assert.rejects(
    () => verifyMachineRequest(altered, env()),
    /invalid signature/,
  );
});

test("HMAC rejects a changed path", async () => {
  const request = await signedRequest();
  const changed = new Request(
    "https://magazine.example/api/ingest/edition",
    request,
  );
  await assert.rejects(
    () => verifyMachineRequest(changed, env()),
    /invalid signature/,
  );
});

test("HMAC rejects wrong content type before handler execution", async () => {
  const request = await signedRequest({ contentType: "text/plain" });
  await assert.rejects(
    () => verifyMachineRequest(request, env()),
    /content type/,
  );
});

test("HMAC rejects stale timestamps", async () => {
  const request = await signedRequest({ timestamp: "1721250000" });
  await assert.rejects(() => verifyMachineRequest(request, env()), /timestamp/);
});

test("HMAC atomically rejects a repeated nonce", async () => {
  const sharedEnv = env();
  await verifyMachineRequest(await signedRequest(), sharedEnv);
  const repeated = await signedRequest();
  await assert.rejects(
    () => verifyMachineRequest(repeated, sharedEnv),
    /nonce already used/,
  );
});

test("HMAC rejects the wrong audience and invalid signature", async () => {
  const wrongAudience = await signedRequest({ audience: "other-service" });
  await assert.rejects(
    () => verifyMachineRequest(wrongAudience, env()),
    /invalid audience/,
  );

  const wrongSignature = await signedRequest({ signingKey: "wrong-secret" });
  await assert.rejects(
    () => verifyMachineRequest(wrongSignature, env()),
    /invalid signature/,
  );
});

test("HMAC security helpers fail closed", () => {
  assert.equal(
    normalizeHttpsEvidenceUrl("https://example.com/a#b"),
    "https://example.com/a#b",
  );
  assert.throws(() => normalizeHttpsEvidenceUrl("http://example.com"), /HTTPS/);
  assert.throws(
    () => normalizeHttpsEvidenceUrl("javascript:alert(1)"),
    /HTTPS/,
  );
  assert.equal(
    privateNoStoreHeaders().get("cache-control"),
    "private, no-store",
  );
  assert.equal(mediaSecurityHeaders().get("x-content-type-options"), "nosniff");
  assert.equal(
    mediaSecurityHeaders().get("cross-origin-resource-policy"),
    "same-origin",
  );
});
