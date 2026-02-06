/**
 * Unit tests for ThinkingIndicator component
 *
 * Tests cover:
 * - Initial render with first stage
 * - Stage progression over time
 * - Progress bar presence
 * - isComplete prop behavior
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import ThinkingIndicator from '../ThinkingIndicator';

describe('ThinkingIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should render the first stage text', () => {
    render(<ThinkingIndicator />);
    expect(screen.getByText('Searching 9,612 business codes...')).toBeTruthy();
  });

  it('should render the avatar circle', () => {
    const { container } = render(<ThinkingIndicator />);
    const avatar = container.querySelector('.rounded-full');
    expect(avatar).toBeTruthy();
  });

  it('should progress to stage 2 after 2.5 seconds', () => {
    render(<ThinkingIndicator />);

    act(() => {
      vi.advanceTimersByTime(2600);
    });

    expect(screen.getByText('Analyzing matches...')).toBeTruthy();
  });

  it('should progress to stage 3 after 6 seconds', () => {
    render(<ThinkingIndicator />);

    act(() => {
      vi.advanceTimersByTime(6100);
    });

    expect(screen.getByText('Generating answer...')).toBeTruthy();
  });

  it('should render a progress bar track', () => {
    const { container } = render(<ThinkingIndicator />);
    const progressTrack = container.querySelector('.overflow-hidden.mt-2');
    expect(progressTrack).toBeTruthy();
  });

  it('should render the progress bar fill', () => {
    const { container } = render(<ThinkingIndicator />);
    const fill = container.querySelector('.bg-gradient-to-r');
    expect(fill).toBeTruthy();
  });

  it('should accept isComplete prop without errors', () => {
    const { container } = render(<ThinkingIndicator isComplete />);
    expect(container.firstChild).toBeTruthy();
  });

  it('should show all three stage texts', () => {
    render(<ThinkingIndicator />);

    // Stage 1 is always visible
    expect(screen.getByText('Searching 9,612 business codes...')).toBeTruthy();

    // Advance to show stages 2 and 3
    act(() => {
      vi.advanceTimersByTime(6100);
    });

    expect(screen.getByText('Analyzing matches...')).toBeTruthy();
    expect(screen.getByText('Generating answer...')).toBeTruthy();
  });
});
