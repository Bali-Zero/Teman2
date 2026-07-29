import React from "react";
import Image from "next/image";
import { ExternalLink, Sparkles } from "lucide-react";
import { BZLogo } from "@balizero/core/components/BZLogo";

const ZANTARA_URL = "https://zantara.balizero.com/chat";

export function ZantaraPortalCard() {
  return (
    <a
      href={ZANTARA_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="bz-product-panel bz-product-panel--interactive group relative block overflow-hidden transition-all duration-500"
    >
      {/* Animated liquid background gradient */}
      <div
        className="absolute inset-0 opacity-40 transition-opacity duration-700 group-hover:opacity-60"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 20% 30%, color-mix(in srgb, var(--bz-copper) 12%, transparent) 0%, transparent 60%), radial-gradient(ellipse 60% 80% at 80% 70%, color-mix(in srgb, var(--state-info) 8%, transparent) 0%, transparent 60%)",
          animation: "liquidShift 8s ease-in-out infinite alternate",
        }}
      />

      {/* Satin sheen on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background:
            "linear-gradient(135deg, color-mix(in srgb, var(--bz-text-1) 5%, transparent) 0%, transparent 50%, color-mix(in srgb, var(--bz-text-1) 2%, transparent) 100%)",
        }}
      />

      {/* Content */}
      <div className="relative flex items-center gap-4 px-5 py-4">
        {/* Logos cluster */}
        <div className="relative flex-shrink-0 w-[52px] h-[52px]">
          {/* BZ logo — background */}
          <div
            className="absolute inset-0 rounded-xl overflow-hidden flex items-center justify-center"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--bz-border)",
            }}
          >
            <BZLogo variant="mark" size={36} />
          </div>
          {/* Lotus — overlaid bottom-right with glow pulse */}
          <div
            className="absolute -bottom-1.5 -right-1.5 w-[26px] h-[26px] rounded-full flex items-center justify-center"
            style={{
              background: "var(--bz-elevated)",
              border:
                "1px solid color-mix(in srgb, var(--state-info) 25%, transparent)",
              animation: "lotusPulse 3s ease-in-out infinite",
            }}
          >
            <Image
              src="/static/zantara-lotus-v2.png"
              alt="Zantara"
              width={22}
              height={22}
              className="object-contain"
            />
          </div>
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span
              className="text-[13px] font-semibold tracking-tight"
              style={{ color: "var(--bz-text-1)" }}
            >
              Zantara AI
            </span>
            <Sparkles
              size={10}
              className="flex-shrink-0"
              style={{ color: "var(--bz-accent)", opacity: 0.8 }}
            />
          </div>
          <p
            className="text-[11px] leading-snug truncate"
            style={{ color: "var(--bz-text-3)" }}
          >
            Intelligence &middot; Bali Zero
          </p>
        </div>

        {/* Arrow */}
        <ExternalLink
          size={13}
          className="flex-shrink-0 opacity-30 group-hover:opacity-70 transition-opacity duration-300"
          style={{ color: "var(--bz-text-2)" }}
        />
      </div>
    </a>
  );
}
