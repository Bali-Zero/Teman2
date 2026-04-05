import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import KnowledgeError from '../error';

// Mock logger
vi.mock('@/lib/logger', () => ({
  logger: {
    error: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    warn: vi.fn(),
  },
}));

// Mock Button component
vi.mock('@/components/ui/button', () => ({
  Button: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

describe('KnowledgeError', () => {
  const mockError = new Error('Test knowledge error') as Error & {
    digest?: string;
  };
  const mockReset = vi.fn();

  it('renders error heading', () => {
    render(<KnowledgeError error={mockError} reset={mockReset} />);
    expect(screen.getByText('Knowledge Base Error')).toBeInTheDocument();
  });

  it('renders error description', () => {
    render(<KnowledgeError error={mockError} reset={mockReset} />);
    expect(screen.getByText(/We couldn't load the knowledge base/)).toBeInTheDocument();
  });

  it('renders retry button', () => {
    render(<KnowledgeError error={mockError} reset={mockReset} />);
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('calls reset when retry is clicked', () => {
    render(<KnowledgeError error={mockError} reset={mockReset} />);
    fireEvent.click(screen.getByText('Retry'));
    expect(mockReset).toHaveBeenCalledTimes(1);
  });
});
