import React from "react";
import { describe, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  act,
  waitFor,
} from "@testing-library/react";
import { ToastProvider, useToast, toastDuration, SLIP_UNDO_MS } from "./toast";

// Test component that exposes useToast
function ToastTester() {
  const { toast, success, error, warning, info, dismiss, clear } = useToast();
  return (
    <div>
      <button onClick={() => success("Success!")}>Add Success</button>
      <button onClick={() => error("Error!", "Something failed")}>
        Add Error
      </button>
      <button onClick={() => warning("Warning!")}>Add Warning</button>
      <button onClick={() => info("Info!")}>Add Info</button>
      <button onClick={() => clear()}>Clear All</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <ToastTester />
    </ToastProvider>,
  );
}

describe("ToastProvider and useToast", () => {
  it("renders children within the provider", () => {
    renderWithProvider();
    expect(screen.getByText("Add Success")).toBeInTheDocument();
  });

  it("adds a success toast", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Success"));
    });

    expect(screen.getByText("Success!")).toBeInTheDocument();
  });

  it("adds an error toast with description", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Error"));
    });

    expect(screen.getByText("Error!")).toBeInTheDocument();
    expect(screen.getByText("Something failed")).toBeInTheDocument();
  });

  it("adds a warning toast", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Warning"));
    });

    expect(screen.getByText("Warning!")).toBeInTheDocument();
  });

  it("adds an info toast", () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Info"));
    });

    expect(screen.getByText("Info!")).toBeInTheDocument();
  });

  it("clears all toasts", async () => {
    renderWithProvider();

    act(() => {
      fireEvent.click(screen.getByText("Add Success"));
      fireEvent.click(screen.getByText("Add Warning"));
    });

    expect(screen.getByText("Success!")).toBeInTheDocument();
    expect(screen.getByText("Warning!")).toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByText("Clear All"));
    });

    // AnimatePresence may keep elements during exit animation;
    // wait for them to be removed from the DOM
    await waitFor(() => {
      expect(screen.queryByText("Success!")).not.toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.queryByText("Warning!")).not.toBeInTheDocument();
    });
  });
});

