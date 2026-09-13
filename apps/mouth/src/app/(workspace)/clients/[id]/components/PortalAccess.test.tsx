/**
 * PortalAccess — the first caller the invitation endpoints have ever had.
 *
 * `POST /api/crm/portal/clients/{id}/invite` shipped months ago with NO caller
 * anywhere in apps/mouth: it could only be reached by hand-crafting an HTTP
 * request with a team JWT. Measured on production 2026-09-10, the last portal
 * invitation and the last client portal login are both dated 2026-07-10 —
 * consultants had no way to send one. So this component's contract is not
 * cosmetic, and the tests below are about which BUTTON a consultant is shown,
 * because each wrong branch has its own real-world cost:
 *
 *   - inviting a client who already has access  -> a confusing second email
 *   - inviting on a FAILED status read          -> a duplicate invitation
 *   - inviting with no email on file            -> a guaranteed 400
 *   - a bare "failed" toast on the 403          -> the consultant hunts logs
 *     for the assigned-owner rule the backend already stated
 *
 * The failed-read case is the one worth stating plainly: an error must NOT
 * degrade into the "no portal access yet" branch, because that branch offers
 * the invite button. Failing open there is how a client gets invited twice.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PortalAccess } from "./PortalAccess";
import { api } from "@/lib/api";
import { toast } from "sonner";

vi.mock("@/lib/api", () => ({
  api: {
    crm: {
      getPortalStatus: vi.fn(),
      sendPortalInvite: vi.fn(),
    },
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const NO_ACCESS = {
  has_portal_access: false,
  portal_user_id: null,
  portal_email: null,
  last_login: null,
  pending_invite: false,
  invite_expires_at: null,
};

const PENDING = {
  ...NO_ACCESS,
  pending_invite: true,
  invite_expires_at: "2026-09-13T00:00:00Z",
};

const ACTIVE = {
  has_portal_access: true,
  portal_user_id: 12,
  portal_email: "client@example.com",
  last_login: "2026-09-01T00:00:00Z",
  pending_invite: false,
  invite_expires_at: null,
};

function renderPanel(email: string | null = "client@example.com") {
  return render(
    <PortalAccess
      clientId={4}
      clientName="Pilot Invitee"
      clientEmail={email}
    />,
  );
}

beforeEach(() => {
  vi.mocked(api.crm.getPortalStatus).mockReset();
  vi.mocked(api.crm.sendPortalInvite).mockReset();
  vi.mocked(toast.success).mockReset();
  vi.mocked(toast.error).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("PortalAccess", () => {
  // Portal audit F1 (2026-09-11): the login identity is
  // `team_members.email`, which a CRM email edit does not move. The panel
  // rendered the stale address as if it were current, so a consultant who
  // had just changed the email had no way to know the client still signs in
  // with the old one.
  it("names the divergence when the login email is not the CRM email", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(ACTIVE);
    renderPanel("moved@example.com");

    expect(
      await screen.findByText(/signs in as client@example\.com/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the CRM now has moved@example\.com/i),
    ).toBeInTheDocument();
  });

  it("stays quiet when the two emails agree", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(ACTIVE);
    renderPanel("client@example.com");

    await screen.findByText(/portal active/i);
    expect(screen.queryByText(/signs in as/i)).not.toBeInTheDocument();
  });

  it("offers the invite button when the client has no portal access", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(NO_ACCESS);
    renderPanel();

    const button = await screen.findByRole("button", {
      name: /invite to portal/i,
    });
    expect(button).toBeEnabled();
  });

  it("sends the invitation and confirms it by name", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(NO_ACCESS);
    vi.mocked(api.crm.sendPortalInvite).mockResolvedValue({
      emailSent: true,
      emailError: null,
    });
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: /invite to portal/i }),
    );

    await waitFor(() =>
      expect(api.crm.sendPortalInvite).toHaveBeenCalledWith(
        4,
        "client@example.com",
      ),
    );
    expect(toast.success).toHaveBeenCalledWith(
      "Portal invitation emailed to Pilot Invitee",
    );
    // The status is re-read so the panel does not keep offering "Invite"
    // after the invitation exists.
    expect(vi.mocked(api.crm.getPortalStatus).mock.calls.length).toBe(2);
  });

  it("does NOT claim success when the invitation was minted but the email failed", async () => {
    // The failure the pilot actually risks: the row exists, the consultant is
    // told "sent", and the client waits for a link that never arrives.
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(NO_ACCESS);
    vi.mocked(api.crm.sendPortalInvite).mockResolvedValue({
      emailSent: false,
      emailError: "Brevo rejected the recipient",
    });
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: /invite to portal/i }),
    );

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(toast.success).not.toHaveBeenCalled();
    expect(vi.mocked(toast.error).mock.calls[0][0]).toMatch(/did NOT go out/i);
    expect(vi.mocked(toast.error).mock.calls[0][1]).toMatchObject({
      description: "Brevo rejected the recipient",
    });
  });

  it("never exposes the invite token — the email is its only channel", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(NO_ACCESS);
    vi.mocked(api.crm.sendPortalInvite).mockResolvedValue({
      emailSent: true,
      emailError: null,
    });
    const { container } = renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: /invite to portal/i }),
    );
    await waitFor(() => expect(api.crm.sendPortalInvite).toHaveBeenCalled());

    expect(container.textContent).not.toMatch(/token|invite_url|\/register\?/i);
  });

  it("explains the assigned-owner rule instead of a bare failure on 403", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(NO_ACCESS);
    vi.mocked(api.crm.sendPortalInvite).mockRejectedValue(
      new Error("403 Forbidden"),
    );
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: /invite to portal/i }),
    );

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(vi.mocked(toast.error).mock.calls[0][1]).toMatchObject({
      description: expect.stringContaining("assigned to this client"),
    });
  });

  it("passes a non-permission error through verbatim", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(NO_ACCESS);
    vi.mocked(api.crm.sendPortalInvite).mockRejectedValue(
      new Error("Client has no email address"),
    );
    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: /invite to portal/i }),
    );

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(vi.mocked(toast.error).mock.calls[0][1]).toMatchObject({
      description: "Client has no email address",
    });
  });

  it("offers resend, not invite, while an invitation is pending", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(PENDING);
    renderPanel();

    expect(await screen.findByText(/invitation pending/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /send again/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /invite to portal/i }),
    ).toBeNull();
  });

  it("offers no invitation at all once the portal is active", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(ACTIVE);
    renderPanel();

    expect(await screen.findByText(/portal active/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /invite|send again/i }),
    ).toBeNull();
  });

  it("does NOT fall back to the invite button when the status read fails", async () => {
    vi.mocked(api.crm.getPortalStatus).mockRejectedValue(new Error("boom"));
    renderPanel();

    expect(
      await screen.findByText(/portal status unavailable/i),
    ).toBeInTheDocument();
    // The whole point: a failed read must not look like "no access yet",
    // because that branch would invite the client a second time.
    expect(
      screen.queryByRole("button", { name: /invite to portal/i }),
    ).toBeNull();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("cannot invite a client with no email on file", async () => {
    vi.mocked(api.crm.getPortalStatus).mockResolvedValue(NO_ACCESS);
    renderPanel(null);

    const button = await screen.findByRole("button", {
      name: /invite to portal/i,
    });
    expect(button).toBeDisabled();
    expect(screen.getByText(/no email address on file/i)).toBeInTheDocument();
  });
});
