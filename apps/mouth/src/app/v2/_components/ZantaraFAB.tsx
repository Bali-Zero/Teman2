"use client";

// Zantara FAB — premium pill with lotus glyph.
// Fixed bottom-right. Purple gradient, live status dot, "Ask Zantara" label.
export function ZantaraFAB() {
  return (
    <button
      aria-label="Ask Zantara, your AI assistant"
      className="fab-zantara fixed z-[500] flex items-center gap-3 rounded-full transition-all hover:-translate-y-1 hover:scale-[1.03] group"
      style={{
        background: "linear-gradient(135deg, #a78bfa 0%, #6d28d9 100%)",
        boxShadow:
          "0 8px 32px rgba(139, 92, 246, 0.5), inset 0 1px 0 rgba(255,255,255,0.2)",
        border: "1px solid rgba(255,255,255,0.18)",
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
            border: "2px solid #6d28d9",
            boxShadow: "0 0 10px rgba(34,197,94,0.8)",
          }}
        />
      </span>

      <span className="fab-label flex flex-col items-start leading-none">
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
            color: "rgba(255,255,255,0.85)",
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
