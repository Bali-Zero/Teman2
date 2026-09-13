import { render, within } from "@testing-library/react";
import {
  ProcessBranches,
  ProcessOutcome,
  ProcessProgress,
} from "./ProcessRail";
import type { OracleFacts } from "../_lib/tree";
import {
  flowReducer,
  getProcessModel,
  initialFlowState,
  type OracleNode,
} from "../_lib/flow";

/** The rail renders a projection, never raw state — the model is the one
 * thing a defect would have to travel through, and `LivingTree` builds it
 * exactly once for every view. */
function m(current: OracleNode, facts: OracleFacts, visitedVerdict = false) {
  return getProcessModel(current, facts, visitedVerdict);
}

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

function rail(part: "progress" | "branches" | "outcome"): HTMLElement {
  const node = document.querySelector<HTMLElement>(
    `[data-process-part="${part}"]`,
  );
  if (!node) throw new Error(`no ${part} rail rendered`);
  return node;
}

describe("ProcessProgress — where the visitor is", () => {
  it("names the answers on record, the open stage and the fact the open question decides", () => {
    render(
      <ProcessProgress
        language="en"
        model={m({ kind: "question", questionId: "nationalities" }, OFFSHORE)}
        variant="desktop"
      />,
    );
    const panel = rail("progress");
    // "3 of 8 ANSWERED", never "step 3": the open question is the fourth,
    // and a count of answers must not be read as an ordinal.
    expect(panel.textContent).toContain("3 of 8 answered");
    expect(panel.textContent).toContain("Who you are");
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

  it("does not claim a HUMAN_CONTEXT answer never reaches the engine — it can feed a DERIVED fact", () => {
    render(
      <ProcessProgress
        language="en"
        model={m(
          { kind: "question", questionId: "holds_stay_permit" },
          { in_indonesia: "no" },
        )}
        variant="desktop"
      />,
    );
    const text = rail("progress").textContent ?? "";
    expect(text).toContain("No engine fact is attached to this question");
    // The refuted copy: `holds_stay_permit` carries no FactPath of its own
    // and STILL resolves `immigration.current_status_code` to
    // NO_STAY_PERMIT through the mapper — pinned by fact-mapper.test.ts's
    // "offshore convergence" case. Promising the answer is never sent was
    // a false statement about a reachable path (council round 3).
    expect(text).not.toContain("never sent to the engine");
  });

  it("marks the safety check as a review signal, not an eligibility fact", () => {
    render(
      <ProcessProgress
        language="en"
        model={m({ kind: "question", questionId: "review_gate" }, WORK_BRANCH)}
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
        model={m({ kind: "verdict" }, WORK_BRANCH)}
        variant="desktop"
        outcome={{
          state: "SUPPORTED_CANDIDATES",
          provenance: "ENGINE",
          candidates: [],
        }}
      />,
    );
    const panel = rail("progress");
    expect(panel.textContent).toContain("The engine’s answer");
    expect(panel.textContent).toContain("No question is open");
  });

  it("does not say the engine HAS the answers while its reply is not on screen", () => {
    // The evaluation request is fired by an effect AFTER this node renders,
    // and it can be in flight, disabled or failed. `outcome` is the only
    // evidence a reply exists (council round 3).
    render(
      <ProcessProgress
        language="en"
        model={m({ kind: "verdict" }, WORK_BRANCH)}
        variant="desktop"
      />,
    );
    const text = rail("progress").textContent ?? "";
    expect(text).toContain("the engine’s reply is not on screen yet");
    expect(text).not.toContain("The engine has the answers");
  });

  it.each([
    ["framing", { kind: "framing" as const }, {}, "Nothing is answered yet"],
    [
      "confirmation",
      { kind: "confirmation" as const },
      WORK_BRANCH,
      "Nothing has been sent yet",
    ],
    [
      "verdict",
      { kind: "verdict" as const },
      WORK_BRANCH,
      "Your answers are confirmed",
    ],
  ])(
    "the %s node says what is true at that node and not at the other two",
    (_name, current, facts, expected) => {
      render(
        <ProcessProgress
          language="en"
          model={m(current, facts)}
          variant="desktop"
        />,
      );
      expect(rail("progress").textContent).toContain(expected);
    },
  );
});

describe("ProcessBranches — what closed and why", () => {
  it("is absent before the purpose question is reached", () => {
    render(
      <ProcessBranches
        language="en"
        model={m({ kind: "question", questionId: "in_indonesia" }, {})}
        variant="desktop"
      />,
    );
    expect(document.querySelector('[data-process-part="branches"]')).toBeNull();
  });

  it("shows every branch as open while the purpose question is the one on screen", () => {
    render(
      <ProcessBranches
        language="en"
        model={m(
          { kind: "question", questionId: "category" },
          { ...OFFSHORE, nationalities: "IT", birth_date: "1990-02-03" },
        )}
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
        model={m({ kind: "question", questionId: "work_payer" }, WORK_BRANCH)}
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
    // The chosen-and-still-open branch keeps its OWN status in the
    // attribute: painting it "done" made the chip say one thing to the eye
    // and another to the screen reader reading its own status text.
    expect(
      panel.querySelector('[data-process-category="work"]'),
    ).toHaveAttribute("data-status", "current");
    expect(panel.textContent).toContain(
      "10 branches closed when you chose “Work & employment”",
    );
  });

  it("renders the closed-branch sentence in Indonesian", () => {
    render(
      <ProcessBranches
        language="id"
        model={m({ kind: "question", questionId: "work_payer" }, WORK_BRANCH)}
        variant="mobile"
      />,
    );
    const panel = rail("branches");
    expect(panel).toHaveAttribute("data-process-rail", "mobile");
    expect(panel.textContent).toContain(
      "10 cabang ditutup ketika Anda memilih",
    );
  });
});

describe("ProcessOutcome — only what the ENGINE named", () => {
  it("never names a product before the engine has answered", () => {
    render(
      <ProcessOutcome
        language="en"
        model={m({ kind: "question", questionId: "work_payer" }, WORK_BRANCH)}
        variant="desktop"
      />,
    );
    expect(rail("outcome").textContent).toContain("No product is named yet");
  });

  it("names the engine's own product codes at the terminal node", () => {
    render(
      <ProcessOutcome
        language="en"
        model={m({ kind: "verdict" }, WORK_BRANCH)}
        variant="desktop"
        outcome={{
          state: "SUPPORTED_CANDIDATES",
          provenance: "ENGINE",
          candidates: [
            { code: "E23", name: { en: "Working KITAS", id: "KITAS Kerja" } },
          ],
        }}
      />,
    );
    const panel = rail("outcome");
    expect(
      panel.querySelector('[data-process-candidate="E23"]')?.textContent,
    ).toContain("Working KITAS");
    expect(panel.textContent).toContain("last node of this tree");
  });

  it("says the engine named nothing only when the engine DECIDED nothing fits", () => {
    render(
      <ProcessOutcome
        language="en"
        model={m({ kind: "verdict" }, WORK_BRANCH)}
        variant="desktop"
        outcome={{
          state: "NO_SUPPORTED_PATH",
          provenance: "ENGINE",
          candidates: [],
        }}
      />,
    );
    expect(rail("outcome").textContent).toContain(
      "The engine named no product",
    );
  });

  it.each([
    ["TEMPORARILY_UNAVAILABLE"],
    ["HUMAN_REVIEW_REQUIRED"],
    ["NEEDS_INPUT"],
  ] as const)(
    "does NOT read %s as 'no product exists' — that is an eligibility claim it never measured",
    (state) => {
      render(
        <ProcessOutcome
          language="en"
          model={m({ kind: "verdict" }, WORK_BRANCH)}
          variant="desktop"
          outcome={{ state, provenance: "ENGINE", candidates: [] }}
        />,
      );
      const panel = rail("outcome");
      expect(panel.textContent).toContain("did not name a product");
      expect(panel.textContent).not.toContain("The engine named no product");
    },
  );

  it("renders the pending sentence in Indonesian", () => {
    render(
      <ProcessOutcome
        language="id"
        model={m({ kind: "question", questionId: "work_payer" }, WORK_BRANCH)}
        variant="mobile"
      />,
    );
    expect(rail("outcome").textContent).toContain(
      "Belum ada produk yang disebut",
    );
  });
});

describe("the NEEDS_INPUT follow-up node", () => {
  // `ASK_FOLLOW_UP` appends a question the current path's order does not
  // contain, so `getTreeSteps` reports every trunk step "pending". Counting
  // those statuses told someone who had answered a dozen questions that they
  // were on "0 of 13" — the count now falls back to the facts themselves.
  const COMPLETED_TOURISM: OracleFacts = {
    ...OFFSHORE,
    nationalities: "IT",
    birth_date: "1985-04-12",
    category: "tourism",
    trip_scope: "single",
    stay_days: "30",
    entry_pattern: "SINGLE",
    review_gate: "none",
  };
  const FOLLOW_UP: OracleNode = {
    kind: "question",
    questionId: "family_sponsor_confirmed",
  };

  it("counts the answers already given and adds the follow-up to the total", () => {
    render(
      <ProcessProgress
        language="en"
        model={m(FOLLOW_UP, COMPLETED_TOURISM, true)}
        variant="desktop"
      />,
    );
    const panel = rail("progress");
    const match = panel.textContent?.match(/(\d+) of (\d+) answered/);
    if (!match) throw new Error(`no count in: ${panel.textContent}`);
    const [, answered, total] = match.map(Number);
    expect(answered).toBe(Object.keys(COMPLETED_TOURISM).length);
    expect(total).toBe(answered + 1);
    // The stage that question belongs to is the one open, not "none".
    expect(
      panel.querySelector('[data-process-phase="details"]'),
    ).toHaveAttribute("data-status", "current");
    // And the outcome stage is open too — the engine is waiting on this
    // answer, so calling it "complete" would contradict the panel below.
    expect(
      panel.querySelector('[data-process-phase="outcome"]'),
    ).toHaveAttribute("data-status", "current");
  });

  it("says the engine asked for this fact — not that no product exists yet", () => {
    render(
      <ProcessOutcome
        language="en"
        model={m(FOLLOW_UP, COMPLETED_TOURISM, true)}
        variant="desktop"
      />,
    );
    const text = rail("outcome").textContent ?? "";
    expect(text).toContain("asked for one more fact");
    // …and does not promise the next evaluation names a product: a second
    // NEEDS_INPUT, a review hold or no supported path are all possible
    // (council round 5).
    expect(text).not.toContain("before it names a product");
  });

  it("still shows the branches the interview closed", () => {
    render(
      <ProcessBranches
        language="en"
        model={m(FOLLOW_UP, COMPLETED_TOURISM, true)}
        variant="desktop"
      />,
    );
    expect(rail("branches").textContent).toContain(
      "closed when you chose “Tourism & short visit”",
    );
  });
});

describe("the council's skipped-spine lane, re-measured", () => {
  // Council finding #2 (codex-gpt-5.6-sol, round 1) said the onshore
  // urgent permit lane jumps from `permit_expiry` straight to
  // `review_gate`, leaving earlier questions unasked and the purpose fan
  // claiming eleven open branches. The claim quotes `getTreeSteps`'s own
  // comment, which is STALE: `computeNextNode`'s `permit_expiry` case
  // routes onshore to `holds_stay_permit` today. This pins the routing the
  // refutation rests on, so the day it changes, this test says so.
  const TODAY = new Date("2026-09-13T00:00:00Z");

  it("onshore permit_expiry leads to holds_stay_permit, not to review_gate", () => {
    let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "yes",
      today: TODAY,
    });
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: "permit_expiry",
      value: "2026-09-16",
      today: TODAY,
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "holds_stay_permit",
    });
  });

  it("the purpose fan stays shut until the purpose question is the one on screen", () => {
    render(
      <ProcessBranches
        language="en"
        model={m(
          { kind: "question", questionId: "birth_date" },
          { ...OFFSHORE, nationalities: "IT" },
        )}
        variant="desktop"
      />,
    );
    expect(document.querySelector('[data-process-part="branches"]')).toBeNull();
  });
});

