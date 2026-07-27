import { act } from "react";
import { fireEvent, render, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OracleShell } from "./OracleShell";
import {
  stableFactsKey,
  mapOracleFactsToApplicantFacts,
} from "../_lib/fact-mapper";

/**
 * INDEPENDENT adversarial review of the SHADOW dedupe fix
 * (OracleShell.tsx's dedupe effect + flow.ts's `attempt` counter +
 * fact-mapper.ts's `stableFactsKey`). Written from scratch by an
 * independent reviewer, driving the REAL component tree exactly like the
 * shipped `OracleShell.test.tsx` truth-table tests, but exercising
 * different paths and different break-it angles: language toggle, theme
 * toggle, LivingTree tap-to-edit, Back navigation, SELECT_CATEGORY
 * ("what instead"), and key-stability of `stableFactsKey` itself.
 */

const SEE_MY_OPTIONS = "See my options";

function okFetch() {
  return vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
}

async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function driveTourismToVerdict(container: HTMLElement): Promise<void> {
  const scope = within(container);
  fireEvent.click(scope.getByRole("button", { name: "Start" }));
  fireEvent.click(
    scope.getByRole("button", { name: "No, I’m planning ahead" }),
  );
  fireEvent.click(scope.getByRole("button", { name: "Tourism & short visit" }));
  fireEvent.click(scope.getByRole("button", { name: "Up to 30 days" }));
  fireEvent.click(scope.getByLabelText("None of these apply to me"));
  fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
  fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
  await flush();
}

