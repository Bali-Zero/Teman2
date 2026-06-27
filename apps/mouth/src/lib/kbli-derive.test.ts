import { describe, expect, it } from "vitest";
import {
  licenseForRisk,
  resolveLicenseType,
  formatTimeframe,
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
