/**
 * Unit tests for FileListSkeleton component
 *
 * Tests cover:
 * - Rendering with default count
 * - Rendering with custom count
 * - Table header skeleton
 * - Row structure
 * - Shimmer animation presence
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { FileListSkeleton } from '../FileListSkeleton';

describe('FileListSkeleton', () => {
  it('should render with default count of 10 skeleton rows', () => {
    const { container } = render(<FileListSkeleton />);

    // Should have default 10 skeleton rows (excluding header)
    const rows = container.querySelectorAll('.border-b.border-\\[\\#dadce0\\]');
    // 10 rows + header = 11 total
    expect(rows.length).toBe(10);
  });

  it('should render with custom count', () => {
    const { container } = render(<FileListSkeleton count={5} />);

    const rows = container.querySelectorAll('.grid.grid-cols-\\[auto_1fr_auto_auto_auto\\]');
    // 5 rows + 1 header row = 6
    expect(rows.length).toBe(6);
  });

  it('should render table header skeleton', () => {
    const { container } = render(<FileListSkeleton />);

    // Header should be sticky
    const header = container.querySelector('.sticky.top-0');
    expect(header).toBeTruthy();

    // Header should have backdrop blur
    expect(header?.className).toContain('backdrop-blur-sm');
  });

  it('should render header column skeletons', () => {
    const { container } = render(<FileListSkeleton />);

    // Header should have multiple skeleton elements for columns
    const header = container.querySelector('.sticky.top-0');
    const headerSkeletons = header?.querySelectorAll('.rounded');
    expect(headerSkeletons?.length).toBeGreaterThanOrEqual(3); // Name, Modified, Size columns
  });

  it('should render row with all required placeholder elements', () => {
    const { container } = render(<FileListSkeleton count={1} />);

    // Get the first row (after header)
    const rows = container.querySelectorAll('.grid.grid-cols-\\[auto_1fr_auto_auto_auto\\]');
    const dataRow = rows[1]; // Skip header

    // Icon placeholder (h-5 w-5)
    const iconPlaceholder = dataRow?.querySelector('.h-5.w-5');
    expect(iconPlaceholder).toBeTruthy();

    // Name placeholder (h-4 w-48)
    const namePlaceholder = dataRow?.querySelector('.h-4.w-48');
    expect(namePlaceholder).toBeTruthy();

    // Size placeholder (h-3 w-16)
    const sizePlaceholder = dataRow?.querySelector('.h-3.w-16');
    expect(sizePlaceholder).toBeTruthy();
  });

  it('should have shimmer animation styles', () => {
    const { container } = render(<FileListSkeleton count={1} />);

    // Should have elements with shimmer background gradient
    const shimmerElements = container.querySelectorAll('[style*="background"]');
    expect(shimmerElements.length).toBeGreaterThan(0);
  });

  it('should hide modified date column on mobile', () => {
    const { container } = render(<FileListSkeleton count={1} />);

    // Modified date placeholder should have md:block class
    const modifiedPlaceholder = container.querySelector('.hidden.md\\:block.h-3.w-24');
    expect(modifiedPlaceholder).toBeTruthy();
  });

  it('should render with zero count', () => {
    const { container } = render(<FileListSkeleton count={0} />);

    // Should still have header but no data rows
    const header = container.querySelector('.sticky.top-0');
    expect(header).toBeTruthy();

    // Only 1 grid (the header)
    const grids = container.querySelectorAll('.grid.grid-cols-\\[auto_1fr_auto_auto_auto\\]');
    expect(grids.length).toBe(1);
  });
});
