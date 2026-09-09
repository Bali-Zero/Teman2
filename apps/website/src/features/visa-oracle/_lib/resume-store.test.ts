import { afterEach, describe, expect, it, vi } from "vitest";
import {
  VISA_ORACLE_RESUME_KEY,
  clearInterviewResume,
  loadInterviewResume,
  loadInterviewResumeWithExpiry,
  saveInterviewResume,
  scheduleInterviewResumeCleanup,
} from "./resume-store";

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    values,
  };
}

const NOW = new Date("2026-08-03T10:00:00.000Z");

afterEach(() => vi.useRealTimers());

describe("Visa Oracle resume store", () => {
  it("defaults to short-lived session storage and never writes local storage", () => {
    window.sessionStorage.clear();
    window.localStorage.clear();

    expect(saveInterviewResume({ facts: { category: "work" } })).toBe(true);
    expect(
      window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY),
    ).not.toBeNull();
    expect(window.localStorage.getItem(VISA_ORACLE_RESUME_KEY)).toBeNull();

    clearInterviewResume();
    expect(window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY)).toBeNull();
  });

  it("persists a versioned snapshot and restores it through a validator", () => {
    const storage = memoryStorage();
    const snapshot = {
      schemaVersion: 1,
      attempt: 2,
      facts: { category: "work" },
    };

    expect(
      saveInterviewResume(snapshot, { storage, now: NOW, ttlMs: 5_000 }),
    ).toBe(true);

    const raw = JSON.parse(storage.values.get(VISA_ORACLE_RESUME_KEY) ?? "{}");
    expect(raw).toMatchObject({
      schemaVersion: 1,
      savedAtIso: NOW.toISOString(),
      snapshot,
    });

    expect(
      loadInterviewResume(
        (value) =>
          typeof value === "object" && value !== null
            ? (value as typeof snapshot)
            : null,
        { storage, now: new Date(NOW.getTime() + 1_000) },
      ),
    ).toEqual(snapshot);
    expect(
      loadInterviewResumeWithExpiry((value) => value as typeof snapshot, {
        storage,
        now: new Date(NOW.getTime() + 1_000),
      }),
    ).toEqual({
      snapshot,
      expiresAtIso: new Date(NOW.getTime() + 5_000).toISOString(),
    });
  });

  it("deletes the snapshot at its wall-clock expiry while the tab remains open", () => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    const storage = memoryStorage();
    saveInterviewResume({ facts: {} }, { storage, now: NOW, ttlMs: 1_000 });
    const onExpired = vi.fn();
    const cancel = scheduleInterviewResumeCleanup(
      new Date(NOW.getTime() + 1_000).toISOString(),
      { storage, onExpired },
    );

    vi.advanceTimersByTime(999);
    expect(storage.values.has(VISA_ORACLE_RESUME_KEY)).toBe(true);
    vi.advanceTimersByTime(1);
    expect(storage.values.has(VISA_ORACLE_RESUME_KEY)).toBe(false);
    expect(onExpired).toHaveBeenCalledOnce();
    cancel();
  });

  it("deletes expired, malformed, and flow-invalid data", () => {
    const storage = memoryStorage();
    saveInterviewResume({ facts: {} }, { storage, now: NOW, ttlMs: 1_000 });

    expect(
      loadInterviewResume(() => ({ facts: {} }), {
        storage,
        now: new Date(NOW.getTime() + 1_001),
      }),
    ).toBeNull();
    expect(storage.values.has(VISA_ORACLE_RESUME_KEY)).toBe(false);

    storage.values.set(VISA_ORACLE_RESUME_KEY, "not-json");
    expect(
      loadInterviewResume(() => ({ facts: {} }), { storage, now: NOW }),
    ).toBeNull();
    expect(storage.values.has(VISA_ORACLE_RESUME_KEY)).toBe(false);

    saveInterviewResume({ facts: { smuggled: true } }, { storage, now: NOW });
    expect(loadInterviewResume(() => null, { storage, now: NOW })).toBeNull();
    expect(storage.values.has(VISA_ORACLE_RESUME_KEY)).toBe(false);
  });

  it("fails closed when storage throws", () => {
    const storage = {
      getItem: vi.fn(() => {
        throw new Error("blocked");
      }),
      setItem: vi.fn(() => {
        throw new Error("quota");
      }),
      removeItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };

    expect(saveInterviewResume({}, { storage, now: NOW })).toBe(false);
    expect(loadInterviewResume(() => ({}), { storage, now: NOW })).toBeNull();
    expect(() => clearInterviewResume({ storage })).not.toThrow();
  });
});
