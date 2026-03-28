"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  BookOpen,
  Layers,
  Activity,
  Sparkles,
  Scale,
  FileText,
  ChevronRight,
  Loader2,
  History,
  Send,
  Menu,
  X,
  Utensils,
  Building2,
  ShoppingCart,
  Briefcase,
  ArrowRight,
  Copy,
  Columns,
  Trash2,
  Check,
} from "lucide-react";
import { kbliApi, KBLIDetail, KBLISearchResult } from "@/lib/api/kbli.api";
import { toast } from "sonner";
import { useSessionStorage } from "@/lib/hooks/optimized/useLocalStorage";
import KBLIInspector, {
  getPmaBadge,
  getRiskBadge,
  getRiskLevel,
} from "./components/KBLIInspector";
import ThinkingIndicator from "./components/ThinkingIndicator";
import MatchScoreRing from "./components/MatchScoreRing";
import RiskGauge from "./components/RiskGauge";
import ComparisonModal from "./components/ComparisonModal";
import { useTypewriter } from "./hooks/useTypewriter";
import LegacyAlert from "./components/LegacyAlert";
import BlackBookModal from "./components/BlackBookModal";
import { KBLI_CONCORDANCE_2025 } from "./concordance";

// =============================================================================
// CONSTANTS & HELPERS
// =============================================================================

const MOCK_SOURCES = [
  {
    id: "pp28",
    title: "PP 28/2025 Lampiran I",
    type: "Official Regulation",
    date: "Jan 2025",
  },
  {
    id: "bps25",
    title: "Peraturan BPS 7/2025",
    type: "Statistical Standard",
    date: "Feb 2025",
  },
];

const ROTATING_PLACEHOLDERS = [
  "What do I need to open a restaurant in Bali?",
  "Can a foreigner own a consulting company?",
  "What KBLI code do I need for e-commerce?",
  "What licenses are required for a hotel?",
];

const STARTER_CHIPS = [
  {
    label: "Restaurant / Cafe",
    query: "I want to open a restaurant in Bali",
    icon: Utensils,
  },
  {
    label: "Hotel / Villa",
    query: "I want to open a hotel or villa rental",
    icon: Building2,
  },
  {
    label: "E-commerce",
    query: "I want to start an e-commerce business",
    icon: ShoppingCart,
  },
  {
    label: "Consulting",
    query: "I want to open a consulting company",
    icon: Briefcase,
  },
];

const GLOSSARY: Record<string, string> = {
  KBLI: "Indonesia's business classification system — like ATECO codes in Italy or NAICS in the US",
  PMA: "Foreign investment company (Penanaman Modal Asing) — required for foreign-owned businesses",
  PT: "Limited liability company (Perseroan Terbatas) — the standard Indonesian company type",
  OSS: "Online Single Submission — Indonesia's online licensing portal",
  NIB: "Business Identification Number — your first permit, obtained via OSS",
  TERBUKA: "Open — fully available for foreign investment",
  TERBATAS:
    "Restricted — foreign investment allowed with conditions or ownership limits",
  TERTUTUP: "Closed — not available for foreign investment",
};

function getPmaBadgeInline(status: string): {
  label: string;
  color: string;
  bg: string;
  border: string;
} {
  const s = (status || "").toUpperCase();
  if (s === "TERBUKA")
    return {
      label: "Open to Foreigners",
      color: "#34d399",
      bg: "rgba(34,197,94,0.12)",
      border: "rgba(34,197,94,0.25)",
    };
  if (s === "TERBATAS")
    return {
      label: "Restricted",
      color: "#fbbf24",
      bg: "rgba(251,191,36,0.12)",
      border: "rgba(251,191,36,0.25)",
    };
  if (s === "TERTUTUP")
    return {
      label: "Closed to Foreigners",
      color: "#f87171",
      bg: "rgba(239,68,68,0.12)",
      border: "rgba(239,68,68,0.25)",
    };
  return { label: "", color: "", bg: "", border: "" };
}

// =============================================================================
// TOOLTIP COMPONENT (Accessible — 3B)
// =============================================================================

