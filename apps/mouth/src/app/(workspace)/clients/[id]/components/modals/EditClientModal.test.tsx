import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditClientModal } from "./EditClientModal";
import type { Client } from "@/lib/api/crm/crm.types";

// --- module mocks -----------------------------------------------------------
const { getProfile, updateClient, uploadClientAvatar } = vi.hoisted(() => ({
  getProfile: vi.fn(),
  updateClient: vi.fn(),
  uploadClientAvatar: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile,
    crm: { updateClient, uploadClientAvatar },
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({ options: [] }),
}));

vi.mock("@/lib/utils/imageResize", () => ({
  cropToSquareBlob: vi
    .fn()
    .mockResolvedValue(new Blob(["x"], { type: "image/jpeg" })),
}));

// --- fixtures ---------------------------------------------------------------
function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: 12125,
    uuid: "uuid-12125",
    full_name: "Test Client",
    status: "lead",
    client_type: "individual",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as Client;
}

const DATA_URI = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAA==";

/** The `updates` object (2nd positional arg) sent to api.crm.updateClient. */
function lastUpdatePayload(): Record<string, unknown> {
  const calls = updateClient.mock.calls;
  const call = calls[calls.length - 1];
  return (call?.[1] ?? {}) as Record<string, unknown>;
}

async function clickSave(): Promise<void> {
  await userEvent.click(screen.getByRole("button", { name: /save changes/i }));
  await waitFor(() => expect(updateClient).toHaveBeenCalled());
}

describe("EditClientModal — avatar_url update contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getProfile.mockResolvedValue({ email: "surya@balizero.com" });
    updateClient.mockResolvedValue({});
  });

  it("never echoes a legacy data: URI avatar back on save (the #2208 edit-block bug)", async () => {
    render(
      <EditClientModal
        client={makeClient({ avatar_url: DATA_URI })}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    await clickSave();

    const payload = lastUpdatePayload();
    // The data: URI must NOT be forwarded — the backend rejects it and it would
    // block every edit of clients carrying a pre-#2208 base64 avatar.
    expect(payload).not.toHaveProperty("avatar_url");
    // The rest of the edit still goes through.
    expect(payload).toHaveProperty("full_name", "Test Client");
  });

  it("does not send avatar_url when the client has no avatar (nothing changed)", async () => {
    render(
      <EditClientModal
        client={makeClient({ avatar_url: undefined })}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    await clickSave();

    expect(lastUpdatePayload()).not.toHaveProperty("avatar_url");
  });

  it("forwards an empty avatar_url when the user removes a legacy avatar", async () => {
    render(
      <EditClientModal
        client={makeClient({ avatar_url: DATA_URI })}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    // The remove (X) button only renders when an avatar is present.
    await userEvent.click(
      screen.getByRole("button", { name: /remove avatar/i }),
    );
    await clickSave();

    // Clearing is an explicit change → send "" (never the data: URI).
    expect(lastUpdatePayload()).toHaveProperty("avatar_url", "");
  });

  it("forwards a freshly uploaded storage URL", async () => {
    uploadClientAvatar.mockResolvedValue({
      avatar_url: "https://cdn.example.com/client-avatar/12125/abcd1234.jpg",
    });

    render(
      <EditClientModal
        client={makeClient({ avatar_url: DATA_URI })}
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    const file = new File(["img-bytes"], "photo.png", { type: "image/png" });
    const input = screen.getByLabelText(/upload client photo/i);
    await userEvent.upload(input, file);
    await waitFor(() => expect(uploadClientAvatar).toHaveBeenCalled());

    await clickSave();

    expect(lastUpdatePayload()).toHaveProperty(
      "avatar_url",
      "https://cdn.example.com/client-avatar/12125/abcd1234.jpg",
    );
  });
});
