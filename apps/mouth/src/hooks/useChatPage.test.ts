import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const sonnerToast = Object.assign(vi.fn(), { dismiss: vi.fn() });

  return {
    router: { push: vi.fn() },
    api: {
      // Pre-cure production code still calls this directly (class-audit
      // gate #10/#11, not yet migrated at RED time) — fixed `true` and
      // never the thing a test asserts against, so it stays harmless
      // straight through the GREEN cutover. See `sessionState` below for
      // the value that actually drives the gate post-cure.
      isAuthenticated: vi.fn().mockReturnValue(true),
      getUserProfile: vi.fn(),
      getProfile: vi.fn(),
      getConversation: vi.fn(),
    },
    // Drives the mocked `useSessionState()` below. Auth here is
    // cookie-PRIMARY (client.ts docstring): the gate now asks the session
    // probe, not a local-token-only `api.isAuthenticated()`.
    sessionState: "authenticated" as
      "pending" | "authenticated" | "anonymous" | "unknown",
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
    // Both hooks below call authenticated-only endpoints; these capture what
    // `useChatPage` allows them to do, so an anonymous visitor firing a 401 is
    // caught here rather than in production. See the comment at the gate.
    snapshotOptions: null as Record<string, unknown> | null,
    conversationsArgs: null as unknown[] | null,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
}));

vi.mock("uuid", () => ({
  v4: () => "uuid-fixed",
}));

vi.mock("@/lib/api", async () => {
  const { ApiError } = await vi.importActual<
    typeof import("@/lib/api/error-handler")
  >("@/lib/api/error-handler");
  return { ApiError, api: mocks.api };
});
vi.mock("./useSessionState", () => ({
  useSessionState: () => mocks.sessionState,
}));
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
  useConversations: (...args: unknown[]) => {
    mocks.conversationsArgs = args;
    return mocks.conversations;
  },
}));
vi.mock("./useTeamStatus", () => ({
  useTeamStatus: () => mocks.teamStatus,
}));
vi.mock("./useConversationPersistence", () => ({
  useConversationPersistence: () => mocks.persistence,
}));
vi.mock("./useChatSnapshot", () => ({
  useChatSnapshot: (options: Record<string, unknown>) => {
    mocks.snapshotOptions = options;
    return mocks.snapshot;
  },
}));
vi.mock("./useChatSend", () => ({
  useChatSend: (options: Record<string, unknown>) => {
    mocks.chatSendOptions = options;
    return mocks.chatSend;
  },
}));

import { ApiError } from "@/lib/api";
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
  mocks.sessionState = "authenticated";
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
  mocks.snapshotOptions = null;
  mocks.conversationsArgs = null;
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
    mocks.sessionState = "anonymous";

    renderHook(() => useChatPage());

    await waitFor(() => {
      expect(mocks.router.push).toHaveBeenCalledWith("/login");
    });
    expect(mocks.conversations.loadConversationList).not.toHaveBeenCalled();
    expect(mocks.teamStatus.loadClockStatus).not.toHaveBeenCalled();

    // The two assertions above only cover the MANUAL refetch inside
    // `loadInitialData`. The data hooks fetch on their own — a React Query
    // mount fetch and an effect — and neither consults the auth check that
    // produced the redirect above. Measured live on 2026-08-27: every
    // anonymous pageview of the public `/chat` collected a 401 from
    // `conversations/list` AND `conversations/history`, and the caught history
    // error went to Sentry (logger.warn forwards unconditionally in prod),
    // which answered 429 — dropping events. So this test's own promise,
    // "without loading private chat data", needs these two lines to be true.
    expect(mocks.snapshotOptions?.enabled).toBe(false);
    expect(mocks.conversationsArgs?.[0]).toBe(false);
  });

  it("lets an authenticated visitor load private chat data", async () => {
    // Innocence half of the pair above: the gate must not cost a logged-in
    // user their sidebar and history. If this goes red, the fix has broken
    // the very thing `/chat` exists to do.
    mocks.sessionState = "authenticated";

    renderHook(() => useChatPage());

    await waitFor(() => {
      expect(mocks.snapshotOptions).not.toBeNull();
    });
    expect(mocks.snapshotOptions?.enabled).toBe(true);
    expect(mocks.conversationsArgs?.[0]).toBe(true);
    expect(mocks.router.push).not.toHaveBeenCalledWith("/login");
  });

  it("does not load or redirect while the session is still pending", async () => {
    mocks.sessionState = "pending";

    renderHook(() => useChatPage());

    await waitFor(() => {
      expect(mocks.snapshotOptions).not.toBeNull();
    });
    expect(mocks.snapshotOptions?.enabled).toBe(false);
    expect(mocks.conversationsArgs?.[0]).toBe(false);
    expect(mocks.conversations.loadConversationList).not.toHaveBeenCalled();
    expect(mocks.router.push).not.toHaveBeenCalledWith("/login");
  });

  it("does not load or redirect when the session probe is inconclusive (unknown)", async () => {
    mocks.sessionState = "unknown";

    renderHook(() => useChatPage());

    await waitFor(() => {
      expect(mocks.snapshotOptions).not.toBeNull();
    });
    expect(mocks.snapshotOptions?.enabled).toBe(false);
    expect(mocks.conversationsArgs?.[0]).toBe(false);
    expect(mocks.conversations.loadConversationList).not.toHaveBeenCalled();
    expect(mocks.router.push).not.toHaveBeenCalledWith("/login");
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

  describe("profile-load classification (auth-gates-cookie-primary round 2)", () => {
    beforeEach(() => {
      // Force the fallback path: no cached profile, so getProfile() is awaited.
      mocks.api.getUserProfile.mockReturnValue(null);
    });

    it("calls getProfile with redirectOnUnauthorized: false — the session gate above decides the redirect, not getProfile's own 401 handler", async () => {
      mocks.api.getProfile.mockRejectedValue(
        new ApiError("Authentication required", 401),
      );

      renderHook(() => useChatPage());

      await waitFor(() => {
        expect(mocks.api.getProfile).toHaveBeenCalledWith({
          redirectOnUnauthorized: false,
        });
      });
    });

    it("classifies an anonymous/cookie-only profile load (401) at debug, never at error", async () => {
      mocks.api.getProfile.mockRejectedValue(
        new ApiError("Authentication required", 401),
      );

      renderHook(() => useChatPage());

      await waitFor(() => {
        expect(mocks.logger.debug).toHaveBeenCalled();
      });
      expect(mocks.logger.error).not.toHaveBeenCalledWith(
        "Failed to load user profile",
        expect.anything(),
        expect.anything(),
      );
    });

    it("still logs a genuine profile-load failure at error", async () => {
      mocks.api.getProfile.mockRejectedValue(
        new ApiError("Server exploded", 500),
      );

      renderHook(() => useChatPage());

      await waitFor(() => {
        expect(mocks.logger.error).toHaveBeenCalledWith(
          "Failed to load user profile",
          expect.objectContaining({ component: "useChatPage" }),
          expect.anything(),
        );
      });
    });
  });
});