describe("Independent adversarial review — SHADOW dedupe", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("language toggle mid-flow AND at the verdict screen never changes the POST count", async () => {
    global.fetch = okFetch();
    const { container } = render(<OracleShell />);
    const scope = within(container);

    fireEvent.click(scope.getByRole("button", { name: "Start" }));
    // Toggle to Indonesian and back to English mid-interview — SET_LANGUAGE
    // never touches `facts`, so this must be a complete no-op for dedupe.
    fireEvent.click(scope.getByRole("button", { name: "Indonesia" }));
    fireEvent.click(scope.getByRole("button", { name: "English" }));
    fireEvent.click(
      scope.getByRole("button", { name: "No, I’m planning ahead" }),
    );
    fireEvent.click(
      scope.getByRole("button", { name: "Tourism & short visit" }),
    );
    fireEvent.click(scope.getByRole("button", { name: "Up to 30 days" }));
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Toggle language repeatedly WHILE at "verdict" — the dedupe effect's
    // dependency array includes `state.facts`, and SET_LANGUAGE never
    // creates a new facts object, so this must not re-fire the POST.
    fireEvent.click(scope.getByRole("button", { name: "Indonesia" }));
    await flush();
    fireEvent.click(scope.getByRole("button", { name: "English" }));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("theme toggle mid-flow AND at the verdict screen never changes the POST count", async () => {
    global.fetch = okFetch();
    const { container } = render(<OracleShell />);
    const scope = within(container);

    // ThemeToggle lives entirely in OracleShell's own `useState` — never
    // touches `useOracleFlow` state at all.
    fireEvent.click(
      scope.getByRole("button", { name: "Switch between light and dark" }),
    );
    await driveTourismToVerdict(container);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    fireEvent.click(
      scope.getByRole("button", { name: "Switch between light and dark" }),
    );
    await flush();
    fireEvent.click(
      scope.getByRole("button", { name: "Switch between light and dark" }),
    );
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("LivingTree tap-to-edit on a trunk step ('Category'), re-answered IDENTICALLY, still dedupes to 1 POST", async () => {
    global.fetch = okFetch();
    const { container } = render(<OracleShell />);
    const scope = within(container);

    await driveTourismToVerdict(container);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Trunk tap-to-edit, NOT the confirmation card's row-level Edit and
    // NOT "Edit answers" — a third, independent way back into the tree
    // from the verdict screen (design doc §3 interaction #6).
    fireEvent.click(
      scope.getByRole("button", { name: "Edit answer: Category" }),
    );

    // Re-answer with the EXACT same values all the way back to verdict.
    fireEvent.click(
      scope.getByRole("button", { name: "Tourism & short visit" }),
    );
    fireEvent.click(scope.getByRole("button", { name: "Up to 30 days" }));
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("LivingTree tap-to-edit changes a UI answer to a DIFFERENT value mapping to the SAME wire value -> still 1 POST", async () => {
    global.fetch = okFetch();
    const { container } = render(<OracleShell />);
    const scope = within(container);

    // remote path, remote_clients="mixed" first.
    fireEvent.click(scope.getByRole("button", { name: "Start" }));
    fireEvent.click(
      scope.getByRole("button", { name: "No, I’m planning ahead" }),
    );
    fireEvent.click(scope.getByRole("button", { name: "Remote worker" }));
    fireEvent.click(scope.getByRole("button", { name: "A mix of both" }));
    fireEvent.click(
      scope.getByRole("button", { name: "Yes, comfortably above it" }),
    );
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Edit "Where clients sit" via the LivingTree trunk, switch "mixed" ->
    // "indonesian" — `mapRemoteClientsDerived` treats both identically
    // (KNOWN(true)/KNOWN(true) for both derived FactPaths) — then
    // re-answer everything downstream identically.
    fireEvent.click(
      scope.getByRole("button", { name: "Edit answer: Where clients sit" }),
    );
    fireEvent.click(
      scope.getByRole("button", {
        name: "Indonesia — I’m effectively employed here",
      }),
    );
    fireEvent.click(
      scope.getByRole("button", { name: "Yes, comfortably above it" }),
    );
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Independent proof the wire payloads really are byte-identical for
    // "mixed" vs "indonesian", using the SAME pure mapper the component
    // uses — the suppression is provably correct, not incidental.
    const collectedAt = new Date("2026-07-27T00:00:00.000Z");
    const base = {
      in_indonesia: "no",
      category: "remote",
      remote_income: "above",
      review_gate: "none",
    };
    const mixedWire = mapOracleFactsToApplicantFacts(
      { ...base, remote_clients: "mixed" },
      { assessmentId: "t1", collectedAt },
    ).facts;
    const indonesianWire = mapOracleFactsToApplicantFacts(
      { ...base, remote_clients: "indonesian" },
      { assessmentId: "t2", collectedAt },
    ).facts;
    expect(indonesianWire).toEqual(mixedWire);
  });

  it("Back navigation after an EDIT, re-answered identically, still dedupes to 1 POST", async () => {
    global.fetch = okFetch();
    const { container } = render(<OracleShell />);
    const scope = within(container);

    await driveTourismToVerdict(container);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // "Edit answers" -> confirmation, then the category row's own "Edit"
    // -> the "category" question (canGoBack now true, since history has
    // > 1 entry: framing, in_indonesia, category).
    fireEvent.click(scope.getByRole("button", { name: "Edit answers" }));
    const content = container.querySelector(
      ".oracle-main__content",
    ) as HTMLElement;
    const categoryValue = within(content).getByText("Tourism & short visit");
    const categoryRow = categoryValue.closest(
      ".oracle-confirmation__row",
    ) as HTMLElement;
    fireEvent.click(within(categoryRow).getByRole("button", { name: "Edit" }));

    // Now use the literal "Back" affordance (QuestionScreen's own back
    // link) to step up ONE MORE level, past "category" to "in_indonesia".
    fireEvent.click(scope.getByRole("button", { name: "Back" }));

    // Retrace forward with the IDENTICAL answers all the way to verdict.
    fireEvent.click(
      scope.getByRole("button", { name: "No, I’m planning ahead" }),
    );
    fireEvent.click(
      scope.getByRole("button", { name: "Tourism & short visit" }),
    );
    fireEvent.click(scope.getByRole("button", { name: "Up to 30 days" }));
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("Back navigation that changes the eventual wire payload correctly produces a 2nd POST", async () => {
    global.fetch = okFetch();
    const { container } = render(<OracleShell />);
    const scope = within(container);

    await driveTourismToVerdict(container);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    fireEvent.click(scope.getByRole("button", { name: "Edit answers" }));
    const content = container.querySelector(
      ".oracle-main__content",
    ) as HTMLElement;
    const categoryValue = within(content).getByText("Tourism & short visit");
    const categoryRow = categoryValue.closest(
      ".oracle-confirmation__row",
    ) as HTMLElement;
    fireEvent.click(within(categoryRow).getByRole("button", { name: "Edit" }));
    fireEvent.click(scope.getByRole("button", { name: "Back" }));

    // This time answer in_indonesia DIFFERENTLY ("yes" instead of "no") —
    // a genuinely different wire payload (adds permit_expiry, changes
    // `immigration.currently_in_indonesia`).
    fireEvent.click(scope.getByRole("button", { name: "Yes, I’m here" }));
    const dateInput = container.querySelector(
      'input[type="date"]',
    ) as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: "2027-01-01" } });
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(
      scope.getByRole("button", { name: "Tourism & short visit" }),
    );
    fireEvent.click(scope.getByRole("button", { name: "Up to 30 days" }));
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it("SELECT_CATEGORY ('what instead' from NO_SUPPORTED_PATH) reaching a 2nd verdict fires a 2nd POST", async () => {
    global.fetch = okFetch();
    const { container } = render(<OracleShell />);
    const scope = within(container);

    // category=work + work_payer="no" -> the ONLY work-category candidate
    // (E23) requires work_payer="yes" -> 0 candidates -> NO_SUPPORTED_PATH.
    fireEvent.click(scope.getByRole("button", { name: "Start" }));
    fireEvent.click(
      scope.getByRole("button", { name: "No, I’m planning ahead" }),
    );
    fireEvent.click(scope.getByRole("button", { name: "Work & employment" }));
    fireEvent.click(
      scope.getByRole("button", { name: "No, I’m paid from abroad" }),
    );
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    // Sanity: this really is the NO_SUPPORTED_PATH alternatives screen.
    expect(container.querySelector(".oracle-outcome")).not.toBeNull();

    // "what instead" -> SELECT_CATEGORY("remote") -> jumps to
    // remote_clients (NOT straight to verdict) -> answer through to a
    // 2nd, genuinely different verdict.
    fireEvent.click(scope.getByRole("button", { name: "Remote worker" }));
    fireEvent.click(
      scope.getByRole("button", {
        name: "Abroad — they pay me from outside Indonesia",
      }),
    );
    fireEvent.click(
      scope.getByRole("button", { name: "Yes, comfortably above it" }),
    );
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS }));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(2);

    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const firstBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(firstBody.facts["intent.purposes"]).toEqual({
      status: "KNOWN",
      value: ["EMPLOYMENT"],
    });
    expect(secondBody.facts["intent.purposes"]).toEqual({
      status: "KNOWN",
      value: ["REMOTE_WORK"],
    });
  });
});

describe("Independent adversarial review — stableFactsKey serialization stability", () => {
  it("is independent of the TOP-LEVEL key insertion order of the real 40-key wire object", () => {
    const collectedAt = new Date("2026-07-27T00:00:00.000Z");
    const wire = mapOracleFactsToApplicantFacts(
      {
        in_indonesia: "no",
        category: "tourism",
        tourism_duration: "short",
        review_gate: "none",
      },
      { assessmentId: "a", collectedAt },
    ).facts;

    const naturalKey = stableFactsKey(wire);

    // Rebuild the SAME 40 entries in REVERSED key order — this simulates
    // a hypothetical future call site that assembles the object
    // differently (e.g. via `Object.assign` in another order, or a
    // refactor that stops using the one literal in
    // `mapOracleFactsToApplicantFacts`).
    const reversedEntries = Object.fromEntries(
      Object.entries(wire).reverse(),
    ) as typeof wire;
    const reversedKey = stableFactsKey(reversedEntries);

    expect(reversedKey).toBe(naturalKey);
  });

  it("DOES depend on the insertion order INSIDE a nested FactValue object (JSON.stringify is not deep-canonical) — latent, but unreachable via the real mapper", () => {
    const collectedAt = new Date("2026-07-27T00:00:00.000Z");
    const wire = mapOracleFactsToApplicantFacts(
      { in_indonesia: "yes" },
      { assessmentId: "a", collectedAt },
    ).facts;

    const naturalKey = stableFactsKey(wire);

    // Hand-construct a semantically-identical copy where ONE nested
    // FactValue's own keys are written in the opposite order
    // ({value, status} instead of {status, value}). `known()`/
    // `unknownFact()` never do this in the real module (verified: they
    // are the sole two factories, both used unconditionally with a fixed
    // literal key order) — but `stableFactsKey`'s own docstring claims
    // "order-independent" without that caveat, so this documents exactly
    // how far the guarantee actually extends.
    const mutated = {
      ...wire,
      "immigration.currently_in_indonesia": {
        value: (
          wire["immigration.currently_in_indonesia"] as { value: boolean }
        ).value,
        status: "KNOWN",
      },
    } as typeof wire;

    const mutatedKey = stableFactsKey(mutated);

    // These two objects are DEEPLY/semantically equal...
    expect(mutated).toEqual(wire);
    // ...yet `stableFactsKey` treats them as different strings. This is a
    // real gap in the "order-independent" claim, not exercised by any
    // live call site today (see grep evidence in the review notes), so it
    // is reported as a robustness note, not a reachable dedupe defect.
    expect(mutatedKey).not.toBe(naturalKey);
  });
});
