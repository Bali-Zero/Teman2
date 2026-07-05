import type { KBLICode } from "@/lib/kbli-types";

export interface KbliFaqEntry {
  question: string;
  answer: string;
}

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

  const pmaAnswer =
    code.pma.status === "open"
      ? baliBlocked
        ? `Nationally yes — but NOT in Bali. KBLI ${code.code} (${code.titleId}) is TERBUKA (100% foreign ownership) at the national level, but a PT PMA currently cannot register it in Bali (reserved for UMKM / 2026 moratorium). ${code.baliL4?.reason ?? "See the Bali status above."} Outside Bali it is open to a PT PMA with no local partner required.`
        : `Yes. KBLI ${code.code} (${code.titleId}) is TERBUKA — open to 100% foreign ownership via PT PMA. No local Indonesian partner required.`
      : code.pma.status === "restricted"
        ? code.pma.capSpecial
          ? `Conditionally. KBLI ${code.code} (${code.titleId}) is TERBATAS with special distribution conditions (open to foreign ownership but subject to a special distribution-network/location requirement — verify the exact terms in OSS).${code.pma.condition ? ` Condition: ${code.pma.condition}` : ""}`
          : `Partially. KBLI ${code.code} (${code.titleId}) is TERBATAS — foreign ownership is ${code.pma.capVerified ? "capped" : "indicatively capped (unverified)"} at ${code.pma.maxForeign}%.${code.pma.condition ? ` Condition: ${code.pma.condition}` : ""} An Indonesian partner holds the remaining shares.`
        : `No. KBLI ${code.code} (${code.titleId}) is TERTUTUP — closed to foreign investment. Reserved for Indonesian nationals only.`;

  const licenseAnswer =
    code.licensing.length > 0
      ? `KBLI ${code.code} has a ${code.licensing[0].riskCategory} risk classification. Required license: ${code.licensing[0].licenseType ?? "NIB (Nomor Induk Berusaha)"}. ${code.licensing[0].timeframe ? `Processing time: ${code.licensing[0].timeframe}.` : "Processed through OSS (Online Single Submission)."}`
      : `KBLI ${code.code} requires a NIB (Nomor Induk Berusaha) via OSS (Online Single Submission). Contact a licensed consultant for specific requirements.`;

  const entries: KbliFaqEntry[] = [
    {
      question: `Can foreigners operate a ${code.titleEn.toLowerCase()} business in Indonesia?`,
      answer: pmaAnswer,
    },
    {
      question: `What license is required for KBLI ${code.code}?`,
      answer: licenseAnswer,
    },
    {
      question: `What is KBLI ${code.code}?`,
      answer: `KBLI ${code.code} is the Indonesian business classification code for "${code.titleId}" (${code.titleEn}). It falls under Section ${code.section ?? "N/A"} of KBLI 2025, the Indonesian Standard Industrial Classification updated by BPS (Regulation 7/2025), effective June 18, 2026.`,
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
      answer: `KBLI ${code.code} was mapped from previous code${code.transition.previousCodes.length > 1 ? "s" : ""} ${code.transition.previousCodes.join(", ")} (KBLI 2020).${code.transition.mappingNote ? ` ${code.transition.mappingNote}` : ""}${mappingStatusNote} All businesses must migrate to KBLI 2025 by June 18, 2026 per BPS Regulation 7/2025.`,
    });
  }

  return entries;
}
