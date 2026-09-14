/**
 * K3a — /clients desk grammar (SAETTA-R19K window K3).
 *
 * Mocking follows app/(workspace)/process/__tests__/page.test.tsx
 * (next/navigation, @/lib/api, @/hooks/useTeamMembers, @/components/ui/toast)
 * plus @/hooks for useCrmClients/useCrmStats and the map's dynamic import
 * target, so PrimeNexusLayout never actually loads. All fixtures are
 * synthetic — no real client name, phone or email.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Client } from "@/lib/api/crm/crm.types";
import {
  clientStatusTone,
  passportDaysLeft,
  passportTone,
  viewerIsNext,
} from "../client-row-model";
import styles from "../clients-desk.module.css";
import ClientsPage from "../page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPush = vi.fn();
const mockRouter = {
  push: mockPush,
  back: vi.fn(),
  forward: vi.fn(),
  refresh: vi.fn(),
  replace: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/clients",
}));

const VIEWER_EMAIL = "staff@example.test";
const OTHER_MEMBER = "member-a@example.test";

const mockGetUserProfile = vi.fn(() => ({ email: VIEWER_EMAIL }));
const mockUpdateClient = vi.fn().mockResolvedValue({});
const mockGetClientAssignees = vi.fn().mockResolvedValue([]);
const mockGetClients = vi.fn().mockResolvedValue([]);

vi.mock("@/lib/api", () => ({
  api: {
    getUserProfile: (...args: unknown[]) =>
      (mockGetUserProfile as (...a: unknown[]) => unknown)(...args),
    crm: {
      updateClient: (...args: unknown[]) =>
        (mockUpdateClient as (...a: unknown[]) => unknown)(...args),
      getClientAssignees: (...args: unknown[]) =>
        (mockGetClientAssignees as (...a: unknown[]) => unknown)(...args),
      getClients: (...args: unknown[]) =>
        (mockGetClients as (...a: unknown[]) => unknown)(...args),
    },
  },
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({
    options: [
      { value: VIEWER_EMAIL, label: "Staff member" },
      { value: OTHER_MEMBER, label: "member A" },
    ],
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

vi.mock("@/components/maps/prime/PrimeNexusLayout", () => ({
  default: () => <div data-testid="prime-nexus-mock" />,
}));

// jsdom has no layout engine, so @tanstack/react-virtual never sees a real
// viewport — same fix as
// src/components/crm/__tests__/ClientKanban.virtualization.test.tsx.
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: vi.fn(() => ({
    getVirtualItems: () => [],
    getTotalSize: () => 0,
  })),
}));

const mockUseCrmClients = vi.fn();
const mockUseCrmStats = vi.fn();

vi.mock("@/hooks", () => ({
  useCrmClients: (...args: unknown[]) =>
    (mockUseCrmClients as (...a: unknown[]) => unknown)(...args),
  useCrmStats: (...args: unknown[]) =>
    (mockUseCrmStats as (...a: unknown[]) => unknown)(...args),
}));

// ---------------------------------------------------------------------------
// Fixtures — synthetic only (Client 0401 …, staff@example.test, member A)
// ---------------------------------------------------------------------------

function makeClient(overrides: Partial<Client> & { id: number }): Client {
  const padded = String(overrides.id).padStart(4, "0");
  return {
    uuid: `uuid-${overrides.id}`,
    full_name: `Client ${padded}`,
    email: `client${overrides.id}@example.test`,
    status: "lead",
    client_type: "individual",
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  } as Client;
}

const soonExpiry = new Date(Date.now() + 10 * 86_400_000).toISOString();

// c0401: owned by the viewer, still moving, an expiring passport — the row
// this suite's "needs you" / optimistic-completion checks turn on.
const CLIENT_OWNED = makeClient({
  id: 401,
  status: "active",
  assigned_to: VIEWER_EMAIL,
  nationality: "ID",
  passport_expiry: soonExpiry,
  last_interaction_date: new Date().toISOString(),
});
// c0402: assigned to the viewer but terminal — DISPOSITION F15 guilt case.
const CLIENT_TERMINAL_OWNED = makeClient({
  id: 402,
  status: "completed",
  assigned_to: VIEWER_EMAIL,
});
// c0403: assigned to someone else.
const CLIENT_OTHERS = makeClient({
  id: 403,
  status: "lead",
  assigned_to: OTHER_MEMBER,
});
// c0404: unassigned.
const CLIENT_UNASSIGNED = makeClient({
  id: 404,
  status: "active",
});

const BASE_CLIENTS: Client[] = [
  CLIENT_OWNED,
  CLIENT_TERMINAL_OWNED,
  CLIENT_OTHERS,
  CLIENT_UNASSIGNED,
];

function crmClientsFrom(list: Client[]) {
  return (options: { status?: string; assigned_to?: string } = {}) => {
    let filtered = list;
    if (options.status) {
      filtered = filtered.filter((c) => c.status === options.status);
    }
    if (options.assigned_to) {
      filtered = filtered.filter((c) => c.assigned_to === options.assigned_to);
    }
    return {
      clients: filtered,
      total: filtered.length,
      isLoading: false,
      isError: false,
      error: null,
      loadMore: vi.fn(),
      hasMore: false,
      isLoadingMore: false,
    };
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ClientsPage />
    </QueryClientProvider>,
  );
}

async function switchToTableView() {
  const tableToggle = screen.getByRole("button", {
    name: "Switch to table view",
  });
  fireEvent.click(tableToggle);
  await waitFor(() => {
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
}

// `import.meta.url` is not a file URL under this runner's environment, so
// the page is located from the working directory instead — same pattern as
// src/app/(workspace)/garuda-voa/r19.test.tsx.
const CLIENTS_DIR = (() => {
  const suffix = join("src", "app", "(workspace)", "clients");
  for (const base of [process.cwd(), join(process.cwd(), "apps", "mouth")]) {
    const candidate = join(base, suffix);
    if (existsSync(candidate)) return candidate + "/";
  }
  throw new Error(
    `clients desk sources not found from ${process.cwd()} — the file-based checks cannot run`,
  );
})();

/** The module's own comments quote the declarations they explain, so a text
 *  assertion over the raw file passes even when the real rule is deleted.
 *  Every check below reads this comment-free view instead. */
