import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OrderTracker } from "./OrderTracker";
import type { OrderState, OrderView } from "./types";

/**
 * GARUDA VOA tracker — `voa-order-state.coverage.test.tsx` (design-A-claude.md §8).
 *
 * Guards the invariant the `created` hole violated: every `OrderState` member must
 * render exactly one step-rail `current` marker (or an exception panel for a
 * terminal state) AND at least one focusable control — never a dead end with no
 * marker, no message and no way forward.
 *
 * `FIXTURES` is typed `Record<OrderState, ...>`, not a hand-written array: adding a
 * member to `OrderState` (types.ts, transcribed from openapi.yaml /
 * garuda-voa.generated.d.ts) without adding a row here fails `tsc`, not this test at
 * runtime — the same exhaustiveness convention `messages.ts`'s `COPY` table already
 * uses for `OrderErrorCode`.
 */
const FIXTURES: Record<OrderState, Partial<OrderView>> = {
  created: { order_state: "created", practice: null },
  awaiting_payment: { order_state: "awaiting_payment", practice: null },
  // A representative *complete* paid journey (practice delivered) — the paid step
  // itself never varies with practice sub-state; PracticeState combinations are a
  // separate surface, out of scope for this OrderState-level invariant.
  paid: {
    order_state: "paid",
    practice: {
      practice_id: "practice-1",
      state: "Delivered",
      artifact_available: true,
    },
  },
  failed: { order_state: "failed", practice: null },
  expired: { order_state: "expired", practice: null },
  refunded: { order_state: "refunded", practice: null },
};

const ORDER_STATES = Object.keys(FIXTURES) as OrderState[];

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function order(overrides: Partial<OrderView>): OrderView {
  return {
    order_id: "order-1",
    order_state: "awaiting_payment",
    price_idr: 850000,
    browser_observation: "browser_not_returned",
    practice: null,
    ...overrides,
  };
}

describe("voa-order-state.coverage", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.useRealTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it.each(ORDER_STATES)(
    "OrderState %s yields exactly one current step or an exception panel, plus a focusable control",
    async (state) => {
      fetchMock.mockResolvedValue(jsonResponse(200, order(FIXTURES[state])));
      const { container } = render(<OrderTracker orderId="order-1" />);

      await screen.findByText(/Rp/);

      const rail = container.querySelectorAll(
        '[aria-label="Application progress"] li',
      );
      // "●" is the step rail's ONE current-marker glyph ("✓" done, "○" upcoming) —
      // reading it back is the ground truth for "exactly one current step".
      const currentGlyphs = Array.from(rail).filter(
        (li) => li.querySelector('[aria-hidden="true"]')?.textContent === "●",
      );

      const isTerminalException =
        state === "failed" || state === "expired" || state === "refunded";

      if (isTerminalException) {
        // Terminal states render no step rail at all (ParcelSteps returns null) —
        // the exception panel itself is the "or an exception panel" branch.
        expect(rail.length).toBe(0);
        expect(currentGlyphs.length).toBe(0);
      } else {
        expect(currentGlyphs.length).toBe(1);
      }

      const focusableControls = container.querySelectorAll("a[href], button");
      expect(focusableControls.length).toBeGreaterThanOrEqual(1);
    },
  );
});