describe("a non-ENGINE outcome is not an engine answer (council round 4)", () => {
  // `outcome-fallbacks.ts` builds a NON-null outcome for a client guard, a
  // network failure, a shadow comparison and a developer preview — each with
  // zero candidates by contract. Reading "outcome !== null" as "the engine
  // replied" made the rail speak for an engine it never reached.
  it.each(["CLIENT_GUARD", "NETWORK_FAILURE", "SHADOW", "PREVIEW"] as const)(
    "%s renders neither the engine-has-your-answers line nor a no-product claim",
    (provenance) => {
      render(
        <ProcessProgress
          language="en"
          model={m({ kind: "verdict" }, WORK_BRANCH)}
          variant="desktop"
          outcome={{
            state: "TEMPORARILY_UNAVAILABLE",
            provenance,
            candidates: [],
          }}
        />,
      );
      expect(rail("progress").textContent).toContain(
        "the engine’s reply is not on screen yet",
      );

      render(
        <ProcessOutcome
          language="en"
          model={m({ kind: "verdict" }, WORK_BRANCH)}
          variant="mobile"
          outcome={{
            state: "TEMPORARILY_UNAVAILABLE",
            provenance,
            candidates: [],
          }}
        />,
      );
      const outcomePanel = document.querySelector(
        '[data-process-part="outcome"][data-process-rail="mobile"]',
      );
      expect(outcomePanel?.textContent).toContain("No product is named yet");
      expect(outcomePanel?.textContent).not.toContain("named no product");
    },
  );
});

