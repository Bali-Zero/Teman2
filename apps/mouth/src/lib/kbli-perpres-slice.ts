import fs from "fs";
import path from "path";

/**
 * Codes whose WHOLE-CODE `pma.status` renders "100% open" (BROADER-adjudicated
 * — see `scripts/kbli_filiera/apply_perpres_foreign_caps.py`'s `ADJUDICATION`)
 * while a NARROWER bidang usaha inside them carries a Perpres 10/2021 (as
 * amended by 49/2021) Lampiran III foreign-ownership cap. `13133` (Industri
 * Kain Batik) is correctly 100% open as a whole code; "batik cap" (stamped
 * batik) specifically is reserved to domestic capital. A client filing under
 * 13133 for stamped-batik production would file "100% open" and be wrong
 * about the one activity they are actually doing.
 *
 * This module does NOT detect or adjudicate anything. The join (ancestor
 * lineage -> annex row), the two hand-authored 30111/30113 rows, the two
 * codes excluded as adjacent-not-contained (20235, 30303 — their own
 * ADJUDICATION reason says the annex activity is a neighbour, not something
 * inside the code) and the refusal conditions that guard all of it (a
 * BROADER code missing from the join; a cap outside {0, 49}; a code whose
 * own `pma_status` is not TERBUKA; an adjacent-not-contained exclusion whose
 * ADJUDICATION verdict or reason has drifted) live in
 * `scripts/kbli_filiera/perpres_slice_disclosure_relation.py` with its own
 * guilt/innocence corpus — re-implementing any of that here would make two
 * writers of one verdict (W105). That script emits
 * `data/kbli-perpres-slice-disclosures.json`; a pytest freshness check
 * recomputes the population and fails when the artifact is stale, so a NEW
 * disclosure cannot reach the page without riding along with the data change
 * that created it.
 *
 * FAIL-CLOSED, same contract as `kbli-risk-dispute.ts` (the pattern this
 * module is copied from): a missing file, unparseable JSON, a payload without
 * a `disclosures` key, an EMPTY `disclosures` object (the compiler never
 * emits zero entries — an empty map here is silent total data loss across
 * every page that should carry a notice), a `_meta.count` that disagrees
 * with the actual entry count, or a malformed per-entry/per-row shape all
 * THROW at first read rather than degrading to "no slice" — silently reading
 * a restricted code as unqualified-open is exactly the class of
 * client-facing lie this module exists to prevent. Every throw names the
 * `--emit` command that fixes it.
 */
export interface KBLIPerpresSliceRow {
  bidangUsaha: string;
  foreignCapPct: 0 | 49;
  condition: string | null;
  locator: string;
}

const SLICE_PATH = path.join(
  process.cwd(),
  "data",
  "kbli-perpres-slice-disclosures.json",
);

type RawSliceRow = {
  bidangUsaha?: unknown;
  foreignCapPct?: unknown;
  condition?: unknown;
  locator?: unknown;
};

function isValidCap(v: unknown): v is 0 | 49 {
  return v === 0 || v === 49;
}

let _cache: Record<string, KBLIPerpresSliceRow[]> | null = null;

