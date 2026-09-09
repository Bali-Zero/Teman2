import { describe, expect, it } from "vitest";
import { prepareEvaluationRequest } from "./evaluation-request";
import { clearEvaluationIdentities } from "./evaluation-identity-store";

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
  };
}

function deterministicHash(value: string): Promise<string> {
  let marker = 0;
  for (const character of value)
    marker = (marker * 33 + character.charCodeAt(0)) >>> 0;
  return Promise.resolve(marker.toString(16).padStart(8, "0").repeat(8));
}

describe("Visa Oracle durable evaluation request", () => {
  it("replays a byte-identical body and key after reload with an advanced clock", async () => {
    const storage = memoryStorage();
    let idIndex = 0;
    const shared = {
      facts: {
        category: "tourism",
        stay_days: "30",
        review_gate: "none",
      },
      attempt: 4,
      storage,
      createId: () => IDS[idIndex++],
      hash: deterministicHash,
    } as const;
    const first = await prepareEvaluationRequest({
      ...shared,
      now: new Date("2026-08-03T01:00:00.000Z"),
    });
    const reload = await prepareEvaluationRequest({
      ...shared,
      now: new Date("2026-08-03T02:00:00.000Z"),
    });

    expect(reload.identity.idempotencyKey).toBe(first.identity.idempotencyKey);
    expect(JSON.stringify(reload.request)).toBe(JSON.stringify(first.request));
    expect(reload.request.collected_at).toBe(first.identity.createdAtIso);
    expect(idIndex).toBe(2);
  });

  it("deduplicates identical wire input but separates review flags and facts", async () => {
    const storage = memoryStorage();
    let idIndex = 0;
    const prepare = (facts: Record<string, string>) =>
      prepareEvaluationRequest({
        facts,
        attempt: 0,
        storage,
        now: new Date("2026-08-03T01:00:00.000Z"),
        createId: () => IDS[idIndex++],
        hash: deterministicHash,
      });

    const pep = await prepare({
      category: "tourism",
      stay_days: "30",
      review_gate: "pep_or_sanctions",
    });
    const pepAgain = await prepare({
      category: "tourism",
      stay_days: "30",
      review_gate: "pep_or_sanctions",
    });
    const health = await prepare({
      category: "tourism",
      stay_days: "30",
      review_gate: "health_flag",
    });
    const otherCategory = await prepare({
      category: "business",
      stay_days: "30",
      review_gate: "pep_or_sanctions",
    });

    expect(pepAgain.identity.idempotencyKey).toBe(pep.identity.idempotencyKey);
    expect(health.request.facts).toEqual(pep.request.facts);
    expect(health.identity.idempotencyKey).not.toBe(
      pep.identity.idempotencyKey,
    );
    expect(otherCategory.identity.idempotencyKey).not.toBe(
      pep.identity.idempotencyKey,
    );
  });

  it("rotates assessment and key only after an explicit product retry", async () => {
    const storage = memoryStorage();
    let idIndex = 0;
    const options = {
      facts: { category: "tourism", stay_days: "30" },
      attempt: 0,
      storage,
      now: new Date("2026-08-03T01:00:00.000Z"),
      createId: () => IDS[idIndex++],
      hash: deterministicHash,
    } as const;
    const first = await prepareEvaluationRequest(options);
    clearEvaluationIdentities(storage);
    const explicitRetry = await prepareEvaluationRequest(options);

    expect(explicitRetry.evaluationHash).toBe(first.evaluationHash);
    expect(explicitRetry.identity.assessmentId).not.toBe(
      first.identity.assessmentId,
    );
    expect(explicitRetry.identity.idempotencyKey).not.toBe(
      first.identity.idempotencyKey,
    );
  });
});