describe("an ANSWERED follow-up stays on the trunk (council round 4)", () => {
  // Reproduced by codex-gpt-5.6-sol: once the follow-up was answered the
  // reducer returned to the verdict, the question left the projection, the
  // count fell from 10/11 back to 10/10 and the answer the ENGINE asked for
  // by name had no jump target.
  const ANSWERED: OracleFacts = {
    in_indonesia: "no",
    holds_stay_permit: "no",
    overstay_days: "0",
    nationalities: "IT",
    birth_date: "1985-04-12",
    category: "tourism",
    trip_scope: "single",
    stay_days: "30",
    entry_pattern: "SINGLE",
    review_gate: "none",
    family_sponsor_confirmed: "yes",
  };

  it("counts it and keeps it editable after the interview returns to the verdict", () => {
    const model = m({ kind: "verdict" }, ANSWERED);
    expect(model.answeredQuestions).toBe(Object.keys(ANSWERED).length);
    expect(model.totalQuestions).toBe(Object.keys(ANSWERED).length);
    const step = model.trunk.find((s) => s.id === "family_sponsor_confirmed");
    expect(step).toBeDefined();
    expect(step?.status).toBe("done");
  });

  it("is open, not lost, while it is the question on screen", () => {
    const open: OracleFacts = { ...ANSWERED };
    delete open.family_sponsor_confirmed;
    const model = m(
      { kind: "question", questionId: "family_sponsor_confirmed" },
      open,
    );
    const step = model.trunk.find((s) => s.id === "family_sponsor_confirmed");
    expect(step?.status).toBe("current");
    expect(model.totalQuestions).toBe(model.answeredQuestions + 1);
  });
});

