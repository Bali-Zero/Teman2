/**
 * Locale-aware date formatting for the portal.
 *
 * Portal surfaces used to hardcode `toLocaleDateString("en-US", ...)` in
 * ~20 call sites regardless of the client's saved language preference
 * (`useLanguage`, cookie `bz_lang`). This module is the single place that
 * maps a saved language to an IETF locale tag, so the choice a client
 * makes is actually honoured.
 */
import type { Language } from "@/lib/schemas/settings";

/**
 * Map a saved portal language to an IETF locale tag for `Intl`/
 * `toLocaleDateString`/`toLocaleString`.
 *
 * `null`/`undefined` (no saved preference yet) returns `undefined`,
 * which tells the `Intl` APIs to fall back to the browser's own locale
 * rather than guessing.
 */
export function localeTagFor(
  language: Language | null | undefined,
): string | undefined {
  switch (language) {
    case "it":
      return "it-IT";
    case "en":
      return "en-US";
    case "id":
      return "id-ID";
    default:
      return undefined;
  }
}

function toValidDate(value: string | Date | null | undefined): Date | null {
  if (value == null) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Locale-aware wrapper over `Date#toLocaleDateString`.
 * Returns `""` for `null`/`undefined`/unparseable input instead of the
 * native `"Invalid Date"` string.
 */
export function formatDate(
  value: string | Date | null | undefined,
  language: Language | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = toValidDate(value);
  if (!date) return "";
  return date.toLocaleDateString(localeTagFor(language), options);
}

/**
 * Locale-aware wrapper over `Date#toLocaleString`.
 * Returns `""` for `null`/`undefined`/unparseable input instead of the
 * native `"Invalid Date"` string.
 */
export function formatDateTime(
  value: string | Date | null | undefined,
  language: Language | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = toValidDate(value);
  if (!date) return "";
  return date.toLocaleString(localeTagFor(language), options);
}
