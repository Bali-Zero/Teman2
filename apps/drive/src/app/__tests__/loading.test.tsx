import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Loading from '../loading';

describe('Drive Loading Page', () => {
  it('renders without crashing', () => {
    const { container } = render(<Loading />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders sidebar skeleton', () => {
    const { container } = render(<Loading />);
    const pulsingElements = container.querySelectorAll('.animate-pulse');
    expect(pulsingElements.length).toBeGreaterThan(0);
  });

  it('renders file grid skeleton with 10 items', () => {
    const { container } = render(<Loading />);
    const gridItems = container.querySelectorAll('.grid > .animate-pulse');
    expect(gridItems.length).toBe(10);
  });

  it('renders toolbar skeleton area', () => {
    const { container } = render(<Loading />);
    // The toolbar area should have the search skeleton
    const flexItems = container.querySelectorAll('.mb-6 .animate-pulse');
    expect(flexItems.length).toBeGreaterThan(0);
  });
});
