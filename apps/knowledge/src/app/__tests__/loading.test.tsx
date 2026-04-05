import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import KnowledgeLoading from '../loading';

describe('KnowledgeLoading', () => {
  it('renders without crashing', () => {
    const { container } = render(<KnowledgeLoading />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders skeleton placeholders with animation', () => {
    const { container } = render(<KnowledgeLoading />);
    const pulsingElements = container.querySelectorAll('.animate-pulse');
    expect(pulsingElements.length).toBeGreaterThan(5);
  });

  it('renders grid skeleton for documents', () => {
    const { container } = render(<KnowledgeLoading />);
    const gridItems = container.querySelectorAll('.grid .rounded-lg');
    expect(gridItems.length).toBe(9);
  });

  it('renders category skeleton pills', () => {
    const { container } = render(<KnowledgeLoading />);
    const categorySkeletons = container.querySelectorAll('.flex.flex-wrap .animate-pulse');
    expect(categorySkeletons.length).toBe(5);
  });
});
