import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Loading from '../loading';

describe('Calendar Loading Page', () => {
  it('renders without crashing', () => {
    const { container } = render(<Loading />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders skeleton placeholders with animation', () => {
    const { container } = render(<Loading />);
    const pulsingElements = container.querySelectorAll('.animate-pulse');
    expect(pulsingElements.length).toBeGreaterThan(0);
  });

  it('renders calendar grid and weekday header skeletons', () => {
    const { container } = render(<Loading />);
    // Two grids with grid-cols-7: week headers (7) + calendar cells (35) = 42
    const allGridCells = container.querySelectorAll('.grid.grid-cols-7 > .animate-pulse');
    expect(allGridCells.length).toBe(42);
  });

  it('renders sidebar skeleton items', () => {
    const { container } = render(<Loading />);
    const sidebarItems = container.querySelectorAll('.space-y-2 > .animate-pulse');
    expect(sidebarItems.length).toBe(4);
  });
});
