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
 * The other KBLI codes this code's licensing rows were carried from, for a
 * surface that CAN qualify a claim — or null when there is nothing to declare.
 *
 * Complement of the `verifiedLicenseType` gate in `kbli-meta.ts`, and
 * deliberately the opposite behaviour: an indexed `<title>`/`<meta>` has no room
 * for a qualifier, so it goes SILENT; a page body has room, so it KEEPS the
 * licence type and says where it came from. Same fact, two surfaces, opposite
 * correct answers — which is why they are two helpers and not one flag.
 *
 * Requires rows to be served: a code with no licensing rows has no inherited
 * claim on screen to qualify, whatever `pp28_sources` says.
 */
export function licensingContentInheritedFrom(code: KBLICode): string[] | null {
  if ((code.licensing?.length ?? 0) === 0) return null;
  return code.provenance?.licensing?.contentInheritedFrom ?? null;
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
/** Does the official BPS crosswalk record KBLI-2020 ancestry?
 *
 * Structured markers only (cicatrix #3 — never prose), and by ENTITY rather than
 * truthiness: `bps_2020_ancestors` is an object, so a bare `if (raw.bps_2020_ancestors)`
 * would read an empty `{}` as "has ancestry". `pp28_sources` deliberately does
 * not count: it records which KBLI-2020-numbered PP 28 rows supplied licensing
 * content, not official predecessor identity.
 */
function hasAuthoritativeBps2020Ancestry(raw: KBLIRawCode): boolean {
  const bps = raw.bps_2020_ancestors?.codes;
  return Array.isArray(bps) && bps.length > 0;
}

/**
 * The OTHER codes this record's PP 28 licensing content was carried from, or
 * null when it is self-sourced or records no PP 28 source at all.
 *
 * Structured field only (cicatrix #3), and by ENTITY rather than truthiness:
 * membership of the record's OWN code in `pp28_sources` is what distinguishes
 * "this row is mine" from "this row is someone else's". A record that lists
 * its own code alongside others is NOT treated as inherited — it has a row of
 * its own, and the extra entries are supplements.
 *
 * Absence is not evidence: `pp28_sources` empty (175 codes) returns null, the
 * same answer as self-sourced, because there is nothing recorded to inherit
 * FROM. That is deliberately the permissive branch — this signal exists to
 * withdraw a claim, and withdrawing one on missing data would be asserting
 * inheritance we cannot show.
 */
export function pp28ContentInheritedFrom(raw: KBLIRawCode): string[] | null {
  const sources = (raw.pp28_sources ?? []).map(String).filter(Boolean);
  if (sources.length === 0) return null;
  const own = String(raw.kode_kbli_2025 ?? "");
  if (own && sources.includes(own)) return null;
  return sources;
}

/** Provenance of the foreign-ownership verdict — DERIVED, not a constant.
 *
 * The Perpres 10/2021 + 49/2021 annexes are KBLI-2020-vintage across the catalog
 * (FATAL-2), so a code with an authoritative BPS-recorded 2020 origin is
 * honestly described as
 * "vintage 2020, per-code crosswalk audit pending". A code with NO recorded 2020
 * BPS origin cannot be: there is nothing authoritative to crosswalk FROM, and
 * saying the crosswalk is
 * pending would imply a basis we cannot show. Neither branch claims the verdict is
 * wrong — both describe what our sources can and cannot trace.
 */
function pmaProvenance(raw: KBLIRawCode): KBLIProvenance["pma"] {
  const traceable = hasAuthoritativeBps2020Ancestry(raw);
  return {
    source: raw.pma_source ?? null,
    vintage: traceable ? "2020" : null,
    status: traceable ? "pending_crosswalk" : "untraceable_basis",
  };
}

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
  // Independent of every marker above: WHERE the PP 28 rows came from. Computed
  // once and attached to all FOUR licensing branches (detached,
  // unverified_source, pending_crosswalk, oss_native) so none can omit it.
  const contentInheritedFrom = pp28ContentInheritedFrom(raw);

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
            contentInheritedFrom,
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
                contentInheritedFrom,
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
                contentInheritedFrom,
              }
          : {
              status: "oss_native",
              locator: OSS_NATIVE_L2,
              vintage: "2025",
              noOssScope: noOssRisk,
              contentInheritedFrom,
            },
    pma: pmaProvenance(raw),
    dataNote: raw._data_note ?? null,
    disputed,
  };
}

// -----------------------------------------------------------------------------
// Bare-claim gates — for surfaces that CANNOT carry a qualifier
// -----------------------------------------------------------------------------
//
// `isLicensingVerificationPending` above gates surfaces that CAN qualify a claim
// (risk badge, FAQ, JSON-LD, key-fact grid): they default to SHOWING and add a
// "verification pending" marker. An indexed `<title>`/`<meta description>` has
// no room for that marker — Google indexes the sentence, not the footnote — so
// those surfaces need the POSITIVE complement: state the fact only when its
// provenance is affirmatively verified, and stay silent otherwise.
//
// The asymmetry is deliberate. Negative gating (`!pending`) would promote a
// record with an absent or unreadable provenance block to "verified" by default;
// these helpers return false in exactly that case. Added 2026-07-26 with the
// Batch-3 title/meta rewrite, which would otherwise have put 422 unverified
// "blocked in Bali" claims and 6 unverified risk/license claims into indexed
// titles (measured on the 1,559-code canonical, not estimated).

/**
 * True when the code's licensing rows are OSS-RBA KBLI-2025 native, i.e. the
 * risk tier and license type may be stated as bare fact on an unqualifiable
 * surface. False for pending-crosswalk, unverified-source, detached, rowless,
 * and — critically — for any record whose provenance block is missing.
 */
export function isLicensingVerifiedForBareClaim(code: KBLICode): boolean {
  // Every hop is optional-chained on purpose. `provenance?.licensing.status`
  // guards a null provenance and then THROWS on a non-null provenance that has
  // no `licensing` key — a malformed record would take the page down instead of
  // degrading, which is fail-open by crash. The types forbid that shape; the
  // dataset is regenerated by scripts that the types do not run over. Found by
  // an adversarial pass probing `{}` as provenance.
  return (
    (code.licensing?.length ?? 0) > 0 &&
    code.provenance?.licensing?.status === "oss_native"
  );
}

/**
 * True when the L4 Bali "blocked" verdict is strong enough to state without a
 * qualifier: blocked, HIGH confidence, and not flagged for review. The page
 * body states it at any confidence because `BaliStatusBadge` renders the
 * confidence and a "· needs review" marker alongside it; a `<title>` cannot.
 */
export function isBaliL4BlockVerifiedForBareClaim(code: KBLICode): boolean {
  const l4 = code.baliL4;
  return !!l4?.blocked && l4.confidence === "HIGH" && l4.needsReview !== true;
}
