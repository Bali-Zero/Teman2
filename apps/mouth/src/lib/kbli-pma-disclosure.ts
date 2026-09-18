import type {
  KBLIBaliL4,
  KBLIPmaInfo,
  KBLIPmaStatus,
  KBLIProvenance,
  KBLIRawCode,
} from "./kbli-types";
import { shouldShowReason } from "./kbli-bali-block";
import { knownPmaRawStatus } from "./kbli-provenance";
import { humanizeInternalEnums } from "./kbli-status-labels";

const ALLOWED_BALI_STATUSES = new Set([
  "APERTO_BALI_RISCHIO_ALTO",
  "ATTENZIONE_FASCIA_BALI",
  "BLOCCATO_CLASSE_RISCHIO",
  "BLOCCATO_DIPENDE_SCOPE",
  "CHIUSO_BALI",
  "CHIUSO_BALI_PROPOSTO",
  "CHIUSO_MORATORIA_BALI",
  "CHIUSO_PMA_NO_BESAR",
  "CHIUSO_REGOLATORE_SETTORIALE",
  "NON_CLASSIFICABILE",
  "OK_or_HIGHER_RISK",
  "TERBATAS",
  "TERTUTUP",
]);

/**
 * Is `s` one of the L4 Bali statuses this disclosure layer recognizes?
 *
 * Exported so `kbli-data.ts`'s `getBaliCensus()` reuses the SAME allow-list
 * instead of re-declaring it — a second list drifts the moment one status is
 * added here and not there. `test_kbli_pma_disclosure_ts_sync.py` parses the
 * `ALLOWED_BALI_STATUSES` declaration above by regex, so its shape (a single
 * `const ALLOWED_BALI_STATUSES = new Set([...])` literal) must not change.
 */
export function isAllowedBaliStatus(s: string): boolean {
  return ALLOWED_BALI_STATUSES.has(s);
}

function publicText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** Same as `publicText`, but only for a value that is actually an http(s) URL. */
function publicUrl(value: unknown): string | null {
  const text = publicText(value);
  return text && /^https?:\/\//i.test(text) ? text : null;
}

function publicPmaCap(raw: KBLIRawCode): number | "special" | null {
  if (raw.pma_cap_verified !== true) return null;
  const cap: unknown = raw.pma_max_asing;
  if (typeof cap === "number" && Number.isFinite(cap)) return cap;
  if (cap === "special" && raw.pma_cap_special === true) return "special";
  return null;
}

export function normalizedPmaStatus(value: unknown): KBLIPmaStatus {
  const known = knownPmaRawStatus(value);
  if (known === "TERBUKA") return "open";
  if (known === "TERBATAS") return "restricted";
  if (known === "TERTUTUP") return "closed";
  return "unknown";
}

/** True only when generated prose may safely repeat a cap assertion. */
export function hasPublishablePmaCap(pma: KBLIPmaInfo): boolean {
  if (pma.verificationStatus !== "located" || pma.capVerified !== true) {
    return false;
  }
  if (typeof pma.maxForeign === "number") {
    return Number.isFinite(pma.maxForeign);
  }
  return pma.maxForeign === "special" && pma.capSpecial === true;
}

/**
 * Public whole-code PMA disclosure. The canonical source may retain legacy
 * values as internal evidence, but no presenter receives them until the
 * compiler-owned located+basis+vintage tuple verifies the verdict.
 */
export function disclosePmaInfo(
  raw: KBLIRawCode,
  provenance: KBLIProvenance,
  citation: string | null = null,
): KBLIPmaInfo {
  if (provenance.pma.status !== "located") {
    return {
      status: "unknown",
      maxForeign: null,
      condition: null,
      isPriority: false,
      note: null,
      source: null,
      verificationStatus: "declared_gap",
      officialBasis: null,
      sourceVintage: null,
      capSpecial: false,
      capVerified: false,
      routeTo: null,
      citation: null,
    };
  }

  const maxForeign = publicPmaCap(raw);
  return {
    status: normalizedPmaStatus(raw.pma_status),
    maxForeign,
    condition: publicText(raw.pma_kondisi),
    isPriority: raw.pma_prioritas === true,
    note: publicText(raw.pma_nota),
    source: publicText(raw.pma_source),
    verificationStatus: "located",
    officialBasis: provenance.pma.locator,
    sourceVintage: provenance.pma.vintage,
    capSpecial: maxForeign === "special",
    capVerified: maxForeign !== null,
    routeTo: publicText(raw.pma_route_to),
    citation: publicText(citation),
  };
}

