export interface DocumentCategory {
  code: string;
  name: string;
  category_group: string;
  description?: string | null;
  has_expiry?: boolean | null;
}

interface PracticeLike {
  practice_id: number;
  practice_type_code: string;
  title?: string | null;
  status: string;
}

export const DEFAULT_CATEGORY_GROUPS = [
  "immigration",
  "pma",
  "tax",
  "personal",
  "other",
] as const;

export const GROUP_LABELS: Record<string, string> = {
  immigration: "Immigration",
  pma: "Company",
  tax: "Tax",
  personal: "Personal",
  other: "Other",
};

const DRIVE_FOLDER_LABELS: Record<string, string> = {
  immigration: "01_Immigration",
  pma: "02_Company",
  tax: "03_Tax",
};

const DOC_TYPE_DESTINATIONS: Record<
  string,
  { group: string; categoryCode: string }
> = {
  passport: { group: "immigration", categoryCode: "passport" },
  kitas: { group: "immigration", categoryCode: "kitas" },
  npwp: { group: "tax", categoryCode: "npwp" },
  nib: { group: "pma", categoryCode: "nib" },
  akta_pendirian: { group: "pma", categoryCode: "akta_pendirian" },
};

function normalizeCode(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function humanize(value: string): string {
  const words = value.replaceAll("_", " ").trim().split(/\s+/);
  return words
    .filter(Boolean)
    .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function groupLabel(group: string): string {
  return GROUP_LABELS[group] ?? humanize(group);
}

export function categoryGroups(categories: DocumentCategory[]): string[] {
  const extraGroups = categories
    .map((category) => normalizeCode(category.category_group))
    .filter(
      (group) =>
        group &&
        !DEFAULT_CATEGORY_GROUPS.includes(
          group as (typeof DEFAULT_CATEGORY_GROUPS)[number],
        ),
    );

  return [...DEFAULT_CATEGORY_GROUPS, ...Array.from(new Set(extraGroups))];
}

export function categoriesForGroup(
  categories: DocumentCategory[],
  group: string,
): DocumentCategory[] {
  const normalizedGroup = normalizeCode(group);
  return categories.filter(
    (category) => normalizeCode(category.category_group) === normalizedGroup,
  );
}

export function inferDestinationFromDocType(
  docType: string | null | undefined,
  categories: DocumentCategory[],
): { group: string; categoryCode: string } {
  const normalizedDocType = normalizeCode(docType);
  const mapped = DOC_TYPE_DESTINATIONS[normalizedDocType] ?? {
    group: "other",
    categoryCode: "",
  };
  const categoryExists = categories.some(
    (category) =>
      normalizeCode(category.category_group) === mapped.group &&
      normalizeCode(category.code) === mapped.categoryCode,
  );

  return {
    group: mapped.group,
    categoryCode: categoryExists ? mapped.categoryCode : "",
  };
}

export function formatOperator(receivedBy: string | null | undefined): string {
  return receivedBy?.trim() || "unassigned";
}

export function formatPracticeOption(practice: PracticeLike): string {
  const title = practice.title?.trim();
  return title
    ? `#${practice.practice_id} — ${practice.practice_type_code} · ${title} (${practice.status})`
    : `#${practice.practice_id} — ${practice.practice_type_code} (${practice.status})`;
}

export function driveFolderLabel(group: string): string {
  return DRIVE_FOLDER_LABELS[group] ?? "backend default";
}
