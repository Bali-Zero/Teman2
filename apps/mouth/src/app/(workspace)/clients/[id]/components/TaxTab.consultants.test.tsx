// The tax-consultant dropdown is fed by the SERVER, and this proves it.
//
// C4b removed a module-scope literal from TaxTab.tsx because a literal in a
// "use client" module is compiled into this route's static chunk, which Next
// serves from the CDN path with no session. Two guards already cover the
// mechanics: `scripts/assert-roster-not-in-public-chunks.mjs` greps the built
// artifact, and `src/lib/client-roster-boundary.test.ts` catches the import that
// would put the roster back into a client module.
//
// Neither of them can see the thing this file checks: that the options a user
// actually gets are the ones the server passed. A "fix" that deleted the literal
// and rendered nothing would pass both guards and leave the dropdown empty, so
// the assertion here is EXACT EQUALITY against the prop, not "contains" — under
// "contains", re-adding a hardcoded row beside the prop would still pass.
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn().mockResolvedValue({ email: "tester@example.test" }),
    crm: { updateClient: vi.fn().mockResolvedValue({}) },
  },
}));
// Both resolve to `{ items }`, which is the shape TaxTab actually destructures
// (`histRes.value.items`). A bare `[]` here left `items` undefined and the
// component threw on `.filter` — the mock was wrong, not the component, and it
// is written out because a mock whose shape drifts from the API is a test that
// passes while erroring.
vi.mock("@/lib/api/workspace/lkpm.api", () => ({
  lkpmApi: {
    getClientHistory: vi.fn().mockResolvedValue({ items: [] }),
    getClientReceipts: vi.fn().mockResolvedValue({ items: [] }),
  },
}));
vi.mock("./AiSummaryCard", () => ({
  AiSummaryCard: () => <div data-testid="AiSummaryCard" />,
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const CONSULTANTS = [
  { value: "alpha.tax@example.test", label: "Alpha" },
  { value: "beta.tax@example.test", label: "Beta" },
  { value: "gamma.tax@example.test", label: "Gamma" },
];

describe("TaxTab tax-consultant options", () => {
  beforeEach(() => vi.clearAllMocks());

  it("offers exactly the consultants handed down as a prop", async () => {
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={CONSULTANTS}
      />,
    );

    const select = (await waitFor(() =>
      screen.getByLabelText("Tax Consultant"),
    )) as HTMLSelectElement;

    // The placeholder row plus one row per supplied consultant, and nothing else.
    const rendered = Array.from(select.options).map((o) => ({
      value: o.value,
      label: o.textContent,
    }));
    expect(rendered).toEqual([
      { value: "", label: "— not assigned —" },
      ...CONSULTANTS.map((c) => ({ value: c.value, label: c.label })),
    ]);
  });

  it("renders no options beyond the placeholder when the server supplies none", async () => {
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    const select = (await waitFor(() =>
      screen.getByLabelText("Tax Consultant"),
    )) as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual([""]);
  });
});
