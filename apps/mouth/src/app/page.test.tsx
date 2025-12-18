import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { waitFor } from '@testing-library/dom';

// Use vi.hoisted to create mocks
const { mockIsAuthenticated } = vi.hoisted(() => ({
  mockIsAuthenticated: vi.fn(),
}));

// Mock the api module
vi.mock('@/lib/api', () => ({
  api: {
    isAuthenticated: mockIsAuthenticated,
  },
}));

import Home from './page';

// Mock useRouter
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe('Home Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should redirect to /chat when authenticated', async () => {
    mockIsAuthenticated.mockReturnValue(true);

    render(<Home />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/chat');
    });
  });

  it('should redirect to /login when not authenticated', async () => {
    mockIsAuthenticated.mockReturnValue(false);

    render(<Home />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/login');
    });
  });

  it('should show loading spinner while redirecting', () => {
    mockIsAuthenticated.mockReturnValue(true);

    const { container } = render(<Home />);

    // Should show the loading pulse animation (div with animate-pulse class)
    const pulseElement = container.querySelector('.animate-pulse');
    expect(pulseElement).toBeInTheDocument();
  });
});
