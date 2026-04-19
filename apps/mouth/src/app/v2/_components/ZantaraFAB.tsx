"use client";

import { BZLogo } from "@balizero/core/components/BZLogo";

// Inline FAB markup. Token-driven (--fab-bg-gradient, --fab-fg).
// Promoted to a shared @balizero/core component in Phase 4 (design §R9).
export function ZantaraFAB() {
  return (
    <button
      title="Chat with Zantara"
      className="fixed bottom-7 right-7 z-50 w-14 h-14 rounded-2xl flex items-center justify-center transition-transform hover:-translate-y-1 hover:scale-105"
      style={{
        background: "var(--fab-bg-gradient)",
        boxShadow: "0 4px 24px color-mix(in srgb, var(--accent-zantara) 40%, transparent)",
      }}
    >
      <BZLogo variant="zantara" size={28} />
      <span
        className="absolute -top-1 -right-1 w-3 h-3 rounded-full"
        style={{
          background: "var(--state-success)",
          boxShadow: "0 0 10px var(--state-success)",
        }}
      />
    </button>
  );
}
