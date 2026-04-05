/**
 * Client-side iCal (.ics) generator
 * Produces RFC 5545-compliant iCalendar files from CalendarEvent arrays.
 */

import type { CalendarEvent } from './types';

function escapeIcal(str: string): string {
  return str
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '');
}

function toIcalDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  // Format: YYYYMMDDTHHMMSSZ (UTC)
  return d
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/\.\d{3}/, '');
}

function foldLine(line: string): string {
  // RFC 5545: lines > 75 octets should be folded
  const maxLen = 75;
  if (line.length <= maxLen) return line;
  let folded = '';
  while (line.length > maxLen) {
    folded += line.slice(0, maxLen) + '\r\n ';
    line = line.slice(maxLen);
  }
  folded += line;
  return folded;
}

export function generateIcal(events: CalendarEvent[], calendarName = 'Bali Zero Calendar'): string {
  const lines: string[] = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    `PRODID:-//Bali Zero//Nuzantara Calendar//IT`,
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    `X-WR-CALNAME:${escapeIcal(calendarName)}`,
    'X-WR-TIMEZONE:Asia/Makassar',
  ];

  for (const event of events) {
    const dtstart = toIcalDate(event.start);
    const dtend = toIcalDate(event.end);
    if (!dtstart || !dtend) continue;

    const uid = `${event.id}@balizero.com`;
    const now = toIcalDate(new Date().toISOString());

    lines.push('BEGIN:VEVENT');
    lines.push(foldLine(`UID:${uid}`));
    lines.push(foldLine(`DTSTAMP:${now}`));
    lines.push(foldLine(`DTSTART:${dtstart}`));
    lines.push(foldLine(`DTEND:${dtend}`));
    lines.push(foldLine(`SUMMARY:${escapeIcal(event.summary)}`));

    if (event.description) {
      lines.push(foldLine(`DESCRIPTION:${escapeIcal(event.description)}`));
    }
    if (event.location) {
      lines.push(foldLine(`LOCATION:${escapeIcal(event.location)}`));
    }
    if (event.hangoutLink) {
      lines.push(foldLine(`URL:${event.hangoutLink}`));
    }
    if (event.attendees && event.attendees.length > 0) {
      for (const email of event.attendees) {
        lines.push(foldLine(`ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT:mailto:${email}`));
      }
    }

    lines.push('END:VEVENT');
  }

  lines.push('END:VCALENDAR');
  return lines.join('\r\n');
}

export function downloadIcal(events: CalendarEvent[], filename = 'balizero-calendar.ics'): void {
  const content = generateIcal(events);
  const blob = new Blob([content], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
