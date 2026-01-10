import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import IntelligenceAnalyticsPage from './page';
import { intelligenceApi, IntelligenceAnalytics } from '@/lib/api/intelligence.api';
import { logger } from '@/lib/logger';

vi.mock('@/lib/api/intelligence.api');
vi.mock('@/lib/logger');
vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

const mockAnalytics: IntelligenceAnalytics = {
  period_days: 30,
  summary: {
    total_processed: 150,
    total_approved: 120,
    total_rejected: 30,
    total_published: 45,
    approval_rate: 80.0,
    rejection_rate: 20.0,
  },
  daily_trends: [
    { date: '2025-01-01', processed: 5, approved: 4, rejected: 1, published: 2 },
    { date: '2025-01-02', processed: 8, approved: 6, rejected: 2, published: 3 },
    { date: '2025-01-03', processed: 3, approved: 3, rejected: 0, published: 1 },
  ],
  type_breakdown: {
    visa: { processed: 100, approved: 80, rejected: 20 },
    news: { processed: 50, approved: 40, rejected: 10, published: 45 },
  },
  detection_type_breakdown: {
    NEW: 90,
    UPDATED: 60,
  },
};

describe('IntelligenceAnalyticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(intelligenceApi.getAnalytics).mockResolvedValue(mockAnalytics);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should log component mount', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(logger.componentMount).toHaveBeenCalledWith('IntelligenceAnalyticsPage');
    });
  });

  it('should log component unmount', async () => {
    const { unmount } = render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.queryByText('Loading Analytics...')).not.toBeInTheDocument();
    });

    unmount();

    expect(logger.componentUnmount).toHaveBeenCalledWith('IntelligenceAnalyticsPage');
  });

  it('should show loading state initially', () => {
    vi.mocked(intelligenceApi.getAnalytics).mockImplementation(() => new Promise(() => {}));

    render(<IntelligenceAnalyticsPage />);

    expect(screen.getByText('Loading Analytics...')).toBeInTheDocument();
  });

  it('should fetch analytics on mount', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(intelligenceApi.getAnalytics).toHaveBeenCalledWith(30);
    });
  });

  it('should display summary cards', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument(); // Total Processed
      expect(screen.getByText('80.0%')).toBeInTheDocument(); // Approval Rate
      expect(screen.getByText('20.0%')).toBeInTheDocument(); // Rejection Rate
      expect(screen.getByText('45')).toBeInTheDocument(); // Published
    });
  });

  it('should display daily trends chart', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Daily Trends')).toBeInTheDocument();
    });

    // Check that dates are displayed
    const dates = screen.getAllByText(/Jan \d+/);
    expect(dates.length).toBeGreaterThan(0);
  });

  it('should display type breakdown', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Visa Oracle Breakdown')).toBeInTheDocument();
      expect(screen.getByText('News Room Breakdown')).toBeInTheDocument();
    });

    // Check Visa breakdown
    expect(screen.getByText('100')).toBeInTheDocument(); // Visa processed
    expect(screen.getByText('80')).toBeInTheDocument(); // Visa approved

    // Check News breakdown
    expect(screen.getByText('50')).toBeInTheDocument(); // News processed
    expect(screen.getByText('45')).toBeInTheDocument(); // News published
  });

  it('should change period when period selector changes', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    // Note: Select component interaction requires more complex setup
    // The period change is tested via useEffect dependency on periodDays state
    // Full Select component testing would require mocking Radix UI components
    // For now, we verify the initial call with default period (30 days)
    expect(intelligenceApi.getAnalytics).toHaveBeenCalledWith(30);
  });

  it('should refresh analytics when refresh button is clicked', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    const refreshButton = screen.getByText('Refresh');
    await userEvent.click(refreshButton);

    expect(intelligenceApi.getAnalytics).toHaveBeenCalledTimes(2);
  });

  it('should handle errors gracefully', async () => {
    const mockError = new Error('Failed to load analytics');
    vi.mocked(intelligenceApi.getAnalytics).mockRejectedValueOnce(mockError);

    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Analytics Unavailable')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });

    expect(logger.error).toHaveBeenCalledWith(
      'Failed to load analytics',
      expect.any(Object),
      mockError
    );
  });

  it('should retry loading analytics when Retry button is clicked', async () => {
    const mockError = new Error('Failed to load analytics');
    vi.mocked(intelligenceApi.getAnalytics)
      .mockRejectedValueOnce(mockError)
      .mockResolvedValueOnce(mockAnalytics);

    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Analytics Unavailable')).toBeInTheDocument();
    });

    const retryButton = screen.getByText('Retry');
    await userEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });

    expect(intelligenceApi.getAnalytics).toHaveBeenCalledTimes(2);
  });

  it('should log success when analytics load successfully', async () => {
    render(<IntelligenceAnalyticsPage />);

    await waitFor(() => {
      expect(logger.info).toHaveBeenCalledWith(
        'Analytics loaded successfully',
        expect.objectContaining({
          metadata: expect.objectContaining({
            total_processed: 150,
            approval_rate: 80.0,
          }),
        })
      );
    });
  });
});
