import { create } from "zustand";
import type { WaMessage, SseStreamState } from "@/types/wa-message";

interface InboxStore {
  messages: WaMessage[];
  stream: SseStreamState;
  pushMessage: (m: WaMessage) => void;
  pushBatch: (batch: WaMessage[]) => void;
  setStreamStatus: (status: SseStreamState["status"]) => void;
  setLastEventId: (id: number) => void;
  incrementError: () => void;
  clear: () => void;
}

const MAX_BUFFER = 1000;

export const useInboxStore = create<InboxStore>((set) => ({
  messages: [],
  stream: { status: "idle", lastEventId: 0, errorCount: 0 },
  pushMessage: (m) =>
    set((s) => ({
      messages: [...s.messages.slice(-(MAX_BUFFER - 1)), m],
      stream: {
        ...s.stream,
        lastEventId: Math.max(s.stream.lastEventId, m.id),
      },
    })),
  pushBatch: (batch) =>
    set((s) => {
      const next = [...s.messages, ...batch].slice(-MAX_BUFFER);
      const maxId = batch.reduce(
        (acc, m) => Math.max(acc, m.id),
        s.stream.lastEventId,
      );
      return { messages: next, stream: { ...s.stream, lastEventId: maxId } };
    }),
  setStreamStatus: (status) =>
    set((s) => ({ stream: { ...s.stream, status } })),
  setLastEventId: (id) =>
    set((s) => ({
      stream: { ...s.stream, lastEventId: Math.max(s.stream.lastEventId, id) },
    })),
  incrementError: () =>
    set((s) => ({
      stream: { ...s.stream, errorCount: s.stream.errorCount + 1 },
    })),
  clear: () =>
    set({
      messages: [],
      stream: { status: "idle", lastEventId: 0, errorCount: 0 },
    }),
}));
