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
    title: "PPh 25 mensile",
    date: "2026-05-15T00:00:00Z",
    description:
      "Pagamento entro il 15 del mese seguente (JCSS 2025 cambio da 10 a 15).",
  },
  {
    id: "ppn-monthly",
    kind: "PPN",
    title: "PPN SPT Masa",
    date: "2026-05-31T00:00:00Z",
    description: "SPT Masa PPN entro fine mese successivo.",
  },
  {
    id: "lkpm-q1",
    kind: "LKPM",
    title: "LKPM Q1 2026",
    date: "2026-07-10T00:00:00Z",
    description: "Laporan Kegiatan Penanaman Modal, trimestrale.",
  },
  {
    id: "pb1-badung",
    kind: "PB1",
    title: "PB1 Badung",
    date: "2026-05-10T00:00:00Z",
    regency: "Badung",
    description: "Pajak Hotel/Restoran 10%.",
  },
  {
    id: "pb1-gianyar",
    kind: "PB1",
    title: "PB1 Gianyar",
    date: "2026-05-15T00:00:00Z",
    regency: "Gianyar",
    description: "PB1 reggenza Gianyar.",
  },
  {
    id: "spt-individual-2026",
    kind: "PPh",
    title: "SPT Tahunan Individuale 2025",
    date: "2026-04-30T00:00:00Z",
    description: "Estesa a 30 aprile (era 31 marzo).",
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
