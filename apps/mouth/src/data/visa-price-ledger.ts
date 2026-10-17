import type { ServicePackage } from "@/data/services_data";

/**
 * Editorial grouping of the public visa price list.
 *
 * The catalogue (PricingTool SSOT, mirrored to data/bali-zero-prices.json)
 * is flat: 79 exact rows across five categories. This module decides how
 * those rows READ on /services/visa — five chapters, each a few families,
 * each family either a matrix (one service, several catalogue variants
 * laid out as columns) or a list (one line per catalogue row).
 *
 * It never carries a price. Every cell resolves to a ServicePackage whose
 * figure comes from the snapshot at render time, and `buildVisaLedger`
 * reports both directions of drift: a spec key the catalogue no longer has
 * (`dangling`) and a catalogue row the spec does not place (`unplaced`,
 * rendered in a trailing chapter so nothing is ever hidden).
 */

export interface MatrixVariantSpec {
  /** One service, several catalogue rows that differ only by this label
   *  (1 year / 2 years, ordinary / electronic): never split into services. */
  label: string;
  cells: (string | null)[];
}

export interface MatrixRowSpec {
  name: string;
  cells?: (string | null)[];
  variants?: MatrixVariantSpec[];
}

export interface MatrixFamilySpec {
  kind: "matrix";
  id: string;
  name: string;
  columns: string[];
  rows: MatrixRowSpec[];
}

export interface ListFamilySpec {
  kind: "list";
  id: string;
  name: string;
  keys: string[];
}

export type FamilySpec = MatrixFamilySpec | ListFamilySpec;

export interface ChapterSpec {
  id: string;
  numeral: string;
  title: string;
  lede: string;
  families: FamilySpec[];
}

const CHANNEL = ["Offshore", "Onshore", "Extension"];

