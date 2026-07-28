import { act } from "react";
import { fireEvent, render, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OracleShell } from "./OracleShell";
import { mapOracleFactsToApplicantFacts } from "../_lib/fact-mapper";

/**
 * SHADOW-mode invisibility (mandate acceptance test 5 — the load-bearing
 * one): drives the mock interview to the verdict screen twice — once with
 * `fetch` mocked to resolve 200, once mocked to REJECT — and asserts the
 * rendered container HTML is byte-identical between the two runs.
 *
 * Path driven (offshore tourist, short stay, no review-gate flags — reaches
 * SUPPORTED_CANDIDATES, the richest verdict render: VerdictReveal + the
 * full OutcomeSheet, not just an early-abstain state):
 *   framing -> in_indonesia="no" (skips permit_expiry entirely) ->
 *   category="tourism" -> tourism_duration="short" -> review_gate="none"
 *   -> confirmation -> verdict.
 *
 * This test file is NOT one of the mandate's explicitly enumerated NEW
 * files — it exists because acceptance test 5 cannot be satisfied any
 * other way (it requires driving `OracleShell` itself, the one place the
 * two new one-shot effects interact). See the shipped report for this
 * note.
 */

const SEE_MY_OPTIONS = "See my options";

async function driveToVerdict(container: HTMLElement): Promise<void> {
  const scope = within(container);

  fireEvent.click(scope.getByRole("button", { name: "Start" }));
  fireEvent.click(
    scope.getByRole("button", { name: "No, I’m planning ahead" }),
  );
  fireEvent.click(scope.getByRole("button", { name: "Tourism & short visit" }));
  fireEvent.click(scope.getByRole("button", { name: "Up to 30 days" }));
  fireEvent.click(scope.getByLabelText("None of these apply to me"));
  fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // review-gate continue
  fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // ConfirmationCard confirm

  // The verdict render triggers OracleShell's two one-shot effects
  // (frozenToday, then the SHADOW POST) across an extra internal render
  // pass. `fireEvent`'s own `act()` wrapping already flushes React to
  // quiescence synchronously, but this drains any leftover microtask
  // defensively before the DOM is read.
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("OracleShell — SHADOW mode is invisible to the render path", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("renders byte-identical verdict HTML whether the shadow POST resolves 200 or rejects", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const resolvedRun = render(<OracleShell />);
    await driveToVerdict(resolvedRun.container);
    // Sanity: the shadow POST really fired on this run — otherwise this
    // test would trivially pass without ever exercising the invariant it
    // claims to test.
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const resolvedHtml = resolvedRun.container.innerHTML;
    resolvedRun.unmount();

    global.fetch = vi.fn().mockRejectedValue(new Error("network down"));
    const rejectedRun = render(<OracleShell />);
    await driveToVerdict(rejectedRun.container);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const rejectedHtml = rejectedRun.container.innerHTML;
    rejectedRun.unmount();

    expect(rejectedHtml).toBe(resolvedHtml);
  });

  it("renders byte-identical verdict HTML whether the shadow POST resolves or fetch itself throws synchronously", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const resolvedRun = render(<OracleShell />);
    await driveToVerdict(resolvedRun.container);
    const resolvedHtml = resolvedRun.container.innerHTML;
    resolvedRun.unmount();

    global.fetch = vi.fn(() => {
      throw new Error("fetch is not available");
    });
    const throwingRun = render(<OracleShell />);
    await driveToVerdict(throwingRun.container);
    const throwingHtml = throwingRun.container.innerHTML;
    throwingRun.unmount();

    expect(throwingHtml).toBe(resolvedHtml);
  });

  it("reaches the SUPPORTED_CANDIDATES verdict screen on this path (sanity the drive is real, not a stub)", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const { container, unmount } = render(<OracleShell />);
    await driveToVerdict(container);
    expect(container.querySelector(".oracle-outcome")).not.toBeNull();
    unmount();
  });
});

/**
 * SHADOW dedupe truth table (bug fix, 2026-07-27): exactly one SHADOW POST
 * per (interview attempt x distinct WIRE payload). Two independent review
 * rounds found the dedupe key wrong in both of its dimensions — CONTENT
 * (keyed on raw UI facts instead of the mapped wire payload the engine
 * actually receives) and LIFETIME (a `useRef` that outlives RESTART, so a
 * second honest interview with the same answers produced no second row).
 * `OracleShell.tsx`'s own dedupe-effect docstring carries the full fix
 * rationale and the attempt-identity design; these four tests drive the
 * REAL component through every row of the table that motivated it.
 */
