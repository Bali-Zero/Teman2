// filters.test.ts — unit tests for the wa-mirror JID parser.
//
// parseJid() must distinguish (1) real phone JIDs (@s.whatsapp.net / @c.us),
// (2) LID identifiers (@lid, WhatsApp privacy-shielded anonymous IDs rolled
// out late 2024), (3) groups (@g.us, dropped from mirror), and (4) malformed
// input. The pre-v2 bridge collapsed (2) into fake phone numbers; the LID
// branch here is the regression fence for that bug.

import { describe, expect, it } from "vitest";

import { jidToPhone, parseJid } from "../bridge/filters.js";

describe("parseJid — phone server (@s.whatsapp.net / @c.us)", () => {
  it("returns kind='phone' and canonical E.164 for standard JID", () => {
    expect(parseJid("628123456789@s.whatsapp.net")).toEqual({
      kind: "phone",
      phone: "+628123456789",
      lid: "",
      server: "s.whatsapp.net",
    });
  });

  it("handles the legacy @c.us server tag", () => {
    expect(parseJid("628123456789@c.us")).toMatchObject({
      kind: "phone",
      phone: "+628123456789",
      server: "c.us",
    });
  });

  it("strips the :<device> multi-device suffix", () => {
    expect(parseJid("6282230102328:1@s.whatsapp.net")).toMatchObject({
      kind: "phone",
      phone: "+6282230102328",
    });
    expect(parseJid("6282230102328:42@s.whatsapp.net")).toMatchObject({
      kind: "phone",
      phone: "+6282230102328",
    });
  });

  it("preserves international numbers (Italian +39)", () => {
    expect(parseJid("393398745516@s.whatsapp.net")).toMatchObject({
      kind: "phone",
      phone: "+393398745516",
    });
  });

  it("returns kind='empty' when the JID user has no digits", () => {
    expect(parseJid("@s.whatsapp.net")).toMatchObject({ kind: "empty" });
  });
});

describe("parseJid — @lid (privacy-shielded identifiers)", () => {
  it("returns kind='lid' and preserves the raw LID identifier, NO phone synthesis", () => {
    expect(parseJid("224112131756075@lid")).toEqual({
      kind: "lid",
      phone: "",
      lid: "224112131756075",
      server: "lid",
    });
  });

  it("never injects +62 into a LID identifier (regression for the +62NNNNNNNNNNNNN bug)", () => {
    const cases = [
      "224112131756075@lid",
      "179065826877524@lid",
      "187840445030654@lid",
      "224971225866242@lid",
    ];
    for (const jid of cases) {
      const out = parseJid(jid);
      expect(out.kind).toBe("lid");
      expect(out.phone).toBe("");
      expect(out.lid).not.toMatch(/^\+62/);
    }
  });
});

describe("parseJid — group / broadcast / newsletter (must NOT be mirrored)", () => {
  it("returns kind='group' for @g.us regardless of digit content", () => {
    expect(parseJid("120363012345678901@g.us")).toMatchObject({
      kind: "group",
    });
    expect(parseJid("628123456789@g.us")).toMatchObject({ kind: "group" });
  });

  it("returns kind='broadcast' for status / broadcast / newsletter", () => {
    expect(parseJid("status@broadcast")).toMatchObject({ kind: "broadcast" });
    expect(parseJid("0@broadcast")).toMatchObject({ kind: "broadcast" });
    expect(parseJid("xxx@newsletter")).toMatchObject({ kind: "broadcast" });
  });
});

describe("parseJid — empty / malformed", () => {
  it("returns kind='empty' for null / undefined / empty / no-@", () => {
    expect(parseJid(null)).toMatchObject({ kind: "empty" });
    expect(parseJid(undefined)).toMatchObject({ kind: "empty" });
    expect(parseJid("")).toMatchObject({ kind: "empty" });
    expect(parseJid("no-at-sign-here")).toMatchObject({ kind: "empty" });
  });
});

describe("jidToPhone (legacy) — STRICTER post-v2 contract", () => {
  it("returns digits for phone JIDs", () => {
    expect(jidToPhone("6282230102328:1@s.whatsapp.net")).toBe("6282230102328");
  });

  it("returns '' for @lid (BREAKING change from v1 — callers must migrate to parseJid)", () => {
    expect(jidToPhone("224112131756075@lid")).toBe("");
  });

  it("returns '' for groups, broadcasts, malformed", () => {
    expect(jidToPhone("120363012345678901@g.us")).toBe("");
    expect(jidToPhone("status@broadcast")).toBe("");
    expect(jidToPhone(null)).toBe("");
    expect(jidToPhone("")).toBe("");
  });
});
