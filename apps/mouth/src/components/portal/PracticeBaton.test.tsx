import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { PracticeBaton, statusToBaton, STATUS_TO_BATON } from "./PracticeBaton";

describe("statusToBaton — Your Turn / Our Turn derivation", () => {
  // Every status in PROCESS_STATUS_CONFIG (process/page.tsx, mirrored from CRM)
  // must resolve to a deliberate baton. This is the SSOT contract.
  const cases: Array<[string, ReturnType<typeof statusToBaton>]> = [
    // Your Turn — client must act
    ["payment_pending", "your_turn"],
    ["waiting_payment", "your_turn"],
    ["waiting_documents", "your_turn"],
    ["quotation_sent", "your_turn"],
    ["sending_invoice", "your_turn"],
    ["rejected", "your_turn"],
    // Our Turn — Bali Zero is working
    ["inquiry", "our_turn"],
    ["in_progress", "our_turn"],
    ["on_process", "our_turn"],
    ["submitted_to_gov", "our_turn"],
    ["uploaded", "our_turn"],
    ["pending", "our_turn"],
    // Done — closed
    ["approved", "done"],
    ["completed", "done"],
    ["verified", "done"],
    ["cancelled", "done"],
  ];

  it.each(cases)("maps %s → %s", (status, expected) => {
    expect(statusToBaton(status)).toBe(expected);
  });

  it("is case- and whitespace-insensitive", () => {
    expect(statusToBaton("  WAITING_DOCUMENTS ")).toBe("your_turn");
    expect(statusToBaton("In_Progress")).toBe("our_turn");
  });

  it("defaults unknown/empty status to our_turn (never falsely tells client to act)", () => {
    expect(statusToBaton("some_new_unmapped_status")).toBe("our_turn");
    expect(statusToBaton(undefined)).toBe("our_turn");
    expect(statusToBaton(null)).toBe("our_turn");
    expect(statusToBaton("")).toBe("our_turn");
  });

  it("never leaves a client-actionable status as our_turn by accident", () => {
    // Defensive: any status whose name signals client action should be your_turn
    for (const [status, baton] of Object.entries(STATUS_TO_BATON)) {
      if (/waiting_(payment|documents)|payment_pending|rejected/.test(status)) {
        expect(baton).toBe("your_turn");
      }
    }
  });
});

describe("PracticeBaton — rendering", () => {
  it("renders a vibrant CTA with the concrete next action when it's the client's turn", () => {
    const onAction = vi.fn();
    render(
      <PracticeBaton
        status="waiting_documents"
        nextActionLabel="Upload your passport scan"
        onAction={onAction}
      />,
    );
    expect(screen.getByText("Your turn")).toBeTruthy();
    const cta = screen.getByText("Upload your passport scan");
    expect(cta).toBeTruthy();
    fireEvent.click(cta);
    expect(onAction).toHaveBeenCalledOnce();
  });

  it("renders a calm reassurance (no CTA) when it's our turn", () => {
    render(
      <PracticeBaton
        status="submitted_to_gov"
        statusLabel="Submitted to Immigration"
        lastUpdate="2 hours ago"
      />,
    );
    expect(screen.getByText("Our turn")).toBeTruthy();
    expect(screen.getByText("Submitted to Immigration")).toBeTruthy();
    expect(screen.getByText(/Last update: 2 hours ago/)).toBeTruthy();
    // No actionable button in our-turn state
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("exposes the baton via data attribute for downstream styling/tests", () => {
    const { container } = render(<PracticeBaton status="approved" />);
    expect(container.querySelector('[data-baton="done"]')).toBeTruthy();
  });
});
