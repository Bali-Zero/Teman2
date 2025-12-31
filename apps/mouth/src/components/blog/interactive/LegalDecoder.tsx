'use client';

import * as React from 'react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Scale,
  ChevronDown,
  FileText,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  BookOpen,
  MessageCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface LegalSection {
  id: string;
  /** Original legal text */
  original: string;
  /** Plain language explanation */
  explanation: string;
  /** Key points */
  keyPoints?: string[];
  /** Impact/implications */
  impact?: string;
  /** Severity: how much this affects the reader */
  severity?: 'low' | 'medium' | 'high';
  /** Article/Pasal reference */
  reference?: string;
}

export interface LegalDecoderProps {
  /** Title */
  title: string;
  /** Document reference (e.g., "PP 28/2025") */
  documentRef: string;
  /** Document type */
  documentType?: 'UU' | 'PP' | 'PM' | 'SK' | 'PERPRES' | 'Other';
  /** Date published */
  publishedDate?: string;
  /** Status */
  status?: 'active' | 'amended' | 'revoked';
  /** Sections to decode */
  sections: LegalSection[];
  /** Summary */
  summary?: string;
  /** Link to full document */
  documentUrl?: string;
  /** Custom class */
  className?: string;
}

// ============================================================================
// Severity styles
// ============================================================================

const severityStyles = {
  low: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    label: 'Low Impact',
  },
  medium: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    label: 'Medium Impact',
  },
  high: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
    label: 'High Impact',
  },
};

const statusStyles = {
  active: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Active' },
  amended: { bg: 'bg-amber-500/20', text: 'text-amber-400', label: 'Amended' },
  revoked: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Revoked' },
};

// ============================================================================
// Main Component
// ============================================================================

export function LegalDecoder({
  title,
  documentRef,
  documentType = 'Other',
  publishedDate,
  status = 'active',
  sections,
  summary,
  documentUrl,
  className,
}: LegalDecoderProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [showOriginal, setShowOriginal] = useState<Set<string>>(new Set());

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleOriginal = (id: string) => {
    setShowOriginal((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const statusStyle = statusStyles[status];

  return (
    <div className={cn('bg-black/40 rounded-2xl border border-white/10 overflow-hidden', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10 bg-gradient-to-r from-amber-500/10 to-transparent">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs px-2 py-0.5 rounded bg-white/10 text-white/60 font-mono">
                  {documentType}
                </span>
                <span className={cn('text-xs px-2 py-0.5 rounded', statusStyle.bg, statusStyle.text)}>
                  {statusStyle.label}
                </span>
              </div>
              <h3 className="font-serif text-xl font-semibold text-white mt-2">{title}</h3>
              <p className="text-white/60 text-sm mt-1">
                {documentRef}
                {publishedDate && ` • Published ${publishedDate}`}
              </p>
            </div>
          </div>

          {documentUrl && (
            <a
              href={documentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-white/60 hover:text-white transition-colors"
            >
              <FileText className="w-4 h-4" />
              <span>Full Document</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>

        {/* Summary */}
        {summary && (
          <div className="mt-4 p-3 rounded-lg bg-white/5 border border-white/10">
            <div className="flex items-start gap-2">
              <BookOpen className="w-4 h-4 text-white/40 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-white/70">{summary}</p>
            </div>
          </div>
        )}
      </div>

      {/* Sections */}
      <div className="p-6 space-y-4">
        {sections.map((section, index) => {
          const isExpanded = expandedSections.has(section.id);
          const isShowingOriginal = showOriginal.has(section.id);
          const severity = section.severity || 'low';
          const sevStyle = severityStyles[severity];

          return (
            <motion.div
              key={section.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className={cn(
                'rounded-xl border overflow-hidden',
                isExpanded ? sevStyle.border : 'border-white/10'
              )}
            >
              {/* Section header */}
              <button
                onClick={() => toggleSection(section.id)}
                className={cn(
                  'w-full flex items-center justify-between p-4 text-left transition-colors',
                  isExpanded ? sevStyle.bg : 'bg-white/5 hover:bg-white/10'
                )}
              >
                <div className="flex items-center gap-3">
                  {section.reference && (
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/10 text-white/60">
                      {section.reference}
                    </span>
                  )}
                  <span className={cn(
                    'font-medium',
                    isExpanded ? sevStyle.text : 'text-white'
                  )}>
                    {section.explanation.slice(0, 60)}...
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn('text-xs px-2 py-0.5 rounded', sevStyle.bg, sevStyle.text)}>
                    {sevStyle.label}
                  </span>
                  <ChevronDown
                    className={cn(
                      'w-4 h-4 text-white/40 transition-transform',
                      isExpanded && 'rotate-180'
                    )}
                  />
                </div>
              </button>

              {/* Expanded content */}
              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="p-4 space-y-4 border-t border-white/10">
                      {/* Toggle original text */}
                      <button
                        onClick={() => toggleOriginal(section.id)}
                        className="flex items-center gap-2 text-xs text-white/50 hover:text-white transition-colors"
                      >
                        <FileText className="w-3 h-3" />
                        <span>{isShowingOriginal ? 'Hide' : 'Show'} original legal text</span>
                      </button>

                      {/* Original text */}
                      {isShowingOriginal && (
                        <div className="p-3 rounded-lg bg-black/40 border border-white/10">
                          <p className="text-xs text-white/40 mb-2">Original Text:</p>
                          <p className="text-sm text-white/60 italic font-serif">
                            "{section.original}"
                          </p>
                        </div>
                      )}

                      {/* Explanation */}
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <MessageCircle className="w-4 h-4 text-[#2251ff]" />
                          <span className="text-sm font-medium text-[#2251ff]">In Plain English</span>
                        </div>
                        <p className="text-white/80 leading-relaxed">{section.explanation}</p>
                      </div>

                      {/* Key points */}
                      {section.keyPoints && section.keyPoints.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-white/60 mb-2">Key Points:</p>
                          <ul className="space-y-1.5">
                            {section.keyPoints.map((point, i) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-white/70">
                                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                                <span>{point}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Impact */}
                      {section.impact && (
                        <div className={cn('p-3 rounded-lg', sevStyle.bg)}>
                          <div className="flex items-start gap-2">
                            <AlertTriangle className={cn('w-4 h-4 flex-shrink-0 mt-0.5', sevStyle.text)} />
                            <div>
                              <p className={cn('text-sm font-medium mb-1', sevStyle.text)}>
                                Impact on Your Business
                              </p>
                              <p className="text-sm text-white/70">{section.impact}</p>
                            </div>
                          </div>
                        </div>
                      )}
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
}
