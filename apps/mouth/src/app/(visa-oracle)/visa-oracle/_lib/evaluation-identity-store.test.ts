import { describe, expect, it, vi } from "vitest";
import {
  VISA_ORACLE_IDENTITY_KEY,
  browserEvaluationIdentityStorage,
  clearEvaluationIdentities,
  getOrCreateEvaluationIdentity,
} from "./evaluation-identity-store";

const NOW = new Date("2026-08-03T12:00:00.000Z");
const HASH = "a".repeat(64);
const IDS = [
  "11111111-1111-4111-8111-111111111111",
  "22222222-2222-4222-8222-222222222222",
  "33333333-3333-4333-8333-333333333333",
  "44444444-4444-4444-8444-444444444444",
  "55555555-5555-4555-8555-555555555555",
  "66666666-6666-4666-8666-666666666666",
];

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    values,
  };
}

describe("evaluation identity store", () => {
  it("uses browser session storage only when the caller explicitly opts in", () => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    let index = 0;

    getOrCreateEvaluationIdentity({
      attempt: 0,
      evaluationHash: HASH,
      now: NOW,
      createId: () => IDS[index++],
    });

    expect(window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY)).toBeNull();
    expect(window.localStorage.getItem(VISA_ORACLE_IDENTITY_KEY)).toBeNull();

    const sessionStorage = browserEvaluationIdentityStorage();
    expect(sessionStorage).not.toBeNull();
    getOrCreateEvaluationIdentity({
      attempt: 0,
      evaluationHash: HASH,
      storage: sessionStorage,
      now: NOW,
      createId: () => IDS[index++],
    });

    expect(
      window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY),
    ).not.toBeNull();
    expect(window.localStorage.getItem(VISA_ORACLE_IDENTITY_KEY)).toBeNull();

    clearEvaluationIdentities();
    expect(window.sessionStorage.getItem(VISA_ORACLE_IDENTITY_KEY)).toBeNull();
  });

  it("reuses assessment and idempotency UUIDs for the same attempt/hash", () => {
    const storage = memoryStorage();
    const createId = vi.fn(() => IDS[createId.mock.calls.length - 1]);
    const first = getOrCreateEvaluationIdentity({
      attempt: 2,
      evaluationHash: HASH,
      storage,
      now: NOW,
      createId,
    });
    const resumed = getOrCreateEvaluationIdentity({
      attempt: 2,
      evaluationHash: HASH,
      storage,
      now: new Date(NOW.getTime() + 1_000),
      createId,
    });

    expect(resumed).toEqual(first);
    expect(createId).toHaveBeenCalledTimes(2);
    expect(
      JSON.stringify(storage.values.get(VISA_ORACLE_IDENTITY_KEY)),
    ).not.toContain("category");
  });

  it("creates a new identity after an edit or a new attempt", () => {
    const storage = memoryStorage();
    let index = 0;
    const createId = () => IDS[index++];
    const first = getOrCreateEvaluationIdentity({
      attempt: 0,
      evaluationHash: HASH,
      storage,
      now: NOW,
      createId,
    });
    const next = getOrCreateEvaluationIdentity({
      attempt: 1,
      evaluationHash: HASH,
      storage,
      now: new Date(NOW.getTime() + 1),
      createId,
    });
    expect(next.idempotencyKey).not.toBe(first.idempotencyKey);
  });

  it("does not renew an old entry when a later identity extends the envelope", () => {
    const storage = memoryStorage();
    let index = 0;
    const createId = () => IDS[index++];
    const first = getOrCreateEvaluationIdentity({
      attempt: 0,
      evaluationHash: HASH,
      storage,
      now: NOW,
      createId,
    });
    getOrCreateEvaluationIdentity({
      attempt: 1,
      evaluationHash: "b".repeat(64),
      storage,
      now: new Date(NOW.getTime() + 60 * 60 * 1_000),
      createId,
    });

    const afterOriginalTtl = getOrCreateEvaluationIdentity({
      attempt: 0,
      evaluationHash: HASH,
      storage,
      now: new Date(NOW.getTime() + 2 * 60 * 60 * 1_000),
      createId,
    });
    expect(afterOriginalTtl.idempotencyKey).not.toBe(first.idempotencyKey);

    const envelope = JSON.parse(
      storage.values.get(VISA_ORACLE_IDENTITY_KEY) ?? "{}",
    ) as { entries?: Record<string, { createdAtIso: string }> };
    expect(
      Object.values(envelope.entries ?? {}).every(
        (entry) => entry.createdAtIso !== NOW.toISOString(),
      ),
    ).toBe(true);
  });

  it("rejects raw/invalid keys and corrupt persisted identities", () => {
    const storage = memoryStorage();
    expect(() =>
      getOrCreateEvaluationIdentity({
        attempt: 0,
        evaluationHash: "raw-facts",
        storage,
        now: NOW,
      }),
    ).toThrow("Invalid evaluation identity key");

    storage.values.set(
      VISA_ORACLE_IDENTITY_KEY,
      JSON.stringify({
        schemaVersion: 1,
        expiresAtIso: "2099-01-01T00:00:00.000Z",
        entries: { injected: { assessmentId: "not-a-uuid" } },
      }),
    );
    let index = 0;
    const identity = getOrCreateEvaluationIdentity({
      attempt: 0,
      evaluationHash: HASH,
      storage,
      now: NOW,
      createId: () => IDS[index++],
    });
    expect(identity.assessmentId).toBe(IDS[0]);
  });

  it("clears all persisted request identities on explicit restart", () => {
    const storage = memoryStorage();
    storage.values.set(VISA_ORACLE_IDENTITY_KEY, "stored");
    clearEvaluationIdentities(storage);
    expect(storage.values.has(VISA_ORACLE_IDENTITY_KEY)).toBe(false);
  });
});
