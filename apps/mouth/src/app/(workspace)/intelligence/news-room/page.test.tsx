import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NewsRoomPage from './page';
import { intelligenceApi, StagingItem } from '@/lib/api/intelligence.api';
import { logger } from '@/lib/logger';

vi.mock('@/lib/api/intelligence.api');
vi.mock('@/lib/logger');
vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

const mockNewsItems: StagingItem[] = [
  {
    id: 'news-1',
    type: 'news',
    title: 'Breaking: New Immigration Policy Announced',
    status: 'pending',
    detected_at: '2025-01-01T10:00:00Z',
    source: 'Jakarta Post',
    detection_type: 'NEW',
    is_critical: true,
  },
  {
    id: 'news-2',
    type: 'news',
    title: 'Visa Requirements Updated for Business Travelers',
    status: 'pending',
    detected_at: '2025-01-02T11:00:00Z',
    source: 'Tempo',
    detection_type: 'UPDATED',
    is_critical: false,
  },
  {
    id: 'news-3',
    type: 'news',
    title: 'Indonesia Opens New Immigration Office in Bali',
    status: 'pending',
    detected_at: '2025-01-03T12:00:00Z',
    source: 'Kompas',
    detection_type: 'NEW',
    is_critical: false,
  },
];

describe('NewsRoomPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(intelligenceApi.getPendingItems).mockResolvedValue({
      items: mockNewsItems,
      count: 3,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should log component mount', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(logger.componentMount).toHaveBeenCalledWith('NewsRoomPage');
    });
  });

  it('should log component unmount', async () => {
    const { unmount } = render(<NewsRoomPage />);

    await waitFor(() => {
      expect(screen.queryByText('Gathering Global Intelligence...')).not.toBeInTheDocument();
    });

    unmount();

    expect(logger.componentUnmount).toHaveBeenCalledWith('NewsRoomPage');
  });

  it('should show loading state initially', () => {
    render(<NewsRoomPage />);

    expect(screen.getByText('Gathering Global Intelligence...')).toBeInTheDocument();
  });

  it('should load and display pending news items', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(screen.getByText('Breaking: New Immigration Policy Announced')).toBeInTheDocument();
    });

    expect(screen.getByText('Visa Requirements Updated for Business Travelers')).toBeInTheDocument();
    expect(screen.getByText('Indonesia Opens New Immigration Office in Bali')).toBeInTheDocument();
    expect(intelligenceApi.getPendingItems).toHaveBeenCalledWith('news');
  });

  it('should show empty state when no items', async () => {
    vi.mocked(intelligenceApi.getPendingItems).mockResolvedValue({
      items: [],
      count: 0,
    });

    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(screen.getByText('No Drafts Pending')).toBeInTheDocument();
    });

    expect(screen.getByText(/The intelligence scraper hasn't flagged any new items/i)).toBeInTheDocument();
  });

  it('should display source badges correctly', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(screen.getByText('Jakarta Post')).toBeInTheDocument();
    });

    expect(screen.getByText('Tempo')).toBeInTheDocument();
    expect(screen.getByText('Kompas')).toBeInTheDocument();
  });

  it('should display CRITICAL badge for critical items', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    });
  });

  it('should not display CRITICAL badge for non-critical items', async () => {
    vi.mocked(intelligenceApi.getPendingItems).mockResolvedValue({
      items: mockNewsItems.filter(item => !item.is_critical),
      count: 2,
    });

    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(screen.getByText('Visa Requirements Updated for Business Travelers')).toBeInTheDocument();
    });

    expect(screen.queryByText('CRITICAL')).not.toBeInTheDocument();
  });

  it('should display detection type for each item', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      const detectionTypes = screen.getAllByText(/NEW|UPDATED/);
      expect(detectionTypes.length).toBeGreaterThan(0);
    });
  });

  it('should format dates correctly', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      // Check that dates are formatted (format depends on locale, so just check presence)
      const dateElements = screen.getAllByText(/2025/);
      expect(dateElements.length).toBeGreaterThan(0);
    });
  });

  it('should display "Open Editor" buttons for each item', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      const editorButtons = screen.getAllByText('Open Editor');
      expect(editorButtons.length).toBe(3);
    });
  });

  it('should display external source links', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      const externalLinks = screen.getAllByRole('link');
      // Filter for actual external links (not just text that says "Jakarta Post")
      const sourceLinks = externalLinks.filter(link =>
        link.getAttribute('target') === '_blank'
      );
      expect(sourceLinks.length).toBe(3);
    });
  });

  it('should refresh items when "Sync Sources" button is clicked', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(screen.getByText('Breaking: New Immigration Policy Announced')).toBeInTheDocument();
    });

    const syncButton = screen.getByText('Sync Sources');
    await userEvent.click(syncButton);

    expect(intelligenceApi.getPendingItems).toHaveBeenCalledTimes(2);
  });

  it('should log success with critical count metadata', async () => {
    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(logger.info).toHaveBeenCalledWith(
        'Loaded 3 news items',
        expect.objectContaining({
          metadata: expect.objectContaining({
            criticalCount: 1,
          }),
        })
      );
    });
  });

  it('should handle load errors gracefully', async () => {
    const mockError = new Error('Failed to load news');
    vi.mocked(intelligenceApi.getPendingItems).mockRejectedValue(mockError);

    render(<NewsRoomPage />);

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalledWith(
        'Failed to load news items',
        expect.any(Object),
        mockError
      );
    });
  });
});
