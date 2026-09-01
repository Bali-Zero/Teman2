import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { emptyPlan } from "@/lib/secondhome-studio/plan-codec";
import type { Verdict } from "@/lib/secondhome-studio/types";
import { WhatsAppHandoff } from "./WhatsAppHandoff";

/**
 * WCAG AA contrast guard (measured 2026-08-24): white text on the WhatsApp
 * brand green (`#25D366`) computes to ~1.98:1, badly failing the 4.5:1
 * normal-text floor. Ratified cure (app/(visa-oracle)/visa-oracle/oracle.css
 * :23-30, 2026-07-17 adversarial review): `#0d3a1f` on `#25D366` ~6.45:1.
 *
 * jsdom resolves neither `color-mix()` nor custom properties, so this
 * asserts on the literal inline style value the component sets rather than
 * a computed color (jsdom's CSSOM normalizes a literal hex it parses to
 * `rgb()` form, hence the expected values below — confirmed live via
 * Playwright render, see the shipping commit for the measured
 * rgb()/contrast numbers).
 */
describe("WhatsAppHandoff", () => {
  const verdict: Verdict = {
    band: "strong_fit",
    product: "E33",
    reasons: [],
    humanReviewNote: null,
  };

  it("keeps the WhatsApp button's ink dark enough on the brand green (WCAG AA)", () => {
    render(<WhatsAppHandoff plan={emptyPlan()} verdict={verdict} />);

    const cta = screen.getByRole("link", { name: /ask us to review my plan/i });

    // Brand green stays byte-identical — only the ink moves.
    expect(cta.style.background).toBe("rgb(37, 211, 102)"); // #25D366
    expect(cta.style.color).toBe("rgb(13, 58, 31)"); // #0d3a1f
    expect(cta.style.color).not.toBe("rgb(255, 255, 255)"); // was #fff
  });
});
