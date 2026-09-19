/** R8 — Activity tab (Timeline + WhatsApp folded into one). Synthetic
 * fixtures only, no real client / person / phone / message text. */
import type { ComponentProps } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ActivityTab } from "./ActivityTab";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/error-handler";
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

  // R8 audit item 2: the copy is chosen by `ApiError.statusCode`, never by
  // interpolating the raw backend `detail` — a 404 in PROD today reads
  // "Not found" and must never reach the operator verbatim.
  it.each([
    [404, /did not accept/],
    [403, /permission/],
    [401, /session expired/i],
  ])(
    "a %s rejection shows operator copy, never the backend detail",
    async (status, re) => {
      // R8 gate C5: the real `ApiError` class, not a plain `Error` with a
      // bolted-on `statusCode` — dies if the class ever renames the field.
      const err = new ApiError("Not found", status, { detail: "Not found" });
      vi.mocked(api.crm.createInteraction).mockRejectedValue(err);
      renderTab();
      const field = screen.getByLabelText("Log an update");
      fireEvent.change(field, {
        target: { value: "Synthetic unsaved note" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
      await flush();

      expect(screen.getByRole("alert")).toHaveTextContent(re);
      expect(screen.getByRole("alert")).not.toHaveTextContent("Not found");
      expect(field).toHaveValue("Synthetic unsaved note");
    },
  );
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

  // R8 audit item 1a: `POST /api/crm/interactions/` never writes
  // `created_by` (`crm_interactions.py:167-175`), so `DELETE` 403s for
  // every non-admin (`crm_utils.py::is_crm_admin`). The row must not
  // silently vanish only for a later window-focus refetch to bring it back
  // unexplained — a refused delete keeps the entry and says so.
  it("a refused DELETE keeps the entry and says so", async () => {
    vi.mocked(api.crm.createInteraction).mockResolvedValue({
      ...SHORT_NOTE,
      id: 557,
      summary: "Synthetic refused-undo event",
    });
    vi.mocked(api.crm.deleteInteraction).mockRejectedValue(
      new Error("You can only delete interactions you created"),
    );
    const { onInteractionRemoved } = renderTab();
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "Synthetic refused-undo event" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await flush();

    expect(api.crm.deleteInteraction).toHaveBeenCalledWith(557, EMAIL);
    expect(onInteractionRemoved).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/Could not undo/);
    expect(screen.getByRole("alert")).not.toHaveTextContent(
      /only delete interactions/,
    );
  });
});

describe("ActivityTab — 24px target floor (R8 audit item 3)", () => {
  // jsdom does no layout, so this pins a CLASS CONTRACT, not a measured
  // pixel height — the mock's `.preset-btn{ height:32px }` -> `h-8`, and
  // OverviewTab.tsx:141's identical inline text button -> `min-h-6`.
  it("every new control carries a >=24px height class (jsdom cannot measure; this pins the contract)", () => {
    renderTab();
    for (const name of [
      "Called — no answer",
      "Sent documents",
      "Follow-up scheduled",
      "Payment reminder sent",
    ]) {
      expect(screen.getByRole("button", { name })).toHaveClass(
        /h-8|min-h-6|min-h-11/,
      );
    }
    fireEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getByRole("button", { name: "Show less" })).toHaveClass(
      /min-h-6|min-h-11/,
    );
  });

  it("Save keeps an accessible name while submitting", async () => {
    vi.mocked(api.crm.createInteraction).mockImplementation(
      () => new Promise(() => {}), // never resolves — hold isSubmitting=true
    );
    renderTab();
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "Synthetic in-flight note" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();
    expect(screen.getByRole("button", { name: /sav/i })).toBeInTheDocument();
  });
});

describe("ActivityTab — invalidates the client query after a successful save (R8 audit item 6)", () => {
  it("calls onInteractionCreated and onSaved exactly once each on a successful save", async () => {
    vi.mocked(api.crm.createInteraction).mockResolvedValue({
      ...SHORT_NOTE,
      id: 558,
      summary: "Synthetic invalidate-on-save event",
    });
    const onSaved = vi.fn();
    const { onInteractionCreated } = renderTab({ onSaved });
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "Synthetic invalidate-on-save event" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();

    expect(onInteractionCreated).toHaveBeenCalledTimes(1);
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("does not call onSaved on a failed save", async () => {
    vi.mocked(api.crm.createInteraction).mockRejectedValue(
      new Error("404 Not Found"),
    );
    const onSaved = vi.fn();
    renderTab({ onSaved });
    fireEvent.change(screen.getByLabelText("Log an update"), {
      target: { value: "Synthetic unsaved event" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await flush();

    expect(onSaved).not.toHaveBeenCalled();
  });
});
