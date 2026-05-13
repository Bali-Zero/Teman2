// filters.ts — privacy gate. The PRIVACY_CONTRACT_TEAM.md commitment is
// enforced HERE: a message is mirrored to the CRM only when the counterpart
// phone is a registered Bali Zero client.
//
// This file is the only path to disk for message content. The orchestrator
// MUST go through `shouldMirror()` before any persistence call. There is
// intentionally no "bypass filter" flag.

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
 * Decide whether a message should be mirrored to the CRM.
 *
 * The decision is based ONLY on whether the counterpart phone exists in the
 * Bali Zero clients table. Team-member's own number is NEVER the criterion:
 * messages BETWEEN a team member and a client are mirrored regardless of
 * direction (inbound from client → mirrored; outbound from team member to
 * client → mirrored). Messages between a team member and a non-client are
 * dropped before any text is written.
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
      mirror: false,
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
