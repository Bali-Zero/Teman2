import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import {
  useKeyboardShortcuts,
  formatShortcut,
  COMMON_SHORTCUTS,
} from "./useKeyboardShortcuts";

function fireKeyDown(
  key: string,
  opts: {
    ctrlKey?: boolean;
    metaKey?: boolean;
    shiftKey?: boolean;
    altKey?: boolean;
    target?: HTMLElement;
  } = {},
) {
  const event = new KeyboardEvent("keydown", {
    key,
    ctrlKey: opts.ctrlKey ?? false,
    metaKey: opts.metaKey ?? false,
    shiftKey: opts.shiftKey ?? false,
    altKey: opts.altKey ?? false,
    bubbles: true,
    cancelable: true,
  });
  // Assign target if needed
  if (opts.target) {
    Object.defineProperty(event, "target", { value: opts.target });
  }
  window.dispatchEvent(event);
}

describe("useKeyboardShortcuts", () => {
  it("fires action when matching key is pressed", () => {
    const action = vi.fn();
    renderHook(() =>
      useKeyboardShortcuts({
        shortcuts: [{ key: "Escape", action, description: "Close" }],
      }),
    );

    fireKeyDown("Escape");
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("does not fire when a non-matching key is pressed", () => {
    const action = vi.fn();
    renderHook(() =>
      useKeyboardShortcuts({
        shortcuts: [{ key: "Escape", action, description: "Close" }],
      }),
    );

    fireKeyDown("Enter");
    expect(action).not.toHaveBeenCalled();
  });

  it("supports modifier keys (metaKey/ctrlKey)", () => {
    const action = vi.fn();
    renderHook(() =>
      useKeyboardShortcuts({
        shortcuts: [
          { key: "k", metaKey: true, action, description: "Open search" },
        ],
      }),
    );

    // Without meta - should not fire
    fireKeyDown("k");
    expect(action).not.toHaveBeenCalled();

    // With meta - should fire
    fireKeyDown("k", { metaKey: true });
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("does not fire when hook is disabled", () => {
    const action = vi.fn();
    renderHook(() =>
      useKeyboardShortcuts({
        shortcuts: [{ key: "Escape", action, description: "Close" }],
        enabled: false,
      }),
    );

    fireKeyDown("Escape");
    expect(action).not.toHaveBeenCalled();
  });

  it("does not fire for disabled individual shortcuts", () => {
    const action = vi.fn();
    renderHook(() =>
      useKeyboardShortcuts({
        shortcuts: [
          { key: "Escape", action, description: "Close", enabled: false },
        ],
      }),
    );

    fireKeyDown("Escape");
    expect(action).not.toHaveBeenCalled();
  });

  it("filters disabled shortcuts from returned list", () => {
    const action = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardShortcuts({
        shortcuts: [
          { key: "Escape", action, description: "Close" },
          { key: "Enter", action, description: "Send", enabled: false },
          { key: "k", metaKey: true, action, description: "Search" },
        ],
      }),
    );

    expect(result.current.shortcuts).toHaveLength(2);
    expect(result.current.shortcuts.map((s) => s.key)).toEqual([
      "Escape",
      "k",
    ]);
  });

  it("cleans up event listener on unmount", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const action = vi.fn();
    const { unmount } = renderHook(() =>
      useKeyboardShortcuts({
        shortcuts: [{ key: "Escape", action, description: "Close" }],
      }),
    );

    unmount();
    expect(removeSpy).toHaveBeenCalledWith("keydown", expect.any(Function));
    removeSpy.mockRestore();
  });
});

describe("formatShortcut", () => {
  let originalPlatform: PropertyDescriptor | undefined;

  beforeEach(() => {
    originalPlatform = Object.getOwnPropertyDescriptor(navigator, "platform");
  });

  afterEach(() => {
    if (originalPlatform) {
      Object.defineProperty(navigator, "platform", originalPlatform);
    }
  });

  it("formats simple key", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Win32",
      configurable: true,
    });
    const result = formatShortcut({
      key: "Escape",
      action: vi.fn(),
      description: "Close",
    });
    expect(result).toBe("Esc");
  });

  it("formats meta+key on Mac", () => {
    Object.defineProperty(navigator, "platform", {
      value: "MacIntel",
      configurable: true,
    });
    const result = formatShortcut({
      key: "k",
      metaKey: true,
      action: vi.fn(),
      description: "Search",
    });
    // Mac uses the command symbol joined without separator
    expect(result).toContain("K");
  });

  it("formats Ctrl+key on Windows", () => {
    Object.defineProperty(navigator, "platform", {
      value: "Win32",
      configurable: true,
    });
    const result = formatShortcut({
      key: "k",
      ctrlKey: true,
      action: vi.fn(),
      description: "Search",
    });
    expect(result).toBe("Ctrl+K");
  });

  it("formats Enter as arrow symbol", () => {
    const result = formatShortcut({
      key: "Enter",
      action: vi.fn(),
      description: "Submit",
    });
    expect(result).toContain("\u21B5");
  });
});

describe("COMMON_SHORTCUTS", () => {
  it("defines expected shortcut presets", () => {
    expect(COMMON_SHORTCUTS.SEARCH.key).toBe("k");
    expect(COMMON_SHORTCUTS.CLOSE.key).toBe("Escape");
    expect(COMMON_SHORTCUTS.SEND.key).toBe("Enter");
    expect(COMMON_SHORTCUTS.NEW_CHAT.key).toBe("n");
  });
});
