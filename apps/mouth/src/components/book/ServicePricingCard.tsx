'use client';

import { useState } from 'react';
import { LazyMotion, domAnimation, m, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { usePricingData } from '@/hooks/usePricingData';
import { CONTACTS } from './book-data';

interface ServicePricingCardProps {
  title: string;
  tagline: string;
  serviceKey: string;
  features: string[];
  waMessage: string;
}

export function ServicePricingCard({
  title,
  tagline,
  serviceKey,
  features,
  waMessage,
}: ServicePricingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { price, isLoading } = usePricingData(serviceKey);

  const visible = features.slice(0, 2);
  const hidden = features.slice(2);

  return (
    <LazyMotion features={domAnimation}>
      <div className="border border-white/10 rounded-2xl p-6 bg-white/[0.02] hover:border-[#d4845a]/30 transition-colors">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-[family-name:var(--font-spartan)] text-white font-bold text-lg">
              {title}
            </h3>
            <p className="font-[family-name:var(--font-montserrat)] text-white/50 text-sm">
              {tagline}
            </p>
          </div>
          <div className="text-right">
            {isLoading ? (
              <div className="h-6 w-20 bg-white/10 rounded animate-pulse" />
            ) : (
              <span className="font-[family-name:var(--font-spartan)] text-[#d4845a] font-bold text-xl">
                {price ?? 'Da verificare'}
              </span>
            )}
          </div>
        </div>

        <ul className="space-y-1.5 mb-4">
          {visible.map((f) => (
            <li
              key={f}
              className="flex items-start gap-2 text-sm text-white/70 font-[family-name:var(--font-montserrat)]"
            >
              <span className="text-[#d4845a] mt-0.5 flex-shrink-0">✓</span>
              {f}
            </li>
          ))}
        </ul>

        <AnimatePresence>
          {expanded && hidden.length > 0 && (
            <m.ul
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden space-y-1.5 mb-4"
            >
              {hidden.map((f) => (
                <li
                  key={f}
                  className="flex items-start gap-2 text-sm text-white/70 font-[family-name:var(--font-montserrat)]"
                >
                  <span className="text-[#d4845a] mt-0.5 flex-shrink-0">✓</span>
                  {f}
                </li>
              ))}
            </m.ul>
          )}
        </AnimatePresence>

        {hidden.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-white/40 hover:text-white text-xs mb-4 transition-colors font-[family-name:var(--font-montserrat)]"
          >
            <ChevronDown
              size={14}
              className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
            />
            {expanded ? 'Meno dettagli' : `+${hidden.length} inclusi`}
          </button>
        )}

        <a
          href={`${CONTACTS.whatsappUrl}?text=${encodeURIComponent(waMessage)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center py-2.5 rounded-xl bg-[#25D366] text-white text-sm font-medium font-[family-name:var(--font-montserrat)] hover:bg-[#1fb855] transition-colors"
        >
          Richiedi info su WhatsApp
        </a>
      </div>
    </LazyMotion>
  );
}
