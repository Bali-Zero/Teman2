import { describe, expect, it } from "vitest";
import { trustedPrimarySourceUrl } from "./trusted-source-url";

describe("trustedPrimarySourceUrl", () => {
  it.each([
    [
      "https://www.imigrasi.go.id/visa/requirements?lang=en#documents",
      "https://www.imigrasi.go.id/visa/requirements?lang=en#documents",
    ],
    ["https://evisa.imigrasi.go.id/", "https://evisa.imigrasi.go.id/"],
    [
      "https://kanwilsultra.imigrasi.go.id/berita/aturan",
      "https://kanwilsultra.imigrasi.go.id/berita/aturan",
    ],
    ["https://kemenimipas.go.id/", "https://kemenimipas.go.id/"],
    [
      "https://www.peraturan.go.id/id/perpres",
      "https://www.peraturan.go.id/id/perpres",
    ],
    [
      "https://peraturan.bpk.go.id/Details/123",
      "https://peraturan.bpk.go.id/Details/123",
    ],
  ])("accepts official HTTPS source %s", (value, expected) => {
    expect(trustedPrimarySourceUrl(value)).toBe(expected);
  });

  it.each([
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "http://imigrasi.go.id/rules",
    "https://imigrasi.go.id/rules",
    "https://peraturan.go.id/rules",
    "https://imigrasi.go.id.evil.example/rules",
    "https://evil-imigrasi.go.id/rules",
    "https://evil.imigrasi.go.id/rules",
    "https://foo.kanwilsultra.imigrasi.go.id/rules",
    "https://imigrasi.go.id@evil.example/rules",
    "https://evil.example@imigrasi.go.id/rules",
    "https://xn--imigrsi-7za.go.id/rules",
    "https://xn--imigrasi-go-id-9tb.example/rules",
    "https://sub.kemenimipas.go.id/rules",
    "https://sub.peraturan.go.id/rules",
    "https://imigrasi.go.id.:443/rules",
    "https://imigrasi.go.id:8443/rules",
    " https://imigrasi.go.id/rules",
  ])("rejects an untrusted or ambiguous source URL: %s", (value) => {
    expect(trustedPrimarySourceUrl(value)).toBeNull();
  });
});
