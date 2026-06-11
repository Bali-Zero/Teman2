"use client";

import type { ReactNode } from "react";
import { trackPersonaDoor, type PersonaDoor } from "@/lib/analytics";

/**
 * PersonaDoors — MYTHOS B2 (IA-1): three task-framed doors directly after
 * the hero. "Start where you are." — the visitor self-selects by situation,
 * not by tool name (Fragomen P10 / GOV.UK P5 exemplar pattern).
 *
 * Rumah Putih rules applied:
 *  - warm-paper editorial band (light insert between dark sections)
 *  - Cormorant headings / Inter utility (rule 3)
 *  - soft CTAs in navy, NO red anywhere in this section (rules 4+8)
 *  - one concrete fact line per door, numbers over adjectives (rule 2)
 *
 * Fact lines verified against the codebase 2026-06-11:
 *  - E33G / C1: live visa funnel + SocialProof reference both codes
 *  - 1,563 KBLI codes: kbli/page.tsx + sitemap.ts (the mockup said 1,790 —
 *    unverifiable, swapped for the verified count)
 *  - leasehold 25–30 yr: property KB ground truth (W68 scar verification)
 *
 * Measurement: persona_door_click (payload: door) — FUNNEL_EVENTS +
 * backend ALLOWED_EVENTS, parity-tested.
 */

const PAPER = "#f7f6f2";
const HAIRLINE = "#e3e1da";
const NAVY = "#1e3863";
const INK_SOFT = "#475372";

interface Door {
  door: PersonaDoor;
  title: string;
  body: string;
  fact: ReactNode;
  href: string;
}

const DOORS: Door[] = [
  {
    door: "visa",
    title: "I'm moving to Bali",
    body: "Visas, KITAS, family permits. Find the permit that matches your plan — before you book the flight.",
    fact: (
      <>
        Most common: <b style={{ color: NAVY }}>E33G remote-worker</b> ·{" "}
        <b style={{ color: NAVY }}>C1 tourism</b>
      </>
    ),
    href: "/visa",
  },
  {
    door: "company",
    title: "I'm starting a business",
    body: "PT PMA setup, KBLI codes, licensing. From idea to a legal Indonesian company — without the nominee traps.",
    fact: (
      <>
        Tool: <b style={{ color: NAVY }}>KBLI Navigator</b> · 1,563 codes mapped
      </>
    ),
    href: "/kbli",
  },
  {
    door: "property",
    title: "I'm buying property",
    body: "Leasehold vs freehold, zoning, due diligence. Know what you can legally own before you wire a deposit.",
    fact: (
      <>
        Guide: <b style={{ color: NAVY }}>leasehold 25–30 yr</b> · zoning checks
      </>
    ),
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {DOORS.map(({ door, title, body, fact, href }) => (
            <article
              key={door}
              className="flex flex-col gap-4 rounded-xl p-8 transition-colors"
              style={{
                background: "#ffffff",
                border: `1px solid ${HAIRLINE}`,
              }}
            >
              <h3
                style={{
                  fontFamily: "var(--font-serif)",
                  fontWeight: 600,
                  fontSize: 28,
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
              <div
                style={{
                  fontSize: 13,
                  color: INK_SOFT,
                  borderTop: `1px solid ${HAIRLINE}`,
                  paddingTop: 16,
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
          ))}
        </div>
      </div>
    </section>
  );
}
