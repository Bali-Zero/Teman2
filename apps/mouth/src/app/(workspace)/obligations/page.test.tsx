import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/error-handler";
import type { components } from "@/lib/api/schema";
import MemberObligationsPage from "./page";

type Result = components["schemas"]["MemberObligationsOut"];
const apiMock = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: apiMock }));

const PASSPORT: Result["items"][number] = {
  kind: "passport",
  client_id: 42,
  client_name: "Passport fixture",
  practice_id: null,
  practice_type_name: null,
  status: "expiring",
  created_at: null,
  age_days: null,
  passport_expiry: "2026-11-16",
  days_left: 30,
  assigned_to: "member-a@example.test",
  can_open_process: false,
};
const PROCESS: Result["items"][number] = {
  kind: "process",
  client_id: 43,
  client_name: "Process fixture",
  practice_id: 101,
  practice_type_name: "Fixture service",
  status: "on_process",
  created_at: "2026-10-01T00:00:00Z",
  age_days: 16,
  passport_expiry: null,
  days_left: null,
  assigned_to: "member-a@example.test",
  can_open_process: true,
};
const OWNERS = [{ email: "member-a@example.test", name: "Member A", total: 2 }];
const PERSONAL: Result = {
  scope: "mine",
  can_view_team: false,
  can_view_register: false,
  total: 2,
  passport_count: 1,
  process_count: 1,
  limit: 50,
  offset: 0,
  owners: OWNERS,
  items: [PASSPORT, PROCESS],
};
const EMPTY: Result = {
  ...PERSONAL,
  total: 0,
  passport_count: 0,
  process_count: 0,
  owners: [],
  items: [],
};

beforeEach(() => {
  apiMock.get.mockReset();
  apiMock.get.mockResolvedValue(PERSONAL);
});

