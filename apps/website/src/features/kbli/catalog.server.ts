// Keep the canonical KBLI engine, editorial certification and disclosure gates
// in Mouth. This module adapts presentation only; no dataset is copied or edited.
import {
  getAllCodes,
  getCode,
  getSections,
  getRelatedCodes,
} from "../../../../mouth/src/lib/kbli-data";
import { getGoldContent } from "../../../../mouth/src/lib/kbli-data.server";
import { searchCodes } from "../../../../mouth/src/lib/kbli-search";
import { formatPmaOwnership } from "../../../../mouth/src/lib/kbli-pma-disclosure";
import {
  isPmaVerdictVerified,
  isLicensingVerificationPending,
  licensingContentInheritedFrom,
} from "../../../../mouth/src/lib/kbli-provenance";
import { riskLabelEn } from "../../../../mouth/src/lib/kbli-derive";
import { BALI_STATUS_CONFIG } from "../../../../mouth/src/lib/kbli-status-labels";
import {
  discloseKbliEditorial,
  discloseKbliBaliReason,
} from "../../../../mouth/src/lib/kbli-pma-editorial";
import { buildKbliFaq } from "../../../../mouth/src/lib/kbli-faq";
import type {
  KBLICode,
  KBLIPmaStatus,
  KBLIRiskCategory,
} from "../../../../mouth/src/lib/kbli-types";
import type { CatalogItem } from "./types";

export {
  getAllCodes,
  getCode,
  getSections,
  getRelatedCodes,
  formatPmaOwnership,
  isPmaVerdictVerified,
  isLicensingVerificationPending,
  licensingContentInheritedFrom,
  riskLabelEn,
  buildKbliFaq,
  discloseKbliBaliReason,
};
export type { KBLICode };
export const PAGE_SIZE = 24;
export type SearchParams = Record<string, string | string[] | undefined>;
export const first = (value: string | string[] | undefined): string =>
  Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
export const riskOptions: KBLIRiskCategory[] = [
  "Rendah",
  "Menengah Rendah",
  "Menengah Tinggi",
  "Tinggi",
];

export function publicItem(code: KBLICode): CatalogItem {
  const pending = isLicensingVerificationPending(code);
  return {
    code: code.code,
    title: code.titleEn,
    titleId: code.titleId,
    section: code.section,
    sectionName: code.sectionName,
    ownership: formatPmaOwnership(code.pma),
    ownershipVerified: isPmaVerdictVerified(code),
    risks: [
      ...new Set(
        code.licensing
          .map((row) => riskLabelEn(row.riskCategory))
          .filter((risk): risk is string => risk !== null),
      ),
    ],
    licensingPending: pending,
    licensingInherited: licensingContentInheritedFrom(code) ?? [],
    bali: code.baliL4
      ? (BALI_STATUS_CONFIG[code.baliL4.status]?.label ??
        "Bali status requires review")
      : "Bali status not available",
    licenses: [...new Set(code.licensing.map((row) => row.licenseType))],
    predecessorCodes:
      code.transition.bpsCrosswalk?.codes ??
      code.transition.pp28LicensingSourceCodes,
  };
}

export function catalogSearch(params: SearchParams, fixedSection?: string) {
  const q = first(params.q).trim().slice(0, 200);
  const section = fixedSection ?? first(params.section);
  const pma = ["open", "restricted", "closed", "unknown"].includes(
    first(params.pma),
  )
    ? (first(params.pma) as KBLIPmaStatus)
    : undefined;
  const risk = riskOptions.includes(first(params.risk) as KBLIRiskCategory)
    ? (first(params.risk) as KBLIRiskCategory)
    : undefined;
  let codes = getAllCodes().filter(
    (code) => !section || code.section === section,
  );
  if (q)
    codes = searchCodes(codes, q, { pmaStatus: pma, riskCategory: risk }).map(
      (result) => result.code,
    );
  else
    codes = codes.filter(
      (code) =>
        (!pma ||
          (pma === "unknown"
            ? !isPmaVerdictVerified(code)
            : isPmaVerdictVerified(code) && code.pma.status === pma)) &&
        (!risk || code.licensing.some((row) => row.riskCategory === risk)),
    );
  const pages = Math.max(1, Math.ceil(codes.length / PAGE_SIZE));
  const page = Math.min(
    pages,
    Math.max(1, Number.parseInt(first(params.page), 10) || 1),
  );
  return {
    q,
    section,
    pma,
    risk,
    page,
    pages,
    count: codes.length,
    items: codes
      .slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
      .map(publicItem),
  };
}

export function publicEditorial(code: KBLICode) {
  return discloseKbliEditorial(code, getGoldContent(code.code));
}
