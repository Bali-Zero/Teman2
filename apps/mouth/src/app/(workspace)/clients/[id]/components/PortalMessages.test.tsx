/**
 * PortalMessages — scroll-guard coverage.
 *
 * PR #4152 (commit ac1a3b21a, "stop client page auto-scrolling on initial
 * message load") added two guards to the scroll effect at
 * apps/mouth/src/app/(workspace)/clients/[id]/components/PortalMessages.tsx:55-68
 * and shipped with zero test files — before or after. The guards are:
 *
 *   GUARD-A  line 58  `!hasSeenData.current`          -> first data arrival never scrolls
 *   GUARD-B  line 64  `length > prevMessageCountRef`  -> only a GROWN count scrolls
 *
 * Two guards, two different bugs. Deleting either one leaves the other bug
 * open, so each guard gets a guilt test, and the feature itself gets two
 * innocence tests:
 *
 *   (a) guilt      first load must NOT scroll        -> dies if GUARD-A is removed
 *   (b) guilt      same-count poll must NOT scroll   -> dies if GUARD-B is removed
 *   (c) innocence  a new incoming message MUST scroll
 *   (d) innocence  sending your own message MUST scroll
 *
 * (c) and (d) are what stop the next reader from "simplifying" one guard
 * away because it looks redundant: with both guards gone the component still
 * scrolls on new messages, so guilt tests alone would let a change that
 * breaks the actual feature look green.
 *
 * (a) deliberately loads >= 1 message. GUARD-0 (line 56, `length === 0`)
 * returns before GUARD-A ever runs, so an empty first load would make (a)
 * pass without exercising GUARD-A at all — green while testing nothing.
 *
 * (a) turns out to cover GUARD-0 as well: deleting line 56 also kills it.
 * The initial render carries an empty `messages`, so without GUARD-0 that
 * render spends the `hasSeenData` flag, and the first real batch then falls
 * straight through to GUARD-B (2 > 0) and scrolls. GUARD-0 is what makes
 * GUARD-A land on the first DATA rather than the first RENDER — it is not
 * a decorative early-out.
 *
 * Timer pattern (fake timers + advanceTimersByTimeAsync inside act) is taken
 * from src/components/portal/PortalBottomNav.test.tsx:177-202, which polls the
 * same 30s interval. Neither test file in this directory uses timers at all,
 * so the prior art comes from a file that is already green elsewhere in the
 * repo rather than from a new style introduced by this PR.
 *
 * scrollIntoView is already stubbed globally at src/test/setup.tsx:133
 * (`Element.prototype.scrollIntoView = vi.fn()`). That stub is one vi.fn()
 * shared across files, so the handle is re-read and cleared explicitly in
 * beforeEach rather than trusting vi.clearAllMocks() alone.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { PortalMessages } from "./PortalMessages";
import { api } from "@/lib/api";
import type { PortalMessageThread } from "@/lib/api/crm/crm.types";

vi.mock("@/lib/api", () => ({
  api: {
    crm: {
      getPortalMessages: vi.fn(),
      sendPortalMessage: vi.fn(),
      markPortalMessageRead: vi.fn(),
    },
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    dismiss: vi.fn(),
  },
}));

const CLIENT_ID = 42;
const CLIENT_NAME = "Test Client";
const POLL_INTERVAL_MS = 30000; // PortalMessages.tsx:51

// direction "team_to_client" keeps the mark-as-read branch (PortalMessages.tsx:38)
// out of the picture entirely — it only fires for unread client_to_team rows.
const makeMessage = (id: number): PortalMessageThread => ({
  id,
  content: `Portal message ${id}`,
  direction: "team_to_client",
  sent_by: "agent@balizero.com",
  read_at: "2026-08-14T02:00:00Z",
  created_at: "2026-08-14T01:00:00Z",
});

const TWO_MESSAGES = [makeMessage(1), makeMessage(2)];
const THREE_MESSAGES = [makeMessage(1), makeMessage(2), makeMessage(3)];

/**
 * Queue one response batch per call, last batch repeating.
 *
 * Each call returns a FRESH array. This is not cosmetic: the real
 * getPortalMessages parses a new JSON payload every poll, so `setMessages`
 * always receives a new object identity and the `[messages]` effect always
 * re-runs. Handing back one shared array object instead makes setMessages an
 * Object.is no-op — React skips the re-render, the effect never fires, and a
 * test for GUARD-B would pass without ever reaching GUARD-B. Measured: with a
 * shared array, deleting GUARD-B killed 0 tests; with a fresh array it kills
 * exactly the poll test.
 */
