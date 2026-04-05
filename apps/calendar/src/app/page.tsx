'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Calendar as CalendarIcon, Clock, MapPin, Users, Video, Trash2, X, ExternalLink, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CalendarHeader } from '@/components/CalendarHeader';
import { CalendarGrid } from '@/components/CalendarGrid';
import { EventCreateForm, type NewEventData } from '@/components/EventCreateForm';
import { EventList } from '@/components/EventList';
import { UpcomingEvents } from '@/components/UpcomingEvents';
import { downloadIcal } from '@/components/ical';
import type { CalendarEvent, CalendarInfo } from '@/components/types';

const BLANK_EVENT: NewEventData = {
  summary: '',
  from: '',
  to: '',
  description: '',
  location: '',
  attendees: '',
  withMeet: false,
};

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
}

function formatDateFull(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('it-IT', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [calendars, setCalendars] = useState<CalendarInfo[]>([]);
  const [selectedCalendar, setSelectedCalendar] = useState(
    'ec0863e7c14ac6bf414ec23e2aab81960ecb26823c6a8f397c664fc64901d617@group.calendar.google.com'
  );
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [currentMonth, setCurrentMonth] = useState<Date | null>(null);
  const [view, setView] = useState<'month' | 'list'>('month');
  const [isMounted, setIsMounted] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newEvent, setNewEvent] = useState<NewEventData>(BLANK_EVENT);

  // Escape key handler
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showCreateForm) setShowCreateForm(false);
        else if (selectedEvent) setSelectedEvent(null);
      }
    },
    [showCreateForm, selectedEvent]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Hydration fix
  useEffect(() => {
    setCurrentMonth(new Date());
    setIsMounted(true);
  }, []);

  const fetchCalendars = useCallback(async () => {
    try {
      const res = await fetch('/api/calendar/calendars');
      const data = await res.json();
      if (data.success) setCalendars(data.calendars ?? []);
    } catch {
      // Silent fail
    }
  }, []);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/calendar/events?calendarId=${encodeURIComponent(selectedCalendar)}&days=90`
      );
      const data = await res.json();
      if (data.success) {
        setEvents(data.events ?? []);
      } else {
        setError(data.error);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [selectedCalendar]);

  useEffect(() => {
    if (isMounted) {
      fetchCalendars();
      fetchEvents();
    }
  }, [selectedCalendar, isMounted, fetchCalendars, fetchEvents]);

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    try {
      const res = await fetch('/api/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newEvent, calendarId: selectedCalendar }),
      });
      const data = await res.json();
      if (data.success) {
        setShowCreateForm(false);
        setNewEvent(BLANK_EVENT);
        fetchEvents();
      } else {
        setError(data.error ?? 'Errore nella creazione evento');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Errore nella creazione evento');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteEvent = async (eventId: string) => {
    if (!confirm('Eliminare questo evento?')) return;
    try {
      const res = await fetch(
        `/api/calendar/events?eventId=${eventId}&calendarId=${encodeURIComponent(selectedCalendar)}`,
        { method: 'DELETE' }
      );
      const data = await res.json();
      if (data.success) {
        setSelectedEvent(null);
        fetchEvents();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Errore nella cancellazione evento');
    }
  };

  const handleDateClick = (date: Date) => {
    setSelectedDate(date);
    setSelectedEvent(null);
    const dayEvents = events.filter(
      (event) => new Date(event.start).toDateString() === date.toDateString()
    );
    if (dayEvents.length === 1) setSelectedEvent(dayEvents[0]);
  };

  const handleExportIcal = () => {
    const calName =
      calendars.find((c) => c.id === selectedCalendar)?.name ?? 'Bali Zero Calendar';
    downloadIcal(events, `balizero-calendar-${new Date().toISOString().slice(0, 10)}.ics`);
  };

  if (!isMounted || !currentMonth) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0c0c0e]">
        <RefreshCw className="h-8 w-8 animate-spin text-[#9AA0AE]" aria-label="Caricamento..." />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-[#0c0c0e] overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header + Month nav */}
        <CalendarHeader
          currentMonth={currentMonth}
          calendars={calendars}
          selectedCalendar={selectedCalendar}
          view={view}
          loading={loading}
          eventCount={events.length}
          onPrevMonth={() =>
            setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1))
          }
          onNextMonth={() =>
            setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1))
          }
          onToday={() => setCurrentMonth(new Date())}
          onViewChange={setView}
          onCalendarChange={setSelectedCalendar}
          onRefresh={fetchEvents}
          onNewEvent={() => setShowCreateForm(true)}
          onExportIcal={handleExportIcal}
        />

        <div className="flex-1 flex overflow-hidden">
          {/* Main area */}
          <main className="flex-1 flex flex-col overflow-hidden">
            {view === 'month' ? (
              <CalendarGrid
                currentMonth={currentMonth}
                events={events}
                selectedDate={selectedDate}
                selectedEvent={selectedEvent}
                onDateClick={handleDateClick}
                onEventClick={setSelectedEvent}
              />
            ) : (
              <div className="flex-1 overflow-auto">
                <EventList
                  events={events}
                  selectedEvent={selectedEvent}
                  loading={loading}
                  onEventClick={setSelectedEvent}
                />
              </div>
            )}
          </main>

          {/* Right sidebar */}
          <aside
            aria-label="Dettagli evento"
            className="w-80 border-l border-white/5 bg-[#1A1D24]/50 flex flex-col overflow-hidden shrink-0"
          >
            {showCreateForm ? (
              <EventCreateForm
                value={newEvent}
                onChange={setNewEvent}
                onSubmit={handleCreateEvent}
                onCancel={() => setShowCreateForm(false)}
                creating={creating}
              />
            ) : selectedEvent ? (
              <EventDetail
                event={selectedEvent}
                onDelete={handleDeleteEvent}
                onClose={() => setSelectedEvent(null)}
              />
            ) : (
              <UpcomingEvents
                events={events}
                onEventClick={setSelectedEvent}
              />
            )}
          </aside>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-red-900/80 text-red-200 px-4 py-2 rounded-lg text-sm backdrop-blur-sm border border-red-700/50"
        >
          {error}
          <button
            type="button"
            onClick={() => setError(null)}
            className="ml-3 text-red-300 hover:text-red-100"
            aria-label="Chiudi errore"
          >
            <X className="h-4 w-4 inline" />
          </button>
        </div>
      )}
    </div>
  );
}

/** Inline event detail panel — kept in page.tsx as it's small and page-specific */
function EventDetail({
  event,
  onDelete,
  onClose,
}: {
  event: CalendarEvent;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 border-b border-white/5">
        <div className="flex items-start justify-between mb-4">
          <h3 className="text-lg font-semibold text-[#E6E7EB] pr-4">{event.summary}</h3>
          <div className="flex gap-1 shrink-0">
            <button
              type="button"
              onClick={() => onDelete(event.id)}
              className="p-2 rounded-lg text-[#d4845a] hover:bg-[#d4845a]/10 transition-colors"
              aria-label="Elimina evento"
            >
              <Trash2 className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-2 text-[#9AA0AE] hover:text-[#E6E7EB] transition-colors"
              aria-label="Chiudi dettaglio evento"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="space-y-3 text-sm">
          <div className="flex items-center gap-3 text-[#9AA0AE]">
            <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <div className="font-medium text-[#E6E7EB]">
                {new Date(event.start).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })} –{' '}
                {new Date(event.end).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}
              </div>
              <div className="capitalize">
                {new Date(event.start).toLocaleDateString('it-IT', {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                })}
              </div>
            </div>
          </div>

          {event.location && (
            <div className="flex items-center gap-3 text-[#9AA0AE]">
              <MapPin className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{event.location}</span>
            </div>
          )}
        </div>
      </div>

      {event.hangoutLink && (
        <div className="p-4 border-b border-white/5 bg-[#34D399]/5">
          <a
            href={event.hangoutLink}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 text-[#34D399] hover:text-[#10B981] font-medium transition-colors"
          >
            <Video className="h-5 w-5" aria-hidden="true" />
            Partecipa con Google Meet
            <ExternalLink className="h-3 w-3 ml-auto" aria-hidden="true" />
          </a>
        </div>
      )}

      {event.description && (
        <div className="p-6 border-b border-white/5">
          <h4 className="text-sm font-medium text-[#9AA0AE] mb-2">Descrizione</h4>
          <p className="text-sm text-[#E6E7EB] whitespace-pre-wrap">{event.description}</p>
        </div>
      )}

      {event.attendees && event.attendees.length > 0 && (
        <div className="p-6 border-b border-white/5">
          <h4 className="text-sm font-medium text-[#9AA0AE] mb-3 flex items-center gap-2">
            <Users className="h-4 w-4" aria-hidden="true" />
            Partecipanti ({event.attendees.length})
          </h4>
          <div className="space-y-2" role="list">
            {event.attendees.map((email, i) => (
              <div key={i} role="listitem" className="text-sm flex items-center gap-2 text-[#E6E7EB]">
                <div
                  className="w-8 h-8 rounded-full bg-[#d4845a]/20 flex items-center justify-center text-xs font-medium text-[#d4845a] shrink-0"
                  aria-hidden="true"
                >
                  {email[0].toUpperCase()}
                </div>
                <span className="truncate">{email}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="p-6">
        <div className="text-xs text-[#9AA0AE] font-mono">ID: {event.id}</div>
      </div>
    </div>
  );
}
