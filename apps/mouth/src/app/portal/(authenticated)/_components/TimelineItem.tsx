'use client';

/**
 * TimelineItem — extracted from the portal home so the timeline section
 * can be dynamic-imported, trimming the portal home's initial bundle.
 */

import React from 'react';
import { Clock, MessageCircle, FileText, Briefcase, AlertTriangle, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TimelineEntry } from '@/lib/api/types/timeline.types';

export function TimelineItem({ entry, isLast }: { entry: TimelineEntry; isLast: boolean }) {
  const isFuture =
    'isFuture' in entry ? Boolean((entry as unknown as { isFuture?: boolean }).isFuture) : false;

  const getIcon = () => {
    switch (entry.type) {
      case 'message':
        return <MessageCircle className="w-4 h-4" />;
      case 'document':
        return <FileText className="w-4 h-4" />;
      case 'practice':
        return <Briefcase className="w-4 h-4" />;
      case 'deadline':
        return <AlertTriangle className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const getBgColor = () => {
    if (isFuture) return 'bg-[rgba(245,158,11,0.15)] text-[var(--neon-amber)]';
    switch (entry.type) {
      case 'message':
        return 'bg-[rgba(59,130,246,0.15)] text-[var(--neon-blue)]';
      case 'deadline':
        return 'bg-[rgba(244,63,94,0.15)] text-[var(--neon-rose)]';
      default:
        return 'text-[var(--tx-secondary)]';
    }
  };

  const getDotStyle = (): React.CSSProperties => {
    if (isFuture)
      return {
        background: 'rgba(245,158,11,0.1)',
        color: 'var(--neon-amber)',
        borderColor: 'var(--neon-amber)',
      };
    switch (entry.type) {
      case 'message':
        return {
          background: 'rgba(59,130,246,0.1)',
          color: 'var(--neon-blue)',
          borderColor: 'var(--neon-blue)',
        };
      case 'deadline':
        return {
          background: 'rgba(244,63,94,0.1)',
          color: 'var(--neon-rose)',
          borderColor: 'var(--neon-rose)',
        };
      default:
        return {
          background: 'var(--glass-rim)',
          color: 'var(--tx-secondary)',
          borderColor: 'rgba(255,255,255,0.1)',
        };
    }
  };

  const _isLast = isLast; // retained for API compatibility
  void _isLast;

  return (
    <div className="relative pl-6">
      <div
        className="absolute -left-[9px] top-0 w-4 h-4 rounded-full flex items-center justify-center border-2 border-[var(--anthracite-base)] shadow-[0_0_10px_currentColor]"
        style={getDotStyle()}
      >
        {/* Dot only */}
      </div>

      <div
        className="crystal-stat-card !border !p-4 !shadow-none"
        style={{
          background: isFuture ? 'rgba(245,158,11,0.02)' : 'rgba(255,255,255,0.02)',
          borderColor: isFuture ? 'rgba(245,158,11,0.2)' : 'var(--glass-rim)',
        }}
      >
        <div className="flex items-center gap-2 mb-2">
          <div
            className={cn(
              'p-1.5 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)]',
              getBgColor()
            )}
          >
            {getIcon()}
          </div>
          <span
            className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)]"
            title={new Date(entry.occurredAt).toLocaleDateString('en-US', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
              year: 'numeric',
            })}
          >
            {new Date(entry.occurredAt).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
            {isFuture && ' (Upcoming)'}
          </span>
          {(() => {
            const diff = Math.round((new Date(entry.occurredAt).getTime() - Date.now()) / 86400000);
            if (diff === 0)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold">
                  Today
                </span>
              );
            if (diff > 0)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-semibold">
                  ⏰ In {diff}d
                </span>
              );
            const abs = Math.abs(diff);
            if (abs <= 7)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[var(--bz-text-2)] font-semibold">
                  {abs}d ago
                </span>
              );
            if (abs <= 30)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[var(--bz-text-2)] font-semibold">
                  {Math.floor(abs / 7)}w ago
                </span>
              );
            return null;
          })()}
        </div>

        <h3 className="font-bold text-[var(--tx-pure)] text-sm">{entry.title}</h3>
        <p className="text-xs mt-1.5 text-[var(--tx-secondary)] line-clamp-2">
          {entry.description}
        </p>

        {entry.type === 'message' && entry.status === 'team_to_client' && (
          <button
            type="button"
            onClick={() => {
              window.location.href = '/portal/chat';
            }}
            className="mt-3 text-[10px] font-bold uppercase tracking-widest flex items-center text-[var(--bz-copper)] hover:text-white transition-colors cursor-pointer w-fit inline-flex"
          >
            Reply <ChevronRight className="w-3 h-3 ml-1" />
          </button>
        )}
      </div>
    </div>
  );
}