export const VISA_LEDGER_SPEC: ChapterSpec[] = [
  {
    id: "short-stays",
    numeral: "I",
    title: "Short stays",
    lede: "Single-entry visas for a visit, a business trip or a short assignment.",
    families: [
      {
        kind: "matrix",
        id: "arrive",
        name: "On arrival",
        columns: ["Visa", "Extension"],
        rows: [
          {
            name: "A1 Visa-Free Tourism",
            cells: ["A1 Visa-Free Tourism", null],
          },
          {
            name: "B1 Visa on Arrival",
            cells: ["B1 Visa on Arrival (VOA)", "B1 Visa on Arrival Extension"],
          },
        ],
      },
      {
        kind: "matrix",
        id: "visit",
        name: "Visit",
        columns: ["Visa", "Extension"],
        rows: [
          { name: "C1 Tourism", cells: ["C1 Tourism", "C1 Tourism Extension"] },
          { name: "C2 Business", cells: ["C2 Business", null] },
          { name: "C6 Social Activity", cells: ["C6 Social Activity", null] },
        ],
      },
      {
        kind: "list",
        id: "perform",
        name: "Perform, compete, speak",
        keys: ["C7A,B,C Music/Art", "C8A,B", "C10 Speaker Visa"],
      },
      {
        kind: "matrix",
        id: "train",
        name: "Train and learn",
        columns: ["60 days", "180 days"],
        rows: [
          {
            name: "C22A&B Internship",
            cells: [
              "C22A&B Internship (60 Days)",
              "C22A&B Internship (180 Days)",
            ],
          },
        ],
      },
      {
        kind: "list",
        id: "trial-bridge",
        name: "Work trial and bridging",
        keys: ["C18 Work Trial", "Bridging Visa"],
      },
    ],
  },
  {
    id: "multiple-entry",
    numeral: "II",
    title: "Multiple entry",
    lede: "One visa, repeated entries, one to five years of validity.",
    families: [
      {
        kind: "matrix",
        id: "multi",
        name: "Multiple-entry visas",
        columns: ["1 year", "2 years", "5 years"],
        rows: [
          {
            name: "D1 Tourism",
            cells: [
              "D1 Tourism (1 Year)",
              "D1 Tourism (2 Years)",
              "D1 Tourism (5 Years)",
            ],
          },
          {
            name: "D2 Business",
            cells: [
              "D2 Business (1 Year)",
              "D2 Business (2 Years)",
              "D2 Business (5 Years)",
            ],
          },
          {
            name: "D12 Business Investigation",
            cells: [
              "D12 Business Investigation (1 Year)",
              "D12 Business Investigation (2 Years)",
              null,
            ],
          },
        ],
      },
    ],
  },
  {
    id: "kitas",
    numeral: "III",
    title: "KITAS",
    lede: "Limited stay permits for work, investment, remote work, a second home, study and family.",
    families: [
      {
        kind: "matrix",
        id: "work",
        name: "Work",
        columns: CHANNEL,
        rows: [
          {
            name: "Working KITAS",
            cells: [
              "Working KITAS (Offshore)",
              "Working KITAS (Altus/Onshore)",
              "Working KITAS (Extend)",
            ],
          },
          {
            name: "Freelance E23",
            cells: [
              "Freelance E23 (Offshore)",
              "Freelance E23 (Altus/Onshore)",
              null,
            ],
          },
        ],
      },
      {
        kind: "matrix",
        id: "invest",
        name: "Invest",
        columns: CHANNEL,
        rows: [
          {
            name: "Investor KITAS, 2 years",
            cells: [
              "Investor KITAS 2 Years (Offshore)",
              "Investor KITAS 2 Years (Altus/Onshore)",
              "Investor KITAS 2 Years (Extend)",
            ],
          },
        ],
      },
      {
        kind: "matrix",
        id: "remote",
        name: "Remote work",
        columns: CHANNEL,
        rows: [
          {
            name: "E33G Remote Worker",
            cells: [
              "E33G Remote Worker (Offshore)",
              "E33G Remote Worker (Altus/Onshore)",
              "E33G Remote Worker (Extend)",
            ],
          },
        ],
      },
      {
        kind: "matrix",
        id: "second-home",
        name: "Second Home",
        columns: ["New permit", "Extension"],
        rows: [
          {
            name: "E33 Second Home",
            variants: [
              {
                label: "5 years",
                cells: ["E33 Second Home (5 Years)", null],
              },
            ],
          },
          {
            name: "E33E Second Home Senior",
            variants: [
              {
                label: "5 years",
                cells: [
                  "E33E Second Home Senior (5 Years)",
                  "E33E Second Home Senior (Extend)",
                ],
              },
            ],
          },
          {
            name: "E33F Second Home Senior",
            variants: [
              {
                label: "1 year, Offshore",
                cells: ["E33F Second Home Senior (1 Year, Offshore)", null],
              },
              {
                label: "1 year, Altus / Onshore",
                cells: [
                  "E33F Second Home Senior (1 Year, Altus/Onshore)",
                  "E33F Second Home Senior (Extend)",
                ],
              },
            ],
          },
        ],
      },
      {
        kind: "matrix",
        id: "study",
        name: "Study",
        columns: ["1 year", "2 years", "4 years"],
        rows: [
          {
            name: "E30A Education Visa",
            cells: [
              "E30A Education Visa (1 Year)",
              "E30A Education Visa (2 Years)",
              null,
            ],
          },
          {
            name: "E30B Higher Education",
            cells: [
              "E30B Higher Education (1 Year)",
              "E30B Higher Education (2 Years)",
              "E30B Higher Education (4 Years)",
            ],
          },
        ],
      },
      {
        kind: "matrix",
        id: "family",
        name: "Family",
        columns: CHANNEL,
        rows: [
          {
            name: "Spouse KITAS",
            variants: [
              {
                label: "1 year",
                cells: [
                  "Spouse 1 Year (Offshore)",
                  "Spouse 1 Year (Altus/Onshore)",
                  "Spouse 1 Year (Extend)",
                ],
              },
              {
                label: "2 years",
                cells: [
                  "Spouse 2 Years (Offshore)",
                  "Spouse 2 Years (Altus/Onshore)",
                  "Spouse 2 Years (Extend)",
                ],
              },
            ],
          },
          {
            name: "Dependent KITAS",
            variants: [
              {
                label: "1 year",
                cells: [
                  "Dependent 1 Year (Offshore)",
                  "Dependent 1 Year (Altus/Onshore)",
                  "Dependent 1 Year (Extend)",
                ],
              },
              {
                label: "2 years",
                cells: [
                  "Dependent 2 Years (Offshore)",
                  "Dependent 2 Years (Altus/Onshore)",
                  "Dependent 2 Years (Extend)",
                ],
              },
            ],
          },
        ],
      },
      {
        kind: "list",
        id: "newborn",
        name: "Born in Indonesia",
        keys: ["Born KITAS"],
      },
    ],
  },
  {
    id: "kitap",
    numeral: "IV",
    title: "KITAP",
    lede: "Permanent stay permits, each issued with its multiple exit re-entry permit (MERP).",
    families: [
      {
        kind: "list",
        id: "permanent",
        name: "Permanent residence",
        keys: [
          "Investor KITAP + MERP",
          "Retirement KITAP + MERP",
          "Dependent KITAP + MERP",
        ],
      },
    ],
  },
  {
    id: "paperwork",
    numeral: "V",
    title: "Paperwork and permits",
    lede: "Passports, registrations, record changes, work-permit administration and exit permits.",
    families: [
      {
        kind: "matrix",
        id: "passports",
        name: "Passports",
        columns: ["5 years", "10 years"],
        rows: [
          {
            name: "Passport",
            variants: [
              {
                label: "Ordinary",
                cells: ["Passport 5 Years", "Passport 10 Years"],
              },
              {
                label: "Electronic",
                cells: [
                  "Electronic Passport 5 Years",
                  "Electronic Passport 10 Years",
                ],
              },
            ],
          },
        ],
      },
      {
        kind: "list",
        id: "registrations",
        name: "Registrations and letters",
        keys: ["SKTT", "SKCK", "Domicilie Letter"],
      },
      {
        kind: "matrix",
        id: "birth-report",
        name: "Birth report",
        columns: ["Under", "Up"],
        rows: [
          {
            name: "Lapor Lahir",
            cells: ["Lapor Lahir (Under)", "Lapor Lahir (Up)"],
          },
        ],
      },
      {
        kind: "matrix",
        id: "address-mutation",
        name: "Address mutation",
        columns: ["Standard", "2 Kanim"],
        rows: [
          {
            name: "Mutation Address",
            cells: ["Mutation Address", "Mutation Address 2 Kanim"],
          },
        ],
      },
      {
        kind: "list",
        id: "record-changes",
        name: "Changes on record",
        keys: ["Mutation Passport", "Reset Molina"],
      },
      {
        kind: "matrix",
        id: "work-permit",
        name: "Work permit administration",
        columns: ["6 months or less", "12 months"],
        rows: [
          {
            name: "IMTA & RPTKA only",
            cells: [
              "Process IMTA & RPTKA Only (6 Months or Less)",
              "Process IMTA & RPTKA Only (12 Months)",
            ],
          },
        ],
      },
      {
        kind: "list",
        id: "cancellations",
        name: "Cancellations",
        keys: ["Cancel RPTKA", "Cancel Wajib Lapor"],
      },
      {
        kind: "list",
        id: "exit",
        name: "Exit permits",
        keys: ["EPO (Exit Permit Only)", "ERP (Exit Re-entry Permit)"],
      },
    ],
  },
];

