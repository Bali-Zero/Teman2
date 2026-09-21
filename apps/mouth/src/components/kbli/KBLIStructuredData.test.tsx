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
  // 2026-09-18 naso PR-3: 01287 moved declared_gap→located (UU 25/2007
  // Pasal 12(2) item, statutory closure); 20119 (TERTUTUP, declared_gap,
  // BPS ancestors 20111/20114) is the exemplar now.
  it("guilt: 20119 emits the declared gap and no 100% ownership promise", () => {
    const code = getCode("20119") as KBLICode;
    expect(code.provenance?.pma.status).toBe("declared_gap");

    const article = JSON.stringify(jsonLdOf(code));
    const faq = JSON.stringify(faqJsonLdOf(code));
    expect(article).toContain("not yet verified");
    expect(faq).toContain("recorded KBLI 2020 ancestor(s) 20111, 20114");
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
// A Bali APPLIED closure is self-sufficient evidence for the JSON-LD too —
// Google/AI answers must not read a national "not yet verified" gap as
// silence about Bali (added 2026-09-16, W-J B1 disclose).
// =============================================================================
describe("structured data — a sourced Bali closure on an unverified national record", () => {
  // Review F2: `pmaAttribution` must sit right after "nationally" and must
  // never be appended a second time after the Bali clause — the exact
  // rendered `pmaLabel` is pinned here, not just a loose substring, so a
  // regression that trails or duplicates the attribution fails this test.
  it("68111 (unscoped, HIGH confidence): pmaAttribution sits right after 'nationally', once, and the Bali clause names no qualifier", () => {
    const code = getCode("68111") as KBLICode;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4).toMatchObject({ status: "CHIUSO_BALI", blocked: true });
    expect(code.baliL4?.confidence).toBe("HIGH");
    expect(code.baliL4?.closure?.scopeQualifier).toBeFalsy();

    const jsonLd = jsonLdOf(code);
    const description = jsonLd.description as string;
    const pmaLabel =
      "Foreign-ownership status not yet verified for this KBLI 2025 code" +
      " nationally — no adjudicated per-code official basis and vintage" +
      " currently verify this verdict; confirm it at oss.go.id. In Bali:" +
      " closed to new PT PMA licensing (Bali Provincial Government, 2026)";
    expect(description).toContain(pmaLabel);
    // The attribution clause appears exactly once — never trailed a second
    // time after the Bali clause.
    expect(
      description.split("no adjudicated per-code official basis").length - 1,
    ).toBe(1);
  });

  it("55101 (Five-Star Hotel, scoped: building area under 6,000 m²): the scope rides on the Bali clause, not the national one", () => {
    const code = getCode("55101") as KBLICode;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.confidence).toBe("HIGH");
    expect(code.baliL4?.closure?.scopeQualifier).toBe(
      "building area under 6,000 m²",
    );

    const jsonLd = jsonLdOf(code);
    const description = jsonLd.description as string;
    const pmaLabel =
      "Foreign-ownership status not yet verified for this KBLI 2025 code" +
      " nationally — no adjudicated per-code official basis and vintage" +
      " currently verify this verdict; confirm it at oss.go.id. In Bali:" +
      " closed to new PT PMA licensing for building area under 6,000 m²" +
      " (Bali Provincial Government, 2026)";
    expect(description).toContain(pmaLabel);
    expect(
      description.split("no adjudicated per-code official basis").length - 1,
    ).toBe(1);
  });

  it("47211 (MEDIUM confidence, unscoped): the conservative-reading caveat rides on the Bali clause", () => {
    const code = getCode("47211") as KBLICode;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4?.confidence).toBe("MEDIUM");
    expect(code.baliL4?.closure?.scopeQualifier).toBeFalsy();

    const jsonLd = jsonLdOf(code);
    const description = jsonLd.description as string;
    expect(description).toContain(
      "In Bali: closed to new PT PMA licensing (conservative reading: this" +
        " 2025 code also covers activities not on Bali's list) (Bali" +
        " Provincial Government, 2026)",
    );
  });

  it("62900 (unlocated, no sourced closure) keeps the plain not-yet-verified label", () => {
    // 01192 was this test's example until naso PR-5 (residual lot 2) located
    // it. 62900 carries the same ATTENZIONE_FASCIA_BALI status and stays
    // declared_gap (withheld by that lot's legacy_pma_prose leg).
    const code = getCode("62900") as KBLICode;
    expect(code.provenance?.pma.status).toBe("declared_gap");
    expect(code.baliL4).toBeUndefined();

    const article = JSON.stringify(jsonLdOf(code));
    expect(article).toContain(
      "Foreign-ownership status not yet verified for this KBLI 2025 code —",
    );
    expect(article).not.toContain("closed to new PT PMA licensing in Bali");
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
