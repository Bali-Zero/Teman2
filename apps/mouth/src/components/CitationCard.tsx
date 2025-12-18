import React, { useState } from 'react';
import { FileText, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface Source {
  title?: string;
  content?: string;
}

interface CitationCardProps {
  sources: Source[];
}

export const CitationCard: React.FC<CitationCardProps> = ({ sources }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const toggleSource = (idx: number) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  return (
    <div className="mt-4 pt-3 border-t border-[var(--glass-border)] space-y-3">
      <div className="text-[10px] uppercase tracking-wider font-semibold text-[var(--foreground-muted)] mb-2 flex items-center gap-1">
        <CheckCircle2 className="w-3 h-3 text-[var(--success)]" />
        Verified Sources
      </div>
      
      <div className="grid gap-2">
        {sources.map((source, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1, duration: 0.3 }}
            className={`
              group relative overflow-hidden rounded-[var(--radius)] 
              bg-[var(--glass-bg)] border border-[var(--glass-border)]
              hover:border-[var(--accent)]/30 hover:bg-[var(--background-secondary)]
              transition-colors duration-300
            `}
          >
            {/* Header / Title */}
            <div 
              onClick={() => toggleSource(idx)}
              className="px-3 py-2.5 flex items-center justify-between cursor-pointer"
            >
              <div className="flex items-center gap-2.5 overflow-hidden">
                <div className="p-1 rounded-md bg-[var(--background)]/50 text-[var(--accent)]">
                  <FileText className="w-3.5 h-3.5" />
                </div>
                <span className="text-xs font-medium text-[var(--foreground-secondary)] group-hover:text-[var(--foreground)] transition-colors truncate">
                  {source.title || 'Unknown Source'}
                </span>
              </div>
              
              <div className="text-[var(--foreground-muted)] group-hover:text-[var(--accent)] transition-colors">
                {expandedIndex === idx ? (
                  <ChevronUp className="w-3.5 h-3.5" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
              </div>
            </div>

            {/* Expandable Content */}
            <AnimatePresence>
              {expandedIndex === idx && source.content && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="px-3 pb-3 pt-0">
                     <div className="p-2.5 rounded-md bg-[var(--background)]/50 text-[11px] leading-relaxed text-[var(--foreground-muted)] border border-[var(--border)]/30 font-mono">
                        {source.content}
                     </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>
    </div>
  );
};