describe("useToast outside provider", () => {
  it("throws when used without ToastProvider", () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<ToastTester />)).toThrow(
      "useToast must be used within a ToastProvider",
    );
    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// SAETTA-R19K K1c2 — the slip.
//
// A slip is the paper that follows a completed row and offers, for six
// seconds, to take it back. It is a FIFTH variant, not a restyle: every
// assertion below that pins the slip has a twin that pins one of the four
// shipped variants, because a guard that only knows what it wants is a guard
// that would also accept the four being dragged along with it.
// ---------------------------------------------------------------------------

function SlipTester({ onUndo = () => {} }: { onUndo?: () => void }) {
  const { slip, success, error, info } = useToast();
  return (
    <div>
      <button
        onClick={() =>
          slip(
            "Row archived",
            { label: "Undo", onClick: onUndo },
            "Client 8821",
          )
        }
      >
        Add Slip
      </button>
      <button onClick={() => success("Saved!")}>Add Plain Success</button>
      <button
        onClick={() =>
          error("Upload failed", "Try later", {
            label: "Retry",
            onClick: () => {},
          })
        }
      >
        Add Error With Action
      </button>
      <button onClick={() => info("Heads up")}>Add Plain Info</button>
    </div>
  );
}

function renderSlipTester(onUndo?: () => void) {
  return render(
    <ToastProvider>
      <SlipTester onUndo={onUndo} />
    </ToastProvider>,
  );
}

/** The card the toast is printed on, found from its own title. */
function cardFor(title: string): HTMLElement {
  const card = screen
    .getByText(title)
    .closest<HTMLElement>(".pointer-events-auto");
  if (!card) throw new Error(`no toast card around "${title}"`);
  return card;
}

describe("toastDuration — the window, without a clock", () => {
  it("gives a slip exactly the six-second Undo window", () => {
    expect(toastDuration("slip")).toBe(6000);
  });

  it("keeps SLIP_UNDO_MS and the slip's duration the SAME number", () => {
    // Guilt case for the defect this pairing exists to prevent: a caller that
    // schedules its commit on SLIP_UNDO_MS while the toast runs on some other
    // number would let an Undo click land after the row was already gone.
    expect(toastDuration("slip")).toBe(SLIP_UNDO_MS);
  });

  it("leaves the four shipped windows untouched", () => {
    expect(toastDuration("error")).toBe(8000);
    expect(toastDuration("success")).toBe(5000);
    expect(toastDuration("warning")).toBe(5000);
    expect(toastDuration("info")).toBe(5000);
  });

  it("lets an explicit duration win, for every variant alike", () => {
    expect(toastDuration("slip", 250)).toBe(250);
    expect(toastDuration("error", 250)).toBe(250);
    // Innocence for the `!== undefined` reading: a deliberate 0 means "never
    // auto-dismiss", and must not fall back to the variant default.
    expect(toastDuration("slip", 0)).toBe(0);
  });
});

describe("the slip toast", () => {
  it("prints the title, the description and the Undo label", () => {
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Slip"));
    });
    expect(screen.getByText("Row archived")).toBeInTheDocument();
    expect(screen.getByText("Client 8821")).toBeInTheDocument();
    expect(screen.getByText("Undo")).toBeInTheDocument();
  });

  it("calls the Undo action when the label is pressed", () => {
    const onUndo = vi.fn();
    renderSlipTester(onUndo);
    act(() => {
      fireEvent.click(screen.getByText("Add Slip"));
    });
    act(() => {
      fireEvent.click(screen.getByText("Undo"));
    });
    expect(onUndo).toHaveBeenCalledTimes(1);
  });

  it("is square and sits on the control boundary", () => {
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Slip"));
    });
    const cls = cardFor("Row archived").className;
    expect(cls).toContain("rounded-none");
    expect(cls).toContain("border-[var(--line-control)]");
    expect(cls).toContain("bg-[var(--bz-card)]");
  });

  it("carries no rounded corner, no left bar and no lifted ground", () => {
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Slip"));
    });
    const cls = cardFor("Row archived").className;
    expect(cls).not.toContain("rounded-lg");
    expect(cls).not.toContain("border-l-4");
    expect(cls).not.toContain("background-elevated");
    expect(cls).not.toContain("shadow-lg");
  });

  it("INNOCENCE: the shipped success card keeps all four of those", () => {
    // Without this twin the assertion above would still pass if the slip's
    // shape had simply been applied to every variant.
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Plain Success"));
    });
    const cls = cardFor("Saved!").className;
    expect(cls).toContain("rounded-lg");
    expect(cls).toContain("border-l-4");
    expect(cls).toContain("bg-[var(--background-elevated)]");
    expect(cls).toContain("shadow-lg");
    expect(cls).not.toContain("rounded-none");
  });

  it("shows no status glyph — a slip says it in words", () => {
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Slip"));
    });
    const card = cardFor("Row archived");
    // The dismiss "x" is a button; the status icon is not. Count only the
    // glyphs that are NOT inside a button.
    const loose = Array.from(card.querySelectorAll("svg")).filter(
      (svg) => !svg.closest("button"),
    );
    expect(loose).toHaveLength(0);
  });

  it("INNOCENCE: the shipped info card still shows its glyph", () => {
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Plain Info"));
    });
    const card = cardFor("Heads up");
    const loose = Array.from(card.querySelectorAll("svg")).filter(
      (svg) => !svg.closest("button"),
    );
    expect(loose.length).toBeGreaterThan(0);
  });

  it("gives Undo a 44px target on the control boundary, with no retry glyph", () => {
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Slip"));
    });
    const undo = screen.getByText("Undo").closest("button")!;
    expect(undo.className).toContain("min-h-11");
    expect(undo.className).toContain("border-[var(--line-control)]");
    // An Undo is not a retry: the circular-arrow glyph would say the opposite
    // of what the button does.
    expect(undo.querySelectorAll("svg")).toHaveLength(0);
  });

  it("INNOCENCE: the shipped error action keeps its retry glyph and its link look", () => {
    renderSlipTester();
    act(() => {
      fireEvent.click(screen.getByText("Add Error With Action"));
    });
    const retry = screen.getByText("Retry").closest("button")!;
    expect(retry.className).toContain("text-[var(--accent)]");
    expect(retry.className).not.toContain("min-h-11");
    expect(retry.querySelectorAll("svg").length).toBeGreaterThan(0);
  });
});