function cssCode(): string {
  return readFileSync(CLIENTS_DIR + "clients-desk.module.css", "utf8").replace(
    /\/\*[\s\S]*?\*\//g,
    "",
  );
}

/** Brace-counting media-query extractor — a non-greedy regex breaks on the
 *  first nested rule's own closing brace. */
function extractMediaBlock(css: string, mediaStart: string): string {
  const startIdx = css.indexOf(mediaStart);
  if (startIdx === -1) return "";
  const braceOpen = css.indexOf("{", startIdx);
  let depth = 0;
  let i = braceOpen;
  for (; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return css.slice(braceOpen + 1, i);
}

// jsdom ships no Clipboard API, so the copy action would be a silent no-op
// and the assertion below would read `undefined.writeText`. Install a stub
// once; `vi.clearAllMocks()` resets its calls between tests.
const clipboardWriteText = vi.fn().mockResolvedValue(undefined);
Object.defineProperty(navigator, "clipboard", {
  value: { writeText: clipboardWriteText },
  configurable: true,
});

beforeEach(() => {
  vi.clearAllMocks();
  clipboardWriteText.mockResolvedValue(undefined);
  window.localStorage.clear();
  mockGetUserProfile.mockReturnValue({ email: VIEWER_EMAIL });
  mockUpdateClient.mockResolvedValue({});
  mockGetClientAssignees.mockResolvedValue([]);
  mockGetClients.mockResolvedValue([]);
  mockUseCrmClients.mockImplementation(crmClientsFrom(BASE_CLIENTS));
  mockUseCrmStats.mockReturnValue({ data: undefined, isError: false });
});

// ---------------------------------------------------------------------------
// 1. Row model
// ---------------------------------------------------------------------------

describe("row model", () => {
  const NOW = new Date("2026-09-14T00:00:00.000Z").getTime();

  it("clientStatusTone: lead→wait, active→ours, completed→ok, lost→wait, inactive→wait", () => {
    expect(clientStatusTone("lead")).toBe("wait");
    expect(clientStatusTone("active")).toBe("ours");
    expect(clientStatusTone("completed")).toBe("ok");
    expect(clientStatusTone("lost")).toBe("wait");
    expect(clientStatusTone("inactive")).toBe("wait");
  });

  it("viewerIsNext is true for an assigned lead/active and false for an assigned completed/lost/inactive (F15)", () => {
    expect(
      viewerIsNext({ assigned_to: VIEWER_EMAIL, status: "lead" }, VIEWER_EMAIL),
    ).toBe(true);
    expect(
      viewerIsNext(
        { assigned_to: VIEWER_EMAIL, status: "active" },
        VIEWER_EMAIL,
      ),
    ).toBe(true);
    expect(
      viewerIsNext(
        { assigned_to: VIEWER_EMAIL, status: "completed" },
        VIEWER_EMAIL,
      ),
    ).toBe(false);
    expect(
      viewerIsNext({ assigned_to: VIEWER_EMAIL, status: "lost" }, VIEWER_EMAIL),
    ).toBe(false);
    expect(
      viewerIsNext(
        { assigned_to: VIEWER_EMAIL, status: "inactive" },
        VIEWER_EMAIL,
      ),
    ).toBe(false);
  });

  it("viewerIsNext is false for a status this model does not recognise", () => {
    // Guilt case: the predicate used to be `!isTerminalClientStatus(status)`,
    // a DENY-list, so any status outside {completed,lost,inactive} — a typo, a
    // future pipeline stage, an empty string — painted copper and claimed the
    // viewer was next. Copper has to be proven, not assumed.
    for (const status of ["unknown", "", "archived", "on_hold", "LEAD"]) {
      expect(
        viewerIsNext(
          {
            assigned_to: VIEWER_EMAIL,
            // The point of this case is a status OUTSIDE the union, which is
            // exactly what a backend can hand a client at runtime.
            status: status as Client["status"],
          },
          VIEWER_EMAIL,
        ),
        `status "${status}" must not resolve to copper`,
      ).toBe(false);
    }
  });

  it("viewerIsNext is false when assigned_to is another member", () => {
    expect(
      viewerIsNext(
        { assigned_to: OTHER_MEMBER, status: "active" },
        VIEWER_EMAIL,
      ),
    ).toBe(false);
  });

  it("passportTone returns warning for an expired and a 30-day passport, never copper", () => {
    const expiredDays = passportDaysLeft("2026-08-01T00:00:00.000Z", NOW);
    const in30Days = passportDaysLeft(
      new Date(NOW + 30 * 86_400_000).toISOString(),
      NOW,
    );
    const toneExpired = passportTone(expiredDays);
    const tone30 = passportTone(in30Days);
    expect(toneExpired).toBe("warning");
    expect(tone30).toBe("warning");
    // A passport 6 months out is NOT urgent — the guilt case for a rule that
    // simply returned "warning" for every date it was handed.
    expect(
      passportTone(
        passportDaysLeft(new Date(NOW + 180 * 86_400_000).toISOString(), NOW),
      ),
    ).toBe("muted");
  });
});

// ---------------------------------------------------------------------------
// 2-5, 10. Rendered page behaviour
// ---------------------------------------------------------------------------

describe("/clients desk", () => {
  it("desk pill toggles the filter", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Client 0401")).toBeInTheDocument();
    });

    const allPill = screen.getByRole("button", { name: "All" });
    const activePill = screen.getByRole("button", { name: "Active" });
    expect(allPill).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(activePill);

    await waitFor(() => {
      expect(activePill).toHaveAttribute("aria-pressed", "true");
    });
    expect(allPill).toHaveAttribute("aria-pressed", "false");
    // c0401 (active) stays; c0403 (lead) narrows out.
    expect(screen.getByText("Client 0401")).toBeInTheDocument();
    expect(screen.queryByText("Client 0403")).not.toBeInTheDocument();
  });

  it("whole-row click navigates", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Client 0401"));
    await switchToTableView();

    const row = screen.getByRole("link", {
      name: /Open client Client 0401/,
    });
    fireEvent.click(row);
    expect(mockPush).toHaveBeenCalledWith("/clients/401");
  });

  it("a secondary action does NOT navigate", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Client 0401"));
    await switchToTableView();

    const copyButton = screen.getByRole("button", {
      name: "Copy Client 0401 reference",
    });
    fireEvent.click(copyButton);

    expect(mockPush).not.toHaveBeenCalled();
    expect(clipboardWriteText).toHaveBeenCalledWith("Client 401");
  });

  it("a secondary action does NOT navigate on Enter either", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Client 0401"));
    await switchToTableView();

    const copyButton = screen.getByRole("button", {
      name: "Copy Client 0401 reference",
    });
    // The row is role="link" with its own Enter/Space handler. Without the
    // `event.target !== event.currentTarget` guard on the row, this keystroke
    // bubbles up and navigates instead of copying.
    fireEvent.keyDown(copyButton, { key: "Enter" });
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("the row menu exists for a non-hover pointer", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Client 0401"));
    await switchToTableView();

    const triggers = screen.getAllByRole("button", {
      name: /^Actions for/,
    });
    expect(triggers).toHaveLength(BASE_CLIENTS.length);
    triggers.forEach((t) =>
      expect(t).toHaveAttribute("aria-expanded", "false"),
    );

    const first = triggers[0];
    fireEvent.click(first);
    expect(first).toHaveAttribute("aria-expanded", "true");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(first).toHaveAttribute("aria-expanded", "false");
    expect(first).toHaveFocus();
  });

  it("sticky head is wired to the module class and the CSS declares position: sticky", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Client 0401"));
    await switchToTableView();

    const table = screen.getByRole("table");
    expect(table.className).toContain(styles.deskTable);

    // jsdom applies no stylesheet (no layout engine) — a getComputedStyle
    // assertion here would be a no-op that always "passes". Reading the
    // source CSS is the honest check for the sticky declaration.
    const css = cssCode();
    expect(css).toContain("position: sticky");
    // The offset must CLEAR the 44px DeskStrip, which is itself sticky at the
    // header height and paints above the head (higher z-index). Guilt case:
    // `top: var(--bz-header-height, 48px)` measures as pinned — a probe reads
    // th.top === 48 and calls it a pass — while the strip covers it. A bare
    // `toContain("top: var(--bz-header-height")` passes on both, so it is the
    // calc that is asserted here.
    expect(css).toContain("top: calc(var(--bz-header-height, 48px) + 44px)");
  });

  it("the touch fallback is declared AFTER the base rule that hides it", () => {
    // Guilt case this pins: an earlier revision declared
    // `.rowMenuTrigger { display: none }` BELOW the `@media (hover: none)`
    // block that sets it to grid. Equal specificity, later source wins, so a
    // touch pointer got neither the hover actions nor the menu — the row had
    // no secondary actions at all, and nothing rendered an error.
    const css = cssCode();
    const baseHide = css.indexOf(".rowMenuTrigger {\n  display: none;");
    const hoverNone = css.indexOf("@media (hover: none) {");
    expect(baseHide).toBeGreaterThan(-1);
    expect(hoverNone).toBeGreaterThan(-1);
    expect(baseHide).toBeLessThan(hoverNone);

    const touchBlock = extractMediaBlock(css, "@media (hover: none) {");
    expect(touchBlock).toContain(".rowMenuTrigger");
    expect(touchBlock).toContain("display: grid");
    expect(touchBlock).toContain("display: none !important");

    // Second guilt case the ordering check alone misses: a NEW rule hiding the
    // trigger, added anywhere AFTER the touch block, re-breaks it silently.
    expect(
      css.slice(hoverNone).includes(".rowMenuTrigger {\n  display: none;"),
      "a later .rowMenuTrigger hide would override the touch fallback",
    ).toBe(false);
  });

  it("1360 collapse is declared, and its lower bound leaves no gap", () => {
    const css = cssCode();
    const header = "@media (max-width: 1360px) and (min-width: 700.02px) {";
    expect(css).toContain(header);
    const block = extractMediaBlock(css, header);
    expect(block).toContain("nth-child(4)");
    expect(block).toContain("nth-child(7)");
    // Without this the block could keep naming the columns and stop hiding
    // them, and the assertions above would not notice.
    expect(block).toContain("display: none");
    expect(block).toContain(".collapsedMeta");
    expect(block).toContain("display: inline");

    // Guilt case: a `min-width: 701px` lower bound leaves 700.0-701.0 matching
    // NEITHER query, so a 700.5px viewport keeps all eight columns.
    expect(css).not.toContain("(min-width: 701px)");
  });

  it("negative — the card view still virtualizes", async () => {
    const manyClients = Array.from({ length: 200 }, (_, i) =>
      makeClient({
        id: 1000 + i,
        status: "active",
        assigned_to: OTHER_MEMBER,
      }),
    );
    mockUseCrmClients.mockImplementation(crmClientsFrom(manyClients));

    renderPage();
    await waitFor(() => {
      expect(mockUseCrmClients).toHaveBeenCalled();
    });

    // useVirtualizer is mocked to return zero rows (jsdom cannot measure a
    // real viewport). A regression that bypasses virtualization above
    // VIRTUALIZATION_THRESHOLD (30) would render all 200 real ClientCards
    // here regardless of the mock, failing this assertion.
    const cards = screen.queryAllByText(/^Client \d{4}$/);
    expect(cards.length).toBeLessThan(200);

    // Innocence half: `< 200` alone also passes when the card view renders
    // nothing at all. Below the threshold the same view must render EVERY row,
    // which is what proves the count above came from virtualization and not
    // from a dead branch.
    mockUseCrmClients.mockImplementation(crmClientsFrom(BASE_CLIENTS));
    cleanup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Client 0401")).toBeInTheDocument();
    });
    expect(screen.queryAllByText(/^Client \d{4}$/).length).toBe(
      BASE_CLIENTS.length,
    );
  });

  it("no red, in every file this desk owns", () => {
    // Guilt case the narrower version missed: a `--state-danger` border added
    // to the CSS module breaks the same law and left page.tsx untouched.
    for (const file of [
      "page.tsx",
      "clients-desk.module.css",
      "client-row-model.ts",
    ]) {
      const source = readFileSync(CLIENTS_DIR + file, "utf8");
      expect(source, `${file} carries --state-danger`).not.toContain(
        "--state-danger",
      );
      expect(source, `${file} carries a red utility`).not.toMatch(
        /\b(?:bg|text|border)-red\b/,
      );
    }
  });

  it("a failed completion rolls the copper back and says so", async () => {
    mockUpdateClient.mockRejectedValue(new Error("write refused"));
    renderPage();
    await waitFor(() => screen.getByText("Client 0401"));
    await switchToTableView();

    const ownedRow = screen.getByRole("link", {
      name: /Open client Client 0401/,
    });
    expect(within(ownedRow).getByText("Needs you")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Mark Client 0401 completed" }),
    );

    // The row must come BACK: an optimistic update that does not roll back
    // leaves the desk claiming work is done that the server refused.
    await waitFor(() => {
      expect(
        screen.getByText("Could not update — the row is unchanged."),
      ).toBeInTheDocument();
    });
    expect(within(ownedRow).getByText("Needs you")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  });

  it("optimistic completion clears the copper (DISPOSITION F6)", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Client 0401"));
    await switchToTableView();

    const needsLabel = screen.getByText("Needs action");
    const kpiCell = needsLabel.closest("div");
    expect(kpiCell).not.toBeNull();
    expect(within(kpiCell as HTMLElement).getByText("01")).toBeInTheDocument();

    const ownedRow = screen.getByRole("link", {
      name: /Open client Client 0401/,
    });
    expect(within(ownedRow).getByText("Needs you")).toBeInTheDocument();

    const completeButton = screen.getByRole("button", {
      name: "Mark Client 0401 completed",
    });
    fireEvent.click(completeButton);

    await waitFor(() => {
      expect(
        within(kpiCell as HTMLElement).getByText("00"),
      ).toBeInTheDocument();
    });
    expect(within(ownedRow).queryByText("Needs you")).not.toBeInTheDocument();

    const undoButton = await screen.findByRole("button", { name: "Undo" });
    fireEvent.click(undoButton);

    await waitFor(() => {
      expect(
        within(kpiCell as HTMLElement).getByText("01"),
      ).toBeInTheDocument();
    });
    expect(within(ownedRow).getByText("Needs you")).toBeInTheDocument();
  });
});
