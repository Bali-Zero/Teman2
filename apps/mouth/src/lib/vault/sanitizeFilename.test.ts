import { describe, it, expect } from "vitest";
import { sanitizeFilename } from "./sanitizeFilename";

describe("sanitizeFilename", () => {
  it("leaves normal filenames untouched", () => {
    expect(sanitizeFilename("report.pdf")).toBe("report.pdf");
  });
  it("replaces path separators", () => {
    expect(sanitizeFilename("../../etc/passwd")).toMatch(/^_+etc_passwd$/);
  });
  it("replaces traversal sequences", () => {
    expect(sanitizeFilename("foo..bar.pdf")).toBe("foo_bar.pdf");
  });
  it("strips null bytes and control chars", () => {
    expect(sanitizeFilename("file\x00name.pdf")).toBe("file_name.pdf");
  });
  it("replaces leading dots (no hidden files)", () => {
    expect(sanitizeFilename(".htaccess")).toBe("_htaccess");
  });
  it("caps at 240 chars", () => {
    const long = "a".repeat(500) + ".pdf";
    expect(sanitizeFilename(long).length).toBe(240);
  });
  it("returns unnamed for empty", () => {
    expect(sanitizeFilename("")).toBe("unnamed");
    expect(sanitizeFilename("   ")).toBe("unnamed");
  });
  it("replaces Windows reserved chars", () => {
    expect(sanitizeFilename('file<>:"|?*.txt')).toBe("file_______.txt");
  });
  it("preserves unicode in names", () => {
    expect(sanitizeFilename("rápport-español.pdf")).toBe("rápport-español.pdf");
  });
});
