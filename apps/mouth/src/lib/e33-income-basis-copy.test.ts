// Guard for E33E / E33F senior Second Home income basis in public article copy.
// The official E33E/E33F immigration rule states "income or allowance"
// ("penghasilan atau tunjangan"), never "passive income" ("pendapatan pasif").
//
// The E28A guide used to carry an E33E/E33F comparison line and this test pinned
// it. The E28A guide now says only what the E28A page says, so that line is gone
// and no other article carries the same comparison line. The guard keeps its
// purpose on the E28 family: none of the three guides, in any locale, may state
// an E33E/E33F income basis as passive income. (second-home-visa-indonesia, EN
// and ID, still says "proven passive income" at lines 121-122: not an E28 file,
// pre-existing, recorded as backlog in the evidence pack.)
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const app = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const immigrationDir = join(app, "src/content/articles/immigration");
const E28_FAMILY = [
  "e28a-investor-kitas-guide",
  "golden-visa-indonesia-complete-guide",
  "investor-kitas-guide",
].flatMap((slug) =>
  ["", ".id", ".it", ".fr", ".ru"].map((l) => `${slug}${l}.mdx`),
);

export function incomeBasisIsPassive(line: string): boolean {
  return (
    /E33[EF]/.test(line) &&
    /passive income|(?:pendapatan|penghasilan) pasif/i.test(line)
  );
}

// Fixture lines in the shape the E28A guide used to carry (EN and ID).
const EN_LINE =
  "| Senior route (E33E/E33F) | Age 60+ | documented income or allowance of at least USD 3,000 per month |";
const ID_LINE =
  "| Jalur senior (E33E/E33F) | Usia 60+ | penghasilan atau tunjangan terdokumentasi minimal USD 3.000 per bulan |";

describe("E33E/E33F income basis is never passive income in the E28 family guides", () => {
  it("no line of the E28 family guides (15 files) states an E33E/E33F passive-income basis", () => {
    const hits = E28_FAMILY.flatMap((f) =>
      readFileSync(join(immigrationDir, f), "utf8")
        .split("\n")
        .map((line, i) => ({ f, n: i + 1, line }))
        .filter(({ line }) => incomeBasisIsPassive(line))
        .map(({ f, n }) => `${f}:${n}`),
    );
    expect(hits).toEqual([]);
  });

  it("innocence: the 'income or allowance' wording is not convicted (EN and ID)", () => {
    expect(incomeBasisIsPassive(EN_LINE)).toBe(false);
    expect(incomeBasisIsPassive(ID_LINE)).toBe(false);
  });

  it("guilt: the same line using 'passive income' / 'pendapatan pasif' is convicted", () => {
    expect(
      incomeBasisIsPassive(
        EN_LINE.replace("income or allowance", "passive income"),
      ),
    ).toBe(true);
    expect(
      incomeBasisIsPassive(
        ID_LINE.replace("penghasilan atau tunjangan", "pendapatan pasif"),
      ),
    ).toBe(true);
    expect(
      incomeBasisIsPassive(
        ID_LINE.replace("penghasilan atau tunjangan", "penghasilan pasif"),
      ),
    ).toBe(true);
  });

  it("innocence: an unrelated line mentioning passive income without E33E/E33F is not convicted", () => {
    expect(
      incomeBasisIsPassive(
        "- Managing personal investments (passive income from abroad)",
      ),
    ).toBe(false);
  });
});
