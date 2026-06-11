"use client";

import type { ReactNode } from "react";
import {
  trackFunnelCTA,
  trackPersonaDoor,
  type PersonaDoor,
} from "@/lib/analytics";

/**
 * PersonaDoors — MYTHOS B2R2 (IA-1, iteration 2): four task-framed doors
 * directly after the hero. "Start where you are." — the visitor self-selects
 * by situation, not by tool name (Fragomen P10 / GOV.UK P5 exemplar pattern).
 *
 * B2R2 (Antonello 2026-06-11):
 *  - FOUR doors now (tax added THIRD): moving · business · tax · property
 *  - the FunnelChips strip is gone — each door carries its tool identity
 *    as a bold tool-link line (label · sub verbatim from the old chips,
 *    href byte-identical to FunnelFeature.FUNNEL_HREF; D10 not resolved
 *    here). Tool links keep the chips' trackFunnelCTA(funnel, "cta_click")
 *    instrumentation; the door CTA keeps persona_door_click.
 *  - the #visa/#kbli/#tax/#property in-page anchors used by NAV_ITEMS now
 *    live on the door cards (they pointed at the chips before).
 *
 * Rumah Putih rules applied:
 *  - warm-paper editorial band (light insert between dark sections)
 *  - Cormorant headings / Inter utility (rule 3)
 *  - soft CTAs in navy, NO red anywhere in this section (rules 4+8)
 *  - one concrete fact line per door, numbers over adjectives (rule 2)
 *
 * Fact lines verified against the codebase 2026-06-11:
 *  - E33G / C1: live visa funnel + SocialProof reference both codes
 *  - 1,563 KBLI codes: kbli/page.tsx + sitemap.ts
 *  - PPh · PPN · LKPM: TAX_DEADLINES kinds in
 *    app/api/tax-calendar/deadlines.ts (the tax.balizero.com calendar)
 *  - leasehold 25–30 yr: property KB ground truth (W68 scar verification)
 *
 * Measurement: persona_door_click (payload: door = visa|company|tax|property)
 * + per-tool <funnel>_cta_click — FUNNEL_EVENTS + backend ALLOWED_EVENTS,
 * parity-tested.
 */

const PAPER = "#f7f6f2";
const HAIRLINE = "#e3e1da";
const NAVY = "#1e3863";
const INK_SOFT = "#475372";

interface Door {
  door: PersonaDoor;
  /** Funnel id — also the in-page anchor (#visa/#kbli/#tax/#property). */
  funnel: "visa" | "kbli" | "tax" | "property";
  title: string;
  body: string;
  fact: ReactNode;
  /** Tool identity (ex-FunnelChips): label · sub, href byte-identical. */
  tool: { label: string; sub: string; href: string };
  href: string;
}

const DOORS: Door[] = [
  {
    door: "visa",
    funnel: "visa",
    title: "I'm moving to Bali",
    body: "Visas, KITAS, family permits. Find the permit that matches your plan — before you book the flight.",
    fact: (
      <>
        Most common: <b style={{ color: NAVY }}>E33G remote-worker</b> ·{" "}
        <b style={{ color: NAVY }}>C1 tourism</b>
      </>
    ),
    tool: {
      label: "Visa Oracle",
      sub: "check your visa",
      href: "https://visa.balizero.com/",
    },
    href: "/visa",
  },
  {
    door: "company",
    funnel: "kbli",
    title: "I'm starting a business",
    body: "PT PMA setup, KBLI codes, licensing. From idea to a legal Indonesian company — without the nominee traps.",
    fact: (
      <>
        <b style={{ color: NAVY }}>1,563 KBLI codes</b> mapped
      </>
    ),
    tool: {
      label: "KBLI Navigator",
      sub: "find your code",
      href: "/kbli",
    },
    href: "/kbli",
  },
  {
    door: "tax",
    funnel: "tax",
    title: "I'm already here — taxes confuse me",
    body: "NPWP, monthly SPT, Coretax — Indonesian tax has its own alphabet. One calendar of what you owe and when, instead of guesswork.",
    fact: (
      <>
        <b style={{ color: NAVY }}>PPh · PPN · LKPM</b> deadlines tracked
      </>
    ),
    tool: {
      label: "Tax Intelligence",
      sub: "deadlines",
      href: "https://tax.balizero.com/",
    },
    href: "https://tax.balizero.com/",
  },
  {
    door: "property",
    funnel: "property",
    title: "I'm buying property",
    body: "Leasehold vs freehold, zoning, due diligence. Know what you can legally own before you wire a deposit.",
    fact: (
      <>
        Guide: <b style={{ color: NAVY }}>leasehold 25–30 yr</b> · zoning checks
      </>
    ),
    tool: {
      label: "Property Map",
      sub: "zoning",
      href: "/property/eligibility",
    },
    href: "/property",
  },
];

