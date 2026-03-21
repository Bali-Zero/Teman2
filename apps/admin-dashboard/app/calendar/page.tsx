"use client";

import { useState, useEffect, useMemo } from "react";
import { error as logError } from "@/lib/logger";
import { Badge, Button, Card, CardContent } from "@/components/ui/primitives";
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
} from "lucide-react";
import { cn } from "@/lib/utils";

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

const TEAM_CALENDAR_ID =
  "ec0863e7c14ac6bf414ec23e2aab81960ecb26823c6a8f397c664fc64901d617@group.calendar.google.com";

const WEEKDAYS = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"];
const WEEKDAYS_FULL = [
  "Domenica",
  "Lunedì",
  "Martedì",
  "Mercoledì",
  "Giovedì",
  "Venerdì",
  "Sabato",
];

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [calendars, setCalendars] = useState<CalendarInfo[]>([]);
  const [selectedCalendar, setSelectedCalendar] = useState(TEAM_CALENDAR_ID);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(
    null,
  );
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [currentMonth, setCurrentMonth] = useState<Date | null>(null);
  const [view, setView] = useState<"month" | "list">("month");
  const [isMounted, setIsMounted] = useState(false);

  // Fix hydration mismatch - set date only on client
  useEffect(() => {
    setCurrentMonth(new Date());
    setIsMounted(true);
  }, []);

  const [newEvent, setNewEvent] = useState({
    summary: "",
    from: "",
    to: "",
    description: "",
    location: "",
    attendees: "",
    withMeet: false,
  });

  useEffect(() => {
    fetchCalendars();
    fetchEvents();
  }, [selectedCalendar]);

  const fetchCalendars = async () => {
    try {
      const res = await fetch("/api/calendar/calendars");
      const data = await res.json();
      if (data.success) {
        setCalendars(data.calendars || []);
      }
    } catch (err) {
      logError("Failed to fetch calendars:", err);
    }
  };

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/calendar/events?calendarId=${encodeURIComponent(selectedCalendar)}&days=90`,
      );
      const data = await res.json();
      if (data.success) {
        setEvents(data.events || []);
      } else {
        setError(data.error);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const createEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/calendar/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...newEvent, calendarId: selectedCalendar }),
      });
      const data = await res.json();
      if (data.success) {
        setShowCreateForm(false);
        setNewEvent({
          summary: "",
          from: "",
          to: "",
          description: "",
          location: "",
          attendees: "",
          withMeet: false,
        });
        fetchEvents();
      } else {
        alert("Errore: " + data.error);
      }
    } catch (err: any) {
      alert("Errore: " + err.message);
    }
  };

  const deleteEvent = async (eventId: string) => {
    if (!confirm("Eliminare questo evento?")) return;
    try {
      const res = await fetch(
        `/api/calendar/events?eventId=${eventId}&calendarId=${encodeURIComponent(selectedCalendar)}`,
        {
          method: "DELETE",
        },
      );
      const data = await res.json();
      if (data.success) {
        setSelectedEvent(null);
        fetchEvents();
      }
    } catch (err: any) {
      alert("Errore: " + err.message);
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

    // Previous month padding
    const startPadding = firstDay.getDay();
    for (let i = startPadding - 1; i >= 0; i--) {
      days.push(new Date(year, month, -i));
    }

    // Current month
    for (let i = 1; i <= lastDay.getDate(); i++) {
      days.push(new Date(year, month, i));
    }

    // Next month padding (fill to 42 = 6 weeks)
    while (days.length < 42) {
      days.push(
        new Date(
          year,
          month + 1,
          days.length - lastDay.getDate() - startPadding + 1,
        ),
      );
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

  const isToday = (date: Date) =>
    date.toDateString() === new Date().toDateString();
  const isCurrentMonth = (date: Date) =>
    currentMonth ? date.getMonth() === currentMonth.getMonth() : false;
  const isSelected = (date: Date) =>
    selectedDate?.toDateString() === date.toDateString();

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString("it-IT", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDateShort = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("it-IT", {
      day: "numeric",
      month: "short",
    });
  };

  const formatDateFull = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("it-IT", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
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

  // Show loading state until client hydration complete
  if (!isMounted || !currentMonth) {
    return (
      <div className="h-screen flex items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <header className="border-b bg-background px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Calendario</h1>
              <p className="text-sm text-muted-foreground">
                {calendars.find((c) => c.id === selectedCalendar)?.name ||
                  "Bali Zero Calendar"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Calendar selector */}
            <select
              value={selectedCalendar}
              onChange={(e) => setSelectedCalendar(e.target.value)}
              className="bg-background border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
            >
              {calendars.map((cal) => (
                <option key={cal.id} value={cal.id}>
                  {cal.name}
                </option>
              ))}
            </select>

            {/* View toggle */}
            <div className="flex border rounded-md overflow-hidden">
              <button
                onClick={() => setView("month")}
                className={cn(
                  "px-3 py-2 text-sm transition-colors",
                  view === "month"
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted",
                )}
              >
                <Grid3X3 className="h-4 w-4" />
              </button>
              <button
                onClick={() => setView("list")}
                className={cn(
                  "px-3 py-2 text-sm transition-colors",
                  view === "list"
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted",
                )}
              >
                <List className="h-4 w-4" />
              </button>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={fetchEvents}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </Button>

            <Button size="sm" onClick={() => setShowCreateForm(true)}>
              <Plus className="h-4 w-4 mr-2" /> Nuovo
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Main Calendar Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Month Navigation */}
          <div className="px-6 py-3 border-b bg-muted/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setCurrentMonth(
                    new Date(
                      currentMonth.getFullYear(),
                      currentMonth.getMonth() - 1,
                      1,
                    ),
                  )
                }
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setCurrentMonth(
                    new Date(
                      currentMonth.getFullYear(),
                      currentMonth.getMonth() + 1,
                      1,
                    ),
                  )
                }
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={goToToday}>
                Oggi
              </Button>
            </div>

            <h2 className="text-lg font-semibold capitalize">
              {currentMonth.toLocaleDateString("it-IT", {
                month: "long",
                year: "numeric",
              })}
            </h2>

            <div className="text-sm text-muted-foreground">
              {events.length} eventi
            </div>
          </div>

          {/* Calendar Grid or List */}
          {view === "month" ? (
            <div className="flex-1 overflow-auto p-4">
              {/* Weekday headers */}
              <div className="grid grid-cols-7 mb-2">
                {WEEKDAYS.map((day, i) => (
                  <div
                    key={day}
                    className={cn(
                      "text-center text-xs font-medium py-2",
                      i === 0 && "text-red-500",
                      i !== 0 && "text-muted-foreground",
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
                        "min-h-[100px] p-2 border rounded-lg cursor-pointer transition-all",
                        isInMonth ? "bg-background" : "bg-muted/30",
                        isToday(date) && "ring-2 ring-primary",
                        isSelected(date) && "bg-primary/10 border-primary",
                        !isInMonth && "opacity-50",
                        "hover:border-primary/50",
                      )}
                    >
                      <div
                        className={cn(
                          "text-sm font-medium mb-1",
                          isToday(date) && "text-primary",
                          date.getDay() === 0 && "text-red-500",
                        )}
                      >
                        {date.getDate()}
                      </div>

                      <div className="space-y-1">
                        {dayEvents.slice(0, 3).map((event) => (
                          <div
                            key={event.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedEvent(event);
                            }}
                            className={cn(
                              "text-xs px-1.5 py-0.5 rounded truncate cursor-pointer",
                              "bg-primary/20 text-primary hover:bg-primary/30",
                              event.hangoutLink &&
                                "bg-green-500/20 text-green-700",
                            )}
                          >
                            {formatTime(event.start)} {event.summary}
                          </div>
                        ))}
                        {dayEvents.length > 3 && (
                          <div className="text-xs text-muted-foreground px-1">
                            +{dayEvents.length - 3} altri
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
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <RefreshCw className="h-5 w-5 animate-spin mr-2" />{" "}
                  Caricamento...
                </div>
              ) : events.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                  <CalendarIcon className="h-16 w-16 mb-4 opacity-20" />
                  <p>Nessun evento programmato</p>
                </div>
              ) : (
                <div className="divide-y">
                  {events.map((event) => (
                    <div
                      key={event.id}
                      onClick={() => setSelectedEvent(event)}
                      className={cn(
                        "px-6 py-4 cursor-pointer hover:bg-muted/50 transition-colors",
                        selectedEvent?.id === event.id &&
                          "bg-primary/5 border-l-4 border-l-primary",
                      )}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-medium">{event.summary}</div>
                          <div className="text-sm text-muted-foreground flex items-center gap-4 mt-1">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatDateShort(event.start)}{" "}
                              {formatTime(event.start)}
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
                          <Badge variant="secondary" className="text-xs">
                            <Video className="h-3 w-3 mr-1" /> Meet
                          </Badge>
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
        <div className="w-96 border-l bg-muted/10 flex flex-col overflow-hidden">
          {showCreateForm ? (
            <div className="flex-1 overflow-auto p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold">Nuovo Evento</h3>
                <button
                  onClick={() => setShowCreateForm(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <form onSubmit={createEvent} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Titolo
                  </label>
                  <input
                    type="text"
                    required
                    value={newEvent.summary}
                    onChange={(e) =>
                      setNewEvent({ ...newEvent, summary: e.target.value })
                    }
                    className="w-full bg-background border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    placeholder="Aggiungi titolo"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Inizio
                    </label>
                    <input
                      type="datetime-local"
                      required
                      value={newEvent.from}
                      onChange={(e) =>
                        setNewEvent({ ...newEvent, from: e.target.value })
                      }
                      className="w-full bg-background border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Fine
                    </label>
                    <input
                      type="datetime-local"
                      required
                      value={newEvent.to}
                      onChange={(e) =>
                        setNewEvent({ ...newEvent, to: e.target.value })
                      }
                      className="w-full bg-background border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Luogo
                  </label>
                  <input
                    type="text"
                    value={newEvent.location}
                    onChange={(e) =>
                      setNewEvent({ ...newEvent, location: e.target.value })
                    }
                    className="w-full bg-background border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    placeholder="Aggiungi luogo"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Descrizione
                  </label>
                  <textarea
                    value={newEvent.description}
                    onChange={(e) =>
                      setNewEvent({ ...newEvent, description: e.target.value })
                    }
                    className="w-full bg-background border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none resize-none"
                    rows={3}
                    placeholder="Aggiungi descrizione"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Partecipanti
                  </label>
                  <input
                    type="text"
                    value={newEvent.attendees}
                    onChange={(e) =>
                      setNewEvent({ ...newEvent, attendees: e.target.value })
                    }
                    className="w-full bg-background border rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                    placeholder="email@esempio.com, altro@esempio.com"
                  />
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newEvent.withMeet}
                    onChange={(e) =>
                      setNewEvent({ ...newEvent, withMeet: e.target.checked })
                    }
                    className="w-4 h-4 rounded"
                  />
                  <Video className="h-4 w-4 text-green-600" />
                  <span className="text-sm">Aggiungi Google Meet</span>
                </label>

                <div className="flex gap-2 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1"
                    onClick={() => setShowCreateForm(false)}
                  >
                    Annulla
                  </Button>
                  <Button type="submit" className="flex-1">
                    Salva
                  </Button>
                </div>
              </form>
            </div>
          ) : selectedEvent ? (
            <div className="flex-1 overflow-auto">
              <div className="p-6 border-b">
                <div className="flex items-start justify-between mb-4">
                  <h3 className="text-xl font-semibold pr-4">
                    {selectedEvent.summary}
                  </h3>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:bg-destructive/10"
                      onClick={() => deleteEvent(selectedEvent.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    <button
                      onClick={() => setSelectedEvent(null)}
                      className="p-2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="space-y-3 text-sm">
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <div>
                      <div className="font-medium text-foreground">
                        {formatTime(selectedEvent.start)} -{" "}
                        {formatTime(selectedEvent.end)}
                      </div>
                      <div className="capitalize">
                        {formatDateFull(selectedEvent.start)}
                      </div>
                    </div>
                  </div>

                  {selectedEvent.location && (
                    <div className="flex items-center gap-3 text-muted-foreground">
                      <MapPin className="h-4 w-4" />
                      <span>{selectedEvent.location}</span>
                    </div>
                  )}
                </div>
              </div>

              {selectedEvent.hangoutLink && (
                <div className="p-4 border-b bg-green-500/5">
                  <a
                    href={selectedEvent.hangoutLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 text-green-700 hover:text-green-800 font-medium"
                  >
                    <Video className="h-5 w-5" />
                    Partecipa con Google Meet
                    <ExternalLink className="h-3 w-3 ml-auto" />
                  </a>
                </div>
              )}

              {selectedEvent.description && (
                <div className="p-6 border-b">
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">
                    Descrizione
                  </h4>
                  <p className="text-sm whitespace-pre-wrap">
                    {selectedEvent.description}
                  </p>
                </div>
              )}

              {selectedEvent.attendees &&
                selectedEvent.attendees.length > 0 && (
                  <div className="p-6 border-b">
                    <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                      <Users className="h-4 w-4" />
                      Partecipanti ({selectedEvent.attendees.length})
                    </h4>
                    <div className="space-y-2">
                      {selectedEvent.attendees.map((email, i) => (
                        <div
                          key={i}
                          className="text-sm flex items-center gap-2"
                        >
                          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium text-primary">
                            {email[0].toUpperCase()}
                          </div>
                          {email}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              <div className="p-6">
                <div className="text-xs text-muted-foreground font-mono">
                  ID: {selectedEvent.id}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-auto p-6">
              <h3 className="font-semibold mb-4">Prossimi Eventi</h3>
              {upcomingEvents.length === 0 ? (
                <div className="text-center text-muted-foreground py-8">
                  <CalendarIcon className="h-12 w-12 mx-auto mb-3 opacity-20" />
                  <p className="text-sm">Nessun evento in programma</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {upcomingEvents.map((event) => (
                    <div
                      key={event.id}
                      onClick={() => setSelectedEvent(event)}
                      className="p-3 border rounded-lg cursor-pointer hover:bg-muted/50 transition-colors"
                    >
                      <div className="font-medium text-sm">{event.summary}</div>
                      <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
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
  );
}
