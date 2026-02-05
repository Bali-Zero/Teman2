'use client';

import React, { useState, useEffect, useRef } from 'react';
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
  AlertCircle,
  CheckCircle2,
  Loader2,
  History,
  MessageSquare,
  Send,
} from 'lucide-react';
import { kbliApi, KBLIDetail, KBLISearchResult } from '@/lib/api/kbli.api';
import { toast } from 'sonner';

// --- MOCK SOURCES ---
const MOCK_SOURCES = [
  { id: 'pp28', title: 'PP 28/2025 Lampiran I', type: 'Official Regulation', date: 'Jan 2025' },
  { id: 'bps25', title: 'Peraturan BPS 7/2025', type: 'Statistical Standard', date: 'Feb 2025' },
];

// --- COMPONENTS ---

const SourceCard = ({ source }: { source: any }) => (
  <div className="group flex items-center gap-4 p-4 rounded-lg bg-[#0F1115]/40 border border-white/5 hover:bg-[#151921] hover:border-[#D4B483]/30 transition-all duration-300 cursor-pointer backdrop-blur-sm">
    <div className="p-2.5 rounded bg-[#1A1D24] text-[#888] group-hover:text-[#D4B483] transition-colors border border-white/5">
      <BookOpen size={14} strokeWidth={1.5} />
    </div>
    <div>
      <h4 className="text-sm font-medium text-[#E1E1E3] group-hover:text-white font-serif tracking-wide">
        {source.title}
      </h4>
      <p className="text-[10px] uppercase tracking-widest text-[#666] mt-1">
        {source.type} • {source.date}
      </p>
    </div>
  </div>
);

const ChatMessage = ({ role, content }: { role: 'user' | 'ai'; content: React.ReactNode }) => (
  <motion.div
    initial={{ opacity: 0, y: 15 }}
    animate={{ opacity: 1, y: 0 }}
    className={`flex gap-6 ${role === 'ai' ? 'items-start' : 'items-center flex-row-reverse'}`}
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
      className={`max-w-[85%] ${role === 'ai' ? 'text-lg font-light leading-relaxed' : 'text-base font-medium text-white/90'}`}
    >
      {content}
    </div>
  </motion.div>
);

