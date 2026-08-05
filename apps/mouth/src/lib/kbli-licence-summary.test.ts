import { describe, it, expect } from "vitest";
import {
  summariseLicences,
  LICENCE_GAP_LABEL,
  LICENCE_NONE_LABEL,
} from "./kbli-licence-summary";

describe("summariseLicences", () => {
  // GUILT — the defect this file exists for. An empty list on a REGULATED code
  // must never be reported as "None"; 07101 (iron sand mining, REGULATED,
  // risk Tinggi) rendered exactly that in the clipboard export.
  it("never says None for a REGULATED code with no licence rows", () => {
    const out = summariseLicences([], "REGULATED");
    expect(out).toBe(LICENCE_GAP_LABEL);
    expect(out.toLowerCase()).not.toContain("none");
  });

  it.each(["PENDING_REGULATION", "NOT_IN_KBLI_2025", null, undefined])(
    "declares a gap rather than absence for status %s",
    (status) => {
      expect(summariseLicences([], status)).toBe(LICENCE_GAP_LABEL);
    },
  );

  // INNOCENCE — the one status where "none required" is the truth, and the
  // ordinary case where we do hold rows, must both keep working.
  it("reports none required only for NOT_APPLICABLE_OSS", () => {
    expect(summariseLicences([], "NOT_APPLICABLE_OSS")).toBe(
      LICENCE_NONE_LABEL,
    );
  });

  it("joins the licence types it actually holds", () => {
    expect(
      summariseLicences(["NIB dan Izin", "Sertifikat Standar"], "REGULATED"),
    ).toBe("NIB dan Izin, Sertifikat Standar");
  });

  it("keeps the real rows even when the status says none are required", () => {
    expect(summariseLicences(["Izin Usaha"], "NOT_APPLICABLE_OSS")).toBe(
      "Izin Usaha",
    );
  });

  // A list of blanks is an empty list, not a licence named "" — otherwise the
  // join emits a bare comma and reads as two unnamed licences.
  it("treats blank and null entries as no rows at all", () => {
    expect(summariseLicences(["", "   ", null, undefined], "REGULATED")).toBe(
      LICENCE_GAP_LABEL,
    );
  });

  it("drops blanks but keeps the named rows beside them", () => {
    expect(summariseLicences(["", "NIB", null], "REGULATED")).toBe("NIB");
  });
});
