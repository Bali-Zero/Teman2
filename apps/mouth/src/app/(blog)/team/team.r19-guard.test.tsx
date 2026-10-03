import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import TeamPage from "./page";
import styles from "./team.module.css";

// R19 guard (common rules, R19 group B): this page's real old-design offender is not a
// Tailwind color className (this route barely uses any) but a literal linear-gradient
// baked into an inline `style` per team member (page.tsx's `member.gradient`). So this
// guard checks BOTH: (1) the className-based forbidden set the common rules define, in
// case a literal Tailwind color utility ever creeps in, and (2) every rendered element's
// inline `style` attribute for a `gradient(...)` value or a literal hex color that is not
// merely a `var(--x, #fallback)` safety net.
const FORBIDDEN_CLASS =
  /(^|[\s"'`])(bg-gradient-|text-white\b|bg-black\b|border-white\/|bg-white\/|font-black\b|font-extrabold\b|(sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-\d{2,3})/;

describe("/team — R19 guard: no pre-R19 literal color/gradient escapes a token", () => {
  it("renders with no forbidden Tailwind color className and no inline gradient/hex background", () => {
    const { container } = render(<TeamPage />);

    // Scoped to this lane's own markup (`styles.page` wraps everything this page
    // owns), so the shared `<GoogleReviewsBlock>` sibling — out of this lane, per
    // the R19-B common rules — isn't swept into a guard it doesn't own.
    const scope = container.querySelector(`.${CSS.escape(styles.page)}`);
    expect(scope, "the page's own container did not render").not.toBeNull();

    const all = scope!.querySelectorAll("*");
    expect(all.length).toBeGreaterThan(0);

    for (const el of Array.from(all)) {
      const cls = el.getAttribute("class") ?? "";
      expect(cls, `forbidden class on <${el.tagName}>: "${cls}"`).not.toMatch(
        FORBIDDEN_CLASS,
      );

      const style = el.getAttribute("style") ?? "";
      expect(
        style,
        `inline gradient background on <${el.tagName}>: "${style}"`,
      ).not.toMatch(/gradient\(/i);

      // A literal hex is fine ONLY as a var() fallback (`var(--x, #fff)`) — strip those
      // out first, then anything left is a color leaking straight past the token layer.
      const hexOutsideVar = style.replace(/var\([^)]*\)/g, "");
      expect(
        hexOutsideVar,
        `literal hex outside a var() fallback on <${el.tagName}>: "${style}"`,
      ).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});
