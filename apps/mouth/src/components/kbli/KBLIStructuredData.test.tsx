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

  it("innocence: a Perpres-sourced TERBATAS code keeps the existing structured-data clause verbatim", () => {
    const code = getAllCodes().find(
      (c) =>
        c.pma.status === "restricted" &&
        !!c.pma.source?.startsWith("Perpres 10/2021") &&
        c.provenance?.pma.status !== "untraceable_basis",
    ) as KBLICode;
    expect(code).toBeDefined();
    const jsonLd = jsonLdOf(code);
    expect(jsonLd.description as string).toContain(
      "per Perpres 10/2021 as amended (crosswalk to KBLI 2025 pending)",
    );
  });
});

describe("structured data — untraceable BPS ancestry", () => {
  it("guilt: 01287 emits the BPS-specific gap and no audit-in-progress claim in either JSON-LD block", () => {
    const code = getCode("01287") as KBLICode;
    expect(code.provenance?.pma.status).toBe("untraceable_basis");

    const article = JSON.stringify(jsonLdOf(code));
    const faq = JSON.stringify(faqJsonLdOf(code));
    expect(article).toContain(
      "The official BPS crosswalk records no KBLI-2020 predecessor",
    );
    expect(faq).toContain(
      "No official BPS 2020 → 2025 crosswalk ancestor is recorded",
    );
    expect(article).not.toContain("crosswalk audit in progress");
    expect(faq).not.toContain("crosswalk audit in progress");
  });

  it("innocence: a BPS-ancestry code keeps the pending-crosswalk attribution", () => {
    const code = getCode("01111") as KBLICode;
    expect(code.provenance?.pma.status).toBe("pending_crosswalk");
    expect(JSON.stringify(jsonLdOf(code))).toContain(
      "crosswalk to KBLI 2025 pending",
    );
  });
});
