import type { KBLIPmaInfo, KBLIPmaStatus, KBLIRawCode } from "./kbli-types";

const ALLOWED_PMA_STATUSES = new Set(["TERBUKA", "TERBATAS", "TERTUTUP"]);

function publicText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function normalizedPmaStatus(value: unknown): KBLIPmaStatus {
  if (value === "TERBUKA") return "open";
  if (value === "TERBATAS") return "restricted";
  if (value === "TERTUTUP") return "closed";
  return "unknown";
}

export function hasLocatedPmaTuple(record: Record<string, unknown>): boolean {
  return (
    record.pma_verification_status === "located" &&
    typeof record.pma_status === "string" &&
    ALLOWED_PMA_STATUSES.has(record.pma_status) &&
    publicText(record.pma_official_basis) !== null &&
    publicText(record.pma_source_vintage) !== null
  );
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

function publicPmaCap(raw: KBLIRawCode): number | "special" | null {
  if (raw.pma_cap_verified !== true) return null;

  const cap: unknown = raw.pma_max_asing;
  if (typeof cap === "number" && Number.isFinite(cap)) return cap;
  if (cap === "special" && raw.pma_cap_special === true) return "special";
  return null;
}

export function disclosePmaInfo(raw: KBLIRawCode): KBLIPmaInfo {
  if (!hasLocatedPmaTuple(raw as unknown as Record<string, unknown>)) {
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
    officialBasis: publicText(raw.pma_official_basis),
    sourceVintage: publicText(raw.pma_source_vintage),
    capSpecial: maxForeign === "special",
    capVerified: maxForeign !== null && raw.pma_cap_verified === true,
    routeTo: publicText(raw.pma_route_to),
  };
}

/**
 * Render the public ownership verdict without inventing a percentage.
 * `TERBUKA` establishes the status, but only the separately disclosed cap may
 * establish a numeric ownership ceiling. This function is deliberately shared
 * by metadata and visible facts so they cannot drift into `null%` or a default
 * `100%` claim when the cap is absent or malformed.
 */
export function formatPmaOwnership(
  pma: KBLIPmaInfo,
  style: "compact" | "metadata" = "compact",
): string {
  if (pma.verificationStatus !== "located" || pma.status === "unknown") {
    return style === "metadata"
      ? "Foreign Ownership Not Yet Verified"
      : "Not yet verified";
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
