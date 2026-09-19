/**
 * Canonical `companies.company_type` values.
 *
 * The DB column is free text (no enum constraint — see
 * `company_models.py::Company.company_type`), and real rows carry legacy
 * spellings ("PMA" instead of "PT PMA") alongside the current default. A
 * plain `<select>` bound to that raw value silently falls back to its first
 * `<option>` whenever the value doesn't match one exactly — which looks like
 * a no-op edit but actually overwrites the stored type on save.
 *
 * Canonical options: `PT PMA`, `PT` (local/PMDN — an ordinary Indonesian
 * limited company, not foreign-invested), `PT Perorangan`, `CV`, `Other`.
 */
export interface CompanyTypeOption {
  value: string;
  label: string;
}

export const COMPANY_TYPE_OPTIONS: CompanyTypeOption[] = [
  { value: "PT PMA", label: "PT PMA" },
  { value: "PT", label: "PT (local / PMDN)" },
  { value: "PT Perorangan", label: "PT Perorangan" },
  { value: "CV", label: "CV" },
  { value: "Other", label: "Other" },
];

/** Known legacy/short spellings observed in stored data, mapped to canonical values. */
const LEGACY_ALIASES: Record<string, string> = {
  PMA: "PT PMA",
  PT_PMA: "PT PMA",
  PERORANGAN: "PT Perorangan",
  PT_PERORANGAN: "PT Perorangan",
  PMDN: "PT",
  PT_PMDN: "PT",
  "PT PMDN": "PT",
};

/**
 * Maps a raw stored `company_type` to a canonical value. Unrecognized values
 * are returned unchanged rather than coerced — the caller is expected to
 * surface them as a visible, selectable option instead of silently
 * defaulting to the first one.
 */
export function normalizeCompanyType(raw: string | undefined | null): string {
  if (!raw) return COMPANY_TYPE_OPTIONS[0].value;
  const canonical = COMPANY_TYPE_OPTIONS.find((o) => o.value === raw);
  if (canonical) return canonical.value;
  return LEGACY_ALIASES[raw.trim().toUpperCase()] || raw;
}

/**
 * Options for the company type `<select>`, guaranteed to include
 * `currentValue` even when it isn't one of the canonical values — so an
 * unrecognized/legacy value is shown truthfully instead of falling back to
 * the first option.
 */
export function companyTypeOptionsWithCurrent(
  currentValue: string,
): CompanyTypeOption[] {
  if (COMPANY_TYPE_OPTIONS.some((o) => o.value === currentValue)) {
    return COMPANY_TYPE_OPTIONS;
  }
  return [
    { value: currentValue, label: `${currentValue} (unrecognized)` },
    ...COMPANY_TYPE_OPTIONS,
  ];
}
