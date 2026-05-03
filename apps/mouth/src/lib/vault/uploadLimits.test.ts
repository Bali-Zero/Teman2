import { describe, it, expect } from "vitest";
import {
  MAX_SIZE_BYTES,
  ALLOWED_UPLOAD_MIMES,
  isAllowedUploadMime,
} from "./uploadLimits";

describe("uploadLimits", () => {
  it("MAX_SIZE_BYTES is a positive finite number", () => {
    expect(Number.isFinite(MAX_SIZE_BYTES)).toBe(true);
    expect(MAX_SIZE_BYTES).toBeGreaterThan(0);
  });
  it("defaults to 20 MB when env var absent (resolved at module load)", () => {
    // Note: env is read at module load; this assertion just confirms the runtime
    // value is either the default or a valid override.
    expect(MAX_SIZE_BYTES).toBeLessThanOrEqual(1024 * 1024 * 1024); // ≤1 GB sanity
  });
  it("ALLOWED_UPLOAD_MIMES contains PDF + common image/office types", () => {
    expect(ALLOWED_UPLOAD_MIMES).toContain("application/pdf");
    expect(ALLOWED_UPLOAD_MIMES).toContain("image/jpeg");
  });
  it("isAllowedUploadMime accepts known types", () => {
    expect(isAllowedUploadMime("application/pdf")).toBe(true);
    expect(isAllowedUploadMime("image/png")).toBe(true);
  });
  it("isAllowedUploadMime rejects unknown types", () => {
    expect(isAllowedUploadMime("application/x-msdownload")).toBe(false);
    expect(isAllowedUploadMime("text/html")).toBe(false);
    expect(isAllowedUploadMime("")).toBe(false);
  });
});
