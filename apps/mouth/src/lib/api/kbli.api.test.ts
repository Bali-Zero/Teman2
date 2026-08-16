import { describe, expect, it } from "vitest";

import {
  apiPmaPresentation,
  apiPmaStatusLabel,
  isApiPmaVerdictVerified,
  type KBLIPmaDisclosure,
} from "./kbli.api";

const GAP_01111: KBLIPmaDisclosure = {
  pma_status: "TERBUKA",
  pma_max_asing: 100,
  pma_cap_special: false,
  pma_cap_verified: false,
  pma_verification_status: "declared_gap",
  pma_official_basis: null,
  pma_source_vintage: null,
};

describe("KBLI API PMA disclosure", () => {
  it("fails closed for the real 01111 raw TERBUKA/100 shape", () => {
    expect(isApiPmaVerdictVerified(GAP_01111)).toBe(false);
    expect(apiPmaStatusLabel(GAP_01111)).toBe("PMA not verified");
  });

  it("requires every evidence field, not just the located marker", () => {
    expect(
      isApiPmaVerdictVerified({
        ...GAP_01111,
        pma_verification_status: "located",
      }),
    ).toBe(false);
    expect(
      isApiPmaVerdictVerified({
        ...GAP_01111,
        pma_verification_status: "located",
        pma_official_basis: "Perpres 49/2021 Lampiran III",
        pma_source_vintage: "2021-05-25",
      }),
    ).toBe(true);
  });

  it("keeps a located verdict but qualifies every label until its cap is verified", () => {
    const closedWithoutCap: KBLIPmaDisclosure = {
      ...GAP_01111,
      pma_status: "TERTUTUP",
      pma_max_asing: null,
      pma_verification_status: "located",
      pma_official_basis: "Perpres 49/2021 Lampiran III",
      pma_source_vintage: "2021-05-25",
    };

    expect(isApiPmaVerdictVerified(closedWithoutCap)).toBe(true);
    expect(apiPmaPresentation(closedWithoutCap)).toMatchObject({
      status: "closed",
      capVerified: false,
      statusLabel: "TERTUTUP · ownership cap not verified",
      ownershipLabel:
        "Closed to Foreign Investment · ownership cap not verified",
      compactLabel: "Closed to Foreigners · ownership cap not verified",
    });
  });

  it("publishes only a finite numeric or exact marked-special cap", () => {
    const located = {
      ...GAP_01111,
      pma_status: "TERBATAS",
      pma_verification_status: "located",
      pma_official_basis: "Perpres 49/2021 Lampiran III",
      pma_source_vintage: "2021-05-25",
      pma_cap_verified: true,
    } satisfies KBLIPmaDisclosure;

    expect(apiPmaPresentation({ ...located, pma_max_asing: 49 })).toMatchObject(
      { capVerified: true, statusLabel: "TERBATAS" },
    );
    expect(
      apiPmaPresentation({
        ...located,
        pma_max_asing: "special",
        pma_cap_special: false,
      }),
    ).toMatchObject({
      capVerified: false,
      statusLabel: "TERBATAS · ownership cap not verified",
    });
    expect(
      apiPmaPresentation({
        ...located,
        pma_max_asing: "special",
        pma_cap_special: true,
      }),
    ).toMatchObject({ capVerified: true, statusLabel: "TERBATAS" });
  });

  it("fails closed for an unknown status even with complete provenance", () => {
    const future = {
      ...GAP_01111,
      pma_status: "FUTURE_STATUS",
      pma_verification_status: "located",
      pma_official_basis: "Perpres 49/2021 Lampiran III",
      pma_source_vintage: "2021-05-25",
    };

    expect(isApiPmaVerdictVerified(future)).toBe(false);
    expect(apiPmaStatusLabel(future)).toBe("PMA not verified");
  });

  it("fails closed without throwing when runtime provenance is non-text", () => {
    const malformed = {
      ...GAP_01111,
      pma_verification_status: "located",
      pma_official_basis: { locator: "not text" },
      pma_source_vintage: ["2021-05-25"],
    } as unknown as KBLIPmaDisclosure;

    expect(isApiPmaVerdictVerified(malformed)).toBe(false);
    expect(apiPmaStatusLabel(malformed)).toBe("PMA not verified");
  });
});
