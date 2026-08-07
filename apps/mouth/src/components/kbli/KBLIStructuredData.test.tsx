import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { getAllCodes, getCode } from "@/lib/kbli-data";
import type { KBLICode } from "@/lib/kbli-types";
import { KBLICodeJsonLd } from "./KBLIStructuredData";

/** Extract the JSON-LD payload the component embeds in its <script> tag. */
function jsonLdOf(code: KBLICode): Record<string, unknown> {
  const html = renderToStaticMarkup(<KBLICodeJsonLd code={code} />);
  const match = html.match(/<script[^>]*>([\s\S]*)<\/script>/);
  expect(match).not.toBeNull();
  return JSON.parse(match![1]);
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
