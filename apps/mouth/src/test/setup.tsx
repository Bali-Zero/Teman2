import React from "react";
import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock Next.js router
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock Next.js font loader (next/font/google)
// Required by @balizero/core barrel which re-exports fonts/inter.ts
vi.mock("next/font/google", () => ({
  Inter: () => ({
    className: "mock-inter",
    variable: "--font-inter",
    style: { fontFamily: "Inter" },
  }),
  Montserrat: () => ({
    className: "mock-montserrat",
    variable: "--font-montserrat",
    style: { fontFamily: "Montserrat" },
  }),
}));

// Mock Next.js Image component
vi.mock("next/image", () => ({
  default: ({
    src,
    alt,
    priority: _priority,
    fill: _fill,
    unoptimized: _unoptimized,
    ...props
  }: {
    src: string;
    alt: string;
    priority?: boolean;
    fill?: boolean;
    unoptimized?: boolean;
    [key: string]: unknown;
  }) => {
    // Filter out Next.js-specific props that shouldn't be passed to img
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { width: _width, height: _height, ...imgProps } = props as any;

    return <img src={src} alt={alt} {...imgProps} />;
  },
}));

// Create a working localStorage mock that actually stores values
// This is needed because jsdom's localStorage may not work correctly in all vitest scenarios
class LocalStorageMock implements Storage {
  private store: Map<string, string> = new Map();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  key(index: number): string | null {
    const keys = Array.from(this.store.keys());
    return keys[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

const localStorageMock = new LocalStorageMock();
Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  writable: true,
  configurable: true,
});

// Mock fetch
global.fetch = vi.fn();

// Mock clipboard
const clipboardMock = {
  writeText: vi.fn().mockResolvedValue(undefined),
};
Object.defineProperty(navigator, "clipboard", {
  value: clipboardMock,
  writable: true,
  configurable: true,
});

// Mock confirm
window.confirm = vi.fn(() => true);

// Mock scrollIntoView (not available in JSDOM)
Element.prototype.scrollIntoView = vi.fn();
