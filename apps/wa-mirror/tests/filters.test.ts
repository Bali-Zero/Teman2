// filters.test.ts — unit tests for the wa-mirror privacy gate.
//
// jidToPhone() is load-bearing for the PRIVACY_CONTRACT_TEAM.md commitment:
// it MUST return "" for any group JID (@g.us) so group chats never reach the
// mirror path, and it MUST normalise direct-chat JIDs to a digit-only string
// so the clients-table lookup in shouldMirror() can match.
//
// shouldMirror() itself touches Postgres (findClientByPhone), so it is out of
// scope for this pure-function test file — the jidToPhone behaviour it
// depends on is what we pin here.

import { describe, expect, it } from "vitest";

import { jidToPhone } from "../bridge/filters.js";

describe("jidToPhone — group rejection (privacy contract)", () => {
  it("returns empty string for any @g.us group JID", () => {
    expect(jidToPhone("120363012345678901@g.us")).toBe("");
    expect(jidToPhone("0@g.us")).toBe("");
  });

  it("rejects group JIDs even if they contain a phone-like prefix", () => {
    // A group id can be all-digits; the @g.us suffix is the only signal.
    expect(jidToPhone("628123456789@g.us")).toBe("");
  });
});

describe("jidToPhone — direct chat normalisation", () => {
  it("extracts digits from a standard @s.whatsapp.net JID", () => {
    expect(jidToPhone("628123456789@s.whatsapp.net")).toBe("628123456789");
  });

  it("extracts digits from the legacy @c.us JID", () => {
    expect(jidToPhone("628123456789@c.us")).toBe("628123456789");
  });

  it("strips the multi-device :<device> suffix", () => {
    // This is the exact shape Baileys reported for zero@balizero.com:
    //   628213107363:1@s.whatsapp.net
    expect(jidToPhone("628213107363:1@s.whatsapp.net")).toBe("628213107363");
    expect(jidToPhone("628123456789:42@s.whatsapp.net")).toBe("628123456789");
  });

  it("strips any non-digit characters defensively", () => {
    expect(jidToPhone("+62 812-3456-789@s.whatsapp.net")).toBe("628123456789");
  });
});

describe("jidToPhone — empty / malformed input", () => {
  it("returns empty string for null/undefined/empty", () => {
    expect(jidToPhone(null)).toBe("");
    expect(jidToPhone(undefined)).toBe("");
    expect(jidToPhone("")).toBe("");
  });

  it("returns empty string when there are no digits at all", () => {
    expect(jidToPhone("@s.whatsapp.net")).toBe("");
    expect(jidToPhone("status@broadcast")).toBe("");
  });
});
