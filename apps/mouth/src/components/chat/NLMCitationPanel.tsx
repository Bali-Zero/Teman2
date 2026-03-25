"use client";

import React from "react";
import { BookOpen, ChevronDown, ChevronUp, FileText } from "lucide-react";

interface NLMCitation {
  source_file: string;
  section: string;
  excerpt: string;
  page?: number;
}

interface NLMCitationPanelProps {
  citations: NLMCitation[];
  domainLabel: string;
  expanded: boolean;
  onToggle: () => void;
}

export const NLMCitationPanel: React.FC<NLMCitationPanelProps> = ({
  citations,
  domainLabel,
  expanded,
  onToggle,
}) => {
  return (
    <div className="mt-3 rounded-lg border-l-2 border-amber-600 overflow-hidden">
      {/* Header — always visible, toggles expand */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 bg-zinc-900/50 hover:bg-zinc-900/70 transition-colors text-left"
      >
        <div className="flex items-center gap-2 text-xs font-medium text-amber-600">
          <BookOpen size={14} />
          <span>Fonti ufficiali — {domainLabel}</span>
        </div>
        <div className="text-zinc-400">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {/* Collapsible citations list */}
      <div
        className="transition-[max-height,opacity] duration-300 ease-in-out overflow-hidden"
        style={{
          maxHeight: expanded ? `${citations.length * 120 + 16}px` : "0px",
          opacity: expanded ? 1 : 0,
        }}
      >
        <div className="px-3 pb-3 pt-1 bg-zinc-900/50 space-y-3">
          {citations.map((citation, idx) => (
            <div key={idx} className="flex gap-2.5">
              <div className="flex-shrink-0 mt-0.5 text-amber-600/60">
                <FileText size={12} />
              </div>
              <div className="min-w-0 space-y-0.5">
                <p className="text-xs font-medium text-zinc-300 truncate">
                  {citation.source_file}
                </p>
                <p className="text-[10px] text-zinc-500">
                  {citation.section}
                  {citation.page != null && ` — p. ${citation.page}`}
                </p>
                <p className="text-[11px] text-zinc-400 italic leading-relaxed">
                  &ldquo;{citation.excerpt}&rdquo;
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
