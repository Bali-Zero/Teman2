'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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
} from 'lucide-react';
import { kbliApi, KBLIDetail, KBLISearchResult } from '@/lib/api/kbli.api';
import { toast } from 'sonner';

// =============================================================================
// CONSTANTS & HELPERS
// =============================================================================

const MOCK_SOURCES = [
  { id: 'pp28', title: 'PP 28/2025 Lampiran I', type: 'Official Regulation', date: 'Jan 2025' },
  { id: 'bps25', title: 'Peraturan BPS 7/2025', type: 'Statistical Standard', date: 'Feb 2025' },
];

const ROTATING_PLACEHOLDERS = [
  'What do I need to open a restaurant in Bali?',
  'Can a foreigner own a consulting company?',
  'What KBLI code do I need for e-commerce?',
  'What licenses are required for a hotel?',
];

const STARTER_CHIPS = [
  { label: 'Restaurant / Cafe', query: 'I want to open a restaurant in Bali', icon: Utensils },
  { label: 'Hotel / Villa', query: 'I want to open a hotel or villa rental', icon: Building2 },
  { label: 'E-commerce', query: 'I want to start an e-commerce business', icon: ShoppingCart },
  { label: 'Consulting', query: 'I want to open a consulting company', icon: Briefcase },
];

const GLOSSARY: Record<string, string> = {
  KBLI: "Indonesia's business classification system — like ATECO codes in Italy or NAICS in the US",
  PMA: 'Foreign investment company (Penanaman Modal Asing) — required for foreign-owned businesses',
  PT: 'Limited liability company (Perseroan Terbatas) — the standard Indonesian company type',
  OSS: "Online Single Submission — Indonesia's online licensing portal",
  NIB: 'Business Identification Number — your first permit, obtained via OSS',
  TERBUKA: 'Open — fully available for foreign investment',
  TERBATAS: 'Restricted — foreign investment allowed with conditions or ownership limits',
  TERTUTUP: 'Closed — not available for foreign investment',
};

function getPmaBadge(status: string): { label: string; className: string } {
  const s = (status || '').toUpperCase();
  if (s === 'TERBUKA')
    return { label: 'Open to Foreign Investment', className: 'badge badge-success' };
  if (s === 'TERBATAS')
    return { label: 'Restricted - Conditions Apply', className: 'badge badge-warning' };
  if (s === 'TERTUTUP')
    return { label: 'Closed to Foreign Investment', className: 'badge badge-error' };
  return { label: 'Status Unknown', className: 'badge badge-neutral' };
}

function getRiskBadge(risk: string): { label: string; className: string } {
  const r = (risk || '').toLowerCase();
  if (r.includes('tinggi') && r.includes('menengah'))
    return { label: 'Medium-High Risk', className: 'badge badge-warning' };
  if (r.includes('tinggi') || r === 'high')
    return { label: 'High Risk', className: 'badge badge-error' };
  if (r.includes('menengah') && r.includes('rendah'))
    return { label: 'Medium-Low Risk', className: 'badge badge-cyan' };
  if (r.includes('menengah') || r === 'medium')
    return { label: 'Medium Risk', className: 'badge badge-warning' };
  if (r.includes('rendah') || r === 'low')
    return { label: 'Low Risk', className: 'badge badge-info' };
  return { label: risk || 'Unknown', className: 'badge badge-neutral' };
}

function getPmaBadgeInline(status: string): { label: string; color: string; bg: string; border: string } {
  const s = (status || '').toUpperCase();
  if (s === 'TERBUKA')
    return { label: 'Open to Foreigners', color: '#34d399', bg: 'rgba(34,197,94,0.12)', border: 'rgba(34,197,94,0.25)' };
  if (s === 'TERBATAS')
    return { label: 'Restricted', color: '#fbbf24', bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.25)' };
  if (s === 'TERTUTUP')
    return { label: 'Closed to Foreigners', color: '#f87171', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.25)' };
  return { label: '', color: '', bg: '', border: '' };
}

