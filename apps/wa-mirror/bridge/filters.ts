// filters.ts — JID helpers and legacy match classifier.
//
// WhatsApp ships two distinct JID server tags relevant to wa-mirror:
//   1. `@s.whatsapp.net` / `@c.us` — the user part is the actual phone
//      number (E.164 digits, no `+`).
//   2. `@lid` — Linked Identity Device, an anonymous identifier rolled
//      out late 2024 for privacy-shielded contacts. The user part is
//      NOT a phone number; it is a random 15-16-digit string.
//
// Pre-2026-05-19 the bridge only handled (1) and silently turned (2)
// into fake E.164 by prepending `62`. That broke 70% of inbound match
// in production (the `+62…17-18 digit` rows in whatsapp_message_context).
// v2 separates the two surfaces via `parseJid()`.

import { findClientByPhone } from "./pg.js";
import { normalizePhone } from "./phone.js";

export type JidKind = "phone" | "lid" | "group" | "broadcast" | "empty";

export type ParsedJid = {
  /** Always populated. */
  kind: JidKind;
  /** Canonical E.164 (with `+`) when kind === "phone", else "". */
  phone: string;
  /** The LID identifier (digits only) when kind === "lid", else "". */
  lid: string;
  /** Raw server tag stripped of leading "@" — for diagnostics. */
  server: string;
};

const GROUP_SERVER = "g.us";
const BROADCAST_SERVER = "broadcast";
const NEWSLETTER_SERVER = "newsletter";
const LID_SERVER = "lid";
const PHONE_SERVERS = new Set(["s.whatsapp.net", "c.us"]);

/**
 * Parse a Baileys JID into a typed shape. Returns kind="empty" for any
 * non-string / missing input. Never throws.
 */
export function parseJid(jid: string | null | undefined): ParsedJid {
  const empty: ParsedJid = { kind: "empty", phone: "", lid: "", server: "" };
  if (!jid || typeof jid !== "string") return empty;

  const sepIdx = jid.indexOf("@");
  if (sepIdx < 0) return empty;

  const server = jid.slice(sepIdx + 1);
  const userCombined = jid.slice(0, sepIdx);
  // strip `:<device>` multi-device suffix and `_<agent>` (rare)
  const beforeDevice = userCombined.split(":")[0] ?? "";
  const user = beforeDevice.split("_")[0] ?? "";

  if (server === GROUP_SERVER) {
    return { kind: "group", phone: "", lid: "", server };
  }
  if (server === BROADCAST_SERVER || server === NEWSLETTER_SERVER) {
    return { kind: "broadcast", phone: "", lid: "", server };
  }

  if (server === LID_SERVER) {
    const lid = user.replace(/[^\d]/g, "");
    if (lid.length === 0) return empty;
    return { kind: "lid", phone: "", lid, server };
  }

  if (PHONE_SERVERS.has(server)) {
    // `user` here is a bare phone (no `+`). normalizePhone will:
    // (a) validate via libphonenumber (rejects garbage),
    // (b) emit canonical E.164 with `+`.
    // We prepend `+` so libphonenumber treats it as international (the
    // user part of @s.whatsapp.net ALWAYS includes country code).
    const digits = user.replace(/[^\d]/g, "");
    if (digits.length === 0) return empty;
    const e164 = normalizePhone(`+${digits}`);
    if (!e164) return empty;
    return { kind: "phone", phone: e164, lid: "", server };
  }

  return empty;
}

/**
 * Legacy: extract a digit-only phone string from a Baileys JID.
 *
 * v1 behaviour preserved for callers that still expect a string: returns
 * "" for groups/broadcasts/LIDs/malformed; returns digit-only E.164 for
 * phone JIDs. LIDs return "" — callers that need the LID must use
 * `parseJid()` instead.
 *
 * NOTE: this is a STRICTER contract than the pre-v2 version. Previously
 * LIDs slipped through as fake phone numbers. Callers that need to keep
 * the LID separate MUST migrate to `parseJid()`.
 */
export function jidToPhone(jid: string | null | undefined): string {
  const parsed = parseJid(jid);
  if (parsed.kind !== "phone") return "";
  return parsed.phone.replace(/[^\d]/g, "");
}

export type FilterDecision = {
  mirror: boolean;
  clientId: number | null;
  reason:
    | "client_match"
    | "no_client_match"
    | "self_message"
    | "empty_jid"
    | "lid_unresolved";
  counterpartNormalized: string;
  counterpartLid: string;
};

/**
 * Legacy classifier retained for callers that want CRM match metadata.
 *
 * Behaviour for LID JIDs (kind === "lid"): we cannot do CRM matching
 * because we don't know the real phone yet. The message is still
 * mirrorable — the caller is expected to populate `counterpart_lid` and
 * let the async resolver (whatsapp_lid_phone_map) attribute later.
 *
 * Self-messages (team member writing notes to themselves) are dropped.
 */
export async function shouldMirror(opts: {
  counterpartJid: string | null;
  teamMemberPhone: string;
}): Promise<FilterDecision> {
  const parsed = parseJid(opts.counterpartJid);
  if (
    parsed.kind === "empty" ||
    parsed.kind === "group" ||
    parsed.kind === "broadcast"
  ) {
    return {
      mirror: false,
      clientId: null,
      reason: "empty_jid",
      counterpartNormalized: "",
      counterpartLid: "",
    };
  }

  if (parsed.kind === "lid") {
    return {
      mirror: true,
      clientId: null,
      reason: "lid_unresolved",
      counterpartNormalized: "",
      counterpartLid: parsed.lid,
    };
  }

  // parsed.kind === "phone"
  const counterpartDigits = parsed.phone.replace(/[^\d]/g, "");
  const teamDigits = opts.teamMemberPhone.replace(/[^\d]/g, "");
  if (counterpartDigits === teamDigits) {
    return {
      mirror: false,
      clientId: null,
      reason: "self_message",
      counterpartNormalized: parsed.phone,
      counterpartLid: "",
    };
  }
  const clientId = await findClientByPhone(parsed.phone);
  return {
    mirror: true,
    clientId,
    reason: clientId === null ? "no_client_match" : "client_match",
    counterpartNormalized: parsed.phone,
    counterpartLid: "",
  };
}
