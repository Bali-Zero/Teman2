// filters.ts — JID helpers and legacy match classifier.
//
// Current capture policy is store-everything for one-to-one chats. No CRM
// match means prospect/client_id=NULL, not a dropped message. Groups and
// malformed JIDs remain out of scope.

import { findClientByPhone } from "./pg.js";

export type FilterDecision = {
  mirror: boolean;
  clientId: number | null;
  reason: "client_match" | "no_client_match" | "self_message" | "empty_jid";
  counterpartNormalized: string;
};

/**
 * Extract a normalized phone number from a Baileys JID.
 *
 * Baileys JID formats we care about:
 *   <country><number>@s.whatsapp.net  — direct chat (1-to-1)
 *   <country><number>@c.us            — older format, same meaning
 *   <number>@g.us                     — group (we filter these out entirely)
 *   <number>:<device>@s.whatsapp.net  — multi-device suffix
 *
 * Returns digit-only string (e.g. "628123456789") or empty string when the
 * JID is a group or unparseable. Groups are NEVER mirrored.
 */
export function jidToPhone(jid: string | null | undefined): string {
  if (!jid) return "";
  // Reject groups outright — group chats are out of v1 scope.
  if (jid.endsWith("@g.us")) return "";
  // Strip device suffix and JID server.
  const beforeServer = jid.split("@")[0] ?? "";
  const beforeDevice = beforeServer.split(":")[0] ?? "";
  return beforeDevice.replace(/[^\d]/g, "");
}

/**
 * Legacy classifier retained for callers that want CRM match metadata.
 *
 * A no-client match is still mirrorable: the message is a prospect/lead and
 * must be stored with client_id=NULL. Only empty JIDs and self-messages are
 * non-mirrorable.
 *
 * Self-messages (team member writing notes to themselves) are dropped.
 */
export async function shouldMirror(opts: {
  counterpartJid: string | null;
  teamMemberPhone: string;
}): Promise<FilterDecision> {
  const counterpart = jidToPhone(opts.counterpartJid);
  if (counterpart.length === 0) {
    return {
      mirror: false,
      clientId: null,
      reason: "empty_jid",
      counterpartNormalized: "",
    };
  }
  if (counterpart === opts.teamMemberPhone.replace(/[^\d]/g, "")) {
    return {
      mirror: false,
      clientId: null,
      reason: "self_message",
      counterpartNormalized: counterpart,
    };
  }
  const clientId = await findClientByPhone(counterpart);
  if (clientId === null) {
    return {
      mirror: true,
      clientId: null,
      reason: "no_client_match",
      counterpartNormalized: counterpart,
    };
  }
  return {
    mirror: true,
    clientId,
    reason: "client_match",
    counterpartNormalized: counterpart,
  };
}
