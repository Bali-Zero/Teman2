import type { KBLICode } from "@/lib/kbli-types";
import { isLicensingVerificationPending } from "@/lib/kbli-provenance";

export interface KbliFaqEntry {
  question: string;
  answer: string;
}

const KBLI_2025_POST_DEADLINE_NOTE =
  "The June 2026 KBLI 2025 transition window has closed; operators should verify the code's current OSS/NIB treatment before relying on it for licensing, reporting, or amendments.";

const KBLI_2025_MIGRATION_OVERDUE_NOTE =
  "The June 2026 KBLI 2025 transition window has closed. If an NIB still relies on legacy KBLI 2020 mappings, treat the migration as overdue and verify/remediate the OSS record before new license applications, amendments, LKPM, import approvals, or investor/worker sponsorship.";

/**
 * Single source of truth for the per-code FAQ.
 *
 * Feeds BOTH the FAQPage JSON-LD (KBLIFaqJsonLd) and the visible
 * "Common Questions" section (KBLICommonQuestions). Google requires
 * FAQPage markup content to be visible on the page — before this module
 * the JSON-LD was emitted on every page while the visible Q&A only
 * existed on non-Gold layouts, and the two texts had drifted apart
 * (the JSON-LD carried the Bali-block qualification, the visible answer
 * did not; the visible answer handled capSpecial, the JSON-LD did not).
 * One builder = the markup is honest by construction.
 *
 * Every fact below comes from dataset fields already rendered elsewhere
 * on the same page (PMA verdict banner, licensing table, transition
 * note) — no new regulatory claims.
 */
