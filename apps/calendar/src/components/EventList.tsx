'use client';

import React from 'react';
import { Calendar as CalendarIcon, RefreshCw } from 'lucide-react';
import { EventCard } from './EventCard';
import type { CalendarEvent } from './types';

interface EventListProps {
  events: CalendarEvent[];
  selectedEvent: CalendarEvent | null;
  loading: boolean;
  onEventClick: (event: CalendarEvent) => void;
}

export function EventList({ events, selectedEvent, loading, onEventClick }: EventListProps) {
  if (loading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-center justify-center h-full text-[#9AA0AE]"
      >
        <RefreshCw className="h-5 w-5 animate-spin mr-2" aria-hidden="true" />
        <span>Caricamento...</span>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-[#9AA0AE]">
        <CalendarIcon className="h-16 w-16 mb-4 opacity-20" aria-hidden="true" />
        <p>Nessun evento programmato</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-white/5" role="list" aria-label="Lista eventi">
      {events.map((event) => (
        <div key={event.id} role="listitem" className="px-6 py-2">
          <EventCard
            event={event}
            isSelected={selectedEvent?.id === event.id}
            onClick={onEventClick}
          />
        </div>
      ))}
    </div>
  );
}
