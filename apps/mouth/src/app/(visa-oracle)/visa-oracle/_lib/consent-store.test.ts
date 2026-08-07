import { describe, expect, it, vi } from "vitest";
import {
  VISA_ORACLE_CONSENT_KEY,
  VISA_ORACLE_CONSENT_TTL_MS,
  clearLocalConsentReceipt,
  createLocalConsentReceipt,
  loadLocalConsentReceipt,
  saveLocalConsentReceipt,
} from "./consent-store";

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
const SCOPE = {
  state: "SUPPORTED_CANDIDATES",
  assessmentReference: "abcdef1234567890",
} as const;

describe("Visa Oracle local consent store", () => {
  it("defaults to sessionStorage, never localStorage, with the shared two-hour TTL", () => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    const receipt = createLocalConsentReceipt(NOW, "receipt-1", SCOPE);

    expect(saveLocalConsentReceipt(receipt)).toBe(true);
    expect(
      window.sessionStorage.getItem(VISA_ORACLE_CONSENT_KEY),
    ).not.toBeNull();
    expect(window.localStorage.getItem(VISA_ORACLE_CONSENT_KEY)).toBeNull();
    expect(Date.parse(receipt.expiresAtIso) - NOW.getTime()).toBe(
      VISA_ORACLE_CONSENT_TTL_MS,
    );

    clearLocalConsentReceipt();
    expect(window.sessionStorage.getItem(VISA_ORACLE_CONSENT_KEY)).toBeNull();
  });

  it("restores current consent and prunes expired or malformed receipts", () => {
    const storage = memoryStorage();
    const receipt = createLocalConsentReceipt(NOW, "receipt-2", SCOPE);
    saveLocalConsentReceipt(receipt, { storage });

    expect(
      loadLocalConsentReceipt(SCOPE, {
        storage,
        now: new Date(NOW.getTime() + VISA_ORACLE_CONSENT_TTL_MS - 1),
      }),
    ).toEqual(receipt);
    expect(
      loadLocalConsentReceipt(SCOPE, {
        storage,
        now: new Date(NOW.getTime() + VISA_ORACLE_CONSENT_TTL_MS),
      }),
    ).toBeNull();
    expect(storage.values.has(VISA_ORACLE_CONSENT_KEY)).toBe(false);

    storage.values.set(VISA_ORACLE_CONSENT_KEY, '{"schemaVersion":1}');
    expect(loadLocalConsentReceipt(SCOPE, { storage, now: NOW })).toBeNull();
    expect(storage.values.has(VISA_ORACLE_CONSENT_KEY)).toBe(false);
  });

  it("revokes a receipt when the outcome or opaque decision reference changes", () => {
    const storage = memoryStorage();
    const receipt = createLocalConsentReceipt(NOW, "receipt-scoped", SCOPE);
    saveLocalConsentReceipt(receipt, { storage });

    expect(
      loadLocalConsentReceipt(
        { ...SCOPE, assessmentReference: "bbbbbbbbbbbbbbbb" },
        { storage, now: NOW },
      ),
    ).toBeNull();
    expect(storage.values.has(VISA_ORACLE_CONSENT_KEY)).toBe(false);
  });

  it("rejects an extended retention window and fails closed when storage throws", () => {
    const storage = memoryStorage();
    const receipt = createLocalConsentReceipt(NOW, "receipt-3", SCOPE);
    storage.values.set(
      VISA_ORACLE_CONSENT_KEY,
      JSON.stringify({
        ...receipt,
        expiresAtIso: new Date(
          NOW.getTime() + VISA_ORACLE_CONSENT_TTL_MS + 1,
        ).toISOString(),
      }),
    );
    expect(loadLocalConsentReceipt(SCOPE, { storage, now: NOW })).toBeNull();

    const blocked = {
      getItem: vi.fn(() => {
        throw new Error("blocked");
      }),
      setItem: vi.fn(() => {
        throw new Error("blocked");
      }),
      removeItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };
    expect(saveLocalConsentReceipt(receipt, { storage: blocked })).toBe(false);
    expect(
      loadLocalConsentReceipt(SCOPE, { storage: blocked, now: NOW }),
    ).toBeNull();
    expect(() => clearLocalConsentReceipt({ storage: blocked })).not.toThrow();
  });
});
