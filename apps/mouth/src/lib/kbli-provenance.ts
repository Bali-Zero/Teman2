// =============================================================================
// KBLI Provenance Derivation (TRACK-P)
// Derives the per-code verification state + per-fact provenance from the
// structured GARUDA-FILIERA markers on the raw record.
//
// HARD RULES (kbli-navigator corner §4):
// - Decisions come ONLY from structured fields (`_l2_source`, `_l2_status`,
//   `per_skala_disputed_*` keys) — NEVER from substring matching on prose
//   (cicatrix #3: guard-over-match).
// - This module never authors licensing values: it only restates locators and
//   vintages the dataset already carries, or declares the gap.
// =============================================================================

import type {
  KBLICode,
  KBLIDisputedLicensing,
  KBLIDisputedScaleRow,
  KBLIProvenance,
  KBLIRawCode,
} from "./kbli-types";

const DISPUTED_KEY_PREFIX = "per_skala_disputed_";

/** OSS-native L2 marker value (KBLI-2025-vintage risk rows). */
const OSS_NATIVE_L2 = "OSS_RBA_resiko_2025";

/** `_l2_status` marker for the no-scope set (OSS ruang-lingkup 404). */
const NO_OSS_RISK = "no_oss_risk";

/**
 * Normalize a `per_skala_disputed_*` value to a row array. Two live shapes:
 * a bare row array (single-scope cures), or `{ per_skala: rows, ... }`
 * (multi-scope collision cures, e.g. 49213/20111).
 */
function normalizeDisputedRows(value: unknown): KBLIDisputedScaleRow[] {
  if (Array.isArray(value)) return value as KBLIDisputedScaleRow[];
  if (value && typeof value === "object") {
    const inner = (value as { per_skala?: unknown }).per_skala;
    if (Array.isArray(inner)) return inner as KBLIDisputedScaleRow[];
  }
  return [];
}

/** Extract the (single) disputed licensing block, if the record carries one. */
export function getDisputedLicensing(
  raw: KBLIRawCode,
): KBLIDisputedLicensing | null {
  for (const key of Object.keys(raw)) {
    if (!key.startsWith(DISPUTED_KEY_PREFIX)) continue;
    const rows = normalizeDisputedRows(
      raw[key as `per_skala_disputed_${string}`],
    );
    return { key, rows };
  }
  return null;
}

/**
 * True when the code SERVES licensing rows whose provenance is not verified
 * against a KBLI-2025-native OSS source (pending crosswalk, or unreadable
 * marker). Every surface that states risk/license/processing as fact for such
 * a code must qualify the claim (Codex gate round 4) — FAQ, JSON-LD, key-fact
 * grids all key on this single helper so they can't drift apart.
 */
export function isLicensingVerificationPending(code: KBLICode): boolean {
  const status = code.provenance?.licensing.status;
  return (
    code.licensing.length > 0 &&
    (status === "pending_crosswalk" || status === "unverified_source")
  );
}

/**
 * Derive the full provenance object for a raw KBLI record.
 *
 * State partition (exhaustive over the 1,559 catalog):
 * - `not_classifiable` — a `per_skala_disputed_*` block exists: a collision
 *   cure detached the rows; the divergence is documented in `_data_note`.
 * - `pending`  — `_l2_status === "no_oss_risk"`: OSS published no scope; any
 *   rows served were carried from KBLI-2020-vintage sources (PP 28/2025 via
 *   the 2020 numbering) and await crosswalk adjudication.
 * - `verified` — `_l2_source` EXACTLY equals the OSS-native marker
 *   (`OSS_RBA_resiko_2025`).
 * - fallback `pending` — a record with none of the markers, or an unknown
 *   `_l2_source` value, is treated as unaudited, never silently promoted to
 *   verified.
 */
export function deriveProvenance(raw: KBLIRawCode): KBLIProvenance {
  const disputed = getDisputedLicensing(raw);
  const noOssRisk = raw._l2_status === NO_OSS_RISK;
  // EXACT marker match — a future/unknown `_l2_source` value must degrade to
  // pending, never silently promote to "OSS-verified" (Codex gate F4).
  const ossNative = raw._l2_source === OSS_NATIVE_L2;
  // An unknown-but-present marker means the provenance claim itself is
  // unverifiable — it beats every other licensing reading except a detach
  // (Codex gate F6: even alongside no_oss_risk, don't claim PP28/2020).
  const unknownL2 = raw._l2_source != null && !ossNative;

  const state = disputed
    ? "not_classifiable"
    : noOssRisk
      ? "pending"
      : ossNative
        ? "verified"
        : "pending";

  return {
    state,
    definition: {
      locator: raw._l1_source ?? null,
      assembly: raw._source ?? null,
    },
    licensing:
      state === "not_classifiable"
        ? {
            status: "detached",
            locator: null,
            vintage: null,
            noOssScope: noOssRisk,
          }
        : state === "pending"
          ? unknownL2 || !noOssRisk
            ? {
                // No recognised L2 marker (absent, or present-but-unknown —
                // even alongside no_oss_risk): we cannot state the rows'
                // source or vintage; asserting "PP28 via KBLI-2020" would
                // invent provenance (Codex gate F6). Declare the audit need.
                status: "unverified_source",
                locator: null,
                vintage: null,
                noOssScope: noOssRisk,
              }
            : {
                status: "pending_crosswalk",
                locator: null,
                // The no-scope set splits in two (live census 2026-07-17:
                // 114 vs 101): codes WITH rows carry PP28 rows recorded under
                // the KBLI-2020 numbering (vintage 2020); codes with ZERO rows
                // are special/sectoral-regime — there is no row to vintage.
                vintage: (raw.per_skala ?? []).length > 0 ? "2020" : null,
                noOssScope: true,
              }
          : {
              status: "oss_native",
              locator: OSS_NATIVE_L2,
              vintage: "2025",
              noOssScope: noOssRisk,
            },
    pma: {
      source: raw.pma_source ?? null,
      // Perpres 10/2021 + 49/2021 annexes are KBLI-2020-vintage across the
      // whole catalog (FATAL-2) — declared as pending until the per-code
      // crosswalk audit lands. This is a source-vintage disclosure, not a
      // claim that the value is wrong.
      vintage: "2020",
      status: "pending_crosswalk",
    },
    dataNote: raw._data_note ?? null,
    disputed,
  };
}
