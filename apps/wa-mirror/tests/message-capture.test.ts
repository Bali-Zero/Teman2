import { describe, expect, it } from "vitest";

import {
  InMemoryMessageContextStore,
  extractMessageRecord,
  persistCapturedMessage,
} from "../bridge/message_capture.js";

const account = {
  phone: "+628213107363",
  name: "Adit",
};

describe("message capture persistence", () => {
  it("upserts the same baileys_message_id only once", async () => {
    const store = new InMemoryMessageContextStore();
    const message = {
      baileysMessageId: "wamid-1",
      direction: "inbound" as const,
      teamMemberPhone: account.phone,
      counterpartPhone: "+6281234567890",
      body: "hello",
      timestamp: new Date("2026-05-16T00:00:00.000Z"),
      mediaType: "text" as const,
      mediaMime: null,
      mediaUrl: null,
      rawBaileysEvent: { key: { id: "wamid-1" } },
    };

    await persistCapturedMessage(message, {
      store,
      resolveClientId: async () => 42,
      resolvePracticeId: async () => 88,
    });
    await persistCapturedMessage(message, {
      store,
      resolveClientId: async () => 42,
      resolvePracticeId: async () => 88,
    });

    expect(store.rows).toHaveLength(1);
    expect(store.rows[0]).toMatchObject({
      baileysMessageId: "wamid-1",
      clientId: 42,
      practiceId: 88,
      body: "hello",
    });
  });

  it("stores prospects with client_id NULL instead of dropping them", async () => {
    const store = new InMemoryMessageContextStore();
    const message = {
      baileysMessageId: "prospect-1",
      direction: "inbound" as const,
      teamMemberPhone: account.phone,
      counterpartPhone: "+6289876543210",
      body: "Can you help with a visa?",
      timestamp: new Date("2026-05-16T00:01:00.000Z"),
      mediaType: "text" as const,
      mediaMime: null,
      mediaUrl: null,
      rawBaileysEvent: { key: { id: "prospect-1" } },
    };

    await persistCapturedMessage(message, {
      store,
      resolveClientId: async () => null,
      resolvePracticeId: async () => null,
    });

    expect(store.rows).toHaveLength(1);
    expect(store.rows[0]).toMatchObject({
      clientId: null,
      practiceId: null,
      counterpartPhone: "+6289876543210",
      body: "Can you help with a visa?",
    });
  });
});

describe("extractMessageRecord", () => {
  it("extracts media metadata and keeps media-only body empty", () => {
    const record = extractMessageRecord(
      {
        key: {
          id: "image-1",
          fromMe: false,
          remoteJid: "6281234567890@s.whatsapp.net",
        },
        messageTimestamp: 1_779_000_000,
        message: {
          imageMessage: {
            mimetype: "image/jpeg",
            url: "https://mmg.whatsapp.net/example",
          },
        },
      },
      account
    );

    expect(record).toMatchObject({
      baileysMessageId: "image-1",
      direction: "inbound",
      teamMemberPhone: "+628213107363",
      counterpartPhone: "+6281234567890",
      body: "",
      mediaType: "image",
      mediaMime: "image/jpeg",
      mediaUrl: "https://mmg.whatsapp.net/example",
    });
  });
});