const InfoTooltip = ({
  term,
  explanation,
}: {
  term: string;
  explanation: string;
}) => {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const [above, setAbove] = useState(true);

  const show = () => {
    // Smart positioning: check if there's room above
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setAbove(rect.top > 120);
    }
    setVisible(true);
  };
  const hide = () => setVisible(false);
  const toggle = () => (visible ? hide() : show());

  return (
    <span
      ref={ref}
      className="relative group cursor-help border-b border-dashed border-[#D4B483]/40"
      tabIndex={0}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onClick={toggle}
      role="button"
      aria-expanded={visible}
    >
      {term}
      <AnimatePresence>
        {visible && (
          <motion.span
            initial={{ opacity: 0, y: above ? 4 : -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={`absolute left-1/2 -translate-x-1/2 px-3 py-2 bg-[#1A1D24] border border-white/10 rounded text-xs text-[#CCC] w-52 z-50 text-center shadow-xl pointer-events-none ${
              above ? "bottom-full mb-2" : "top-full mt-2"
            }`}
          >
            {explanation}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
};

function renderWithTooltips(text: string): React.ReactNode {
  const parts: (string | React.ReactElement)[] = [text];

  // All occurrences — no "first only" limit (3B)
  for (const [term, explanation] of Object.entries(GLOSSARY)) {
    const regex = new RegExp(`\\b${term}\\b`, "gi");
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      if (typeof part !== "string") continue;
      const match = regex.exec(part);
      if (match) {
        const before = part.slice(0, match.index);
        const matched = match[0];
        const after = part.slice(match.index + matched.length);
        const replacement: (string | React.ReactElement)[] = [];
        if (before) replacement.push(before);
        replacement.push(
          <InfoTooltip
            key={`tt-${term}-${i}-${match.index}`}
            term={matched}
            explanation={explanation}
          />,
        );
        if (after) replacement.push(after);
        parts.splice(i, 1, ...replacement);
        // Continue scanning rest of string (don't break)
        regex.lastIndex = 0;
      }
    }
  }

  return <>{parts}</>;
}

// =============================================================================
// SUBCOMPONENTS
// =============================================================================

const SourceCard = ({
  source,
}: {
  source: { id: string; title: string; type: string; date: string };
}) => (
  <div className="group flex items-center gap-4 p-4 rounded-lg bg-[#0F1115]/40 border border-white/5 hover:bg-[#151921] hover:border-[#D4B483]/30 transition-all duration-300 cursor-pointer backdrop-blur-sm">
    <div className="p-2.5 rounded bg-[#1A1D24] text-[#888] group-hover:text-[#D4B483] transition-colors border border-white/5">
      <BookOpen size={14} strokeWidth={1.5} />
    </div>
    <div>
      <h4 className="text-sm font-medium text-[#E1E1E3] group-hover:text-white font-serif tracking-wide">
        {source.title}
      </h4>
      <p className="text-[10px] md:text-[10px] uppercase tracking-widest text-[#666] mt-1">
        {source.type}
      </p>
    </div>
  </div>
);

const ChatMessage = ({
  role,
  content,
}: {
  role: "user" | "ai";
  content: React.ReactNode;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 15 }}
    animate={{ opacity: 1, y: 0 }}
    className={`flex gap-4 md:gap-6 ${role === "ai" ? "items-start" : "items-center flex-row-reverse"}`}
  >
    <div
      className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${role === "ai" ? "bg-[#0F1115] border-[#D4B483]/20 text-[#D4B483]" : "bg-[#1A1D24] border-white/10 text-slate-400"}`}
    >
      {role === "ai" ? (
        <Sparkles size={14} />
      ) : (
        <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />
      )}
    </div>
    <div
      className={`max-w-[90%] md:max-w-[85%] ${role === "ai" ? "text-base md:text-lg font-light leading-relaxed" : "text-sm md:text-base font-medium text-white/90"}`}
    >
      {content}
    </div>
  </motion.div>
);

// =============================================================================
// WELCOME COMPONENT
// =============================================================================

const WelcomeOnboarding = ({
  onChipClick,
  onOpenBlackBook,
}: {
  onChipClick: (query: string) => void;
  onOpenBlackBook: () => void;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -20 }}
    className="max-w-2xl mx-auto text-center py-4 md:py-8"
  >
    {/* 2025 Transition Banner */}
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.2 }}
      className="mb-10 p-1 rounded-xl bg-gradient-to-r from-[#D4B483]/40 via-[#D4B483]/10 to-transparent border border-[#D4B483]/30"
    >
      <div className="bg-[#050507] rounded-lg p-4 md:p-6 flex flex-col md:flex-row items-center gap-6 text-left">
        <div className="relative shrink-0">
          <div className="w-16 h-20 bg-[#0A0C10] border border-[#D4B483]/40 rounded shadow-2xl flex items-center justify-center p-2 text-center transform -rotate-2">
            <div className="text-[5px] uppercase tracking-wider text-[#D4B483]">
              KBLI 2025 Dossier
            </div>
          </div>
          <div className="absolute -top-2 -right-2 bg-red-600 text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full animate-pulse shadow-lg">
            RESTRICTED
          </div>
        </div>
        <div className="flex-1">
          <h4 className="text-white font-serif text-lg mb-1">
            Are your company codes still valid?
          </h4>
          <p className="text-[#888] text-xs leading-relaxed mb-4">
            Hundreds of KBLI 2020 codes were revoked on Dec 17. The KBLI 2025
            transition starts now.
          </p>
          <button
            onClick={onOpenBlackBook}
            className="flex items-center gap-2 text-[#D4B483] text-[10px] font-bold uppercase tracking-widest hover:text-white transition-colors group"
          >
            <span>Get the 2025 Black Book</span>
            <ArrowRight
              size={12}
              className="group-hover:translate-x-1 transition-transform"
            />
          </button>
        </div>
      </div>
    </motion.div>

    <h1 className="text-2xl md:text-4xl font-serif text-[#F0F0F0] leading-tight mb-3">
      What business do you want to start in Indonesia?
    </h1>
    <p className="text-sm md:text-base text-[#888] mb-8 md:mb-10">
      Describe your idea in any language and we&apos;ll find the right codes,
      licenses and requirements.
    </p>

    <div className="grid grid-cols-2 gap-3 mb-10 md:mb-12">
      {STARTER_CHIPS.map((chip) => {
        const Icon = chip.icon;
        return (
          <button
            key={chip.label}
            onClick={() => onChipClick(chip.query)}
            className="group flex items-center gap-3 p-4 min-h-[44px] rounded-lg bg-[#0F1115]/60 border border-white/5 hover:border-[#D4B483]/40 hover:bg-[#151921] transition-all duration-200 text-left"
          >
            <div className="p-2 rounded bg-[#1A1D24] text-[#888] group-hover:text-[#D4B483] transition-colors border border-white/5">
              <Icon size={16} />
            </div>
            <span className="text-sm text-[#CCC] group-hover:text-white transition-colors">
              {chip.label}
            </span>
          </button>
        );
      })}
    </div>

    <div className="border-t border-white/5 pt-8 md:pt-10">
      <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-6">
        How it works
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
        {[
          { step: "1", text: "Describe your business idea in any language" },
          {
            step: "2",
            text: "We find the right Indonesian business codes (KBLI)",
          },
          {
            step: "3",
            text: "We show you requirements, restrictions & next steps",
          },
        ].map((item) => (
          <div key={item.step} className="flex items-start gap-3">
            <span className="flex-shrink-0 w-7 h-7 rounded-full bg-[#D4B483]/10 border border-[#D4B483]/20 text-[#D4B483] text-xs flex items-center justify-center font-mono">
              {item.step}
            </span>
            <p className="text-sm text-[#999] leading-relaxed">{item.text}</p>
          </div>
        ))}
      </div>
    </div>
  </motion.div>
);

// =============================================================================
// AI MESSAGE WITH TYPEWRITER (2A + 3C + 1B integrated)
// =============================================================================

type MessageData = {
  role: "user" | "ai";
  content: string;
  detected_kbli?: string[];
  results?: KBLISearchResult[];
  suggested_queries?: string[];
};

const AIMessageContent = ({
  msg,
  isLatest,
  handleInspect,
  handleSendMessage,
  compareMode,
  compareSelection,
  onToggleCompare,
}: {
  msg: MessageData;
  isLatest: boolean;
  handleInspect: (code: string) => void;
  handleSendMessage: (text: string) => void;
  compareMode: boolean;
  compareSelection: string[];
  onToggleCompare: (code: string) => void;
}) => {
  const { displayText, isTyping, skip } = useTypewriter(
    msg.content,
    isLatest ? 15 : 0, // Only typewrite the latest message
  );

  // Show full content if not latest (already typed)
  const textToRender = isLatest ? displayText : msg.content;
  const showExtras = !isTyping || !isLatest;

  // Risk sorting helper for licenses in results
  const sortByRisk = (results: KBLISearchResult[]) => results;

  return (
    <div className="space-y-6 text-[#BBB]">
      {/* Text with typewriter + cursor */}
      <div
        className="whitespace-pre-line"
        onClick={isTyping ? skip : undefined}
      >
        {isTyping ? (
          <>
            {textToRender}
            <span className="inline-block w-[2px] h-[1em] bg-[#D4B483] ml-0.5 animate-pulse" />
          </>
        ) : (
          renderWithTooltips(msg.content)
        )}
      </div>

      {/* Skip button */}
      {isTyping && isLatest && (
        <button
          onClick={skip}
          className="text-[10px] uppercase tracking-widest text-[#555] hover:text-[#D4B483] transition-colors"
        >
          Skip &rarr;
        </button>
      )}

      {/* Result cards — stagger in after typing */}
      <AnimatePresence>
        {showExtras && msg.results && msg.results.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-3 mt-4"
          >
            {sortByRisk(msg.results).map(
              (result: KBLISearchResult, rIdx: number) => {
                const pmaBadgeInline = getPmaBadgeInline(result.pma_status);
                const isSelected = compareSelection.includes(result.code);
                return (
                  <motion.div
                    key={result.code}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: rIdx * 0.08 }}
                  >
                    <button
                      onClick={() => {
                        if (compareMode) {
                          onToggleCompare(result.code);
                        } else {
                          handleInspect(result.code);
                        }
                      }}
                      className={`group w-full text-left p-4 min-h-[44px] rounded-lg bg-[#0F1115]/60 border transition-all duration-200 ${
                        isSelected
                          ? "border-[#D4B483] bg-[#D4B483]/5"
                          : "border-white/5 hover:border-[#D4B483]/40 hover:bg-[#151921]"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          {compareMode && (
                            <div
                              className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                isSelected
                                  ? "bg-[#D4B483] border-[#D4B483]"
                                  : "border-white/20"
                              }`}
                            >
                              {isSelected && (
                                <Check size={10} className="text-[#050507]" />
                              )}
                            </div>
                          )}
                          <span className="font-mono text-sm tracking-wider text-[#D4B483] bg-[#D4B483]/10 px-2.5 py-0.5 rounded border border-[#D4B483]/20">
                            {result.code}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          {pmaBadgeInline.label && (
                            <span
                              className="text-[10px] px-2 py-0.5 rounded-full border"
                              style={{
                                color: pmaBadgeInline.color,
                                backgroundColor: pmaBadgeInline.bg,
                                borderColor: pmaBadgeInline.border,
                              }}
                            >
                              {pmaBadgeInline.label}
                            </span>
                          )}
                          <MatchScoreRing
                            score={Math.round(result.score * 100)}
                          />
                        </div>
                      </div>
                      <h4 className="text-sm font-serif text-[#E1E1E3] group-hover:text-white transition-colors mb-1">
                        {result.title}
                      </h4>
                      <p className="text-xs text-[#777] leading-relaxed line-clamp-2">
                        {result.description}
                      </p>
                      {!compareMode && (
                        <div className="flex items-center gap-1 mt-2 text-[10px] text-[#555] group-hover:text-[#D4B483] transition-colors">
                          <span>View details</span>
                          <ChevronRight size={10} />
                        </div>
                      )}
                    </button>
                  </motion.div>
                );
              },
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Detected KBLI codes (when no full results) */}
      <AnimatePresence>
        {showExtras &&
          (!msg.results || msg.results.length === 0) &&
          msg.detected_kbli &&
          msg.detected_kbli.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-wrap gap-2 mt-4"
            >
              {msg.detected_kbli.map((code: string) => (
                <button
                  key={code}
                  onClick={() => handleInspect(code)}
                  className="group flex items-center gap-2 px-3 py-2 min-h-[44px] rounded bg-[#151921] border border-white/10 hover:border-[#D4B483] transition-all"
                >
                  <span className="font-mono text-[#D4B483] text-xs">
                    KBLI {code}
                  </span>
                  <ChevronRight
                    size={12}
                    className="text-[#555] group-hover:text-[#D4B483]"
                  />
                </button>
              ))}
            </motion.div>
          )}
      </AnimatePresence>

      {/* Suggested follow-up queries */}
      <AnimatePresence>
        {showExtras &&
          msg.suggested_queries &&
          msg.suggested_queries.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-white/5"
            >
              {msg.suggested_queries.map((sq: string, sqIdx: number) => (
                <button
                  key={sqIdx}
                  onClick={() => handleSendMessage(sq)}
                  className="group flex items-center gap-1.5 px-3 py-2 min-h-[44px] rounded-full text-xs text-[#D4B483] bg-[#D4B483]/5 border border-[#D4B483]/20 hover:bg-[#D4B483]/10 hover:border-[#D4B483]/40 transition-all"
                >
                  <ArrowRight
                    size={10}
                    className="opacity-60 group-hover:opacity-100"
                  />
                  <span>{sq}</span>
                </button>
              ))}
            </motion.div>
          )}
      </AnimatePresence>
    </div>
  );
};

// =============================================================================
// INSPECTOR WITH CHOREOGRAPHY (1C + 2B + 2C + 3C)
// =============================================================================

const InspectorChoreographed = ({
  data,
  isLoading,
  onClose,
  onInspect,
}: {
  data: KBLIDetail | null;
  isLoading: boolean;
  onClose?: () => void;
  onInspect?: (code: string) => void;
}) => {
  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#D4B483]">
        <Loader2 size={32} className="animate-spin mb-4" />
        <p className="text-xs uppercase tracking-widest opacity-50">
          Loading details...
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#444] px-8 text-center">
        <Search size={48} className="mb-6 opacity-20 stroke-1" />
        <p className="text-sm font-medium text-[#666] mb-2">
          Click on any result to see full details
        </p>
        <p className="text-xs text-[#444]">
          Licenses, restrictions, risk level and related business codes will
          appear here
        </p>
      </div>
    );
  }

  const pmaBadge = getPmaBadge(data.pma_status);
  const riskLevel = getRiskLevel(data.risk_profile);

  // Copy/Export (2C)
  const handleCopy = () => {
    const licList = data.licenses.map((l) => l.type).join(", ") || "None";
    const text = `KBLI ${data.code} — ${data.title} | PMA: ${pmaBadge.label} | Risk: ${getRiskBadge(data.risk_profile).label} | Licenses: ${licList} | Sector: ${data.sector}`;
    navigator.clipboard.writeText(text).then(() => {
      toast.success("Copied to clipboard");
    });
  };

  const handleShare = () => {
    const url = `${window.location.origin}${window.location.pathname}?inspect=${data.code}`;
    navigator.clipboard.writeText(url).then(() => {
      toast.success("Link copied");
    });
  };

  // Sort licenses by risk (3C) — highest risk first
  const riskOrder: Record<string, number> = {
    tinggi: 3,
    menengah: 2,
    rendah: 1,
  };
  const sortedLicenses = [...data.licenses].sort((a, b) => {
    const aRisk =
      Object.entries(riskOrder).find(([k]) =>
        a.risk_level.toLowerCase().includes(k),
      )?.[1] || 0;
    const bRisk =
      Object.entries(riskOrder).find(([k]) =>
        b.risk_level.toLowerCase().includes(k),
      )?.[1] || 0;
    return bRisk - aRisk;
  });

  // Stagger variants
  const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } },
  };
  const item = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="h-full flex flex-col"
    >
      {/* Mobile close button */}
      {onClose && (
        <button
          onClick={onClose}
          className="md:hidden absolute top-4 right-4 z-10 p-2 rounded-full bg-[#1A1D24] text-[#888]"
        >
          <X size={18} />
        </button>
      )}
      {onClose && (
        <div className="md:hidden flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>
      )}

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="p-6 md:p-8 border-b border-white/5 bg-gradient-to-b from-[#0F1115] to-[#050507]"
      >
        {/* Header with copy/share buttons (2C) */}
        <div className="flex items-center justify-between mb-4">
          <motion.div
            variants={item}
            className="flex items-center gap-2 flex-wrap"
          >
            <motion.span
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 200, damping: 15 }}
              className="px-3 py-1 rounded text-xs font-mono tracking-wider bg-[#D4B483]/10 text-[#D4B483] border border-[#D4B483]/20"
            >
              KBLI {data.code}
            </motion.span>
            <motion.span
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
              className={pmaBadge.className}
            >
              {pmaBadge.label}
            </motion.span>
          </motion.div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopy}
              className="p-2 rounded hover:bg-white/5 text-[#666] hover:text-[#D4B483] transition-colors"
              title="Copy details"
            >
              <Copy size={14} />
            </button>
          </div>
        </div>
        <motion.h2
          variants={item}
          className="text-2xl md:text-3xl font-serif text-[#F0F0F0] leading-tight mb-6"
        >
          {data.title}
        </motion.h2>

        {/* Risk Gauge (2B) */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="flex items-center justify-between"
        >
          <RiskGauge level={riskLevel} />
          <span className="text-[10px] uppercase tracking-widest text-[#D4B483]">
            {data.licensing_status}
          </span>
        </motion.div>
      </motion.div>

      <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-10 custom-scrollbar">
        {/* Description (1C stagger) */}
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <FileText size={12} /> Official Description
          </h3>
          <p className="text-sm text-[#CCC] leading-loose font-light border-l border-[#D4B483]/30 pl-5 italic">
            &ldquo;{data.description}&rdquo;
          </p>
        </motion.section>

        {/* Licenses with visual hierarchy (3C) */}
        {sortedLicenses.length > 0 && (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
              <Scale size={12} /> Required Licenses
            </h3>
            <div className="relative">
              {/* Vertical connecting line */}
              {sortedLicenses.length > 1 && (
                <div className="absolute left-[11px] top-6 bottom-6 w-px bg-white/5" />
              )}
              <div className="space-y-4">
                {sortedLicenses.map((lic, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.4 + idx * 0.08 }}
                    className="flex gap-3"
                  >
                    {/* Step number */}
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#0F1115] border border-white/10 text-[10px] text-[#666] flex items-center justify-center font-mono z-10">
                      {idx + 1}
                    </div>
                    <div
                      className={`group flex-1 p-4 bg-[#0A0C10] rounded hover:border-[#D4B483]/20 transition-all ${
                        idx === 0
                          ? "border-l-[3px] border border-[#D4B483]/30 border-l-[#D4B483]"
                          : "border-l-2 border border-white/5 border-l-white/10"
                      }`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <span
                          className={`font-medium text-[#E1E1E3] group-hover:text-white transition-colors ${idx === 0 ? "text-sm" : "text-xs"}`}
                        >
                          {lic.type}
                        </span>
                        <span className="text-[10px] uppercase px-2 py-1 rounded-full bg-[#151921] text-[#888] border border-white/5">
                          {lic.sla}
                        </span>
                      </div>
                      <div className="flex flex-col gap-1 text-xs text-[#666]">
                        <span>
                          Business Size:{" "}
                          <span className="text-[#999]">
                            {lic.scale.join(", ")}
                          </span>
                        </span>
                        <span>
                          Risk Level:{" "}
                          <span className="text-[#999]">{lic.risk_level}</span>
                        </span>
                      </div>
                      {lic.requirements.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-white/5">
                          <p className="text-[10px] text-[#444] uppercase mb-2">
                            What you need to do:
                          </p>
                          <ul className="space-y-1">
                            {lic.requirements.slice(0, 3).map((req, ridx) => (
                              <li
                                key={ridx}
                                className="text-[11px] text-[#888] leading-tight"
                              >
                                &bull; {req}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.section>
        )}

        {/* Related codes */}
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <Activity size={12} /> Related Business Codes
          </h3>
          <div className="flex flex-wrap gap-2">
            <div className="px-4 py-2 rounded-full bg-[#0F1115] text-xs text-[#D4B483] border border-[#D4B483]/20">
              Sector: {data.sector}
            </div>
            {data.related_codes.map((rel, idx) => (
              <button
                key={idx}
                onClick={() => onInspect?.(rel)}
                className="px-4 py-2 rounded-full bg-[#0F1115] text-xs text-[#888] border border-white/5 hover:border-[#D4B483]/30 hover:text-[#D4B483] cursor-pointer transition-all"
              >
                {rel}
              </button>
            ))}
          </div>
        </motion.section>
      </div>
    </motion.div>
  );
};

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function KBLIExplorerPage() {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KBLISearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [activeKBLI, setActiveKBLI] = useState<KBLIDetail | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  // Session persistence (3A) — messages survive refresh
  const [messages, setMessages, clearMessages] = useSessionStorage<
    MessageData[]
  >("kbli-messages", []);
  const [isChatting, setIsChatting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [placeholderVisible, setPlaceholderVisible] = useState(true);
  // Comparison mode (Phase 4)
  const [compareMode, setCompareMode] = useState(false);
  const [compareSelection, setCompareSelection] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);

  // Black Book Funnel (2025 Transition)
  const [isBlackBookOpen, setIsBlackBookOpen] = useState(false);
  const [detectedLegacyCode, setDetectedLegacyCode] = useState<
    string | undefined
  >();

  const chatEndRef = useRef<HTMLDivElement>(null);

  const isWelcome = messages.length === 0;

  // Deep-link: ?inspect={code} (2C)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const inspectCode = params.get("inspect");
    if (inspectCode) {
      handleInspect(inspectCode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close mobile overlays on Escape
  useEffect(() => {
    const openOverlay = sidebarOpen || inspectorOpen;
    if (!openOverlay) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (inspectorOpen) setInspectorOpen(false);
        else if (sidebarOpen) setSidebarOpen(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [sidebarOpen, inspectorOpen]);

  // Rotating placeholder
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderVisible(false);
      setTimeout(() => {
        setPlaceholderIdx((prev) => (prev + 1) % ROTATING_PLACEHOLDERS.length);
        setPlaceholderVisible(true);
      }, 300);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  // Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleInspect = useCallback(async (code: string) => {
    setIsInspecting(true);
    setInspectorOpen(true);

    // Check if it's a legacy code to trigger the funnel later
    if (KBLI_CONCORDANCE_2025[code]) {
      setDetectedLegacyCode(code);
    }

    try {
      const detail = await kbliApi.inspect(code);
      setActiveKBLI(detail);
    } catch {
      toast.error(`Failed to load KBLI ${code}`);
    } finally {
      setIsInspecting(false);
    }
  }, []);

  const handleSendMessage = useCallback(
    async (messageText?: string, e?: React.FormEvent) => {
      if (e) e.preventDefault();
      const text = messageText || query;
      if (!text || isChatting) return;

      setQuery("");
      setSearchResults([]);
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setIsChatting(true);

      try {
        const response = await kbliApi.chat(text);
        setMessages((prev) => [
          ...prev,
          {
            role: "ai",
            content: response.answer,
            detected_kbli: response.detected_kbli,
            results: response.results,
            suggested_queries: response.suggested_queries || [],
          },
        ]);

        if (response.results && response.results.length > 0) {
          handleInspect(response.results[0].code);

          // Trigger legacy detection from results
          const firstLegacy = response.results.find(
            (r) => KBLI_CONCORDANCE_2025[r.code],
          );
          if (firstLegacy) setDetectedLegacyCode(firstLegacy.code);
        } else if (response.detected_kbli.length > 0) {
          handleInspect(response.detected_kbli[0]);

          // Trigger legacy detection from detected codes
          const firstLegacy = response.detected_kbli.find(
            (c) => KBLI_CONCORDANCE_2025[c],
          );
          if (firstLegacy) setDetectedLegacyCode(firstLegacy);
        }
      } catch {
        toast.error("Failed to process request");
      } finally {
        setIsChatting(false);
      }
    },
    [query, isChatting, handleInspect, setMessages],
  );

  const handleChipClick = useCallback(
    (chipQuery: string) => {
      handleSendMessage(chipQuery);
    },
    [handleSendMessage],
  );

  const handleClearConversation = useCallback(() => {
    clearMessages();
    setActiveKBLI(null);
    setCompareMode(false);
    setCompareSelection([]);
  }, [clearMessages]);

  const toggleCompareCode = useCallback((code: string) => {
    setCompareSelection((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  }, []);

  const currentPlaceholder = ROTATING_PLACEHOLDERS[placeholderIdx];

  return (
    <div className="flex h-full font-sans overflow-x-hidden">
      {/* MOBILE SIDEBAR BACKDROP */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-30 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* LEFT PANEL: Sources & Context */}
      <aside
        className={`
          fixed md:relative z-40 md:z-20
          w-[280px] md:w-[320px] h-full
          bg-[#080A0E] border-r border-white/5 flex flex-col
          shadow-[5px_0_30px_rgba(0,0,0,0.3)]
          transition-transform duration-300
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
          hidden md:flex
          ${sidebarOpen ? "!flex" : ""}
        `}
      >
        <div className="p-6 md:p-8 pb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 relative flex-shrink-0">
              <img
                src="/images/logo-zantara.png"
                alt="Zantara Logo"
                className="w-full h-full object-contain filter drop-shadow-[0_0_8px_rgba(212,180,131,0.2)]"
              />
            </div>
            <div className="flex flex-col">
              <span className="font-serif text-lg tracking-wide text-[#E1E1E3]">
                Zantara
              </span>
              <span className="text-[9px] uppercase tracking-[0.3em] text-[#444] -mt-1">
                Business Code Guide
              </span>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden p-2 rounded text-[#888] hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-8">
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#333] mb-4 px-2">
              2025 Transition
            </h3>
            <button
              onClick={() => setIsBlackBookOpen(true)}
              className="w-full group p-4 rounded-lg bg-gradient-to-br from-[#D4B483]/20 to-[#0A0C10] border border-[#D4B483]/30 hover:border-[#D4B483] transition-all text-left"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded bg-[#0F1115] text-[#D4B483] border border-[#D4B483]/20">
                  <FileText size={14} />
                </div>
                <span className="text-xs font-bold text-white tracking-wide">
                  KBLI 2025 BLACK BOOK
                </span>
              </div>
              <p className="text-[10px] text-[#888] leading-tight group-hover:text-[#CCC] transition-colors">
                Download the dossier on revoked codes and the 2025 compliance
                moats.
              </p>
            </button>
          </section>

          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#333] mb-4 px-2">
              Official Sources
            </h3>
            <div className="space-y-3">
              {MOCK_SOURCES.map((source) => (
                <SourceCard key={source.id} source={source} />
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#333] mb-4 px-2">
              Quick Access
            </h3>
            <div className="space-y-1">
              <button className="w-full group flex items-center justify-between px-4 py-3 min-h-[44px] rounded text-sm text-[#666] hover:bg-[#151921] hover:text-[#CCC] transition-all border border-transparent hover:border-white/5 text-left">
                <span className="flex items-center gap-2">
                  <History size={14} /> Recent Searches
                </span>
                <ChevronRight
                  size={12}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </button>
              <button className="w-full group flex items-center justify-between px-4 py-3 min-h-[44px] rounded text-sm text-[#666] hover:bg-[#151921] hover:text-[#CCC] transition-all border border-transparent hover:border-white/5 text-left">
                <span className="flex items-center gap-2">
                  <Layers size={14} /> Browse by Sector
                </span>
                <ChevronRight
                  size={12}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </button>
            </div>
          </section>
        </div>

        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3 p-2 rounded hover:bg-[#151921] cursor-pointer transition-colors">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#D4B483] to-[#8C7350] flex items-center justify-center text-[#050507] text-[10px] font-bold">
              AZ
            </div>
            <div>
              <div className="text-xs font-medium text-[#E1E1E3]">
                Business Assistant
              </div>
              <div className="text-[10px] text-[#555] uppercase tracking-wider">
                Ready to help
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* CENTER PANEL: The Workspace */}
      <main className="flex-1 flex flex-col bg-transparent relative z-10 min-w-0">
        {/* Header/Search */}
        <div className="p-4 md:p-8 pt-6 md:pt-10 relative">
          <div className="relative max-w-3xl mx-auto">
            {/* Mobile hamburger */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden absolute -left-1 top-1/2 -translate-y-1/2 p-2 rounded text-[#888] hover:text-white z-10"
            >
              <Menu size={20} />
            </button>

            <form onSubmit={(e) => handleSendMessage(undefined, e)}>
              <input
                type="text"
                placeholder=""
                className="w-full bg-[#0F1115]/80 backdrop-blur-md text-[#E1E1E3] placeholder-[#444] rounded-lg py-4 md:py-5 pl-12 md:pl-14 pr-28 border border-white/5 focus:border-[#D4B483]/30 focus:ring-1 focus:ring-[#D4B483]/30 focus:outline-none transition-all shadow-2xl font-light tracking-wide min-h-[44px]"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {/* Rotating placeholder overlay */}
              {!query && (
                <span
                  className="absolute left-12 md:left-14 top-1/2 -translate-y-1/2 text-[#444] font-light tracking-wide pointer-events-none text-sm md:text-base transition-opacity duration-300"
                  style={{ opacity: placeholderVisible ? 1 : 0 }}
                >
                  {currentPlaceholder}
                </span>
              )}
              <Search
                className="absolute left-4 md:left-5 top-1/2 -translate-y-1/2 text-[#444]"
                size={18}
                strokeWidth={1.5}
              />
              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
                {/* Compare toggle (Phase 4) */}
                {!isWelcome && (
                  <button
                    type="button"
                    onClick={() => {
                      setCompareMode((prev) => !prev);
                      if (compareMode) setCompareSelection([]);
                    }}
                    className={`p-2 rounded-md transition-colors min-h-[36px] min-w-[36px] flex items-center justify-center ${
                      compareMode
                        ? "bg-[#D4B483]/15 text-[#D4B483]"
                        : "hover:bg-[#1A1D24] text-[#555] hover:text-[#888]"
                    }`}
                    title={compareMode ? "Exit compare mode" : "Compare codes"}
                  >
                    <Columns size={16} />
                  </button>
                )}
                {/* Clear conversation (3A) */}
                {!isWelcome && (
                  <button
                    type="button"
                    onClick={handleClearConversation}
                    className="p-2 rounded-md hover:bg-[#1A1D24] text-[#555] hover:text-[#888] transition-colors min-h-[36px] min-w-[36px] flex items-center justify-center"
                    title="Clear conversation"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
                {/* Send */}
                <button
                  type="submit"
                  className="p-2 rounded-md hover:bg-[#1A1D24] text-[#D4B483] transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                  disabled={isChatting}
                >
                  {isChatting ? (
                    <Loader2 size={18} className="animate-spin" />
                  ) : (
                    <Send size={18} />
                  )}
                </button>
              </div>
            </form>

            {/* Floating Search Results */}
            <AnimatePresence>
              {searchResults.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="absolute top-full mt-2 left-0 w-full bg-[#0F1115] border border-white/10 rounded-lg shadow-2xl z-50 overflow-hidden"
                >
                  <div className="p-2 border-b border-white/5 text-[10px] uppercase tracking-widest text-[#555] px-4">
                    Related Results
                  </div>
                  <div className="max-h-60 overflow-y-auto custom-scrollbar">
                    {searchResults.map((res, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          handleInspect(res.code);
                          setSearchResults([]);
                        }}
                        className="w-full flex items-center gap-4 px-4 py-3 min-h-[44px] hover:bg-[#1A1D24] border-b border-white/5 last:border-0 text-left transition-colors"
                      >
                        <span className="font-mono text-[#D4B483] text-xs w-12">
                          {res.code}
                        </span>
                        <span className="text-sm text-[#E1E1E3] truncate flex-1">
                          {res.title}
                        </span>
                        <ChevronRight size={12} className="text-[#333]" />
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Conversation Area */}
        <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
          <div className="max-w-3xl mx-auto space-y-8 md:space-y-12 py-4">
            <AnimatePresence mode="wait">
              {isWelcome ? (
                <WelcomeOnboarding
                  key="welcome"
                  onChipClick={handleChipClick}
                  onOpenBlackBook={() => setIsBlackBookOpen(true)}
                />
              ) : (
                <motion.div
                  key="chat"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="space-y-8 md:space-y-12"
                >
                  {/* Show Legacy Alert if a critical code is detected in current session */}
                  {detectedLegacyCode && (
                    <LegacyAlert
                      code={detectedLegacyCode}
                      onOpenBlackBook={() => setIsBlackBookOpen(true)}
                    />
                  )}

                  {messages.map((msg, idx) => (
                    <div key={idx} className="space-y-4">
                      <ChatMessage
                        role={msg.role}
                        content={
                          msg.role === "user" ? (
                            <p className="text-lg md:text-xl font-serif text-[#F0F0F0] leading-normal">
                              {msg.content}
                            </p>
                          ) : (
                            <AIMessageContent
                              msg={msg}
                              isLatest={idx === messages.length - 1}
                              handleInspect={handleInspect}
                              handleSendMessage={(text) =>
                                handleSendMessage(text)
                              }
                              compareMode={compareMode}
                              compareSelection={compareSelection}
                              onToggleCompare={toggleCompareCode}
                            />
                          )
                        }
                      />
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Thinking Indicator (1A) — replaces animate-pulse skeleton */}
            {isChatting && <ThinkingIndicator />}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Compare sticky bottom bar (Phase 4) */}
        <AnimatePresence>
          {compareMode && compareSelection.length >= 2 && (
            <motion.div
              initial={{ y: 60, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 60, opacity: 0 }}
              className="sticky bottom-0 left-0 right-0 p-4 bg-[#0A0C10]/95 backdrop-blur-lg border-t border-[#D4B483]/20 z-30"
            >
              <div className="max-w-3xl mx-auto flex items-center justify-between">
                <span className="text-sm text-[#CCC]">
                  <span className="text-[#D4B483] font-mono">
                    {compareSelection.length}
                  </span>{" "}
                  codes selected
                </span>
                <button
                  onClick={() => setCompareOpen(true)}
                  className="px-4 py-2 rounded-lg bg-[#D4B483] text-[#050507] text-sm font-medium hover:bg-[#C4A473] transition-colors"
                >
                  Compare {compareSelection.length} codes &rarr;
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* RIGHT PANEL: The Inspector — desktop fixed, mobile bottom sheet */}
      <aside className="hidden xl:block w-[420px] bg-[#0A0C10]/90 backdrop-blur-2xl border-l border-white/5 relative z-20 shadow-[-5px_0_30px_rgba(0,0,0,0.2)]">
        <InspectorChoreographed
          data={activeKBLI}
          isLoading={isInspecting}
          onInspect={handleInspect}
        />
      </aside>

      {/* Mobile/Tablet bottom sheet inspector */}
      <AnimatePresence>
        {inspectorOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="xl:hidden fixed inset-0 bg-black/50 z-40"
              onClick={() => setInspectorOpen(false)}
            />
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="xl:hidden fixed bottom-0 left-0 right-0 h-[70vh] bg-[#0A0C10] border-t border-white/10 rounded-t-2xl z-50 overflow-hidden"
            >
              <InspectorChoreographed
                data={activeKBLI}
                isLoading={isInspecting}
                onClose={() => setInspectorOpen(false)}
                onInspect={handleInspect}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Comparison Modal (Phase 4) */}
      <ComparisonModal
        codes={compareSelection}
        open={compareOpen}
        onOpenChange={setCompareOpen}
      />

      {/* Black Book Lead Funnel */}
      <BlackBookModal
        isOpen={isBlackBookOpen}
        onClose={() => setIsBlackBookOpen(false)}
        detectedCode={detectedLegacyCode}
      />
    </div>
  );
}
