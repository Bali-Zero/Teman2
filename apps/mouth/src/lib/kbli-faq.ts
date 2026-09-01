import type { KBLICode } from "@/lib/kbli-types";
import {
  isLicensingVerificationPending,
  isPmaVerdictVerified,
} from "@/lib/kbli-provenance";
import {
  baliBlockClause,
  isNationalClosure,
  shouldShowReason,
} from "@/lib/kbli-bali-block";
import { pmaCapShape } from "@/lib/kbli-pma-shape";
import { formatPmaOwnership } from "@/lib/kbli-pma-disclosure";
import { riskLabelEn } from "@/lib/kbli-derive";
import { pmaSourceNoteFaq } from "@/lib/kbli-pma-source";

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

  if (code.pma.capVerified !== true) {
    return `Restricted, with the ownership cap not yet verified. ${head} is TERBATAS; do not rely on any percentage or special-cap claim until it is confirmed in OSS.${cond}`;
  }

  if (
    code.pma.capVerified === true &&
    code.pma.capSpecial === true &&
    code.pma.maxForeign === "special"
  ) {
    return `Conditionally. ${head} is TERBATAS with special distribution conditions (open to foreign ownership but subject to a special distribution-network/location requirement — verify the exact terms in OSS).${cond}`;
  }

  if (
    typeof code.pma.maxForeign !== "number" ||
    !Number.isFinite(code.pma.maxForeign)
  ) {
    return `Restricted. ${head} is TERBATAS, but the public record does not carry a publishable ownership cap. Verify the exact ceiling and conditions in OSS.${cond}`;
  }

  switch (pmaCapShape(code.pma)) {
    case "none":
      return `No. ${head} is TERBATAS, but the ceiling for foreign capital is 0% — in practice the activity is not available to a PT PMA and is held by an Indonesian-owned company.${cond}`;
    case "full":
    case "conditional":
      return `Yes, with conditions. ${head} is TERBATAS, but the restriction is not an ownership ceiling — foreign ownership may reach 100%. Verify the applicable conditions in OSS.${cond}`;
    default: {
      // The trailing absolute is only true when there IS no condition
      // narrating who may hold what — a code whose `pma.condition` already
      // says "listed insurers exempt" / "pre-2018 holdings grandfathered"
      // (65111 and its siblings, this fix-pack) contradicts itself if this
      // clause is appended after it: the condition just said an Indonesian
      // partner is NOT always required, and the trailing sentence asserts
      // the opposite as flat fact. Drop it whenever a condition is present;
      // the condition is the more specific, more correct statement.
      const remainderClause = cond
        ? ""
        : " An Indonesian partner holds the remaining shares.";
      return `Partially. ${head} is TERBATAS — foreign ownership is capped at ${code.pma.maxForeign}%.${cond}${remainderClause}`;
    }
  }
}

interface OpenPmaWording {
  claim: string;
  short: string;
  fullyOpen: boolean;
}

/** TERBUKA wording that never manufactures a 100% cap from the status alone. */
function openPmaWording(code: KBLICode): OpenPmaWording {
  if (
    code.pma.capVerified === true &&
    code.pma.capSpecial === true &&
    code.pma.maxForeign === "special"
  ) {
    return {
      claim:
        "open to foreign investment under special non-percentage conditions",
      short: "special non-percentage conditions",
      fullyOpen: false,
    };
  }

  const cap =
    typeof code.pma.maxForeign === "number" &&
    Number.isFinite(code.pma.maxForeign)
      ? code.pma.maxForeign
      : null;
  if (code.pma.capVerified !== true || cap === null) {
    return {
      claim: "recorded as TERBUKA, but its ownership cap is not verified",
      short: "ownership cap not verified",
      fullyOpen: false,
    };
  }
  if (cap === 0) {
    return {
      claim:
        "not available to foreign capital because the verified ceiling is 0%",
      short: "0% foreign ownership",
      fullyOpen: false,
    };
  }
  if (cap === 100) {
    return {
      claim: "open to 100% foreign ownership via PT PMA",
      short: "100% foreign ownership",
      fullyOpen: true,
    };
  }
  return {
    claim: `open to up to ${cap}% foreign ownership via PT PMA`,
    short: `up to ${cap}% foreign ownership`,
    fullyOpen: false,
  };
}

