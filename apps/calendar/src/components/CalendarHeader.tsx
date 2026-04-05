'use client';

import React from 'react';
import { Plus, RefreshCw, ChevronLeft, ChevronRight, Grid3X3, List, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CalendarEvent, CalendarInfo } from './types';

interface CalendarHeaderProps {
  currentMonth: Date;
  calendars: CalendarInfo[];
  selectedCalendar: string;
  view: 'month' | 'list';
  loading: boolean;
  eventCount: number;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onToday: () => void;
  onViewChange: (view: 'month' | 'list') => void;
  onCalendarChange: (calendarId: string) => void;
  onRefresh: () => void;
  onNewEvent: () => void;
  onExportIcal: () => void;
}

export function CalendarHeader({
  currentMonth,
  calendars,
  selectedCalendar,
  view,
  loading,
  eventCount,
  onPrevMonth,
  onNextMonth,
  onToday,
  onViewChange,
  onCalendarChange,
  onRefresh,
  onNewEvent,
  onExportIcal,
}: CalendarHeaderProps) {
  return (
    <>
      {/* Top bar */}
      <header className="border-b border-white/5 bg-[#1A1D24] px-6 py-4 shrink-0">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-xl font-semibold text-[#E6E7EB]">Bali Zero Calendar</h1>
            <p className="text-sm text-[#9AA0AE]">
              {calendars.find((c) => c.id === selectedCalendar)?.name ?? 'Team Calendar'}
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Calendar selector */}
            <select
              value={selectedCalendar}
              onChange={(e) => onCalendarChange(e.target.value)}
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
            <div
              className="flex border border-white/10 rounded-lg overflow-hidden"
              role="group"
              aria-label="Seleziona vista"
            >
              <button
                onClick={() => onViewChange('month')}
                className={cn(
                  'px-3 py-2 text-sm transition-colors',
                  view === 'month' ? 'bg-[#d4845a] text-white' : 'text-[#9AA0AE] hover:bg-white/5'
                )}
                aria-pressed={view === 'month'}
                aria-label="Vista mese"
              >
                <Grid3X3 className="h-4 w-4" />
              </button>
              <button
                onClick={() => onViewChange('list')}
                className={cn(
                  'px-3 py-2 text-sm transition-colors',
                  view === 'list' ? 'bg-[#d4845a] text-white' : 'text-[#9AA0AE] hover:bg-white/5'
                )}
                aria-pressed={view === 'list'}
                aria-label="Vista lista"
              >
                <List className="h-4 w-4" />
              </button>
            </div>

            {/* Export iCal */}
            <button
              onClick={onExportIcal}
              className="p-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5 hover:text-[#E6E7EB] transition-colors"
              aria-label="Esporta iCal"
              title="Esporta iCal (.ics)"
            >
              <Download className="h-4 w-4" />
            </button>

            {/* Refresh */}
            <button
              onClick={onRefresh}
              disabled={loading}
              className="p-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5 disabled:opacity-50 transition-colors"
              aria-label="Aggiorna eventi"
            >
              <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
            </button>

            {/* New Event */}
            <button
              onClick={onNewEvent}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#d4845a] text-white hover:bg-[#bf7350] transition-colors text-sm font-medium"
            >
              <Plus className="h-4 w-4" />
              Nuovo
            </button>
          </div>
        </div>
      </header>

      {/* Month navigation bar */}
      <div className="px-6 py-3 border-b border-white/5 bg-[#1A1D24]/50 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={onPrevMonth}
            className="p-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5 transition-colors"
            aria-label="Mese precedente"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={onNextMonth}
            className="p-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5 transition-colors"
            aria-label="Mese successivo"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            onClick={onToday}
            className="px-3 py-2 rounded-lg text-sm text-[#9AA0AE] hover:bg-white/5 transition-colors"
          >
            Oggi
          </button>
        </div>

        <h2 className="text-lg font-semibold capitalize text-[#E6E7EB]">
          {currentMonth.toLocaleDateString('it-IT', { month: 'long', year: 'numeric' })}
        </h2>

        <div className="text-sm text-[#9AA0AE]" aria-live="polite">
          {eventCount} event{eventCount === 1 ? 'o' : 'i'}
        </div>
      </div>
    </>
  );
}
