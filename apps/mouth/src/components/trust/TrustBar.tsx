import React from "react";
import { Star, Users, ShieldCheck, Clock } from "lucide-react";

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
      {/* Desktop inline variant — single minimal row */}
      <div className="hidden md:flex items-center gap-6 flex-wrap text-[9px] leading-tight text-[#475372]">
        <span className="inline-flex items-center gap-1">
          <Star size={10} className="fill-current text-[#fbbf24]" />
          <span>4.9 ★ · 627 Reviews</span>
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
        <span className="opacity-40">·</span>
        <span className="inline-flex items-center gap-1">
          <Clock size={10} />
          <span>Avg reply: 2 min</span>
        </span>
      </div>

      {/* Mobile sticky variant — fixed bottom bar */}
      <div className="flex md:hidden fixed bottom-0 left-0 right-0 z-40 bg-[#12161f]/95 backdrop-blur-md border-t border-white/10 shadow-lg py-2 px-4 items-center justify-center gap-4 flex-wrap text-[9px] leading-tight text-white/70">
        <span className="inline-flex items-center gap-1">
          <Star size={10} className="fill-current text-[#fbbf24]" />
          <span>4.9 ★ · 627 Reviews</span>
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
        <span className="opacity-40">·</span>
        <span className="inline-flex items-center gap-1">
          <Clock size={10} />
          <span>Avg reply: 2 min</span>
        </span>
      </div>
    </>
  );
}
