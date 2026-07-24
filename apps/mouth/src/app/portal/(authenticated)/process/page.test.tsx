import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ClientRequiredDocument } from "@/lib/types/required-documents";

const { mockGetProfile, mockGetMyRequiredDocuments, mockUploadClientDocument } =
  vi.hoisted(() => ({
    mockGetProfile: vi.fn(),
    mockGetMyRequiredDocuments: vi.fn(),
    mockUploadClientDocument: vi.fn(),
  }));

vi.mock("next/dynamic", () => ({
  default: (
    loader: () => Promise<{
      default: React.ComponentType<Record<string, unknown>>;
    }>,
  ) => {
    const Component = (props: Record<string, unknown>) => {
      const [Resolved, setResolved] = React.useState<React.ComponentType<
        Record<string, unknown>
      > | null>(null);
      React.useEffect(() => {
        loader().then((mod) => setResolved(() => mod.default));
      }, []);
      if (!Resolved) return null;
      return <Resolved {...props} />;
    };
    Component.displayName = "DynamicMock";
    return Component;
  },
}));

vi.mock("@/components/documents/FileUploadField", () => ({
  FileUploadField: ({
    onFileSelect,
  }: {
    onFileSelect: (file: File | null, error: string | null) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        onFileSelect(
          new File(["kaiser upload"], "kaiser-address-statement.pdf", {
            type: "application/pdf",
          }),
          null,
        )
      }
    >
      Select test file
    </button>
  ),
}));

vi.mock("@/components/portal", () => ({
  ProcessStepper: () => <div>Timeline</div>,
}));

vi.mock("@/components/portal/PracticeBaton", () => ({
  PracticeBaton: () => <div>Your turn</div>,
  statusToBaton: () => "your_turn",
}));

vi.mock("@/hooks/usePortalProcessTimeline", () => ({
  usePortalProcessTimeline: () => ({ data: undefined, isLoading: false }),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? <div>{children}</div> : null,
  DialogContent: ({ children }: { children: React.ReactNode }) => (
    <div role="dialog">{children}</div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getProfile: mockGetProfile,
      getMyRequiredDocuments: mockGetMyRequiredDocuments,
    },
    crm: {
      uploadClientDocument: mockUploadClientDocument,
    },
  },
}));

const pendingDocument: ClientRequiredDocument = {
  id: 97,
  practice_id: 603,
  process_name: "Kaiser Test Onboarding",
  process_status: "waiting_documents",
  document_type: "kaiser_live_browser_loop_upload",
  document_label: "Kaiser Live QA Address Statement",
  description: "Address proof",
  is_required: true,
  uploaded_by_client: false,
  status: "pending",
  client_notes: null,
  team_member_notes: null,
};

class MockFileReader {
  result = "data:application/pdf;base64,a2Fpc2Vy";
  onloadend: (() => void) | null = null;

  readAsDataURL() {
    this.onloadend?.();
  }
}

describe("PortalProcessPage", () => {
  const originalFileReader = globalThis.FileReader;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.FileReader = MockFileReader as unknown as typeof FileReader;
    mockGetProfile.mockResolvedValue({ id: 11898, fullName: "Kaiser Test" });
    mockUploadClientDocument.mockResolvedValue({
      success: true,
      document_id: 19027,
      message: "Uploaded",
    });
  });

  afterEach(() => {
    globalThis.FileReader = originalFileReader;
  });

  it("shows uploaded status immediately after upload before the background refresh finishes", async () => {
    const user = userEvent.setup();
    let resolveRefresh: ((value: ClientRequiredDocument[]) => void) | undefined;
    mockGetMyRequiredDocuments
      .mockResolvedValueOnce([pendingDocument])
      .mockImplementationOnce(
        () =>
          new Promise<ClientRequiredDocument[]>((resolve) => {
            resolveRefresh = resolve;
          }),
      );

    const { default: PortalProcessPage } = await import("./page");
    render(<PortalProcessPage />);

    expect(
      await screen.findByText("Kaiser Live QA Address Statement"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^upload$/i }));
    const dialog = await screen.findByRole("dialog");
    await user.click(
      await within(dialog).findByRole("button", { name: /select test file/i }),
    );
    await user.click(within(dialog).getByRole("button", { name: /^upload$/i }));

    await waitFor(() => {
      expect(mockUploadClientDocument).toHaveBeenCalledWith(603, {
        required_doc_id: 97,
        file: "data:application/pdf;base64,a2Fpc2Vy",
        file_name: "kaiser-address-statement.pdf",
        notes: "",
      });
    });
    expect(await screen.findByText("Under Review")).toBeInTheDocument();

    await act(async () => {
      resolveRefresh?.([
        {
          ...pendingDocument,
          uploaded_by_client: true,
          status: "uploaded",
        },
      ]);
    });
  });

  it("drives practice/doc status styling from semantic --state-* tokens (WS3 day pass)", async () => {
    mockGetMyRequiredDocuments.mockResolvedValue([pendingDocument]);

    const { default: PortalProcessPage } = await import("./page");
    render(<PortalProcessPage />);

    // Practice status chip (waiting_documents → --state-warning)
    const chip = await screen.findByText("Waiting for Documents");
    expect(chip).toHaveStyle({ color: "var(--state-warning)" });

    // "Documents Required" banner + required badge read the same token
    // (the stats grid carries a "Documents Required" label too — pick the
    // warning-styled banner title)
    const bannerTitle = (await screen.findAllByText("Documents Required")).find(
      (el) => el.style.color.includes("--state-warning"),
    );
    expect(bannerTitle).toBeDefined();
    expect(screen.getByText("Required")).toHaveStyle({
      color: "var(--state-warning)",
    });

    // Doc status badge (pending → --state-warning)
    expect(screen.getByText("Pending")).toHaveStyle({
      color: "var(--state-warning)",
    });

    // Pending stat value uses --state-warning (was text-amber-400)
    const statsLabel = screen.getByText("Pending Upload");
    const statValue = statsLabel.parentElement?.querySelector(
      "p.text-2xl",
    ) as HTMLElement;
    expect(statValue).toHaveStyle({ color: "var(--state-warning)" });
  });

  it("renders the Day masthead: copper rule + Cormorant serif headline", async () => {
    mockGetMyRequiredDocuments.mockResolvedValue([pendingDocument]);

    const { default: PortalProcessPage } = await import("./page");
    render(<PortalProcessPage />);

    const heading = await screen.findByRole("heading", {
      level: 1,
      name: "My Processes",
    });
    expect(heading).toHaveStyle({ fontFamily: "var(--font-serif)" });
    expect(heading.className).toContain("text-[var(--tx-pure)]");
  });
});
