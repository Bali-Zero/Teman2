import { createHash } from "node:crypto";

import certifications from "../../../../data/kbli-filiera/pma-editorial-certifications.json";
import { hasPublishablePmaCap } from "./kbli-pma-disclosure";
import type { KBLIPmaInfo } from "./kbli-types";

type Certification = {
  pmaFingerprint: string;
  contentSha256: string;
};

type CertificationSection = Record<string, Certification>;

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value !== null && typeof value === "object") {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((result, key) => {
        const item = (value as Record<string, unknown>)[key];
        if (item !== undefined) result[key] = stableValue(item);
        return result;
      }, {});
  }
  return value;
}

/** Stable JSON hash shared with the checked-in review registry generator. */
export function stableEditorialSha256(value: unknown): string {
  const serialized = JSON.stringify(stableValue(value));
  if (serialized === undefined) return "";
  return createHash("sha256").update(serialized).digest("hex");
}

/**
 * Fingerprint every public PMA field that legacy prose could repeat. Citation
 * is deliberately excluded because the standalone app has no citation field;
 * locator and vintage remain mandatory and are included here.
 */
export function pmaEditorialFingerprint(pma: KBLIPmaInfo): string {
  return stableEditorialSha256({
    status: pma.status,
    maxForeign: pma.maxForeign,
    condition: pma.condition,
    isPriority: pma.isPriority,
    note: pma.note,
    source: pma.source,
    verificationStatus: pma.verificationStatus,
    officialBasis: pma.officialBasis,
    sourceVintage: pma.sourceVintage,
    capSpecial: pma.capSpecial,
    capVerified: pma.capVerified,
    routeTo: pma.routeTo,
  });
}

function matchesCertification(
  section: CertificationSection,
  code: string,
  pma: KBLIPmaInfo,
  content: unknown,
): boolean {
  if (!hasPublishablePmaCap(pma) || content === null || content === undefined) {
    return false;
  }
  const certification = section[code];
  return (
    certification !== undefined &&
    certification.pmaFingerprint === pmaEditorialFingerprint(pma) &&
    certification.contentSha256 === stableEditorialSha256(content)
  );
}

export function hasCertifiedCanonicalIntel(
  code: string,
  pma: KBLIPmaInfo,
  content: unknown,
): boolean {
  return matchesCertification(
    certifications.canonicalIntel as CertificationSection,
    code,
    pma,
    content,
  );
}

export function hasCertifiedMouthGold(
  code: string,
  pma: KBLIPmaInfo,
  content: unknown,
): boolean {
  return matchesCertification(
    certifications.mouthGold as CertificationSection,
    code,
    pma,
    content,
  );
}

export function neutralKbliChatOpenerText(code: string): string {
  return `Ask me about KBLI ${code}: its official scope, licensing, risk, or foreign-ownership verification.`;
}

/** Replace legacy sales/status claims only after the whole block certifies. */
export function withNeutralKbliChatOpener<T extends { zantaraOpener?: string }>(
  code: string,
  content: T,
): T {
  return {
    ...content,
    zantaraOpener: neutralKbliChatOpenerText(code),
  };
}
