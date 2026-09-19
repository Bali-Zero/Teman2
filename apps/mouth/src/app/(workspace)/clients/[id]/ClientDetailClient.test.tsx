import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  Client,
  ClientCompanyLink,
  ClientProfile,
} from "@/lib/api/crm/crm.types";

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
// Stubbed (not the real modal) so the Add-company click test can assert on a
// marker this module actually renders; the real modal's own suite covers it.
vi.mock("./components/modals/AddCompanyModal", () => ({
  AddCompanyModal: () => <div data-testid="AddCompanyModal" />,
}));

const makeCompanyLink = (): ClientCompanyLink => ({
  link_id: 701,
  company_id: 7001,
  company_name: "Synthetic PT Sejahtera",
  company_type: "PT PMA",
  role: "shareholder",
  is_primary: true,
  status: "active",
});

const makeProfile = (
  practiceStatus?: string,
  practicesCount = practiceStatus ? 1 : 0,
  companyLinks: ClientCompanyLink[] = [makeCompanyLink()],
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
  company_links: companyLinks,
  stats: {
    family_count: 0,
    documents_count: 0,
    practices_count: practicesCount,
    expired_count: 0,
    red_alerts: 0,
    yellow_alerts: 0,
  },
});

// R7a rework: zero company links, no company name, plus optional client-field
// overrides (a personal tax id is the finding-1 case).
const companyLessProfile = (overrides: Partial<Client> = {}): ClientProfile => {
  const profile = makeProfile(undefined, 0, []);
  return { ...profile, client: { ...profile.client, ...overrides } };
};

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

  // R7a (kita client-profile redesign): a client with ZERO company links
  // loses the Company and Tax tab buttons, and a deep link to either falls
  // back to Overview with the active state agreeing. GUILT: before R7a both
  // buttons rendered and ?tab=company opened CompanyTab. The "no button"
  // assertion dies without the tab-bar filter; the fallback +
  // aria-current-on-Overview assertions die without the render-time
  // visibleTab guard.
  it.each([
    ["company", "Company"],
    ["tax", "Tax"],
  ])(
    "hides the %s tab and falls back to Overview when the client has no company links (R7a)",
    async (tab, name) => {
      mockUseClientDetail.mockReturnValue({
        data: companyLessProfile(),
        isLoading: false,
        error: null,
      });
      stableSearchParams.get.mockImplementation((key: string) =>
        key === "tab" ? tab : null,
      );
      const { ClientDetailClient } = await import("./ClientDetailClient");
      render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
      expect(await screen.findByTestId("OverviewTab")).toBeInTheDocument();
      expect(screen.queryByTestId(`${name}Tab`)).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Overview" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      // The actions the hidden tabs carried must survive on Overview: the
      // section renders with Add company and the tax-consultant select (the
      // client has no personal tax id, so the Tax tab is hidden too and the
      // select is not duplicated anywhere). Dies without the LedgerSection
      // block or its unconditional `!showTaxTab` guard.
      expect(
        screen.getByRole("heading", { name: "Company & tax" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Add company" }),
      ).toBeInTheDocument();
      expect(screen.getByLabelText("Tax consultant")).toBeInTheDocument();
    },
  );

  // Finding 1 (R7a rework): a client with a personal tax identifier but no
  // company keeps the Tax tab — TaxTab renders `client.npwp ?? client.tax_id`
  // and `client.nib`, and no other surface does, so hiding the tab would make
  // a stored fact invisible. GUILT: without the `showTaxTab` flag the Tax
  // button never renders here; the `?tab=tax` deep link falls back to
  // Overview; and the Overview section renders a second tax-consultant select
  // beside the one in TaxTab. All values synthetic.
  it.each([
    ["npwp", "00.000.000.0-000.000"],
    ["tax_id", "SYNTHETIC-TAX-0001"],
    ["nib", "0011223344556"],
  ] as const)(
    "keeps the Tax tab for a company-less client with a personal %s (R7a rework)",
    async (field, value) => {
      mockUseClientDetail.mockReturnValue({
        data: companyLessProfile({ [field]: value }),
        isLoading: false,
        error: null,
      });
      const { ClientDetailClient } = await import("./ClientDetailClient");
      const first = render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

      // Tax visible, Company still hidden.
      expect(screen.getByRole("button", { name: "Tax" })).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Company" }),
      ).not.toBeInTheDocument();

      // Overview block: Add company yes, tax-consultant select NO — the
      // selector already lives in the now-visible Tax tab.
      expect(
        screen.getByRole("heading", { name: "Company & tax" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Add company" }),
      ).toBeInTheDocument();
      expect(screen.queryByLabelText("Tax consultant")).not.toBeInTheDocument();
      first.unmount();

      // ?tab=tax opens Tax.
      stableSearchParams.get.mockImplementation((key: string) =>
        key === "tab" ? "tax" : null,
      );
      const second = render(
        <ClientDetailClient taxConsultants={CONSULTANTS} />,
      );
      expect(await screen.findByTestId("TaxTab")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Tax" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      second.unmount();

      // ?tab=company still falls back to Overview.
      stableSearchParams.get.mockImplementation((key: string) =>
        key === "tab" ? "company" : null,
      );
      render(<ClientDetailClient taxConsultants={CONSULTANTS} />);
      expect(await screen.findByTestId("OverviewTab")).toBeInTheDocument();
      expect(screen.queryByTestId("CompanyTab")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Overview" })).toHaveAttribute(
        "aria-current",
        "page",
      );
    },
  );

  // INNOCENCE: a client WITH a company link is unchanged — both buttons
  // render and both deep links open their tab, and the company-less
  // "Company & tax" section is NOT on Overview. Dies only if the tab filter
  // starts dropping buttons for linked clients too, or if the section stops
  // respecting `showCompanyTab`.
  it("keeps Company and Tax tabs and both deep links for a client with a company link (R7a)", async () => {
    const { ClientDetailClient } = await import("./ClientDetailClient");
    const first = render(<ClientDetailClient taxConsultants={CONSULTANTS} />);
    expect(screen.getByRole("button", { name: "Company" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tax" })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Company & tax" }),
    ).not.toBeInTheDocument();
    first.unmount();

    stableSearchParams.get.mockImplementation((key: string) =>
      key === "tab" ? "company" : null,
    );
    const second = render(<ClientDetailClient taxConsultants={CONSULTANTS} />);
    expect(await screen.findByTestId("CompanyTab")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Company" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    second.unmount();

    stableSearchParams.get.mockImplementation((key: string) =>
      key === "tab" ? "tax" : null,
    );
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);
    expect(await screen.findByTestId("TaxTab")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tax" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  // LOADING: while the profile query is unresolved the page is the spinner
  // (no tab bar exists to flicker, nothing carries aria-current), and a
  // ?tab=company deep link set during that phase must NOT have been bounced
  // to Overview — once the data lands WITH links, the deep link wins.
  // Dies without the render-time guard if the fallback lives in the URL
  // effect instead: the effect runs while `profile` is still undefined and
  // would reset activeTab to overview before the data arrives.
  it("does not bounce ?tab=company while the profile is still loading (R7a)", async () => {
    mockUseClientDetail.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    stableSearchParams.get.mockImplementation((key: string) =>
      key === "tab" ? "company" : null,
    );
    const { ClientDetailClient } = await import("./ClientDetailClient");
    const { rerender, container } = render(
      <ClientDetailClient taxConsultants={CONSULTANTS} />,
    );

    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(container.querySelector('[aria-current="page"]')).toBeNull();

    // The profile arrives — WITH a company link. The deep link set during
    // the loading phase must now resolve to the Company tab.
    mockUseClientDetail.mockReturnValue({
      data: makeProfile(),
      isLoading: false,
      error: null,
    });
    rerender(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    expect(await screen.findByTestId("CompanyTab")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Company" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  // Parity: hiding the tabs must not orphan the two ACTIONS they carried
  // for a company-less client — linking the first company (AddCompanyModal)
  // and assigning the tax consultant (the control TaxTab renders). The modal
  // module is stubbed above, so the assertion is on a marker the stub really
  // renders; without the button the click query dies first.
  it("keeps add-company and tax-consultant reachable when the tabs are hidden (R7a)", async () => {
    mockUseClientDetail.mockReturnValue({
      data: companyLessProfile(),
      isLoading: false,
      error: null,
    });
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    expect(
      screen.getByRole("button", { name: "Add company" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Tax consultant")).toBeInTheDocument();
  });

  // INNOCENCE (round-1 judgement call, pinned): `company_name` set with zero
  // links keeps BOTH tabs — CompanyTab's name-search fallback surfaces real
  // data that hiding would orphan. Dies if `showCompanyTab` stops reading
  // `client.company_name`.
  it("keeps Company and Tax tabs when only company_name is set with zero links (R7a rework)", async () => {
    mockUseClientDetail.mockReturnValue({
      data: companyLessProfile({ company_name: "Synthetic PT Sejahtera" }),
      isLoading: false,
      error: null,
    });
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    expect(screen.getByRole("button", { name: "Company" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tax" })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Company & tax" }),
    ).not.toBeInTheDocument();
  });

  // GUILT: the Add company control must actually open AddCompanyModal —
  // asserted on the stub's own test id, not an id nobody sets.
  it("opens AddCompanyModal when Add company is clicked (R7a rework)", async () => {
    const user = userEvent.setup();
    mockUseClientDetail.mockReturnValue({
      data: companyLessProfile(),
      isLoading: false,
      error: null,
    });
    const { ClientDetailClient } = await import("./ClientDetailClient");
    render(<ClientDetailClient taxConsultants={CONSULTANTS} />);

    await user.click(screen.getByRole("button", { name: "Add company" }));

    expect(await screen.findByTestId("AddCompanyModal")).toBeInTheDocument();
  });
});
