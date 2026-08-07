import { describe, expect, it } from "vitest";
import {
  licenseForRisk,
  resolveLicenseType,
  formatTimeframe,
  riskLabelEn,
} from "./kbli-derive";

describe("licenseForRisk (PP28 Pasal 124(4) — license derives from risk)", () => {
  it("maps Tinggi to NIB + Izin (the high-risk codes must not understate to bare NIB)", () => {
    expect(licenseForRisk("Tinggi")).toBe("NIB + Izin");
  });

  it("maps Menengah tiers to NIB + Sertifikat Standar", () => {
    expect(licenseForRisk("Menengah Tinggi")).toBe("NIB + Sertifikat Standar");
    expect(licenseForRisk("Menengah Rendah")).toBe("NIB + Sertifikat Standar");
  });

  it("maps Rendah and unknown to NIB", () => {
    expect(licenseForRisk("Rendah")).toBe("NIB");
    expect(licenseForRisk("")).toBe("NIB");
    expect(licenseForRisk(null)).toBe("NIB");
  });
});

describe("resolveLicenseType (explicit value wins, else derive)", () => {
  it("prefers the explicit perizinan when present", () => {
    expect(resolveLicenseType("NIB dan Sertifikat Standar", "Tinggi")).toBe(
      "NIB dan Sertifikat Standar",
    );
  });

  it("derives from risk when perizinan is empty", () => {
    expect(resolveLicenseType("", "Tinggi")).toBe("NIB + Izin");
    expect(resolveLicenseType(null, "Rendah")).toBe("NIB");
  });

  // A licence NAME cut off mid-sentence is unusable and must not be shown.
  // Measured 2026-08-05: canonical carries `"NIB dan"` on 21 codes — literally
  // "NIB and" — and it reached TEN render sites including the page <title> and
  // the schema.org JSON-LD Google reads.
  it("treats a truncated licence NAME as absent and derives instead", () => {
    expect(resolveLicenseType("NIB dan", "Menengah Tinggi")).toBe(
      "NIB + Sertifikat Standar",
    );
    expect(resolveLicenseType("NIB dan", "Tinggi")).toBe("NIB + Izin");
    expect(
      resolveLicenseType("Sertifikasi Cara Budi Daya Ternak Yang", "Rendah"),
    ).toBe("NIB");
  });

  it("INNOCENCE — a COMPLETE name containing 'dan' is kept untouched", () => {
    // The whole risk of the rule above: "NIB dan Sertifikat Standar" contains
    // `dan` but ends on `Standar`, so it is not truncated and must survive.
    // (Also asserted by the first test in this block, deliberately twice.)
    expect(resolveLicenseType("NIB dan Sertifikat Standar", "Rendah")).toBe(
      "NIB dan Sertifikat Standar",
    );
    expect(resolveLicenseType("NIB dan Izin", "Tinggi")).toBe("NIB dan Izin");
  });

  it("drops only the truncated entries from the array form", () => {
    expect(
      resolveLicenseType(["NIB dan", "NIB dan Sertifikat Standar"], "Tinggi"),
    ).toBe("NIB dan Sertifikat Standar");
    // ...and derives when every entry is unusable, rather than showing nothing.
    expect(resolveLicenseType(["NIB dan", "  "], "Tinggi")).toBe("NIB + Izin");
  });

  // The real dataset stores perizinan as an ARRAY on ~99.5% of scales (often empty []).
  // A naive (perizinan || "").trim() crashed at runtime — these guard that regression.
  it("handles the array form: joins distinct non-empty entries", () => {
    expect(resolveLicenseType(["NIB", "Izin", "NIB"], "Tinggi")).toBe(
      "NIB · Izin",
    );
    expect(
      resolveLicenseType(["", null as unknown as string, "NIB"], "Tinggi"),
    ).toBe("NIB");
  });

  it("handles the array form: derives from risk when the array is empty", () => {
    expect(resolveLicenseType([], "Tinggi")).toBe("NIB + Izin");
    expect(resolveLicenseType([], "Rendah")).toBe("NIB");
  });
});

describe("formatTimeframe (clean display of jangka_waktu)", () => {
  it("renders Otomatis as Instant", () => {
    expect(formatTimeframe("Otomatis")).toBe("Instant");
  });

  it("renders a bare day count and an N-Hari string as working days", () => {
    expect(formatTimeframe("3")).toBe("3 working days");
    expect(formatTimeframe("14")).toBe("14 working days");
    expect(formatTimeframe("5 Hari")).toBe("5 working days");
    expect(formatTimeframe("13 Hari Kerja")).toBe("13 working days");
  });

  it("passes special-regime labels through verbatim", () => {
    expect(formatTimeframe("Sesuai tahapan IUP (ESDM)")).toBe(
      "Sesuai tahapan IUP (ESDM)",
    );
    expect(formatTimeframe("Sesuai ketentuan OJK/BI")).toBe(
      "Sesuai ketentuan OJK/BI",
    );
  });

  it("returns null for empty / dash so the caller picks the placeholder", () => {
    expect(formatTimeframe("")).toBeNull();
    expect(formatTimeframe("-")).toBeNull();
    expect(formatTimeframe(null)).toBeNull();
  });
});

describe("riskLabelEn", () => {
  it("maps the four kategori_risiko values, compound forms first", () => {
    expect(riskLabelEn("Tinggi")).toBe("High");
    expect(riskLabelEn("Rendah")).toBe("Low");
    expect(riskLabelEn("Menengah Tinggi")).toBe("Medium-High");
    expect(riskLabelEn("Menengah Rendah")).toBe("Medium-Low");
  });

  it("returns null for unknown/empty values — never invents a risk", () => {
    expect(riskLabelEn(undefined)).toBeNull();
    expect(riskLabelEn(null)).toBeNull();
    expect(riskLabelEn("")).toBeNull();
    expect(riskLabelEn("Sedang")).toBeNull();
  });
});
