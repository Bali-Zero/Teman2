/**
 * Shared types for Calendar components
 */

export interface CalendarEvent {
  id: string;
  summary: string;
  start: string;
  end: string;
  description?: string;
  location?: string;
  attendees?: string[];
  hangoutLink?: string;
}

export interface CalendarInfo {
  id: string;
  name: string;
  role: string;
}

export const WEEKDAYS = [
  { short: 'Dom', full: 'Domenica' },
  { short: 'Lun', full: 'Lunedì' },
  { short: 'Mar', full: 'Martedì' },
  { short: 'Mer', full: 'Mercoledì' },
  { short: 'Gio', full: 'Giovedì' },
  { short: 'Ven', full: 'Venerdì' },
  { short: 'Sab', full: 'Sabato' },
];
