import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NewClientPage from "./page";

// --- module mocks -----------------------------------------------------------
const { push, getProfile, createClient, uploadClientAvatar, toastError } =
  vi.hoisted(() => ({
    push: vi.fn(),
    getProfile: vi.fn(),
    createClient: vi.fn(),
    uploadClientAvatar: vi.fn(),
    toastError: vi.fn(),
  }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile,
    crm: { createClient, uploadClientAvatar, uploadDocumentBase64: vi.fn() },
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: toastError, success: vi.fn() }),
}));

vi.mock("@/hooks/useTeamMembers", () => ({
  useTeamMemberOptions: () => ({ options: [] }),
}));

vi.mock("./components/PassportScanSection", () => ({
  default: () => <div data-testid="passport-scan-mock" />,
}));

// The real cropper needs a canvas; the contract under test is that a BLOB (not
// a base64 data: URI) reaches the upload endpoint.
vi.mock("@/lib/utils/imageResize", () => ({
  cropToSquareBlob: vi
    .fn()
    .mockResolvedValue(new Blob(["fake-jpeg-bytes"], { type: "image/jpeg" })),
}));

/** The create payload (1st arg) sent to api.crm.createClient. */
function createPayload(): Record<string, unknown> {
  const call = createClient.mock.calls[createClient.mock.calls.length - 1];
  return (call?.[0] ?? {}) as Record<string, unknown>;
}

/** Open the manual form (the page opens on a scan-vs-manual chooser). */
async function openManualForm(): Promise<void> {
  render(<NewClientPage />);
  await userEvent.click(screen.getByRole("button", { name: /manual entry/i }));
}

async function fillNameAndSubmit(): Promise<void> {
  // The form's labels are not associated to their controls (no htmlFor/id), so
  // getByLabelText can't reach the input — select by its name attribute.
  const name = document.querySelector<HTMLInputElement>(
    'input[name="full_name"]',
  );
  if (!name) throw new Error("full_name input not rendered");
  await userEvent.type(name, "Test Client");
  // The form is a 3-section wizard; Create Client lives in the last one.
  await userEvent.click(screen.getByRole("button", { name: /crm settings/i }));
  await userEvent.click(screen.getByRole("button", { name: /create client/i }));
  await waitFor(() => expect(createClient).toHaveBeenCalled());
}

async function attachPhoto(): Promise<void> {
  const file = new File(["img-bytes"], "photo.png", { type: "image/png" });
  await userEvent.upload(screen.getByLabelText(/upload client photo/i), file);
}

describe("NewClientPage — avatar never travels as a data: URI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getProfile.mockResolvedValue({ email: "surya@balizero.com" });
    createClient.mockResolvedValue({ id: 4242 });
    uploadClientAvatar.mockResolvedValue({
      avatar_url: "https://cdn.example.com/client-avatar/4242/abcd1234.jpg",
    });
    // jsdom has no object-URL implementation.
    global.URL.createObjectURL = vi.fn(() => "blob:preview");
    global.URL.revokeObjectURL = vi.fn();
  });

  it("never puts avatar_url in the create payload, even with a photo attached", async () => {
    await openManualForm();
    await attachPhoto();
    await fillNameAndSubmit();

    // THE invariant: inline base64 in avatar_url is what poisoned 19 of 1744
    // rows — the backend rejects it and a persisted one blocks every later edit.
    const payload = createPayload();
    expect(payload).not.toHaveProperty("avatar_url");
    expect(JSON.stringify(payload)).not.toContain("data:");
    expect(payload).toHaveProperty("full_name", "Test Client");
  });

  it("uploads the photo as bytes AFTER the client exists, with the new id", async () => {
    await openManualForm();
    await attachPhoto();
    await fillNameAndSubmit();

    await waitFor(() => expect(uploadClientAvatar).toHaveBeenCalled());
    const [clientId, file] = uploadClientAvatar.mock.calls[0];
    expect(clientId).toBe(4242); // the id createClient returned
    expect(file).toBeInstanceOf(File); // bytes, not a base64 string
  });

  it("does not call the avatar upload when no photo was attached", async () => {
    await openManualForm();
    await fillNameAndSubmit();

    expect(uploadClientAvatar).not.toHaveBeenCalled();
  });

  it("keeps the created client when the avatar upload fails", async () => {
    uploadClientAvatar.mockRejectedValue(new Error("Tigris down"));

    await openManualForm();
    await attachPhoto();
    await fillNameAndSubmit();

    // The client exists; losing the photo must not lose the client.
    await waitFor(() => expect(push).toHaveBeenCalledWith("/clients/4242"));
    expect(toastError).toHaveBeenCalled();
  });

  it("drops the photo when removed before submit", async () => {
    await openManualForm();
    await attachPhoto();
    await userEvent.click(
      screen.getByRole("button", { name: /remove avatar/i }),
    );
    await fillNameAndSubmit();

    expect(uploadClientAvatar).not.toHaveBeenCalled();
    expect(createPayload()).not.toHaveProperty("avatar_url");
  });
});
