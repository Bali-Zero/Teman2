import { vi } from "vitest";
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
  QUESTIONS,
  shouldAskRenewalPaid,
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
      "Confirming these answers is what asks the engine",
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
    expect(text).toContain("named a fact it still needs");
    // NEEDS_INPUT may name several facts; the rail cannot say "one more"
    // (council round 11).
    expect(text).not.toContain("one more fact");
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
  // Council finding #2 (round 1) said the onshore
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
  // Reproduced by the council: once the follow-up was answered the
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
      "named a fact it still needs",
    );
  });

  it("places the question inside its own stage on the trunk, and the framing behind it (council round 12)", () => {
    const { current, facts } = skippedLocation();
    const ids = (model: ReturnType<typeof m>) =>
      model.trunk.map((step) => step.id);
    const open = m(current, facts);
    const order = ids(open);
    expect(order.indexOf("holds_stay_permit")).toBe(
      order.indexOf("in_indonesia") + 1,
    );
    expect(order.indexOf("holds_stay_permit")).toBeLessThan(
      order.indexOf("confirmation"),
    );
    expect(open.trunk.find((step) => step.id === "framing")?.status).toBe(
      "done",
    );
    // …and once answered, it stays there rather than trailing the pending steps.
    let state = initialFlowState();
    state = flowReducer(state, { type: "ADVANCE" });
    state = flowReducer(state, { type: "SKIP", questionId: "in_indonesia" });
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: "holds_stay_permit",
      value: "no",
    });
    const next = state.history[state.history.length - 1];
    const answered = ids(m(next, state.facts));
    expect(answered.indexOf("holds_stay_permit")).toBe(
      answered.indexOf("in_indonesia") + 1,
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

describe("the outcome stays the last node of the tree (council round 7)", () => {
  const ANSWERED_FOLLOW_UP: OracleFacts = {
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

  it("puts the answered follow-up BEFORE the verdict, not after it", () => {
    const model = m({ kind: "verdict" }, ANSWERED_FOLLOW_UP, true);
    const ids = model.trunk.map((step) => step.id);
    expect(ids[ids.length - 1]).toBe("verdict");
    expect(ids.indexOf("family_sponsor_confirmed")).toBeGreaterThan(-1);
    expect(ids.indexOf("family_sponsor_confirmed")).toBeLessThan(
      ids.indexOf("verdict"),
    );
  });
});

describe("the confirmation node's copy (council round 7)", () => {
  // `REVIEW_ANSWERS` returns to the confirmation screen FROM the verdict, so
  // "nothing has been sent yet" was false for every visitor who had already
  // seen an answer and gone back to change one.
  it("does not deny a submission that already happened", () => {
    render(
      <ProcessProgress
        language="en"
        model={m({ kind: "confirmation" }, WORK_BRANCH)}
        variant="desktop"
      />,
    );
    const text = rail("progress").textContent ?? "";
    expect(text).not.toContain("Nothing has been sent yet");
    expect(text).toContain("asks it again if you have already been here");
  });
});

describe("a stage started but not finished (council round 8)", () => {
  /** Replays the real reducer: any refused answer throws instead of
   * silently leaving the walk where it was. */
  function offshoreInvest() {
    let state = initialFlowState();
    state = flowReducer(state, { type: "ADVANCE" });
    // D19 (2026-09-16): `overstay_days` is not one of these any more —
    // offshore never asks it — so it is not answered here either.
    const pairs: Array<[string, string]> = [
      ["in_indonesia", "no"],
      ["holds_stay_permit", "no"],
      ["nationalities", "IT"],
      ["birth_date", "1990-02-03"],
      ["category", "invest"],
    ];
    for (const [questionId, value] of pairs) {
      const before = Object.keys(state.facts).length;
      state = flowReducer(state, { type: "ANSWER", questionId, value });
      if (Object.keys(state.facts).length !== before + 1) {
        throw new Error(`the reducer refused ${questionId}=${value}`);
      }
    }
    return state;
  }

  it("does not call a stage with two of its three answers 'not started'", () => {
    const state = offshoreInvest();
    const current = state.history[state.history.length - 1];
    const model = m(current, state.facts);
    const location = model.phases.find((phase) => phase.key === "location");
    // D19 (2026-09-16): `overstay_days` no longer counts here — offshore
    // location facts are `in_indonesia` + `holds_stay_permit`, with
    // `wants_onshore_conversion` (offshore invest branch) still pending.
    expect(location?.answered).toBe(2);
    expect(location?.total).toBe(3);
    expect(location?.status).toBe("partial");

    render(<ProcessProgress language="en" model={model} variant="desktop" />);
    const row = rail("progress").querySelector(
      '[data-process-phase="location"]',
    );
    expect(row).toHaveAttribute("data-status", "partial");
    expect(row?.textContent ?? "").toContain("in progress");
    expect(row?.textContent ?? "").not.toContain("not started");
  });

  it("keeps an edited answer counted — an answer is a fact, not a cursor", () => {
    const walked = offshoreInvest();
    const state = flowReducer(walked, { type: "EDIT", questionId: "category" });
    const current = state.history[state.history.length - 1];
    expect(current.kind).toBe("question");
    const answeredFacts = Object.keys(state.facts).length;
    // D19 (2026-09-16): one fewer fact than before — `overstay_days` is not
    // among them (offshore never asks it).
    expect(answeredFacts).toBe(5);
    expect(m(current, state.facts).answeredQuestions).toBe(answeredFacts);
  });
});

describe("council round 10", () => {
  /** Replays the real reducer from the framing node, answering each open
   * question from `answers` (or its first option), until a non-question
   * node is reached. A refused answer throws. */
  function replay(answers: Record<string, string>) {
    let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
    for (let guard = 0; guard < 80; guard += 1) {
      const node = state.history[state.history.length - 1];
      if (node.kind !== "question") return state;
      const question = QUESTIONS[node.questionId];
      const value =
        answers[node.questionId] ?? question.options[0]?.key ?? "none";
      const before = state.history.length;
      state = flowReducer(state, {
        type: "ANSWER",
        questionId: node.questionId,
        value,
      });
      if (state.history.length === before) {
        throw new Error(`the reducer refused ${node.questionId}=${value}`);
      }
    }
    throw new Error("the walk did not leave the question spine");
  }

  const TOURIST = {
    in_indonesia: "no",
    holds_stay_permit: "no",
    nationalities: "IT",
    birth_date: "1985-04-12",
    category: "tourism",
    trip_scope: "single",
    stay_days: "30",
    review_gate: "none",
  };

  it("a purpose answered 'unsure' shows no branch fan that calls eleven branches open", () => {
    // Walk to the purpose question by hand: `replay` would answer it. D19
    // (2026-09-16): `overstay_days` is not one of these any more — offshore
    // never asks it — so it is not answered here either.
    let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
    for (const id of [
      "in_indonesia",
      "holds_stay_permit",
      "nationalities",
      "birth_date",
    ] as const) {
      state = flowReducer(state, {
        type: "ANSWER",
        questionId: id,
        value: TOURIST[id],
      });
    }
    const atCategory = state.history[state.history.length - 1];
    expect(atCategory).toEqual({ kind: "question", questionId: "category" });
    state = flowReducer(state, { type: "SKIP", questionId: "category" });
    expect(state.facts.category).toBe("unsure");
    const current = state.history[state.history.length - 1];
    expect(current).not.toEqual({ kind: "question", questionId: "category" });

    const model = m(current, state.facts);
    expect(model.showCategories).toBe(false);
    render(<ProcessBranches language="en" model={model} variant="desktop" />);
    expect(document.querySelector('[data-process-part="branches"]')).toBeNull();
    expect(model.trunk.find((step) => step.id === "category")?.status).toBe(
      "done",
    );
  });

  it("jumping back from the verdict drops it from history, so an off-spine question is not called the engine's follow-up", () => {
    const atVerdictOrConfirmation = replay(TOURIST);
    let state = atVerdictOrConfirmation;
    if (state.history[state.history.length - 1].kind === "confirmation") {
      state = flowReducer(state, { type: "ADVANCE" });
    }
    expect(state.history[state.history.length - 1].kind).toBe("verdict");

    state = flowReducer(state, { type: "EDIT", questionId: "in_indonesia" });
    state = flowReducer(state, { type: "SKIP", questionId: "in_indonesia" });
    const current = state.history[state.history.length - 1];
    expect(current).toEqual({
      kind: "question",
      questionId: "holds_stay_permit",
    });
    // What OracleShell passes, computed the same way.
    const visitedVerdict = state.history.some(
      (node) => node.kind === "verdict",
    );
    expect(visitedVerdict).toBe(false);
    expect(m(current, state.facts, visitedVerdict).atFollowUp).toBe(false);
  });

  it("an answer from an abandoned branch never reaches the trunk: EDIT prunes facts to history", () => {
    let state = replay({ ...TOURIST, category: "work" });
    expect(state.facts.category).toBe("work");
    state = flowReducer(state, { type: "EDIT", questionId: "category" });
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: "category",
      value: "tourism",
    });
    const inHistory = new Set(
      state.history.flatMap((node) =>
        node.kind === "question" ? [node.questionId] : [],
      ),
    );
    expect(Object.keys(state.facts).every((id) => inHistory.has(id))).toBe(
      true,
    );
    const current = state.history[state.history.length - 1];
    const model = m(current, state.facts);
    const trunkQuestions = model.trunk
      .map((step) => step.id)
      .filter((id) => Object.prototype.hasOwnProperty.call(QUESTIONS, id));
    for (const id of trunkQuestions) {
      if (state.facts[id] !== undefined) expect(inHistory.has(id)).toBe(true);
    }
    expect(model.answeredQuestions).toBe(Object.keys(state.facts).length);
  });

  it.each([["HUMAN_REVIEW_REQUIRED"], ["TEMPORARILY_UNAVAILABLE"]] as const)(
    "does not say the engine is waiting for something on %s, in EN or ID",
    (state) => {
      for (const language of ["en", "id"] as const) {
        const { unmount } = render(
          <ProcessOutcome
            language={language}
            model={m({ kind: "verdict" }, WORK_BRANCH)}
            variant="desktop"
            outcome={{ state, provenance: "ENGINE", candidates: [] }}
          />,
        );
        const text = rail("outcome").textContent ?? "";
        expect(text).not.toMatch(/waiting for|masih ditunggu/);
        expect(text).toContain(
          language === "en" ? "says why" : "menjelaskan alasannya",
        );
        unmount();
      }
    },
  );

  it("the framing copy does not promise a fact for questions that attach none", () => {
    for (const language of ["en", "id"] as const) {
      const { unmount } = render(
        <ProcessProgress
          language={language}
          model={m({ kind: "framing" }, {})}
          variant="desktop"
        />,
      );
      const text = rail("progress").textContent ?? "";
      expect(text).not.toMatch(/the fact it sets|fakta yang ditetapkannya/);
      unmount();
    }
  });
});

