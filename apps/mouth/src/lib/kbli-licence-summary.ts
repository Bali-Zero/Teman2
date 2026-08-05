/**
 * Single resolver for the licence line the KBLI explorer copies to a client's
 * clipboard.
 *
 * Why this file exists: `kbli-explorer/page.tsx` built that line as
 * `data.licenses.map((l) => l.type).join(", ") || "None"`. That fallback is an
 * ASSERTION — "this business needs no licence" — manufactured out of the
 * ABSENCE of data, and unlike a rendered page it TRAVELS: the string is pasted
 * into emails, quotes and chat threads, far from any caveat on screen.
 *
 * Measured on prod 2026-08-05: **284 of 1,559 codes render `licenses: []`**, and
 * canonical states obligations for **125** of them — so for those the duties are
 * known to us and the copied line still said "None". `07101` (iron sand mining)
 * is the sharp case: `licensing_status: REGULATED`, `risk_profile: Tinggi`,
 * `licenses: []` → `Licenses: None`.
 *
 * Only ONE status means "genuinely no OSS licence": `NOT_APPLICABLE_OSS` (75
 * codes). `REGULATED` (1,266), `PENDING_REGULATION` (217), `NOT_IN_KBLI_2025`
 * (4) and a null status (6) all mean we merely hold no licence rows — a gap, to
 * be DECLARED rather than asserted away. Same doctrine as `_resolve_risk_profile`
 * returning "Not classified" instead of a made-up "Low" (Zero, 2026-07-17):
 * honest gap over false reassurance.
 */

import {
  isSourceTruncated,
  TRUNCATION_NOTE,
} from "./kbli-obligation-truncation";

/**
 * A licence NAME can itself stop mid-sentence: measured on prod 2026-08-05, the
 * knowledge graph holds a licence node literally called **`"NIB dan"`** ("NIB
 * and") reachable from **10** KBLI codes, and `"Sertifikasi Cara Budi Daya
 * Ternak Yang"` from 2 more. The endpoint sets `licenses[].type` straight from
 * that node name (`kbli_notebook.py`: `type=lic["name"]`), so it reaches the
 * licence cards AND this clipboard line — which travels into client emails.
 *
 * A truncated name is LABELLED, never trimmed and never replaced: "NIB dan" is
 * a real fragment of a real requirement, and inventing its ending would be the
 * plausible-but-wrong assertion. Same rule and same detector as the obligation
 * text (`kbli-obligation-truncation.ts`), so the two cannot drift apart.
 */

/** Shown when we hold no licence rows and cannot say none are required. */
export const LICENCE_GAP_LABEL = "Not listed in our data";

/** Shown only for the one status that genuinely means no OSS licence applies. */
export const LICENCE_NONE_LABEL = "None (outside OSS licensing)";

/** The only `licensing_status` under which an empty list means "none required". */
export const STATUS_NO_LICENCE_REQUIRED = "NOT_APPLICABLE_OSS";

export function summariseLicences(
  types: readonly (string | null | undefined)[],
  licensingStatus?: string | null,
): string {
  const named = types
    .map((t) => (t ?? "").trim())
    .filter(Boolean)
    .map((t) => (isSourceTruncated(t) ? `${t} [\u2026${TRUNCATION_NOTE}]` : t));
  if (named.length > 0) return named.join(", ");
  return licensingStatus === STATUS_NO_LICENCE_REQUIRED
    ? LICENCE_NONE_LABEL
    : LICENCE_GAP_LABEL;
}
