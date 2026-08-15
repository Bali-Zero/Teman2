import type {
  KBLIBaliL4,
  KBLIPmaInfo,
  KBLIPmaStatus,
  KBLIProvenance,
  KBLIRawCode,
} from "./kbli-types";
import { knownPmaRawStatus } from "./kbli-provenance";
import { humanizeInternalEnums } from "./kbli-status-labels";

const ALLOWED_BALI_STATUSES = new Set([
  "APERTO_BALI_RISCHIO_ALTO",
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

function publicText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
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

  if (pma.status === "closed") {
    return style === "metadata"
      ? "Closed to Foreign Investment"
      : cap === 0 && pma.capVerified === true
        ? "Closed (0%)"
        : "Closed";
  }

  if (pma.capVerified !== true) {
    return pma.status === "open"
      ? style === "metadata"
        ? "Open to Foreign Investment (ownership cap not verified)"
        : "Open · ownership cap not verified"
      : style === "metadata"
        ? "Foreign Ownership Restricted (ownership cap not verified)"
        : "Restricted · ownership cap not verified";
  }

  if (special) {
    return style === "metadata"
      ? "Foreign Ownership Subject to Special Non-Percentage Conditions"
      : "Special non-percentage conditions";
  }

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
 * Public Bali disclosure. It is subordinate to the complete national PMA
 * tuple and requires an allow-listed status plus actual source booleans.
 */
export function discloseBaliL4(
  raw: KBLIRawCode,
  pmaVerdictLocated: boolean,
): KBLIBaliL4 | undefined {
  const l4 = raw.l4_bali;
  if (!pmaVerdictLocated || !l4) return undefined;
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

  return {
    status: l4.status,
    reason: humanizeInternalEnums(publicText(l4.reason) ?? ""),
    confidence: confidence ?? "MEDIUM",
    needsReview: l4.needs_review,
    blocked: l4.blocked,
    from2020: publicText(l4.from_2020),
    moratorium,
  };
}
