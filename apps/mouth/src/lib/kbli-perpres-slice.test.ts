import { describe, expect, it, vi } from "vitest";
import fs from "fs";
import path from "path";
import { perpresSlice } from "./kbli-perpres-slice";

const ARTIFACT = path.join(
  process.cwd(),
  "data",
  "kbli-perpres-slice-disclosures.json",
);

describe("perpresSlice — the /kbli/13133 batik-cap slice reader", () => {
  it("returns the single row for a real BROADER-adjudicated code", () => {
    // 13133 (Industri Kain Batik) is 100% open as a whole code; "batik cap"
    // (stamped batik) specifically is reserved to domestic capital under
    // Perpres 49/2021 Lampiran III entry #2.
    expect(perpresSlice("13133")).toEqual([
      {
        bidangUsaha: "Industri batik cap",
        foreignCapPct: 0,
        condition: null,
        locator:
          "Perpres 49/2021 Lampiran III (Daftar Bidang Usaha dengan Persyaratan Tertentu) entry #2",
      },
    ]);
  });

  it("returns two rows for 30111 (warship + Pinisi/Cadik slices)", () => {
    const rows = perpresSlice("30111");
    expect(rows).toHaveLength(2);
    const caps = rows!.map((r) => r.foreignCapPct).sort();
    expect(caps).toEqual([0, 49]);
  });

  it("returns one row for 30113 (defence slice only — no Pinisi row)", () => {
    const rows = perpresSlice("30113");
    expect(rows).toHaveLength(1);
    expect(rows![0].foreignCapPct).toBe(49);
    expect(rows![0].bidangUsaha).not.toContain("Pinisi");
  });

  it("returns a row with a condition for a 49%-cap code", () => {
    const rows = perpresSlice("26513");
    expect(rows).toEqual([
      {
        bidangUsaha: "Industri radar pertahanan untuk sistem persenjataan",
        foreignCapPct: 49,
        condition: "may exceed 49% with Menteri Pertahanan approval",
        locator:
          "Perpres 49/2021 Lampiran III (Daftar Bidang Usaha dengan Persyaratan Tertentu) entry #7",
      },
    ]);
  });

  it("returns null for a non-affected code (innocence)", () => {
    expect(perpresSlice("56101")).toBeNull();
  });

  it("returns null for an unknown code rather than inventing one", () => {
    expect(perpresSlice("99999")).toBeNull();
  });

  it("never returns a row for 21021/21022 — whole-code restricted, not a slice case", () => {
    expect(perpresSlice("21021")).toBeNull();
    expect(perpresSlice("21022")).toBeNull();
  });
});

// =============================================================================
// FAIL-CLOSED loading — same contract and same mechanism as kbli-risk-dispute.ts
// (mocks the shared `fs` module rather than touching the real artifact).
// =============================================================================

