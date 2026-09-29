import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const motion = vi.hoisted(() => ({ reduced: false }));
vi.mock("framer-motion", async () => {
  const actual =
    await vi.importActual<typeof import("framer-motion")>("framer-motion");
  // Exit fades are framer's job; unmount at once so tests see dismissal.
  return {
    ...actual,
    useReducedMotion: () => motion.reduced,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => (
      <>{children}</>
    ),
  };
});
import {
  parseChampionGoal,
  PortalChampionCelebration,
} from "./PortalChampionCelebration";
import { ChampionPortrait } from "./ChampionPortrait";

class FakeSource extends EventTarget {
  static CLOSED = 2;
  readyState = 1;
  onerror: ((event: Event) => void) | null = null;
  static instances: FakeSource[] = [];
  close = vi.fn();
  constructor(readonly url: string) {
    super();
    FakeSource.instances.push(this);
  }
  goal(id: string, data: object) {
    this.dispatchEvent(
      new MessageEvent("goal", { lastEventId: id, data: JSON.stringify(data) }),
    );
  }
}

const goal = (changes = {}) => ({
  member: "contender",
  display_name: "Contender",
  activations: 12,
  at: new Date().toISOString(),
  ...changes,
});

function mount(identity = "staff") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  return {
    ...render(
      <QueryClientProvider client={client}>
        <PortalChampionCelebration identity={identity} />
      </QueryClientProvider>,
    ),
    invalidate,
  };
}