export function PersonaDoors() {
  return (
    <section
      id="start"
      data-testid="persona-doors"
      style={{
        background: PAPER,
        borderTop: `1px solid ${HAIRLINE}`,
        borderBottom: `1px solid ${HAIRLINE}`,
      }}
    >
      {/* P3 — 8pt rhythm: 64px band padding, 24px gutters/gaps */}
      <div className="max-w-[1120px] mx-auto px-6 py-12 md:py-16">
        <h2
          className="mb-8"
          style={{
            fontFamily: "var(--font-serif)",
            fontWeight: 600,
            fontSize: 30,
            lineHeight: 1.15,
            color: NAVY,
          }}
        >
          Start where you are.
        </h2>
        {/* B2R2: 4 doors — stacked on mobile, 2×2 on tablet, 4-up on
            desktop (cards slimmed: p-6, 24px headings). */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {DOORS.map(({ door, funnel, title, body, fact, tool, href }) => {
            const toolExternal = tool.href.startsWith("http");
            return (
              <article
                key={door}
                id={funnel}
                className="scroll-mt-24 flex flex-col gap-4 rounded-xl p-6 transition-colors"
                style={{
                  background: "#ffffff",
                  border: `1px solid ${HAIRLINE}`,
                }}
              >
                <h3
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontWeight: 600,
                    fontSize: 24,
                    lineHeight: 1.15,
                    color: NAVY,
                  }}
                >
                  {title}
                </h3>
                <p
                  className="flex-1"
                  style={{
                    fontSize: 15,
                    lineHeight: 1.55,
                    color: INK_SOFT,
                  }}
                >
                  {body}
                </p>
                {/* Tool identity line (ex-FunnelChips) — bold tool title,
                    href + cta_click instrumentation preserved verbatim. */}
                <a
                  href={tool.href}
                  data-tool={funnel}
                  target={toolExternal ? "_blank" : undefined}
                  rel={toolExternal ? "noopener noreferrer" : undefined}
                  className="font-bold hover:underline underline-offset-4"
                  style={{
                    fontSize: 15,
                    color: NAVY,
                    borderTop: `1px solid ${HAIRLINE}`,
                    paddingTop: 16,
                    textDecoration: "none",
                  }}
                  onClick={() => trackFunnelCTA(funnel, "cta_click")}
                >
                  {tool.label}{" "}
                  <small style={{ color: INK_SOFT, fontWeight: 400 }}>
                    · {tool.sub}
                  </small>
                </a>
                <div
                  style={{
                    fontSize: 13,
                    color: INK_SOFT,
                  }}
                >
                  {fact}
                </div>
                {/* Soft CTA — navy, never red (rule 8: high-stakes steps get
                    soft primary wording, no urgency mechanics) */}
                <a
                  href={href}
                  data-door={door}
                  className="mt-1 font-semibold hover:underline underline-offset-4"
                  style={{
                    fontSize: 15,
                    color: NAVY,
                    textDecoration: "none",
                  }}
                  onClick={() => trackPersonaDoor(door)}
                >
                  See how it works →
                </a>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