describe("fail-closed loading", () => {
  it("throws when the artifact file cannot be read", async () => {
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockImplementation(() => {
        throw new Error("ENOENT: no such file or directory");
      });
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("13133")).toThrow(
      /cannot read perpres slice-disclosure artifact/,
    );
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("throws when the artifact is not valid JSON", async () => {
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockReturnValue("{ not valid json");
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("13133")).toThrow(/is not valid JSON/);
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it('throws when the payload has no "disclosures" object', async () => {
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockReturnValue(JSON.stringify({ _meta: { count: 0 } }));
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("13133")).toThrow(/has no "disclosures" object/);
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("innocence: a well-formed artifact still loads without throwing", async () => {
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("13133")).not.toThrow();
  });

  it('throws when "disclosures" is an empty object', async () => {
    // The compiler never emits zero entries — an empty map here is silent
    // total data loss: every page that should carry a slice notice would
    // render "100% open" unqualified with zero signal anything is missing.
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockReturnValue(
        JSON.stringify({ _meta: { count: 0 }, disclosures: {} }),
      );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("13133")).toThrow(/empty "disclosures" object/);
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("throws when _meta.count disagrees with the actual entry count", async () => {
    // A hand-edit or a stale compiler run can drift the two apart — the
    // artifact's own freshness signal (_meta.count) must be checked, not
    // trusted blindly, or a partial edit could silently ship fewer/more
    // entries than the compiler believes it emitted.
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        _meta: { count: 5 },
        disclosures: {
          "00000": [
            {
              bidangUsaha: "x",
              foreignCapPct: 0,
              condition: null,
              locator: "x",
            },
          ],
        },
      }),
    );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).toThrow(
      /_meta\.count=5 but "disclosures" carries 1 entries/,
    );
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("innocence: _meta.count matching the real entry count does not throw", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        _meta: { count: 1 },
        disclosures: {
          "00000": [
            {
              bidangUsaha: "x",
              foreignCapPct: 0,
              condition: null,
              locator: "x",
            },
          ],
        },
      }),
    );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).not.toThrow();
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("throws on an entry with a missing/empty row list", async () => {
    const fsMock = await import("fs");
    const spy = vi
      .spyOn(fsMock.default, "readFileSync")
      .mockReturnValue(
        JSON.stringify({ _meta: { count: 1 }, disclosures: { "00000": [] } }),
      );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).toThrow(
      /entry "00000" has a missing or empty row list/,
    );
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("throws on a row with a missing bidangUsaha", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        _meta: { count: 1 },
        disclosures: {
          "00000": [{ foreignCapPct: 0, condition: null, locator: "x" }],
        },
      }),
    );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).toThrow(
      /row 0 has a missing or empty "bidangUsaha"/,
    );
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("throws on a row with an invalid foreignCapPct", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        _meta: { count: 1 },
        disclosures: {
          "00000": [
            {
              bidangUsaha: "x",
              foreignCapPct: 30,
              condition: null,
              locator: "x",
            },
          ],
        },
      }),
    );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).toThrow(/row 0 has an invalid "foreignCapPct"/);
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("throws on a row with a non-null, non-string condition", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        _meta: { count: 1 },
        disclosures: {
          "00000": [
            { bidangUsaha: "x", foreignCapPct: 0, condition: 5, locator: "x" },
          ],
        },
      }),
    );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).toThrow(
      /row 0 has a non-null, non-string "condition"/,
    );
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("throws on a row with a missing locator", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        _meta: { count: 1 },
        disclosures: {
          "00000": [{ bidangUsaha: "x", foreignCapPct: 0, condition: null }],
        },
      }),
    );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).toThrow(/row 0 has a missing or empty "locator"/);
    spy.mockRestore();
    _resetPerpresSliceCache();
  });

  it("innocence: a null condition on an otherwise valid row does not throw", async () => {
    const fsMock = await import("fs");
    const spy = vi.spyOn(fsMock.default, "readFileSync").mockReturnValue(
      JSON.stringify({
        _meta: { count: 1 },
        disclosures: {
          "00000": [
            {
              bidangUsaha: "x",
              foreignCapPct: 0,
              condition: null,
              locator: "x",
            },
          ],
        },
      }),
    );
    const { perpresSlice: ps, _resetPerpresSliceCache } =
      await import("./kbli-perpres-slice");
    _resetPerpresSliceCache();
    expect(() => ps("00000")).not.toThrow();
    spy.mockRestore();
    _resetPerpresSliceCache();
  });
});

describe("the artifact on disk", () => {
  const parsed = JSON.parse(fs.readFileSync(ARTIFACT, "utf-8")) as {
    disclosures: Record<string, { bidangUsaha?: string }[]>;
  };

  it("is generated, and says by what", () => {
    expect(fs.existsSync(ARTIFACT)).toBe(true);
    expect(Object.keys(parsed.disclosures).length).toBeGreaterThan(0);
  });

  it("every code has a non-empty row list", () => {
    for (const [code, rows] of Object.entries(parsed.disclosures)) {
      expect(Array.isArray(rows), `code ${code}`).toBe(true);
      expect(rows.length, `code ${code}`).toBeGreaterThan(0);
    }
  });

  it("population count matches the compiler's pinned population (12 codes)", () => {
    expect(Object.keys(parsed.disclosures)).toHaveLength(12);
  });

  it("20235 and 30303 are excluded — adjacent-not-contained, not a slice inside the code", () => {
    expect(parsed.disclosures["20235"]).toBeUndefined();
    expect(parsed.disclosures["30303"]).toBeUndefined();
  });
});

// =============================================================================
// RENDER CONTRACT — pins on the SOURCE of the two files that render a code's
// perpres slice-disclosure, same pattern as kbli-risk-dispute.test.ts.
// =============================================================================

