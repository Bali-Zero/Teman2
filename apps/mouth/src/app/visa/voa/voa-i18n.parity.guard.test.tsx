import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VOA_COPY, fill, voaCopy, type VoaCopyKey } from "./voa-copy";
import { resolveVoaLocale, VOA_LOCALE_RULING } from "./voa-locale";

/**
 * GARUDA VOA — the parity guard for the funnel's two languages.
 *
 * Types already forbid a missing or extra Indonesian key (`id` is typed
 * `Record<VoaCopyKey, string>`). What types CANNOT see is everything this
 * file measures instead: an Indonesian value left equal to its English
 * original, a key nobody renders, an English sentence still hardcoded in the
 * screen, and — the one that would have made all of the above pointless —
 * the banned-claims guard losing sight of the copy the moment the copy moved
 * into a dictionary.
 *
 * That last one is cicatrix family #3 in the form this lane met three times
 * in one session: a guard that changes WHAT IT READS drops an assertion in
 * silence, and its green then certifies nothing.
 */

const VOA_DIR = join(__dirname);
const PAGE_SRC = readFileSync(join(VOA_DIR, "page.tsx"), "utf8");

const keys = Object.keys(VOA_COPY.en) as VoaCopyKey[];

/**
 * An Indonesian string identical to its English original is USUALLY an
 * untranslated leftover — but not always, and the difference has to be
 * written down rather than assumed, or the guard teaches people to copy
 * English into the `id` column and add the key here. Every row is a word
 * that is the same word in Bahasa Indonesia, with the reason it is.
 */
const SAME_BY_DESIGN: Partial<Record<VoaCopyKey, string>> = {
  "frame.title": "the permit's printed name, never translated",
  "purpose.transit": "the same word in both languages",
  "nationality.AUS": "the country's name is the same in both languages",
  "lead.context.pageLabel": "CRM lead context, English on purpose",
  "lead.context.pageValue": "CRM lead context, English on purpose",
};

describe("voa-i18n — EN and ID are the same funnel, twice", () => {
  it("the two columns carry exactly the same keys", () => {
    expect(Object.keys(VOA_COPY.id).sort()).toEqual([...keys].sort());
    expect(keys.length).toBeGreaterThan(40);
  });

  it("no Indonesian value is empty or blank", () => {
    const blank = keys.filter((k) => VOA_COPY.id[k].trim().length === 0);
    expect(blank).toEqual([]);
  });

  it("no Indonesian value is its English original left in place", () => {
    const untranslated = keys.filter(
      (k) => VOA_COPY.id[k] === VOA_COPY.en[k] && !(k in SAME_BY_DESIGN),
    );
    expect(untranslated).toEqual([]);
  });

  it("is GUILTY of an untranslated value (guilt control)", () => {
    const sabotaged = { ...VOA_COPY.id, "step.dates.title": "Dates" };
    const untranslated = keys.filter(
      (k) => sabotaged[k] === VOA_COPY.en[k] && !(k in SAME_BY_DESIGN),
    );
    expect(untranslated).toEqual(["step.dates.title"]);
  });

  it("every allowlisted twin really is identical (no stale row)", () => {
    for (const k of Object.keys(SAME_BY_DESIGN) as VoaCopyKey[]) {
      expect(VOA_COPY.id[k], `${k} no longer needs its allowlist row`).toBe(
        VOA_COPY.en[k],
      );
    }
  });

  it("both columns keep the same placeholders", () => {
    const placeholders = (s: string) =>
      (s.match(/\{(\w+)\}/g) ?? []).sort().join(",");
    const drifted = keys.filter(
      (k) => placeholders(VOA_COPY.en[k]) !== placeholders(VOA_COPY.id[k]),
    );
    expect(drifted).toEqual([]);
  });

  it("fill() substitutes what it is given and leaves the rest visible", () => {
    expect(fill("Step {current} of {total}", { current: 2, total: 4 })).toBe(
      "Step 2 of 4",
    );
    expect(fill("Step {current} of {total}", { current: 2 })).toBe(
      "Step 2 of {total}",
    );
  });
});

