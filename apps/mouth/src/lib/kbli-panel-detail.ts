import type {
  KBLIBaliL4,
  KBLICode,
  KBLIPmaInfo,
  KBLIRiskCategory,
  KBLITransition,
} from "./kbli-types";
import {
  isLicensingVerificationPending,
  isPmaVerdictVerified,
} from "./kbli-provenance";

/**
 * The projection a KBLI code takes to be shown in the off-canvas drill-down.
 *
 * Why a projection and not the `KBLICode` itself: the drill-down renders on the
 * CLIENT (see KBLISectorOffcanvas for why the server cannot do it at this URL),
 * so whatever it needs crosses the wire for every code in the section. A full
 * KBLICode carries the per-scale licensing rows, the editorial layer and the
 * intel blocks — none of which this view shows.
 *
 * Licences, authority and timeframe are deliberately NOT here either, and the
 * reason is honesty rather than weight. Rendering them in this summary would
 * have made the panel a SECOND licensing surface with none of the framing the
 * vetted one has: `licenseType` is risk-DERIVED whenever `perizinan` is empty
 * (resolveLicenseType), which is the case for 10111 and its whole class, so a
 * bare "Licences:" line states as fact what the full page states as a
 * derivation; `KBLILicenseByScale.authority` is typed `string` but holds the
 * raw `kewenangan` ARRAY (kbli-data.ts:359), which React concatenates into
 * "Bupati/WalikotaMenteri/Kepala Badan…"; and `jangka_waktu` is a bare "15"
 * that only `formatTimeframe` knows how to render without inventing a unit.
 * All three already have a correct home in LicensingSection on `/kbli/[code]`,
 * one click away. (The `authority` type/shape mismatch is pre-existing and out
 * of scope here — it is reported, not fixed, by this change.)
 *
 * `description` (the KBLI `uraian`) is deliberately NOT here. Measured on a
 * production build: carrying it for all 464 codes of Section C took the
 * panel's payload from 34 KB to 124 KB gzipped — heavier than the 69 KB full
 * page this panel exists to save a trip to. Truncating it instead was the
 * other option and was rejected: cutting a legal scope description mid-sentence
 * is the exact failure `kbli-obligation-truncation.ts` exists to catch. The
 * prose lives one click away, on the page that always had it.
 *
 * The important half: this is a projection of the server's ALREADY-DISCLOSED
 * output, never a re-derivation of it. `isPmaVerdictVerified`,
 * `isLicensingVerificationPending` and `summariseLicences` run here, on the
 * server, exactly as they do inside KBLICard — the client receives verdicts,
 * not the inputs to a verdict it might resolve differently.
 */
export interface KBLIPanelDetail {
  code: string;
  titleEn: string;
  titleId: string;
  riskCategory: KBLIRiskCategory | null;
  riskVerificationPending: boolean;
  pma: Pick<
    KBLIPmaInfo,
    "status" | "maxForeign" | "capSpecial" | "capVerified"
  > & { verdictVerified: boolean };
  bali: Pick<KBLIBaliL4, "status"> & { blocked: boolean };
  transition: KBLITransition;
}

export function toPanelDetail(code: KBLICode): KBLIPanelDetail {
  const primary = code.licensing[0];
  const verdictVerified = isPmaVerdictVerified(code);

  return {
    code: code.code,
    titleEn: code.titleEn,
    titleId: code.titleId,
    riskCategory: primary?.riskCategory ?? null,
    riskVerificationPending: isLicensingVerificationPending(code),
    pma: {
      status: code.pma.status,
      maxForeign: code.pma.maxForeign,
      capSpecial: code.pma.capSpecial,
      capVerified: code.pma.capVerified,
      verdictVerified,
    },
    bali: {
      status: code.baliL4?.status ?? "",
      blocked: code.baliL4?.blocked === true,
    },
    transition: code.transition,
  };
}