// =============================================================================
// TOOLTIP COMPONENT (Fase 5)
// =============================================================================

const InfoTooltip = ({ term, explanation }: { term: string; explanation: string }) => (
  <span className="relative group cursor-help border-b border-dashed border-[#D4B483]/40">
    {term}
    <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-[#1A1D24] border border-white/10 rounded text-xs text-[#CCC] w-52 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 text-center shadow-xl">
      {explanation}
    </span>
  </span>
);

function renderWithTooltips(text: string): React.ReactNode {
  const usedTerms = new Set<string>();
  const parts: (string | React.ReactElement)[] = [text];

  for (const [term, explanation] of Object.entries(GLOSSARY)) {
    if (usedTerms.has(term)) continue;
    const regex = new RegExp(`\\b${term}\\b`, 'i');
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      if (typeof part !== 'string') continue;
      const match = regex.exec(part);
      if (match) {
        usedTerms.add(term);
        const before = part.slice(0, match.index);
        const matched = match[0];
        const after = part.slice(match.index + matched.length);
        const replacement: (string | React.ReactElement)[] = [];
        if (before) replacement.push(before);
        replacement.push(<InfoTooltip key={`tt-${term}`} term={matched} explanation={explanation} />);
        if (after) replacement.push(after);
        parts.splice(i, 1, ...replacement);
        break;
      }
    }
  }

  return <>{parts}</>;
}

// =============================================================================
// SUBCOMPONENTS
// =============================================================================

