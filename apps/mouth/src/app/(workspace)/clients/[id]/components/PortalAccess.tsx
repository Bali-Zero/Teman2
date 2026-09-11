"use client";

import React, { useState, useEffect, useCallback } from "react";
import { KeyRound, MailCheck, Clock, ShieldAlert, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { PortalAccessStatus } from "@/lib/api/crm/crm.types";

/**
 * Portal access control for the client-detail page.
 *
 * WHY THIS EXISTS: the invitation endpoints have shipped for months with NO
 * caller anywhere in the workspace — `POST /api/crm/portal/clients/{id}/invite`
 * could only be reached by hand-crafting an HTTP request with a team JWT. The
 * consequence measured on production 2026-09-10: the last portal invitation and
 * the last client portal login are both dated 2026-07-10, because no consultant
 * had a way to send one. This panel is that missing caller.
 *
 * The raw invite token is never available here on purpose: the backend strips
 * `token` and `invite_url` at the router boundary because the Brevo email is
 * their only legitimate channel. So this component can report that an invite
 * was sent, never what it contained.
 */
export function PortalAccess({
  clientId,
  clientName,
  clientEmail,
}: {
  clientId: number;
  clientName: string;
  clientEmail?: string | null;
}) {
  const [status, setStatus] = useState<PortalAccessStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const next = await api.crm.getPortalStatus(clientId);
      setStatus(next);
      setLoadFailed(false);
    } catch {
      // A failed status read must not present as "no portal access" — that
      // would invite a consultant to send a duplicate invitation to a client
      // who already has one. Show the failure instead.
      setLoadFailed(true);
    } finally {
      setIsLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const handleInvite = async () => {
    if (!clientEmail) return;
    setIsSending(true);
    try {
      const { emailSent, emailError } = await api.crm.sendPortalInvite(
        clientId,
        clientEmail,
      );
      if (emailSent) {
        toast.success(`Portal invitation emailed to ${clientName}`);
      } else {
        // The invitation row EXISTS but the mail did not leave, so the client
        // is waiting for a link that will never arrive. Reporting this as a
        // success is how a pilot dies quietly.
        toast.error("Invitation created, but the email did NOT go out", {
          description:
            emailError ??
            "The mail service rejected it. Resend once it is back, or send the client a magic link.",
        });
      }
      await loadStatus();
    } catch (err) {
      const message = (err as Error).message;
      // The assigned-owner rule is the single most likely refusal here, and a
      // generic "failed" toast would send the consultant hunting through logs
      // for a permission rule the backend already stated.
      const isForbidden = /403|forbidden|permission/i.test(message);
      toast.error("Could not send the invitation", {
        description: isForbidden
          ? "Only the team member assigned to this client (or an admin) can invite them."
          : message,
      });
    } finally {
      setIsSending(false);
    }
  };

  // team_members.email (the login) vs clients.email (what the CRM shows).
  // Only meaningful once a portal account exists.
  const loginEmailDiverged = Boolean(
    status?.portal_email &&
    clientEmail &&
    status.portal_email.toLowerCase() !== clientEmail.toLowerCase(),
  );

  const formatDate = (value: string | null) =>
    value
      ? new Date(value).toLocaleDateString(undefined, {
          day: "numeric",
          month: "short",
          year: "numeric",
        })
      : null;

  /* A sign-in is a moment, not a day: the date alone read "Sep 10" in Bali
     for a login made at 05:54 on Sep 11 (portal audit F-07 — the backend
     sent a bare UTC timestamp, now offset-carrying). Showing the time and
     naming the zone is what makes the answer checkable. */
  const formatMoment = (value: string | null) =>
    value
      ? new Date(value).toLocaleString(undefined, {
          day: "numeric",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          timeZoneName: "short",
        })
      : null;

  return (
    <div className="bz-product-panel overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--bz-border)]">
        <div className="flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-[var(--bz-accent)]" />
          <h3 className="text-sm font-medium text-[var(--bz-text-1)]">
            Client Portal Access
          </h3>
        </div>
        <span className="text-xs text-[var(--bz-text-2)]">my.balizero.com</span>
      </div>

      <div className="px-4 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="w-5 h-5 border-2 border-[var(--bz-accent)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : loadFailed ? (
          <div className="flex items-start gap-2">
            <ShieldAlert className="w-4 h-4 text-[var(--bz-text-2)] mt-0.5 shrink-0" />
            <div>
              <p className="text-sm text-[var(--bz-text-1)]">
                Portal status unavailable
              </p>
              <p className="text-xs text-[var(--bz-text-2)] mt-1">
                Not sending an invitation blind — retry before inviting, so this
                client does not receive a second one.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setIsLoading(true);
                  void loadStatus();
                }}
                className="mt-2"
              >
                Retry
              </Button>
            </div>
          </div>
        ) : status?.has_portal_access ? (
          <div className="flex items-start gap-2">
            <MailCheck className="w-4 h-4 text-[var(--bz-accent)] mt-0.5 shrink-0" />
            <div>
              <p className="text-sm text-[var(--bz-text-1)]">
                Portal active
                {status.portal_email ? ` — ${status.portal_email}` : ""}
              </p>
              <p className="text-xs text-[var(--bz-text-2)] mt-1">
                {status.last_login
                  ? `Last signed in ${formatMoment(status.last_login)}`
                  : "Registered, but has never signed in yet"}
              </p>
              {/* The login identity is team_members.email, which a CRM email
                  edit does not move (portal audit F1). Saying so is the whole
                  point: the panel used to render the stale address as if it
                  were current, so a consultant who had just changed the email
                  had no way to know the client still signs in with the old
                  one. */}
              {loginEmailDiverged ? (
                <p className="text-xs text-[var(--state-warning)] mt-1">
                  Signs in as {status.portal_email} — the CRM now has{" "}
                  {clientEmail}. Changing the email here does not move the
                  portal login; the client must keep using {status.portal_email}
                  .
                </p>
              ) : null}
            </div>
          </div>
        ) : status?.pending_invite ? (
          <div className="flex items-start gap-2">
            <Clock className="w-4 h-4 text-[var(--bz-text-2)] mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-[var(--bz-text-1)]">
                Invitation pending
              </p>
              <p className="text-xs text-[var(--bz-text-2)] mt-1">
                {status.invite_expires_at
                  ? `Expires ${formatDate(status.invite_expires_at)}. `
                  : ""}
                Not registered yet.
              </p>
              <Button
                size="sm"
                variant="outline"
                onClick={handleInvite}
                disabled={isSending}
                className="mt-2 gap-1"
              >
                <Send className="w-3.5 h-3.5" />
                {isSending ? "Sending..." : "Send again"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <KeyRound className="w-4 h-4 text-[var(--bz-text-2)] mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-[var(--bz-text-1)]">
                No portal access yet
              </p>
              <p className="text-xs text-[var(--bz-text-2)] mt-1">
                {clientEmail
                  ? `Emails an invitation to ${clientEmail}, where they choose their own PIN.`
                  : "This client has no email address on file, so there is nowhere to send the invitation."}
              </p>
              <Button
                size="sm"
                onClick={handleInvite}
                disabled={isSending || !clientEmail}
                className="mt-2 gap-1"
              >
                <Send className="w-3.5 h-3.5" />
                {isSending ? "Sending..." : "Invite to portal"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
