import { describe, expect, it } from "vitest";
import { toPanelDetail } from "./kbli-panel-detail";
import type { KBLICode } from "./kbli-types";

/**
 * The projection's job is to hand the client VERDICTS, never the inputs to a
 * verdict. These tests pin that boundary: the fields the panel must not carry
 * stay absent, and the disclosure flags are the ones the server computed.
 */

function code(overrides: Partial<KBLICode> = {}): KBLICode {
  return {
    code: "10111",
    titleId: "Kegiatan Rumah Potong Hewan Ruminansia",
    titleEn: "Ruminant Slaughterhouse",
    description: "A long uraian that must never reach the panel payload.",
    section: "C",
    sectionName: "Manufacturing",
    pma: {
      status: "open",
      maxForeign: 100,
      condition: null,
      isPriority: false,
      note: null,
      source: null,
      // isPmaVerdictVerified demands the whole chain: located status AND an
      // official basis AND a vintage AND a provenance record whose locator and
      // vintage MATCH them. A fixture with only `verificationStatus: located`
      // is not a verified code — this test failed until the fixture said so.
      verificationStatus: "located",
      officialBasis: "Perpres 10/2021 Lampiran III",
      sourceVintage: "2021-03-02",
      capSpecial: false,
      capVerified: true,
      routeTo: null,
      citation: null,
    },
    licensing: [
      {
        scales: ["Mikro"],
        riskCategory: "Menengah Tinggi",
        licenseType: "NIB + Sertifikat Standar",
        requirements: [],
        timeframe: "15",
        obligations: [],
        authority: "Bupati/Walikota",
        fictivePositive: false,
      },
    ],
    transition: {
      mappingStatus: "CODICE_RINUMERATO",
      pp28LicensingSourceCodes: [],
    },
    tier: "bronze",
    keywords: [],
    // Both branches are present because deriveProvenance always emits both;
    // `isLicensingVerificationPending` reads `provenance?.licensing.status`
    // with the optional chain stopping at `provenance`, so a half-populated
    // provenance object throws. Not reachable from real data — noted, not
    // fixed here.
    provenance: {
      pma: {
        status: "located",
        locator: "Perpres 10/2021 Lampiran III",
        vintage: "2021-03-02",
      },
      licensing: { status: "oss_native" },
    } as KBLICode["provenance"],
    ...overrides,
  } as KBLICode;
}

describe("toPanelDetail", () => {
  it("carries the identity and badge inputs the drill-down renders", () => {
    const d = toPanelDetail(code());

    expect(d.code).toBe("10111");
    expect(d.titleEn).toBe("Ruminant Slaughterhouse");
    expect(d.titleId).toBe("Kegiatan Rumah Potong Hewan Ruminansia");
    expect(d.riskCategory).toBe("Menengah Tinggi");
    expect(d.pma.status).toBe("open");
    expect(d.pma.maxForeign).toBe(100);
  });

  it("omits the fields the panel deliberately does not display", () => {
    // Each of these has a measured reason in the module docstring: payload for
    // `description`, and a second-disclosure-surface risk for the other three.
    const d = toPanelDetail(code()) as unknown as Record<string, unknown>;

    expect(d).not.toHaveProperty("description");
    expect(d).not.toHaveProperty("licences");
    expect(d).not.toHaveProperty("authority");
    expect(d).not.toHaveProperty("timeframe");
  });

  it("forwards the PMA verdict as a resolved flag, not as raw provenance", () => {
    const located = toPanelDetail(code());
    const gap = toPanelDetail(
      code({
        pma: { ...code().pma, verificationStatus: "declared_gap" },
      }),
    );

    expect(located.pma.verdictVerified).toBe(true);
    expect(gap.pma.verdictVerified).toBe(false);
    // The client is never handed the input it could re-resolve differently.
    expect(located.pma).not.toHaveProperty("verificationStatus");
  });

  it("survives a code with no licensing rows and no Bali layer", () => {
    const d = toPanelDetail(code({ licensing: [], baliL4: undefined }));

    expect(d.riskCategory).toBeNull();
    expect(d.bali).toEqual({ status: "", blocked: false });
  });

  it("reports the Bali block as a boolean the badge can consume directly", () => {
    const d = toPanelDetail(
      code({
        baliL4: { status: "BLOCKED", blocked: true } as KBLICode["baliL4"],
      }),
    );

    expect(d.bali.status).toBe("BLOCKED");
    expect(d.bali.blocked).toBe(true);
  });
});