const KBLIInspector = ({ data, isLoading }: { data: KBLIDetail | null; isLoading: boolean }) => {
  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#D4B483]">
        <Loader2 size={32} className="animate-spin mb-4" />
        <p className="text-xs uppercase tracking-widest opacity-50">Querying Knowledge Graph...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#333]">
        <Activity size={64} className="mb-6 opacity-10 stroke-1" />
        <p className="text-xs uppercase tracking-[0.2em] font-medium">Select a data point</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="h-full flex flex-col"
    >
      <div className="p-8 border-b border-white/5 bg-gradient-to-b from-[#0F1115] to-[#050507]">
        <div className="flex items-center gap-3 mb-4">
          <span className="px-3 py-1 rounded text-xs font-mono tracking-wider bg-[#D4B483]/10 text-[#D4B483] border border-[#D4B483]/20">
            KBLI {data.code}
          </span>
          <span className="px-3 py-1 rounded text-xs tracking-wider uppercase bg-emerald-900/20 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
            <CheckCircle2 size={10} /> {data.pma_status}
          </span>
        </div>
        <h2 className="text-3xl font-serif text-[#F0F0F0] leading-tight mb-6">{data.title}</h2>

        <div className="space-y-3">
          <div className="flex justify-between text-[11px] uppercase tracking-widest text-[#666]">
            <span>Risk Profile: {data.risk_profile}</span>
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

      <div className="flex-1 overflow-y-auto p-8 space-y-10 custom-scrollbar">
        <section>
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <FileText size={12} /> BPS Official Standard
          </h3>
          <p className="text-sm text-[#CCC] leading-loose font-light border-l border-[#D4B483]/30 pl-5 italic">
            "{data.description}"
          </p>
        </section>

        {data.licenses.length > 0 && (
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
              <Scale size={12} /> Compliance Matrix (PP 28/2025)
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
                      Scale: <span className="text-[#999]">{lic.scale.join(', ')}</span>
                    </span>
                    <span>
                      Risk: <span className="text-[#999]">{lic.risk_level}</span>
                    </span>
                  </div>
                  {lic.requirements.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/5">
                      <p className="text-[10px] text-[#444] uppercase mb-2">Key Obligations:</p>
                      <ul className="space-y-1">
                        {lic.requirements.slice(0, 3).map((req, ridx) => (
                          <li key={ridx} className="text-[11px] text-[#888] leading-tight">
                            • {req}
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
          <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <Activity size={12} /> Related Graph Nodes
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

export default function KBLIExplorerPage() {
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<KBLISearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [activeKBLI, setActiveKBLI] = useState<KBLIDetail | null>(null);
  const [isInspecting, setIsInspecting] = useState(false);
  const [messages, setMessages] = useState<any[]>([
    {
      role: 'ai',
      content:
        'Welcome to the Zantara KBLI Intelligence Engine. Ask me about any business classification or requirement under the new 2025 regulatory framework.',
    },
  ]);
  const [isChatting, setIsChatting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-search on typing (debounce)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.length > 2) {
        handleSearch();
      } else {
        setSearchResults([]);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [query]);

  // Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSearch = async () => {
    setIsSearching(true);
    try {
      const results = await kbliApi.search(query);
      setSearchResults(results);
    } catch (err) {
      // Error handled via UI state
    } finally {
      setIsSearching(false);
    }
  };

  const handleInspect = async (code: string) => {
    setIsInspecting(true);
    try {
      const detail = await kbliApi.inspect(code);
      setActiveKBLI(detail);
    } catch (err) {
      toast.error(`Failed to load KBLI ${code}`);
    } finally {
      setIsInspecting(false);
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query || isChatting) return;

    const userQuery = query;
    setQuery('');
    setSearchResults([]);
    setMessages((prev) => [...prev, { role: 'user', content: userQuery }]);
    setIsChatting(true);

    try {
      const response = await kbliApi.chat(userQuery);
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: response.answer,
          detected_kbli: response.detected_kbli,
        },
      ]);

      // If a code was detected, auto-inspect the first one
      if (response.detected_kbli.length > 0) {
        handleInspect(response.detected_kbli[0]);
      }
    } catch (err) {
      toast.error('Failed to process request');
    } finally {
      setIsChatting(false);
    }
  };

  return (
    <div className="flex h-full font-sans">
      {/* LEFT PANEL: Sources & Context (20%) */}
      <aside className="w-[320px] bg-[#080A0E] border-r border-white/5 flex flex-col z-20 shadow-[5px_0_30px_rgba(0,0,0,0.3)]">
        <div className="p-8 pb-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 relative flex-shrink-0">
              <img
                src="/images/logo-zantara.png"
                alt="Zantara Logo"
                className="w-full h-full object-contain filter drop-shadow-[0_0_8px_rgba(212,180,131,0.2)]"
              />
            </div>
            <div className="flex flex-col">
              <span className="font-serif text-lg tracking-wide text-[#E1E1E3]">
                Zantara<span className="text-[#D4B483] font-light">KBLI</span>
              </span>
              <span className="text-[9px] uppercase tracking-[0.3em] text-[#444] -mt-1">
                Intelligence Module
              </span>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-8">
          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#333] mb-4 px-2">
              Knowledge Base
            </h3>
            <div className="space-y-3">
              {MOCK_SOURCES.map((source) => (
                <SourceCard key={source.id} source={source} />
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#333] mb-4 px-2">
              Exploration Hub
            </h3>
            <div className="space-y-1">
              <button className="w-full group flex items-center justify-between px-4 py-3 rounded text-sm text-[#666] hover:bg-[#151921] hover:text-[#CCC] transition-all border border-transparent hover:border-white/5 text-left">
                <span className="flex items-center gap-2">
                  <History size={14} /> Recent Queries
                </span>
                <ChevronRight
                  size={12}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </button>
              <button className="w-full group flex items-center justify-between px-4 py-3 rounded text-sm text-[#666] hover:bg-[#151921] hover:text-[#CCC] transition-all border border-transparent hover:border-white/5 text-left">
                <span className="flex items-center gap-2">
                  <Layers size={14} /> Sector Mapping
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
              <div className="text-xs font-medium text-[#E1E1E3]">Bali Zero Analyst</div>
              <div className="text-[10px] text-[#555] uppercase tracking-wider">
                Online • 2025 Ready
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* CENTER PANEL: The Workspace (50%) */}
      <main className="flex-1 flex flex-col bg-transparent relative z-10">
        {/* Header/Search */}
        <div className="p-8 pt-10 relative">
          <div className="relative max-w-3xl mx-auto">
            <form onSubmit={handleSendMessage}>
              <input
                type="text"
                placeholder="Query the 2025 Regulatory Framework..."
                className="w-full bg-[#0F1115]/80 backdrop-blur-md text-[#E1E1E3] placeholder-[#444] rounded-lg py-5 pl-14 pr-14 border border-white/5 focus:border-[#D4B483]/30 focus:ring-1 focus:ring-[#D4B483]/30 focus:outline-none transition-all shadow-2xl font-light tracking-wide"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <Search
                className="absolute left-5 top-1/2 -translate-y-1/2 text-[#444]"
                size={20}
                strokeWidth={1.5}
              />
              <button
                type="submit"
                className="absolute right-4 top-1/2 -translate-y-1/2 p-2 rounded-md hover:bg-[#1A1D24] text-[#D4B483] transition-colors"
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
                    Semantic Matches
                  </div>
                  <div className="max-h-60 overflow-y-auto custom-scrollbar">
                    {searchResults.map((res, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          handleInspect(res.code);
                          setSearchResults([]);
                        }}
                        className="w-full flex items-center gap-4 px-4 py-3 hover:bg-[#1A1D24] border-b border-white/5 last:border-0 text-left transition-colors"
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
        <div className="flex-1 overflow-y-auto px-8 pb-8 custom-scrollbar">
          <div className="max-w-3xl mx-auto space-y-12 py-4">
            {messages.map((msg, idx) => (
              <div key={idx} className="space-y-4">
                <ChatMessage
                  role={msg.role}
                  content={
                    msg.role === 'user' ? (
                      <p className="text-xl font-serif text-[#F0F0F0] leading-normal">
                        {msg.content}
                      </p>
                    ) : (
                      <div className="space-y-6 text-[#BBB]">
                        <div
                          dangerouslySetInnerHTML={{ __html: msg.content.replace(/\n/g, '<br/>') }}
                        />

                        {msg.detected_kbli && msg.detected_kbli.length > 0 && (
                          <div className="flex flex-wrap gap-2 mt-4">
                            {msg.detected_kbli.map((code: string) => (
                              <button
                                key={code}
                                onClick={() => handleInspect(code)}
                                className="group flex items-center gap-2 px-3 py-2 rounded bg-[#151921] border border-white/10 hover:border-[#D4B483] transition-all"
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
                        )}
                      </div>
                    )
                  }
                />
              </div>
            ))}
            {isChatting && (
              <div className="flex gap-6 items-start animate-pulse">
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

      {/* RIGHT PANEL: The Inspector (30%) */}
      <aside className="w-[420px] bg-[#0A0C10]/90 backdrop-blur-2xl border-l border-white/5 relative z-20 shadow-[-5px_0_30px_rgba(0,0,0,0.2)]">
        <KBLIInspector data={activeKBLI} isLoading={isInspecting} />
      </aside>
    </div>
  );
}