export const UNPLACED_CHAPTER_ID = "more";

export interface LedgerMatrixVariant {
  label: string;
  cells: (ServicePackage | null)[];
}

export interface LedgerMatrixRow {
  name: string;
  /** Empty when the row is split into variants. */
  cells: (ServicePackage | null)[];
  variants?: LedgerMatrixVariant[];
}

export function rowCells(row: LedgerMatrixRow): (ServicePackage | null)[] {
  return row.variants
    ? row.variants.flatMap((variant) => variant.cells)
    : row.cells;
}

export interface LedgerMatrixFamily {
  kind: "matrix";
  id: string;
  name: string;
  columns: string[];
  rows: LedgerMatrixRow[];
}

export interface LedgerListFamily {
  kind: "list";
  id: string;
  name: string;
  items: ServicePackage[];
}

export type LedgerFamily = LedgerMatrixFamily | LedgerListFamily;

export interface LedgerChapter {
  id: string;
  numeral: string;
  title: string;
  lede: string;
  families: LedgerFamily[];
  count: number;
}

export interface VisaLedger {
  chapters: LedgerChapter[];
  /** Spec keys with no matching package: the catalogue moved under the spec. */
  dangling: string[];
  /** Packages the spec never places: shown in the trailing chapter. */
  unplaced: ServicePackage[];
  total: number;
}

