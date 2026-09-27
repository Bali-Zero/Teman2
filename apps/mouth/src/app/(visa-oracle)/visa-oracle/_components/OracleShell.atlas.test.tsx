/**
 * BUILD-SPEC §8 — OracleShell atlas integration (ORACLE-PROD-20260927).
 * Mocks fetch/env the same way OracleShell.test.tsx does; synthetic
 * answers only. This file never touches evaluation/consent/telemetry
 * logic — it only proves the presentational wiring (scene walk, motion
 * pause, "Your route" pruning, language) OracleShellRuntime added on top
 * of the untouched reducer.
 */
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useReducedMotion } from "framer-motion";
import {
  createInterviewSnapshot,
  flowReducer,
  initialFlowState,
  type FlowState,
} from "../_lib/flow";
import { saveInterviewResume } from "../_lib/resume-store";
import {
  QUESTIONS,
  questionPromptI18nKey,
  type OracleFacts,
} from "../_lib/tree";
import { translate, type I18nKey } from "../_lib/i18n";
import { formatFactDisplay } from "./ConfirmationCard";
import { OracleShell } from "./OracleShell";

// framer-motion's `useReducedMotion` lazily runs a MODULE-LEVEL singleton
// (`initPrefersReducedMotion`, guarded so it only ever runs once per
// process) that reads the real `window.matchMedia` the first time ANY test
// in this worker renders anything that calls it — stubbing
// `window.matchMedia` afterwards has no effect. Mocking the hook itself is
// the only reliable way to flip it per-test (FIX-ROUND-2 S2's "renders no
// button when the OS already prefers reduced motion" test needs this).
vi.mock("framer-motion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("framer-motion")>();
  return { ...actual, useReducedMotion: vi.fn(() => false) };
});

function applyAnswers(
  answers: readonly (readonly [string, string])[],
): FlowState {
  let state: FlowState = flowReducer(initialFlowState(), { type: "ADVANCE" });
  for (const [questionId, value] of answers) {
    state = flowReducer(state, { type: "ANSWER", questionId, value });
  }
  return state;
}

function installResumeAt(
  answers: readonly (readonly [string, string])[],
): void {
  const state = applyAnswers(answers);
  expect(
    saveInterviewResume(createInterviewSnapshot(state, new Date()), {
      now: new Date(),
    }),
  ).toBe(true);
}

function root(): HTMLElement {
  return document.querySelector(".oracle-root") as HTMLElement;
}

async function expectScene(
  id: string,
  layout: "stage" | "landscape",
): Promise<void> {
  await waitFor(() => {
    expect(root()).toHaveAttribute("data-scene", id);
    expect(root()).toHaveAttribute("data-scene-layout", layout);
  });
}

describe("OracleShell atlas — data-scene walk", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it("walks entry -> world -> paper -> identity -> watershed -> category(landscape) -> confluence", async () => {
    render(<OracleShell />);

    await screen.findByRole("button", { name: /^start$/i });
    await expectScene("entry", "stage");

    fireEvent.click(screen.getByRole("button", { name: /^start$/i }));
    await expectScene("world", "stage");

    fireEvent.click(
      await screen.findByRole("button", { name: /planning ahead/i }),
    );
    await expectScene("paper", "stage");

    await screen.findByRole("heading", {
      name: /do you currently hold a limited or permanent stay permit/i,
    });
    fireEvent.click(screen.getByRole("button", { name: /^no$/i }));
    // Offshore + holds_stay_permit=no converges straight to nationalities
    // (flow.ts, same convergence OracleShell.test.tsx's completeFreshInterview
    // already exercises) — both identity questions project to "identity".
    await expectScene("identity", "landscape");

    fireEvent.change(await screen.findByRole("combobox"), {
      target: { value: "US" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^add country$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));
    await expectScene("identity", "landscape");

    const birthDate =
      document.querySelector<HTMLInputElement>('input[type="date"]');
    expect(birthDate).not.toBeNull();
    fireEvent.change(birthDate!, { target: { value: "1990-01-01" } });
    fireEvent.click(screen.getByRole("button", { name: /see my options/i }));
    await expectScene("watershed", "landscape");

    fireEvent.click(
      await screen.findByRole("button", { name: "Tourism & short visit" }),
    );
    await expectScene("tourism", "landscape");

    // Drive to review_gate (confluence) exactly like OracleShell.test.tsx's
    // completeFreshInterview does for the tourism branch — no evaluation
    // fetch is ever reached, since review_gate is well before `verdict`.
    fireEvent.click(
      await screen.findByRole("button", { name: /one main purpose/i }),
    );
    fireEvent.change(await screen.findByRole("spinbutton"), {
      target: { value: "30" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));
    fireEvent.click(
      await screen.findByRole("button", { name: /^one entry$/i }),
    );
    await expectScene("confluence", "landscape");
  });
});

describe("OracleShell atlas — motion pause", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it("toggles data-motion and the button's own label, with no aria-pressed (FIX-ROUND-2 S2)", async () => {
    render(<OracleShell />);
    await screen.findByRole("button", { name: /^start$/i });
    expect(root()).toHaveAttribute("data-motion", "on");

    const pause = screen.getByRole("button", { name: "Pause motion" });
    expect(pause).not.toHaveAttribute("aria-pressed");
    fireEvent.click(pause);

    expect(root()).toHaveAttribute("data-motion", "paused");
    const resume = screen.getByRole("button", { name: "Resume motion" });
    expect(resume).not.toHaveAttribute("aria-pressed");

    fireEvent.click(resume);
    expect(root()).toHaveAttribute("data-motion", "on");
  });

  it("renders no Pause/Resume button when the OS already prefers reduced motion (FIX-ROUND-2 S2)", async () => {
    vi.mocked(useReducedMotion).mockReturnValueOnce(true);

    render(<OracleShell />);
    await screen.findByRole("button", { name: /^start$/i });
    expect(root()).toHaveAttribute("data-motion", "paused");
    expect(
      screen.queryByRole("button", { name: /pause motion|resume motion/i }),
    ).toBeNull();
  });
});

