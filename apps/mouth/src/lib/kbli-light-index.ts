import type { KBLICode } from "./kbli-types";
import {
  isLicensingVerificationPending,
  isPmaVerdictVerified,
} from "./kbli-provenance";

/**
 * KBLI light index — the instant first pass of the Navigator search.
 *
 * Built once at build time (app/kbli/search-index.json/route.ts, force-static)
 * from the same `getAllCodes()` list the 1,559 pages render, then fetched once
 * by KBLISearch and scored in the browser with the UNCHANGED `searchCodes`
 * (lib/kbli-search.ts). The API still answers every query and refines the
 * list; this index only removes the network wait from the first frame.
 *
 * Budget: gzip(JSON) ≤ 150 KB (BRIEF-v2 §3.4), measured by
 * kbli-light-index.test.ts against the real dataset. Keywords ride along
 * because `searchCodes` scores them; descriptions do not (they are the
 * weight, and the API covers them).
 *
 * Nothing here claims more than the page does: the ownership figure is only
 * carried when `isPmaVerdictVerified` holds AND the cap itself is verified
 * and numeric — the same gate PMABadge applies on the detail page.
 */
export interface KBLILightRow {
  /** code */
  c: string;
  /** English title */
  e: string;
  /** Indonesian title */
  i: string;
  /** section letter */
  s: string;
  /** keywords, "|"-joined (searchCodes scores them) */
  k?: string;
  /** tier: g | s | b */
  t: "g" | "s" | "b";
  /** verified national PMA status: o | r | c (absent = not verified) */
  p?: "o" | "r" | "c";
  /** verified numeric foreign-ownership cap, % (absent = not verified) */
  f?: number;
  /** first licensing row's risk category */
  r?: string;
  /** risk verification pending */
  rp?: 1;
  /** Bali L4 status + qualifiers, verbatim from the record */
  b?: string;
  bc?: "HIGH" | "MEDIUM" | "LOW";
  bn?: 1;
  bs?: string;
}

const PMA_SHORT = { open: "o", restricted: "r", closed: "c" } as const;
const PMA_LONG = { o: "open", r: "restricted", c: "closed" } as const;

export function buildKbliLightIndex(codes: KBLICode[]): KBLILightRow[] {
  return codes.map((code) => {
    const row: KBLILightRow = {
      c: code.code,
      e: code.titleEn,
      i: code.titleId,
      s: code.section ?? "",
      t: code.tier === "gold" ? "g" : code.tier === "silver" ? "s" : "b",
    };
    if (code.keywords.length > 0) row.k = code.keywords.join("|");
    if (isPmaVerdictVerified(code) && code.pma.status !== "unknown") {
      row.p = PMA_SHORT[code.pma.status];
      if (
        code.pma.capVerified === true &&
        typeof code.pma.maxForeign === "number" &&
        Number.isFinite(code.pma.maxForeign)
      ) {
        row.f = code.pma.maxForeign;
      }
    }
    const risk = code.licensing[0]?.riskCategory;
    if (risk) row.r = risk;
    if (isLicensingVerificationPending(code)) row.rp = 1;
    if (code.baliL4?.status) {
      row.b = code.baliL4.status;
      if (code.baliL4.confidence) row.bc = code.baliL4.confidence;
      if (code.baliL4.needsReview) row.bn = 1;
      const scope = code.baliL4.closure?.scopeQualifier;
      if (scope) row.bs = scope;
    }
    return row;
  });
}

export function lightPmaStatus(
  row: KBLILightRow,
): "open" | "restricted" | "closed" | undefined {
  return row.p ? PMA_LONG[row.p] : undefined;
}

/**
 * The minimum KBLICode shape `searchCodes` reads (code, titles, keywords,
 * description, tier, pma, licensing). Provenance is deliberately absent, so
 * `isPmaVerdictVerified` is false here and the index never earns the
 * verified-open ranking boost — only the API's answer can.
 */
export function lightRowsToSearchable(rows: KBLILightRow[]): KBLICode[] {
  return rows.map(
    (row) =>
      ({
        code: row.c,
        titleEn: row.e,
        titleId: row.i,
        section: row.s,
        description: "",
        keywords: row.k ? row.k.split("|") : [],
        tier: row.t === "g" ? "gold" : row.t === "s" ? "silver" : "bronze",
        pma: { status: "unknown", maxForeign: null },
        licensing: [],
      }) as unknown as KBLICode,
  );
}

export const KBLI_LIGHT_INDEX_URL = "/kbli/search-index.json";

let pending: Promise<KBLILightRow[] | null> | null = null;

/**
 * Fetch the index once per page life. Any failure resolves to null and the
 * search simply stays API-only — the index is an accelerator, never a gate.
 */
export function loadKbliLightIndex(): Promise<KBLILightRow[] | null> {
  if (pending) return pending;
  pending = (async () => {
    try {
      if (typeof window === "undefined" || typeof fetch !== "function") {
        return null;
      }
      const res = await fetch(KBLI_LIGHT_INDEX_URL);
      if (!res.ok) return null;
      const rows = (await res.json()) as unknown;
      return Array.isArray(rows) ? (rows as KBLILightRow[]) : null;
    } catch {
      return null;
    }
  })();
  return pending;
}
