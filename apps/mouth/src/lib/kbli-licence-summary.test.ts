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
  // A licence NAME can itself stop mid-sentence. Measured on prod 2026-08-05:
  // the graph holds a licence node literally called "NIB dan" reachable from 10
  // KBLI codes. This line is COPIED into client emails, so the caveat has to
  // travel with it — the name is labelled, never trimmed and never replaced.
  it("labels a licence name that stops mid-sentence, without altering it", () => {
    const out = summariseLicences(["NIB dan"], "REGULATED");
    expect(out).toContain("NIB dan");
    expect(out).toContain("cut off in the official source");
  });

  it("INNOCENCE — a complete name containing 'dan' is copied verbatim", () => {
    expect(summariseLicences(["NIB dan Sertifikat Standar"], "REGULATED")).toBe(
      "NIB dan Sertifikat Standar",
    );
  });

  it("labels only the truncated entry when several are copied together", () => {
    const out = summariseLicences(["NIB dan", "Izin Usaha"], "REGULATED");
    expect(out.match(/cut off in the official source/g)).toHaveLength(1);
    expect(out).toContain("Izin Usaha");
  });
});