export function buildKbliFaq(code: KBLICode): KbliFaqEntry[] {
  const baliBlocked = !!code.baliL4?.blocked;
  // GARUDA-FILIERA Fase-1 cure #4 (2026-07-17): the risk tier the earlier
  // ok/blocked Bali verdict depended on was carried over from a different
  // activity through a code-number collision and has been detached — Bali
  // applicability is genuinely unresolved, not "open" or "blocked".
  const baliNonClassifiable = code.baliL4?.status === "NON_CLASSIFICABILE";

  const pmaAnswer =
    code.pma.status === "open"
      ? baliBlocked
        ? `Nationally yes — but NOT in Bali. KBLI ${code.code} (${code.titleId}) is TERBUKA (100% foreign ownership) at the national level, but a PT PMA currently cannot register it in Bali (reserved for UMKM / 2026 moratorium). ${code.baliL4?.reason ?? "See the Bali status above."} Outside Bali it is open to a PT PMA with no local partner required.`
        : baliNonClassifiable
          ? `Nationally yes — but Bali applicability cannot be determined yet. KBLI ${code.code} (${code.titleId}) is TERBUKA (100% foreign ownership) at the national level; whether Bali's PMA moratorium applies to this specific activity is not yet classifiable, pending re-derivation of the correct risk tier. Verify with the Bali Zero team before planning a Bali setup.`
          : `Yes. KBLI ${code.code} (${code.titleId}) is TERBUKA — open to 100% foreign ownership via PT PMA. No local Indonesian partner required.`
      : code.pma.status === "restricted"
        ? code.pma.capSpecial
          ? `Conditionally. KBLI ${code.code} (${code.titleId}) is TERBATAS with special distribution conditions (open to foreign ownership but subject to a special distribution-network/location requirement — verify the exact terms in OSS).${code.pma.condition ? ` Condition: ${code.pma.condition}` : ""}`
          : `Partially. KBLI ${code.code} (${code.titleId}) is TERBATAS — foreign ownership is ${code.pma.capVerified ? "capped" : "indicatively capped (unverified)"} at ${code.pma.maxForeign}%.${code.pma.condition ? ` Condition: ${code.pma.condition}` : ""} An Indonesian partner holds the remaining shares.`
        : `No. KBLI ${code.code} (${code.titleId}) is TERTUTUP — closed to foreign investment. Reserved for Indonesian nationals only.`;

  // PMA source attribution with vintage (FATAL-2 axis): the investment-list
  // annexes are the in-force regulation but predate KBLI 2025 — disclose the
  // source and the pending per-code crosswalk instead of asserting bare fact.
  const pmaSourceNote =
    " (Source: Perpres 10/2021 as amended by Perpres 49/2021 — the investment-list annexes predate KBLI 2025; per-code crosswalk audit in progress.)";

  // Rows whose provenance is not KBLI-2025-native (crosswalk pending /
  // unreadable marker) must never be stated as unqualified fact — visible FAQ
  // and FAQPage JSON-LD both come from this builder (Codex gate round 4).
  const licenseQualifier = isLicensingVerificationPending(code)
    ? " Note: the source of these rows has not been verified against a KBLI-2025-native OSS scope; per-code crosswalk adjudication is pending — verify before relying on them (see Sources & Verification on this page)."
    : "";

  const licenseAnswer =
    code.licensing.length > 0
      ? `KBLI ${code.code} has a ${code.licensing[0].riskCategory} risk classification. Required license: ${code.licensing[0].licenseType ?? "NIB (Nomor Induk Berusaha)"}. ${code.licensing[0].timeframe ? `Processing time: ${code.licensing[0].timeframe}.` : "Processed through OSS (Online Single Submission)."}${licenseQualifier}`
      : // No OSS-RBA scale rows. Discriminated by the structured provenance
        // state (TRACK-P), never by prose:
        code.provenance?.state === "not_classifiable"
        ? // Cure-detached. The marker only attests that the old block was
          // quarantined — the CAUSE varies per code (digit collision,
          // wrong-pointer transplant, unlocatable source; the correction note
          // carries the specifics). So this class string is the WEAKEST common
          // truthful claim: it speaks about our verification, never asserts
          // regulatory absence (Codex gate F1).
          `We cannot yet show a verified licensing basis for KBLI ${code.code}: the licensing previously associated with this code was removed because its source could not be verified as applying to this activity. See the Regulatory Divergence section on this page for the documented sources, and verify the current OSS treatment before relying on any licensing assumption.`
        : // Special/sectoral regime (government, finance/OJK, education, health,
          // culture …). Claiming "requires a NIB via OSS" here would be wrong
          // for most of these activities. Wording per F12: a 404 attests
          // retrievability via the OSS API, never publication or absence.
          `KBLI ${code.code} sits outside the ordinary OSS-RBA risk-based licensing flow: no business-scale licensing rows for it are retrievable from OSS. Activities in this group are typically licensed under a special or sectoral regime (e.g. government affairs, financial services under OJK/BI, education or health authorities) — verify the applicable regulator case-by-case before relying on an NIB alone.`;

  // Only show an English gloss when a real English title exists — otherwise the
  // copy degenerates to `"X" (X)` with the Indonesian title repeated twice.
  const enGloss =
    code.titleEnIsReal && code.titleEn !== code.titleId
      ? ` (${code.titleEn})`
      : "";

  const entries: KbliFaqEntry[] = [
    {
      question: `Can foreigners operate a ${code.titleEn.toLowerCase()} business in Indonesia?`,
      answer: `${pmaAnswer}${pmaSourceNote}`,
    },
    {
      question: `What license is required for KBLI ${code.code}?`,
      answer: licenseAnswer,
    },
    {
      question: `What is KBLI ${code.code}?`,
      answer: `KBLI ${code.code} is the Indonesian business classification code for "${code.titleId}"${enGloss}. It falls under Section ${code.section ?? "N/A"} of KBLI 2025, the Indonesian Standard Industrial Classification updated by BPS (Regulation 7/2025). ${KBLI_2025_POST_DEADLINE_NOTE}`,
    },
  ];

  if (code.transition.previousCodes.length > 0) {
    const mappingStatusNote =
      code.transition.mappingStatus === "MATCH_LANGSUNG"
        ? " This is a direct match — the code number and scope remained the same."
        : code.transition.mappingStatus === "CODICE_RINUMERATO"
          ? " The code was renumbered but the business activity scope is essentially unchanged."
          : code.transition.mappingStatus === "MATCH_CON_AGGREGAZIONE"
            ? " Multiple 2020 codes were merged into this single 2025 code."
            : "";
    entries.push({
      question: `How did KBLI ${code.code} change from KBLI 2020 to 2025?`,
      answer: `KBLI ${code.code} was mapped from previous code${code.transition.previousCodes.length > 1 ? "s" : ""} ${code.transition.previousCodes.join(", ")} (KBLI 2020).${code.transition.mappingNote ? ` ${code.transition.mappingNote}` : ""}${mappingStatusNote} ${KBLI_2025_MIGRATION_OVERDUE_NOTE}`,
    });
  }

  return entries;
}
