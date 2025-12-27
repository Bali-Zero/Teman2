import React, { useState } from 'react';
import { FileText, ChevronDown, ChevronUp, CheckCircle2, Download, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Source } from '@/types';

interface CitationCardProps {
  sources: Source[];
}

export const CitationCard: React.FC<CitationCardProps> = ({ sources }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const toggleSource = (idx: number) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  // Get expanded content (prefer content, fallback to snippet)
  const getExpandedContent = (source: Source): string | undefined => {
    return source.content || source.snippet;
  };

  return (
    <div className="mt-4 pt-3 border-t border-[var(--glass-border)] space-y-3">
      <div className="text-[10px] uppercase tracking-wider font-semibold text-[var(--foreground-muted)] mb-2 flex items-center gap-1">
        <CheckCircle2 className="w-3 h-3 text-[var(--success)]" />
        Verified Sources
      </div>

      <div className="grid gap-2">
        {sources.map((source, idx) => {
          const expandedContent = getExpandedContent(source);
          const hasExpandableContent = !!expandedContent;

          return (
            <motion.div
              key={source.id || idx}
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
                onClick={() => hasExpandableContent && toggleSource(idx)}
                className={`px-3 py-2.5 flex items-center justify-between ${hasExpandableContent ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <div className="flex items-center gap-2.5 overflow-hidden">
                  <div className="p-1 rounded-md bg-[var(--background)]/50 text-[var(--accent)]">
                    <FileText className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-xs font-medium text-[var(--foreground-secondary)] group-hover:text-[var(--foreground)] transition-colors truncate">
                    {source.title || 'Unknown Source'}
                  </span>
                  {source.score && source.score > 0.8 && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-[var(--success)]/20 text-[var(--success)]">
                      High match
                    </span>
                  )}
                </div>

                {hasExpandableContent && (
                  <div className="text-[var(--foreground-muted)] group-hover:text-[var(--accent)] transition-colors">
                    {expandedIndex === idx ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </div>
                )}
              </div>

              {/* Expandable Content */}
              <AnimatePresence>
                {expandedIndex === idx && expandedContent && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="px-3 pb-3 pt-0 space-y-2">
                      <div className="p-2.5 rounded-md bg-[var(--background)]/50 text-[11px] leading-relaxed text-[var(--foreground-muted)] border border-[var(--border)]/30 font-mono">
                        {expandedContent}
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-2">
                        {source.download_url && (
                          <a
                            href={source.download_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Download className="w-3 h-3" />
                            Download full document
                          </a>
                        )}
                        {source.url && (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] text-[var(--foreground-muted)] hover:text-[var(--accent)]"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="w-3 h-3" />
                            View source
                          </a>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
