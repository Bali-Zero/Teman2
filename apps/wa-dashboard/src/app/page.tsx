"use client";

import { useWaSse } from "@/hooks/use-wa-sse";
import { InboxStream } from "@/components/InboxStream";
import { StreamStatus } from "@/components/StreamStatus";
import { useInboxStore } from "@/lib/store";

export default function HomePage() {
  useWaSse();
  const messageCount = useInboxStore((s) => s.messages.length);

  return (
    <main className="h-screen flex flex-col bg-neutral-950">
      <header className="border-b border-neutral-800 px-6 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-neutral-100">
            Bali Zero — Team WA Inbox
          </h1>
          <p className="text-xs text-neutral-500">
            Local read-only mirror · M1 · {messageCount} message
            {messageCount === 1 ? "" : "s"}
          </p>
        </div>
        <StreamStatus />
      </header>
      <InboxStream />
    </main>
  );
}