describe("an off-spine question that is NOT the engine's follow-up (council round 6)", () => {
  // Reachable in four clicks, replayed through the real reducer: SKIP on the
  // first location question records `in_indonesia: "unsure"` and routes to
  // `holds_stay_permit`, which the spine's `order` does not contain. The
  // projection used to read "not on the spine" as "the engine asked for this"
  // and marked confirmation and verdict done — a verdict this visitor has
  // never seen.
  function skippedLocation() {
    let state = initialFlowState();
    state = flowReducer(state, { type: "ADVANCE" });
    state = flowReducer(state, { type: "SKIP", questionId: "in_indonesia" });
    const current = state.history[state.history.length - 1];
    if (
      current.kind !== "question" ||
      current.questionId !== "holds_stay_permit"
    ) {
      throw new Error(
        `reducer did not reach the off-spine question: ${JSON.stringify(current)}`,
      );
    }
    if (state.history.some((node) => node.kind === "verdict")) {
      throw new Error("history unexpectedly contains a verdict");
    }
    return { current, facts: state.facts };
  }

  it("does not mark the verdict behind a visitor who has not reached it", () => {
    const { current, facts } = skippedLocation();
    const model = m(current, facts);
    expect(model.atFollowUp).toBe(false);
    expect(model.trunk.find((step) => step.id === "verdict")?.status).not.toBe(
      "done",
    );
    expect(
      model.trunk.find((step) => step.id === "confirmation")?.status,
    ).not.toBe("done");
    expect(model.phases.find((phase) => phase.key === "outcome")?.status).toBe(
      "pending",
    );
  });

  it("does not tell the visitor the engine asked for this fact", () => {
    const { current, facts } = skippedLocation();
    render(
      <ProcessOutcome
        language="en"
        model={m(current, facts)}
        variant="desktop"
      />,
    );
    expect(rail("outcome").textContent ?? "").not.toContain(
      "asked for one more fact",
    );
  });

  it("still opens the stage the skipped-over question belongs to", () => {
    const { current, facts } = skippedLocation();
    render(
      <ProcessProgress
        language="en"
        model={m(current, facts)}
        variant="desktop"
      />,
    );
    expect(
      rail("progress").querySelector('[data-process-phase="location"]'),
    ).toHaveAttribute("data-status", "current");
  });
});
