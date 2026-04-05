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
  default: ({ src, alt, ...props }: { src: string; alt: string; [key: string]: unknown }) => {
    const {
      priority: _p,
      fill: _f,
      unoptimized: _u,
      width: _w,
      height: _h,
      ...imgProps
    } = props as Record<string, unknown>;
    return <img src={src} alt={alt} {...imgProps} />;
  },
}));

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: React.forwardRef((props: Record<string, unknown>, ref: React.Ref<HTMLDivElement>) => {
      const {
        initial: _i,
        animate: _a,
        exit: _e,
        transition: _t,
        variants: _v,
        whileHover: _wh,
        whileTap: _wt,
        layoutId: _l,
        ...rest
      } = props;
      return <div ref={ref} {...rest} />;
    }),
    button: React.forwardRef(
      (props: Record<string, unknown>, ref: React.Ref<HTMLButtonElement>) => {
        const {
          initial: _i,
          animate: _a,
          exit: _e,
          transition: _t,
          variants: _v,
          whileHover: _wh,
          whileTap: _wt,
          layoutId: _l,
          ...rest
        } = props;
        return <button ref={ref} {...rest} />;
      }
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAnimation: () => ({ start: vi.fn(), stop: vi.fn() }),
}));

// Mock localStorage
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
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

Object.defineProperty(window, 'localStorage', {
  value: new LocalStorageMock(),
  writable: true,
  configurable: true,
});

// Mock fetch
global.fetch = vi.fn();

// Mock confirm
window.confirm = vi.fn(() => true);

// Mock scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// Mock IntersectionObserver
class IntersectionObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  constructor(_callback: IntersectionObserverCallback, _options?: IntersectionObserverInit) {}
}
Object.defineProperty(window, 'IntersectionObserver', {
  value: IntersectionObserverMock,
  writable: true,
});