describe("OracleShell atlas — language", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it("framing shows the resume sentence and an unchecked save checkbox by default", async () => {
    render(<OracleShell />);
    await screen.findByRole("button", { name: /^start$/i });
    expect(
      screen.getByText(
        /save the full interview, including sensitive immigration/i,
      ),
    ).toBeInTheDocument();
    const checkbox = screen.getByRole("checkbox", {
      name: /save my interview on this device for 2 hours/i,
    });
    expect(checkbox).not.toBeChecked();
  });

  it("save checkbox's accessible name is ONLY the short opt-in text, the full sentence is a separate visible description (FIX-ROUND-2 S3)", async () => {
    render(<OracleShell />);
    await screen.findByRole("button", { name: /^start$/i });
    const checkbox = screen.getByRole("checkbox", {
      name: "Save my interview on this device for 2 hours",
    });
    const describedById = checkbox.getAttribute("aria-describedby");
    expect(describedById).not.toBeNull();
    const description = document.getElementById(describedById!);
    expect(description).not.toBeNull();
    expect(description).toBeVisible();
    expect(description?.textContent).toMatch(
      /save the full interview, including sensitive immigration/i,
    );
    // The description text is NOT folded into the checkbox's own name.
    expect(checkbox.getAttribute("aria-label")).toBeNull();
  });

  it("switches header/tool copy to Indonesian", async () => {
    render(<OracleShell />);
    await screen.findByRole("button", { name: /^start$/i });
    fireEvent.click(
      screen.getByRole("button", { name: /switch to bahasa indonesia/i }),
    );
    expect(screen.getByRole("button", { name: "Mulai" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Jeda animasi" }),
    ).toBeInTheDocument();
  });
});

describe("OracleShell atlas — Your route pruning", () => {
  // Verified against the real reducer (flowReducer walk, 2026-09-27): after
  // `category=work` the tree asks `trip_scope` (shared with every other
  // category) BEFORE any work-specific question, then `sponsor_category`,
  // then (a `sponsor_category=NONE` premise) `sponsor_government_
  // collaboration`, and only then `work_payer` — the fact this test proves
  // gets pruned when the category changes.
  const WORK_ANSWERS = [
    ["in_indonesia", "no"],
    ["holds_stay_permit", "no"],
    ["nationalities", "US"],
    ["birth_date", "1990-01-01"],
    ["category", "work"],
    ["trip_scope", "single"],
    ["sponsor_category", "NONE"],
    ["sponsor_government_collaboration", "yes"],
    ["work_payer", "yes"],
  ] as const;

  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    installResumeAt(WORK_ANSWERS);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("changing category from work to tourism prunes the work-only fact from the ledger via the reducer", async () => {
    const factsSoFar: OracleFacts = Object.fromEntries(WORK_ANSWERS);
    const workPayerValue = formatFactDisplay("en", "work_payer", "yes");
    const workPayerPrompt = translate(
      "en",
      questionPromptI18nKey(QUESTIONS.work_payer, factsSoFar) as I18nKey,
    );

    render(<OracleShell />);

    // Hydrated straight onto the question right after `work_payer` — the
    // route button only needs ONE answered question to appear, which this
    // resume snapshot already has several of.
    const routeButton = await screen.findByRole("button", {
      name: "Your route",
    });
    fireEvent.click(routeButton);

    let dialog = document.querySelector(".oracle-atlas-route") as HTMLElement;
    // The work-specific fact is on the ledger before the switch.
    expect(within(dialog).getByText(workPayerValue)).toBeInTheDocument();

    fireEvent.click(within(dialog).getByText("Explore another direction"));
    fireEvent.click(within(dialog).getByText("Tourism & short visit"));

    // Re-open to inspect the pruned ledger (selecting a category closes the
    // dialog, same as Change — the REQUIRED FIX for this mandate).
    await act(async () => {});
    fireEvent.click(await screen.findByRole("button", { name: "Your route" }));
    dialog = document.querySelector(".oracle-atlas-route") as HTMLElement;
    expect(within(dialog).queryByText(workPayerPrompt)).toBeNull();
    expect(within(dialog).queryByText(workPayerValue)).toBeNull();
    expect(
      within(dialog).getByText("Tourism & short visit"),
    ).toBeInTheDocument();
  });
});

// ENDING-ROUND scope extension (Dux, coordinator-relayed): the header badge's
// visible text ("Visa decision support") is unchanged and stays; only the
// `title` tooltip exposing "deterministic engine" wording is removed.
describe("OracleShell atlas — badge (ENDING-ROUND scope extension)", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it("renders the badge text with no title attribute and no 'deterministic' wording anywhere on screen", async () => {
    render(<OracleShell />);
    await screen.findByRole("button", { name: /^start$/i });
    const badge = document.querySelector(".oracle-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(
      translate("en", "prototype.badge" as I18nKey),
    );
    expect(badge).not.toHaveAttribute("title");
    expect(document.body.textContent).not.toMatch(/deterministic/i);
  });
});

