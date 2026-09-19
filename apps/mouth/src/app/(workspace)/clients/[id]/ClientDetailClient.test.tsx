import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientProfile } from "@/lib/api/crm/crm.types";

const {
  mockUpdateClient,
  mockSetClientCache,
  mockInvalidateClient,
  mockUseClientDetail,
  stableTimeline,
  stableSearchParams,
  taxTabProps,
} = vi.hoisted(() => ({
  taxTabProps: [] as Record<string, unknown>[],
  mockUpdateClient: vi.fn(),
  mockSetClientCache: vi.fn(),
  mockInvalidateClient: vi.fn(),
  mockUseClientDetail: vi.fn(),
  stableTimeline: [],
  stableSearchParams: {
    get: vi.fn((_key: string): string | null => null),
  },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "7" }),
  useRouter: () => ({
    back: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
  }),
  useSearchParams: () => stableSearchParams,
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn().mockResolvedValue({
      email: "synthetic.team@example.test",
    }),
    // K3b added a synchronous read for the ownership predicate (copper
    // stamp, masthead subtitle) — same shape as `getUserProfile` everywhere
    // else in kita. This mock did not carry it before; a component that now
    // calls it would throw "api.getUserProfile is not a function" on every
    // test in this file, which is why it is added here rather than guarded
    // with optional chaining in the component itself.
    getUserProfile: vi.fn(() => ({ email: "synthetic.team@example.test" })),
    crm: {
      updateClient: mockUpdateClient,
      createInteraction: vi.fn(),
    },
  },
}));

