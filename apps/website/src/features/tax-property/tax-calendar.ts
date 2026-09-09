/** Preserved source records, inspected 2026-09-09 from Mouth at
 * 15751bd0705334dea3dfb06ba475e38b9320ec97. This is NOT a current legal calendar.
 * Raw inherited deadline claims remain in this archive, never silently rolled forward. */
export type TaxKind = "PPh" | "PPN" | "LKPM" | "PB1";
export interface TaxDeadline {
  id: string;
  kind: TaxKind;
  title: string;
  date: string;
  regency?: string;
  description: string;
}
export const TAX_ARCHIVE: TaxDeadline[] = [
  {
    id: "pph25-monthly",
    kind: "PPh",
    title: "PPh 25 — monthly",
    date: "2026-05-15T00:00:00Z",
    description:
      "Payment due by the 15th of the following month (JCSS 2025 shifted it from the 10th to the 15th).",
  },
  {
    id: "ppn-monthly",
    kind: "PPN",
    title: "PPN SPT Masa",
    date: "2026-05-31T00:00:00Z",
    description: "VAT return (SPT Masa) due by the end of the following month.",
  },
  {
    id: "lkpm-q1",
    kind: "LKPM",
    title: "LKPM Q1 2026",
    date: "2026-07-10T00:00:00Z",
    description:
      "Quarterly investment activity report (Laporan Kegiatan Penanaman Modal).",
  },
  {
    id: "pb1-badung",
    kind: "PB1",
    title: "PB1 Badung",
    date: "2026-05-10T00:00:00Z",
    regency: "Badung",
    description: "Hotel and restaurant tax, 10%.",
  },
  {
    id: "pb1-gianyar",
    kind: "PB1",
    title: "PB1 Gianyar",
    date: "2026-05-15T00:00:00Z",
    regency: "Gianyar",
    description: "PB1 for Gianyar regency.",
  },
  {
    id: "spt-individual-2026",
    kind: "PPh",
    title: "SPT Tahunan — Individual 2025",
    date: "2026-04-30T00:00:00Z",
    description: "Extended to April 30 (was March 31).",
  },
];
export const TAX_KINDS = ["ALL", "PPh", "PPN", "LKPM", "PB1"] as const;
export type TaxFilter = (typeof TAX_KINDS)[number];
export const TAX_REGENCIES = [
  ...new Set(TAX_ARCHIVE.flatMap((d) => (d.regency ? [d.regency] : []))),
];
export function filterDeadlines(
  records: TaxDeadline[],
  kind: string,
  regency: string,
): TaxDeadline[] {
  return records
    .filter(
      (d) =>
        (kind === "ALL" || d.kind === kind) &&
        (!regency || !d.regency || d.regency === regency),
    )
    .sort((a, b) => a.date.localeCompare(b.date));
}
function escapeIcal(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/\r?\n/g, "\\n")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,");
}
/** RFC 5545 all-day dates keep the source date independent of browser timezone. */
export function taxCalendarIcal(records: TaxDeadline[]): string {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Bali Zero//Tax Calendar Archive//EN",
    "CALSCALE:GREGORIAN",
  ];
  for (const record of records) {
    const date = new Date(record.date);
    const end = new Date(date.getTime() + 86_400_000);
    const stamp = (d: Date): string =>
      d.toISOString().slice(0, 10).replace(/-/g, "");
    lines.push(
      "BEGIN:VEVENT",
      `UID:balizero-tax-${record.id}@balizero.com`,
      "DTSTAMP:20260909T000000Z",
      `DTSTART;VALUE=DATE:${stamp(date)}`,
      `DTEND;VALUE=DATE:${stamp(end)}`,
      `SUMMARY:${escapeIcal(`[UNVERIFIED ARCHIVE] ${record.title}`)}`,
      `DESCRIPTION:${escapeIcal(`Historical source record. Not a current filing instruction. Verify date and applicability with the tax team. Source note (unverified): ${record.description}`)}`,
      "END:VEVENT",
    );
  }
  lines.push("END:VCALENDAR");
  // Fold by UTF-8 bytes, not JS characters (RFC 5545 section 3.1).
  return (
    lines
      .map((line) => {
        let out = "",
          size = 0;
        for (const char of line) {
          const bytes = new TextEncoder().encode(char).length;
          if (size + bytes > 75) {
            out += "\r\n ";
            size = 1;
          }
          out += char;
          size += bytes;
        }
        return out;
      })
      .join("\r\n") + "\r\n"
  );
}
