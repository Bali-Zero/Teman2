'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Calendar as CalendarIcon,
  Plus,
  RefreshCw,
  Clock,
  MapPin,
  Users,
  Video,
  Trash2,
  ChevronLeft,
  ChevronRight,
  List,
  Grid3X3,
  ExternalLink,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface CalendarEvent {
  id: string;
  summary: string;
  start: string;
  end: string;
  description?: string;
  location?: string;
  attendees?: string[];
  hangoutLink?: string;
}

interface CalendarInfo {
  id: string;
  name: string;
  role: string;
}

const WEEKDAYS = ['Dom', 'Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab'];

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

  const [newEvent, setNewEvent] = useState({
    summary: '',
    from: '',
    to: '',
    description: '',
    location: '',
    attendees: '',
    withMeet: false,
  });

  // Escape key handler for sidebar/form
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showCreateForm) {
          setShowCreateForm(false);
        } else if (selectedEvent) {
          setSelectedEvent(null);
        }
      }
    },
    [showCreateForm, selectedEvent]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Fix hydration - set date only on client
  useEffect(() => {
    setCurrentMonth(new Date());
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (isMounted) {
      fetchCalendars();
      fetchEvents();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCalendar, isMounted]);

  const fetchCalendars = async () => {
    try {
      const res = await fetch('/api/calendar/calendars');
      const data = await res.json();
      if (data.success) {
        setCalendars(data.calendars || []);
      }
    } catch {
      // Silent fail - calendars will be empty
    }
  };

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/calendar/events?calendarId=${encodeURIComponent(selectedCalendar)}&days=90`
      );
      const data = await res.json();
      if (data.success) {
        setEvents(data.events || []);
      } else {
        setError(data.error);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const createEvent = async (e: React.FormEvent) => {
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
        setNewEvent({
          summary: '',
          from: '',
          to: '',
          description: '',
          location: '',
          attendees: '',
          withMeet: false,
        });
        fetchEvents();
      } else {
        alert('Errore: ' + data.error);
      }
    } catch (err: unknown) {
      alert('Errore: ' + (err instanceof Error ? err.message : 'Unknown error'));
    } finally {
      setCreating(false);
    }
  };

  const deleteEvent = async (eventId: string) => {
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
      alert('Errore: ' + (err instanceof Error ? err.message : 'Unknown error'));
    }
  };

  // Calendar grid logic
  const calendarDays = useMemo(() => {
    if (!currentMonth) return [];
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const days: Date[] = [];

    const startPadding = firstDay.getDay();
    for (let i = startPadding - 1; i >= 0; i--) {
      days.push(new Date(year, month, -i));
    }

    for (let i = 1; i <= lastDay.getDate(); i++) {
      days.push(new Date(year, month, i));
    }

    while (days.length < 42) {
      days.push(new Date(year, month + 1, days.length - lastDay.getDate() - startPadding + 1));
    }

    return days;
  }, [currentMonth]);

  const getEventsForDate = (date: Date) => {
    return events.filter((event) => {
      const eventDate = new Date(event.start);
      return eventDate.toDateString() === date.toDateString();
    });
  };

  const upcomingEvents = useMemo(() => {
    const now = new Date();
    return events
      .filter((e) => new Date(e.start) >= now)
      .sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
      .slice(0, 10);
  }, [events]);

  const isToday = (date: Date) => date.toDateString() === new Date().toDateString();
  const isCurrentMonth = (date: Date) =>
    currentMonth ? date.getMonth() === currentMonth.getMonth() : false;
  const isSelected = (date: Date) => selectedDate?.toDateString() === date.toDateString();

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString('it-IT', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDateShort = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('it-IT', {
      day: 'numeric',
      month: 'short',
    });
  };

  const formatDateFull = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('it-IT', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  const goToToday = () => setCurrentMonth(new Date());

  const handleDateClick = (date: Date) => {
    setSelectedDate(date);
    setSelectedEvent(null);
    const dayEvents = getEventsForDate(date);
    if (dayEvents.length === 1) {
      setSelectedEvent(dayEvents[0]);
    }
  };

  if (!isMounted || !currentMonth) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0c0c0e]">
        <RefreshCw className="h-8 w-8 animate-spin text-[#9AA0AE]" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-[#0c0c0e] overflow-hidden">
      {/* Calendar Area */}
      <div className="flex-1 flex flex-col overflow-hidden rounded-none">
        {/* Header */}
        <header className="border-b border-white/5 bg-[#1A1D24] px-6 py-4 shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-[#E6E7EB]">Bali Zero Calendar</h1>
              <p className="text-sm text-[#9AA0AE]">
                {calendars.find((c) => c.id === selectedCalendar)?.name || 'Team Calendar'}
              </p>
            </div>

            <div className="flex items-center gap-3">
              {/* Calendar selector */}
              <select
                value={selectedCalendar}
                onChange={(e) => setSelectedCalendar(e.target.value)}
                className="bg-[#1A1D24] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none"
                aria-label="Seleziona calendario"
              >
                {calendars.map((cal) => (
                  <option key={cal.id} value={cal.id}>
                    {cal.name}
                  </option>
                ))}
              </select>

              {/* View toggle */}
              <div className="flex border border-white/10 rounded-lg overflow-hidden">
                <button
                  onClick={() => setView('month')}
                  className={cn(
                    'px-3 py-2 text-sm transition-colors',
                    view === 'month' ? 'bg-[#d4845a] text-white' : 'text-[#9AA0AE] hover:bg-white/5'
                  )}
                  aria-label="Vista mese"
                >
                  <Grid3X3 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setView('list')}
                  className={cn(
                    'px-3 py-2 text-sm transition-colors',
                    view === 'list' ? 'bg-[#d4845a] text-white' : 'text-[#9AA0AE] hover:bg-white/5'
                  )}
                  aria-label="Vista lista"
                >
                  <List className="h-4 w-4" />
                </button>
              </div>

              <button
                onClick={fetchEvents}
                disabled={loading}
                className="p-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5 disabled:opacity-50"
                aria-label="Aggiorna eventi"
              >
                <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
              </button>

              <button
                onClick={() => setShowCreateForm(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#d4845a] text-white hover:bg-[#bf7350] transition-colors"
              >
                <Plus className="h-4 w-4" /> Nuovo
              </button>
            </div>
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Main Calendar Area */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Month Navigation */}
            <div className="px-6 py-3 border-b border-white/5 bg-[#1A1D24]/50 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    setCurrentMonth(
                      new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1)
                    )
                  }
                  className="p-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5"
                  aria-label="Mese precedente"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() =>
                    setCurrentMonth(
                      new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1)
                    )
                  }
                  className="p-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5"
                  aria-label="Mese successivo"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <button
                  onClick={goToToday}
                  className="px-3 py-2 rounded-lg text-sm text-[#9AA0AE] hover:bg-white/5"
                >
                  Oggi
                </button>
              </div>

              <h2 className="text-lg font-semibold capitalize text-[#E6E7EB]">
                {currentMonth.toLocaleDateString('it-IT', {
                  month: 'long',
                  year: 'numeric',
                })}
              </h2>

              <div className="text-sm text-[#9AA0AE]">{events.length} eventi</div>
            </div>

            {/* Calendar Grid or List */}
            {view === 'month' ? (
              <div className="flex-1 overflow-auto p-4">
                {/* Weekday headers */}
                <div className="grid grid-cols-7 mb-2">
                  {WEEKDAYS.map((day, i) => (
                    <div
                      key={day}
                      className={cn(
                        'text-center text-xs font-medium py-2',
                        i === 0 && 'text-[#d4845a]',
                        i !== 0 && 'text-[#9AA0AE]'
                      )}
                    >
                      {day}
                    </div>
                  ))}
                </div>

                {/* Calendar grid */}
                <div className="grid grid-cols-7 gap-1">
                  {calendarDays.map((date, i) => {
                    const dayEvents = getEventsForDate(date);
                    const isInMonth = isCurrentMonth(date);

                    return (
                      <div
                        key={i}
                        onClick={() => handleDateClick(date)}
                        className={cn(
                          'min-h-[90px] p-2 border border-white/5 rounded-lg cursor-pointer transition-all',
                          isInMonth ? 'bg-[#1A1D24]' : 'bg-[#1A1D24]/30',
                          isToday(date) && 'ring-2 ring-[#d4845a]',
                          isSelected(date) && 'bg-[#d4845a]/10 border-[#d4845a]/50',
                          !isInMonth && 'opacity-40',
                          'hover:border-[#d4845a]/30'
                        )}
                      >
                        <div
                          className={cn(
                            'text-sm font-medium mb-1',
                            isToday(date) && 'text-[#d4845a]',
                            !isToday(date) && isInMonth && 'text-[#E6E7EB]',
                            date.getDay() === 0 && 'text-[#d4845a]'
                          )}
                        >
                          {date.getDate()}
                        </div>

                        <div className="space-y-1">
                          {dayEvents.slice(0, 2).map((event) => (
                            <div
                              key={event.id}
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedEvent(event);
                              }}
                              className={cn(
                                'text-xs px-1.5 py-0.5 rounded truncate cursor-pointer',
                                'bg-[#d4845a]/20 text-[#d4845a] hover:bg-[#d4845a]/30',
                                event.hangoutLink && 'bg-[#34D399]/20 text-[#34D399]'
                              )}
                            >
                              {formatTime(event.start)} {event.summary}
                            </div>
                          ))}
                          {dayEvents.length > 2 && (
                            <div className="text-xs text-[#9AA0AE] px-1">
                              +{dayEvents.length - 2} altri
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              /* List View */
              <div className="flex-1 overflow-auto">
                {loading ? (
                  <div className="flex items-center justify-center h-full text-[#9AA0AE]">
                    <RefreshCw className="h-5 w-5 animate-spin mr-2" />
                    Caricamento...
                  </div>
                ) : events.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-[#9AA0AE]">
                    <CalendarIcon className="h-16 w-16 mb-4 opacity-20" />
                    <p>Nessun evento programmato</p>
                  </div>
                ) : (
                  <div className="divide-y divide-white/5">
                    {events.map((event) => (
                      <div
                        key={event.id}
                        onClick={() => setSelectedEvent(event)}
                        className={cn(
                          'px-6 py-4 cursor-pointer hover:bg-white/5 transition-colors',
                          selectedEvent?.id === event.id &&
                            'bg-[#d4845a]/10 border-l-2 border-l-[#d4845a]'
                        )}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="font-medium text-[#E6E7EB]">{event.summary}</div>
                            <div className="text-sm text-[#9AA0AE] flex items-center gap-4 mt-1">
                              <span className="flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {formatDateShort(event.start)} {formatTime(event.start)}
                              </span>
                              {event.location && (
                                <span className="flex items-center gap-1">
                                  <MapPin className="h-3 w-3" />
                                  {event.location}
                                </span>
                              )}
                            </div>
                          </div>
                          {event.hangoutLink && (
                            <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-[#34D399]/20 text-[#34D399] text-xs">
                              <Video className="h-3 w-3" /> Meet
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Sidebar - Event Details */}
          <div className="w-80 border-l border-white/5 bg-[#1A1D24]/50 flex flex-col overflow-hidden">
            {showCreateForm ? (
              <div className="flex-1 overflow-auto p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="font-semibold text-[#E6E7EB]">Nuovo Evento</h3>
                  <button
                    onClick={() => setShowCreateForm(false)}
                    className="text-[#9AA0AE] hover:text-[#E6E7EB]"
                    aria-label="Chiudi modulo creazione evento"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                <form onSubmit={createEvent} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-[#9AA0AE] mb-1.5">
                      Titolo
                    </label>
                    <input
                      type="text"
                      required
                      value={newEvent.summary}
                      onChange={(e) => setNewEvent({ ...newEvent, summary: e.target.value })}
                      className="w-full bg-[#242424] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none"
                      placeholder="Aggiungi titolo"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-[#9AA0AE] mb-1.5">
                        Inizio
                      </label>
                      <input
                        type="datetime-local"
                        required
                        value={newEvent.from}
                        onChange={(e) => setNewEvent({ ...newEvent, from: e.target.value })}
                        className="w-full bg-[#242424] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-[#9AA0AE] mb-1.5">
                        Fine
                      </label>
                      <input
                        type="datetime-local"
                        required
                        value={newEvent.to}
                        onChange={(e) => setNewEvent({ ...newEvent, to: e.target.value })}
                        className="w-full bg-[#242424] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-[#9AA0AE] mb-1.5">Luogo</label>
                    <input
                      type="text"
                      value={newEvent.location}
                      onChange={(e) => setNewEvent({ ...newEvent, location: e.target.value })}
                      className="w-full bg-[#242424] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none"
                      placeholder="Aggiungi luogo"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-[#9AA0AE] mb-1.5">
                      Descrizione
                    </label>
                    <textarea
                      value={newEvent.description}
                      onChange={(e) =>
                        setNewEvent({
                          ...newEvent,
                          description: e.target.value,
                        })
                      }
                      className="w-full bg-[#242424] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none resize-none"
                      rows={3}
                      placeholder="Aggiungi descrizione"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-[#9AA0AE] mb-1.5">
                      Partecipanti
                    </label>
                    <input
                      type="text"
                      value={newEvent.attendees}
                      onChange={(e) =>
                        setNewEvent({
                          ...newEvent,
                          attendees: e.target.value,
                        })
                      }
                      className="w-full bg-[#242424] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none"
                      placeholder="email1@example.com, email2@example.com"
                      aria-label="Partecipanti (separati da virgola)"
                    />
                  </div>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newEvent.withMeet}
                      onChange={(e) => setNewEvent({ ...newEvent, withMeet: e.target.checked })}
                      className="w-4 h-4 rounded bg-[#242424] border-white/10"
                    />
                    <Video className="h-4 w-4 text-[#34D399]" />
                    <span className="text-sm text-[#9AA0AE]">Aggiungi Google Meet</span>
                  </label>

                  <div className="flex gap-2 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowCreateForm(false)}
                      className="flex-1 px-4 py-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5"
                    >
                      Annulla
                    </button>
                    <button
                      type="submit"
                      disabled={creating}
                      className="flex-1 px-4 py-2 rounded-lg bg-[#d4845a] text-white hover:bg-[#bf7350] disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2"
                    >
                      {creating && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                      {creating ? 'Salvataggio...' : 'Salva'}
                    </button>
                  </div>
                </form>
              </div>
            ) : selectedEvent ? (
              <div className="flex-1 overflow-auto">
                <div className="p-6 border-b border-white/5">
                  <div className="flex items-start justify-between mb-4">
                    <h3 className="text-lg font-semibold text-[#E6E7EB] pr-4">
                      {selectedEvent.summary}
                    </h3>
                    <div className="flex gap-1">
                      <button
                        onClick={() => deleteEvent(selectedEvent.id)}
                        className="p-2 rounded-lg text-[#d4845a] hover:bg-[#d4845a]/10"
                        aria-label="Elimina evento"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setSelectedEvent(null)}
                        className="p-2 text-[#9AA0AE] hover:text-[#E6E7EB]"
                        aria-label="Chiudi dettaglio evento"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-3 text-sm">
                    <div className="flex items-center gap-3 text-[#9AA0AE]">
                      <Clock className="h-4 w-4" />
                      <div>
                        <div className="font-medium text-[#E6E7EB]">
                          {formatTime(selectedEvent.start)} - {formatTime(selectedEvent.end)}
                        </div>
                        <div className="capitalize">{formatDateFull(selectedEvent.start)}</div>
                      </div>
                    </div>

                    {selectedEvent.location && (
                      <div className="flex items-center gap-3 text-[#9AA0AE]">
                        <MapPin className="h-4 w-4" />
                        <span>{selectedEvent.location}</span>
                      </div>
                    )}
                  </div>
                </div>

                {selectedEvent.hangoutLink && (
                  <div className="p-4 border-b border-white/5 bg-[#34D399]/5">
                    <a
                      href={selectedEvent.hangoutLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-3 text-[#34D399] hover:text-[#10B981] font-medium"
                    >
                      <Video className="h-5 w-5" />
                      Partecipa con Google Meet
                      <ExternalLink className="h-3 w-3 ml-auto" />
                    </a>
                  </div>
                )}

                {selectedEvent.description && (
                  <div className="p-6 border-b border-white/5">
                    <h4 className="text-sm font-medium text-[#9AA0AE] mb-2">Descrizione</h4>
                    <p className="text-sm text-[#E6E7EB] whitespace-pre-wrap">
                      {selectedEvent.description}
                    </p>
                  </div>
                )}

                {selectedEvent.attendees && selectedEvent.attendees.length > 0 && (
                  <div className="p-6 border-b border-white/5">
                    <h4 className="text-sm font-medium text-[#9AA0AE] mb-3 flex items-center gap-2">
                      <Users className="h-4 w-4" />
                      Partecipanti ({selectedEvent.attendees.length})
                    </h4>
                    <div className="space-y-2">
                      {selectedEvent.attendees.map((email, i) => (
                        <div key={i} className="text-sm flex items-center gap-2 text-[#E6E7EB]">
                          <div className="w-8 h-8 rounded-full bg-[#d4845a]/20 flex items-center justify-center text-xs font-medium text-[#d4845a]">
                            {email[0].toUpperCase()}
                          </div>
                          {email}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="p-6">
                  <div className="text-xs text-[#9AA0AE] font-mono">ID: {selectedEvent.id}</div>
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-auto p-6">
                <h3 className="font-semibold text-[#E6E7EB] mb-4">Prossimi Eventi</h3>
                {upcomingEvents.length === 0 ? (
                  <div className="text-center text-[#9AA0AE] py-8">
                    <CalendarIcon className="h-12 w-12 mx-auto mb-3 opacity-20" />
                    <p className="text-sm">Nessun evento in programma</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {upcomingEvents.map((event) => (
                      <div
                        key={event.id}
                        onClick={() => setSelectedEvent(event)}
                        className="p-3 border border-white/5 rounded-lg cursor-pointer hover:bg-white/5 transition-colors"
                      >
                        <div className="font-medium text-sm text-[#E6E7EB]">{event.summary}</div>
                        <div className="text-xs text-[#9AA0AE] mt-1 flex items-center gap-2">
                          <Clock className="h-3 w-3" />
                          {formatDateShort(event.start)} {formatTime(event.start)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          role="alert"
          className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-red-900/80 text-red-200 px-4 py-2 rounded-lg text-sm backdrop-blur-sm border border-red-700/50"
        >
          {error}
        </div>
      )}
    </div>
  );
}
