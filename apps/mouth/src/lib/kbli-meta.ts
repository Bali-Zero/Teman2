// =============================================================================
// kbli-meta.ts — what a KBLI page may ASSERT on its indexed metadata surface
//
// Batch 3 (v3), prepared 2026-07-05 as PR #1967, resurrected 2026-07-26 after
// that PR was closed as collateral of the PII history-purge force-push.
//
// WHY THIS IS ITS OWN MODULE. v2 shipped 1,559 near-identical titles ending in
// "Indonesia Business Guide 2025", which answered neither of the long-tail
// query families this cluster can win (`KBLI [code] foreign ownership`,
// `KBLI [code] risk level`). v3 differentiates the suffix with the datum the
// query is actually asking for. That turns the <title> into a REGULATORY
// ASSERTION on 1,559 indexed pages — so the composition lives here, pure and
// unit-tested, instead of inline in a server component where nothing can
// exercise it.
//
// THE GATE. Every fact stated here is gated on affirmative provenance:
//   - risk tier + license type  → isLicensingVerifiedForBareClaim
//   - "blocked in Bali"         → isBaliL4BlockVerifiedForBareClaim
//   - foreign-ownership cap %   → kbli.pma.capVerified (pre-existing discipline)
// An ungated record degrades to a neutral suffix; it is never omitted from the
// page BODY, which can and does qualify the same claims (RiskBadge takes
// `verificationPending`, BaliStatusBadge takes `confidence` + `needsReview`).
// A <title> has no room for a qualifier, so it stays silent instead.
//
// Formulas + per-page quality checklist:
// research/seo/2026-07-05-batch3-title-meta-queue.md
// =============================================================================

import { riskLabelEn } from "./kbli-derive";
import {
  isBaliL4BlockVerifiedForBareClaim,
  isLicensingVerifiedForBareClaim,
} from "./kbli-provenance";
import type { KBLICode } from "./kbli-types";

/** Risk label safe to state bare, or null when provenance does not back it. */
export function verifiedRiskLabel(kbli: KBLICode): string | null {
  if (!isLicensingVerifiedForBareClaim(kbli)) return null;
  return riskLabelEn(kbli.licensing[0]?.riskCategory);
}

/** License type safe to state bare, or null. Only ever paired with the risk. */
export function verifiedLicenseType(kbli: KBLICode): string | null {
  if (!verifiedRiskLabel(kbli)) return null;
  return kbli.licensing[0]?.licenseType || "NIB";
}

/**
 * Human PMA label used in the description. Unchanged from v2 — `capSpecial`
 * and the cap % were already provenance-aware upstream.
 */
export function kbliPmaLabel(kbli: KBLICode): string {
  if (kbli.pma.status === "open") return "100% Foreign Ownership";
  if (kbli.pma.status !== "restricted") return "Closed to Foreign Investment";
  return kbli.pma.capSpecial
    ? "Restricted (special distribution conditions)"
    : `Restricted (max ${kbli.pma.maxForeign}% foreign)`;
}

/**
 * The differentiating title suffix. Order matters: a verified Bali block is the
 * strongest answer for an open code (the reader asking "can I do this in Bali"
 * is not served by "100% Foreign Ownership"), so it wins over the risk variant.
 * An UNVERIFIED Bali block falls through to the national fact, which is itself
 * verified — the Bali caveat is then carried by the page body, not the title.
 */
export function kbliMetaTitleSuffix(kbli: KBLICode): string {
  if (kbli.pma.status === "open") {
    if (isBaliL4BlockVerifiedForBareClaim(kbli)) {
      return "Blocked for PT PMA in Bali (2026)";
    }
    const risk = verifiedRiskLabel(kbli);
    return risk
      ? `100% Foreign Ownership, ${risk} Risk`
      : "100% Foreign Ownership";
  }
  if (kbli.pma.status === "restricted") {
    if (kbli.pma.capSpecial) return "Foreign Ownership With Conditions";
    return kbli.pma.capVerified
      ? `Max ${kbli.pma.maxForeign}% Foreign Ownership`
      : "Foreign Ownership Restricted";
  }
  return "Closed to Foreign Investment";
}

/** `<title>` for /kbli/[code]. `metaTitleEn` respects NEXT_PUBLIC_KBLI_META_EN. */
export function kbliMetaTitle(kbli: KBLICode, metaTitleEn: string): string {
  return `KBLI ${kbli.code}: ${metaTitleEn} — ${kbliMetaTitleSuffix(kbli)}`;
}

/** `<meta name="description">` — leads with the answer, then the gated facts. */
export function kbliMetaDescription(
  kbli: KBLICode,
  metaTitleEn: string,
): string {
  const baliBlocked =
    kbli.pma.status === "open" && isBaliL4BlockVerifiedForBareClaim(kbli);
  const risk = verifiedRiskLabel(kbli);
  const license = verifiedLicenseType(kbli);

  return [
    `${metaTitleEn} (KBLI ${kbli.code}): ${kbliPmaLabel(kbli)}${
      baliBlocked ? " nationally — blocked for a PT PMA in Bali (2026)" : ""
    }.`,
    risk && license ? `${risk} risk, license: ${license}.` : null,
    "KBLI 2025 rules + Bali notes by Bali Zero.",
  ]
    .filter(Boolean)
    .join(" ");
}
