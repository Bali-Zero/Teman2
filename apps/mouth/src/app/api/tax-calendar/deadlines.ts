export type TaxDeadlineKind = "PPh" | "PPN" | "LKPM" | "PB1";

export interface TaxDeadline {
  id: string;
  kind: TaxDeadlineKind;
  title: string;
  date: string; // ISO 8601
  regency?: string;
  description: string;
}

export const TAX_DEADLINES: TaxDeadline[] = [
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

export function getRegencies(): string[] {
  return Array.from(
    new Set(
      TAX_DEADLINES.filter((d): d is TaxDeadline & { regency: string } =>
        Boolean(d.regency),
      ).map((d) => d.regency),
    ),
  );
}
