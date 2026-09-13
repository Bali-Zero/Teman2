import { render, within } from "@testing-library/react";
import { ProcessBranches, ProcessProgress } from "./ProcessRail";
import type { OracleFacts } from "../_lib/tree";

const OFFSHORE: OracleFacts = {
  in_indonesia: "no",
  holds_stay_permit: "no",
  overstay_days: "0",
};

const WORK_BRANCH: OracleFacts = {
  ...OFFSHORE,
  nationalities: "IT",
  birth_date: "1990-02-03",
  category: "work",
  trip_scope: "single",
};

function rail(part: "progress" | "branches"): HTMLElement {
  const node = document.querySelector<HTMLElement>(
    `[data-process-part="${part}"]`,
  );
  if (!node) throw new Error(`no ${part} rail rendered`);
  return node;
}

describe("ProcessProgress — where the visitor is", () => {
  it("names the step, the open stage and the fact the open question decides", () => {
    render(
      <ProcessProgress
        language="en"
        current={{ kind: "question", questionId: "nationalities" }}
        facts={OFFSHORE}
        variant="desktop"
      />,
    );
    const panel = rail("progress");
    expect(panel.textContent).toContain("Step 3 of 8");
    expect(panel.textContent).toContain("Who you are");
    // The stage the visitor is inside reads "open now"; a finished one
    // reads "complete" — status is projected, never hard-coded.
    expect(
      panel.querySelector('[data-process-phase="identity"]'),
    ).toHaveAttribute("data-status", "current");
    expect(
      panel.querySelector('[data-process-phase="location"]'),
    ).toHaveAttribute("data-status", "done");
    expect(
      panel.querySelector('[data-process-phase="outcome"]'),
    ).toHaveAttribute("data-status", "pending");
    // The engine's own vocabulary, not a paraphrase.
    expect(within(panel).getByText("person.nationalities")).toBeInTheDocument();
  });

  it("says plainly when an answer is human context the engine never reads", () => {
    render(
      <ProcessProgress
        language="en"
        current={{ kind: "question", questionId: "holds_stay_permit" }}
        facts={{ in_indonesia: "no" }}
        variant="desktop"
      />,
    );
    expect(rail("progress").textContent).toContain(
      "this answer is never sent to the engine",
    );
  });

  it("marks the safety check as a review signal, not an eligibility fact", () => {
    render(
      <ProcessProgress
        language="en"
        current={{ kind: "question", questionId: "review_gate" }}
        facts={WORK_BRANCH}
        variant="desktop"
      />,
    );
    expect(rail("progress").textContent).toContain(
      "it can send this case to a person",
    );
  });

  it("at the terminal node no question is open and the stage is the outcome", () => {
    render(
      <ProcessProgress
        language="en"
        current={{ kind: "verdict" }}
        facts={WORK_BRANCH}
        variant="desktop"
      />,
    );
    const panel = rail("progress");
    expect(panel.textContent).toContain("The engine’s answer");
    expect(panel.textContent).toContain("No question is open");
  });
});

describe("ProcessBranches — what closed, why, and what the engine named", () => {
  it("is absent before the purpose question is reached", () => {
    render(
      <ProcessBranches
        language="en"
        current={{ kind: "question", questionId: "in_indonesia" }}
        facts={{}}
        variant="desktop"
      />,
    );
    expect(document.querySelector('[data-process-part="branches"]')).toBeNull();
  });

  it("shows every branch as open while none is chosen", () => {
    render(
      <ProcessBranches
        language="en"
        current={{ kind: "question", questionId: "category" }}
        facts={{ ...OFFSHORE, nationalities: "IT", birth_date: "1990-02-03" }}
        variant="desktop"
      />,
    );
    const panel = rail("branches");
    expect(panel.querySelectorAll("[data-process-category]")).toHaveLength(11);
    expect(
      panel.querySelector('[data-process-category="work"]'),
    ).toHaveAttribute("data-status", "pending");
    expect(panel.textContent).toContain("Every purpose branch is still open");
  });

  it("keeps the ten closed branches VISIBLE and names the answer that closed them", () => {
    render(
      <ProcessBranches
        language="en"
        current={{ kind: "question", questionId: "work_payer" }}
        facts={WORK_BRANCH}
        variant="desktop"
      />,
    );
    const panel = rail("branches");
    // The defect this fixes: the old leaf row DROPPED every pruned chip the
    // moment one was chosen, so "what did my answer close?" had no answer
    // on screen at all.
    expect(panel.querySelectorAll("[data-process-category]")).toHaveLength(11);
    expect(
      panel.querySelectorAll('[data-process-category][data-status="pruned"]'),
    ).toHaveLength(10);
    expect(
      panel.querySelector('[data-process-category="tourism"]'),
    ).toHaveAttribute("data-status", "pruned");
    expect(panel.textContent).toContain(
      "10 branches closed when you chose “Work & employment”",
    );
  });

  it("never names a product before the engine has answered", () => {
    render(
      <ProcessBranches
        language="en"
        current={{ kind: "question", questionId: "work_payer" }}
        facts={WORK_BRANCH}
        variant="desktop"
      />,
    );
    expect(rail("branches").textContent).toContain("No product is named yet");
  });

  it("names the engine's own product codes at the terminal node", () => {
    render(
      <ProcessBranches
        language="en"
        current={{ kind: "verdict" }}
        facts={WORK_BRANCH}
        variant="desktop"
        outcome={{
          state: "SUPPORTED_CANDIDATES",
          candidates: [
            { code: "E23", name: { en: "Working KITAS", id: "KITAS Kerja" } },
          ],
        }}
      />,
    );
    const panel = rail("branches");
    expect(
      panel.querySelector('[data-process-candidate="E23"]')?.textContent,
    ).toContain("Working KITAS");
    expect(panel.textContent).toContain("last node of this tree");
  });

  it("says the engine named nothing when it named nothing", () => {
    render(
      <ProcessBranches
        language="en"
        current={{ kind: "verdict" }}
        facts={WORK_BRANCH}
        variant="desktop"
        outcome={{ state: "NO_SUPPORTED_PATH", candidates: [] }}
      />,
    );
    expect(rail("branches").textContent).toContain(
      "The engine named no product",
    );
  });

  it("renders the closed-branch sentence in Indonesian", () => {
    render(
      <ProcessBranches
        language="id"
        current={{ kind: "question", questionId: "work_payer" }}
        facts={WORK_BRANCH}
        variant="mobile"
      />,
    );
    const panel = rail("branches");
    expect(panel).toHaveAttribute("data-process-rail", "mobile");
    expect(panel.textContent).toContain(
      "10 cabang ditutup ketika Anda memilih",
    );
    expect(panel.textContent).toContain("Belum ada produk yang disebut");
  });
});
