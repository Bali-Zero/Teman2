import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { PortalBottomNav } from './PortalBottomNav';

// Mock next/navigation
const mockUsePathname = vi.fn(() => '/portal');
vi.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
  Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// Mock api
const mockGetMessages = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    portal: {
      getMessages: mockGetMessages,
    },
  },
}));

describe('PortalBottomNav', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePathname.mockReturnValue('/portal');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render navigation tabs', async () => {
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 0 });

    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(screen.getByText('Home')).toBeInTheDocument();
      expect(screen.getByText('Vault')).toBeInTheDocument();
      expect(screen.getByText('Chat')).toBeInTheDocument();
      expect(screen.getByText('Profile')).toBeInTheDocument();
    });
  });

  it('should highlight active tab based on pathname', async () => {
    mockUsePathname.mockReturnValue('/portal/vault');
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 0 });

    render(<PortalBottomNav />);

    await waitFor(() => {
      const vaultLink = screen.getByText('Vault').closest('a');
      expect(vaultLink).toHaveAttribute('href', '/portal/vault');
    });
  });

  it('should fetch and display unread message count', async () => {
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 5 });

    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledWith(1, 0);
    });

    await waitFor(() => {
      const badge = screen.getByText('5');
      expect(badge).toBeInTheDocument();
    });
  });

  it('should display 99+ for counts over 99', async () => {
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 150 });

    render(<PortalBottomNav />);

    await waitFor(() => {
      const badge = screen.getByText('99+');
      expect(badge).toBeInTheDocument();
    });
  });

  it('should not show badge when unread count is 0', async () => {
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 0 });

    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalled();
    });

    const badges = screen.queryAllByText(/^\d+$/);
    expect(badges.length).toBe(0);
  });

  it('should poll for unread count every 30 seconds', async () => {
    vi.useFakeTimers();
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 0 });

    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledTimes(1);
    });

    // Fast-forward 30 seconds
    vi.advanceTimersByTime(30000);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalledTimes(2);
    });

    vi.useRealTimers();
  });

  it('should refetch when navigating away from chat', async () => {
    mockUsePathname.mockReturnValue('/portal/chat');
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 0 });

    const { rerender } = render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalled();
    });

    // Navigate away from chat
    mockUsePathname.mockReturnValue('/portal/vault');
    rerender(<PortalBottomNav />);

    await waitFor(() => {
      // Should have been called again due to pathname change
      expect(mockGetMessages.mock.calls.length).toBeGreaterThan(1);
    });
  });

  it('should handle API errors gracefully', async () => {
    mockGetMessages.mockRejectedValue(new Error('API Error'));

    // Should not throw
    render(<PortalBottomNav />);

    await waitFor(() => {
      expect(mockGetMessages).toHaveBeenCalled();
    });

    // Component should still render
    await waitFor(() => {
      expect(screen.getByText('Home')).toBeInTheDocument();
    });
  });

  it('should only render on mobile (md:hidden)', async () => {
    mockGetMessages.mockResolvedValue({ messages: [], total: 0, unreadCount: 0 });

    const { container } = render(<PortalBottomNav />);

    await waitFor(() => {
      const nav = container.querySelector('[class*="md:hidden"]');
      expect(nav).toBeInTheDocument();
    });
  });
});
