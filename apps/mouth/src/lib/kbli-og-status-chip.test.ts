import { describe, expect, it } from "vitest";
import { getCode } from "@/lib/kbli-data";
import type { KBLICode } from "@/lib/kbli-types";
import { statusChip } from "./kbli-og-status-chip";

// Review F1(f): the social-preview chip must carry the same scope/confidence
// caveat as every other surface — `statusChip` is the pure label/color
// function extracted from the route (next/og's `ImageResponse` cannot be
// rendered under vitest, so this is the unit under test instead). Moved out
// of the route's own test file (review r2 BLOCKER B1): a Next.js route
// module may only export route handlers/config, so `statusChip` moved to
// `kbli-og-status-chip.ts` and this test moved with it.
describe("statusChip — the Bali closure's own scope/conservative-reading caveat", () => {
  it("68111 (unscoped, HIGH confidence, declared_gap nationally): bare 'BALI: CLOSED TO PMA'", () => {
    const kbli = getCode("68111") as KBLICode;
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4?.confidence).toBe("HIGH");
    expect(kbli.baliL4?.closure?.scopeQualifier).toBeFalsy();

    expect(statusChip(kbli)).toEqual({
      label: "BALI: CLOSED TO PMA",
      color: "#e0645a",
    });
  });

  it("55101 (Five-Star Hotel, scoped: building area under 6,000 m²): 'BALI: CLOSED — CHECK SCOPE', not the bare chip", () => {
    const kbli = getCode("55101") as KBLICode;
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4?.confidence).toBe("HIGH");
    expect(kbli.baliL4?.closure?.scopeQualifier).toBe(
      "building area under 6,000 m²",
    );

    expect(statusChip(kbli)).toEqual({
      label: "BALI: CLOSED — CHECK SCOPE",
      color: "#e0645a",
    });
  });

  it("47211 (MEDIUM confidence, unscoped): 'BALI: CLOSED — CHECK SCOPE', not the bare chip", () => {
    const kbli = getCode("47211") as KBLICode;
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4?.confidence).toBe("MEDIUM");
    expect(kbli.baliL4?.closure?.scopeQualifier).toBeFalsy();

    expect(statusChip(kbli)).toEqual({
      label: "BALI: CLOSED — CHECK SCOPE",
      color: "#e0645a",
    });
  });

  it("innocence: 55105 (located, verified Bali-blocked) keeps the original verified chip, not the new branch", () => {
    const kbli = getCode("55105") as KBLICode;
    expect(kbli.provenance?.pma.status).toBe("located");
    expect(kbli.baliL4).toMatchObject({ status: "CHIUSO_BALI", blocked: true });

    expect(statusChip(kbli)).toEqual({
      label: "BALI: BLOCKED",
      color: "#e0645a",
    });
  });

  it("innocence: a genuinely unlocated, non-sourced-closure code (62900) gets the neutral verify chip", () => {
    // 01192 was this test's example until naso PR-5 (residual lot 2) located
    // it. 62900 carries the same ATTENZIONE_FASCIA_BALI status and stays
    // declared_gap (withheld by that lot's legacy_pma_prose leg).
    const kbli = getCode("62900") as KBLICode;
    expect(kbli.provenance?.pma.status).toBe("declared_gap");
    expect(kbli.baliL4).toBeUndefined();

    expect(statusChip(kbli)).toEqual({
      label: "PMA: VERIFY",
      color: "#8f96a3",
    });
  });
});
