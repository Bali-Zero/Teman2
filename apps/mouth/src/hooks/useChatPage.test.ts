import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const sonnerToast = Object.assign(vi.fn(), { dismiss: vi.fn() });

  return {
    router: { push: vi.fn() },
    api: {
      isAuthenticated: vi.fn(),
      getUserProfile: vi.fn(),
      getProfile: vi.fn(),
      getConversation: vi.fn(),
    },
    sonnerToast,
    logger: {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    },
    chatMetrics: {
      conversationLoaded: vi.fn(),
    },
    trackEvent: vi.fn(),
    saveConversation: vi.fn(),
    chatInput: {
      input: "",
      setInput: vi.fn(),
      attachedImages: [] as Array<{
        id: string;
        base64: string;
        name: string;
        size: number;
      }>,
      setAttachedImages: vi.fn(),
      imageGenPrompt: "",
      setImageGenPrompt: vi.fn(),
      setShowToast: vi.fn(),
    },
    sidebar: {
      closeSidebar: vi.fn(),
    },
    conversations: {
      currentConversationId: null as number | null,
      setCurrentConversationId: vi.fn(),
      loadConversationList: vi.fn(),
      deleteConversation: vi.fn(),
    },
    teamStatus: {
      loadClockStatus: vi.fn(),
      toggleClock: vi.fn(),
    },
    persistence: {
      sessionId: "session-existing",
      setSessionId: vi.fn(),
      isLoading: false,
    },
    snapshot: {
      snapshot: null as Array<Record<string, unknown>> | null,
      isRevalidating: false,
      save: vi.fn(),
      clear: vi.fn(),
    },
    chatSend: {
      isStreaming: false,
      sendMessage: vi.fn(),
      abortStream: vi.fn(),
    },
    chatSendOptions: null as Record<string, unknown> | null,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
}));

vi.mock("uuid", () => ({
  v4: () => "uuid-fixed",
}));

vi.mock("@/lib/api", () => ({ api: mocks.api }));
vi.mock("sonner", () => ({ toast: mocks.sonnerToast }));
vi.mock("@/lib/logger", () => ({ logger: mocks.logger }));
vi.mock("@/lib/metrics", () => ({ chatMetrics: mocks.chatMetrics }));
vi.mock("@/lib/analytics", () => ({ trackEvent: mocks.trackEvent }));
vi.mock("@/app/chat/actions", () => ({
  saveConversation: mocks.saveConversation,
}));

vi.mock("./useChatInput", () => ({
  useChatInput: () => mocks.chatInput,
}));
vi.mock("./useChatSidebar", () => ({
  useChatSidebar: () => mocks.sidebar,
}));
vi.mock("./useConversations", () => ({
  useConversations: () => mocks.conversations,
}));
vi.mock("./useTeamStatus", () => ({
  useTeamStatus: () => mocks.teamStatus,
}));
vi.mock("./useConversationPersistence", () => ({
  useConversationPersistence: () => mocks.persistence,
}));
vi.mock("./useChatSnapshot", () => ({
  useChatSnapshot: () => mocks.snapshot,
}));
vi.mock("./useChatSend", () => ({
  useChatSend: (options: Record<string, unknown>) => {
    mocks.chatSendOptions = options;
    return mocks.chatSend;
  },
}));

import { useChatPage } from "./useChatPage";

function getSendCallback<T extends (...args: never[]) => unknown>(
  name: string,
): T {
  if (!mocks.chatSendOptions) {
    throw new Error("useChatSend was not initialized");
  }
  return mocks.chatSendOptions[name] as T;
}