describe("voa-i18n — every key has a consumer, every sentence has a key", () => {
  it("no key is orphaned: the wizard renders each one", () => {
    const orphans = keys.filter((k) => !PAGE_SRC.includes(`"${k}"`));
    expect(orphans).toEqual([]);
  });

  it("is GUILTY of an orphan key (guilt control)", () => {
    const orphans = [...keys, "frame.subtitle.v2"].filter(
      (k) => !PAGE_SRC.includes(`"${k}"`),
    );
    expect(orphans).toEqual(["frame.subtitle.v2"]);
  });

  /**
   * Prose still hardcoded in the screen. Two shapes only, because those are
   * the two that reach a customer: a string-valued accessible or visible
   * prop, and a bare JSX text node. Style values (`"1px solid var(--x)"`) and
   * identifiers are deliberately out of reach — convicting them would be the
   * over-match half of family #3.
   */
  const PROSE_PROP_RE =
    /\b(?:aria-label|placeholder|title|subtitle|label)="([^"]{4,})"/g;
  const JSX_TEXT_RE = />\s*([A-Z][A-Za-z][^<>{}\n]{6,})\s*</g;

  function proseIn(src: string): string[] {
    const found: string[] = [];
    for (const m of src.matchAll(PROSE_PROP_RE)) found.push(m[1]);
    for (const m of src.matchAll(JSX_TEXT_RE)) found.push(m[1].trim());
    return found;
  }

  it("page.tsx holds no hardcoded sentence any more", () => {
    expect(proseIn(PAGE_SRC)).toEqual([]);
  });

  it("is GUILTY of a hardcoded sentence (guilt control)", () => {
    const sabotaged = `
      <input aria-label="Passport expiry date" />
      <p>Rather ask a person first?</p>
    `;
    expect(proseIn(sabotaged).sort()).toEqual([
      "Passport expiry date",
      "Rather ask a person first?",
    ]);
  });
});

describe("voa-i18n — the ruling is a variable, and it ships at 5a", () => {
  it("ships english-by-default: constraint 5a is what production serves", () => {
    expect(VOA_LOCALE_RULING).toBe("english-by-default");
  });

  it("a Bahasa site preference alone does NOT flip the funnel", () => {
    expect(resolveVoaLocale({ requested: null, preference: "id" })).toBe("en");
  });

  it("?lang=id is the preview channel, and it works", () => {
    expect(resolveVoaLocale({ requested: "id" })).toBe("id");
  });

  it("an unreadable language code is an English visitor, not an error", () => {
    expect(resolveVoaLocale({ requested: "de", preference: "id" })).toBe("en");
    expect(resolveVoaLocale({ requested: "", preference: null })).toBe("en");
  });

  /**
   * FALSIFICATION: the 5a pin above must be the RULING's doing, not the
   * resolver being unable to return Indonesian at all. Flip the one variable
   * and the same stored preference decides — which is exactly the line the
   * owner's answer will move, and nothing else.
   */
  it("flipping the ruling makes the site preference decide", () => {
    expect(
      resolveVoaLocale({
        requested: null,
        preference: "id",
        ruling: "follow-site-preference",
      }),
    ).toBe("id");
    expect(
      resolveVoaLocale({
        requested: "en",
        preference: "id",
        ruling: "follow-site-preference",
      }),
    ).toBe("en");
  });

  it("voaCopy() serves the language it is asked for", () => {
    expect(voaCopy("en")("wizard.next")).toBe("Next");
    expect(voaCopy("id")("wizard.next")).toBe("Lanjut");
  });
});

describe("voa-i18n — the banned-claims guard followed the copy", () => {
  /**
   * The copy left `page.tsx`. If `voa-copy.guard.test.ts` had kept scanning
   * only the screens, its green would have meant "the screens contain no
   * prose", which is now trivially true and worth nothing — and a banned
   * claim typed into either column would ship unchallenged.
   */
  it("voa-copy.guard.test.ts scans the dictionary file itself", () => {
    const guardSrc = readFileSync(
      join(VOA_DIR, "voa-copy.guard.test.ts"),
      "utf8",
    );
    expect(guardSrc).toContain('"voa-copy.ts"');
  });
});

// ---------------------------------------------------------------------------
// The rendered proof: the same wizard, in Indonesian, because a URL asked.
// ---------------------------------------------------------------------------

const searchParams = vi.hoisted(() => ({ current: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/visa/voa",
  useSearchParams: () => searchParams.current,
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => ({
      viewed: vi.fn(),
      wizardStep: vi.fn(),
      wizardAbandoned: vi.fn(),
      formSubmitted: vi.fn(),
      formSubmitFailed: vi.fn(),
    }),
  };
});

describe("voa-i18n — rendered", () => {
  it("serves English when nobody asks", async () => {
    searchParams.current = new URLSearchParams();
    const { default: Page } = await import("./page");
    render(<Page />);
    expect(screen.getByText("What are you here for?")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Next" })).toBeTruthy();
    expect(document.documentElement.lang).toBe("en");
  });

  it("serves Indonesian on ?lang=id — copy AND wizard chrome", async () => {
    searchParams.current = new URLSearchParams("lang=id");
    const { default: Page } = await import("./page");
    render(<Page />);
    expect(screen.getByText("Apa yang Anda perlukan?")).toBeTruthy();
    expect(screen.getByText("Mengurus Visa on Arrival baru")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Lanjut" })).toBeTruthy();
    expect(screen.getByText("Langkah 1 dari 4")).toBeTruthy();
    expect(document.documentElement.lang).toBe("id");
  });
});