export function buildKbliFaq(code: KBLICode): KbliFaqEntry[] {
  const baliBlocked = code.baliL4?.blocked === true;
  const exactSpecialCap =
    code.pma.capVerified === true &&
    code.pma.capSpecial === true &&
    code.pma.maxForeign === "special";
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
  const nationallyClosed =
    isNationalClosure(code.baliL4?.status, code.code) ||
    (!exactSpecialCap &&
      (code.pma.status === "closed" ||
        (code.pma.capVerified && code.pma.maxForeign === 0)));
  const pmaVerdictVerified = isPmaVerdictVerified(code);
  const openWording = openPmaWording(code);
  const outsideBali = openWording.fullyOpen
    ? "Outside Bali it is open to a PT PMA with no local partner required."
    : `Outside Bali, the national record is ${openWording.claim}; verify the exact ownership structure in OSS.`;

  // A slice-carrying code (perpres_slice_disclosure_relation.py — see the
  // qualifier built below) is TERBUKA on the WHOLE code while one narrower
  // activity inside it is not. The opening sentence of the TERBUKA answer
  // must say so UP FRONT: the old text opened on the flat promise ("Yes...
  // No local Indonesian partner required.") and appended the carve-out only
  // afterward — snippet truncation (search results, voice assistants,
  // anything that shows only the first sentence) serves the promise without
  // ever showing the carve-out. `carveOutPhrase` stays count-agnostic
  // because 30111 carries two rows (warship 49% + Pinisi/Cadik 0%), not one.
  const hasPerpresSlice = !!(code.perpresSlice && code.perpresSlice.length > 0);
  const carveOutPhrase = !code.perpresSlice
    ? ""
    : code.perpresSlice.length > 1
      ? `${code.perpresSlice.length} carve-outs`
      : "one carve-out";

  const pmaAnswer = !pmaVerdictVerified
    ? `Not yet verified. The canonical record carries a current PMA label for KBLI ${code.code} (${code.titleId}), but no adjudicated per-code official basis and source vintage verify that whole-code verdict. Confirm the current treatment at oss.go.id before planning a PT PMA.`
    : code.pma.status === "open"
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
            hasPerpresSlice
            ? // A REAL, live case (90200 — Sanggar seni): BROADER-adjudicated
              // AND Bali-blocked at once, independent axes. The "outside Bali
              // it is open, no partner required" tail moves to the qualifier
              // below (after the carve-out is named), same fix as the plain
              // branch — Bali blocking the whole code does not excuse
              // asserting the carve-out-free national picture up front.
              `Nationally this code is TERBUKA for most of its scope, with ${carveOutPhrase} — but NOT in Bali either way. KBLI ${code.code} (${code.titleId}) carries ${openWording.short} at the national level for most of the activity, but in Bali it is ${baliBlockClause(code.baliL4?.status)}.${
                shouldShowReason(code.baliL4?.status, code.baliL4?.reason)
                  ? ` ${code.baliL4?.reason}`
                  : ""
              }`
            : `National status: TERBUKA (${openWording.short}) — but NOT in Bali. KBLI ${code.code} (${code.titleId}) is ${baliBlockClause(code.baliL4?.status)} in Bali.${
                shouldShowReason(code.baliL4?.status, code.baliL4?.reason)
                  ? ` ${code.baliL4?.reason}`
                  : ""
              } ${outsideBali}`
          : baliNonClassifiable
            ? // No BROADER-adjudicated code currently reaches this branch
              // (checked live, 2026-08-07) — declared, not silently assumed
              // safe: a future one would still open on the unqualified "100%
              // foreign ownership at the national level" claim below. Left
              // unfixed rather than guessing untested wording; flag if one
              // ever lands here.
              `National status: TERBUKA (${openWording.short}) — but Bali applicability cannot be determined yet. Whether Bali's PMA moratorium applies to KBLI ${code.code} (${code.titleId}) is not yet classifiable, pending re-derivation of the correct risk tier. Verify with the Bali Zero team before planning a Bali setup.`
            : hasPerpresSlice
              ? `National status: TERBUKA for most of this code, with ${carveOutPhrase}. KBLI ${code.code} (${code.titleId}) is ${openWording.claim} for most of the activity.`
              : openWording.fullyOpen
                ? `Yes. KBLI ${code.code} (${code.titleId}) is TERBUKA — ${openWording.claim}. No local Indonesian partner required.`
                : `National status: TERBUKA. KBLI ${code.code} (${code.titleId}) is ${openWording.claim}. Verify the exact ownership structure in OSS before relying on the status.`
      : code.pma.status === "restricted"
        ? restrictedPmaAnswer(code)
        : `No. KBLI ${code.code} (${code.titleId}) is TERTUTUP — ${formatPmaOwnership(code.pma, "metadata")}. Reserved for Indonesian nationals only.`;

  // PMA source attribution with vintage (FATAL-2 axis): disclose the
  // instrument the RECORD itself names (kbli-pma-source.ts) instead of
  // hardcoding the Perpres investment-list default onto every code — the six
  // insurance codes this fix-pack cures are adjudicated under PP 14/2018
  // Pasal 5(1) jo. PP 3/2020, not the Perpres annexes, and attributing their
  // 80% cap to "Perpres 10/2021" would have named the wrong instrument.
  const pmaSourceNote = pmaSourceNoteFaq(
    code.pma.source,
    code.provenance?.pma.status ?? "declared_gap",
  );

  // BROADER-adjudicated codes render "100% open" correctly for the WHOLE
  // code while a narrower bidang usaha inside them carries a Perpres
  // Lampiran III foreign-cap condition (perpres_slice_disclosure_relation.py
  // — see the licensing-page frame in LicensingSection.tsx for the same
  // content in full). One compact qualifier sentence per row, followed by
  // ONE shared "rest of the code" closer (never per-row — a multi-row code
  // like 30111 would otherwise repeat a false "rest is open" claim right
  // after the very row that isn't). The closer's wording depends on whether
  // Bali also blocks the whole code (`baliBlocked`, independent axis).
  const perpresSliceQualifier = hasPerpresSlice
    ? " " +
      code
        .perpresSlice!.map((row) =>
          row.foreignCapPct === 0
            ? row.condition
              ? // A phased cap (0% at establishment, opening later — e.g.
                // 58130 press: 49% via capital market for expansion) is NOT
                // an absolute closure; render the condition instead of the
                // absolute "no foreign equity" claim, which would be false
                // for the expansion phase.
                `One specific activity inside this code — "${row.bidangUsaha}" — is reserved for domestic capital at establishment under Perpres 10/2021 (as amended) — ${row.condition}.`
              : `One specific activity inside this code — "${row.bidangUsaha}" — is reserved for domestic capital under Perpres 10/2021 (as amended): no foreign equity in that slice.`
            : `One specific activity inside this code — "${row.bidangUsaha}" — is capped at 49% foreign ownership under Perpres 10/2021 (as amended)${row.condition ? `, ${row.condition}` : ""}.`,
        )
        .join(" ") +
      (!pmaVerdictVerified
        ? " These narrower annex entries do not verify the current whole-code PMA verdict."
        : baliBlocked
          ? openWording.fullyOpen
            ? " Outside Bali, the rest of the code remains open to a PT PMA with no local partner required — subject to the Bali restriction stated above."
            : ` Outside Bali, the rest of the code is ${openWording.claim}; verify the exact ownership structure in OSS.`
          : openWording.fullyOpen
            ? " The rest of the code remains open to 100% foreign ownership with no local partner required."
            : ` The rest of the code is ${openWording.claim}; verify the exact ownership structure in OSS.`)
    : "";

  // Rows whose provenance is not KBLI-2025-native (crosswalk pending /
  // unreadable marker) must never be stated as unqualified fact — visible FAQ
  // and FAQPage JSON-LD both come from this builder (Codex gate round 4).
  const licenseQualifier = isLicensingVerificationPending(code)
    ? " Note: the source of these rows has not been verified against a KBLI-2025-native OSS scope; per-code crosswalk adjudication is pending — verify before relying on them (see Sources & Verification on this page)."
    : "";

  // The gold editorial prose and the OSS record's risk tier disagree on 33
  // codes — either sharing nothing (`zero_overlap`), or a universal "X at
  // every scale" claim a multi-tier record falsifies even when X is also
  // among the record's tiers (`universal_claim`). The two kinds are FALSE IN
  // DIFFERENT WAYS (gold_risk_dispute_relation.py) — a qualifier that always
  // says "describes a different risk tier" would itself be a lie on the 3
  // universal_claim codes, whose editorial tier IS in the record; only its
  // claimed universality is false. Round-3 finding. Never enumerate the
  // editorial side's tier here — see the RENDER CONTRACT in
  // kbli-risk-dispute.ts.
  const riskDisputeQualifier = code.riskDispute
    ? code.riskDispute.kind === "universal_claim"
      ? ` The editorial guide describes one tier as applying at every scale, while the record's licensing rows carry ${code.riskDispute.recordTiers.join(" / ")}; the two sources have not been reconciled — verify the current tier on oss.go.id before filing.`
      : " Note: the editorial guide on this page describes a different risk tier for this activity; the two sources have not been reconciled — verify the current tier on oss.go.id."
    : "";

  // A code WITH a riskDispute must not open on `licensing[0].riskCategory`
  // stated as flat fact — that IS the very fact under dispute (round-3 FIX
  // 5). `licensing[0]` is also still just one scope/scale row among several
  // when a record is multi-tier; the reader is directed at the structured
  // record tiers instead, then the kind-specific qualifier above.
  const licenseAnswer = code.riskDispute
    ? `The licensing rows on this record list ${code.riskDispute.recordTiers.join(" / ")} across its scopes and business scales.${licenseQualifier}${riskDisputeQualifier}`
    : code.licensing.length > 0
      ? `KBLI ${code.code} has a ${riskLabelEn(code.licensing[0].riskCategory) ?? code.licensing[0].riskCategory} risk classification. Required license: ${code.licensing[0].licenseType ?? "NIB (Nomor Induk Berusaha)"}. ${code.licensing[0].timeframe ? `Processing time: ${code.licensing[0].timeframe}.` : "Processed through OSS (Online Single Submission)."}${licenseQualifier}`
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
      answer: `${pmaAnswer}${perpresSliceQualifier}${pmaSourceNote}`,
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

  const bpsCodes = code.transition.bpsCrosswalk?.codes ?? [];
  const pp28Codes = code.transition.pp28LicensingSourceCodes;
  const transitionAnswer =
    bpsCodes.length > 0
      ? `According to the official BPS 2020 → 2025 crosswalk, KBLI ${code.code} has recorded KBLI 2020 ancestor(s) ${bpsCodes.join(", ")}. This is provenance only, not a licensing claim; no predecessor licensing regime is asserted to transfer.`
      : `No official BPS 2020 → 2025 crosswalk ancestor is recorded for this code. This is an ancestry data gap, not evidence that no KBLI 2020 predecessor existed.${
          pp28Codes.length > 0
            ? ` PP 28/2025 licensing-source codes recorded for this page: ${pp28Codes.join(", ")}. These are licensing citations, not official BPS ancestors.`
            : ""
        }`;
  entries.push({
    question: `How did KBLI ${code.code} change from KBLI 2020 to 2025?`,
    answer: `${transitionAnswer} ${KBLI_2025_MIGRATION_OVERDUE_NOTE}`,
  });

  return entries;
}
