export interface IcalEvent {
  uid: string;
  summary: string;
  start: Date;
  end: Date;
  description?: string;
}

export interface IcalOptions {
  prodId: string;
}

function icalDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    d.getUTCFullYear().toString() +
    pad(d.getUTCMonth() + 1) +
    pad(d.getUTCDate()) +
    "T" +
    pad(d.getUTCHours()) +
    pad(d.getUTCMinutes()) +
    pad(d.getUTCSeconds()) +
    "Z"
  );
}

function escape(s: string): string {
  return s.replace(/[\\,;]/g, (c) => `\\${c}`).replace(/\n/g, "\\n");
}

export function toIcalString(events: IcalEvent[], opts: IcalOptions): string {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    `PRODID:${opts.prodId}`,
    "CALSCALE:GREGORIAN",
  ];
  for (const e of events) {
    lines.push("BEGIN:VEVENT");
    lines.push(`UID:${e.uid}`);
    lines.push(`DTSTAMP:${icalDate(new Date())}`);
    lines.push(`DTSTART:${icalDate(e.start)}`);
    lines.push(`DTEND:${icalDate(e.end)}`);
    lines.push(`SUMMARY:${escape(e.summary)}`);
    if (e.description) lines.push(`DESCRIPTION:${escape(e.description)}`);
    lines.push("END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}
