/**
 * Unit tests for FileGridSkeleton component
 *
 * Tests cover:
 * - Rendering with default count
 * - Rendering with custom count
 * - Shimmer animation presence
 * - Accessibility
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FileGridSkeleton } from '../FileGridSkeleton';

describe('FileGridSkeleton', () => {
  it('should render with default count of 12 skeleton cards', () => {
    const { container } = render(<FileGridSkeleton />);

    // Grid container should exist
    const grid = container.querySelector('.grid');
    expect(grid).toBeTruthy();

    // Should have default 12 skeleton items
    const skeletonCards = container.querySelectorAll('.rounded-lg');
    expect(skeletonCards.length).toBe(12);
  });

  it('should render with custom count', () => {
    const { container } = render(<FileGridSkeleton count={6} />);

    const skeletonCards = container.querySelectorAll('.rounded-lg');
    expect(skeletonCards.length).toBe(6);
  });

  it('should render with zero count', () => {
    const { container } = render(<FileGridSkeleton count={0} />);

    // Grid should still exist but be empty
    const grid = container.querySelector('.grid');
    expect(grid).toBeTruthy();

    const skeletonCards = container.querySelectorAll('.rounded-lg.border');
    expect(skeletonCards.length).toBe(0);
  });

  it('should have shimmer animation styles', () => {
    const { container } = render(<FileGridSkeleton count={1} />);

    // Should have elements with shimmer background gradient
    const shimmerElements = container.querySelectorAll('[style*="background"]');
    expect(shimmerElements.length).toBeGreaterThan(0);
  });

  it('should render section header skeleton', () => {
    const { container } = render(<FileGridSkeleton />);

    // Should have header separator lines
    const separators = container.querySelectorAll('.h-px');
    expect(separators.length).toBe(2); // Left and right gradient lines
  });

  it('should have responsive grid classes', () => {
    const { container } = render(<FileGridSkeleton />);

    const grid = container.querySelector('.grid');
    expect(grid?.className).toContain('grid-cols-2');
    expect(grid?.className).toContain('sm:grid-cols-3');
    expect(grid?.className).toContain('md:grid-cols-4');
    expect(grid?.className).toContain('lg:grid-cols-5');
    expect(grid?.className).toContain('xl:grid-cols-6');
  });

  it('should render skeleton card with icon, name, and meta placeholders', () => {
    const { container } = render(<FileGridSkeleton count={1} />);

    // Icon placeholder (h-12 w-12)
    const iconPlaceholder = container.querySelector('.h-12.w-12');
    expect(iconPlaceholder).toBeTruthy();

    // Name placeholder (h-4 w-24)
    const namePlaceholder = container.querySelector('.h-4.w-24');
    expect(namePlaceholder).toBeTruthy();

    // Meta placeholder (h-3 w-16)
    const metaPlaceholder = container.querySelector('.h-3.w-16');
    expect(metaPlaceholder).toBeTruthy();
  });
});
