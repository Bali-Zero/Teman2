import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { getPerpresLocator, perpresCitation } from "./kbli-perpres-locator";
import rawData from "../../data/KBLI_2025_FINAL_CLEAN.json";

const ARTIFACT = path.join(process.cwd(), "data", "perpres-locators.json");

describe("Perpres citation on the KBLI page", () => {
  it("covers every code in the catalogue", () => {
    // The page renders the citation for whichever code is requested, so a
    // partial artifact would leave an arbitrary subset of pages silently
    // uncited — visible to nobody, since the render is conditional.
    const codes = (rawData as { data: { kode_kbli_2025: string }[] }).data.map(
      (r) => String(r.kode_kbli_2025),
    );
    const missing = codes.filter((c) => perpresCitation(c) === null);
    expect(missing).toEqual([]);
    expect(codes.length).toBe(1559);
  });

  it("cites the ARTICLE, never just the instrument", () => {
    // The defect this closes: `pma.source` says "Perpres 10/2021, 49/2021" on
    // all 1,559 records — the instrument with no article. A citation that did
    // the same would be the same blanket attribution in a new place.
    const cites = new Set(
      (rawData as { data: { kode_kbli_2025: string }[] }).data.map((r) =>
        perpresCitation(String(r.kode_kbli_2025)),
      ),
    );
    expect(cites.size).toBeGreaterThan(1);
    for (const cite of cites) {
      expect(cite).toMatch(/Pasal|Lampiran/);
    }
  });

  it("names the right article for each kind of code", () => {
    // Guilt, on codes whose classification is established elsewhere in this
    // repo: a restriction, a body closure, a priority listing, a residual.
    expect(perpresCitation("25200")).toContain("Lampiran III"); // arms — capped
    expect(perpresCitation("11010")).toContain("Pasal 2(2)(b)"); // alcohol — closed by name
    expect(perpresCitation("47221")).toContain("Pasal 6(3a)"); // alcohol retail
    expect(perpresCitation("01271")).toContain("Lampiran I"); // priority
    expect(perpresCitation("56101")).toContain("Pasal 3(1)(d)"); // restaurant — residual
  });

  it("says when an activity is named through its KBLI-2020 predecessor", () => {
    // `55203` (Vila) is not in the annex under its own code; `55193` is. A
    // reader who greps the annex for 55203 and finds nothing must be able to
    // see why, rather than conclude the citation is invented.
    expect(perpresCitation("55203")).toContain("via KBLI-2020 55193");
  });

  it("keeps the OSS scale axis OUT of the citation", () => {
    // `Pasal 7(1)` conditions the INVESTOR (a PT PMA must reach Usaha Besar);
    // an absent Besar row in OSS licensing data is not a finding that the
    // activity cannot be run at that scale. Printing it as part of a legal
    // citation would state a bar the instrument does not.
    const villa = getPerpresLocator("55203");
    expect(villa?.besar).toBe("absent");
    expect(villa?.cite).not.toMatch(/Besar|Pasal 7/);
  });

  it("returns null for an unknown code rather than inventing one", () => {
    expect(perpresCitation("99999")).toBeNull();
    expect(getPerpresLocator("99999")).toBeNull();
  });

  it("is generated, and says by what", () => {
    // A data file with no producer named is one nobody can regenerate — the
    // defect that left 41 foreign-ownership caps unre-derivable for a year.
    const parsed = JSON.parse(fs.readFileSync(ARTIFACT, "utf-8"));
    expect(parsed.generated_by).toContain(
      "scripts/kbli_filiera/perpres_body_default_relation.py",
    );
    expect(parsed.codes).toBe(1559);
  });
});

describe("the page's own reader surfaces the citation", () => {
  it("exposes it on kbli.pma.citation for the code the page requests", async () => {
    // The artifact holding the data and the PAGE showing it are two different
    // claims. `page.tsx` renders `kbli.pma.citation` from `getCode()` in
    // kbli-data.ts — so this exercises that path rather than the file, which
    // is the difference between "the data exists" and "the page can reach it".
    const { getCode } = await import("./kbli-data");
    const restaurant = getCode("56101");
    expect(restaurant?.pma.citation).toContain("Pasal 3(1)(d)");
    const villa = getCode("55203");
    expect(villa?.pma.citation).toContain("via KBLI-2020 55193");
  });

  it("agrees between the two readers, on every code", async () => {
    // The invariant is not "the server says X", it is that the two modules
    // never diverge — the cap was once read in both with different defaults
    // and rendered "0% Open" on a live page. Comparing them to each other is
    // the property; comparing each to a hardcoded string is a copy of the
    // answer, and two copies of a wrong answer still agree.
    const { getCode } = await import("./kbli-data");
    const { getCode: getServerCode } = await import("./kbli-data.server");
    const codes = (rawData as { data: { kode_kbli_2025: string }[] }).data.map(
      (r) => String(r.kode_kbli_2025),
    );
    const disagreements = codes.filter(
      (c) => getCode(c)?.pma.citation !== getServerCode(c)?.pma.citation,
    );
    expect(disagreements).toEqual([]);
  });
});
