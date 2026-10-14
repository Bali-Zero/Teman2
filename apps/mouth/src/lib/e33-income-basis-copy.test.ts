// Guard for E33E / E33F senior Second Home income basis in public article copy.
// The official E33E/E33F immigration rule states "income or allowance"
// ("penghasilan atau tunjangan"), never "passive income" ("pendapatan pasif").
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const app = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const enMdxPath = join(
  app,
  "src/content/articles/immigration/e28a-investor-kitas-guide.mdx",
);
const idMdxPath = join(
  app,
  "src/content/articles/immigration/e28a-investor-kitas-guide.id.mdx",
);

export function incomeBasisIsPassive(line: string): boolean {
  return /E33[EF]/.test(line) && /passive income|pendapatan pasif/i.test(line);
}

function pickSeniorRouteLine(filePath: string): string[] {
  return readFileSync(filePath, "utf8")
    .split("\n")
    .filter((line) => /E33E/.test(line) && /E33F/.test(line));
}

describe("E33E/E33F income basis in e28a-investor-kitas-guide (EN + ID parity)", () => {
  it("EN and ID articles each have the E33E/E33F comparison line with 'income or allowance' / 'penghasilan atau tunjangan' and the 3,000 / 3.000 figure", () => {
    const enHits = pickSeniorRouteLine(enMdxPath);
    const idHits = pickSeniorRouteLine(idMdxPath);

    expect(enHits).toHaveLength(1);
    expect(idHits).toHaveLength(1);

    const enLine = enHits[0];
    const idLine = idHits[0];

    expect(enLine).toContain("documented income or allowance");
    expect(enLine).toContain("3,000");
    expect(enLine).not.toMatch(/passive income/i);
    expect(incomeBasisIsPassive(enLine)).toBe(false);

    expect(idLine).toContain("penghasilan atau tunjangan terdokumentasi");
    expect(idLine).toContain("3.000");
    expect(idLine).not.toMatch(/pendapatan pasif/i);
    expect(incomeBasisIsPassive(idLine)).toBe(false);
  });

  it("guilt: a mutated EN or ID E33E/E33F line using 'passive income' / 'pendapatan pasif' is convicted by incomeBasisIsPassive", () => {
    const [enLine] = pickSeniorRouteLine(enMdxPath);
    const [idLine] = pickSeniorRouteLine(idMdxPath);

    const mutatedEn = enLine.replace("income or allowance", "passive income");
    const mutatedId = idLine.replace(
      "penghasilan atau tunjangan",
      "pendapatan pasif",
    );

    expect(incomeBasisIsPassive(mutatedEn)).toBe(true);
    expect(incomeBasisIsPassive(mutatedId)).toBe(true);
  });

  it("innocence: an unrelated line mentioning passive income without E33E/E33F is not convicted", () => {
    expect(
      incomeBasisIsPassive(
        "- Managing personal investments (passive income from abroad)",
      ),
    ).toBe(false);
  });
});
