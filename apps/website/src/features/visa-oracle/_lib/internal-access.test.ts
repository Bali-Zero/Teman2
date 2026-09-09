import { afterEach, describe, expect, it } from "vitest";
import {
  INTERNAL_ACCESS_MAX_AGE_SECONDS,
  configuredPin,
  mintInternalAccessToken,
  safeEquals,
  verifyInternalAccessToken,
} from "./internal-access";

const ORIGINAL_PIN = process.env.VISA_ORACLE_INTERNAL_PIN;

function setPin(value: string | undefined): void {
  if (value === undefined) delete process.env.VISA_ORACLE_INTERNAL_PIN;
  else process.env.VISA_ORACLE_INTERNAL_PIN = value;
}

afterEach(() => {
  setPin(ORIGINAL_PIN);
});

const NOW = 1_770_000_000_000;
const LATER = NOW + INTERNAL_ACCESS_MAX_AGE_SECONDS * 1000;

describe("internal access gate", () => {
  describe("guilt — a real unlock is honoured", () => {
    it("accepts a token minted for the configured PIN", () => {
      setPin("2020");
      const token = mintInternalAccessToken("2020", LATER);
      expect(verifyInternalAccessToken(token, NOW)).toBe(true);
    });

    it("keeps accepting it until the moment it expires", () => {
      setPin("2020");
      const token = mintInternalAccessToken("2020", NOW + 1000);
      expect(verifyInternalAccessToken(token, NOW)).toBe(true);
      expect(verifyInternalAccessToken(token, NOW + 999)).toBe(true);
    });
  });

  describe("innocence — everything else is refused", () => {
    it("fails closed when no PIN is configured, even with a real token", () => {
      // The token is minted while a PIN exists, then the env var disappears:
      // a missing PIN must never mean "everybody is internal".
      const token = mintInternalAccessToken("2020", LATER);
      setPin(undefined);
      expect(verifyInternalAccessToken(token, NOW)).toBe(false);
    });

    it("treats a blank/whitespace PIN as unconfigured", () => {
      setPin("   ");
      expect(configuredPin()).toBeNull();
      expect(
        verifyInternalAccessToken(mintInternalAccessToken("   ", LATER), NOW),
      ).toBe(false);
    });

    it("refuses a forged bare flag (the devtools-written cookie)", () => {
      setPin("2020");
      // HttpOnly stops JS READING a cookie, not a person WRITING one.
      expect(verifyInternalAccessToken("1", NOW)).toBe(false);
      expect(verifyInternalAccessToken("true", NOW)).toBe(false);
      expect(verifyInternalAccessToken(`${LATER}.`, NOW)).toBe(false);
      expect(verifyInternalAccessToken(`${LATER}.forged`, NOW)).toBe(false);
    });

    it("refuses an expired token", () => {
      setPin("2020");
      const token = mintInternalAccessToken("2020", NOW - 1);
      expect(verifyInternalAccessToken(token, NOW)).toBe(false);
    });

    it("refuses a token whose expiry was extended after signing", () => {
      setPin("2020");
      const token = mintInternalAccessToken("2020", NOW + 1000);
      const signature = token.slice(token.indexOf(".") + 1);
      expect(verifyInternalAccessToken(`${LATER}.${signature}`, NOW)).toBe(
        false,
      );
    });

    it("refuses tokens minted for a different PIN (rotation revokes)", () => {
      const oldToken = mintInternalAccessToken("2020", LATER);
      setPin("7391");
      expect(verifyInternalAccessToken(oldToken, NOW)).toBe(false);
      expect(
        verifyInternalAccessToken(mintInternalAccessToken("7391", LATER), NOW),
      ).toBe(true);
    });

    it("refuses absent or malformed values", () => {
      setPin("2020");
      expect(verifyInternalAccessToken(undefined, NOW)).toBe(false);
      expect(verifyInternalAccessToken("", NOW)).toBe(false);
      expect(verifyInternalAccessToken(".abc", NOW)).toBe(false);
      expect(verifyInternalAccessToken("notanumber.abc", NOW)).toBe(false);
      expect(verifyInternalAccessToken("99999999999999999999.abc", NOW)).toBe(
        false,
      );
    });
  });

  describe("safeEquals", () => {
    it("matches identical strings and rejects everything else", () => {
      expect(safeEquals("2020", "2020")).toBe(true);
      expect(safeEquals("2020", "2021")).toBe(false);
      expect(safeEquals("2020", "20200")).toBe(false);
      expect(safeEquals("", "")).toBe(true);
    });
  });
});