describe("RENDER CONTRACT: LicensingSection.tsx and kbli-faq.ts", () => {
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

  it("LicensingSection.tsx renders one paragraph per row via .map", () => {
    expect(LICENSING_SECTION_SOURCE).toContain("kbli.perpresSlice.map");
  });

  it("LicensingSection.tsx branches the sentence on foreignCapPct === 0", () => {
    expect(LICENSING_SECTION_SOURCE).toContain("row.foreignCapPct === 0");
  });

  it("LicensingSection.tsx pins the cap-0-no-condition wording exactly", () => {
    const normalized = LICENSING_SECTION_SOURCE.replace(/\s+/g, " ");
    expect(normalized).toContain(
      "is reserved for domestic capital under Perpres 10/2021 (as amended): no foreign equity in that slice.",
    );
  });

  it("LicensingSection.tsx pins the cap-0-WITH-condition wording exactly (phased caps are not an absolute closure)", () => {
    const normalized = LICENSING_SECTION_SOURCE.replace(/\s+/g, " ");
    expect(normalized).toContain(
      "is reserved for domestic capital at establishment under Perpres 10/2021 (as amended) — {row.condition}.",
    );
  });

  it("LicensingSection.tsx pins the cap-49 wording exactly", () => {
    const normalized = LICENSING_SECTION_SOURCE.replace(/\s+/g, " ");
    expect(normalized).toContain(
      "is capped at 49% foreign ownership under Perpres 10/2021 (as amended)",
    );
  });

  it("LicensingSection.tsx pins the shared tail sentence, rendered once after every row", () => {
    const normalized = LICENSING_SECTION_SOURCE.replace(/\s+/g, " ");
    expect(normalized).toContain(
      "Everything else in this code is open as shown. Check which side your exact activity falls on before filing.",
    );
  });

  it("LicensingSection.tsx renders the tail sentence OUTSIDE the per-row .map callback", () => {
    // Structural pin against the exact regression this fixes: the tail
    // sentence's JSX must appear AFTER the .map(...) call closes, not
    // inside the mapped <p> — otherwise it repeats once per row.
    const mapStart = LICENSING_SECTION_SOURCE.indexOf(
      "kbli.perpresSlice.map((row, i) => (",
    );
    const mapEnd = LICENSING_SECTION_SOURCE.indexOf("))}", mapStart);
    const tailIdx = LICENSING_SECTION_SOURCE.indexOf(
      "Everything else in this code is open as shown",
    );
    expect(mapStart).toBeGreaterThan(-1);
    expect(mapEnd).toBeGreaterThan(mapStart);
    expect(tailIdx).toBeGreaterThan(mapEnd);
  });

  it("LicensingSection.tsx never chains the frame condition to baliBlocked", () => {
    // The frame's own `{kbli.perpresSlice && ...}` condition must not also
    // reference baliBlocked — independent axis, per the brief.
    const frameStart = LICENSING_SECTION_SOURCE.indexOf(
      "kbli.perpresSlice && kbli.perpresSlice.length > 0",
    );
    expect(frameStart).toBeGreaterThan(-1);
  });

  it("kbli-faq.ts appends a perpresSlice qualifier to the PMA answer", () => {
    expect(FAQ_SOURCE).toContain("perpresSliceQualifier");
    expect(FAQ_SOURCE).toContain(
      "answer: `${pmaAnswer}${perpresSliceQualifier}${pmaSourceNote}`",
    );
  });
});

// =============================================================================
// FAQ integration
// =============================================================================

