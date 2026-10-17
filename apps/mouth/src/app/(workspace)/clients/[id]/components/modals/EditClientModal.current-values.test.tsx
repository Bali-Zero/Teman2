import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { EditClientModal } from "./EditClientModal";
import type { Client } from "@/lib/api/crm/crm.types";

// Edit Client must SHOW the values the record already holds. Test on client
// 12414 (12 Oct): the record was assigned to a staff address that is not in
// the team-member list and had status "prospect", which is not one of the
// five status buttons. The modal showed "Unassigned" and no selected status,
// so a staff member touching either control could overwrite the real value
// without ever having seen it.

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn(),
    crm: { updateClient: vi.fn(), uploadClientAvatar: vi.fn() },
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({
    options: [{ value: "listed@example.com", label: "Listed Member" }],
  }),
}));

vi.mock("@/lib/utils/imageResize", () => ({
  cropToSquareBlob: vi.fn(),
}));

function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: 12414,
    uuid: "uuid-12414",
    full_name: "Test Client",
    status: "lead",
    client_type: "individual",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as Client;
}

function assignedSelect(): HTMLSelectElement {
  const label = screen.getByText("Assigned To");
  const select = label.parentElement?.querySelector("select");
  if (!select) throw new Error("Assigned To select not found");
  return select as HTMLSelectElement;
}

function statusGroup(): HTMLElement {
  const label = screen.getByText("Status", { selector: "label" });
  const group = label.parentElement;
  if (!group) throw new Error("Status group not found");
  return group;
}

function renderModal(client: Client) {
  render(
    <EditClientModal client={client} onClose={vi.fn()} onSave={vi.fn()} />,
  );
}

describe("EditClientModal — shows the record's current values", () => {
  beforeEach(() => vi.clearAllMocks());

  it("positive control: a listed assignee is selected by its own label", () => {
    renderModal(makeClient({ assigned_to: "listed@example.com" }));
    const select = assignedSelect();
    expect(select.value).toBe("listed@example.com");
    expect(select.selectedOptions[0]?.textContent).toBe("Listed Member");
  });

  it("an assignee missing from the team list is shown, not 'Unassigned'", () => {
    renderModal(makeClient({ assigned_to: "unlisted@example.com" }));
    const select = assignedSelect();
    expect(select.value).toBe("unlisted@example.com");
    expect(select.selectedOptions[0]?.textContent).toContain(
      "unlisted@example.com",
    );
    expect(select.selectedOptions[0]?.textContent).not.toBe("Unassigned");
  });

  it("an unassigned client still reads 'Unassigned' with no extra option", () => {
    renderModal(makeClient({ assigned_to: undefined }));
    const select = assignedSelect();
    expect(select.value).toBe("");
    expect(select.options).toHaveLength(2);
  });

  it("a status outside the five buttons (prospect) is shown as selected", () => {
    renderModal(makeClient({ status: "prospect" as Client["status"] }));
    const current = within(statusGroup()).getByRole("button", {
      name: /prospect/i,
    });
    expect(current).toHaveAttribute("aria-pressed", "true");
  });

  it("a known status keeps exactly the five buttons", () => {
    renderModal(makeClient({ status: "active" }));
    const buttons = within(statusGroup()).getAllByRole("button");
    expect(buttons).toHaveLength(5);
    expect(
      within(statusGroup()).getByRole("button", { name: "Active" }),
    ).toHaveAttribute("aria-pressed", "true");
  });
});
