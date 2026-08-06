import { describe, it, expect } from "vitest";
import {
  MAX_SIZE_BYTES,
  ALLOWED_UPLOAD_MIMES,
  UPLOAD_ACCEPT,
  UPLOAD_FORMAT_LABEL,
  isAllowedUploadMime,
} from "./uploadLimits";

describe("uploadLimits", () => {
  it("MAX_SIZE_BYTES is a positive finite number", () => {
    expect(Number.isFinite(MAX_SIZE_BYTES)).toBe(true);
    expect(MAX_SIZE_BYTES).toBeGreaterThan(0);
  });
  it("matches the backend 10 MB default cap", () => {
    expect(MAX_SIZE_BYTES).toBe(10 * 1024 * 1024);
  });
  it("contains only formats parsed by the backend", () => {
    expect(ALLOWED_UPLOAD_MIMES).toEqual([
      "application/pdf",
      "image/jpeg",
      "image/png",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]);
    expect(UPLOAD_ACCEPT).toBe(".pdf,.jpg,.jpeg,.png,.docx");
    expect(UPLOAD_FORMAT_LABEL).toBe("PDF, JPG, PNG, or DOCX up to 10 MB");
  });
  it("isAllowedUploadMime accepts known types", () => {
    expect(isAllowedUploadMime("application/pdf")).toBe(true);
    expect(isAllowedUploadMime("image/png")).toBe(true);
  });
  it("isAllowedUploadMime rejects unknown types", () => {
    expect(isAllowedUploadMime("application/x-msdownload")).toBe(false);
    expect(isAllowedUploadMime("text/html")).toBe(false);
    expect(isAllowedUploadMime("image/webp")).toBe(false);
    expect(isAllowedUploadMime("application/msword")).toBe(false);
    expect(
      isAllowedUploadMime(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      ),
    ).toBe(false);
    expect(isAllowedUploadMime("")).toBe(false);
  });
});