// F3 fix (ORACLE-PROD-20260927 delta, gate finding 3): `revealVerdict` used
// to gate the verdict ViewTransition only on the OS's own reduced-motion
// signal, so pressing the in-app Pause control left the transition running
// anyway. It now gates on the same effective `motion` flag
// (`!reducedMotion && !motionPaused`) the rest of the shell already reads.
describe("OracleShell atlas — verdict ViewTransition respects Pause (F3)", () => {
  const CONFIRMATION_ANSWERS = [
    ["in_indonesia", "no"],
    ["holds_stay_permit", "no"],
    ["nationalities", "US"],
    ["birth_date", "1990-01-01"],
    ["category", "tourism"],
    ["trip_scope", "single"],
    ["stay_days", "30"],
    ["entry_pattern", "SINGLE"],
    ["review_gate", "none"],
  ] as const;

  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
    installResumeAt(CONFIRMATION_ANSWERS);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    Reflect.deleteProperty(document, "startViewTransition");
  });

  function stubStartViewTransition() {
    const spy = vi.fn((callback: () => void) => {
      callback();
      return {
        ready: Promise.resolve(),
        finished: Promise.resolve(),
        updateCallbackDone: Promise.resolve(),
      };
    });
    Object.assign(document, { startViewTransition: spy });
    return spy;
  }

  it("makes zero startViewTransition calls confirming into the verdict while Pause is active", async () => {
    const spy = stubStartViewTransition();
    render(<OracleShell />);

    await screen.findByRole("heading", {
      name: translate("en", "confirmation.title"),
    });
    fireEvent.click(screen.getByRole("button", { name: "Pause motion" }));
    expect(root()).toHaveAttribute("data-motion", "paused");

    fireEvent.click(
      screen.getByRole("button", {
        name: translate("en", "confirmation.cta"),
      }),
    );
    await waitFor(() =>
      expect(
        document.querySelector(".oracle-verdict-card"),
      ).toBeInTheDocument(),
    );
    expect(spy).not.toHaveBeenCalled();
  });

  it("makes exactly one startViewTransition call confirming into the verdict when motion is not paused", async () => {
    const spy = stubStartViewTransition();
    render(<OracleShell />);

    await screen.findByRole("heading", {
      name: translate("en", "confirmation.title"),
    });
    expect(root()).toHaveAttribute("data-motion", "on");

    fireEvent.click(
      screen.getByRole("button", {
        name: translate("en", "confirmation.cta"),
      }),
    );
    await waitFor(() =>
      expect(
        document.querySelector(".oracle-verdict-card"),
      ).toBeInTheDocument(),
    );
    expect(spy).toHaveBeenCalledOnce();
  });
});
