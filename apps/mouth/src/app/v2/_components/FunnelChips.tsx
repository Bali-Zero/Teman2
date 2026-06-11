"use client";

import { trackFunnelCTA } from "@/lib/analytics";

/**
 * FunnelChips — MYTHOS B2 (IA-7 demotion): the four full-bleed FunnelFeature
 * blocks leave the homepage; the tools survive as a compact ghost-chip strip
 * for visitors who already know what they need. PersonaDoors (IA-1) is now
 * the navigation layer for everyone else.
 *
 * Preserved from FunnelFeature (do not regress):
 *  - every primary link target (FUNNEL_HREF values, verbatim)
 *  - trackFunnelCTA(funnel, "cta_click") instrumentation — #1277/#1274
 *    canonicalization (property → property_cta_clicked) flows through it
 *  - the #visa/#kbli/#tax/#property in-page anchors used by NAV_ITEMS
 *
 * Deliberately dropped from the homepage (documented divergence): the
 * per-funnel "See transparent pricing" secondary CTAs — CTA-surplus is the
 * audited defect (pack §2a-1); pricing returns properly with IA-6.
 * Regulation Watch chip from the mockup is omitted: no route exists yet
 * (IA-5 ships in B5).
 */

const HAIRLINE = "#e3e1da";
const NAVY = "#1e3863";
const INK_SOFT = "#475372";

interface Chip {
  funnel: "visa" | "kbli" | "tax" | "property";
  label: string;
  sub: string;
  href: string;
}

// Link targets verbatim from FunnelFeature.FUNNEL_HREF — preserved.
const CHIPS: Chip[] = [
  {
    funnel: "visa",
    label: "Visa Oracle",
    sub: "check your visa",
    href: "https://visa.balizero.com/",
  },
  {
    funnel: "kbli",
    label: "KBLI Navigator",
    sub: "find your code",
    href: "/kbli",
  },
  {
    funnel: "tax",
    label: "Tax Intelligence",
    sub: "deadlines",
    href: "https://tax.balizero.com/",
  },
  {
    funnel: "property",
    label: "Property Map",
    sub: "zoning",
    href: "/property/eligibility",
  },
];

export function FunnelChips() {
  return (
    <section
      id="tools"
      data-testid="funnel-chips"
      style={{
        background: "#ffffff",
        borderBottom: `1px solid ${HAIRLINE}`,
      }}
    >
      {/* P3 — 8pt rhythm: 48px band padding, 16px chip gaps */}
      <div className="max-w-[1120px] mx-auto px-6 py-10 md:py-12">
        <div
          className="mb-6 font-semibold uppercase"
          style={{
            fontSize: 13,
            letterSpacing: "0.12em",
            color: INK_SOFT,
          }}
        >
          Tools &amp; channels — when you already know what you need
        </div>
        <div className="flex flex-wrap gap-4">
          {CHIPS.map(({ funnel, label, sub, href }) => {
            const external = href.startsWith("http");
            return (
              <a
                key={funnel}
                id={funnel}
                href={href}
                target={external ? "_blank" : undefined}
                rel={external ? "noopener noreferrer" : undefined}
                className="scroll-mt-24 rounded-full px-[18px] py-2.5 font-medium transition-colors hover:underline underline-offset-4"
                style={{
                  fontSize: 14,
                  color: NAVY,
                  border: `1px solid ${HAIRLINE}`,
                  background: "transparent",
                  textDecoration: "none",
                }}
                onClick={() => trackFunnelCTA(funnel, "cta_click")}
              >
                {label}{" "}
                <small style={{ color: INK_SOFT, fontWeight: 400 }}>
                  · {sub}
                </small>
              </a>
            );
          })}
        </div>
      </div>
    </section>
  );
}
