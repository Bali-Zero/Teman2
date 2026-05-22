"use client";

import { useInboxStore } from "@/lib/store";
import { Virtuoso } from "react-virtuoso";
import { MessageRow } from "./MessageRow";

export function InboxStream() {
  const messages = useInboxStore((s) => s.messages);
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-neutral-500 text-sm">
        Waiting for live messages...
      </div>
    );
  }
  return (
    <Virtuoso
      data={messages}
      itemContent={(_, message) => <MessageRow message={message} />}
      followOutput="smooth"
      atBottomThreshold={120}
      className="flex-1"
    />
  );
}
