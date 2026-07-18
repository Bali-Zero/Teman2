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
  #expires = new Map();
  #now;

  constructor(now = () => Date.now()) {
    this.#now = now;
  }

  async insertUnique(keyId, nonce, expiresAt) {
    const key = `${keyId}:${nonce}`;
    const existingExpiry = this.#expires.get(key);
    if (existingExpiry !== undefined && existingExpiry > this.#now()) {
      return false;
    }
    this.#expires.set(key, expiresAt);
    return true;
  }

  expirationFor(keyId, nonce) {
    return this.#expires.get(`${keyId}:${nonce}`);
  }
}

const key = "machine-hmac-current-secret";
const NOW_MS = 1_721_260_800_000;
const NOW_SECONDS = NOW_MS / 1000;

function env(overrides = {}) {
  const now = overrides.now ?? (() => NOW_MS);
  return {
    audience: "bali-zero-magazine",
    currentKey: {
      id: "current",
      secret: key,
      notBefore: NOW_SECONDS - 600,
      notAfter: NOW_SECONDS + 600,
    },
    nextKey: {
      id: "next",
      secret: "machine-hmac-next-secret",
      notBefore: NOW_SECONDS - 60,
      notAfter: NOW_SECONDS + 60,
    },
    maxClockSkewSeconds: 300,
    nonceStore: new MemoryNonceStore(now),
    now,
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

test("HMAC enforces bounded current and next key validity", async () => {
  const nextKey = {
    id: "next",
    secret: "machine-hmac-next-secret",
    notBefore: NOW_SECONDS - 10,
    notAfter: NOW_SECONDS + 10,
  };
  const beforeSeconds = nextKey.notBefore - 1;
  const before = await signedRequest({
    keyId: "next",
    signingKey: nextKey.secret,
    nonce: "nonce-before-key-1",
    timestamp: String(beforeSeconds),
  });
  await assert.rejects(
    () =>
      verifyMachineRequest(
        before,
        env({ nextKey, now: () => beforeSeconds * 1000 }),
      ),
    /key is not active/,
  );

  const atStart = await signedRequest({
    keyId: "next",
    signingKey: nextKey.secret,
    nonce: "nonce-key-start-1",
    timestamp: String(nextKey.notBefore),
  });
  assert.equal(
    (
      await verifyMachineRequest(
        atStart,
        env({ nextKey, now: () => nextKey.notBefore * 1000 }),
      )
    ).keyId,
    "next",
  );

  const atEnd = await signedRequest({
    keyId: "next",
    signingKey: nextKey.secret,
    nonce: "nonce-key-end-123",
    timestamp: String(nextKey.notAfter),
  });
  await assert.rejects(
    () =>
      verifyMachineRequest(
        atEnd,
        env({ nextKey, now: () => nextKey.notAfter * 1000 }),
      ),
    /key is not active/,
  );

  const expiredCurrent = await signedRequest({ nonce: "nonce-old-current" });
  await assert.rejects(
    () =>
      verifyMachineRequest(
        expiredCurrent,
        env({
          currentKey: {
            id: "current",
            secret: key,
            notBefore: NOW_SECONDS - 600,
            notAfter: NOW_SECONDS,
          },
        }),
      ),
    /key is not active/,
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

test("HMAC binds allowed content type and audience into the signature", async () => {
  const request = await signedRequest();
  request.headers.set("content-type", "image/png");
  await assert.rejects(
    () => verifyMachineRequest(request, env()),
    /invalid signature/,
  );

  const audienceBound = await signedRequest({ audience: "service-a" });
  audienceBound.headers.set("x-magazine-audience", "service-b");
  await assert.rejects(
    () => verifyMachineRequest(audienceBound, env({ audience: "service-b" })),
    /invalid signature/,
  );
});

test("HMAC binds method and normalized route variants", async () => {
  const signedPost = await signedRequest();
  const changedMethod = new Request(signedPost.url, {
    method: "PUT",
    headers: signedPost.headers,
    body: await signedPost.clone().arrayBuffer(),
  });
  await assert.rejects(
    () => verifyMachineRequest(changedMethod, env()),
    /invalid signature/,
  );

  const variants = [
    ["/api/ingest/story?a=1&b=2", "/api/ingest/story?b=2&a=1"],
    ["/api/ingest/%73tory", "/api/ingest/story"],
    ["/api//ingest/story", "/api/ingest/story"],
    ["/api/ingest/story/", "/api/ingest/story"],
  ];
  for (const [signedPath, changedPath] of variants) {
    const original = await signedRequest({ path: signedPath });
    const changed = new Request(`https://magazine.example${changedPath}`, {
      method: original.method,
      headers: original.headers,
      body: await original.clone().arrayBuffer(),
    });
    await assert.rejects(
      () => verifyMachineRequest(changed, env()),
      /invalid signature/,
      `${signedPath} must remain distinct from ${changedPath}`,
    );
  }

  const dotSegment = await signedRequest({
    path: "/api/ingest/temporary/../story",
  });
  assert.equal(new URL(dotSegment.url).pathname, "/api/ingest/story");
  assert.equal(
    (await verifyMachineRequest(dotSegment, env())).keyId,
    "current",
  );
});

test("HMAC rejects stale timestamps", async () => {
  const request = await signedRequest({ timestamp: "1721250000" });
  await assert.rejects(() => verifyMachineRequest(request, env()), /timestamp/);
});

test("HMAC rejects invalid numeric configuration and the exact timestamp boundary", async () => {
  const invalidEnvironments = [
    env({ maxClockSkewSeconds: Number.NaN }),
    env({ maxClockSkewSeconds: Number.POSITIVE_INFINITY }),
    env({ maxBodyBytes: Number.POSITIVE_INFINITY }),
    env({ now: () => Number.NaN }),
  ];
  for (const [index, invalidEnv] of invalidEnvironments.entries()) {
    const request = await signedRequest({
      nonce: `nonce-invalid-env-${index}`,
    });
    await assert.rejects(
      () => verifyMachineRequest(request, invalidEnv),
      /invalid machine environment/,
    );
  }

  const exactBoundary = await signedRequest({
    timestamp: String(NOW_SECONDS - 300),
    nonce: "nonce-exact-boundary",
  });
  await assert.rejects(
    () => verifyMachineRequest(exactBoundary, env()),
    /timestamp outside allowed window/,
  );

  const store = new MemoryNonceStore(() => NOW_MS);
  const justInside = await signedRequest({
    timestamp: String(NOW_SECONDS - 299),
    nonce: "nonce-inside-boundary",
  });
  await verifyMachineRequest(justInside, env({ nonceStore: store }));
  assert.ok(store.expirationFor("current", "nonce-inside-boundary") > NOW_MS);
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

test("HMAC nonce insertion is atomic under concurrency and expiry-aware", async () => {
  let clock = NOW_MS;
  const now = () => clock;
  const store = new MemoryNonceStore(now);
  const sharedEnv = env({ now, nonceStore: store });
  const first = await signedRequest({ nonce: "nonce-race-123456" });
  const second = await signedRequest({ nonce: "nonce-race-123456" });
  const raced = await Promise.allSettled([
    verifyMachineRequest(first, sharedEnv),
    verifyMachineRequest(second, sharedEnv),
  ]);
  assert.equal(
    raced.filter((result) => result.status === "fulfilled").length,
    1,
  );
  assert.equal(
    raced.filter((result) => result.status === "rejected").length,
    1,
  );

  clock = (NOW_SECONDS + 300) * 1000;
  const reusedAfterExpiry = await signedRequest({
    nonce: "nonce-race-123456",
    timestamp: String(NOW_SECONDS + 300),
  });
  await verifyMachineRequest(reusedAfterExpiry, sharedEnv);
  assert.ok(store.expirationFor("current", "nonce-race-123456") > clock);
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
