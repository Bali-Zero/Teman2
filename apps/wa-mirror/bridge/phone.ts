const INDONESIA_COUNTRY_CODE = "62";

/**
 * Normalize WhatsApp/CRM phone values into canonical E.164.
 *
 * Bali Zero numbers are Indonesia-first for this bridge. Common CRM and WA
 * variants all converge to +62...:
 * - 08xxx
 * - 628xxx
 * - +628xxx
 * - 00628xxx
 */
export function normalizePhone(raw: string | null | undefined): string {
  const digitsOnly = (raw ?? "").replace(/[^\d]/g, "");
  if (digitsOnly.length === 0) return "";

  let digits = digitsOnly;
  if (digits.startsWith("00")) {
    digits = digits.slice(2);
  }

  while (digits.startsWith("0")) {
    digits = digits.slice(1);
  }

  if (!digits.startsWith(INDONESIA_COUNTRY_CODE)) {
    digits = `${INDONESIA_COUNTRY_CODE}${digits}`;
  }

  return digits.length > INDONESIA_COUNTRY_CODE.length ? `+${digits}` : "";
}

export function phoneDigits(raw: string | null | undefined): string {
  return normalizePhone(raw).replace(/[^\d]/g, "");
}

export function phoneSearchVariants(raw: string | null | undefined): string[] {
  const canonical = normalizePhone(raw);
  if (!canonical) return [];

  const digits = canonical.replace(/[^\d]/g, "");
  const local =
    digits.startsWith(INDONESIA_COUNTRY_CODE) &&
    digits.length > INDONESIA_COUNTRY_CODE.length
      ? `0${digits.slice(INDONESIA_COUNTRY_CODE.length)}`
      : digits;

  return Array.from(new Set([canonical, digits, local]));
}

export function phonePathSegment(raw: string): string {
  return phoneDigits(raw);
}
