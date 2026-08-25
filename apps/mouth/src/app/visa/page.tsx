"use client";

import Link from "next/link";
import {
  AppBranchSelector,
  AppFrame,
  AppTrustStrip,
  useFunnelApp,
} from "@balizero/core";
import { ConsentBanner } from "@/components/visa/ConsentBanner";

export default function VisaEntryPage() {
  const tracker = useFunnelApp("visa_clock"); // "entry" funnel event; branch_selected fires on click

  return (
    <AppFrame
      funnel="visa"
      title="24 visa types. One fits you."
      subtitle="We know which."
      trustStrip={
        <AppTrustStrip
          items={[
            { value: "5,021", label: "visas filed since 2019" },
            { value: "24+", label: "visa categories supported" },
          ]}
        />
      }
    >
      {/* Ambient video — 12% opacity screen-blend, full-bleed behind AppFrame main */}
      <div
        aria-hidden
        className="hidden lg:block"
        style={{
          position: "absolute",
          inset: 0,
          overflow: "hidden",
          pointerEvents: "none",
          zIndex: 0,
        }}
      >
        <img
          aria-hidden
          alt=""
          src="/video/bali-ambient-poster.jpg"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: 0.12,
            mixBlendMode: "screen",
            filter: "hue-rotate(200deg) brightness(0.7) contrast(1.4)",
          }}
        />
      </div>

      <div
        style={{
          position: "relative",
          zIndex: 1,
          display: "grid",
          gap: "var(--space-5, 2rem)",
        }}
      >
        {/* Live marker */}
        <div
          style={{
            position: "absolute",
            top: "-2.5rem",
            right: 0,
            fontSize: "0.6rem",
            opacity: 0.5,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--color-text-muted)",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span
            aria-hidden
            style={{
              display: "inline-block",
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: "var(--accent-funnel)",
              animation: "bz-live-pulse 2.4s ease-in-out infinite",
            }}
          />
          Ambient · Bali
        </div>

        <AppBranchSelector
          question="Are you already in Indonesia?"
          options={[
            {
              id: "clock",
              title: "Yes, I'm here",
              description:
                "Tell us which visa and when you entered. We'll build your expiry timeline.",
              href: "/visa/clock",
            },
            {
              id: "match",
              title: "No, I'm planning",
              description:
                "Answer 4 short questions. We'll recommend the right visa and show the cost.",
              href: "/visa/match",
            },
          ]}
          onSelect={(opt) => tracker.branchSelected(opt.id)}
        />

        <p
          style={{
            textAlign: "center",
            fontSize: "var(--text-sm, 0.88rem)",
            color: "var(--color-text-muted)",
            margin: 0,
          }}
        >
          Have a USD 130,000 deposit in your own name at a state-owned (BUMN)
          Indonesian bank, or a USD 1,000,000 completed strata unit?{" "}
          <Link
            href="/visa/second-home"
            style={{ color: "var(--accent-funnel)" }}
          >
            See the Second Home Visa (E33) →
          </Link>
        </p>

        <style>{`
          @keyframes bz-live-pulse {
            0%, 100% { opacity: 0.3; }
            50%      { opacity: 1; }
          }
          @media (prefers-reduced-motion: reduce) {
            video { display: none !important; }
          }
        `}</style>
      </div>
      <ConsentBanner />
    </AppFrame>
  );
}
