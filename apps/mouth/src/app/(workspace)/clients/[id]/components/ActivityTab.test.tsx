/** R8 — Activity tab (Timeline + WhatsApp folded into one). Synthetic
 * fixtures only, no real client / person / phone / message text. */
import type { ComponentProps } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ActivityTab } from "./ActivityTab";
import { api } from "@/lib/api";
import type { Interaction } from "@/lib/api/crm/crm.types";

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn(),
    crm: { createInteraction: vi.fn(), deleteInteraction: vi.fn() },
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

// A negative on a testid nobody sets cannot fail — this stub renders one so
// "ActivityTab never mounts AiSummaryCard" is a real, falsifiable check.
vi.mock("./AiSummaryCard", () => ({
  AiSummaryCard: () => <div data-testid="AiSummaryCard" />,
}));

const { waTimelineProps } = vi.hoisted(() => ({
  waTimelineProps: [] as Record<string, unknown>[],
}));
vi.mock("./WaTimelineTab", () => ({
  WaTimelineTab: (props: Record<string, unknown>) => {
    waTimelineProps.push(props);
    return <div data-testid="WaTimelineTab" />;
  },
}));

const EMAIL = "synthetic.team@example.test";
const CLIENT_ID = 4021;

const SHORT_NOTE: Interaction = {
  id: 1,
  client_id: CLIENT_ID,
  interaction_type: "note",
  summary: "Synthetic sponsor letter confirmed with employer.",
  team_member: "ari@example.test",
  direction: "outbound",
  interaction_date: "2026-09-19T09:20:00Z",
  created_at: "2026-09-19T09:20:00Z",
};

const LONG_WA: Interaction = {
  id: 2,
  client_id: CLIENT_ID,
  interaction_type: "whatsapp",
  summary: "Synthetic client asked about the review timeline. ".repeat(4),
  team_member: "ari@example.test",
  direction: "inbound",
  sentiment: "positive",
  interaction_date: "2026-09-19T09:14:00Z",
  created_at: "2026-09-19T09:14:00Z",
};

const formatDate = (d: string) => `date:${d}`;
const formatTime = (d: string) => `time:${d}`;

const renderTab = (
  overrides: Partial<ComponentProps<typeof ActivityTab>> = {},
) => {
  const onInteractionCreated = vi.fn();
  const onInteractionRemoved = vi.fn();
  const utils = render(
    <ActivityTab
      clientId={CLIENT_ID}
      interactions={[SHORT_NOTE, LONG_WA]}
      formatDate={formatDate}
      formatTime={formatTime}
      initialSection="timeline"
      onInteractionCreated={onInteractionCreated}
      onInteractionRemoved={onInteractionRemoved}
      {...overrides}
    />,
  );
  return { ...utils, onInteractionCreated, onInteractionRemoved };
};

const flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
};

