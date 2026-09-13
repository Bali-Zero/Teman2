import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CHECKLIST_ITEMS, readiness } from "@/lib/secondhome-studio/checklist";
import { getCopy } from "@/lib/secondhome-studio/copy";
import { emptyPlan } from "@/lib/secondhome-studio/plan-codec";
import type { PlanState, Verdict } from "@/lib/secondhome-studio/types";

import { ReadinessChecklist } from "./ReadinessChecklist";

function basePlan(overrides: Partial<PlanState> = {}): PlanState {
  return { ...emptyPlan(), ...overrides };
}

const noopVerdict: Verdict = {
  band: "edge_case",
  product: null,
  reasons: [],
  humanReviewNote: null,
};

/** Parses the FLOOR argument out of a CSS clamp() string, e.g.
 *  "clamp(1.5rem, 3vw, 1.75rem)" -> "1.5rem", so a failure prints the
 *  actual offending size instead of a bare boolean. */
function parseClampFloor(clamp: string): string {
  const match = clamp.match(/^clamp\(\s*([^,]+),/);
  if (!match) {
    throw new Error(`Expected a clamp() value, got: "${clamp}"`);
  }
  return match[1].trim();
}

describe("ReadinessChecklist", () => {
  it("pins the Cormorant floor at 1.5rem (R4 §3: display serif never below 24px)", () => {
    render(
      <ReadinessChecklist
        plan={basePlan()}
        verdict={noopVerdict}
        onToggle={vi.fn()}
      />,
    );
    const heading = screen.getByRole("heading", { level: 2 });

    expect(heading.style.fontFamily).toBe("var(--font-serif, Georgia, serif)");
    expect(parseClampFloor(heading.style.fontSize)).toBe("1.5rem");
  });

  it("meter counts only the applicable group, never the full 10-item union", () => {
    const verdict1: Verdict = {
      band: "strong_fit",
      product: "E33",
      reasons: [],
      humanReviewNote: null,
    };
    const plan1 = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
      checklist: { bank_deposit_evidence: true, passport_bio_page: true },
    });
    const { done: done1, total: total1 } = readiness(plan1, verdict1);

    const { rerender } = render(
      <ReadinessChecklist plan={plan1} verdict={verdict1} onToggle={vi.fn()} />,
    );
    expect(
      screen.getByText(
        `${done1} of ${total1} ${getCopy("checklist.readiness.preparedLabel")}`,
      ),
    ).toBeInTheDocument();
    // Never the full union — that was the measured defect this fix cures.
    expect(total1).not.toBe(CHECKLIST_ITEMS.length);
    // The DOM-rendered "applies to your answers" group has exactly
    // `total1` items — not CHECKLIST_ITEMS.length, and not some other count.
    const applicableHeading = screen.getByRole("heading", {
      name: getCopy("checklist.groups.applicableHeading"),
    });
    expect(applicableHeading.parentElement?.querySelectorAll("li").length).toBe(
      total1,
    );

    // A second, differently-shaped plan reaches a DIFFERENT denominator —
    // proves `total` tracks classification, not a constant.
    const verdict2: Verdict = {
      band: "strong_fit",
      product: "E33",
      reasons: [],
      humanReviewNote: null,
    };
    const plan2 = basePlan({
      age: "under_55",
      route: "property",
      property: "owns_qualifying_strata",
      family: { spouse: true, children: 0, parents: 0 },
      checklist: {
        property_documents: true,
        family_records: true,
        passport_bio_page: true,
      },
    });
    const { done: done2, total: total2 } = readiness(plan2, verdict2);
    rerender(
      <ReadinessChecklist plan={plan2} verdict={verdict2} onToggle={vi.fn()} />,
    );
    expect(
      screen.getByText(
        `${done2} of ${total2} ${getCopy("checklist.readiness.preparedLabel")}`,
      ),
    ).toBeInTheDocument();
    expect(total2).not.toBe(total1);
  });

  it("never frames the readiness meter as approval likelihood (spec §5 hard rule)", () => {
    const { container } = render(
      <ReadinessChecklist
        plan={basePlan()}
        verdict={noopVerdict}
        onToggle={vi.fn()}
      />,
    );
    // The meter caption is the ONE sanctioned place these words appear — it
    // explicitly DISCLAIMS approval framing ("... not approval odds"), and a
    // naive whole-text regex would convict the disclaimer for doing its job
    // (superscar #3, guard over-match).
    //
    // The exemption is keyed on the NEGATING CONSTRUCTION, not on whatever the
    // caption happens to say. Exempting the caption by identity — reading the
    // string back from copy.ts and stripping it whole — looks equivalent and is
    // not: it hands the caption a blanket pardon, so rewriting it to "We
    // guarantee approval once these are ready." renders that claim live on the
    // page and the check still passes. Measured, before this line existed:
    // 5/5 green on exactly that mutation. An exemption that widens when its
    // target is edited is the silent half of over-match — it does not shout, it
    // just stops convicting.
    const rest = (container.textContent ?? "").replace(
      /\bnot approval odds\b/gi,
      "",
    );
    expect(rest).not.toMatch(
      /likelihood|chance|probability|approval odds|guarantee/i,
    );
  });

  it("keeps every checklist item a real, tickable checkbox", () => {
    const onToggle = vi.fn();
    render(
      <ReadinessChecklist
        plan={basePlan()}
        verdict={noopVerdict}
        onToggle={onToggle}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(CHECKLIST_ITEMS.length);
    for (const checkbox of checkboxes) {
      expect(checkbox).not.toHaveAttribute("disabled");
    }

    // Clicking the item's TITLE TEXT (not the box) must fire onToggle with
    // that item's id — this is what makes the wrapping <label> a real
    // accessibility guarantee for the small 18px box, not decoration.
    const title = screen.getByText(
      getCopy("checklist.items.passportBioPage.title"),
    );
    fireEvent.click(title);
    expect(onToggle).toHaveBeenCalledWith("passport_bio_page");
  });

  it("hides the 'may also apply' group when it is empty, shows it when it is not", () => {
    // Unresolved route (no age/route answered yet) widens EVERY
    // route-conditioned item to "applies" (checklist.ts's fail-safe), so
    // with a family member also answered, the may-apply group is provably
    // empty — no item can ever land there for this plan.
    const emptyGroupPlan = basePlan({
      family: { spouse: true, children: 0, parents: 0 },
    });
    const { rerender } = render(
      <ReadinessChecklist
        plan={emptyGroupPlan}
        verdict={noopVerdict}
        onToggle={vi.fn()}
      />,
    );
    expect(
      screen.queryByRole("heading", {
        name: getCopy("checklist.groups.mayApplyHeading"),
      }),
    ).toBeNull();

    const nonEmptyGroupPlan = basePlan({
      age: "under_55",
      route: "property",
      property: "owns_qualifying_strata",
      family: { spouse: true, children: 0, parents: 0 },
    });
    rerender(
      <ReadinessChecklist
        plan={nonEmptyGroupPlan}
        verdict={noopVerdict}
        onToggle={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("heading", {
        name: getCopy("checklist.groups.mayApplyHeading"),
      }),
    ).toBeInTheDocument();
  });
});
