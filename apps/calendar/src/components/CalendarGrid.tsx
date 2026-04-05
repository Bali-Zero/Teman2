'use client';

import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { EventCard } from './EventCard';
import type { CalendarEvent } from './types';
import { WEEKDAYS } from './types';

interface CalendarGridProps {
  currentMonth: Date;
  events: CalendarEvent[];
  selectedDate: Date | null;
  selectedEvent: CalendarEvent | null;
  onDateClick: (date: Date) => void;
  onEventClick: (event: CalendarEvent) => void;
}

export function CalendarGrid({
  currentMonth,
  events,
  selectedDate,
  selectedEvent,
  onDateClick,
  onEventClick,
}: CalendarGridProps) {
  const calendarDays = useMemo<Date[]>(() => {
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

  const getEventsForDate = (date: Date): CalendarEvent[] =>
    events.filter(
      (event) => new Date(event.start).toDateString() === date.toDateString()
    );

  const isToday = (date: Date) => date.toDateString() === new Date().toDateString();
  const isCurrentMonth = (date: Date) => date.getMonth() === currentMonth.getMonth();
  const isSelected = (date: Date) => selectedDate?.toDateString() === date.toDateString();

  return (
    <div className="flex-1 overflow-auto p-4">
      {/* Weekday headers */}
      <div className="grid grid-cols-7 mb-2" role="row">
        {WEEKDAYS.map((day, i) => (
          <div
            key={day.short}
            role="columnheader"
            aria-label={day.full}
            className={cn(
              'text-center text-xs font-medium py-2',
              i === 0 ? 'text-[#d4845a]' : 'text-[#9AA0AE]'
            )}
          >
            <abbr title={day.full} className="no-underline">
              {day.short}
            </abbr>
          </div>
        ))}
      </div>

      {/* Calendar day grid */}
      <div className="grid grid-cols-7 gap-1" role="grid" aria-label="Calendario mensile">
        {calendarDays.map((date, i) => {
          const dayEvents = getEventsForDate(date);
          const inMonth = isCurrentMonth(date);

          return (
            <div
              key={i}
              role="gridcell"
              onClick={() => onDateClick(date)}
              aria-label={`${date.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' })}${dayEvents.length > 0 ? `, ${dayEvents.length} event${dayEvents.length > 1 ? 'i' : 'o'}` : ''}`}
              className={cn(
                'min-h-[90px] p-2 border border-white/5 rounded-lg cursor-pointer transition-all',
                inMonth ? 'bg-[#1A1D24]' : 'bg-[#1A1D24]/30 opacity-40',
                isToday(date) && 'ring-2 ring-[#d4845a]',
                isSelected(date) && 'bg-[#d4845a]/10 border-[#d4845a]/50',
                'hover:border-[#d4845a]/30'
              )}
            >
              <div
                className={cn(
                  'text-sm font-medium mb-1',
                  isToday(date) && 'text-[#d4845a]',
                  !isToday(date) && inMonth && 'text-[#E6E7EB]',
                  date.getDay() === 0 && !isToday(date) && 'text-[#d4845a]/70'
                )}
                aria-current={isToday(date) ? 'date' : undefined}
              >
                {date.getDate()}
              </div>

              <div className="space-y-0.5">
                {dayEvents.slice(0, 2).map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    compact
                    isSelected={selectedEvent?.id === event.id}
                    onClick={onEventClick}
                  />
                ))}
                {dayEvents.length > 2 && (
                  <div className="text-[10px] text-[#9AA0AE] px-1">
                    +{dayEvents.length - 2} altri
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
