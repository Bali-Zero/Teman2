/**
 * Chat page — purely presentational, all logic in useChatPage.
 */

"use client";

import { ChatLayout } from "@/components/templates/ChatLayout";
import { ChatPanel } from "@/components/organisms/ChatPanel";
import { useChatPage } from "@/hooks/useChatPage";

export default function ChatPage() {
  const {
    messages,
    currentNode,
    isLoading,
    error,
    handleSend,
    handleAbort,
    handleNewChat,
  } = useChatPage();

  return (
    <ChatLayout onNewChat={handleNewChat}>
      <ChatPanel
        messages={messages}
        currentNode={currentNode}
        isLoading={isLoading}
        error={error}
        onSend={handleSend}
        onAbort={handleAbort}
      />
    </ChatLayout>
  );
}