beforeEach(() => {
  waTimelineProps.length = 0;
  vi.mocked(api.getProfile).mockResolvedValue({ email: EMAIL } as never);
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("ActivityTab — reachability of both legacy sections", () => {
  it("initialSection=timeline shows the interaction rows, not WhatsApp", () => {
    renderTab({ initialSection: "timeline" });
    expect(screen.getByText(SHORT_NOTE.summary!)).toBeInTheDocument();
    expect(screen.queryByTestId("WaTimelineTab")).not.toBeInTheDocument();
  });

  it("initialSection=whatsapp mounts the real WaTimelineTab for this client, lazily", () => {
    renderTab({ initialSection: "whatsapp" });
    expect(screen.getByTestId("WaTimelineTab")).toBeInTheDocument();
    expect(waTimelineProps[0]).toMatchObject({ clientId: CLIENT_ID });
    // GUILT: without the section toggle both would always render, or neither would.
    expect(screen.queryByText(SHORT_NOTE.summary!)).not.toBeInTheDocument();
  });

  it("clicking the WhatsApp filter pill unmounts the Timeline rows and mounts WaTimelineTab", () => {
    renderTab({ initialSection: "timeline" });
    expect(screen.queryByTestId("WaTimelineTab")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "WhatsApp" }));
    expect(screen.getByTestId("WaTimelineTab")).toBeInTheDocument();
    expect(screen.queryByText(SHORT_NOTE.summary!)).not.toBeInTheDocument();
  });

  it("old empty-timeline words survive: 'No interactions recorded yet'", () => {
    renderTab({ interactions: [] });
    expect(
      screen.getByText(/No interactions recorded yet/),
    ).toBeInTheDocument();
  });

  it("never mounts AiSummaryCard (v3 drops it) in either section", () => {
    const { rerender } = renderTab({ initialSection: "timeline" });
    expect(screen.queryByTestId("AiSummaryCard")).not.toBeInTheDocument();
    rerender(
      <ActivityTab
        clientId={CLIENT_ID}
        interactions={[SHORT_NOTE, LONG_WA]}
        formatDate={formatDate}
        formatTime={formatTime}
        initialSection="whatsapp"
        onInteractionCreated={vi.fn()}
        onInteractionRemoved={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("AiSummaryCard")).not.toBeInTheDocument();
  });
});

describe("ActivityTab — long summary expand/collapse, no control in HairlineRow actions", () => {
  it("truncates a long summary behind Show more / Show less", () => {
    renderTab();
    const toggle = screen.getByRole("button", { name: "Show more" });
    fireEvent.click(toggle);
    expect(
      screen.getByRole("button", { name: "Show less" }),
    ).toBeInTheDocument();
  });

  // The Show more/less control sits in the row's BODY cell, never in
  // HairlineRow's hover-gated `actions` slot (invisible on touch,
  // README.md ~121). An ancestor walk proves it structurally: if a future
  // change moved it into `actions=`, this fails.
  it("keeps the Show more control out of HairlineRow's actions slot", () => {
    renderTab();
    let el: HTMLElement | null = screen.getByRole("button", {
      name: "Show more",
    });
    while (el) {
      expect(el.className).not.toMatch(/group-hover\/row/);
      el = el.parentElement;
    }
  });
});

describe("ActivityTab — composer via Field", () => {
  it("labels the field 'Log an update' and shows a required hint while empty", () => {
    renderTab();
    expect(screen.getByLabelText("Log an update")).toBeInTheDocument();
    expect(screen.getByText("Required to save")).toBeInTheDocument();
  });

  it("disables Save until there is non-whitespace text, same rule as OLD (!summary.trim())", () => {
    renderTab();
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "   " },
    });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "Synthetic update" },
    });
    expect(save).toBeEnabled();
  });

  it("Enter in the field submits with type=note", async () => {
    vi.mocked(api.crm.createInteraction).mockResolvedValue({
      ...SHORT_NOTE,
      id: 99,
      summary: "Synthetic follow-up",
    });
    renderTab();
    const field = screen.getByLabelText("Log an update");
    fireEvent.change(field, { target: { value: "Synthetic follow-up" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await flush();
    expect(api.crm.createInteraction).toHaveBeenCalledWith({
      client_id: CLIENT_ID,
      interaction_type: "note",
      summary: "Synthetic follow-up",
      team_member: EMAIL,
      direction: "outbound",
    });
  });
});

describe("ActivityTab — quick-log presets post the same payload shape", () => {
  it.each([
    ["Called — no answer", "call"],
    ["Sent documents", "note"],
    ["Follow-up scheduled", "note"],
    ["Payment reminder sent", "note"],
  ])("preset %s posts interaction_type=%s", async (label, type) => {
    vi.mocked(api.crm.createInteraction).mockResolvedValue({
      ...SHORT_NOTE,
      id: 77,
      summary: label,
    });
    renderTab();
    fireEvent.click(screen.getByRole("button", { name: label }));
    await flush();
    expect(api.crm.createInteraction).toHaveBeenCalledWith({
      client_id: CLIENT_ID,
      interaction_type: type,
      summary: label,
      team_member: EMAIL,
      direction: "outbound",
    });
  });
});

describe("ActivityTab — failed save is honest (PROD defect DIAG-activity-logging-404.md)", () => {
  it("mocked rejection: shows a visible error, keeps the typed text, never shows the success Slip", async () => {
    vi.mocked(api.crm.createInteraction).mockRejectedValue(
      new Error("404 Not Found"),
    );
    const { onInteractionCreated } = renderTab();
    const field = screen.getByLabelText("Log an update");
    fireEvent.change(field, { target: { value: "Synthetic unsaved note" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();

    expect(screen.getByRole("alert")).toHaveTextContent(/Could not save/);
    expect(field).toHaveValue("Synthetic unsaved note");
    expect(screen.queryByText(/^Logged:/)).not.toBeInTheDocument();
    expect(onInteractionCreated).not.toHaveBeenCalled();
  });
});

describe("ActivityTab — Undo (real delete exists: crm_interactions.py DELETE /{interaction_id})", () => {
  it("Undo calls the real delete and removes the entry from the list", async () => {
    vi.mocked(api.crm.createInteraction).mockResolvedValue({
      ...SHORT_NOTE,
      id: 555,
      summary: "Synthetic loggable event",
    });
    vi.mocked(api.crm.deleteInteraction).mockResolvedValue({ success: true });
    const { onInteractionRemoved } = renderTab();
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "Synthetic loggable event" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();

    expect(
      screen.getByText('Logged: "Synthetic loggable event"'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await flush();

    expect(api.crm.deleteInteraction).toHaveBeenCalledWith(555, EMAIL);
    expect(onInteractionRemoved).toHaveBeenCalledWith(555);
    expect(screen.queryByText(/^Logged:/)).not.toBeInTheDocument();
  });

  it("timer boundary: Undo still present at 5999ms, gone by exactly 6000ms (vi.useFakeTimers)", async () => {
    vi.useFakeTimers();
    vi.mocked(api.crm.createInteraction).mockResolvedValue({
      ...SHORT_NOTE,
      id: 556,
      summary: "Synthetic boundary event",
    });
    vi.mocked(api.crm.deleteInteraction).mockResolvedValue({ success: true });
    renderTab();
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "Synthetic boundary event" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();
    expect(
      screen.getByText('Logged: "Synthetic boundary event"'),
    ).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5999);
    });
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(
      screen.queryByRole("button", { name: "Undo" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/^Logged:/)).not.toBeInTheDocument();
  });
});