describe("a path that crossed a date boundary (council round 13)", () => {
  // `renewal_paid` is asked only once the permit has expired, read against
  // the clock. An interview that passed the permit questions BEFORE the
  // expiry date and is rendered AFTER it must not gain an unasked step.
  const BEFORE = new Date("2026-09-01T00:00:00Z");
  const AFTER = new Date("2026-09-20T00:00:00Z");
  const ANSWERS: Record<string, string> = {
    in_indonesia: "yes",
    permit_expiry: "2026-09-10",
    holds_stay_permit: "yes",
    overstay_days: "0",
  };

  function onshoreWalk() {
    let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
    for (let guard = 0; guard < 12; guard += 1) {
      const node = state.history[state.history.length - 1];
      if (node.kind !== "question" || node.questionId === "application_channel")
        return state;
      const value =
        ANSWERS[node.questionId] ?? QUESTIONS[node.questionId].options[0]?.key;
      state = flowReducer(state, {
        type: "ANSWER",
        questionId: node.questionId,
        value,
        today: BEFORE,
      });
    }
    throw new Error("the walk did not reach application_channel");
  }

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not count a question the path never asked as a pending step behind the visitor", () => {
    const state = onshoreWalk();
    expect(
      state.history.some(
        (n) => n.kind === "question" && n.questionId === "renewal_paid",
      ),
    ).toBe(false);
    expect(shouldAskRenewalPaid(state.facts, BEFORE)).toBe(false);
    expect(shouldAskRenewalPaid(state.facts, AFTER)).toBe(true);
    const current = state.history[state.history.length - 1];

    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(BEFORE);
    const then = m(current, state.facts);
    vi.setSystemTime(AFTER);
    const later = m(current, state.facts);

    expect(later.trunk.some((step) => step.id === "renewal_paid")).toBe(false);
    expect(later.totalQuestions).toBe(then.totalQuestions);
    expect(later.answeredQuestions).toBe(then.answeredQuestions);
  });

  it("does not either at the engine's follow-up, where the whole spine is behind", () => {
    const state = onshoreWalk();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(AFTER);
    const model = m(
      { kind: "question", questionId: "family_sponsor_confirmed" },
      state.facts,
      true,
    );
    expect(model.trunk.some((step) => step.id === "renewal_paid")).toBe(false);
    expect(model.totalQuestions).toBe(model.answeredQuestions + 1);
  });
});
