import { beforeEach, describe, expect, it } from "vitest";

import { useInboxStore } from "./store";
import type { WaMessage } from "@/types/wa-message";

function message(id: number): WaMessage {
  return {
    id,
    direction: "incoming",
    team_member_phone: null,
    counterpart_phone: `counterpart-${id}`,
    chat_type: "dm",
    group_jid: null,
    body: `message-${id}`,
    message_date: "2026-07-18T00:00:00Z",
    media_type: null,
    attention_priority: null,
    client_id: null,
    practice_id: null,
  };
}

describe("useInboxStore", () => {
  beforeEach(() => {
    useInboxStore.getState().clear();
  });

  it("appends messages and advances the replay cursor", () => {
    useInboxStore.getState().pushMessage(message(12));
    useInboxStore.getState().pushMessage(message(13));

    const state = useInboxStore.getState();
    expect(state.messages.map(({ id }) => id)).toEqual([12, 13]);
    expect(state.stream.lastEventId).toBe(13);
  });

  it("never moves the replay cursor backwards for an older event", () => {
    useInboxStore.getState().setLastEventId(50);
    useInboxStore.getState().pushMessage(message(49));
    useInboxStore.getState().setLastEventId(10);

    expect(useInboxStore.getState().stream.lastEventId).toBe(50);
  });

  it("keeps only the newest 1000 messages", () => {
    useInboxStore
      .getState()
      .pushBatch(
        Array.from({ length: 1_005 }, (_, index) => message(index + 1)),
      );

    const state = useInboxStore.getState();
    expect(state.messages).toHaveLength(1_000);
    expect(state.messages[0]?.id).toBe(6);
    expect(state.messages.at(-1)?.id).toBe(1_005);
    expect(state.stream.lastEventId).toBe(1_005);
  });

  it("preserves batch order and uses its greatest event id", () => {
    useInboxStore.getState().pushMessage(message(40));
    useInboxStore.getState().pushBatch([message(43), message(41), message(42)]);

    const state = useInboxStore.getState();
    expect(state.messages.map(({ id }) => id)).toEqual([40, 43, 41, 42]);
    expect(state.stream.lastEventId).toBe(43);
  });

  it("leaves messages and cursor unchanged for an empty batch", () => {
    useInboxStore.getState().pushMessage(message(7));
    useInboxStore.getState().pushBatch([]);

    const state = useInboxStore.getState();
    expect(state.messages.map(({ id }) => id)).toEqual([7]);
    expect(state.stream.lastEventId).toBe(7);
  });

  it("tracks connection state and cumulative stream errors", () => {
    useInboxStore.getState().setStreamStatus("connecting");
    useInboxStore.getState().setStreamStatus("error");
    useInboxStore.getState().incrementError();
    useInboxStore.getState().incrementError();

    expect(useInboxStore.getState().stream).toEqual({
      status: "error",
      lastEventId: 0,
      errorCount: 2,
    });
  });

  it("clear restores the complete initial state", () => {
    useInboxStore.getState().pushMessage(message(99));
    useInboxStore.getState().setStreamStatus("open");
    useInboxStore.getState().incrementError();

    useInboxStore.getState().clear();

    expect(useInboxStore.getState().messages).toEqual([]);
    expect(useInboxStore.getState().stream).toEqual({
      status: "idle",
      lastEventId: 0,
      errorCount: 0,
    });
  });
});
