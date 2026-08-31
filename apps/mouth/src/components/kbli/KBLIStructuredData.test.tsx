import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { getAllCodes, getCode } from "@/lib/kbli-data";
import type { KBLICode } from "@/lib/kbli-types";
import { KBLICodeJsonLd, KBLIFaqJsonLd } from "./KBLIStructuredData";

/** Extract the JSON-LD payload the component embeds in its <script> tag.
 *
 * String ops, not a regex on HTML: CodeQL's js/bad-tag-filter flags a
 * hand-rolled `<script>...</script>` regex as unsound (it doesn't match
 * uppercase tags or embedded whitespace variants) even where, as here, the
 * markup is our own component's fixed output, not attacker-controlled HTML.
 */
function jsonLdOf(code: KBLICode): Record<string, unknown> {
  const html = renderToStaticMarkup(<KBLICodeJsonLd code={code} />);
  const openTag = html.indexOf("<script");
  const start = html.indexOf(">", openTag) + 1;
  const end = html.lastIndexOf("</script>");
  expect(openTag).toBeGreaterThanOrEqual(0);
  expect(start).toBeGreaterThan(0);
  expect(end).toBeGreaterThanOrEqual(0);
  return JSON.parse(html.slice(start, end));
}

function faqJsonLdOf(code: KBLICode): Record<string, unknown> {
  const html = renderToStaticMarkup(<KBLIFaqJsonLd code={code} />);
  const start = html.indexOf(">") + 1;
  const end = html.lastIndexOf("</script>");
  return JSON.parse(html.slice(start, end));
}

// =============================================================================
// 2026-08-08 fix-pack, item E: pmaAttribution hardcoded "per Perpres 10/2021
// as amended (crosswalk to KBLI 2025 pending)" onto every TERBATAS/TERBUKA
// code's JSON-LD `description`/`about.description` — including the six
// insurance codes this fix-pack adjudicates under PP 14/2018 Pasal 5(1) jo.
// PP 3/2020, a different instrument entirely.
// =============================================================================
describe("KBLICodeJsonLd — pmaAttribution is source-aware (item E)", () => {
  it("guilt: a sector-law-sourced code (65111) attributes PP 14/2018 in the JSON-LD, not Perpres", () => {
    const code = getCode("65111") as KBLICode;
    expect(code.pma.source).toContain("PP 14/2018");
    const jsonLd = jsonLdOf(code);
    const description = jsonLd.description as string;
    expect(description).toContain("PP 14/2018");
    expect(description).not.toContain("crosswalk to KBLI 2025 pending");
  });

  it("innocence: a located Perpres-sourced TERBATAS code is attributed directly", () => {
    const code = getAllCodes().find(
      (c) =>
        c.pma.status === "restricted" &&
        !!c.pma.source?.startsWith("Perpres 10/2021") &&
        c.provenance?.pma.status === "located",
    ) as KBLICode;
    expect(code).toBeDefined();
    const jsonLd = jsonLdOf(code);
    expect(jsonLd.description as string).toContain("per Perpres 10/2021");
  });
});

