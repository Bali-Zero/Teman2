"use client";

import {
  AppBranchSelector,
  AppFrame,
  AppTrustStrip,
  useFunnelApp,
} from "@balizero/core";

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
            { value: "4.8h", label: "avg first-reply on WhatsApp" },
          ]}
        />
      }
    >
      {/* Ambient video — 12% opacity screen-blend, full-bleed behind AppFrame main */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          overflow: "hidden",
          pointerEvents: "none",
          zIndex: 0,
        }}
      >
        <video
          muted
          loop
          playsInline
          preload="none"
          poster="/video/bali-ambient-poster.jpg"
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
        >
          <source src="/video/bali-ambient-loop.mp4" type="video/mp4" />
        </video>
      </div>

      <div style={{ position: "relative", zIndex: 1, display: "grid", gap: "var(--space-5, 2rem)" }}>
        {/* Live marker */}
        <div style={{
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
        }}>
          <span aria-hidden style={{
            display: "inline-block",
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            background: "var(--accent-funnel)",
            animation: "bz-live-pulse 2.4s ease-in-out infinite",
          }} />
          Ambient · Bali
        </div>

        <AppBranchSelector
          question="Are you already in Indonesia?"
          options={[
            {
              id: "clock",
              title: "Yes, I'm here",
              description: "Tell us which visa and when you entered. We'll build your expiry timeline.",
              href: "/visa/clock",
            },
            {
              id: "match",
              title: "No, I'm planning",
              description: "Answer 4 short questions. We'll recommend the right visa and show the cost.",
              href: "/visa/match",
            },
          ]}
          onSelect={(opt) => tracker.branchSelected(opt.id)}
        />

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
    </AppFrame>
  );
}
