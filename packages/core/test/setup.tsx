import React from "react";
import "@testing-library/jest-dom";
import { vi } from "vitest";

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

vi.mock("next/font/google", () => ({
  Inter: () => ({
    className: "mock-inter",
    variable: "--font-inter",
    style: { fontFamily: "Inter" },
  }),
  Cormorant_Garamond: () => ({
    className: "mock-cormorant",
    variable: "--font-cormorant",
    style: { fontFamily: "Cormorant Garamond" },
  }),
}));

vi.mock("next/image", () => ({
  default: ({
    src,
    alt,
    priority: _priority,
    fill: _fill,
    unoptimized: _unoptimized,
    width: _width,
    height: _height,
    ...props
  }: {
    src: string;
    alt: string;
    priority?: boolean;
    fill?: boolean;
    unoptimized?: boolean;
    width?: number;
    height?: number;
    [key: string]: unknown;
  }) => <img src={src} alt={alt} {...props} />,
}));

class LocalStorageMock implements Storage {
  private readonly store = new Map<string, string>();

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
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

Object.defineProperty(window, "localStorage", {
  value: new LocalStorageMock(),
  writable: true,
  configurable: true,
});

globalThis.fetch = vi.fn();

Object.defineProperty(navigator, "clipboard", {
  value: { writeText: vi.fn().mockResolvedValue(undefined) },
  writable: true,
  configurable: true,
});

window.confirm = vi.fn(() => true);
Element.prototype.scrollIntoView = vi.fn();
