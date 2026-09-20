import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VOA_COPY, fill, voaCopy, type VoaCopyKey } from "./voa-copy";
import { resolveVoaLocale, VOA_LOCALE_RULING } from "./voa-locale";
import { NextSteps } from "./NextSteps";
import { SafeClockHero } from "./SafeClock";

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

/**
 * THE CONSUMERS ARE FOUR FILES, not one, and the day the funnel's second leg
 * started reading the dictionary this list had to say so. A guard that scans
 * `page.tsx` alone would call every verdict-leg key an orphan (and, worse,
 * would certify "no hardcoded sentence" over a screen that no longer holds
 * the copy anyone reads) — cicatrix family #3 in both directions at once.
 *
 * Kept in step with `voa-copy.guard.test.ts`'s own SCREEN_FILES by the last
 * test in this file, which refuses to let one list name a screen the other
 * has never heard of.
 */
const CONSUMER_FILES = [
  "page.tsx", // the wizard
  "[hash]/page.tsx", // the verdict: ACCEPT, DECLINE, deleted, error, loading
  "SafeClock.tsx", // the published-deadline hero
  "NextSteps.tsx", // what happens next / what we cannot promise
  // The DECLINE education table, which lives one tree over (the claims guard
  // reaches it the same way, by the same relative hops).
  "../../../components/garuda/declineEducation.ts",
];

const CONSUMER_SRC: Record<string, string> = Object.fromEntries(
  CONSUMER_FILES.map((rel) => [rel, readFileSync(join(VOA_DIR, rel), "utf8")]),
);
const ALL_CONSUMER_SRC = Object.values(CONSUMER_SRC).join("\n");

const DECLINE_SRC =
  CONSUMER_SRC["../../../components/garuda/declineEducation.ts"];

/**
 * THE ONE FAMILY A SUBSTRING SEARCH CANNOT SEE. The DECLINE sentences are
 * addressed by a TEMPLATE literal — `t(\`decline.${code}.mirror\`)` — so
 * `"decline.GROUP_CASE.mirror"` appears nowhere as a literal and the orphan
 * rule would convict all 57 of them. Weakening the rule for everyone to
 * accommodate one family is how a guard quietly stops guarding, so instead
 * the family is RESOLVED the way the code resolves it: expand the reason-code
 * union against the three parts. What that buys is checked below in both
 * directions — an unexpanded key still counts as an orphan, and an expansion
 * with no key in the register still fails.
 */
const DECLINE_CODES = (
  DECLINE_SRC.split("export type DeclineCode =")[1]?.split(";")[0] ?? ""
)
  .match(/"[A-Z_]+"/g)!
  .map((q) => q.slice(1, -1));

const DECLINE_PARTS = ["mirror", "forbids", "alternative"] as const;

