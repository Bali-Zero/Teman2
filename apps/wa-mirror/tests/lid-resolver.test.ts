import { describe, expect, it, vi } from "vitest";

import {
  InMemoryMessageContextStore,
  persistCapturedMessage,
  type CapturedMessageRecord,
} from "../bridge/message_capture.js";

function makeDirectLidMessage(
  overrides: Partial<CapturedMessageRecord> = {},
): CapturedMessageRecord {
  return {
    baileysMessageId: "lid-msg-1",
    direction: "inbound",
    teamMemberPhone: "+628213454725",
    teamMemberEmail: "",
    counterpartPhone: "",
    counterpartLid: "138654580269171",
    body: "hi",
    timestamp: new Date("2026-05-26T10:00:00.000Z"),
    mediaType: "text",
    mediaMime: null,
    mediaUrl: null,
    rawBaileysEvent: { key: { id: "lid-msg-1" } },
    chatType: "direct",
    groupJid: null,
    groupSubject: null,
    senderPhone: null,
    senderLid: null,
    senderJid: null,
    senderPushName: null,
    ...overrides,
  };
}

describe("FIX 3 (2026-05-26): LID→phone resolver", () => {
  it("resolves counterpartLid to counterpartPhone via deps.resolveLidToPhone", async () => {
    const store = new InMemoryMessageContextStore();
    const message = makeDirectLidMessage();
    const resolveLidToPhone = vi.fn(async (lid: string) => {
      if (lid === "138654580269171") return "+6281312415572";
      return null;
    });
    const resolveClientId = vi.fn(async () => 42);
    const resolvePracticeId = vi.fn(async () => 99);

    await persistCapturedMessage(message, {
      store,
      resolveClientId,
      resolvePracticeId,
      resolveLidToPhone,
    });

    expect(resolveLidToPhone).toHaveBeenCalledWith("138654580269171");
    expect(resolveClientId).toHaveBeenCalledWith("+6281312415572");
    expect(store.rows).toHaveLength(1);
    expect(store.rows[0]).toMatchObject({
      counterpartPhone: "+6281312415572",
      counterpartLid: "138654580269171",
      clientId: 42,
      practiceId: 99,
    });
  });

  it("falls back to empty phone when resolver returns null (cache miss)", async () => {
    const store = new InMemoryMessageContextStore();
    const message = makeDirectLidMessage({ counterpartLid: "unknown_lid" });
    const resolveLidToPhone = vi.fn(async () => null);
    const resolveClientId = vi.fn(async () => null);

    await persistCapturedMessage(message, {
      store,
      resolveClientId,
      resolvePracticeId: async () => null,
      resolveLidToPhone,
    });

    expect(resolveLidToPhone).toHaveBeenCalledWith("unknown_lid");
    expect(resolveClientId).not.toHaveBeenCalled();
    expect(store.rows[0].counterpartPhone).toBe("");
    expect(store.rows[0].counterpartLid).toBe("unknown_lid");
    expect(store.rows[0].clientId).toBeNull();
  });
});
