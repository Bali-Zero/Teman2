import React from 'react';
import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock Next.js Image component
vi.mock('next/image', () => ({
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
    // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/no-explicit-any
    const { width: _width, height: _height, ...imgProps } = props as any;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} {...imgProps} />;
  },
}));

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock fetch
global.fetch = vi.fn();

// Mock clipboard
const clipboardMock = {
  writeText: vi.fn().mockResolvedValue(undefined),
};
Object.defineProperty(navigator, 'clipboard', {
  value: clipboardMock,
  writable: true,
  configurable: true,
});

// Mock confirm
window.confirm = vi.fn(() => true);

// Mock scrollIntoView (not available in JSDOM)
Element.prototype.scrollIntoView = vi.fn();
