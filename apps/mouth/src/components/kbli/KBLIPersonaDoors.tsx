"use client";

import { Building2, Globe, Search } from "lucide-react";
import { trackFunnelEvent } from "@balizero/core/analytics";
import { getOrCreateSessionId } from "@balizero/core/auth";

type KBLIDoor = "start-business" | "pma-investor" | "find-code";

const DOORS = [
  {
    id: "start-business" as KBLIDoor,
    icon: Building2,
    label: "Starting a Business",
    subtext:
      "Find your KBLI code, check license requirements, understand risk class.",
  },
  {
    id: "pma-investor" as KBLIDoor,
    icon: Globe,
    label: "Foreign Investor (PMA)",
    subtext:
      "See which sectors allow 100% foreign ownership and which are restricted.",
  },
  {
    id: "find-code" as KBLIDoor,
    icon: Search,
    label: "I Have a Specific Code",
    subtext: "Know what you need — go straight to the search.",
  },
] as const;

function handleDoorClick(door: KBLIDoor): void {
  void trackFunnelEvent("persona_door_click", {
    sessionId: getOrCreateSessionId(),
    payload: { door, source: "kbli_hero" },
  });
}

export function KBLIPersonaDoors() {
  return (
    <div className="mt-8 mb-0">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500 mb-4">
        Where do you want to begin?
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {DOORS.map(({ id, icon: Icon, label, subtext }) => (
          <a
            key={id}
            href="#kbli-search"
            onClick={() => handleDoorClick(id)}
            className="block p-4 rounded-xl transition-all duration-200 cursor-pointer no-underline bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.07)] hover:bg-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.12)]"
          >
            <Icon size={18} strokeWidth={1.8} className="text-zinc-400 mb-2" />
            <div className="text-[14px] font-semibold text-zinc-100 mb-1">
              {label}
            </div>
            <div className="text-[12px] leading-relaxed text-zinc-500">
              {subtext}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
