import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SystemPulsePage from './page';
import { logger } from '@/lib/logger';
import { intelligenceApi, SystemMetrics } from '@/lib/api/intelligence.api';

vi.mock('@/lib/logger');
vi.mock('@/lib/api/intelligence.api');
vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

const mockMetrics: SystemMetrics = {
  agent_status: 'active',
  last_run: '2025-01-05T10:30:00Z',
  items_processed_today: 15,
  avg_response_time_ms: 2500,
  qdrant_health: 'healthy',
  next_scheduled_run: '2025-01-05T12:00:00Z',
  uptime_percentage: 99.8,
};

describe('SystemPulsePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(intelligenceApi.getMetrics).mockResolvedValue(mockMetrics);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should log component mount', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(logger.componentMount).toHaveBeenCalledWith('SystemPulsePage');
    });
  });

  it('should log component unmount', async () => {
    const { unmount } = render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.queryByText('Loading System Metrics...')).not.toBeInTheDocument();
    });

    unmount();

    expect(logger.componentUnmount).toHaveBeenCalledWith('SystemPulsePage');
  });

  it('should show loading state initially', () => {
    vi.mocked(intelligenceApi.getMetrics).mockImplementation(() => new Promise(() => {}));

    render(<SystemPulsePage />);

    expect(screen.getByText('Loading System Metrics...')).toBeInTheDocument();
  });

  it('should fetch metrics using intelligenceApi on mount', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(intelligenceApi.getMetrics).toHaveBeenCalled();
    });
  });

  it('should display agent status as ACTIVE', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    expect(screen.getByText('Uptime: 99.8%')).toBeInTheDocument();
  });

  it('should display last scan time formatted', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      const lastScanCard = screen.getByText('Last Scan').closest('div');
      expect(lastScanCard).toBeInTheDocument();
    });
  });

  it('should display items processed today', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument();
    });

    expect(screen.getByText('Visa pages analyzed')).toBeInTheDocument();
  });

  it('should display average response time in seconds', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('2.50s')).toBeInTheDocument();
    });

    expect(screen.getByText('Per page analysis')).toBeInTheDocument();
  });

  it('should display Qdrant health as Healthy', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    expect(screen.getByText('All collections operational')).toBeInTheDocument();
  });

  it('should display Qdrant health as Degraded when degraded', async () => {
    vi.mocked(intelligenceApi.getMetrics).mockResolvedValueOnce({
      ...mockMetrics,
      qdrant_health: 'degraded',
    });

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Degraded')).toBeInTheDocument();
    });
  });

  it('should display Qdrant health as Down when down', async () => {
    vi.mocked(intelligenceApi.getMetrics).mockResolvedValueOnce({
      ...mockMetrics,
      qdrant_health: 'down',
    });

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Down')).toBeInTheDocument();
    });
  });

  it('should display agent status as IDLE when idle', async () => {
    vi.mocked(intelligenceApi.getMetrics).mockResolvedValueOnce({
      ...mockMetrics,
      agent_status: 'idle',
    });

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('IDLE')).toBeInTheDocument();
    });
  });

  it('should display agent status as ERROR when error', async () => {
    vi.mocked(intelligenceApi.getMetrics).mockResolvedValueOnce({
      ...mockMetrics,
      agent_status: 'error',
    });

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('ERROR')).toBeInTheDocument();
    });
  });

  it('should handle null last_run gracefully', async () => {
    vi.mocked(intelligenceApi.getMetrics).mockResolvedValueOnce({
      ...mockMetrics,
      last_run: null,
    });

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Never')).toBeInTheDocument();
    });
  });

  it('should handle null next_scheduled_run gracefully', async () => {
    vi.mocked(intelligenceApi.getMetrics).mockResolvedValueOnce({
      ...mockMetrics,
      next_scheduled_run: null,
    });

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });

  it('should display next scheduled run time', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Every 2 hours')).toBeInTheDocument();
    });
  });

  it('should display all 6 metric cards', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Agent Status')).toBeInTheDocument();
    });

    expect(screen.getByText('Last Scan')).toBeInTheDocument();
    expect(screen.getByText('Items Processed Today')).toBeInTheDocument();
    expect(screen.getByText('Avg Response Time')).toBeInTheDocument();
    expect(screen.getByText('Qdrant Health')).toBeInTheDocument();
    expect(screen.getByText('Next Scheduled Run')).toBeInTheDocument();
  });

  it('should display agent configuration', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Agent Configuration')).toBeInTheDocument();
    });

    expect(screen.getByText('Gemini 2.0 Flash (Vision)')).toBeInTheDocument();
    expect(screen.getByText('Playwright Webkit')).toBeInTheDocument();
    expect(screen.getByText('imigrasi.go.id/wna/permohonan-visa')).toBeInTheDocument();
    expect(screen.getByText('MD5 Hash + Vision Analysis')).toBeInTheDocument();
  });

  it('should handle errors and show error state', async () => {
    const mockError = new Error('Failed to load metrics');
    vi.mocked(intelligenceApi.getMetrics).mockRejectedValueOnce(mockError);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Metrics Unavailable')).toBeInTheDocument();
    });

    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('should log error when metrics load fails', async () => {
    const mockError = new Error('Failed to load metrics');
    vi.mocked(intelligenceApi.getMetrics).mockRejectedValueOnce(mockError);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalledWith(
        'Failed to load system metrics',
        expect.any(Object),
        mockError
      );
    });
  });

  it('should log success when metrics load successfully', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(logger.info).toHaveBeenCalledWith(
        'System metrics loaded successfully',
        expect.objectContaining({
          metadata: expect.objectContaining({
            agent_status: 'active',
            qdrant_health: 'healthy',
            items_processed: 15,
          }),
        })
      );
    });
  });

  it('should refresh metrics when Refresh button is clicked', async () => {
    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    const refreshButton = screen.getByText('Refresh');
    await userEvent.click(refreshButton);

    expect(intelligenceApi.getMetrics).toHaveBeenCalledTimes(2);
  });

  it('should retry loading metrics when Retry button is clicked in error state', async () => {
    const mockError = new Error('Failed to load metrics');
    vi.mocked(intelligenceApi.getMetrics)
      .mockRejectedValueOnce(mockError)
      .mockResolvedValueOnce(mockMetrics);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Metrics Unavailable')).toBeInTheDocument();
    });

    const retryButton = screen.getByText('Retry');
    await userEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    expect(intelligenceApi.getMetrics).toHaveBeenCalledTimes(2);
  });
});