vi.mock("@/hooks/useClientDetail", () => ({
  useClientDetail: mockUseClientDetail,
  useClientTimeline: () => ({ data: stableTimeline }),
  useDocumentCategories: () => ({ data: [] }),
  useClientBusinessStory: () => ({
    data: [],
    error: null,
    isLoading: false,
  }),
  useInvalidateClient: () => mockInvalidateClient,
  useSetClientCache: () => mockSetClientCache,
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({ options: [] }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("./components/OverviewTab", () => ({
  OverviewTab: () => <div data-testid="OverviewTab" />,
}));
vi.mock("./components/DocumentsTab", () => ({
  DocumentsTab: () => <div data-testid="DocumentsTab" />,
}));
vi.mock("./components/ProcessTab", () => ({
  ProcessTab: () => <div data-testid="ProcessTab" />,
}));
vi.mock("./components/FamilyTab", () => ({
  FamilyTab: () => <div data-testid="FamilyTab" />,
}));
vi.mock("./components/ImmigrationTab", () => ({
  ImmigrationTab: () => <div data-testid="ImmigrationTab" />,
}));
vi.mock("./components/CompanyTab", () => ({
  CompanyTab: () => <div data-testid="CompanyTab" />,
}));
// Records its props instead of discarding them. A stub that renders and forgets
// cannot tell "the right list was forwarded" from "some same-shaped list was".
vi.mock("./components/TaxTab", () => ({
  TaxTab: (props: Record<string, unknown>) => {
    taxTabProps.push(props);
    return <div data-testid="TaxTab" />;
  },
}));
vi.mock("./components/TimelineTab", () => ({
  TimelineTab: () => <div data-testid="TimelineTab" />,
}));
vi.mock("./components/WaTimelineTab", () => ({
  WaTimelineTab: () => <div data-testid="WaTimelineTab" />,
}));
vi.mock("./components/PortalMessages", () => ({
  PortalMessages: () => <div data-testid="PortalMessages" />,
}));
vi.mock("./components/BusinessStoryPanel", () => ({
  BusinessStoryPanel: () => <div data-testid="BusinessStoryPanel" />,
}));
vi.mock("./components/modals/EditClientModal", () => ({
  EditClientModal: () => null,
}));
vi.mock("./components/modals/AddFamilyMemberModal", () => ({
  AddFamilyMemberModal: () => null,
}));
vi.mock("./components/modals/EditFamilyMemberModal", () => ({
  EditFamilyMemberModal: () => null,
}));
vi.mock("./components/modals/AddDocumentModal", () => ({
  AddDocumentModal: () => null,
}));
vi.mock("./components/modals/EditDocumentModal", () => ({
  EditDocumentModal: () => null,
}));

const makeProfile = (
  practiceStatus?: string,
  practicesCount = practiceStatus ? 1 : 0,
): ClientProfile => ({
  client: {
    id: 7,
    uuid: "synthetic-client-7",
    full_name: "Synthetic Status Client",
    email: "synthetic.status@example.test",
    status: "active",
    client_type: "individual",
    created_at: "2026-07-27T00:00:00Z",
    updated_at: "2026-07-27T00:00:00Z",
  },
  family_members: [],
  documents: [],
  expiry_alerts: [],
  practices: practiceStatus
    ? [
        {
          id: 71,
          status: practiceStatus,
          practice_type_code: "SYNTHETIC",
          practice_type_name: "Synthetic Process",
        },
      ]
    : [],
  company_links: [],
  stats: {
    family_count: 0,
    documents_count: 0,
    practices_count: practicesCount,
    expired_count: 0,
    red_alerts: 0,
    yellow_alerts: 0,
  },
});

/**
 * Synthetic, and deliberately not the real table.
 *
 * The component takes the tax team as a prop precisely so the values are not
 * baked into the client bundle; a fixture that copied the production addresses
 * back into a "use client" test would not fail anything, but it would reintroduce
 * the habit this change exists to break.
 */
const CONSULTANTS = [
  { value: "consultant.one@example.test", label: "Consultant One" },
  { value: "consultant.two@example.test", label: "Consultant Two" },
];

describe("ClientDetailClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // clearAllMocks keeps implementations: without this a deep-link test would
    // leak its ?tab= into every test that runs after it.
    stableSearchParams.get.mockImplementation(() => null);
    taxTabProps.length = 0;
    mockUseClientDetail.mockReturnValue({
      data: makeProfile(),
      isLoading: false,
      error: null,
    });
    mockInvalidateClient.mockResolvedValue(undefined);
    mockUpdateClient.mockResolvedValue({
      ...makeProfile().client,
      status: "inactive",
    });
  });

  it("selects a status with the mouse and patches the authoritative client", async () => {
    const user = userEvent.setup();
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    await user.click(
      screen.getByRole("button", { name: "Change client status" }),
    );
    await user.click(screen.getByRole("button", { name: "inactive" }));

    await waitFor(() => {
      expect(mockUpdateClient).toHaveBeenCalledWith(
        7,
        { status: "inactive" },
        "synthetic.team@example.test",
      );
    });
    expect(mockSetClientCache).toHaveBeenCalledWith(
      expect.objectContaining({ id: 7, status: "inactive" }),
    );
  });

  it("counts only processes visible in the active and completed lists", async () => {
    mockUseClientDetail.mockReturnValue({
      data: makeProfile("cancelled", 1),
      isLoading: false,
      error: null,
    });
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    expect(
      screen.getByRole("button", { name: "Practices (0)" }),
    ).toBeInTheDocument();
  });

  // R5 (kita client-profile redesign): the tab bar becomes a `<nav>` with its
  // own accessible name, matching v3 mock's `aria-label="Client sections"`.
  // GUILT: before R5 this was a bare `<div>` with no navigation landmark at
  // all, so this query found nothing.
  it("wraps the tab bar in a nav landmark named 'Client sections' (R5)", async () => {
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    expect(
      screen.getByRole("navigation", { name: "Client sections" }),
    ).toBeInTheDocument();
  });

  // R5: aria-current="page" tracks whichever tab is active and only that
  // one — mirrors the mock's `.tab[aria-current="page"]` rule. GUILT: before
  // R5 no tab button carried aria-current at all. INNOCENCE: clicking a
  // different tab moves the attribute rather than leaving it on both.
  it("moves aria-current to the tab the viewer picks, and only that one (R5)", async () => {
    const user = userEvent.setup();
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    const overviewTab = screen.getByRole("button", { name: "Overview" });
    const documentsTab = screen.getByRole("button", { name: /^Documents/ });
    expect(overviewTab).toHaveAttribute("aria-current", "page");
    expect(documentsTab).not.toHaveAttribute("aria-current");

    await user.click(documentsTab);

    expect(documentsTab).toHaveAttribute("aria-current", "page");
    expect(overviewTab).not.toHaveAttribute("aria-current");
  });

  /**
   * Both refuter seats reached this independently, and they were right.
   *
   * Deleting `taxConsultants={taxConsultants}` at the TaxTab call site is caught
   * by the type checker, because the prop is required. SUBSTITUTING it is not:
   * this component already calls `useTeamMemberOptions()`, which yields the same
   * `{value, label}` shape, so `taxConsultants={teamMemberOptions}` would
   * typecheck, pass every other test, and pass the chunk guard — while feeding
   * the dropdown a client-fetched roster that disagrees with the values backend
   * migration 093 accepts. Identity of the forwarded array is the assertion.
   */
  it("forwards the server-supplied consultants to TaxTab, not some other same-shaped list", async () => {
    const user = userEvent.setup();
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    await user.click(screen.getByRole("button", { name: "Tax" }));

    await waitFor(() => expect(taxTabProps.length).toBeGreaterThan(0));
    expect(taxTabProps[taxTabProps.length - 1].taxConsultants).toEqual(
      CONSULTANTS,
    );
  });

  // handleTabChange writes `?tab=<key>` for EVERY tab, so every key the page
  // can write must be a key the page can read back — a reload or a shared link
  // otherwise lands on Overview. The table is the whole TabType union.
  it.each([
    ["overview", "OverviewTab"],
    ["documents", "DocumentsTab"],
    ["process", "ProcessTab"],
    ["family", "FamilyTab"],
    ["visas", "ImmigrationTab"],
    ["company", "CompanyTab"],
    ["tax", "TaxTab"],
    ["timeline", "TimelineTab"],
    ["whatsapp", "WaTimelineTab"],
  ])("opens the %s tab from the ?tab= deep link", async (tab, testId) => {
    stableSearchParams.get.mockImplementation((key: string) =>
      key === "tab" ? tab : null,
    );
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    expect(await screen.findByTestId(testId)).toBeInTheDocument();
  });

  it("ignores a ?tab= value that is not a tab and stays on Overview", async () => {
    stableSearchParams.get.mockImplementation((key: string) =>
      key === "tab" ? "constructor" : null,
    );
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    expect(await screen.findByTestId("OverviewTab")).toBeInTheDocument();
    expect(screen.queryByTestId("WaTimelineTab")).not.toBeInTheDocument();
  });
});
