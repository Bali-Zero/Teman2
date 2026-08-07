import { describe, expect, it, vi } from "vitest";
import fs from "fs";
import path from "path";
import { riskDispute } from "./kbli-risk-dispute";

const ARTIFACT = path.join(process.cwd(), "data", "kbli-risk-disputes.json");

describe("riskDispute — the /kbli/82990 disease reader", () => {
  it("returns the record tiers for a real disputed code", () => {
    // Measured 2026-08-07: the gold editorial claims "low risk at every
    // scale" while the OSS record's per_skala rows are all Tinggi — zero
    // overlap, so this is one of the 33 disputes the compiler emitted.
    // 82990's l4_bali.status is OK_or_HIGHER_RISK — tier-derived.
    expect(riskDispute("82990")).toEqual({
      recordTiers: ["Tinggi"],
      kind: "zero_overlap",
      baliDependsOnTier: true,
    });
  });

  it("returns the universal_claim kind + flipped baliDependsOnTier for 46100 (round 3)", () => {
    // Round-3 BLOCKER 2: 46100's l4_bali.status is BLOCCATO_DIPENDE_SCOPE,
    // which IS tier-derived per `_l4bali_basis.RISK_DERIVED_STATUSES` — the
    // round-1 hand-typed list had wrongly reported this as false.
    expect(riskDispute("46100")).toEqual({
      recordTiers: ["Menengah Rendah", "Menengah Tinggi", "Rendah", "Tinggi"],
      kind: "universal_claim",
      baliDependsOnTier: true,
    });
  });

  it("returns null for a non-disputed code", () => {
    expect(riskDispute("56101")).toBeNull();
  });

  it("returns null for an unknown code rather than inventing one", () => {
    expect(riskDispute("99999")).toBeNull();
  });
});

// =============================================================================
// FAIL-CLOSED loading (round-3 FIX 4): a missing/malformed artifact used to
// degrade to `{}` silently, so every code would read as "no dispute" and the
// page would ASSERT undisputed facts about codes the compiler had flagged —
// exactly the class of lie this module exists to prevent. Mocks the shared
// `fs` module (same import both this test file and kbli-risk-dispute.ts
// resolve to) rather than touching the real artifact on disk.
// =============================================================================

describe("fail-closed loading", () => {
  it("throws when the artifact file cannot be read", async () => {
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockImplementation(() => {
        throw new Error("ENOENT: no such file or directory");
      });
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("82990")).toThrow(/cannot read risk-dispute artifact/);
    spy.mockRestore();
    _resetRiskDisputeCache();
  });

  it("throws when the artifact is not valid JSON", async () => {
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockReturnValue("{ not valid json");
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("82990")).toThrow(/is not valid JSON/);
    spy.mockRestore();
    _resetRiskDisputeCache();
  });

  it('throws when the payload has no "disputes" object', async () => {
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockReturnValue(JSON.stringify({ _meta: { count: 0 } }));
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("82990")).toThrow(/has no "disputes" object/);
    spy.mockRestore();
    _resetRiskDisputeCache();
  });

  it("innocence: a well-formed artifact still loads without throwing", async () => {
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("82990")).not.toThrow();
  });

  // -- per-entry fail-closed (round 4): the compiler never emits an entry
  // shaped otherwise, so each of these three shapes IS corruption, not a
  // normal empty state — the old behavior silently dropped/defaulted them,
  // exactly the class of lie the file-level fail-closed above exists to
  // prevent, just one level deeper. --------------------------------------

  it("throws on an entry with a missing record", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        disputes: {
          "00000": { kind: "zero_overlap", baliDependsOnTier: false },
        },
      }),
    );
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("00000")).toThrow(
      /entry "00000" has a missing or empty "record"/,
    );
    spy.mockRestore();
    _resetRiskDisputeCache();
  });

  it("throws on an entry with an empty record array", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        disputes: {
          "00000": {
            record: [],
            kind: "zero_overlap",
            baliDependsOnTier: false,
          },
        },
      }),
    );
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("00000")).toThrow(
      /entry "00000" has a missing or empty "record"/,
    );
    spy.mockRestore();
    _resetRiskDisputeCache();
  });

  it("throws on an entry with a missing/unknown kind", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        disputes: {
          "00000": { record: ["Tinggi"], baliDependsOnTier: false },
        },
      }),
    );
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("00000")).toThrow(
      /entry "00000" has a missing or unknown "kind"/,
    );
    spy.mockRestore();
    _resetRiskDisputeCache();
  });

  it("throws on an entry with a missing/non-boolean baliDependsOnTier", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        disputes: { "00000": { record: ["Tinggi"], kind: "zero_overlap" } },
      }),
    );
    const { riskDispute: rd, _resetRiskDisputeCache } =
      await import("./kbli-risk-dispute");
    _resetRiskDisputeCache();
    expect(() => rd("00000")).toThrow(
      /entry "00000" has a missing or non-boolean "baliDependsOnTier"/,
    );
    spy.mockRestore();
    _resetRiskDisputeCache();
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

  it("LicensingSection.tsx pins the zero_overlap wording exactly", () => {
    // Whitespace-normalized: JSX text wraps across lines and prettier owns
    // the exact line breaks (W112) — the CONTENT is what's pinned.
    const normalized = LICENSING_SECTION_SOURCE.replace(/\s+/g, " ");
    expect(normalized).toContain(
      "across its scopes and business scales, while the editorial guide on this page describes a different tier. The two sources have not been reconciled — verify the current tier on oss.go.id before filing.",
    );
  });

  it("LicensingSection.tsx pins the universal_claim wording exactly (round 3, BLOCKER 1)", () => {
    const normalized = LICENSING_SECTION_SOURCE.replace(/\s+/g, " ");
    expect(normalized).toContain(
      "The editorial guide on this page states one risk tier as applying at every business scale, while the licensing rows on this record carry",
    );
    expect(normalized).toContain(
      "across its scopes and scales. The two sources have not been reconciled — verify the current tier on oss.go.id before filing.",
    );
  });

  it("LicensingSection.tsx branches the frame paragraph on riskDispute.kind", () => {
    expect(LICENSING_SECTION_SOURCE).toContain(
      'riskDispute.kind === "universal_claim"',
    );
  });

  it("LicensingSection.tsx gates the Bali-inheritance sentence on baliDependsOnTier", () => {
    expect(LICENSING_SECTION_SOURCE).toContain("riskDispute.baliDependsOnTier");
    expect(LICENSING_SECTION_SOURCE).toContain(
      "The Bali position shown on this page is derived from the",
    );
  });
});