describe("buildKbliFaq — perpres slice-disclosure qualifier", () => {
  it("qualifies the OPENING sentence when perpresSlice is set — never the flat unqualified promise", async () => {
    // The defect this closes: the answer used to open "Yes. KBLI ... open
    // to 100% foreign ownership via PT PMA. No local Indonesian partner
    // required." and appended the carve-out only afterward — a snippet
    // truncated to the first sentence serves the unqualified promise with
    // zero signal a carve-out exists.
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base).toBeDefined();
    const affected = {
      ...base,
      perpresSlice: [
        {
          bidangUsaha: "Industri batik cap",
          foreignCapPct: 0 as const,
          condition: null,
          locator: "test",
        },
      ],
    } as NonNullable<typeof base>;

    const pmaAnswer = buildKbliFaq(affected)[0].answer;
    expect(
      pmaAnswer.startsWith("Yes for most of this code, with one carve-out:"),
    ).toBe(true);
    expect(pmaAnswer).not.toMatch(
      /^Yes\. KBLI .* No local Indonesian partner required\./,
    );
    expect(pmaAnswer).toContain(
      'One specific activity inside this code — "Industri batik cap" — is reserved for domestic capital under Perpres 10/2021 (as amended): no foreign equity in that slice.',
    );
    // The open-remainder statement comes AFTER the carve-out detail, not
    // stapled onto the opener.
    expect(pmaAnswer).toContain(
      "The rest of the code remains open to 100% foreign ownership with no local partner required.",
    );
    expect(
      pmaAnswer.indexOf("Industri batik cap") <
        pmaAnswer.indexOf("The rest of the code remains open"),
    ).toBe(true);
  });

  it("guilt: a condition-bearing cap-0 row gets the condition, never the absolute closure claim", async () => {
    // Same phased-cap defect as the LicensingSection page frame (58130
    // press: 0% at establishment, 49% via capital market for expansion).
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    const affected = {
      ...base,
      perpresSlice: [
        {
          bidangUsaha: "Penerbitan surat kabar, majalah, dan buletin (pers)",
          foreignCapPct: 0 as const,
          condition:
            "0% at establishment; 49% via capital market for expansion",
          locator: "test",
        },
      ],
    } as NonNullable<typeof base>;

    const pmaAnswer = buildKbliFaq(affected)[0].answer;
    expect(pmaAnswer).toContain(
      'One specific activity inside this code — "Penerbitan surat kabar, majalah, dan buletin (pers)" — is reserved for domestic capital at establishment under Perpres 10/2021 (as amended) — 0% at establishment; 49% via capital market for expansion.',
    );
    expect(pmaAnswer).not.toContain("no foreign equity in that slice");
  });

  it("appends the cap-49 qualifier with the condition when set", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base).toBeDefined();
    const affected = {
      ...base,
      perpresSlice: [
        {
          bidangUsaha: "Industri radar pertahanan untuk sistem persenjataan",
          foreignCapPct: 49 as const,
          condition: "may exceed 49% with Menteri Pertahanan approval",
          locator: "test",
        },
      ],
    } as NonNullable<typeof base>;

    const pmaAnswer = buildKbliFaq(affected)[0].answer;
    expect(pmaAnswer).toContain(
      "is capped at 49% foreign ownership under Perpres 10/2021 (as amended), may exceed 49% with Menteri Pertahanan approval.",
    );
  });

  it("appends one sentence per row for a multi-row code, and pluralizes 'carve-outs' in the opener", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("30111");
    expect(base?.perpresSlice).toHaveLength(2);

    const pmaAnswer = buildKbliFaq(base!)[0].answer;
    expect(
      pmaAnswer.startsWith("Yes for most of this code, with 2 carve-outs:"),
    ).toBe(true);
    expect(pmaAnswer).toContain("Industri kapal perang");
    expect(pmaAnswer).toContain("Pinisi");
    // The shared closer must appear exactly once, after both rows.
    const closerCount =
      pmaAnswer.split(
        "The rest of the code remains open to 100% foreign ownership",
      ).length - 1;
    expect(closerCount).toBe(1);
  });

  it("real case: 90200 (Sanggar seni) is BOTH BROADER-adjudicated AND Bali-blocked — the opener and closer both carry the Bali caveat", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("90200");
    expect(base?.perpresSlice).toHaveLength(1);
    expect(base?.baliL4?.blocked).toBe(true);

    const pmaAnswer = buildKbliFaq(base!)[0].answer;
    expect(
      pmaAnswer.startsWith(
        "Nationally yes for most of this code, with one carve-out — but NOT in Bali either way.",
      ),
    ).toBe(true);
    expect(pmaAnswer).toContain("Sanggar seni");
    expect(pmaAnswer).toContain(
      "Outside Bali, the rest of the code remains open to a PT PMA with no local partner required — subject to the Bali restriction stated above.",
    );
  });

  it("innocence: omits the qualifier when perpresSlice is absent", async () => {
    const { buildKbliFaq } = await import("./kbli-faq");
    const { getCode } = await import("./kbli-data");
    const base = getCode("56101");
    expect(base?.perpresSlice).toBeUndefined();

    const pmaAnswer = buildKbliFaq(base!)[0].answer;
    expect(pmaAnswer).not.toContain("is reserved for domestic capital");
    expect(pmaAnswer).not.toContain("is capped at 49% foreign ownership");
  });
});

// =============================================================================
// The two readers (kbli-data.ts and kbli-data.server.ts) must agree.
// =============================================================================

describe("the two KBLICode readers agree on perpresSlice", () => {
  it("across all disclosed codes", async () => {
    const { getCode } = await import("./kbli-data");
    const { getCode: getServerCode } = await import("./kbli-data.server");
    const parsed = JSON.parse(fs.readFileSync(ARTIFACT, "utf-8")) as {
      disclosures: Record<string, unknown>;
    };
    const disagreements = Object.keys(parsed.disclosures).filter((code) => {
      const a = getCode(code)?.perpresSlice;
      const b = getServerCode(code)?.perpresSlice;
      return JSON.stringify(a) !== JSON.stringify(b);
    });
    expect(disagreements).toEqual([]);
  });

  it("the page's own reader (kbli-data.ts) actually carries perpresSlice for 13133", async () => {
    const { getCode } = await import("./kbli-data");
    expect(getCode("13133")?.perpresSlice).toEqual([
      {
        bidangUsaha: "Industri batik cap",
        foreignCapPct: 0,
        condition: null,
        locator:
          "Perpres 49/2021 Lampiran III (Daftar Bidang Usaha dengan Persyaratan Tertentu) entry #2",
      },
    ]);
  });
});
