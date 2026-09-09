import { describe, expect, it } from "vitest";
import {
  modeMayRenderPreview,
  modeUsesEngine,
  resolveVisaOracleMode,
} from "./runtime-mode";

describe("Visa Oracle runtime mode", () => {
  it.each(["OFF", "SHADOW", "ENGINE"] as const)(
    "accepts explicit public mode %s",
    (mode) => {
      expect(resolveVisaOracleMode(mode, "production")).toBe(mode);
      expect(resolveVisaOracleMode(mode.toLowerCase(), "production")).toBe(
        mode,
      );
    },
  );

  it("blocks PREVIEW in production even when explicitly configured", () => {
    expect(resolveVisaOracleMode("PREVIEW", "production")).toBe("ENGINE");
    expect(resolveVisaOracleMode("preview", "production")).toBe("ENGINE");
    expect(resolveVisaOracleMode("PREVIEW", "development")).toBe("PREVIEW");
    expect(resolveVisaOracleMode("PREVIEW", "test")).toBe("PREVIEW");
  });

  it("defaults every public runtime to ENGINE", () => {
    expect(resolveVisaOracleMode(undefined, "production")).toBe("ENGINE");
    expect(resolveVisaOracleMode(undefined, "development")).toBe("ENGINE");
    expect(resolveVisaOracleMode("invalid", "production")).toBe("ENGINE");
  });

  it("allows the mock by default only inside tests", () => {
    expect(resolveVisaOracleMode(undefined, "test")).toBe("PREVIEW");
    expect(modeMayRenderPreview("PREVIEW")).toBe(true);
    expect(modeMayRenderPreview("ENGINE")).toBe(false);
    expect(modeMayRenderPreview("SHADOW")).toBe(false);
  });

  it("submits SHADOW to the engine without making preview renderable", () => {
    expect(modeUsesEngine("SHADOW")).toBe(true);
    expect(modeUsesEngine("ENGINE")).toBe(true);
    expect(modeUsesEngine("PREVIEW")).toBe(false);
    expect(modeUsesEngine("OFF")).toBe(false);
  });
});