/**
 * Public ownership wording shared by visible and indexed surfaces. A located
 * TERBUKA/TERBATAS status does not manufacture a percentage: numeric wording
 * additionally requires a finite public cap and its explicit verification
 * flag. This keeps malformed future rows from becoming `null%` or `100%`.
 */
export function formatPmaOwnership(
  pma: KBLIPmaInfo,
  style: "compact" | "metadata" = "compact",
): string {
  if (pma.verificationStatus !== "located" || pma.status === "unknown") {
    return style === "metadata"
      ? "Foreign Ownership Not Yet Verified"
      : "Not verified — confirm in OSS";
  }

  const cap =
    typeof pma.maxForeign === "number" && Number.isFinite(pma.maxForeign)
      ? pma.maxForeign
      : null;
  const special = pma.capSpecial === true && pma.maxForeign === "special";

  if (!hasPublishablePmaCap(pma)) {
    if (pma.status === "open") {
      return style === "metadata"
        ? "Open to Foreign Investment (ownership cap not verified)"
        : "Open · ownership cap not verified";
    }
    if (pma.status === "restricted") {
      return style === "metadata"
        ? "Foreign Ownership Restricted (ownership cap not verified)"
        : "Restricted · ownership cap not verified";
    }
    return style === "metadata"
      ? "Closed to Foreign Investment (ownership cap not verified)"
      : "Closed · ownership cap not verified";
  }

  if (pma.status === "closed") {
    return style === "metadata"
      ? "Closed to Foreign Investment"
      : cap === 0
        ? "Closed (0%)"
        : "Closed";
  }

  if (special) {
    return style === "metadata"
      ? "Foreign Ownership Subject to Special Non-Percentage Conditions"
      : "Special non-percentage conditions";
  }

  // Defensive narrowing if a future cap shape and the shared gate drift.
  if (cap === null) {
    return pma.status === "open"
      ? style === "metadata"
        ? "Open to Foreign Investment (ownership cap not verified)"
        : "Open · ownership cap not verified"
      : style === "metadata"
        ? "Foreign Ownership Restricted (ownership cap not verified)"
        : "Restricted · ownership cap not verified";
  }

  if (pma.status === "open") {
    if (cap === 0) {
      return style === "metadata"
        ? "Closed to Foreign Investment"
        : "Closed (0%)";
    }
    return style === "metadata" ? `${cap}% Foreign Ownership` : `${cap}% Open`;
  }

  if (cap === 0) {
    return style === "metadata"
      ? "Closed to Foreign Investment"
      : "Closed (0%)";
  }
  if (cap >= 100) {
    return style === "metadata"
      ? "Foreign Ownership Restricted by Non-Percentage Conditions"
      : "Conditions apply";
  }
  return style === "metadata"
    ? `Restricted (max ${cap}% foreign)`
    : `Max ${cap}%`;
}

/**
 * A Bali APPLIED closure is self-sufficient evidence, independent of the
 * NATIONAL PMA tuple.
 *
 * Every other Bali status this file discloses (ATTENZIONE_FASCIA_BALI, an
 * unresolved risk tier, a proposed-not-enacted closure, …) is a READING of
 * some other fact — the national verdict, a moratorium letter, a risk class —
 * so withholding it until that fact is located is the right, fail-closed
 * default. `CHIUSO_BALI` with `blocked: true` and a public `closure.url` is
 * different in kind: it is Bali's OWN provincial government, in its own named
 * instrument (`closure.url`, always a public press release), stating it
 * closed OSS to new PMA licensing for THIS business field. That fact does not
 * become less true because the unrelated NATIONAL open/restricted/closed
 * tuple has no located locator+vintage — the two are different sovereigns
 * making different statements. A record failing this check (wrong status,
 * `blocked` false, or no verifiable URL) still requires the national tuple,
 * same as before: this is an ADDITIONAL sufficient condition, never a looser
 * replacement for it.
 *
 * The URL is re-validated http(s)-only HERE too (review F6), not merely
 * assumed safe because `discloseBaliL4` already ran it through `publicUrl`
 * before this function ever sees it: `isSourcedBaliClosure` is exported and
 * called from render surfaces on the ALREADY-disclosed `KBLIBaliL4`, but a
 * defensive function that trusts its caller's caller is a check in name
 * only — the same discipline `discloseBaliL4`'s own comment states for
 * `closureSourceNode`.
 */
export function isSourcedBaliClosure(
  l4:
    | {
        status?: string | null;
        blocked?: boolean | null;
        closure?: { url?: string | null } | null;
      }
    | null
    | undefined,
): boolean {
  const url = l4?.closure?.url;
  return (
    l4?.status === "CHIUSO_BALI" &&
    l4?.blocked === true &&
    typeof url === "string" &&
    /^https?:\/\//i.test(url.trim())
  );
}

