import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Loading from './loading';

describe('Loading', () => {
  it('should render loading component', () => {
    render(<Loading />);

    expect(screen.getByText('Loading Zantara...')).toBeInTheDocument();
  });

  it('should render loader icon', () => {
    const { container } = render(<Loading />);

    const loader = container.querySelector('.animate-spin');
    expect(loader).toBeInTheDocument();
  });

  it('should have correct structure', () => {
    const { container } = render(<Loading />);

    const mainDiv = container.firstChild as HTMLElement;
    expect(mainDiv).toHaveClass('flex', 'h-screen', 'w-full', 'items-center', 'justify-center');
  });

  it('should display loading text', () => {
    render(<Loading />);

    const loadingText = screen.getByText('Loading Zantara...');
    expect(loadingText).toBeInTheDocument();
    expect(loadingText).toHaveClass('animate-pulse');
  });
});
