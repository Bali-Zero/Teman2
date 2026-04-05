'use client';

import React, { useMemo } from 'react';
import { Calendar as CalendarIcon, Clock } from 'lucide-react';
import type { CalendarEvent } from './types';

interface UpcomingEventsProps {
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
  maxItems?: number;
}

function formatDateShort(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
}

export function UpcomingEvents({ events, onEventClick, maxItems = 10 }: UpcomingEventsProps) {
  const upcoming = useMemo(() => {
    const now = new Date();
    return events
      .filter((e) => new Date(e.start) >= now)
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
      .slice(0, maxItems);
  }, [events, maxItems]);

  return (
    <div className="flex-1 overflow-auto p-6">
      <h3 className="font-semibold text-[#E6E7EB] mb-4">Prossimi Eventi</h3>
      {upcoming.length === 0 ? (
        <div className="text-center text-[#9AA0AE] py-8">
          <CalendarIcon className="h-12 w-12 mx-auto mb-3 opacity-20" aria-hidden="true" />
          <p className="text-sm">Nessun evento in programma</p>
        </div>
      ) : (
        <div className="space-y-2" role="list" aria-label="Prossimi eventi">
          {upcoming.map((event) => (
            <button
              key={event.id}
              type="button"
              role="listitem"
              onClick={() => onEventClick(event)}
              className="w-full text-left p-3 border border-white/5 rounded-lg cursor-pointer hover:bg-white/5 transition-colors"
            >
              <div
                className="font-medium text-sm text-[#E6E7EB] truncate"
                title={event.summary}
              >
                {event.summary}
              </div>
              <div className="text-xs text-[#9AA0AE] mt-1 flex items-center gap-1.5">
                <Clock className="h-3 w-3 shrink-0" aria-hidden="true" />
                <span>
                  {formatDateShort(event.start)} {formatTime(event.start)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
