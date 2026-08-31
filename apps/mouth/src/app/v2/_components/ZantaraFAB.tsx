"use client";

// Zantara FAB — premium pill with lotus glyph.
// Fixed bottom-right. Brand-navy pill, live status dot, "Ask Zantara" label.
//
// 2026-08-28 brand-accent pass: was a violet gradient (#a78bfa -> #6d28d9),
// the generic SaaS-chatbot palette with no tie to Bali Zero. Because the FAB
// is persistent on every public page it was the most-seen element on the
// site and the least "ours". Repainted to solid brand navy with a gold hair-
// line ring; white label 11.66:1, sub-label 6.28:1 (both AA).
export function ZantaraFAB() {
  return (
    <button
      id="zantara-fab"
      aria-label="Ask Zantara, your AI assistant"
      className="fab-zantara fixed z-[50] flex items-center gap-3 rounded-full transition-all hover:-translate-y-1 hover:scale-[1.03] group p-[10px] sm:pr-[20px]"
      style={{
        background: "#1E3863",
        boxShadow:
          "0 8px 32px rgba(30, 56, 99, 0.45), inset 0 1px 0 rgba(255,255,255,0.14)",
        border: "1px solid rgba(212, 160, 23, 0.4)",
        bottom: 24,
        right: 24,
      }}
    >
      {/* Lotus disc */}
      <span
        className="flex items-center justify-center rounded-full shrink-0 relative"
        style={{
          width: 40,
          height: 40,
          background: "rgba(255,255,255,0.22)",
        }}
      >
        <img
          src="/static/zantara-lotus.png"
          alt=""
          style={{
            width: 24,
            height: 24,
            objectFit: "contain",
            filter: "brightness(0) invert(1)",
          }}
        />
        {/* Online pulse */}
        <span
          className="absolute rounded-full"
          style={{
            top: -2,
            right: -2,
            width: 14,
            height: 14,
            background: "#22c55e",
            border: "2px solid #1E3863",
            boxShadow: "0 0 10px rgba(34,197,94,0.8)",
          }}
        />
      </span>

      <span className="fab-label hidden sm:flex flex-col items-start leading-none">
        <span
          className="font-bold"
          style={{
            color: "#ffffff",
            fontSize: 13,
            letterSpacing: "0.02em",
          }}
        >
          Ask Zantara
        </span>
        <span
          className="mt-1"
          style={{
            color: "rgba(255,255,255,0.72)",
            fontSize: 10,
            fontWeight: 500,
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          AI · Online 24/7
        </span>
      </span>
    </button>
  );
}
