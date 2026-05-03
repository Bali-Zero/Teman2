"use client";

import { useState } from "react";
import Image from "next/image";
import { LazyMotion, domAnimation, m } from "framer-motion";
import {
  TEAM_MEMBERS,
  TRANSLATIONS,
  type TeamMember,
  type Locale,
} from "./book-data";
import { TeamModal } from "./TeamModal";

interface TeamGridProps {
  locale?: Locale;
}

export function TeamGrid({ locale = "en" }: TeamGridProps) {
  const [selected, setSelected] = useState<TeamMember | null>(null);
  const t = TRANSLATIONS[locale];

  return (
    <LazyMotion features={domAnimation}>
      <div className="px-8 md:px-16 py-12">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {TEAM_MEMBERS.map((member, i) => (
            <m.button
              key={member.name}
              onClick={() => setSelected(member)}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: Math.min(i * 0.05, 0.5) }}
              viewport={{ once: true }}
              className="group text-center p-4 rounded-xl border border-white/5 hover:border-accent-warm/40 transition-all bg-white/[0.02] hover:bg-white/[0.05]"
            >
              <div className="w-16 h-16 rounded-full mx-auto mb-3 overflow-hidden flex items-center justify-center ring-2 ring-[#d4845a]/20 group-hover:ring-[#d4845a]/50 transition-all">
                {member.photo ? (
                  <Image
                    src={member.photo}
                    alt={member.name}
                    width={64}
                    height={64}
                    className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-300"
                  />
                ) : (
                  <div
                    className="w-full h-full flex items-center justify-center"
                    style={{
                      background:
                        "linear-gradient(135deg, #1a1410 0%, #2a1f14 50%, #1a1410 100%)",
                    }}
                  >
                    <span className="text-accent-warm font-bold text-base font-[family-name:var(--font-spartan)] select-none">
                      {member.name
                        .split(" ")
                        .map((w) => w[0])
                        .slice(0, 2)
                        .join("")
                        .toUpperCase()}
                    </span>
                  </div>
                )}
              </div>
              <p className="font-[family-name:var(--font-spartan)] text-white text-sm font-semibold leading-tight">
                {member.name}
              </p>
              <p className="font-[family-name:var(--font-montserrat)] text-accent-warm/70 text-[10px] mt-0.5 uppercase tracking-wider">
                {t.teamDepts[member.department]}
              </p>
              <p className="font-[family-name:var(--font-montserrat)] text-white/40 text-xs mt-0.5">
                {member.role}
              </p>
            </m.button>
          ))}
        </div>
      </div>

      <TeamModal
        member={selected}
        open={selected !== null}
        onClose={() => setSelected(null)}
      />
    </LazyMotion>
  );
}
