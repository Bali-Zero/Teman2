import { describe, expect, it } from "vitest";
import fs from "fs";
import path from "path";
import { riskDispute } from "./kbli-risk-dispute";

const ARTIFACT = path.join(process.cwd(), "data", "kbli-risk-disputes.json");

describe("riskDispute — the /kbli/82990 disease reader", () => {
  it("returns the record tiers for a real disputed code", () => {
    // Measured 2026-08-07: the gold editorial claims "low risk at every
    // scale" while the OSS record's per_skala rows are all Tinggi — zero
    // overlap, so this is one of the 30 disputes the compiler emitted.
    expect(riskDispute("82990")).toEqual({ recordTiers: ["Tinggi"] });
  });

  it("returns null for a non-disputed code", () => {
    expect(riskDispute("56101")).toBeNull();
  });

  it("returns null for an unknown code rather than inventing one", () => {
    expect(riskDispute("99999")).toBeNull();
  });
});

describe("the artifact on disk", () => {
  const parsed = JSON.parse(fs.readFileSync(ARTIFACT, "utf-8")) as {
    disputes: Record<
      string,
      { record?: string[]; editorial_mentions?: unknown }
    >;
  };

  it("is generated, and says by what", () => {
    expect(fs.existsSync(ARTIFACT)).toBe(true);
    expect(Object.keys(parsed.disputes).length).toBeGreaterThan(0);
  });

  it("every dispute has a non-empty record side — a dispute with nothing to disclose would not be a dispute", () => {
    for (const [code, entry] of Object.entries(parsed.disputes)) {
      expect(Array.isArray(entry.record), `code ${code}`).toBe(true);
      expect(entry.record!.length, `code ${code}`).toBeGreaterThan(0);
    }
  });
});

// =============================================================================
// RENDER CONTRACT — the editorial side must never reach a render site.
//
// `editorial_mentions` is audit evidence for humans (prose can carry junk: a
// negated tier, a hedge, another code's tier that slipped a guard). Pinned on
// the SOURCE of the two files that render a code's risk-dispute disclosure,
// following the same pattern as the inherited-licensing note pin in
// kbli-provenance.test.ts — grepping the source is what catches a future edit
// that adds `.editorial_mentions` to a template string, not just today's copy.
// =============================================================================

describe("RENDER CONTRACT: editorial_mentions never reaches a render site", () => {
  const LICENSING_SECTION_SOURCE = fs.readFileSync(
    path.join(
      process.cwd(),
      "src",
      "components",
      "kbli",
      "LicensingSection.tsx",
    ),
    "utf-8",
  );
  const FAQ_SOURCE = fs.readFileSync(
    path.join(process.cwd(), "src", "lib", "kbli-faq.ts"),
    "utf-8",
  );

  it("LicensingSection.tsx never references editorial_mentions", () => {
    expect(LICENSING_SECTION_SOURCE).not.toContain("editorial_mentions");
  });

  it("kbli-faq.ts never references editorial_mentions", () => {
    expect(FAQ_SOURCE).not.toContain("editorial_mentions");
  });

  it("LicensingSection.tsx does render the record tiers via recordTiers, not a raw editorial field", () => {
    expect(LICENSING_SECTION_SOURCE).toContain("riskDispute.recordTiers");
  });
});

// =============================================================================
// FAQ integration — buildKbliFaq is the SAME builder that feeds both the
// visible FAQ and the FAQPage JSON-LD Google ingests, so the qualifier has to
// be proven here, not just eyeballed on the page.
// =============================================================================

describe("buildKbliFaq — risk-dispute qualifier", () => {
  it("appends the divergence note when riskDispute is set", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base).toBeDefined();
    const disputed = {
      ...base,
      riskDispute: { recordTiers: ["Tinggi"] },
    } as NonNullable<typeof base>;

    const licenseAnswer = buildKbliFaq(disputed)[1].answer;
    expect(licenseAnswer).toContain("describes a different risk tier");
  });

  it("innocence: omits the note when riskDispute is absent", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base).toBeDefined();
    const undisputed = { ...base, riskDispute: undefined } as NonNullable<
      typeof base
    >;

    const licenseAnswer = buildKbliFaq(undisputed)[1].answer;
    expect(licenseAnswer).not.toContain("describes a different risk tier");
  });
});

// =============================================================================
// The two readers (kbli-data.ts and kbli-data.server.ts) must agree — the
// page body (/kbli/[code]/page.tsx) reads `kbli` from kbli-data.ts's getCode,
// while other surfaces read kbli-data.server.ts's getCode/transformCode. Both
// transforms were wired to riskDispute() independently; if only one had been,
// the disclosure would exist in code but never render on the live page (a
// build-shipped-but-inert bug — superscar #2, "esiste != armato").
// =============================================================================

describe("the two KBLICode readers agree on riskDispute", () => {
  it("across all 30 disputed codes", async () => {
    const { getCode } = await import("./kbli-data");
    const { getCode: getServerCode } = await import("./kbli-data.server");
    const parsed = JSON.parse(fs.readFileSync(ARTIFACT, "utf-8")) as {
      disputes: Record<string, { record: string[] }>;
    };
    const disagreements = Object.keys(parsed.disputes).filter((code) => {
      const a = getCode(code)?.riskDispute;
      const b = getServerCode(code)?.riskDispute;
      return JSON.stringify(a) !== JSON.stringify(b);
    });
    expect(disagreements).toEqual([]);
  });

  it("the page's own reader (kbli-data.ts) actually carries riskDispute for 82990", async () => {
    // The field existing on SOME reader is not the same claim as the page
    // that renders it having it — /kbli/[code]/page.tsx builds `kbli` via
    // getCode() imported from "@/lib/kbli-data", not kbli-data.server.
    const { getCode } = await import("./kbli-data");
    expect(getCode("82990")?.riskDispute).toEqual({
      recordTiers: ["Tinggi"],
    });
  });
});
