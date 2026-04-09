/**
 * TerminalWelcome — empty-state hero shown when no blocks exist yet.
 *
 * Renders the Zantara logo, title/subtitle and a handful of clickable
 * suggestion cards. Language is selected from the user profile (falls
 * back to English / Indonesian mix as per existing WorkspaceAssistant).
 */

"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

interface TerminalWelcomeProps {
  userName?: string;
  onSelectSuggestion: (text: string) => void;
}

const SUGGESTIONS: Array<{ title: string; prompt: string }> = [
  {
    title: "Clients expiring this month",
    prompt: "Show me my clients whose visas or KITAS expire this month.",
  },
  {
    title: "Latest KBLI regulation updates",
    prompt: "What are the latest KBLI 2025 regulation updates I should know about?",
  },
  {
    title: "Draft a visa extension reminder",
    prompt: "Draft a polite WhatsApp reminder in Indonesian for a client whose visa expires in 10 days.",
  },
  {
    title: "Summarise today's new leads",
    prompt: "Summarise the leads that came in today, grouped by service type.",
  },
];

export function TerminalWelcome({ userName, onSelectSuggestion }: TerminalWelcomeProps) {
  const greeting = userName ? `Ready for input, ${userName}` : "Ready for input";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex flex-col items-center justify-center py-12 md:py-16 text-center"
    >
      <div className="relative w-16 h-16 mb-5">
        <Image
          src="/assets/logo/zantara-lotus.png"
          alt="Zantara"
          fill
          sizes="64px"
          className="object-contain drop-shadow-[0_0_24px_rgba(212,132,90,0.25)]"
          priority
        />
      </div>
      <h1 className="font-mono text-[22px] md:text-[26px] font-semibold tracking-tight text-white/95">
        Zantara Terminal
      </h1>
      <p className="mt-1.5 font-mono text-[12px] uppercase tracking-[1.5px] text-white/40">
        {greeting}
      </p>

      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-2xl">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            type="button"
            onClick={() => onSelectSuggestion(s.prompt)}
            className="group text-left rounded-lg border border-white/10 bg-[var(--bz-elevated)]/60 hover:bg-[var(--bz-elevated)] hover:border-[var(--bz-accent)]/40 transition-all px-3.5 py-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="font-mono text-[12px] text-white/85 font-medium">
                {s.title}
              </div>
              <ArrowRight
                size={12}
                className="text-white/30 group-hover:text-[var(--bz-accent)] group-hover:translate-x-0.5 transition-all flex-shrink-0"
              />
            </div>
            <div className="mt-1 font-mono text-[10.5px] text-white/45 line-clamp-2">
              {s.prompt}
            </div>
          </button>
        ))}
      </div>

      <div className="mt-8 font-mono text-[10px] text-white/30 uppercase tracking-[1.2px]">
        Enter to send · Shift+Enter for newline · ↑↓ for history · Esc to cancel
      </div>
    </motion.div>
  );
}
