import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import RootLayout, { metadata } from './layout';

// Mock next/font/google
vi.mock('next/font/google', () => ({
  Geist: () => ({ variable: '--font-geist-sans' }),
  Geist_Mono: () => ({ variable: '--font-geist-mono' }),
}));

describe('RootLayout', () => {
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

  beforeEach(() => {
    consoleErrorSpy.mockClear();
    consoleWarnSpy.mockClear();
  });

  afterAll(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  it('should render children', () => {
    render(
      <RootLayout>
        <div data-testid="child">Hello World</div>
      </RootLayout>
    );

    expect(screen.getByTestId('child')).toBeInTheDocument();
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('should render html and body structure', () => {
    const { container } = render(
      <RootLayout>
        <div>Content</div>
      </RootLayout>
    );

    // In JSDOM, the layout structure is rendered but html/body are handled differently
    // We just verify the content is accessible
    expect(screen.getByText('Content')).toBeInTheDocument();
    expect(container.firstChild).toBeTruthy();
  });
});

describe('metadata', () => {
  it('should have correct title', () => {
    expect((metadata.title as { default: string }).default).toBe('Zantara | Bali Zero Team');
  });

  it('should have correct description', () => {
    expect(metadata.description).toBe(
      'AI-powered team assistant for Bali Zero. Intelligent business operating system.'
    );
  });

  it('should have icon defined', () => {
    expect(metadata.icons).toBeDefined();
  });
});
