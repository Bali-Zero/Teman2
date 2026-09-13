import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { emptyPlan } from "@/lib/secondhome-studio/plan-codec";
import type { Verdict } from "@/lib/secondhome-studio/types";
import { WhatsAppHandoff } from "./WhatsAppHandoff";

/**
 * R4 identity spec guard (research/design/2026-08-27-r4-identity-merah-
 * putih-token-spec.md §3/§4, cure landed 2026-09-01): WhatsApp is the ICON
 * of the human exit, never a text surface — not even at a passing ratio.
 * The 2026-08-24 ink-on-green fix (`#0d3a1f` on `#25D366` ~6.45:1, ratified
 * app/(visa-oracle)/visa-oracle/oracle.css:23-30) answered a different
 * question ("what ink passes AA on a green button?") and the spec rejects
 * a green button outright, on mental-model grounds. The button is now the
 * card-with-icon component: elevated surface (`--surface-raised`),
 * `--border-strong` boundary, ink label (`--text-primary`), with the brand
 * green confined to the Phone glyph alone.
 *
 * jsdom resolves neither `color-mix()` nor custom properties, so this
 * asserts on the literal inline style / SVG attribute value the component
 * sets rather than a computed color — a plain `var(...)` reference (no
 * fallback color jsdom's parser can resolve) is kept as the literal string,
 * confirmed empirically against this jsdom version before writing these
 * assertions (unlike a bare hex, which jsdom's CSSOM normalizes to `rgb()`
 * form — see the old green-pill assertions this test replaces).
 */
describe("WhatsAppHandoff", () => {
  const verdict: Verdict = {
    band: "strong_fit",
    product: "E33",
    reasons: [],
    humanReviewNote: null,
  };

  it("renders the card-with-icon shape: elevated surface, border-strong boundary, ink label", () => {
    render(<WhatsAppHandoff plan={emptyPlan()} verdict={verdict} />);

    const cta = screen.getByRole("link", { name: /ask us to review my plan/i });

    expect(cta.style.background).toBe("var(--surface-raised)");
    expect(cta.style.border).toBe("1px solid var(--border-strong)");
    expect(cta.style.color).toBe("var(--text-primary)");
  });

  it("confines the WhatsApp green to the icon — never a background or label color", () => {
    render(<WhatsAppHandoff plan={emptyPlan()} verdict={verdict} />);

    const cta = screen.getByRole("link", { name: /ask us to review my plan/i });
    const icon = cta.querySelector("svg");

    expect(icon).not.toBeNull();
    expect(icon?.getAttribute("stroke")).toBe(
      "var(--accent-whatsapp, #25d366)",
    );

    // Guard against a regression back to the green pill: neither the link's
    // background nor its label color may carry the brand green again.
    const green = /25d366/i;
    expect(cta.style.background).not.toMatch(green);
    expect(cta.style.color).not.toMatch(green);
  });
});