/**
 * Public Bali disclosure. Ordinarily subordinate to the complete national PMA
 * tuple (an allow-listed status plus actual source booleans) — EXCEPT for a
 * sourced applied closure (`isSourcedBaliClosure`, checked below against the
 * ALREADY-built, already-`publicUrl`-filtered disclosure), which discloses on
 * its own provincial evidence even when the national verdict is not located.
 */
export function discloseBaliL4(
  raw: KBLIRawCode,
  pmaVerdictLocated: boolean,
): KBLIBaliL4 | undefined {
  const l4 = raw.l4_bali;
  if (!l4) return undefined;
  if (
    typeof l4.status !== "string" ||
    !ALLOWED_BALI_STATUSES.has(l4.status) ||
    typeof l4.blocked !== "boolean" ||
    typeof l4.needs_review !== "boolean"
  ) {
    return undefined;
  }

  const confidence = ["HIGH", "MEDIUM", "LOW"].includes(String(l4.confidence))
    ? l4.confidence
    : "MEDIUM";
  const moratorium = l4.moratorium
    ? {
        rule: publicText(l4.moratorium.rule) ?? "",
        effective: publicText(l4.moratorium.effective) ?? "",
        source: publicText(l4.moratorium.source) ?? "",
        virtualOffice: publicText(l4.moratorium.virtual_office) ?? "",
      }
    : undefined;

  // The applied-closure citation (CHIUSO_BALI only). Every URL is re-verified
  // http(s)-only here, at the ONE place that turns raw data into something a
  // component may render as a link — a component must never re-check a URL
  // it is handed, or the check exists in name only.
  const rawClosure = l4.closure;
  const closure =
    rawClosure && typeof rawClosure === "object"
      ? {
          instrument: publicText(rawClosure.instrument) ?? undefined,
          published: publicText(rawClosure.published) ?? undefined,
          url: publicUrl(rawClosure.url),
          listSource: publicText(rawClosure.list_source) ?? undefined,
          listUrl: publicUrl(rawClosure.list_url),
          effective: publicText(rawClosure.effective) ?? undefined,
          until: publicText(rawClosure.until) ?? undefined,
          approval: publicText(rawClosure.approval) ?? undefined,
          ancestors2020: Array.isArray(rawClosure.ancestors_2020)
            ? rawClosure.ancestors_2020.filter(
                (x): x is string => typeof x === "string" && x.trim() !== "",
              )
            : undefined,
          scopeQualifier: publicText(rawClosure.scope_qualifier),
        }
      : undefined;

  // A BLOCKED code whose `reason` is the generator's moratorium-test note
  // ("medium-high/high risk → not blocked by moratorium (verify per address)")
  // or Italian has no client-facing reason: `shouldShowReason` already
  // withholds it after the block clause in the licensing frame and the FAQ,
  // but the Bali badge (`discloseKbliBaliReason`) and the gold baliContext
  // swap in kbli-data.server.ts read `reason` unfiltered. Withheld HERE, at
  // the one raw→public seam, so no consumer can print it beneath a "closed"
  // pill. Non-blocked codes are untouched — there the note is coherent
  // ("the moratorium test cleared it"). Added 2026-09-18 (naso PR-3): the 59
  // statutory closures it locates carry the note on 57 records; 0 of the 72
  // codes located before it are affected (asserted on the real dataset).
  const rawReason = publicText(l4.reason) ?? "";
  const reason =
    l4.blocked && !shouldShowReason(l4.status, rawReason) ? "" : rawReason;

  const disclosed: KBLIBaliL4 = {
    status: l4.status,
    reason: humanizeInternalEnums(reason),
    confidence: confidence ?? "MEDIUM",
    needsReview: l4.needs_review,
    blocked: l4.blocked,
    from2020: publicText(l4.from_2020),
    moratorium,
    closure,
  };

  // The national tuple is irrelevant to a provincial closure (see
  // `isSourcedBaliClosure`'s doc comment) — but every OTHER Bali status on an
  // unlocated national record stays hidden exactly as before. Checked against
  // `disclosed`, not `raw`: `closure.url` above already went through
  // `publicUrl`, so a non-http(s) URL (or a missing one) fails this check and
  // the record is withheld, same as today.
  if (!pmaVerdictLocated && !isSourcedBaliClosure(disclosed)) {
    return undefined;
  }

  return disclosed;
}