const GENERATED = new Set<VoaCopyKey>(
  DECLINE_CODES.flatMap((c) =>
    DECLINE_PARTS.map((part) => `decline.${c}.${part}` as VoaCopyKey),
  ),
);

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
  "verdict.title": "the permit's printed name, never translated",
  "verdict.share.title":
    "the brand and the permit's printed name, nothing else",
  "entry.emailPlaceholder": "an example address, not a sentence",
  "verdict.wa.priceLabel": "CRM lead context, English on purpose",
  "purpose.transit": "the same word in both languages",
  "decline.purpose.transit": "the same word in both languages",
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
  it("no key is orphaned: some screen in the leg renders each one", () => {
    const orphans = keys
      .filter((k) => !GENERATED.has(k))
      .filter((k) => !ALL_CONSUMER_SRC.includes(`"${k}"`));
    expect(orphans).toEqual([]);
  });

  it("is GUILTY of an orphan key (guilt control)", () => {
    const orphans = [...keys, "frame.subtitle.v2"]
      .filter((k) => !GENERATED.has(k as VoaCopyKey))
      .filter((k) => !ALL_CONSUMER_SRC.includes(`"${k}"`));
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

  it("no screen in the leg holds a hardcoded sentence any more", () => {
    const offences = Object.entries(CONSUMER_SRC).flatMap(([rel, src]) =>
      proseIn(src).map((sentence) => `${rel}: ${sentence}`),
    );
    expect(offences).toEqual([]);
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

  it("a language carried from earlier in the journey still decides", () => {
    expect(resolveVoaLocale({ requested: null, session: "id" })).toBe("id");
    // An explicit ?lang= on THIS screen outranks what the tab carried.
    expect(resolveVoaLocale({ requested: "en", session: "id" })).toBe("en");
    // ...and the carry is not a back door for junk.
    expect(resolveVoaLocale({ requested: null, session: "de" })).toBe("en");
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

  /**
   * Two lists, one subject. A screen that renders customer copy belongs in
   * BOTH — here, so its keys are not called orphans and its literals are
   * convicted; and there, so a banned claim typed into it is convicted too.
   * Checking the inclusion mechanically is cheaper than remembering it.
   */
  it("the DECLINE family is generated, and the expansion matches the register", () => {
    // The union really was read (a silent regex miss would make this vacuous).
    expect(DECLINE_CODES.length).toBeGreaterThan(15);
    // Direction 1 — every expansion exists as a key. Types already enforce
    // this at build time via `DeclineSentenceKey`; asserted here so the
    // failure names the missing sentence instead of a type error in a file
    // nobody was editing.
    const absent = [...GENERATED].filter((k) => !keys.includes(k));
    expect(absent).toEqual([]);
    // Direction 2 — every `decline.<CODE>.` key in the register is one the
    // expansion produces, so a key for a retired code cannot linger.
    const stray = keys.filter(
      (k) => /^decline\.[A-Z_]+\./.test(k) && !GENERATED.has(k),
    );
    expect(stray).toEqual([]);
    // ...and the template that makes them reachable is really in the file.
    for (const part of DECLINE_PARTS) {
      expect(DECLINE_SRC).toContain(`decline.\${code}.${part}`);
    }
  });

  /**
   * THE TWO LISTS, COMPARED AS PATHS — not as text, and never as basenames.
   *
   * The first version of this check grepped the claims guard's source for the
   * literal relative path. That worked until the out-of-tree DECLINE table
   * joined the set: the claims guard reaches it through a multi-argument
   * `join(VOA_DIR, "..", "..", "..", …)`, so there is no full-path literal to
   * find. Falling back to the BASENAME made it pass — and silently stopped
   * convicting `[hash]/page.tsx`, whose basename `page.tsx` the wizard's own
   * entry already satisfies. One assertion, dropped by the fix to a different
   * one: cicatrix family #3, caught by the gate on this very diff.
   *
   * So both sides are RESOLVED to absolute paths and compared as paths. The
   * guilt control below is the mutation that exposed the basename version.
   */
  function claimsGuardScannedFiles(src: string): Set<string> {
    const screen = src.split("const SCREEN_FILES = [")[1]?.split("].map(")[0];
    const joined = src
      .split("const DECLINE_EDUCATION_FILE = join(")[1]
      ?.split(");")[0];
    if (!screen || !joined) throw new Error("claims guard shape changed");
    const rels = [...screen.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    const hops = [...joined.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    return new Set([
      ...rels.map((rel) => join(VOA_DIR, rel)),
      join(VOA_DIR, ...hops),
    ]);
  }

  const CLAIMS_GUARD_SRC = readFileSync(
    join(VOA_DIR, "voa-copy.guard.test.ts"),
    "utf8",
  );

  it("every consumer this file scans is scanned by the claims guard too", () => {
    const scanned = claimsGuardScannedFiles(CLAIMS_GUARD_SRC);
    // The parse really parsed — a silent split miss would make this vacuous.
    expect(scanned.size).toBeGreaterThan(10);
    const missing = CONSUMER_FILES.filter(
      (rel) => !scanned.has(join(VOA_DIR, rel)),
    );
    expect(missing).toEqual([]);
  });

  it("is GUILTY of the claims guard dropping the verdict screen (guilt control)", () => {
    const sabotaged = CLAIMS_GUARD_SRC.replace(
      /^.*"\[hash\]\/page\.tsx".*\n/m,
      "",
    );
    // The mutation must have bitten, or the control proves nothing.
    expect(sabotaged).not.toBe(CLAIMS_GUARD_SRC);
    const scanned = claimsGuardScannedFiles(sabotaged);
    const missing = CONSUMER_FILES.filter(
      (rel) => !scanned.has(join(VOA_DIR, rel)),
    );
    expect(missing).toEqual(["[hash]/page.tsx"]);
  });

  it("is GUILTY of the claims guard dropping the DECLINE table (guilt control)", () => {
    const sabotaged = CLAIMS_GUARD_SRC.replace(
      '"declineEducation.ts"',
      '"declineEducation.SOMETHING-ELSE.ts"',
    );
    expect(sabotaged).not.toBe(CLAIMS_GUARD_SRC);
    const scanned = claimsGuardScannedFiles(sabotaged);
    const missing = CONSUMER_FILES.filter(
      (rel) => !scanned.has(join(VOA_DIR, rel)),
    );
    expect(missing).toEqual(["../../../components/garuda/declineEducation.ts"]);
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
      // The verdict screen's half of the tracker — the wizard never calls
      // these, and the DECLINE render below would die on the first one.
      resultViewed: vi.fn(),
      ctaClicked: vi.fn(),
      shareClicked: vi.fn(),
      whatsappHandoff: vi.fn(),
      emailSubscribed: vi.fn(),
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

// ---------------------------------------------------------------------------
// The SECOND leg, rendered. The wizard was already proven bilingual above; a
// funnel that answers in English after being asked in Indonesian is the exact
// failure this slice exists to close, and the two pieces the verdict screen
// leads with are the two proven here.
//
// The date under the count is asserted as a FORMAT, not as a string the copy
// file could satisfy: `Intl` decides it, and only passing the locale through
// `formatCivilDay` makes it Indonesian.
// ---------------------------------------------------------------------------
describe("voa-i18n — the verdict leg renders in Indonesian too", () => {
  const DEADLINE = "2026-10-24";
  /** Noon WITA on D-4, so the civil day is unambiguous on either side of UTC. */
  const NOW = new Date("2026-10-20T04:00:00Z");

  /**
   * A NEW TAB per test. `?lang=id` now writes the choice into sessionStorage
   * (that is the whole point of this slice — see the carry test below), and
   * jsdom keeps one storage for the whole file, so without this the second
   * test would inherit the first one's language and "English by default"
   * would be measured on a tab that had already asked for Indonesian.
   */
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("the Safe Clock hero counts, dates and warns in Indonesian", () => {
    searchParams.current = new URLSearchParams("lang=id");
    render(<SafeClockHero deadline={DEADLINE} now={NOW} handoffHref="#wa" />);
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("hari untuk mengajukan")).toBeTruthy();
    expect(screen.getByText(/24 Oktober 2026/)).toBeTruthy();
    expect(screen.queryByText(/24 October 2026/)).toBeNull();
    expect(screen.getByLabelText(VOA_COPY.id["clock.aria"])).toBeTruthy();
  });

  it("the same hero is English when nobody asks", () => {
    searchParams.current = new URLSearchParams();
    render(<SafeClockHero deadline={DEADLINE} now={NOW} handoffHref="#wa" />);
    expect(screen.getByText("days to file")).toBeTruthy();
    expect(screen.getByText(/24 October 2026/)).toBeTruthy();
  });

  it("what-happens-next and what-we-cannot-promise are Indonesian", () => {
    searchParams.current = new URLSearchParams("lang=id");
    render(<NextSteps handoffHref="#wa" hasDeadline />);
    expect(screen.getByText(VOA_COPY.id["next.heading"])).toBeTruthy();
    expect(screen.getByText(VOA_COPY.id["next.limits.heading"])).toBeTruthy();
    expect(screen.getByText(VOA_COPY.id["next.step1"])).toBeTruthy();
    expect(screen.getByText(VOA_COPY.id["next.limit2"])).toBeTruthy();
  });

  /**
   * The `hasDeadline={false}` verdict is a DIFFERENT sentence, not a hidden
   * one: `[hash]/page.tsx` renders no clock at all there, so the step that
   * points at "the date above" would point at nothing.
   */
  it("without a deadline the leg swaps sentences, in both languages", () => {
    searchParams.current = new URLSearchParams("lang=id");
    const { unmount } = render(
      <NextSteps handoffHref="#wa" hasDeadline={false} />,
    );
    expect(screen.getByText(VOA_COPY.id["next.step3.noDeadline"])).toBeTruthy();
    expect(screen.queryByText(VOA_COPY.id["next.step3"])).toBeNull();
    unmount();

    window.sessionStorage.clear();
    searchParams.current = new URLSearchParams();
    render(<NextSteps handoffHref="#wa" hasDeadline={false} />);
    expect(screen.getByText(VOA_COPY.en["next.step3.noDeadline"])).toBeTruthy();
  });

  /**
   * THE BUG THIS SLICE CLOSES, stated as a test. The wizard reaches the
   * verdict with `router.push(\`/visa/voa/${hash}\`)` — no query string — so
   * before the session carry, a visitor who answered four questions in
   * Indonesian read the price, the deadline and the limits in English. The
   * second render below is that navigation: same tab, no `?lang=`.
   */
  it("the language typed on the first screen survives the navigation", () => {
    searchParams.current = new URLSearchParams("lang=id");
    const { unmount } = render(<NextSteps handoffHref="#wa" hasDeadline />);
    expect(screen.getByText(VOA_COPY.id["next.heading"])).toBeTruthy();
    unmount();

    searchParams.current = new URLSearchParams();
    render(<NextSteps handoffHref="#wa" hasDeadline />);
    expect(screen.getByText(VOA_COPY.id["next.heading"])).toBeTruthy();
  });

  /**
   * THE DECLINE SCREEN, RENDERED. This is the half of the verdict a refused
   * visitor reads, and it is built client-side from the answers this tab
   * holds — so "the copy is in the register" is not enough: the screen has to
   * pass its own `t` down into the builder, and only a render proves it did.
   */
  it("the DECLINE education reaches the screen in Indonesian", async () => {
    searchParams.current = new URLSearchParams("lang=id");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          verdict: "DECLINE",
          reason_codes: ["PURPOSE_NOT_ELIGIBLE"],
        }),
      })),
    );
    const { default: VerdictPage } = await import("./[hash]/page");
    render(<VerdictPage params={Promise.resolve({ hash: "synthetic" })} />);
    expect(
      await screen.findByText(
        VOA_COPY.id["decline.PURPOSE_NOT_ELIGIBLE.forbids"],
      ),
    ).toBeTruthy();
    expect(
      screen.queryByText(VOA_COPY.en["decline.PURPOSE_NOT_ELIGIBLE.forbids"]),
    ).toBeNull();
    vi.unstubAllGlobals();
  });

  /**
   * The builder's default argument is what keeps every existing two-argument
   * caller — and `declineEducation.test.ts`'s English assertions — meaning
   * what they meant. Pinned, because a later refactor that drops the default
   * would silently flip those callers to whatever locale happened to be set.
   */
  it("buildDeclineEducation still answers English when asked for nothing", async () => {
    const { buildDeclineEducation } =
      await import("@/components/garuda/declineEducation");
    const answers = {
      case_type: "issuance",
      nationality: "USA",
      purpose: "transit",
      travellers: 3,
      self_pay: true,
      extension_already_used: false,
    } as const;
    expect(buildDeclineEducation("GROUP_CASE", answers).mirror).toBe(
      VOA_COPY.en["decline.GROUP_CASE.mirror"].replace("{travellers}", "3"),
    );
    expect(
      buildDeclineEducation("GROUP_CASE", answers, voaCopy("id")).mirror,
    ).toBe(
      VOA_COPY.id["decline.GROUP_CASE.mirror"].replace("{travellers}", "3"),
    );
  });

  /** FALSIFICATION: a genuinely fresh tab is still English. */
  it("a tab that never asked reads English", () => {
    searchParams.current = new URLSearchParams();
    render(<NextSteps handoffHref="#wa" hasDeadline />);
    expect(screen.getByText(VOA_COPY.en["next.heading"])).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// The register, as a rule instead of as taste.
//
// The ID column's register was documented in a docblock and enforced by
// nobody, so the first pass shipped a calque (`meja visa` — `meja` is the
// physical table), a literal that is not Imigrasi's term (`tanggal berakhir`
// where the permit says `masa berlaku`), and a word for "check" that reads as
// an official inspection (`pemeriksaan`) in a sentence about deleting one's
// own data. Each row below is a term with a DOCUMENTED replacement, so the
// message can say what to write instead — a ban with no alternative just
// moves the argument to review.
// ---------------------------------------------------------------------------
const ID_REGISTER_BANS: Array<{ re: RegExp; write: string; why: string }> = [
  {
    re: /\bkamu\b/i,
    write: "Anda",
    why: "the register is warm-formal; `kamu` addresses a friend, not a client",
  },
  {
    re: /tanggal berakhir/i,
    write: "masa berlaku",
    why: "Imigrasi's own term for a permit's validity",
  },
  {
    re: /\bmeja visa\b/i,
    write: "tim visa",
    why: "`meja` is the furniture; the English `desk` meaning a team does not carry",
  },
  {
    re: /menghapus pemeriksaan/i,
    write: "menghapus data pengecekan",
    why: "`pemeriksaan` reads as an official inspection, not the customer's own record",
  },
];

describe("voa-i18n — the Indonesian register is enforced, not described", () => {
  it("no banned term survives in the id column", () => {
    const offences: string[] = [];
    for (const key of keys) {
      for (const ban of ID_REGISTER_BANS) {
        if (ban.re.test(VOA_COPY.id[key])) {
          offences.push(`${key}: write "${ban.write}" — ${ban.why}`);
        }
      }
    }
    expect(offences).toEqual([]);
  });

  it("is GUILTY of each banned term (guilt control, one row at a time)", () => {
    const samples: Array<[string, string]> = [
      ["Apa kewarganegaraan kamu?", "Anda"],
      ["Tanggal berakhir paspor", "masa berlaku"],
      ["Meja visa kami menjawab di WhatsApp.", "tim visa"],
      ["saya dapat menghapus pemeriksaan ini", "menghapus data pengecekan"],
    ];
    for (const [sentence, expected] of samples) {
      const hit = ID_REGISTER_BANS.find((ban) => ban.re.test(sentence));
      expect(hit?.write, sentence).toBe(expected);
    }
  });

  it("is INNOCENT on the cured strings (innocence control)", () => {
    const cured = [
      "Masa berlaku paspor",
      "Tim visa kami menjawab di WhatsApp.",
      "saya dapat menghapus data pengecekan ini kapan saja",
      "Apa kewarganegaraan Anda?",
    ];
    for (const sentence of cured) {
      expect(
        ID_REGISTER_BANS.some((ban) => ban.re.test(sentence)),
        sentence,
      ).toBe(false);
    }
  });

  /**
   * The English column is NOT scanned: `tanggal berakhir` cannot appear there
   * and `kamu` is not an English word, so running these over `en` would only
   * create a second place for the list to drift. Stated because a reader will
   * wonder, and a silent asymmetry is how a guard loses half its subject.
   */
  it("the bans are scoped to the id column on purpose", () => {
    expect(ID_REGISTER_BANS.length).toBeGreaterThan(0);
    expect(
      ID_REGISTER_BANS.some((ban) =>
        keys.some((key) => ban.re.test(VOA_COPY.en[key])),
      ),
    ).toBe(false);
  });
});
