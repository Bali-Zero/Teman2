import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditDocumentModal } from "./EditDocumentModal";
import { viewerCanChangeDocumentVisibility } from "./document-visibility";
import type { ClientDocument } from "@/lib/api/crm/crm.types";

const { updateDocument } = vi.hoisted(() => ({ updateDocument: vi.fn() }));

vi.mock("@/lib/api", () => ({ api: { crm: { updateDocument } } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

function makeDoc(overrides: Partial<ClientDocument> = {}): ClientDocument {
  return {
    id: 501,
    client_id: 12414,
    document_type: "notes",
    file_name: "notes.txt",
    document_category: "other",
    client_visible: true,
    ...overrides,
  } as ClientDocument;
}

function renderModal(doc: ClientDocument, canChangeVisibility: boolean) {
  return render(
    <EditDocumentModal
      clientId={12414}
      document={doc}
      categories={[]}
      familyMembers={[]}
      canChangeVisibility={canChangeVisibility}
      onClose={vi.fn()}
      onSave={vi.fn()}
    />,
  );
}

function lastPayload(): Record<string, unknown> {
  const calls = updateDocument.mock.calls;
  return (calls[calls.length - 1]?.[2] ?? {}) as Record<string, unknown>;
}

async function clickSave() {
  await userEvent.click(screen.getByRole("button", { name: /save/i }));
  await waitFor(() => expect(updateDocument).toHaveBeenCalled());
}

describe("EditDocumentModal — visible to client (contract: Comm Log 192)", () => {
  beforeEach(() => {
    updateDocument.mockReset();
    updateDocument.mockResolvedValue({ success: true });
  });

  it("GUILT: flipping the toggle sends client_visible=false", async () => {
    renderModal(makeDoc({ client_visible: true }), true);
    const toggle = screen.getByRole("checkbox", { name: /visible to client/i });
    expect(toggle).toBeChecked();
    await userEvent.click(toggle);
    await clickSave();
    expect(lastPayload()).toHaveProperty("client_visible", false);
  });

  it("GUILT: a hidden document can be made visible again", async () => {
    renderModal(makeDoc({ client_visible: false }), true);
    const toggle = screen.getByRole("checkbox", { name: /visible to client/i });
    expect(toggle).not.toBeChecked();
    await userEvent.click(toggle);
    await clickSave();
    expect(lastPayload()).toHaveProperty("client_visible", true);
  });

  it("INNOCENCE: saving without touching the toggle never sends the field", async () => {
    renderModal(makeDoc({ client_visible: true }), true);
    await clickSave();
    expect(lastPayload()).not.toHaveProperty("client_visible");
    expect(lastPayload()).toHaveProperty("file_name", "notes.txt");
  });

  it("INNOCENCE: a viewer outside the allowed roles gets no toggle and never sends the field", async () => {
    renderModal(makeDoc({ client_visible: false }), false);
    expect(
      screen.queryByRole("checkbox", { name: /visible to client/i }),
    ).toBeNull();
    expect(screen.getByText(/hidden from the client/i)).toBeInTheDocument();
    await clickSave();
    expect(lastPayload()).not.toHaveProperty("client_visible");
  });

  it("INNOCENCE: a backend without the field shows no visibility row at all", () => {
    renderModal(makeDoc({ client_visible: undefined }), true);
    expect(
      screen.queryByRole("checkbox", { name: /visible to client/i }),
    ).toBeNull();
    expect(screen.queryByText(/hidden from the client/i)).toBeNull();
  });
});

describe("viewerCanChangeDocumentVisibility — mirrors crm_utils.py gate", () => {
  it.each([
    "admin",
    "Founder",
    "CEO",
    "board member",
    "Team Leader",
    "tax lead",
    " Supervisor ",
  ])("allows %s", (role) => {
    expect(viewerCanChangeDocumentVisibility(role)).toBe(true);
  });

  it.each([
    "consultant",
    "junior consultant",
    "tax care",
    "reception",
    "",
    undefined,
  ])("refuses %s", (role) => {
    expect(viewerCanChangeDocumentVisibility(role)).toBe(false);
  });
});