async function renderChatPage() {
  const rendered = renderHook(() => useChatPage());
  await waitFor(() => {
    expect(mocks.conversations.loadConversationList).toHaveBeenCalledOnce();
  });
  return rendered;
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mocks.api.isAuthenticated.mockReturnValue(true);
  mocks.api.getUserProfile.mockReturnValue({
    email: "operator@example.test",
    name: "Operator",
  });
  mocks.api.getProfile.mockResolvedValue(null);
  mocks.api.getConversation.mockResolvedValue(null);
  mocks.saveConversation.mockResolvedValue(undefined);
  mocks.conversations.loadConversationList.mockResolvedValue(undefined);
  mocks.conversations.deleteConversation.mockResolvedValue(undefined);
  mocks.teamStatus.loadClockStatus.mockResolvedValue(undefined);
  mocks.teamStatus.toggleClock.mockResolvedValue(undefined);
  mocks.chatSend.sendMessage.mockResolvedValue(undefined);

  mocks.chatInput.input = "";
  mocks.chatInput.attachedImages = [];
  mocks.chatInput.imageGenPrompt = "";
  mocks.conversations.currentConversationId = null;
  mocks.persistence.sessionId = "session-existing";
  mocks.persistence.isLoading = false;
  mocks.snapshot.snapshot = null;
  mocks.snapshot.isRevalidating = false;
  mocks.chatSend.isStreaming = false;
  mocks.chatSendOptions = null;
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: 1024,
  });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useChatPage", () => {
  it("redirects unauthenticated users without loading private chat data", async () => {
    mocks.api.isAuthenticated.mockReturnValue(false);

    renderHook(() => useChatPage());

    await waitFor(() => {
      expect(mocks.router.push).toHaveBeenCalledWith("/login");
    });
    expect(mocks.conversations.loadConversationList).not.toHaveBeenCalled();
    expect(mocks.teamStatus.loadClockStatus).not.toHaveBeenCalled();
  });

  it("guards empty sends and sends a trimmed message with optimistic state", async () => {
    const { result, rerender } = await renderChatPage();

    await act(async () => {
      await result.current.handleSend();
    });
    expect(mocks.chatSend.sendMessage).not.toHaveBeenCalled();

    const image = {
      id: "image-1",
      base64: "data:image/png;base64,abc",
      name: "proof.png",
      size: 3,
    };
    mocks.chatInput.input = "  explain this  ";
    mocks.chatInput.attachedImages = [image];
    rerender();

    await act(async () => {
      await result.current.handleSend();
    });

    expect(mocks.chatSend.sendMessage).toHaveBeenCalledWith("explain this", [
      image,
    ]);
    expect(mocks.chatInput.setInput).toHaveBeenCalledWith("");
    expect(mocks.chatInput.setAttachedImages).toHaveBeenCalledWith([]);
    expect(mocks.chatInput.setImageGenPrompt).toHaveBeenCalledWith("");
    expect(result.current.messages).toMatchObject([
      { role: "user", content: "explain this", isPending: false },
      { role: "assistant", content: "", isStreaming: true },
    ]);
    expect(mocks.snapshot.save).not.toHaveBeenCalled();
  });

  it("does not send while a stream is already active", async () => {
    mocks.chatInput.input = "duplicate";
    mocks.chatSend.isStreaming = true;
    const { result } = await renderChatPage();

    await act(async () => {
      await result.current.handleSend();
    });

    expect(mocks.chatSend.sendMessage).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
    expect(result.current.isPending).toBe(true);
  });

  it("hydrates a final snapshot and persists it after the turn is closed", async () => {
    mocks.snapshot.snapshot = [
      {
        id: "cached-1",
        role: "assistant",
        content: "Cached answer",
        timestamp: new Date("2026-01-01T00:00:00Z"),
      },
    ];

    const { result } = await renderChatPage();

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(1);
    });
    expect(result.current.messages[0]).toMatchObject({
      id: "cached-1",
      content: "Cached answer",
      isPending: false,
    });
    await waitFor(() => {
      expect(mocks.snapshot.save).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ id: "cached-1", content: "Cached answer" }),
        ]),
      );
    });
  });

  it("applies stream chunks, completes the assistant turn, and persists it", async () => {
    mocks.chatInput.input = "question";
    const { result } = await renderChatPage();

    await act(async () => {
      await result.current.handleSend();
    });
    mocks.snapshot.save.mockClear();

    act(() => {
      getSendCallback<(chunk: string) => void>("onChunk")("partial");
    });
    expect(
      result.current.messages[result.current.messages.length - 1],
    ).toMatchObject({
      role: "assistant",
      content: "partial",
      isStreaming: true,
    });

    const sources = [{ title: "Official source", content: "Evidence" }];
    const metadata = { model: "test-model" };
    await act(async () => {
      await getSendCallback<
        (
          response: string,
          responseSources: typeof sources,
          responseMetadata: typeof metadata,
        ) => Promise<void>
      >("onComplete")("final answer", sources, metadata);
    });

    expect(
      result.current.messages[result.current.messages.length - 1],
    ).toMatchObject({
      role: "assistant",
      content: "final answer",
      sources,
      metadata,
      isStreaming: false,
    });
    expect(mocks.saveConversation).toHaveBeenCalledWith(
      "session-existing",
      expect.arrayContaining([
        expect.objectContaining({ role: "assistant", content: "final answer" }),
      ]),
    );
    await waitFor(() => {
      expect(mocks.snapshot.save).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ content: "final answer" }),
        ]),
      );
    });
  });

  it("contains stream and persistence failures without corrupting the turn", async () => {
    mocks.chatInput.input = "question";
    mocks.saveConversation.mockRejectedValueOnce(new Error("database down"));
    const { result } = await renderChatPage();

    await act(async () => {
      await result.current.handleSend();
    });
    const streamError = new Error("stream failed");
    act(() => {
      getSendCallback<(error: Error) => void>("onError")(streamError);
    });
    await act(async () => {
      await getSendCallback<(response: string, sources: []) => Promise<void>>(
        "onComplete",
      )("fallback answer", []);
    });

    expect(mocks.logger.error).toHaveBeenCalledWith(
      "Chat error",
      { component: "useChatPage" },
      streamError,
    );
    expect(mocks.logger.error).toHaveBeenCalledWith(
      "Save error",
      {},
      expect.objectContaining({ message: "database down" }),
    );
    expect(
      result.current.messages[result.current.messages.length - 1],
    ).toMatchObject({
      content: "fallback answer",
      isStreaming: false,
    });
  });

  it("stops the active stream", async () => {
    const { result } = await renderChatPage();

    act(() => result.current.handleStop());

    expect(mocks.chatSend.abortStream).toHaveBeenCalledOnce();
    expect(mocks.logger.info).toHaveBeenCalledWith(
      "Message generation stopped by user",
      expect.objectContaining({
        action: "handleStop",
        metadata: { sessionId: "session-existing" },
      }),
    );
  });

  it("starts a new isolated session and clears local conversation state", async () => {
    mocks.snapshot.snapshot = [
      { role: "user", content: "old message", timestamp: new Date() },
    ];
    const { result } = await renderChatPage();
    await waitFor(() => expect(result.current.messages).toHaveLength(1));

    act(() => result.current.handleNewChat());

    expect(result.current.messages).toEqual([]);
    expect(mocks.persistence.setSessionId).toHaveBeenCalledWith(
      "session_uuid-fixed",
    );
    expect(mocks.snapshot.clear).toHaveBeenCalledOnce();
    expect(mocks.conversations.setCurrentConversationId).toHaveBeenCalledWith(
      null,
    );
    expect(mocks.sidebar.closeSidebar).toHaveBeenCalledOnce();
    expect(mocks.trackEvent).toHaveBeenCalledWith(
      "chat_new_conversation",
      { previousSessionId: "session-existing" },
      "operator@example.test",
    );
  });

  it("loads and normalizes a conversation, then closes the mobile sidebar", async () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 640,
    });
    mocks.api.getConversation.mockResolvedValue({
      session_id: "session-loaded",
      messages: [
        {
          id: "user-1",
          role: "user",
          content: "Hello",
          timestamp: "2026-06-01T00:00:00Z",
          sources: [{ title: "", content: "ignored" }],
        },
        { role: "tool", content: "Tool output" },
        { role: "assistant", content: 123 },
        null,
      ],
    });
    const { result } = await renderChatPage();

    await act(async () => {
      await result.current.handleConversationClick(42);
    });

    expect(mocks.conversations.setCurrentConversationId).toHaveBeenCalledWith(
      42,
    );
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({
      id: "user-1",
      role: "user",
      content: "Hello",
    });
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "Tool output",
    });
    expect(mocks.persistence.setSessionId).toHaveBeenCalledWith(
      "session-loaded",
    );
    expect(mocks.chatMetrics.conversationLoaded).toHaveBeenCalledWith(42, 4);
    expect(mocks.trackEvent).toHaveBeenCalledWith(
      "chat_conversation_loaded",
      { conversationId: 42, messageCount: 4 },
      "operator@example.test",
    );
    expect(mocks.sidebar.closeSidebar).toHaveBeenCalledOnce();
  });

  it("logs conversation-load failures and still restores mobile navigation", async () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 640,
    });
    const failure = new Error("history unavailable");
    mocks.api.getConversation.mockRejectedValue(failure);
    const { result } = await renderChatPage();

    await act(async () => {
      await result.current.handleConversationClick(77);
    });

    expect(mocks.logger.error).toHaveBeenCalledWith(
      "Failed to load conversation",
      expect.objectContaining({ metadata: { conversationId: 77 } }),
      failure,
    );
    expect(mocks.sidebar.closeSidebar).toHaveBeenCalledOnce();
  });

  it("deletes a selected conversation only after confirmation", async () => {
    mocks.conversations.currentConversationId = 9;
    const { result } = await renderChatPage();
    const stopPropagation = vi.fn();

    act(() => {
      result.current.handleDeleteConversation(9, {
        stopPropagation,
      } as never);
    });

    expect(stopPropagation).toHaveBeenCalledOnce();
    expect(mocks.conversations.deleteConversation).not.toHaveBeenCalled();
    const options = mocks.sonnerToast.mock.calls[0][1] as {
      action: { onClick: () => Promise<void> };
    };
    await act(async () => {
      await options.action.onClick();
    });

    expect(mocks.conversations.deleteConversation).toHaveBeenCalledWith(9);
    expect(mocks.trackEvent).toHaveBeenCalledWith(
      "chat_conversation_deleted",
      { conversationId: 9 },
      "operator@example.test",
    );
    expect(mocks.persistence.setSessionId).toHaveBeenCalledWith(
      "session_uuid-fixed",
    );
  });

  it("contains deletion failures and leaves the current chat in place", async () => {
    mocks.conversations.currentConversationId = 5;
    const failure = new Error("delete failed");
    mocks.conversations.deleteConversation.mockRejectedValue(failure);
    const { result } = await renderChatPage();

    act(() => {
      result.current.handleDeleteConversation(5, {
        stopPropagation: vi.fn(),
      } as never);
    });
    const options = mocks.sonnerToast.mock.calls[0][1] as {
      action: { onClick: () => Promise<void> };
    };
    await act(async () => {
      await options.action.onClick();
    });

    expect(mocks.logger.error).toHaveBeenCalledWith(
      "Failed to delete conversation",
      expect.objectContaining({ metadata: { conversationId: 5 } }),
      failure,
    );
    expect(mocks.persistence.setSessionId).not.toHaveBeenCalled();
  });

  it("marks the hook unmounted so late async callbacks can self-cancel", async () => {
    const { result, unmount } = await renderChatPage();
    const mountedRef = result.current.isMountedRef;

    expect(mountedRef.current).toBe(true);
    unmount();
    expect(mountedRef.current).toBe(false);
  });
});
