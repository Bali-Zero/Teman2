import notices from "../../data/kbli-pma-review-notices.json";
import type { KBLIRawCode } from "./kbli-types";

/**
 * Per-code PMA review notice (SAETTA-20260915/W-H PR-5).
 *
 * The 12 "hold" codes (no Perpres 10/2021 Lampiran I/II/III reservation, no
 * Usaha Besar row in OSS's current licensing snapshot) keep their national
 * PMA tuple at `declared_gap` — no 0%, no 100% is published — but the reader
 * deserves the SPECIFIC reason instead of the generic "not yet verified"
 * sentence every other unverified code shows. This is that specific text,
 * looked up by code and disclosed ONLY while the guarded raw fields still
 * match what the notice was authored against: a future data change (a new
 * OSS scale row, a re-adjudicated `pma_status`) silently WITHDRAWS the
 * notice instead of narrating a claim the record no longer supports.
 *
 * Idea from the unmerged `kbli-pma-resolution-astra` worktree
 * (`kbli-pma-review.ts` / `kbli-pma-review-notices.json`), rewritten here:
 * that draft matched on `pma_nota` (a field this cure never touches) and had
 * no dedicated key for the notice string.
 */

interface ReviewNoticeEntry {
  pma_status?: unknown;
  pma_max_asing?: unknown;
  pma_verification_status?: unknown;
  note: string;
}

const NOTICES: Record<string, ReviewNoticeEntry> = (
  notices as { notices: Record<string, ReviewNoticeEntry> }
).notices;

/** The notice text for `raw`, or null when no notice is registered for this
 * code, or the guarded fields have drifted since the notice was authored. */
export function pmaReviewNotice(raw: KBLIRawCode): string | null {
  const entry = NOTICES[raw.kode_kbli_2025];
  if (!entry) return null;
  const { note, ...guard } = entry;
  const rawRecord = raw as unknown as Record<string, unknown>;
  const drifted = Object.entries(guard).some(
    ([key, expected]) => rawRecord[key] !== expected,
  );
  return drifted ? null : note;
}