describe("OracleShell — SHADOW dedupe truth table (attempt x wire payload)", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  /**
   * category="remote" path with `remote_clients="foreign"` — the one path
   * that visits `remote_income`, the load-bearing no-FactPath field row C
   * needs. `review_gate` is always answered "none" here so it never
   * becomes a second confound alongside `remote_income`.
   */
  async function driveRemoteToVerdict(
    container: HTMLElement,
    remoteIncomeLabel: string,
  ): Promise<void> {
    const scope = within(container);
    fireEvent.click(scope.getByRole("button", { name: "Start" }));
    fireEvent.click(
      scope.getByRole("button", { name: "No, I’m planning ahead" }),
    );
    fireEvent.click(scope.getByRole("button", { name: "Remote worker" }));
    fireEvent.click(
      scope.getByRole("button", {
        name: "Abroad — they pay me from outside Indonesia",
      }),
    );
    fireEvent.click(scope.getByRole("button", { name: remoteIncomeLabel }));
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // review-gate continue
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // ConfirmationCard confirm

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  it("A: reaches verdict once, nothing else -> exactly 1 POST", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const { container } = render(<OracleShell />);

    await driveToVerdict(container);

    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("B: edits an answer that CHANGES the wire payload and re-confirms -> 2 POSTs, the 2nd carrying the new value", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const { container } = render(<OracleShell />);
    const scope = within(container);

    await driveToVerdict(container);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Verdict screen's "Edit answers" link -> back to the confirmation
    // screen, every fact still in place.
    fireEvent.click(scope.getByRole("button", { name: "Edit answers" }));

    // Jump back to the "category" question via THAT row's own "Edit"
    // button (several rows on screen each have one). Scoped to the
    // confirmation content, not the whole container — `LivingTree`'s
    // sidebar renders the same "Tourism & short visit" leaf text
    // alongside the confirmation card.
    const content = container.querySelector(
      ".oracle-main__content",
    ) as HTMLElement;
    const categoryValue = within(content).getByText("Tourism & short visit");
    const categoryRow = categoryValue.closest(
      ".oracle-confirmation__row",
    ) as HTMLElement;
    fireEvent.click(within(categoryRow).getByRole("button", { name: "Edit" }));

    // Materially different category: tourism -> work — `intent.purposes`
    // DOES have a FactPath, so the wire payload genuinely changes.
    fireEvent.click(scope.getByRole("button", { name: "Work & employment" }));
    fireEvent.click(
      scope.getByRole("button", { name: "No, I’m paid from abroad" }),
    );
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // review-gate continue
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // ConfirmationCard confirm

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(global.fetch).toHaveBeenCalledTimes(2);

    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const firstBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);

    // The FIRST post carried the original (tourism) answer...
    expect(firstBody.facts["intent.purposes"]).toEqual({
      status: "KNOWN",
      value: ["TOURISM"],
    });
    // ...and the SECOND post carries the edited (work) answer — never a
    // repeat of the pre-edit one.
    expect(secondBody.facts["intent.purposes"]).toEqual({
      status: "KNOWN",
      value: ["EMPLOYMENT"],
    });
  });

  it("C: edits ONLY remote_income (no FactPath) and re-confirms -> still 1 POST, wire payload provably identical", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const { container } = render(<OracleShell />);
    const scope = within(container);

    await driveRemoteToVerdict(container, "Yes, comfortably above it");
    expect(global.fetch).toHaveBeenCalledTimes(1);

    fireEvent.click(scope.getByRole("button", { name: "Edit answers" }));

    const content = container.querySelector(
      ".oracle-main__content",
    ) as HTMLElement;
    const incomeValue = within(content).getByText("Yes, comfortably above it");
    const incomeRow = incomeValue.closest(
      ".oracle-confirmation__row",
    ) as HTMLElement;
    fireEvent.click(within(incomeRow).getByRole("button", { name: "Edit" }));

    // ONLY remote_income changes here — review_gate is re-answered
    // identically ("none"), so the ONLY variable between the two
    // confirmations is a field with no FactPath at all.
    fireEvent.click(
      scope.getByRole("button", { name: "No, it doesn’t clear the floor" }),
    );
    fireEvent.click(scope.getByLabelText("None of these apply to me"));
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // review-gate continue
    fireEvent.click(scope.getByRole("button", { name: SEE_MY_OPTIONS })); // ConfirmationCard confirm

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    // The suppression claim: still exactly 1 POST, never a 2nd.
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Prove the suppression is CORRECT, not incidental: independently map
    // both raw-fact states the UI just walked through (remote_income
    // "above" vs "below", everything else held constant) to their wire
    // payloads via the SAME pure mapper the component uses, and assert
    // they're deep-equal — remote_income really has zero wire
    // representation, exactly as fact-mapper.ts's own docstring claims.
    const commonFacts = {
      in_indonesia: "no",
      category: "remote",
      remote_clients: "foreign",
      review_gate: "none",
    };
    const collectedAt = new Date("2026-07-27T00:00:00.000Z");
    const aboveWire = mapOracleFactsToApplicantFacts(
      { ...commonFacts, remote_income: "above" },
      { assessmentId: "test-above", collectedAt },
    ).facts;
    const belowWire = mapOracleFactsToApplicantFacts(
      { ...commonFacts, remote_income: "below" },
      { assessmentId: "test-below", collectedAt },
    ).facts;
    expect(belowWire).toEqual(aboveWire);

    // And the one POST that DID fire actually carries that predicted wire
    // payload — the suppression really is of an already-sent identical
    // payload, not a coincidence independent of what was sent.
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const sentBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(sentBody.facts).toEqual(aboveWire);
  });

  it("D: restarts and retraces the SAME answers to a new verdict -> 2 POSTs, two genuinely separate interviews", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    const { container } = render(<OracleShell />);
    const scope = within(container);

    await driveToVerdict(container);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // "Start over" -> RESTART -> back to "framing" — then retrace the
    // EXACT SAME answers as the first attempt.
    fireEvent.click(scope.getByRole("button", { name: "Start over" }));
    await driveToVerdict(container);

    expect(global.fetch).toHaveBeenCalledTimes(2);

    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const firstBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    const secondBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    // Same retraced answers -> the SAME wire payload — yet still a
    // SECOND honest row, because it's a genuinely separate interview
    // attempt, never suppressed as a "duplicate" of the first.
    expect(secondBody.facts).toEqual(firstBody.facts);
  });
});
