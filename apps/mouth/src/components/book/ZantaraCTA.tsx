"use client";

import { m, LazyMotion, domAnimation } from "framer-motion";

interface ZantaraCTAProps {
  onClick: () => void;
}

export function ZantaraCTA({ onClick }: ZantaraCTAProps) {
  return (
    <LazyMotion features={domAnimation}>
      <m.button
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        onClick={onClick}
        className="fixed bottom-20 md:bottom-8 right-6 z-50 flex items-center gap-2 px-5 py-3 rounded-full bg-accent-warm text-white font-[family-name:var(--font-montserrat)] font-semibold text-sm shadow-lg shadow-[#d4845a]/30 hover:bg-[#c4744a] transition-colors"
      >
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-40" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-white" />
        </span>
        Chiedi a Zantara
      </m.button>
    </LazyMotion>
  );
}