// =============================================================================
// FAQ integration — buildKbliFaq is the SAME builder that feeds both the
// visible FAQ and the FAQPage JSON-LD Google ingests, so the qualifier has to
// be proven here, not just eyeballed on the page.
// =============================================================================

describe("buildKbliFaq — risk-dispute qualifier", () => {
  it("appends the zero_overlap divergence note when riskDispute is set", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base).toBeDefined();
    const disputed = {
      ...base,
      riskDispute: {
        recordTiers: ["Tinggi"],
        kind: "zero_overlap" as const,
        baliDependsOnTier: false,
      },
    } as NonNullable<typeof base>;

    const licenseAnswer = buildKbliFaq(disputed)[1].answer;
    expect(licenseAnswer).toContain("describes a different risk tier");
  });

  it("appends the zero_overlap qualifier with the exact pinned wording", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base).toBeDefined();
    const disputed = {
      ...base,
      riskDispute: {
        recordTiers: ["Tinggi"],
        kind: "zero_overlap" as const,
        baliDependsOnTier: false,
      },
    } as NonNullable<typeof base>;

    const licenseAnswer = buildKbliFaq(disputed)[1].answer;
    expect(licenseAnswer).toContain(
      " Note: the editorial guide on this page describes a different risk tier for this activity; the two sources have not been reconciled — verify the current tier on oss.go.id.",
    );
  });

  // -- round-3 BLOCKER 1: universal_claim gets a DIFFERENT sentence --------
  // Never "describes a different tier" — that's false for these 3 codes.

  it("appends the universal_claim qualifier, never the zero_overlap phrasing", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base).toBeDefined();
    const disputed = {
      ...base,
      riskDispute: {
        recordTiers: ["Menengah Rendah", "Rendah", "Tinggi"],
        kind: "universal_claim" as const,
        baliDependsOnTier: false,
      },
    } as NonNullable<typeof base>;

    const licenseAnswer = buildKbliFaq(disputed)[1].answer;
    expect(licenseAnswer).toContain(
      " The editorial guide describes one tier as applying at every scale, while the record's licensing rows carry Menengah Rendah / Rendah / Tinggi; the two sources have not been reconciled — verify the current tier on oss.go.id before filing.",
    );
    expect(licenseAnswer).not.toContain("describes a different risk tier");
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
    expect(licenseAnswer).not.toContain("applying at every scale");
  });
});

// =============================================================================
// FAQ opening (round-3 FIX 5): a disputed code's answer must not open with
// `licensing[0].riskCategory` stated as flat fact — that IS the disputed
// fact. A non-disputed code's answer is untouched (byte-identical to before
// this round; a broader licensing[0]-single-fact issue on non-disputed
// multi-tier records stays ledgered debt, out of scope here).
// =============================================================================

describe("buildKbliFaq — opening sentence for disputed vs non-disputed codes", () => {
  it("a disputed code's answer never opens with the flat risk-classification sentence", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    // 46100 is a REAL universal_claim dispute in the live artifact.
    const disputed = getCode("46100");
    expect(disputed?.riskDispute).toBeDefined();

    const licenseAnswer = buildKbliFaq(disputed!)[1].answer;
    expect(licenseAnswer).not.toContain("risk classification");
    expect(licenseAnswer).not.toMatch(/^KBLI \d+ has a/);
    expect(licenseAnswer).toContain("The licensing rows on this record list");
  });

  it("a non-disputed code's answer keeps the original flat opening (untouched)", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const undisputed = getCode("56101");
    expect(undisputed?.riskDispute).toBeUndefined();

    const licenseAnswer = buildKbliFaq(undisputed!)[1].answer;
    expect(licenseAnswer).toMatch(/^KBLI 56101 has a .+ risk classification\./);
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
  it("across all disputed codes", async () => {
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
      kind: "zero_overlap",
      baliDependsOnTier: true,
    });
  });
});