function familyCount(family: LedgerFamily): number {
  if (family.kind === "list") return family.items.length;
  return family.rows.reduce(
    (count, row) => count + rowCells(row).filter(Boolean).length,
    0,
  );
}

export function buildVisaLedger(
  packages: ServicePackage[],
  spec: ChapterSpec[] = VISA_LEDGER_SPEC,
): VisaLedger {
  const byKey = new Map<string, ServicePackage>();
  for (const pkg of packages) {
    if (pkg.livePriceKey) byKey.set(pkg.livePriceKey, pkg);
  }
  const placed = new Set<string>();
  const dangling: string[] = [];

  const resolve = (key: string | null): ServicePackage | null => {
    if (key === null) return null;
    const pkg = byKey.get(key);
    if (!pkg) {
      dangling.push(key);
      return null;
    }
    placed.add(key);
    return pkg;
  };

  const chapters: LedgerChapter[] = spec.map((chapter) => {
    const families: LedgerFamily[] = chapter.families
      .map((family): LedgerFamily => {
        if (family.kind === "list") {
          return {
            kind: "list",
            id: family.id,
            name: family.name,
            items: family.keys
              .map(resolve)
              .filter((pkg): pkg is ServicePackage => pkg !== null),
          };
        }
        return {
          kind: "matrix",
          id: family.id,
          name: family.name,
          columns: family.columns,
          rows: family.rows
            .map((row): LedgerMatrixRow =>
              row.variants
                ? {
                    name: row.name,
                    cells: [],
                    variants: row.variants
                      .map((variant) => ({
                        label: variant.label,
                        cells: variant.cells.map(resolve),
                      }))
                      .filter((variant) => variant.cells.some(Boolean)),
                  }
                : { name: row.name, cells: (row.cells ?? []).map(resolve) },
            )
            .filter((row) => rowCells(row).some(Boolean)),
        };
      })
      .filter((family) => familyCount(family) > 0);
    return {
      id: chapter.id,
      numeral: chapter.numeral,
      title: chapter.title,
      lede: chapter.lede,
      families,
      count: families.reduce((count, family) => count + familyCount(family), 0),
    };
  });

  const unplaced = packages.filter(
    (pkg) => !pkg.livePriceKey || !placed.has(pkg.livePriceKey),
  );
  if (unplaced.length > 0) {
    chapters.push({
      id: UNPLACED_CHAPTER_ID,
      numeral: "+",
      title: "More services",
      lede: "Further services from the current price list.",
      families: [
        {
          kind: "list",
          id: "unplaced",
          name: "Also available",
          items: unplaced,
        },
      ],
      count: unplaced.length,
    });
  }

  const visible = chapters.filter((chapter) => chapter.count > 0);
  return {
    chapters: visible,
    dangling,
    unplaced,
    total: visible.reduce((count, chapter) => count + chapter.count, 0),
  };
}
