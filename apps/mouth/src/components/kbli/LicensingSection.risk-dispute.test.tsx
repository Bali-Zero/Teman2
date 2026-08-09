// Round-3 gate BLOCKER 1 (2026-08-07): the risk-tier dispute frame always
// said "the editorial guide on this page describes a different tier" — true
// for `zero_overlap` disputes, FALSE for `universal_claim` ones (46100,
// 47901, 71109), whose editorial tier IS among the record's tiers; only its
// claimed UNIVERSALITY across scales is false. A frame that can't tell the
// two kinds apart is itself a lie on those three pages. This is a real
// render, using REAL disputed codes from the live artifact via kbli-data.ts
// (not synthetic overrides) — the strongest available proof that `kind`
// actually reaches the rendered DOM, not just the type.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getCode } from "@/lib/kbli-data";
import { LicensingSection } from "./LicensingSection";

describe("LicensingSection risk-dispute frame — kind branching", () => {
  it("universal_claim (46100) renders the universality wording, never 'describes a different tier'", () => {
    const kbli = getCode("46100");
    expect(kbli?.riskDispute?.kind).toBe("universal_claim");
    if (!kbli) throw new Error("46100 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(
      screen.getByText(
        /states one risk tier as applying at every business scale/,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/describes a different tier/)).toBeNull();
  });

  it("zero_overlap (82990) keeps the original wording, never the universality phrasing", () => {
    const kbli = getCode("82990");
    expect(kbli?.riskDispute?.kind).toBe("zero_overlap");
    if (!kbli) throw new Error("82990 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(screen.getByText(/describes a different tier/)).toBeInTheDocument();
    expect(
      screen.queryByText(
        /states one risk tier as applying at every business scale/,
      ),
    ).toBeNull();
  });

  it("both kinds render the shared 'not been reconciled' close", () => {
    for (const code of ["46100", "82990"]) {
      const kbli = getCode(code);
      if (!kbli) throw new Error(`${code} missing from kbli-data.ts`);
      const { unmount } = render(<LicensingSection kbli={kbli} gold={null} />);
      expect(screen.getByText(/have not been reconciled/)).toBeInTheDocument();
      unmount();
    }
  });

  it("a non-disputed code (56101) renders neither dispute sentence", () => {
    const kbli = getCode("56101");
    expect(kbli?.riskDispute).toBeUndefined();
    if (!kbli) throw new Error("56101 missing from kbli-data.ts");

    render(<LicensingSection kbli={kbli} gold={null} />);

    expect(screen.queryByText(/have not been reconciled/)).toBeNull();
  });
});
