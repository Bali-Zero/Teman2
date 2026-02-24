import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChatMessages } from "@/hooks/useChatMessages";

describe("useChatMessages", () => {
  it("starts with empty messages", () => {
    const { result } = renderHook(() => useChatMessages());
    expect(result.current.messages).toHaveLength(0);
  });

  it("adds a user message", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.addUserMessage("Hello");
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("Hello");
  });

  it("adds an assistant placeholder", () => {
    const { result } = renderHook(() => useChatMessages());

    let id: string;
    act(() => {
      id = result.current.addAssistantPlaceholder();
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("assistant");
    expect(result.current.messages[0].content).toBe("");
    expect(result.current.messages[0].isStreaming).toBe(true);
  });

  it("finalizes an assistant message", () => {
    const { result } = renderHook(() => useChatMessages());

    let id: string;
    act(() => {
      id = result.current.addAssistantPlaceholder();
    });

    act(() => {
      result.current.finalizeAssistant(id!, "Final answer", [
        { title: "Source 1" },
      ]);
    });

    expect(result.current.messages[0].content).toBe("Final answer");
    expect(result.current.messages[0].isStreaming).toBe(false);
    expect(result.current.messages[0].sources).toHaveLength(1);
  });

  it("updates assistant node", () => {
    const { result } = renderHook(() => useChatMessages());

    let id: string;
    act(() => {
      id = result.current.addAssistantPlaceholder();
    });

    act(() => {
      result.current.updateAssistantNode(id!, "retrieve");
    });

    expect(result.current.messages[0].currentNode).toBe("retrieve");
  });

  it("clears all messages", () => {
    const { result } = renderHook(() => useChatMessages());

    act(() => {
      result.current.addUserMessage("Hello");
      result.current.addAssistantPlaceholder();
    });

    expect(result.current.messages).toHaveLength(2);

    act(() => {
      result.current.clearMessages();
    });

    expect(result.current.messages).toHaveLength(0);
  });

  it("returns unique message IDs", () => {
    const { result } = renderHook(() => useChatMessages());

    let id1: string, id2: string;
    act(() => {
      id1 = result.current.addUserMessage("First");
      id2 = result.current.addUserMessage("Second");
    });

    expect(id1!).not.toBe(id2!);
  });
});
