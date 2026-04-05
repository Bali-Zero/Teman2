'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { CalendarEvent } from './types';

interface EventCardProps {
  event: CalendarEvent;
  compact?: boolean;
  onClick?: (event: CalendarEvent) => void;
  isSelected?: boolean;
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString('it-IT', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function EventCard({ event, compact = false, onClick, isSelected }: EventCardProps) {
  const isMeet = Boolean(event.hangoutLink);

  if (compact) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClick?.(event);
        }}
        className={cn(
          'w-full text-left text-xs px-1.5 py-0.5 rounded truncate cursor-pointer transition-colors',
          isMeet
            ? 'bg-[#34D399]/20 text-[#34D399] hover:bg-[#34D399]/30'
            : 'bg-[#d4845a]/20 text-[#d4845a] hover:bg-[#d4845a]/30',
          isSelected && 'ring-1 ring-current'
        )}
        aria-label={`Evento: ${event.summary} alle ${formatTime(event.start)}`}
      >
        {formatTime(event.start)} {event.summary}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onClick?.(event)}
      className={cn(
        'w-full text-left p-3 border border-white/5 rounded-lg cursor-pointer transition-colors',
        'hover:bg-white/5',
        isSelected && 'bg-[#d4845a]/10 border-l-2 border-l-[#d4845a]'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div
            className={cn(
              'font-medium text-sm truncate',
              isMeet ? 'text-[#34D399]' : 'text-[#E6E7EB]'
            )}
          >
            {event.summary}
          </div>
          <div className="text-xs text-[#9AA0AE] mt-0.5">
            {formatTime(event.start)} – {formatTime(event.end)}
          </div>
        </div>
        {isMeet && (
          <span className="shrink-0 px-1.5 py-0.5 rounded-full bg-[#34D399]/20 text-[#34D399] text-[10px] font-medium">
            Meet
          </span>
        )}
      </div>
    </button>
  );
}