beforeEach(() => {
  motion.reduced = false;
  FakeSource.instances = [];
  vi.stubGlobal("EventSource", FakeSource);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("goal validation", () => {
  it("refuses old, future and malformed goals", () => {
    for (const value of [
      "broken",
      "{}",
      JSON.stringify(goal({ activations: 1.5 })),
      JSON.stringify(
        goal({ at: new Date(Date.now() - 100_000).toISOString() }),
      ),
      JSON.stringify(goal({ at: new Date(Date.now() + 60_000).toISOString() })),
    ])
      expect(parseChampionGoal(value)).toBeNull();
    expect(parseChampionGoal(JSON.stringify(goal()))?.activations).toBe(12);
  });
});

describe("workspace-wide celebrations", () => {
  it("connects only an authenticated workspace and closes on unmount", () => {
    const anonymous = mount("");
    expect(FakeSource.instances).toHaveLength(0);
    anonymous.unmount();
    const staff = mount();
    expect(FakeSource.instances[0].url).toBe(
      "/api/dashboard/portal-challenge/events",
    );
    staff.unmount();
    expect(FakeSource.instances[0].close).toHaveBeenCalledOnce();
  });

  it("delivers a goal to two screens and ignores repeated event IDs", () => {
    const first = mount("staff-one");
    const second = mount("staff-two");
    act(() => {
      for (const source of FakeSource.instances) {
        source.goal("100-0", goal());
        source.goal("100-0", goal());
      }
    });
    expect(screen.getAllByRole("status")).toHaveLength(2);
    expect(first.invalidate).toHaveBeenCalledOnce();
    expect(second.invalidate).toHaveBeenCalledOnce();
    expect(first.invalidate).toHaveBeenCalledWith({
      queryKey: ["portal-challenge", "staff-one"],
    });
  });

  it("queues goals and dismisses them without navigating", () => {
    mount();
    act(() => {
      FakeSource.instances[0].goal("100-0", goal());
      FakeSource.instances[0].goal(
        "101-0",
        goal({ member: "second", display_name: "Second" }),
      );
    });
    expect(screen.getByRole("status")).toHaveTextContent("GOAL oleh Contender");
    fireEvent.click(screen.getByRole("button", { name: "Tutup selebrasi" }));
    expect(screen.getByText("GOAL oleh Second")).toBeInTheDocument();
  });

  it("drops queued goals that aged past 90 seconds before their turn", () => {
    vi.useFakeTimers();
    mount();
    act(() => {
      FakeSource.instances[0].goal("100-0", goal());
      FakeSource.instances[0].goal(
        "101-0",
        goal({ member: "second", display_name: "Second" }),
      );
    });
    vi.setSystemTime(Date.now() + 91_000);
    fireEvent.click(screen.getByRole("button", { name: "Tutup selebrasi" }));
    expect(screen.queryByText("GOAL oleh Second")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("revalidates the standing at connect and never celebrates a stale event", () => {
    const { invalidate } = mount();
    act(() => {
      FakeSource.instances[0].dispatchEvent(new Event("ready"));
      FakeSource.instances[0].goal(
        "90-0",
        goal({ at: "2000-01-01T00:00:00Z" }),
      );
    });
    expect(invalidate).toHaveBeenCalledOnce();
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("uses initials for unsafe and broken portraits", () => {
    const { rerender } = render(
      <ChampionPortrait
        name="Sample Staff"
        src="https://external.invalid/photo.jpg"
      />,
    );
    expect(screen.getByRole("img")).toHaveTextContent("SS");
    expect(screen.getByText("SS")).toBeInTheDocument();
    rerender(
      <ChampionPortrait name="Sample Staff" src="/static/team/sample.jpg" />,
    );
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByText("SS")).toBeInTheDocument();
  });

  it("reconnects a closed transport with its cursor and cancels retries on logout", () => {
    vi.useFakeTimers();
    const { unmount } = mount();
    const source = FakeSource.instances[0];
    act(() => {
      source.dispatchEvent(
        new MessageEvent("ready", {
          lastEventId: "123-0",
          data: JSON.stringify({ server_time: new Date().toISOString() }),
        }),
      );
      source.readyState = 2;
      source.onerror?.(new Event("error"));
      vi.advanceTimersByTime(6000);
    });
    expect(FakeSource.instances[1].url).toContain("last_event_id=123-0");
    FakeSource.instances[1].readyState = 2;
    FakeSource.instances[1].onerror?.(new Event("error"));
    unmount();
    vi.advanceTimersByTime(120_000);
    expect(FakeSource.instances).toHaveLength(2);
  });

  it("closes the stream in a hidden tab and resumes from its cursor when visible", () => {
    let visibility: DocumentVisibilityState = "hidden";
    const spy = vi
      .spyOn(document, "visibilityState", "get")
      .mockImplementation(() => visibility);
    const flip = (next: DocumentVisibilityState) =>
      act(() => {
        visibility = next;
        document.dispatchEvent(new Event("visibilitychange"));
      });
    try {
      mount();
      expect(FakeSource.instances).toHaveLength(0);
      flip("visible");
      const first = FakeSource.instances[0];
      act(() => {
        first.dispatchEvent(
          new MessageEvent("ready", {
            lastEventId: "123-0",
            data: JSON.stringify({ server_time: new Date().toISOString() }),
          }),
        );
      });
      flip("hidden");
      expect(first.close).toHaveBeenCalledOnce();
      expect(FakeSource.instances).toHaveLength(1);
      flip("visible");
      expect(FakeSource.instances).toHaveLength(2);
      expect(FakeSource.instances[1].url).toBe(
        "/api/dashboard/portal-challenge/events?last_event_id=123-0",
      );
      act(() => FakeSource.instances[1].goal("124-0", goal()));
      expect(screen.getByRole("status")).toHaveTextContent(
        "GOAL oleh Contender",
      );
    } finally {
      spy.mockRestore();
    }
  });

  it("uses server time even when the laptop clock is wrong", () => {
    mount();
    const serverTime = Date.now() + 3600_000;
    act(() => {
      FakeSource.instances[0].dispatchEvent(
        new MessageEvent("ready", {
          data: JSON.stringify({
            server_time: new Date(serverTime).toISOString(),
          }),
        }),
      );
      FakeSource.instances[0].goal(
        "200-0",
        goal({ at: new Date(serverTime).toISOString() }),
      );
    });
    expect(screen.getByRole("status")).toHaveTextContent("GOAL oleh Contender");
  });
});

describe("kinds of takeover", () => {
  const send = (id: string, data: object) =>
    act(() => FakeSource.instances[0].goal(id, data));

  it("parses kinds: missing kind is a goal, unknown kinds are ignored", () => {
    expect(parseChampionGoal(JSON.stringify(goal()))?.kind).toBe("goal");
    expect(
      parseChampionGoal(JSON.stringify(goal({ kind: "bomb", points: 3 })))
        ?.kind,
    ).toBe("bomb");
    expect(
      parseChampionGoal(JSON.stringify(goal({ kind: "jackpot" }))),
    ).toBeNull();
    expect(parseChampionGoal(JSON.stringify(goal({ kind: 7 })))).toBeNull();
  });

  it("keeps penalties at zero or negative totals but still drops stale ones", () => {
    for (const activations of [0, -3])
      expect(
        parseChampionGoal(
          JSON.stringify(
            goal({
              kind: "penalty",
              points: -2,
              activations,
              reason: "unanswered_request",
            }),
          ),
        )?.activations,
      ).toBe(activations);
    expect(
      parseChampionGoal(
        JSON.stringify(
          goal({
            kind: "penalty",
            points: -1,
            activations: 0,
            at: new Date(Date.now() - 100_000).toISOString(),
          }),
        ),
      ),
    ).toBeNull();
  });

  it("keeps goals and bombs of members whose total is zero or negative", () => {
    for (const kind of ["goal", "bomb"])
      for (const activations of [0, -1])
        expect(
          parseChampionGoal(JSON.stringify(goal({ kind, activations })))
            ?.activations,
        ).toBe(activations);
  });

  it("never renders an unknown kind and does not consume its event", () => {
    mount();
    send("1-0", goal({ kind: "jackpot" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("goal takeover is intense: confetti, shake, +1 headline, 9 s", () => {
    vi.useFakeTimers();
    mount();
    send("1-0", goal());
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("data-takeover", "goal");
    expect(dialog).toHaveTextContent("GOAL");
    expect(dialog).toHaveTextContent("+1 poin");
    expect(screen.getAllByTestId("champion-confetti").length).toBeGreaterThan(
      20,
    );
    expect(screen.getByTestId("champion-shake")).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(8500));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("bomb takeover: BOM +3, no client identity, shockwave, 9 s", () => {
    vi.useFakeTimers();
    mount();
    send("1-0", goal({ kind: "bomb", points: 3, activations: 15 }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("data-takeover", "bomb");
    expect(dialog).toHaveTextContent("BOM!");
    expect(dialog).toHaveTextContent("+3 poin");
    expect(dialog).toHaveTextContent("Dokumen pertama klien untuk Contender");
    expect(screen.getByRole("status")).toHaveTextContent("BOM!");
    expect(screen.getAllByTestId("champion-shockwave").length).toBeGreaterThan(
      0,
    );
    expect(screen.queryByTestId("champion-confetti")).not.toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(8500));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it.each([
    ["unanswered_request", -2, "Permintaan klien belum dijawab > 3 jam kerja"],
    ["unreviewed_document", -1, "Dokumen belum ditinjau > 1 hari kerja"],
  ])("penalty %s: disappointment, reason line, 6 s", (reason, points, line) => {
    vi.useFakeTimers();
    mount();
    send("1-0", goal({ kind: "penalty", points, reason, activations: 0 }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("data-takeover", "penalty");
    expect(dialog).toHaveTextContent("Aduh");
    expect(dialog).toHaveTextContent(`\u2212${Math.abs(points)} poin`);
    expect(dialog).toHaveTextContent("Contender");
    expect(dialog).toHaveTextContent(line);
    expect(screen.queryByTestId("champion-confetti")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Aduh");
    act(() => void vi.advanceTimersByTime(5500));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("goal at a negative total shows the signed total", () => {
    mount();
    send("1-0", goal({ activations: -1 }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("data-takeover", "goal");
    expect(dialog).toHaveTextContent("\u22121 poin");
    expect(screen.getByRole("status")).toHaveTextContent("\u22121 poin");
  });

  it("penalty with an unknown reason never reads or shows undefined", () => {
    mount();
    send(
      "1-0",
      goal({
        kind: "penalty",
        points: -2,
        reason: "late_invoice",
        activations: 0,
      }),
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Poin dikurangi.");
    expect(dialog).not.toHaveTextContent("undefined");
    expect(screen.getByRole("status")).not.toHaveTextContent("undefined");
  });

  it("penalty dismisses with Escape and keeps a focusable close button", () => {
    mount();
    send(
      "1-0",
      goal({
        kind: "penalty",
        points: -2,
        reason: "unanswered_request",
        activations: -1,
      }),
    );
    expect(
      screen.getByRole("button", { name: "Tutup selebrasi" }),
    ).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("reduced motion: text emphasis only, no confetti/shake/shockwave", () => {
    motion.reduced = true;
    mount();
    send("1-0", goal());
    expect(screen.getByRole("dialog")).toHaveTextContent("GOAL");
    expect(screen.queryByTestId("champion-confetti")).not.toBeInTheDocument();
    expect(screen.queryByTestId("champion-shake")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tutup selebrasi" }));
    send("2-0", goal({ kind: "bomb", points: 3 }));
    expect(screen.getByRole("dialog")).toHaveTextContent("BOM!");
    expect(screen.queryByTestId("champion-shockwave")).not.toBeInTheDocument();
  });
});