describe("Member obligations", () => {
  it("shows personal duties with links to the existing source records", async () => {
    render(<MemberObligationsPage />);
    expect(await screen.findByText("Passport fixture")).toBeVisible();
    expect(apiMock.get).toHaveBeenCalledWith(
      "/api/crm/member-obligations?scope=mine&limit=50&offset=0",
    );
    expect(screen.getByRole("link", { name: "Open client" })).toHaveAttribute(
      "href",
      "/clients/42?tab=overview",
    );
    expect(screen.getByRole("link", { name: "Open process" })).toHaveAttribute(
      "href",
      "/process/101",
    );
    expect(screen.getByLabelText("To review: 2")).toBeVisible();
    expect(screen.getByLabelText("Passports: 1")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Team overview" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Compliance register" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /complete|done|record/i }),
    ).not.toBeInTheDocument();
  });

  it("does not get stuck loading when the selected scope is clicked again", async () => {
    render(<MemberObligationsPage />);
    await screen.findByText("Passport fixture");
    fireEvent.click(screen.getByRole("button", { name: "My obligations" }));
    expect(screen.queryByText("Loading obligations…")).not.toBeInTheDocument();
    expect(apiMock.get).toHaveBeenCalledTimes(1);
  });

  it("clears duties on refresh after the original records change", async () => {
    render(<MemberObligationsPage />);
    await screen.findByText("Passport fixture");
    apiMock.get.mockResolvedValue(EMPTY);
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(
      await screen.findByText("No obligations need your attention."),
    ).toBeVisible();
    expect(screen.queryByText("Passport fixture")).not.toBeInTheDocument();
    expect(screen.getByLabelText("To review: 0")).toBeVisible();
  });

  it("rechecks source records when returning to the page", async () => {
    render(<MemberObligationsPage />);
    await screen.findByText("Passport fixture");
    apiMock.get.mockResolvedValue(EMPTY);
    fireEvent(window, new Event("focus"));
    expect(
      await screen.findByText("No obligations need your attention."),
    ).toBeVisible();
  });

  it("gives supervisors a team filter and honors the server's source-link flag", async () => {
    const team: Result = {
      ...PERSONAL,
      scope: "team",
      can_view_team: true,
      items: [{ ...PROCESS, can_open_process: false }],
      total: 1,
      passport_count: 0,
    };
    apiMock.get.mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("scope=team") ? team : { ...EMPTY, can_view_team: true },
      ),
    );
    render(<MemberObligationsPage />);
    await screen.findByRole("button", { name: "Team overview" });
    fireEvent.click(screen.getByRole("button", { name: "Team overview" }));
    expect(await screen.findByText("Process fixture")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Open process" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Review with the responsible team member"),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Compliance register" }),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Team member" }), {
      target: { value: "member-a@example.test" },
    });
    await waitFor(() =>
      expect(apiMock.get).toHaveBeenLastCalledWith(
        "/api/crm/member-obligations?scope=team&limit=50&offset=0&assigned_to=member-a%40example.test",
      ),
    );
  });

  it("keeps the statutory register link separate and restricted", async () => {
    apiMock.get.mockResolvedValue({
      ...PERSONAL,
      can_view_team: true,
      can_view_register: true,
    });
    render(<MemberObligationsPage />);
    expect(
      await screen.findByRole("link", { name: "Compliance register" }),
    ).toHaveAttribute("href", "/obligations/register");
  });

  it("does not replace a team response with a late personal response", async () => {
    let finishPersonal: (value: Result) => void = () => {};
    apiMock.get.mockResolvedValueOnce({ ...PERSONAL, can_view_team: true });
    render(<MemberObligationsPage />);
    await screen.findByText("Passport fixture");
    apiMock.get.mockImplementation((url: string) =>
      url.includes("scope=team")
        ? Promise.resolve({
            ...PERSONAL,
            scope: "team",
            can_view_team: true,
            items: [{ ...PROCESS, client_name: "Team-only fixture" }],
          })
        : new Promise<Result>((resolve) => {
            finishPersonal = resolve;
          }),
    );
    fireEvent(window, new Event("focus"));
    fireEvent.click(screen.getByRole("button", { name: "Team overview" }));
    await screen.findByText("Team-only fixture");
    await act(async () => {
      finishPersonal({ ...PERSONAL, can_view_team: true });
    });
    expect(screen.getByText("Team-only fixture")).toBeVisible();
    expect(screen.queryByText("Passport fixture")).not.toBeInTheDocument();
  });

  it("preserves an owner filter when their last duty disappears", async () => {
    const team: Result = { ...PERSONAL, scope: "team", can_view_team: true };
    apiMock.get.mockResolvedValue(team);
    render(<MemberObligationsPage />);
    await screen.findByRole("button", { name: "Team overview" });
    fireEvent.click(screen.getByRole("button", { name: "Team overview" }));
    await screen.findByRole("combobox", { name: "Team member" });
    apiMock.get.mockResolvedValue({
      ...EMPTY,
      scope: "team",
      can_view_team: true,
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Team member" }), {
      target: { value: "member-a@example.test" },
    });
    await screen.findByText(
      "No obligations need attention for this selection.",
    );
    expect(screen.getByRole("combobox", { name: "Team member" })).toHaveValue(
      "member-a@example.test",
    );
  });

  it("paginates using the server total and recovers when a page empties", async () => {
    apiMock.get.mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("offset=50")
          ? {
              ...PERSONAL,
              total: 51,
              items: [{ ...PROCESS, client_name: "Second-page fixture" }],
              offset: 50,
            }
          : { ...PERSONAL, total: 51 },
      ),
    );
    render(<MemberObligationsPage />);
    await screen.findByText("Passport fixture");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Second-page fixture");
    // The refreshed last page is now beyond the total; the empty-page response
    // causes a new read from offset zero.
    apiMock.get.mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("offset=50") ? { ...PERSONAL, items: [] } : PERSONAL,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() =>
      expect(apiMock.get).toHaveBeenLastCalledWith(
        "/api/crm/member-obligations?scope=mine&limit=50&offset=0",
      ),
    );
  });

  it("shows a denied overview without leaking response details", async () => {
    apiMock.get.mockRejectedValue(
      new ApiError("Forbidden", 403, { detail: "sensitive fixture detail" }),
    );
    render(<MemberObligationsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You do not have access to this overview.",
    );
    expect(
      screen.queryByText("sensitive fixture detail"),
    ).not.toBeInTheDocument();
  });
});