function load(): Record<string, KBLIPerpresSliceRow[]> {
  if (_cache) return _cache;

  let raw: string;
  try {
    raw = fs.readFileSync(SLICE_PATH, "utf-8");
  } catch (err) {
    throw new Error(
      `[kbli] cannot read perpres slice-disclosure artifact at ${SLICE_PATH} ` +
        `— run \`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\` ` +
        `(${err instanceof Error ? err.message : String(err)})`,
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(
      `[kbli] perpres slice-disclosure artifact at ${SLICE_PATH} is not valid ` +
        `JSON — run \`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\` ` +
        `(${err instanceof Error ? err.message : String(err)})`,
    );
  }

  const disclosuresRaw = (parsed as { disclosures?: unknown } | null)
    ?.disclosures;
  if (
    disclosuresRaw === undefined ||
    disclosuresRaw === null ||
    typeof disclosuresRaw !== "object" ||
    Array.isArray(disclosuresRaw)
  ) {
    throw new Error(
      `[kbli] perpres slice-disclosure artifact at ${SLICE_PATH} has no ` +
        `"disclosures" object — run ` +
        `\`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
    );
  }

  const disclosures = disclosuresRaw as Record<string, unknown>;

  // The compiler never emits an empty population — 12 real codes as of
  // 2026-08-07 (10 general BROADER + 2 hand-authored) — so `{}` here is not
  // a legitimate "nothing to disclose" state, it is silent data loss: EVERY
  // page that should carry a slice notice would render "100% open"
  // unqualified with zero signal that anything is missing.
  const codes = Object.keys(disclosures);
  if (codes.length === 0) {
    throw new Error(
      `[kbli] perpres slice-disclosure artifact at ${SLICE_PATH} has an ` +
        `empty "disclosures" object — the compiler never emits zero ` +
        `entries, so this is corrupt or hand-edited, not a normal empty ` +
        `state; run ` +
        `\`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
    );
  }

  const metaCount = (parsed as { _meta?: { count?: unknown } } | null)?._meta
    ?.count;
  if (typeof metaCount !== "number" || metaCount !== codes.length) {
    throw new Error(
      `[kbli] perpres slice-disclosure artifact at ${SLICE_PATH} has ` +
        `_meta.count=${JSON.stringify(metaCount)} but "disclosures" carries ` +
        `${codes.length} entries — the two disagree on the population, ` +
        `which means the artifact was hand-edited or written by a stale ` +
        `compiler; run ` +
        `\`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
    );
  }
  _cache = Object.fromEntries(
    Object.entries(disclosures).map(([code, rowsRaw]) => {
      if (!Array.isArray(rowsRaw) || rowsRaw.length === 0) {
        throw new Error(
          `[kbli] perpres slice-disclosure artifact entry "${code}" has a ` +
            `missing or empty row list — the compiler never emits such an ` +
            `entry, so this is a corrupt artifact, not a normal empty ` +
            `state; run ` +
            `\`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
        );
      }
      const rows = (rowsRaw as RawSliceRow[]).map((row, i) => {
        if (typeof row.bidangUsaha !== "string" || row.bidangUsaha === "") {
          throw new Error(
            `[kbli] perpres slice-disclosure artifact entry "${code}" row ` +
              `${i} has a missing or empty "bidangUsaha" — run ` +
              `\`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
          );
        }
        if (!isValidCap(row.foreignCapPct)) {
          throw new Error(
            `[kbli] perpres slice-disclosure artifact entry "${code}" row ` +
              `${i} has an invalid "foreignCapPct" ` +
              `(${JSON.stringify(row.foreignCapPct)}), expected 0 or 49 — ` +
              `run \`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
          );
        }
        if (row.condition !== null && typeof row.condition !== "string") {
          throw new Error(
            `[kbli] perpres slice-disclosure artifact entry "${code}" row ` +
              `${i} has a non-null, non-string "condition" ` +
              `(${JSON.stringify(row.condition)}) — run ` +
              `\`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
          );
        }
        if (typeof row.locator !== "string" || row.locator === "") {
          throw new Error(
            `[kbli] perpres slice-disclosure artifact entry "${code}" row ` +
              `${i} has a missing or empty "locator" — run ` +
              `\`python3 scripts/kbli_filiera/perpres_slice_disclosure_relation.py --emit\``,
          );
        }
        return {
          bidangUsaha: row.bidangUsaha,
          foreignCapPct: row.foreignCapPct,
          condition: row.condition,
          locator: row.locator,
        } satisfies KBLIPerpresSliceRow;
      });
      return [code, rows];
    }),
  );
  return _cache;
}

/** The restricted Perpres slice(s) hiding inside a BROADER-open code, or null. */
export function perpresSlice(code: string): KBLIPerpresSliceRow[] | null {
  return load()[code] ?? null;
}

/** Test-only: drop the module cache so a test can point at a fresh file. */
export function _resetPerpresSliceCache(): void {
  _cache = null;
}
