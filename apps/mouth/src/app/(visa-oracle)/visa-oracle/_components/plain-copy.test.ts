import { dict, translate, type I18nKey } from "../_lib/i18n";
import {
  PLAIN_COPY,
  PLAIN_COPY_EXEMPT,
  answeredOf,
  plainTranslate,
} from "./plain-copy";

const vars = (value: string) =>
  Array.from(value.matchAll(/\{\{(?!plural:)(\w+)\}\}/g), (m) => m[1]).sort();

/** Engine vocabulary Zero rejected on this surface (MV:2167) and the
 * council flagged (CRITIQUE-v2 Oracle #1). Each pattern carries its own
 * guilt sample so a pattern that stops matching fails loudly. */
const BANNED: [RegExp, string][] = [
  [/\binterview branch/i, "3 interview branches"],
  [/\bbranch(es)?\b/i, "Purpose branches"],
  [/\bclosed\b/i, "10 other purposes closed"],
  [/\bpruned\b/i, "pruned"],
  [/\bengine\b/i, "the engine’s answer"],
  [/\bfacts?\b/i, "Identity facts"],
  [/\bdecision input\b/i, "Decision input: x"],
  [/\bmesin\b/i, "Jawaban mesin"],
  [/\bcabang\b/i, "cabang wawancara"],
  [/\bditutup\b/i, "10 tujuan lain ditutup"],
  [/\bfakta\b/i, "Fakta identitas"],
];

describe("PLAIN_COPY — plain wording over the frozen dictionary", () => {
  it("carries the same keys in EN and ID", () => {
    expect(Object.keys(PLAIN_COPY.id).sort()).toEqual(
      Object.keys(PLAIN_COPY.en).sort(),
    );
  });

  for (const key of Object.keys(PLAIN_COPY.en) as I18nKey[]) {
    it(`${key}: exists in the frozen dictionary with the same {{vars}}`, () => {
      for (const language of ["en", "id"] as const) {
        const frozen = (dict[language] as Record<string, string>)[key];
        const plain = (PLAIN_COPY[language] as Record<string, string>)[key];
        expect(frozen).toBeDefined();
        expect(plain.trim()).not.toBe("");
        expect(vars(plain)).toEqual(vars(frozen));
      }
    });
  }

  it("never carries engine vocabulary (guilt samples fire)", () => {
    const all = [
      ...Object.values(PLAIN_COPY.en),
      ...Object.values(PLAIN_COPY.id),
    ].join("\n");
    for (const [pattern, guilt] of BANNED) {
      expect(guilt).toMatch(pattern);
      expect(all).not.toMatch(pattern);
    }
  });

  it("covers every customer-facing frozen string that still speaks the engine's language", () => {
    // `why.*` (the collapsed "Why we ask" disclosure) and the retired
    // `process.decides_*` / `process.candidates_title` rail blocks are out:
    // the first is a seam for its own PR, the second no longer renders.
    const rendered =
      /^(paths|confirmation|tree|verdict|outcome|assumption|process)\.|^q\.[\w.]+\.hint$/;
    const retired = /^process\.(decides_|candidates_title$)/;
    const uncovered: string[] = [];
    for (const language of ["en", "id"] as const) {
      for (const [key, value] of Object.entries(dict[language])) {
        if (!rendered.test(key) || retired.test(key)) continue;
        if (key in PLAIN_COPY[language] || key in PLAIN_COPY_EXEMPT) continue;
        if (BANNED.some(([pattern]) => pattern.test(value as string))) {
          uncovered.push(`${language}:${key}`);
        }
      }
    }
    expect(uncovered).toEqual([]);
  });

  it("interpolates like translate(), plural marker included", () => {
    expect(plainTranslate("en", "paths.counter.label", { count: 11 })).toBe(
      "11 purposes still possible",
    );
    expect(plainTranslate("en", "paths.counter.label", { count: 1 })).toBe(
      "1 purpose — the one you chose",
    );
    expect(
      plainTranslate("id", "process.announce_prune", {
        count: 10,
        category: "Wisata",
      }),
    ).toBe(
      "Anda memilih Wisata. 10 tujuan lain dikesampingkan untuk saat ini.",
    );
    // A key with no override is the frozen string, untouched.
    expect(plainTranslate("en", "framing.cta")).toBe(
      translate("en", "framing.cta"),
    );
  });

  it("says 'about' while the road can still grow, and the exact count at the end", () => {
    expect(answeredOf("en", 3, 7)).toBe("3 of about 7 answered");
    expect(answeredOf("id", 0, 6)).toBe("0 dari sekitar 6 terjawab");
    expect(answeredOf("en", 9, 9)).toBe("9 of 9 answered");
  });
});