const SourceCard = ({ source }: { source: { id: string; title: string; type: string; date: string } }) => (
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

const ChatMessage = ({ role, content }: { role: 'user' | 'ai'; content: React.ReactNode }) => (
  <motion.div
    initial={{ opacity: 0, y: 15 }}
    animate={{ opacity: 1, y: 0 }}
    className={`flex gap-4 md:gap-6 ${role === 'ai' ? 'items-start' : 'items-center flex-row-reverse'}`}
  >
    <div
      className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${role === 'ai' ? 'bg-[#0F1115] border-[#D4B483]/20 text-[#D4B483]' : 'bg-[#1A1D24] border-white/10 text-slate-400'}`}
    >
      {role === 'ai' ? (
        <Sparkles size={14} />
      ) : (
        <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />
      )}
    </div>
    <div
      className={`max-w-[90%] md:max-w-[85%] ${role === 'ai' ? 'text-base md:text-lg font-light leading-relaxed' : 'text-sm md:text-base font-medium text-white/90'}`}
    >
      {content}
    </div>
  </motion.div>
);

// =============================================================================
// INSPECTOR (Fase 2 labels)
// =============================================================================

const KBLIInspector = ({
  data,
  isLoading,
  onClose,
}: {
  data: KBLIDetail | null;
  isLoading: boolean;
  onClose?: () => void;
}) => {
  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#D4B483]">
        <Loader2 size={32} className="animate-spin mb-4" />
        <p className="text-xs uppercase tracking-widest opacity-50">Loading details...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#444] px-8 text-center">
        <Search size={48} className="mb-6 opacity-20 stroke-1" />
        <p className="text-sm font-medium text-[#666] mb-2">Click on any result to see full details</p>
        <p className="text-xs text-[#444]">
          Licenses, restrictions, risk level and related business codes will appear here
        </p>
      </div>
    );
  }

  const pmaBadge = getPmaBadge(data.pma_status);
  const riskBadge = getRiskBadge(data.risk_profile);

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
      {/* Drag handle for mobile */}
      {onClose && (
        <div className="md:hidden flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>
      )}

      <div className="p-6 md:p-8 border-b border-white/5 bg-gradient-to-b from-[#0F1115] to-[#050507]">
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <span className="px-3 py-1 rounded text-xs font-mono tracking-wider bg-[#D4B483]/10 text-[#D4B483] border border-[#D4B483]/20">
            KBLI {data.code}
          </span>
          <span className={pmaBadge.className}>{pmaBadge.label}</span>
        </div>
        <h2 className="text-2xl md:text-3xl font-serif text-[#F0F0F0] leading-tight mb-6">{data.title}</h2>

        <div className="space-y-3">
          <div className="flex justify-between items-center text-[11px] md:text-[10px] uppercase tracking-widest text-[#666]">
            <span className={riskBadge.className}>{riskBadge.label}</span>
            <span className="text-[#D4B483]">{data.licensing_status}</span>
          </div>
          <div className="h-[2px] w-full bg-[#1A1D24] relative">
            <div
              className="absolute top-0 left-0 h-full bg-[#D4B483] shadow-[0_0_10px_rgba(212,180,131,0.3)] transition-all duration-1000"
              style={{
                width: data.risk_profile.toLowerCase().includes('tinggi')
                  ? '90%'
                  : data.risk_profile.toLowerCase().includes('menengah')
                    ? '50%'
                    : '20%',
              }}
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-10 custom-scrollbar">
        <section>
          <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <FileText size={12} /> Official Description
          </h3>
          <p className="text-sm text-[#CCC] leading-loose font-light border-l border-[#D4B483]/30 pl-5 italic">
            &ldquo;{data.description}&rdquo;
          </p>
        </section>

        {data.licenses.length > 0 && (
          <section>
            <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
              <Scale size={12} /> Required Licenses
            </h3>
            <div className="space-y-4">
              {data.licenses.map((lic, idx) => (
                <div
                  key={idx}
                  className="group p-4 bg-[#0A0C10] rounded border border-white/5 hover:border-[#D4B483]/20 transition-all"
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-medium text-[#E1E1E3] group-hover:text-white transition-colors">
                      {lic.type}
                    </span>
                    <span className="text-[10px] uppercase px-2 py-1 rounded-full bg-[#151921] text-[#888] border border-white/5">
                      {lic.sla}
                    </span>
                  </div>
                  <div className="flex flex-col gap-1 text-xs text-[#666]">
                    <span>
                      Business Size: <span className="text-[#999]">{lic.scale.join(', ')}</span>
                    </span>
                    <span>
                      Risk Level: <span className="text-[#999]">{lic.risk_level}</span>
                    </span>
                  </div>
                  {lic.requirements.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/5">
                      <p className="text-[10px] text-[#444] uppercase mb-2">What you need to do:</p>
                      <ul className="space-y-1">
                        {lic.requirements.slice(0, 3).map((req, ridx) => (
                          <li key={ridx} className="text-[11px] text-[#888] leading-tight">
                            &bull; {req}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <Activity size={12} /> Related Business Codes
          </h3>
          <div className="flex flex-wrap gap-2">
            <div className="px-4 py-2 rounded-full bg-[#0F1115] text-xs text-[#D4B483] border border-[#D4B483]/20">
              Sector: {data.sector}
            </div>
            {data.related_codes.map((rel, idx) => (
              <div
                key={idx}
                className="px-4 py-2 rounded-full bg-[#0F1115] text-xs text-[#888] border border-white/5 hover:border-[#D4B483]/30 hover:text-[#D4B483] cursor-pointer transition-all"
              >
                {rel}
              </div>
            ))}
          </div>
        </section>
      </div>
    </motion.div>
  );
};

// =============================================================================
// WELCOME COMPONENT (Fase 1)
// =============================================================================

const WelcomeOnboarding = ({ onChipClick }: { onChipClick: (query: string) => void }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -20 }}
    className="max-w-2xl mx-auto text-center py-4 md:py-8"
  >
    <h1 className="text-2xl md:text-4xl font-serif text-[#F0F0F0] leading-tight mb-3">
      What business do you want to start in Indonesia?
    </h1>
    <p className="text-sm md:text-base text-[#888] mb-8 md:mb-10">
      Describe your idea in any language and we&apos;ll find the right codes, licenses and requirements.
    </p>

    {/* Starter Chips */}
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

    {/* How it works */}
    <div className="border-t border-white/5 pt-8 md:pt-10">
      <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-6">
        How it works
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
        {[
          { step: '1', text: 'Describe your business idea in any language' },
          { step: '2', text: 'We find the right Indonesian business codes (KBLI)' },
          { step: '3', text: 'We show you requirements, restrictions & next steps' },
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
// MAIN PAGE
// =============================================================================

export default function KBLIExplorerPage() {
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<KBLISearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [activeKBLI, setActiveKBLI] = useState<KBLIDetail | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const [messages, setMessages] = useState<{
    role: 'user' | 'ai';
    content: string;
    detected_kbli?: string[];
    results?: KBLISearchResult[];
    suggested_queries?: string[];
  }[]>([]);
  const [isChatting, setIsChatting] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [placeholderVisible, setPlaceholderVisible] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const isWelcome = messages.length === 0;

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
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleInspect = useCallback(async (code: string) => {
    setIsInspecting(true);
    setInspectorOpen(true);
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

      setQuery('');
      setSearchResults([]);
      setMessages((prev) => [...prev, { role: 'user', content: text }]);
      setIsChatting(true);

      try {
        const response = await kbliApi.chat(text);
        setMessages((prev) => [
          ...prev,
          {
            role: 'ai',
            content: response.answer,
            detected_kbli: response.detected_kbli,
            results: response.results,
            suggested_queries: response.suggested_queries || [],
          },
        ]);

        if (response.results && response.results.length > 0) {
          handleInspect(response.results[0].code);
        } else if (response.detected_kbli.length > 0) {
          handleInspect(response.detected_kbli[0]);
        }
      } catch {
        toast.error('Failed to process request');
      } finally {
        setIsChatting(false);
      }
    },
    [query, isChatting, handleInspect],
  );

  const handleChipClick = useCallback(
    (chipQuery: string) => {
      handleSendMessage(chipQuery);
    },
    [handleSendMessage],
  );

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
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          hidden md:flex
          ${sidebarOpen ? '!flex' : ''}
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
              <div className="text-xs font-medium text-[#E1E1E3]">Business Assistant</div>
              <div className="text-[10px] text-[#555] uppercase tracking-wider">Ready to help</div>
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
                className="w-full bg-[#0F1115]/80 backdrop-blur-md text-[#E1E1E3] placeholder-[#444] rounded-lg py-4 md:py-5 pl-12 md:pl-14 pr-14 border border-white/5 focus:border-[#D4B483]/30 focus:ring-1 focus:ring-[#D4B483]/30 focus:outline-none transition-all shadow-2xl font-light tracking-wide min-h-[44px]"
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
              <button
                type="submit"
                className="absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-md hover:bg-[#1A1D24] text-[#D4B483] transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                disabled={isChatting}
              >
                {isChatting ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
              </button>
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
                        <span className="font-mono text-[#D4B483] text-xs w-12">{res.code}</span>
                        <span className="text-sm text-[#E1E1E3] truncate flex-1">{res.title}</span>
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
            {/* Welcome onboarding OR chat messages */}
            <AnimatePresence mode="wait">
              {isWelcome ? (
                <WelcomeOnboarding key="welcome" onChipClick={handleChipClick} />
              ) : (
                <motion.div
                  key="chat"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="space-y-8 md:space-y-12"
                >
                  {messages.map((msg, idx) => (
                    <div key={idx} className="space-y-4">
                      <ChatMessage
                        role={msg.role}
                        content={
                          msg.role === 'user' ? (
                            <p className="text-lg md:text-xl font-serif text-[#F0F0F0] leading-normal">
                              {msg.content}
                            </p>
                          ) : (
                            <div className="space-y-6 text-[#BBB]">
                              <div className="whitespace-pre-line">
                                {renderWithTooltips(msg.content)}
                              </div>

                              {msg.results && msg.results.length > 0 ? (
                                <div className="space-y-3 mt-4">
                                  {msg.results.map((result: KBLISearchResult) => {
                                    const pmaBadgeInline = getPmaBadgeInline(result.pma_status);
                                    return (
                                      <button
                                        key={result.code}
                                        onClick={() => handleInspect(result.code)}
                                        className="group w-full text-left p-4 min-h-[44px] rounded-lg bg-[#0F1115]/60 border border-white/5 hover:border-[#D4B483]/40 hover:bg-[#151921] transition-all duration-200"
                                      >
                                        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                                          <span className="font-mono text-sm tracking-wider text-[#D4B483] bg-[#D4B483]/10 px-2.5 py-0.5 rounded border border-[#D4B483]/20">
                                            {result.code}
                                          </span>
                                          <div className="flex items-center gap-2">
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
                                            <span className="text-[10px] uppercase tracking-widest text-[#555]">
                                              {Math.round(result.score * 100)}% match
                                            </span>
                                          </div>
                                        </div>
                                        <h4 className="text-sm font-serif text-[#E1E1E3] group-hover:text-white transition-colors mb-1">
                                          {result.title}
                                        </h4>
                                        <p className="text-xs text-[#777] leading-relaxed line-clamp-2">
                                          {result.description}
                                        </p>
                                        <div className="flex items-center gap-1 mt-2 text-[10px] text-[#555] group-hover:text-[#D4B483] transition-colors">
                                          <span>View details</span>
                                          <ChevronRight size={10} />
                                        </div>
                                      </button>
                                    );
                                  })}
                                </div>
                              ) : (
                                msg.detected_kbli &&
                                msg.detected_kbli.length > 0 && (
                                  <div className="flex flex-wrap gap-2 mt-4">
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
                                  </div>
                                )
                              )}

                              {/* Suggested follow-up queries (Fase 4) */}
                              {msg.suggested_queries && msg.suggested_queries.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-white/5">
                                  {msg.suggested_queries.map((sq: string, sqIdx: number) => (
                                    <button
                                      key={sqIdx}
                                      onClick={() => handleSendMessage(sq)}
                                      className="group flex items-center gap-1.5 px-3 py-2 min-h-[44px] rounded-full text-xs text-[#D4B483] bg-[#D4B483]/5 border border-[#D4B483]/20 hover:bg-[#D4B483]/10 hover:border-[#D4B483]/40 transition-all"
                                    >
                                      <ArrowRight size={10} className="opacity-60 group-hover:opacity-100" />
                                      <span>{sq}</span>
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        }
                      />
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {isChatting && (
              <div className="flex gap-4 md:gap-6 items-start animate-pulse">
                <div className="w-8 h-8 rounded-full border bg-[#0F1115] border-[#D4B483]/20 text-[#D4B483] flex items-center justify-center">
                  <Sparkles size={14} />
                </div>
                <div className="h-4 bg-[#1A1D24] rounded w-2/3 mt-2" />
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>
      </main>

      {/* RIGHT PANEL: The Inspector — desktop fixed, mobile bottom sheet */}
      {/* Desktop inspector */}
      <aside className="hidden xl:block w-[420px] bg-[#0A0C10]/90 backdrop-blur-2xl border-l border-white/5 relative z-20 shadow-[-5px_0_30px_rgba(0,0,0,0.2)]">
        <KBLIInspector data={activeKBLI} isLoading={isInspecting} />
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
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="xl:hidden fixed bottom-0 left-0 right-0 h-[70vh] bg-[#0A0C10] border-t border-white/10 rounded-t-2xl z-50 overflow-hidden"
            >
              <KBLIInspector
                data={activeKBLI}
                isLoading={isInspecting}
                onClose={() => setInspectorOpen(false)}
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
