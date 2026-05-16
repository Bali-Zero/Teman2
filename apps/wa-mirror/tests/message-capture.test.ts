import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  InMemoryMessageContextStore,
  PgMessageContextStore,
  extractMessageRecord,
  persistCapturedMessage,
} from "../bridge/message_capture.js";
import { query } from "../bridge/pg.js";

vi.mock("../bridge/pg.js", () => ({
  query: vi.fn(),
}));

const account = {
  phone: "+628213107363",
  name: "Adit",
};

describe("message capture persistence", () => {
  beforeEach(() => {
    vi.mocked(query).mockReset();
  });

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

  it("persists via live wa-mirror columns without the legacy phone_number column", async () => {
    vi.mocked(query).mockResolvedValueOnce({
      rowCount: 1,
      rows: [{ id: 7 }],
    } as never);

    const store = new PgMessageContextStore();
    await store.upsertMessage({
      baileysMessageId: "wamid-live-schema",
      direction: "inbound",
      teamMemberPhone: account.phone,
      counterpartPhone: "+6289876543210",
      body: "hello from live schema",
      timestamp: new Date("2026-05-16T00:02:00.000Z"),
      mediaType: "text",
      mediaMime: null,
      mediaUrl: null,
      rawBaileysEvent: { key: { id: "wamid-live-schema" } },
      clientId: null,
      practiceId: null,
    });

    const sql = vi.mocked(query).mock.calls[0][0];
    expect(sql).toContain("counterpart_phone");
    expect(sql).not.toContain("phone_number");
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
      account,
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
