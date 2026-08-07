import type { KBLICode } from "@/lib/kbli-types";
import { isLicensingVerificationPending } from "@/lib/kbli-provenance";
import {
  baliBlockClause,
  isNationalClosure,
  shouldShowReason,
} from "@/lib/kbli-bali-block";
import { pmaCapShape } from "@/lib/kbli-pma-shape";

export interface KbliFaqEntry {
  question: string;
  answer: string;
}

const KBLI_2025_POST_DEADLINE_NOTE =
  "The June 2026 KBLI 2025 transition window has closed; operators should verify the code's current OSS/NIB treatment before relying on it for licensing, reporting, or amendments.";

const KBLI_2025_MIGRATION_OVERDUE_NOTE =
  "The June 2026 KBLI 2025 transition window has closed. If an NIB still relies on legacy KBLI 2020 mappings, treat the migration as overdue and verify/remediate the OSS record before new license applications, amendments, LKPM, import approvals, or investor/worker sponsorship.";

/** Condition prose, spliced as its own sentence. */
function conditionClause(code: KBLICode): string {
  const c = code.pma.condition;
  if (!c) return "";
  // The splice used to run straight into the next sentence — live on /kbli/47111
  // as "Condition: UMKM only An Indonesian partner holds…". The dataset's
  // condition strings carry no terminal punctuation, so it is added here.
  return ` Condition: ${/[.!?]$/.test(c.trim()) ? c.trim() : `${c.trim()}.`}`;
}

/**
 * The TERBATAS answer, split out of the nested ternary it used to live in so the
 * extremes can be handled and tested.
 *
 * The old single string said "foreign ownership is capped at {cap}% … An
 * Indonesian partner holds the remaining shares" for EVERY restricted code. On
 * the two extremes that trailing clause is not merely clumsy: at 100% there are
 * no remaining shares, so the sentence was false — in the visible answer AND in
 * the FAQPage JSON-LD, which is the copy Google ingests (measured live on
 * /kbli/79110, 2026-07-29).
 */
function restrictedPmaAnswer(code: KBLICode): string {
  const head = `KBLI ${code.code} (${code.titleId})`;
  const cond = conditionClause(code);

  if (code.pma.capSpecial) {
    return `Conditionally. ${head} is TERBATAS with special distribution conditions (open to foreign ownership but subject to a special distribution-network/location requirement — verify the exact terms in OSS).${cond}`;
  }

  switch (pmaCapShape(code.pma)) {
    case "none":
      return `No. ${head} is TERBATAS, but the ceiling for foreign capital is 0% — in practice the activity is not available to a PT PMA and is held by an Indonesian-owned company.${cond}`;
    case "full":
    case "conditional":
      return `Yes, with conditions. ${head} is TERBATAS, but the restriction is not an ownership ceiling — foreign ownership may reach 100%. Verify the applicable conditions in OSS.${cond}`;
    default:
      return `Partially. ${head} is TERBATAS — foreign ownership is ${code.pma.capVerified ? "capped" : "indicatively capped (unverified)"} at ${code.pma.maxForeign}%.${cond} An Indonesian partner holds the remaining shares.`;
  }
}

export function buildKbliFaq(code: KBLICode): KbliFaqEntry[] {
  const baliBlocked = !!code.baliL4?.blocked;
  // GARUDA-FILIERA Fase-1 cure #4 (2026-07-17): the risk tier the earlier
  // ok/blocked Bali verdict depended on was carried over from a different
  // activity through a code-number collision and has been detached — Bali
  // applicability is genuinely unresolved, not "open" or "blocked".
  const baliNonClassifiable = code.baliL4?.status === "NON_CLASSIFICABILE";

  // A NATIONAL closure recorded in the Bali-scoped `l4_bali` field. Without this
  // branch the answer below ends "Outside Bali it is open to a PT PMA with no
  // local partner required" — published in the FAQPage JSON-LD Google ingests —
  // for the central bank, radioactive-waste collection, and seven bidang usaha a
  // presidential annex allocates to Koperasi/UMKM nationwide. The TERBUKA/100%
  // it leans on is the absence-from-the-annex default fill, not a permission.
  const nationallyClosed = isNationalClosure(code.baliL4?.status, code.code);

  const pmaAnswer =
    code.pma.status === "open"
      ? nationallyClosed
        ? `No — and not only in Bali. KBLI ${code.code} (${code.titleId}) is ${baliBlockClause(code.baliL4?.status)}, and that closure applies everywhere in Indonesia, so registering the activity in another province does not change the answer.${
            shouldShowReason(code.baliL4?.status, code.baliL4?.reason)
              ? ` ${code.baliL4?.reason}`
              : ""
          } Our records carry no confirmed national foreign-ownership ceiling for this activity: the 100% some rows display is a default applied when the investment list holds no specific entry, not a recorded permission.`
        : baliBlocked
          ? // The cause is DERIVED, and the record's own reason is gated by the same
            // rule the licensing frame uses. Both were hardcoded here: the clause
            // named UMKM and the 2026 moratorium together for EVERY blocking status
            // (the literal is asserted absent by test, so it is not repeated here),
            // and the reason was spliced unconditionally. Measured on the canonical of
            // 2026-07-27: 455 pages reach this branch, 416 of them carry a status the
            // hardcoded clause misnames, and `69104` served Italian ("Notaio/PPAT è
            // ufficio personale e statale, solo WNI…") — in the visible answer AND in
            // the FAQPage JSON-LD, which is the copy Google ingests.
            `Nationally yes — but NOT in Bali. KBLI ${code.code} (${code.titleId}) is TERBUKA (100% foreign ownership) at the national level, but in Bali it is ${baliBlockClause(code.baliL4?.status)}.${
              shouldShowReason(code.baliL4?.status, code.baliL4?.reason)
                ? ` ${code.baliL4?.reason}`
                : ""
            } Outside Bali it is open to a PT PMA with no local partner required.`
          : baliNonClassifiable
            ? `Nationally yes — but Bali applicability cannot be determined yet. KBLI ${code.code} (${code.titleId}) is TERBUKA (100% foreign ownership) at the national level; whether Bali's PMA moratorium applies to this specific activity is not yet classifiable, pending re-derivation of the correct risk tier. Verify with the Bali Zero team before planning a Bali setup.`
            : `Yes. KBLI ${code.code} (${code.titleId}) is TERBUKA — open to 100% foreign ownership via PT PMA. No local Indonesian partner required.`
      : code.pma.status === "restricted"
        ? restrictedPmaAnswer(code)
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

  // The gold editorial prose and the OSS record's risk tier share nothing on
  // 30 codes (gold_risk_dispute_relation.py). Never enumerate the editorial
  // side's tier here — see the RENDER CONTRACT in kbli-risk-dispute.ts.
  const riskDisputeQualifier = code.riskDispute
    ? " Note: the editorial guide on this page describes a different risk tier for this activity; the divergence is under review — verify the current tier on oss.go.id."
    : "";

  const licenseAnswer =
    code.licensing.length > 0
      ? `KBLI ${code.code} has a ${code.licensing[0].riskCategory} risk classification. Required license: ${code.licensing[0].licenseType ?? "NIB (Nomor Induk Berusaha)"}. ${code.licensing[0].timeframe ? `Processing time: ${code.licensing[0].timeframe}.` : "Processed through OSS (Online Single Submission)."}${licenseQualifier}${riskDisputeQualifier}`
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