describe("structured data — whole-verdict PMA gate", () => {
  it("guilt: 01287 emits the declared gap and no 100% ownership promise", () => {
    const code = getCode("01287") as KBLICode;
    expect(code.provenance?.pma.status).toBe("declared_gap");

    const article = JSON.stringify(jsonLdOf(code));
    const faq = JSON.stringify(faqJsonLdOf(code));
    expect(article).toContain("not yet verified");
    expect(faq).toContain("recorded KBLI 2020 ancestor(s) 01287");
    expect(article).not.toContain("100% foreign ownership allowed");
    expect(faq).not.toContain("open to 100% foreign ownership");
  });

  it("innocence: a located sector-law code keeps its verified ownership cap", () => {
    const code = getCode("65111") as KBLICode;
    expect(code.provenance?.pma.status).toBe("located");
    const article = JSON.stringify(jsonLdOf(code));
    expect(article).toContain("80% foreign ownership");
    expect(article).toContain("PP 14/2018");
  });

  it("guilt: a located open status without a publishable cap does not become 100%", () => {
    const base = getCode("02102") as KBLICode;
    const malformed = {
      ...base,
      pma: {
        ...base.pma,
        status: "open",
        maxForeign: null,
        capVerified: false,
      },
    } as KBLICode;

    const article = JSON.stringify(jsonLdOf(malformed));
    expect(article).toContain("ownership cap not verified");
    expect(article).not.toContain("100% foreign ownership allowed");
  });

  it.each([
    [49, false],
    ["special", true],
  ])(
    "guilt: a restricted unverified cap %p never reaches JSON-LD",
    (maxForeign, capSpecial) => {
      const base = getCode("65111") as KBLICode;
      const unverified = {
        ...base,
        pma: {
          ...base.pma,
          status: "restricted",
          maxForeign,
          capSpecial,
          capVerified: false,
        },
      } as KBLICode;

      const article = JSON.stringify(jsonLdOf(unverified));
      expect(article).toContain("ownership cap not verified");
      expect(article).not.toContain("49%");
      expect(article).not.toContain("special non-percentage conditions");
    },
  );

  it("guilt: a located closed verdict with no verified cap stays qualified", () => {
    const base = getCode("65111") as KBLICode;
    const closedWithoutCap = {
      ...base,
      pma: {
        ...base.pma,
        status: "closed",
        maxForeign: null,
        capSpecial: false,
        capVerified: false,
      },
    } as KBLICode;

    const article = JSON.stringify(jsonLdOf(closedWithoutCap));
    expect(article).toContain(
      "Closed to Foreign Investment (ownership cap not verified) (TERTUTUP)",
    );
  });
});

// =============================================================================
// The rendered page translates the risk tier (PR #4776) and the JSON-LD did
// not, so a block declaring `"inLanguage": "en"` shipped `Risk: Menengah
// Rendah` into the description, keywords and GovernmentService that search
// engines read. Measured live on 2026-08-31 at kbli/56101: 22 "Medium-Low" in
// the rendered body, 6 "Menengah Rendah" — every one of them inside JSON-LD.
// =============================================================================
describe("KBLICodeJsonLd — the risk tier is translated in the JSON-LD too", () => {
  it("guilt: a Bahasa tier reaches the JSON-LD in English, not raw", () => {
    const code = getAllCodes().find((c) =>
      /menengah\s+rendah/i.test(c.licensing[0]?.riskCategory ?? ""),
    ) as KBLICode;
    expect(code).toBeDefined();

    const payload = JSON.stringify(jsonLdOf(code));
    expect(payload).toContain("Medium-Low");
    expect(payload).not.toMatch(/Menengah\s+Rendah/i);
  });

  it("innocence: a tier the translator does not recognise is kept verbatim, never dropped", () => {
    const base = getAllCodes().find(
      (c) => !!c.licensing[0]?.riskCategory,
    ) as KBLICode;
    expect(base).toBeDefined();
    const exotic = {
      ...base,
      licensing: [
        { ...base.licensing[0], riskCategory: "Kategori Baru 2027" },
        ...base.licensing.slice(1),
      ],
    } as KBLICode;

    const payload = JSON.stringify(jsonLdOf(exotic));
    expect(payload).toContain("Kategori Baru 2027");
    expect(payload).not.toContain("Unknown");
  });

  it("innocence: a code with no risk tier at all still falls back to Unknown", () => {
    const base = getAllCodes().find(
      (c) => !!c.licensing[0]?.riskCategory,
    ) as KBLICode;
    const bare = {
      ...base,
      licensing: [
        { ...base.licensing[0], riskCategory: undefined },
        ...base.licensing.slice(1),
      ],
    } as unknown as KBLICode;

    expect(JSON.stringify(jsonLdOf(bare))).toContain("Unknown");
  });
});
