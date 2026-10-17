import { describe, expect, it } from "vitest";

import { SERVICES_DATA, type ServicePackage } from "@/data/services_data";
import {
  UNPLACED_CHAPTER_ID,
  VISA_LEDGER_SPEC,
  buildVisaLedger,
  rowCells,
  type ChapterSpec,
} from "./visa-price-ledger";

const PACKAGES = SERVICES_DATA.visa.packages;

function pkg(key: string, category = "single_entry_visas"): ServicePackage {
  return {
    name: key,
    description: "",
    price: "Contact",
    features: [],
    popular: false,
    livePriceKey: key,
    livePriceCategory: category,
  };
}

describe("the visa price ledger places the live catalogue", () => {
  const ledger = buildVisaLedger(PACKAGES);

  it("places every public visa row exactly once and names nothing the catalogue lacks", () => {
    expect(ledger.dangling).toEqual([]);
    expect(ledger.unplaced).toEqual([]);
    expect(ledger.chapters.map((chapter) => chapter.id)).not.toContain(
      UNPLACED_CHAPTER_ID,
    );
    expect(ledger.total).toBe(PACKAGES.length);
    const seen = ledger.chapters.flatMap((chapter) =>
      chapter.families.flatMap((family) =>
        family.kind === "list"
          ? family.items.map((item) => item.livePriceKey)
          : family.rows.flatMap((row) =>
              rowCells(row).flatMap((cell) =>
                cell ? [cell.livePriceKey] : [],
              ),
            ),
      ),
    );
    expect(new Set(seen).size).toBe(seen.length);
    expect([...seen].sort()).toEqual(
      PACKAGES.map((item) => item.livePriceKey).sort(),
    );
  });

  it("reads as five chapters, every one with a lede and at least one family", () => {
    expect(ledger.chapters.map((chapter) => chapter.numeral)).toEqual([
      "I",
      "II",
      "III",
      "IV",
      "V",
    ]);
    for (const chapter of ledger.chapters) {
      expect(chapter.lede.length).toBeGreaterThan(20);
      expect(chapter.families.length).toBeGreaterThan(0);
      expect(chapter.count).toBeGreaterThan(0);
    }
  });

  it("keeps the first row in document order a row whose name is its key", () => {
    // book-pricing.spec.ts opens the first card's dialog and looks it up by
    // the row KEY: the first placed row must be one where name === key.
    const first = ledger.chapters[0].families[0];
    const row =
      first.kind === "list" ? first.items[0] : rowCells(first.rows[0])[0];
    expect(row?.name).toBe(row?.livePriceKey);
  });

  it("lays variant families out as matrices with one column per catalogue variant", () => {
    const kitas = ledger.chapters.find((chapter) => chapter.id === "kitas");
    const work = kitas?.families.find((family) => family.id === "work");
    expect(work?.kind).toBe("matrix");
    if (work?.kind !== "matrix") return;
    expect(work.columns).toEqual(["Offshore", "Onshore", "Extension"]);
    const working = work.rows.find((row) => row.name === "Working KITAS");
    expect(working?.cells.map((cell) => cell?.livePriceKey)).toEqual([
      "Working KITAS (Offshore)",
      "Working KITAS (Altus/Onshore)",
      "Working KITAS (Extend)",
    ]);
  });

  it("never references a key twice across the spec", () => {
    const keys = VISA_LEDGER_SPEC.flatMap((chapter) =>
      chapter.families.flatMap((family) =>
        family.kind === "list"
          ? family.keys
          : family.rows.flatMap((row) =>
              (row.variants
                ? row.variants.flatMap((variant) => variant.cells)
                : (row.cells ?? [])
              ).filter((cell): cell is string => cell !== null),
            ),
      ),
    );
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("keeps one service per row: durations and extensions are variants, never separate rows", () => {
    const kitas = ledger.chapters.find((chapter) => chapter.id === "kitas");
    const family = kitas?.families.find((item) => item.id === "family");
    expect(family?.kind).toBe("matrix");
    if (family?.kind !== "matrix") return;
    expect(family.rows.map((row) => row.name)).toEqual([
      "Spouse KITAS",
      "Dependent KITAS",
    ]);
    expect(family.rows[0].variants?.map((variant) => variant.label)).toEqual([
      "1 year",
      "2 years",
    ]);
    const visit = ledger.chapters[0].families.find(
      (item) => item.id === "visit",
    );
    if (visit?.kind !== "matrix") throw new Error("visit is a matrix");
    expect(visit.columns).toEqual(["Visa", "Extension"]);
    expect(
      visit.rows
        .find((row) => row.name === "C1 Tourism")
        ?.cells.map((cell) => cell?.livePriceKey),
    ).toEqual(["C1 Tourism", "C1 Tourism Extension"]);
  });
});

describe("the visa price ledger reports drift in both directions (guilt)", () => {
  const spec: ChapterSpec[] = [
    {
      id: "one",
      numeral: "I",
      title: "One",
      lede: "A chapter with a stale key and a live one.",
      families: [
        {
          kind: "matrix",
          id: "m",
          name: "M",
          columns: ["A", "B"],
          rows: [{ name: "Row", cells: ["C1 Tourism", "C317 Single Entry"] }],
        },
      ],
    },
  ];

  it("lists a spec key the catalogue no longer carries as dangling", () => {
    const ledger = buildVisaLedger([pkg("C1 Tourism")], spec);
    expect(ledger.dangling).toEqual(["C317 Single Entry"]);
    expect(ledger.total).toBe(1);
  });

  it("surfaces a catalogue row the spec never placed in a trailing chapter", () => {
    const ledger = buildVisaLedger(
      [pkg("C1 Tourism"), pkg("Urgent 1 Day", "urgent_processing")],
      spec,
    );
    expect(ledger.unplaced.map((item) => item.livePriceKey)).toEqual([
      "Urgent 1 Day",
    ]);
    const last = ledger.chapters[ledger.chapters.length - 1];
    expect(last.id).toBe(UNPLACED_CHAPTER_ID);
    expect(last.count).toBe(1);
    expect(ledger.total).toBe(2);
  });

  it("drops a matrix row and a family that resolve to nothing", () => {
    const ledger = buildVisaLedger([pkg("Something else")], spec);
    expect(ledger.chapters.map((chapter) => chapter.id)).toEqual([
      UNPLACED_CHAPTER_ID,
    ]);
  });
});
