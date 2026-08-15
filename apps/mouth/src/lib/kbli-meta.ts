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
import { pmaCapShape } from "./kbli-pma-shape";
import { formatPmaOwnership } from "./kbli-pma-disclosure";
import {
  isBaliL4BlockVerifiedForBareClaim,
  isLicensingVerifiedForBareClaim,
  isPmaVerdictVerified,
} from "./kbli-provenance";
import type { KBLICode } from "./kbli-types";

/** Risk label safe to state bare, or null when provenance does not back it. */
export function verifiedRiskLabel(kbli: KBLICode): string | null {
  if (!isLicensingVerifiedForBareClaim(kbli)) return null;
  return riskLabelEn(kbli.licensing[0]?.riskCategory);
}

/**
 * License type safe to state bare, or null. Only ever paired with the risk.
 *
 * The second gate is NOT redundant with the first. `isLicensingVerifiedForBareClaim`
 * reads `_l2_source`, which names the OSS-RBA **risk** source; `pp28_sources`
 * separately records where the PP 28 licensing rows came from, and the two
 * disagree on **337** codes — risk genuinely 2025-native, licensing content
 * carried from other codes. `62110` (video game development) is sourced from
 * five 62xxx computer-programming codes and inherits three defence-industry
 * permits that way.
 *
 * So the risk label survives (it is verified) and the licence type goes silent
 * (it may belong to another code). One flag for both would suppress a true fact
 * to qualify a different one.
 */
export function verifiedLicenseType(kbli: KBLICode): string | null {
  if (!verifiedRiskLabel(kbli)) return null;
  if (kbli.provenance?.licensing?.contentInheritedFrom) return null;
  return kbli.licensing[0]?.licenseType || "NIB";
}

/**
 * Human PMA label used in the description.
 *
 * The v2 comment here claimed "the cap % was already provenance-aware
 * upstream". It was not, and the claim is the interesting part: the title path
 * gates `maxForeign` on `capVerified` and this one did not, so the same
 * unverified percentage that the title refused to state was printed in the
 * description of the same page. An adversarial pass found it; a sentence
 * asserting a surface is safe is not a check on that surface.
 *
 * Both surfaces now degrade identically when the cap is unverified.
 */
export function kbliPmaLabel(kbli: KBLICode): string {
  if (!isPmaVerdictVerified(kbli)) return "Foreign Ownership Not Yet Verified";
  if (kbli.pma.status === "open")
    return formatPmaOwnership(kbli.pma, "metadata");
  if (kbli.pma.status !== "restricted") return "Closed to Foreign Investment";
  if (
    kbli.pma.capVerified &&
    kbli.pma.capSpecial &&
    kbli.pma.maxForeign === "special"
  )
    return "Restricted (special distribution conditions)";
  if (!kbli.pma.capVerified) return "Restricted for foreign ownership";
  switch (pmaCapShape(kbli.pma)) {
    case "none":
      return "Closed to Foreign Investment";
    case "full":
    case "conditional":
      return "Restricted (conditions apply, no ownership cap)";
    default:
      return `Restricted (max ${kbli.pma.maxForeign}% foreign)`;
  }
}

/**
 * The differentiating title suffix. Order matters: a verified Bali block is the
 * strongest answer for an open code (the reader asking "can I do this in Bali"
 * is not served by "100% Foreign Ownership"), so it wins over the risk variant.
 * An UNVERIFIED Bali block falls through to the national fact, which is itself
 * verified — the Bali caveat is then carried by the page body, not the title.
 */
export function kbliMetaTitleSuffix(kbli: KBLICode): string {
  if (!isPmaVerdictVerified(kbli))
    return "PMA Eligibility Requires Verification";
  if (kbli.pma.status === "open") {
    if (kbli.pma.capVerified && kbli.pma.maxForeign === 0) {
      return "Closed to Foreign Investment";
    }
    if (isBaliL4BlockVerifiedForBareClaim(kbli)) {
      return "Blocked for PT PMA in Bali (2026)";
    }
    const risk = verifiedRiskLabel(kbli);
    const ownership = formatPmaOwnership(kbli.pma, "metadata");
    return risk ? `${ownership}, ${risk} Risk` : ownership;
  }
  if (kbli.pma.status === "restricted") {
    // Even the non-percentage special regime is a cap claim and therefore
    // requires the explicit cap-verification flag.
    if (
      kbli.pma.capVerified &&
      kbli.pma.capSpecial &&
      kbli.pma.maxForeign === "special"
    )
      return "Foreign Ownership With Conditions";
    if (!kbli.pma.capVerified) return "Foreign Ownership Restricted";
    switch (pmaCapShape(kbli.pma)) {
      // A 0% ceiling is not a share on offer. Outcome-identical to the 61
      // TERTUTUP codes, which already say exactly this — 47111 missed the
      // wording only because it is classified TERBATAS.
      case "none":
        return "Closed to Foreign Investment";
      // "Max 100%" restricts nothing. Whatever binds here is a condition, so
      // it borrows the phrasing capSpecial already uses.
      case "full":
      case "conditional":
        return "Foreign Ownership With Conditions";
      default:
        return `Max ${kbli.pma.maxForeign}% Foreign Ownership`;
    }
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
    // Degrade one fact at a time. `risk && license ? … : null` dropped BOTH
    // when only the licence was ungated, so the 337 inherited-content codes
    // would have lost a risk tier that is verified — silence about what we
    // cannot back, not silence about everything near it.
    risk && license
      ? `${risk} risk, license: ${license}.`
      : risk
        ? `${risk} risk.`
        : null,
    "KBLI 2025 rules + Bali notes by Bali Zero.",
  ]
    .filter(Boolean)
    .join(" ");
}
