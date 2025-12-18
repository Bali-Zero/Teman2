import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import NotFound from './not-found';

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

describe('NotFound', () => {
  it('should render not found message', () => {
    render(<NotFound />);

    expect(screen.getByText('Page Not Found')).toBeInTheDocument();
    expect(
      screen.getByText('The page you are looking for does not exist or has been moved.')
    ).toBeInTheDocument();
  });

  it('should render return home link', () => {
    render(<NotFound />);

    const homeLink = screen.getByText('Return Home');
    expect(homeLink).toBeInTheDocument();
    expect(homeLink.closest('a')).toHaveAttribute('href', '/');
  });

  it('should render go to chat link', () => {
    render(<NotFound />);

    const chatLink = screen.getByText('Go to Chat');
    expect(chatLink).toBeInTheDocument();
    expect(chatLink.closest('a')).toHaveAttribute('href', '/chat');
  });

  it('should have correct structure', () => {
    const { container } = render(<NotFound />);

    const mainDiv = container.firstChild as HTMLElement;
    expect(mainDiv).toHaveClass(
      'flex',
      'h-screen',
      'w-full',
      'flex-col',
      'items-center',
      'justify-center'
    );
  });

  it('should render file question icon', () => {
    const { container } = render(<NotFound />);

    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });
});
