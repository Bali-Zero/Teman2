import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
  FakeSource.instances = [];
  vi.stubGlobal("EventSource", FakeSource);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("goal validation", () => {
  it("refuses old, future, malformed and non-positive points", () => {
    for (const value of [
      "broken",
      "{}",
      JSON.stringify(goal({ activations: 0 })),
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
