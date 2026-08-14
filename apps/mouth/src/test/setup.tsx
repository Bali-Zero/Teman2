import React from "react";
import "@testing-library/jest-dom";
import { configure } from "@testing-library/react";
import { vi } from "vitest";

// Raise testing-library's default `waitFor`/`findBy*` timeout from its 1000ms
// default. Canary investigation 2026-08-15 (PR bisecting a deterministic-on-CI,
// unreproducible-locally failure of `PortalHomePage > should render timeline
// when available`): a full local `npx vitest --run` of this suite (382 files,
// 3584 tests, IDENTICAL config to CI — pool:threads, maxThreads:2) passed
// 100% at the exact commit where CI failed this one assertion twice on two
// unrelated PRs (#4204, #4202); the component/hook/test file had zero code
// changes in the surrounding merge window (git log empty). 351 `waitFor(...)`
// call sites across 49 files in this suite, ZERO with an explicit timeout
// override — every one of them share this same implicit 1000ms margin against
// a 2-thread GH Actions runner that has never been re-measured as this suite
// grew (the exact frontend-side analogue of scripts/suite_growth_probe.py's
// backend finding). vitest's own `testTimeout: 20000` (vitest.config.ts) is
// the real ceiling for a genuinely hung/broken assertion — 5000ms here still
// distinguishes "slow under CI contention" from "actually never resolves"
// with 4x margin, and is a single choke point rather than 351 individual
// call-site edits (class fix, not instance fix).
configure({ asyncUtilTimeout: 5000 });

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
  Cormorant_Garamond: () => ({
    className: "mock-cormorant",
    variable: "--font-cormorant",
    style: { fontFamily: "Cormorant Garamond" },
  }),
}));

// Mock Next.js local font loader (next/font/local) — self-hosted fonts
// (2026-08-13, apps/mouth/packages/core/fonts/{inter,cormorant,montserrat,
// league-spartan}.ts) call `localFont(opts)` the same way `Inter(opts)` etc
// used to. Outside a real Next build there is no SWC/webpack transform to
// swap this for generated CSS, so the real package throws at import time —
// same reason next/font/google is mocked above. Echo back the `variable`
// option so `<family>.variable` still resolves to the real CSS custom
// property name (--font-sans, --font-serif, --font-montserrat, --font-spartan).
vi.mock("next/font/local", () => ({
  default: (opts: { variable?: string } = {}) => ({
    className: "mock-local-font",
    variable: opts.variable ?? "--font-mock-local",
    style: { fontFamily: "mock-local-font" },
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
