/**
 * K3b — /clients/[id] desk grammar (SAETTA-R19K window K3).
 *
 * Mocking follows `../ClientDetailClient.test.tsx` (same component, the
 * pre-existing file already has the full mock surface for every child tab
 * and modal) — this file adds the masthead/status/DOM-order/stamp/copper
 * checks the K3b spec asks for, without re-deriving anything K3a already
 * settled: `clientStatusTone` and `viewerIsNext` are imported from the row
 * model, not recomputed here.
 *
 * Fixtures are synthetic only — `Client 0412`, `client412@example.test`,
 * `staff@example.test`, `member-a@example.test` — never a real name, phone,
 * passport number or email (K3b spec §1).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientProfile } from "@/lib/api/crm/crm.types";
import { clientStatusTone, viewerIsNext } from "../../client-row-model";

const {
  mockUpdateClient,
  mockSetClientCache,
  mockInvalidateClient,
  mockUseClientDetail,
  mockGetUserProfile,
  stableTimeline,
  stableSearchParams,
} = vi.hoisted(() => ({
  mockUpdateClient: vi.fn(),
  mockSetClientCache: vi.fn(),
  mockInvalidateClient: vi.fn(),
  mockUseClientDetail: vi.fn(),
  mockGetUserProfile: vi.fn(),
  stableTimeline: [],
  stableSearchParams: { get: vi.fn(() => null) },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "412" }),
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
      email: "staff@example.test",
    }),
    getUserProfile: (...args: unknown[]) =>
      (mockGetUserProfile as (...a: unknown[]) => unknown)(...args),
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

vi.mock("../components/OverviewTab", () => ({
  OverviewTab: () => <div data-testid="OverviewTab" />,
}));
vi.mock("../components/DocumentsTab", () => ({
  DocumentsTab: () => <div data-testid="DocumentsTab" />,
}));
vi.mock("../components/ProcessTab", () => ({
  ProcessTab: () => <div data-testid="ProcessTab" />,
}));
vi.mock("../components/FamilyTab", () => ({
  FamilyTab: () => <div data-testid="FamilyTab" />,
}));
vi.mock("../components/ImmigrationTab", () => ({
  ImmigrationTab: () => <div data-testid="ImmigrationTab" />,
}));
vi.mock("../components/CompanyTab", () => ({
  CompanyTab: () => <div data-testid="CompanyTab" />,
}));
vi.mock("../components/TaxTab", () => ({
  TaxTab: () => <div data-testid="TaxTab" />,
}));
vi.mock("../components/TimelineTab", () => ({
  TimelineTab: () => <div data-testid="TimelineTab" />,
}));
vi.mock("../components/WaTimelineTab", () => ({
  WaTimelineTab: () => <div data-testid="WaTimelineTab" />,
}));
vi.mock("../components/PortalMessages", () => ({
  PortalMessages: () => <div data-testid="PortalMessages" />,
}));
vi.mock("../components/BusinessStoryPanel", () => ({
  BusinessStoryPanel: () => <div data-testid="BusinessStoryPanel" />,
}));
vi.mock("../components/modals/EditClientModal", () => ({
  EditClientModal: () => null,
}));
vi.mock("../components/modals/AddFamilyMemberModal", () => ({
  AddFamilyMemberModal: () => null,
}));
vi.mock("../components/modals/EditFamilyMemberModal", () => ({
  EditFamilyMemberModal: () => null,
}));
vi.mock("../components/modals/AddDocumentModal", () => ({
  AddDocumentModal: () => null,
}));
vi.mock("../components/modals/EditDocumentModal", () => ({
  EditDocumentModal: () => null,
}));

// ---------------------------------------------------------------------------
// Fixtures — synthetic only
// ---------------------------------------------------------------------------

const VIEWER_EMAIL = "staff@example.test";
const OTHER_MEMBER = "member-a@example.test";

function makeProfile(
  overrides: {
    status?: "lead" | "active" | "completed" | "lost" | "inactive";
    assignedTo?: string;
    activePracticesCount?: number;
    companyName?: string;
  } = {},
): ClientProfile {
  const {
    status = "active",
    assignedTo,
    activePracticesCount = 0,
    companyName,
  } = overrides;
  return {
    client: {
      id: 412,
      uuid: "uuid-412",
      full_name: "Client 0412",
      email: "client412@example.test",
      status,
      client_type: "individual",
      assigned_to: assignedTo,
      company_name: companyName,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    family_members: [],
    documents: [],
    expiry_alerts: [],
    practices: Array.from({ length: activePracticesCount }, (_, i) => ({
      id: 9000 + i,
      status: "on_process",
      practice_type_code: "SYNTHETIC",
      practice_type_name: "Synthetic Process",
    })),
    company_links: [],
    stats: {
      family_count: 0,
      documents_count: 0,
      practices_count: activePracticesCount,
      expired_count: 0,
      red_alerts: 0,
      yellow_alerts: 0,
    },
  };
}

function renderClient(profile: ClientProfile) {
  mockUseClientDetail.mockReturnValue({
    data: profile,
    isLoading: false,
    error: null,
  });
  return import("../ClientDetailClient").then(({ ClientDetailClient }) =>
    render(<ClientDetailClient taxConsultants={[]} />),
  );
}

// The file-based checks are located from the working directory, same
// pattern as `clients/__tests__/clients-desk.test.tsx` and
// `garuda-voa/r19.test.tsx` (`import.meta.url` is not a file URL here).
const DETAIL_DIR = join(
  process.cwd(),
  "src",
  "app",
  "(workspace)",
  "clients",
  "[id]",
);

beforeEach(() => {
  vi.clearAllMocks();
  mockGetUserProfile.mockReturnValue({ email: VIEWER_EMAIL });
  mockInvalidateClient.mockResolvedValue(undefined);
  mockUpdateClient.mockResolvedValue({});
});

// ---------------------------------------------------------------------------
// 1. Masthead — reference eyebrow, computed subtitle
// ---------------------------------------------------------------------------

describe("masthead", () => {
  it("renders the zero-padded reference eyebrow from client.id", async () => {
    await renderClient(makeProfile());
    expect(screen.getByText("CLIENT · #0412")).toBeInTheDocument();
  });

  it("appends the company name to the eyebrow only when the field is set", async () => {
    await renderClient(makeProfile({ companyName: "PT Contoh Abadi" }));
    expect(
      screen.getByText("CLIENT · #0412 · PT Contoh Abadi"),
    ).toBeInTheDocument();
  });

  it("GUILT: a fixture with no active practices renders NO subtitle sentence", async () => {
    // A regex on the expected WORDING (e.g. /processes are moving/) would
    // pass even if the subtitle were mutated to some OTHER always-on
    // string — this caught exactly that when mutation-tested. The
    // structural check below does not: Masthead renders `sentence ? <p>…
    // : null` as the title's very next sibling, so "no subtitle" is "the
    // <h1> has no next element" regardless of what text a bug might put
    // there instead.
    await renderClient(makeProfile({ activePracticesCount: 0 }));
    const heading = screen.getByRole("heading", {
      level: 1,
      name: "Client 0412",
    });
    expect(heading.nextElementSibling).toBeNull();
  });

  it("INNOCENCE: active practices produce a sentence, singular and plural both", async () => {
    await renderClient(makeProfile({ activePracticesCount: 1 }));
    expect(screen.getByText(/^1 process is moving\.$/)).toBeInTheDocument();
    cleanup();

    await renderClient(makeProfile({ activePracticesCount: 3 }));
    expect(screen.getByText(/^3 processes are moving\.$/)).toBeInTheDocument();
  });

  it("adds the ownership clause only when the viewer is next, never a count it cannot prove", async () => {
    await renderClient(
      makeProfile({
        activePracticesCount: 3,
        assignedTo: VIEWER_EMAIL,
        status: "active",
      }),
    );
    await waitFor(() => {
      expect(
        screen.getByText(
          "3 processes are moving; this record needs your action.",
        ),
      ).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// 2. Status → tone, everywhere
// ---------------------------------------------------------------------------

describe("status tone", () => {
  it("lost and inactive are NOT the same tone as completed", () => {
    expect(clientStatusTone("lost")).not.toBe(clientStatusTone("completed"));
    expect(clientStatusTone("inactive")).not.toBe(
      clientStatusTone("completed"),
    );
    expect(clientStatusTone("lost")).toBe(clientStatusTone("inactive"));
  });

  it("the status trigger's colour is wired from clientStatusTone, not a second map", async () => {
    await renderClient(makeProfile({ status: "completed" }));
    const completedTrigger = screen.getByRole("button", {
      name: "Change client status",
    });
    expect(completedTrigger.className).toContain("state-success");
    cleanup();

    await renderClient(makeProfile({ status: "lost" }));
    const lostTrigger = screen.getByRole("button", {
      name: "Change client status",
    });
    expect(lostTrigger.className).toContain("tx-secondary");
    expect(lostTrigger.className).not.toContain("state-success");
  });

  it("every status option in the menu is a real StatePill (aria-pressed button), one per status", async () => {
    const user = userEvent.setup();
    await renderClient(makeProfile({ status: "active" }));

    await user.click(
      screen.getByRole("button", { name: "Change client status" }),
    );

    const options = ["lead", "active", "completed", "lost", "inactive"].map(
      (s) => screen.getByRole("button", { name: s }),
    );
    expect(options).toHaveLength(5);
    options.forEach((opt) => expect(opt).toHaveAttribute("aria-pressed"));
    expect(screen.getByRole("button", { name: "active" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "lost" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});

// ---------------------------------------------------------------------------
// 3. No red, in every file this window touched
// ---------------------------------------------------------------------------

describe("no red", () => {
  it("carries no --state-danger, no --bz-neon-purple, no red utility, in any file this PR touched", () => {
    for (const file of [
      "ClientDetailClient.tsx",
      "client-detail-desk.module.css",
      join("components", "OverviewTab.tsx"),
      join("components", "PassportCard.tsx"),
      join("components", "VisaCard.tsx"),
      join("components", "ProcessTab.tsx"),
      join("components", "DocumentsTab.tsx"),
      join("components", "constants.ts"),
      join("components", "utils.ts"),
    ]) {
      const source = readFileSync(join(DETAIL_DIR, file), "utf8");
      expect(source, `${file} carries --state-danger`).not.toContain(
        "--state-danger",
      );
      expect(source, `${file} carries --bz-neon-purple`).not.toContain(
        "--bz-neon-purple",
      );
      expect(source, `${file} carries a red utility`).not.toMatch(
        /\b(?:bg|text|border)-red-\d/,
      );
    }
  });
});

// ---------------------------------------------------------------------------
// 4. "Where it stands" is first in the DOM
// ---------------------------------------------------------------------------

describe("DOM order", () => {
  it("the status column precedes the tab bar in document order", async () => {
    await renderClient(makeProfile({ activePracticesCount: 1 }));
    const statusColumn = screen.getByTestId("status-column");
    const tabBar = screen.getByTestId("tab-bar");
    // DOCUMENT_POSITION_FOLLOWING (4): tabBar comes AFTER statusColumn.
    // jsdom applies no layout/CSS, so this is honestly a DOM-order check —
    // the visual "moved right on desktop" is the CSS module's `order`,
    // proven by inspection, not by a jsdom assertion that would always pass.
    expect(
      statusColumn.compareDocumentPosition(tabBar) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 5. Stamp binds to a timestamp, and to nothing else
// ---------------------------------------------------------------------------

describe("stamp", () => {
  it("Client has no review timestamp field, so no forest 'Reviewed' stamp ever renders", async () => {
    await renderClient(
      makeProfile({ status: "active", assignedTo: VIEWER_EMAIL }),
    );
    expect(screen.queryByText(/Reviewed/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 6. Copper — derived ownership only
// ---------------------------------------------------------------------------

describe("copper ownership", () => {
  it("a client assigned to the viewer and non-terminal shows the copper mark", async () => {
    const owned = makeProfile({ status: "active", assignedTo: VIEWER_EMAIL });
    expect(viewerIsNext(owned.client, VIEWER_EMAIL)).toBe(true);

    await renderClient(owned);
    await waitFor(() => {
      expect(screen.getByText("Needs you")).toBeInTheDocument();
    });
  });

  it("the SAME client completed does not (DISPOSITION F15)", async () => {
    const terminal = makeProfile({
      status: "completed",
      assignedTo: VIEWER_EMAIL,
    });
    expect(viewerIsNext(terminal.client, VIEWER_EMAIL)).toBe(false);

    await renderClient(terminal);
    await waitFor(() => {
      expect(mockGetUserProfile).toHaveBeenCalled();
    });
    expect(screen.queryByText("Needs you")).not.toBeInTheDocument();
  });

  it("a client assigned to someone else never shows the viewer's copper mark", async () => {
    await renderClient(
      makeProfile({ status: "active", assignedTo: OTHER_MEMBER }),
    );
    await waitFor(() => {
      expect(mockGetUserProfile).toHaveBeenCalled();
    });
    expect(screen.queryByText("Needs you")).not.toBeInTheDocument();
  });
});
