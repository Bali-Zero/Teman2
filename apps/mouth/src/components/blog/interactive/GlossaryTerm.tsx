'use client';

import * as React from 'react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ExternalLink, BookOpen, Link2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface GlossaryTermProps {
  /** The term being defined */
  term: string;
  /** Short definition (shown in tooltip) */
  definition: string;
  /** Full explanation (shown in expanded view) */
  fullExplanation?: string;
  /** Indonesian translation */
  indonesian?: string;
  /** Related terms */
  relatedTerms?: string[];
  /** Link to full article */
  articleUrl?: string;
  /** Variant */
  variant?: 'inline' | 'highlight';
  /** Children (usually the term text) */
  children?: React.ReactNode;
  /** Custom class */
  className?: string;
}

// ============================================================================
// Main Component
// ============================================================================

export function GlossaryTerm({
  term,
  definition,
  fullExplanation,
  indonesian,
  relatedTerms,
  articleUrl,
  variant = 'inline',
  children,
  className,
}: GlossaryTermProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState<'above' | 'below'>('above');
  const triggerRef = React.useRef<HTMLSpanElement>(null);

  // Calculate tooltip position
  const handleMouseEnter = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const spaceAbove = rect.top;
      const spaceBelow = window.innerHeight - rect.bottom;
      setTooltipPosition(spaceBelow > 200 || spaceBelow > spaceAbove ? 'below' : 'above');
    }
    setIsOpen(true);
  };

  const isHighlight = variant === 'highlight';

  return (
    <span className={cn('relative inline-block', className)}>
      {/* Trigger */}
      <span
        ref={triggerRef}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setIsOpen(false)}
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'cursor-help transition-colors',
          isHighlight
            ? 'px-1.5 py-0.5 rounded bg-[#2251ff]/10 text-[#2251ff] font-medium'
            : 'border-b border-dotted border-white/40 hover:border-[#2251ff] hover:text-[#2251ff]'
        )}
      >
        {children || term}
      </span>

      {/* Tooltip/Popover */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: tooltipPosition === 'above' ? 5 : -5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: tooltipPosition === 'above' ? 5 : -5, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className={cn(
              'absolute z-50 w-72 p-4 rounded-xl',
              'bg-black/95 border border-white/10 shadow-2xl',
              tooltipPosition === 'above'
                ? 'bottom-full left-1/2 -translate-x-1/2 mb-2'
                : 'top-full left-1/2 -translate-x-1/2 mt-2'
            )}
            onMouseEnter={() => setIsOpen(true)}
            onMouseLeave={() => setIsOpen(false)}
          >
            {/* Arrow */}
            <div
              className={cn(
                'absolute left-1/2 -translate-x-1/2 w-3 h-3 rotate-45 bg-black/95 border-white/10',
                tooltipPosition === 'above'
                  ? 'bottom-0 translate-y-1/2 border-r border-b'
                  : 'top-0 -translate-y-1/2 border-l border-t'
              )}
            />

            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <h5 className="font-semibold text-white">{term}</h5>
                {indonesian && (
                  <p className="text-xs text-white/40 mt-0.5">
                    🇮🇩 {indonesian}
                  </p>
                )}
              </div>
              <div className="p-1 rounded bg-[#2251ff]/20">
                <BookOpen className="w-3.5 h-3.5 text-[#2251ff]" />
              </div>
            </div>

            {/* Definition */}
            <p className="text-sm text-white/70 leading-relaxed">{definition}</p>

            {/* Full explanation (if provided) */}
            {fullExplanation && (
              <p className="text-sm text-white/50 mt-2 pt-2 border-t border-white/10">
                {fullExplanation}
              </p>
            )}

            {/* Related terms */}
            {relatedTerms && relatedTerms.length > 0 && (
              <div className="mt-3 pt-2 border-t border-white/10">
                <p className="text-xs text-white/40 mb-1.5 flex items-center gap-1">
                  <Link2 className="w-3 h-3" />
                  Related terms
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {relatedTerms.map((rt) => (
                    <span
                      key={rt}
                      className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/60"
                    >
                      {rt}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Article link */}
            {articleUrl && (
              <a
                href={articleUrl}
                className="mt-3 flex items-center gap-1.5 text-xs text-[#2251ff] hover:underline"
              >
                <span>Read full article</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}
