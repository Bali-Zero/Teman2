import React from "react";
import { Star, Users, ShieldCheck } from "lucide-react";
import { ratingBadge, reviewsShort } from "@/lib/trust-figures";

/**
 * TrustBar — CRO quick-win trust proof banner.
 *
 * Renders in two variants:
 * 1. Desktop inline: minimal 9px text row co-located below the hero CTA.
 * 2. Mobile sticky: fixed bottom bar on mobile viewports for constant visibility during scroll.
 */
export function TrustBar(): React.ReactElement {
  return (
    <>
      {/* Desktop inline variant — P1/P2: raised from 9px to 12px.
          Text is inside the hero's dark scrim overlay; text-shadow adds
          safety on lighter photo patches (was ~1.5:1 without it). */}
      <div
        className="hidden md:flex items-center gap-6 flex-wrap text-[12px] leading-tight"
        style={{
          color: "rgba(255,255,255,0.82)",
          textShadow: "0 1px 8px rgba(0,0,0,0.7)",
        }}
      >
        <span className="inline-flex items-center gap-1">
          <Star size={10} className="fill-current text-[#fbbf24]" />
          <span>{`${ratingBadge()} · ${reviewsShort()}`}</span>
        </span>
        <span className="opacity-40">·</span>
        <span className="inline-flex items-center gap-1">
          <Users size={10} />
          <span>5,000+ Clients</span>
        </span>
        <span className="opacity-40">·</span>
        <span className="inline-flex items-center gap-1">
          <ShieldCheck size={10} />
          <span>Licensed Notary & Tax Agent</span>
        </span>
      </div>

      {/* Mobile sticky variant — fixed bottom bar */}
      <div className="flex md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#12161f]/95 backdrop-blur-md border-t border-white/10 shadow-lg py-2 px-4 items-center justify-center gap-4 flex-wrap text-[9px] leading-tight text-white/70">
        <span className="inline-flex items-center gap-1">
          <Star size={10} className="fill-current text-[#fbbf24]" />
          <span>{`${ratingBadge()} · ${reviewsShort()}`}</span>
        </span>
        <span className="opacity-40">·</span>
        <span className="inline-flex items-center gap-1">
          <Users size={10} />
          <span>5,000+ Clients</span>
        </span>
        <span className="opacity-40">·</span>
        <span className="inline-flex items-center gap-1">
          <ShieldCheck size={10} />
          <span>Licensed Notary & Tax Agent</span>
        </span>
      </div>
    </>
  );
}
