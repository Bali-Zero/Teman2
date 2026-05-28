// phone.ts — strict E.164 normalisation via libphonenumber-js.
//
// Replaces the regex-based heuristic (pre-2026-05-19) which had a real
// production bug verified empirically against `whatsapp_message_context`
// (15,209 rows, 0% client match):
//
// 1. False country-code injection on WhatsApp `@lid` (Linked Identity
//    Device) identifiers. A LID like `224112131756075` is not a phone
//    number; the old code blindly prepended `62` and produced fake
//    E.164 strings (`+62224112131756075`, 17-18 digits) for 70% of
//    inbound messages, making client-side matching impossible.
//
// HISTORICAL NOTE (eviction 2026-05-26): an earlier version of this
// comment claimed a "leading-zero truncation" bug that turned
// `+6282134547725` (12 digits) into `+628213454725` (11 digits) for
// Adit/Vino/Sahira. That was wrong on both counts:
// - libphonenumber-js NEVER truncated those numbers — see
//   tests/phone.test.ts coverage for the real 11-digit Indonesian
//   national format `+62812…`.
// - The 12-digit strings in `~/.wa-mirror.env` were operator-side
//   typos (likely a double-tap on the `4` while typing the Adit/Vino
//   numbers in batch). Real phones per `~/.wa-mirror.accounts.json`
//   are 11-digit national: `+628213454725` (Adit), `+628213454727`
//   (Vino), `+628213454723` (Sahira).
// The launcher (`~/scripts/wa-mirror-launcher/start-one.sh`) overrides
// `WA_MIRROR_ACCOUNTS` from accounts.json at spawn time, so runtime
// was correct; only `npm start` (which reads the env directly) saw
// the typo, plus this comment + tests/phone.test.ts cementing a
// "regression test" that guarded a bug that never existed.
//
// Contract for v2:
// - normalizePhone() ALWAYS returns a valid E.164 string (with `+`) or
//   an empty string. Indonesia is the default region for ambiguous inputs
//   that lack a country code (e.g. `0812…` / `812…`).
// - International numbers (`+39…`, `+61…`, `+966…`) are preserved
//   unchanged when they already carry a `+`.
// - LID strings MUST be filtered upstream by `filters.ts::parseJid`;
//   this module does not attempt to detect them. If a caller passes a
//   LID by mistake, libphonenumber rejects it as invalid and we return
//   "" — fail-safe, no fake match.

import {
  parsePhoneNumberFromString,
  type CountryCode,
} from "libphonenumber-js";

const INDONESIA: CountryCode = "ID";

function looksInternational(raw: string): boolean {
  const trimmed = raw.trimStart();
  if (trimmed.startsWith("+")) return true;
  // `00` international-dial prefix → treat as +CC
  if (trimmed.startsWith("00")) return true;
  return false;
}

export function normalizePhone(raw: string | null | undefined): string {
  if (!raw) return "";
  const cleaned = String(raw).trim();
  if (cleaned.length === 0) return "";

  // Convert `00CCxxx` to `+CCxxx` so libphonenumber sees the international form.
  const withPlus = cleaned.startsWith("00") ? `+${cleaned.slice(2)}` : cleaned;

  // If the input carries an explicit country prefix, parse without a default
  // region — libphonenumber uses whatever country the `+CC` indicates
  // (Italy `+39`, Australia `+61`, Saudi `+966`, etc.). This is what kills
  // the cross-country last-N-digit collision class.
  const parsed = looksInternational(withPlus)
    ? parsePhoneNumberFromString(withPlus)
    : parsePhoneNumberFromString(withPlus, INDONESIA);

  if (!parsed || !parsed.isValid()) return "";
  return parsed.number; // canonical E.164 with leading `+`
}

export function phoneDigits(raw: string | null | undefined): string {
  return normalizePhone(raw).replace(/[^\d]/g, "");
}

/**
 * Variants emitted for legacy CRM lookups where rows may be stored in
 * mixed formats (`+6281…`, `6281…`, `0812…`). The canonical E.164 form
 * is always first so callers can prefer it.
 *
 * Non-Indonesian numbers only emit the canonical E.164 + digit-only form —
 * there is no "local 0-prefix" equivalent for arbitrary countries.
 */
export function phoneSearchVariants(raw: string | null | undefined): string[] {
  const canonical = normalizePhone(raw);
  if (!canonical) return [];

  const digits = canonical.replace(/[^\d]/g, "");
  const variants = [canonical, digits];

  // Indonesia-only: emit the local `0xxx` form so we still match legacy
  // CRM rows that were typed as `08123…` without country code.
  if (digits.startsWith("62") && digits.length > 2) {
    variants.push(`0${digits.slice(2)}`);
  }

  return Array.from(new Set(variants));
}

export function phonePathSegment(raw: string): string {
  return phoneDigits(raw);
}
