"use client";

import { useState } from "react";
import { LazyMotion, domAnimation, m, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { usePricingData } from "@/hooks/usePricingData";
import { CONTACTS } from "./book-data";

interface ServicePricingCardProps {
  title: string;
  tagline: string;
  serviceKey: string;
  features: string[];
  waMessage: string;
  badge?: string;
  ctaLabel?: string;
}

export function ServicePricingCard({
  title,
  tagline,
  serviceKey,
  features,
  waMessage,
  badge,
  ctaLabel = "Ask on WhatsApp",
}: ServicePricingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { price, isLoading } = usePricingData(serviceKey);

  const visible = features.slice(0, 3);
  const hidden = features.slice(3);

  return (
    <LazyMotion features={domAnimation}>
      <div className="relative border border-white/10 rounded-2xl p-6 bg-white/[0.025] hover:border-accent-warm/40 hover:bg-white/[0.04] transition-all group">
        {badge && (
          <div className="absolute -top-3 left-4">
            <span className="bg-accent-warm text-white text-[10px] font-semibold font-[family-name:var(--font-montserrat)] tracking-wider uppercase px-3 py-1 rounded-full">
              {badge}
            </span>
          </div>
        )}

        <div className="flex items-start justify-between mb-4 mt-1">
          <div className="flex-1 min-w-0 pr-3">
            <h3 className="font-[family-name:var(--font-spartan)] text-white font-bold text-lg leading-tight">
              {title}
            </h3>
            <p className="font-[family-name:var(--font-montserrat)] text-white/45 text-sm mt-0.5">
              {tagline}
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            {isLoading ? (
              <div className="h-6 w-20 bg-white/10 rounded-lg animate-pulse" />
            ) : (
              <span className="font-[family-name:var(--font-spartan)] text-accent-warm font-bold text-xl">
                {price ?? "—"}
              </span>
            )}
          </div>
        </div>

        <ul className="space-y-2 mb-4">
          {visible.map((f) => (
            <li
              key={f}
              className="flex items-start gap-2.5 text-sm text-white/65 font-[family-name:var(--font-montserrat)]"
            >
              <span className="text-accent-warm mt-0.5 flex-shrink-0 text-xs">
                ✦
              </span>
              {f}
            </li>
          ))}
        </ul>

        <AnimatePresence>
          {expanded && hidden.length > 0 && (
            <m.ul
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden space-y-2 mb-4"
            >
              {hidden.map((f) => (
                <li
                  key={f}
                  className="flex items-start gap-2.5 text-sm text-white/65 font-[family-name:var(--font-montserrat)]"
                >
                  <span className="text-accent-warm mt-0.5 flex-shrink-0 text-xs">
                    ✦
                  </span>
                  {f}
                </li>
              ))}
            </m.ul>
          )}
        </AnimatePresence>

        {hidden.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-white/35 hover:text-white/70 text-xs mb-4 transition-colors font-[family-name:var(--font-montserrat)]"
          >
            <ChevronDown
              size={13}
              className={`transition-transform ${expanded ? "rotate-180" : ""}`}
            />
            {expanded ? "— less" : `+${hidden.length} more included`}
          </button>
        )}

        <a
          href={`${CONTACTS.whatsappUrl}?text=${encodeURIComponent(waMessage)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center py-3 rounded-xl bg-[#25D366]/90 hover:bg-[#25D366] text-white text-sm font-medium font-[family-name:var(--font-montserrat)] transition-colors shadow-[0_0_16px_rgba(37,211,102,0.15)]"
        >
          {ctaLabel}
        </a>
      </div>
    </LazyMotion>
  );
}