const respondWith = (...batches: PortalMessageThread[][]) => {
  let call = 0;
  vi.mocked(api.crm.getPortalMessages).mockImplementation(async () => {
    const batch = batches[Math.min(call, batches.length - 1)];
    call += 1;
    return { messages: [...batch], total: batch.length };
  });
};

/** Rendered message bodies — PortalMessages.tsx:163 renders one <p> per message. */
const renderedMessageCount = () =>
  screen.queryAllByText(/^Portal message \d+$/).length;

const advance = async (ms: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

const renderComponent = () =>
  render(<PortalMessages clientId={CLIENT_ID} clientName={CLIENT_NAME} />);

describe("PortalMessages scroll guards", () => {
  let scrollSpy: Mock;

  beforeEach(() => {
    // Premise check: every assertion below is meaningless if the global stub
    // is not a mock. Fail loudly here instead of silently asserting nothing.
    if (!vi.isMockFunction(Element.prototype.scrollIntoView)) {
      throw new Error(
        "premise broken: Element.prototype.scrollIntoView is not a vi.fn(). " +
          "Expected the global stub at apps/mouth/src/test/setup.tsx:133.",
      );
    }
    scrollSpy = Element.prototype.scrollIntoView as unknown as Mock;

    vi.clearAllMocks();
    scrollSpy.mockClear(); // explicit: the stub is shared across test files

    vi.mocked(api.crm.getPortalMessages).mockReset();
    vi.mocked(api.crm.sendPortalMessage).mockReset();
    vi.mocked(api.crm.markPortalMessageRead).mockReset();
    vi.mocked(api.crm.markPortalMessageRead).mockResolvedValue(undefined);

    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("first load does not scroll", async () => {
    respondWith(TWO_MESSAGES);

    renderComponent();
    await advance(100);

    // Premise: messages actually arrived and rendered. Without this the test
    // would also pass on an empty load, where GUARD-0 short-circuits and
    // GUARD-A is never reached.
    expect(renderedMessageCount()).toBe(2);
    expect(api.crm.getPortalMessages).toHaveBeenCalledWith(CLIENT_ID);

    expect(scrollSpy).not.toHaveBeenCalled();
  });

  it("a poll returning the same count does not scroll", async () => {
    respondWith(TWO_MESSAGES);

    renderComponent();
    await advance(100);

    expect(renderedMessageCount()).toBe(2);
    const callsAfterFirstLoad = vi.mocked(api.crm.getPortalMessages).mock.calls
      .length;
    expect(callsAfterFirstLoad).toBeGreaterThanOrEqual(1);

    // The first load owns its own claim in test (a); this test owns the poll.
    scrollSpy.mockClear();

    await advance(POLL_INTERVAL_MS);

    // Premise: the poll really fired and the count really stayed the same.
    // "Did not scroll" proves nothing if nothing happened.
    expect(
      vi.mocked(api.crm.getPortalMessages).mock.calls.length,
    ).toBeGreaterThan(callsAfterFirstLoad);
    expect(renderedMessageCount()).toBe(2);

    expect(scrollSpy).not.toHaveBeenCalled();
  });

  it("a new incoming message scrolls", async () => {
    respondWith(TWO_MESSAGES, THREE_MESSAGES);

    renderComponent();
    await advance(100);

    expect(renderedMessageCount()).toBe(2);
    scrollSpy.mockClear();

    await advance(POLL_INTERVAL_MS);

    expect(renderedMessageCount()).toBe(3);
    expect(scrollSpy).toHaveBeenCalled();
  });

  it("sending your own message scrolls", async () => {
    respondWith(TWO_MESSAGES, THREE_MESSAGES);
    vi.mocked(api.crm.sendPortalMessage).mockResolvedValue(makeMessage(3));

    renderComponent();
    await advance(100);

    expect(renderedMessageCount()).toBe(2);
    scrollSpy.mockClear();

    // The Send button is disabled while newMessage is empty
    // (PortalMessages.tsx:206), and handleSend returns early on a blank input
    // (PortalMessages.tsx:71) — so the input has to be filled first. The real
    // chain runs from here: handleSend -> sendPortalMessage -> loadMessages.
    fireEvent.change(screen.getByPlaceholderText(`Message ${CLIENT_NAME}...`), {
      target: { value: "Reply from team" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await advance(100);

    expect(api.crm.sendPortalMessage).toHaveBeenCalledWith(
      CLIENT_ID,
      "Reply from team",
    );
    expect(renderedMessageCount()).toBe(3);
    expect(scrollSpy).toHaveBeenCalled();
  });
});
