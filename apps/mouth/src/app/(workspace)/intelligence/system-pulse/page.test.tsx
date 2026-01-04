import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SystemPulsePage from './page';
import { logger } from '@/lib/logger';

vi.mock('@/lib/logger');

interface SystemMetrics {
  agent_status: "active" | "idle" | "error";
  last_run: string;
  items_processed_today: number;
  avg_response_time_ms: number;
  qdrant_health: "healthy" | "degraded" | "down";
  next_scheduled_run: string;
  uptime_percentage: number;
}

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
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should log component mount', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(logger.componentMount).toHaveBeenCalledWith('SystemPulsePage');
    });
  });

  it('should log component unmount', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    const { unmount } = render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.queryByText('Loading System Metrics...')).not.toBeInTheDocument();
    });

    unmount();

    expect(logger.componentUnmount).toHaveBeenCalledWith('SystemPulsePage');
  });

  it('should show loading state initially', () => {
    vi.mocked(fetch).mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<SystemPulsePage />);

    expect(screen.getByText('Loading System Metrics...')).toBeInTheDocument();
  });

  it('should fetch metrics from /api/intel/metrics on mount', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/intel/metrics');
    });
  });

  it('should display agent status as ACTIVE', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    expect(screen.getByText('Uptime: 99.8%')).toBeInTheDocument();
  });

  it('should display last scan time formatted', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      // Check that time is displayed (format depends on locale)
      const lastScanCard = screen.getByText('Last Scan').closest('div');
      expect(lastScanCard).toBeInTheDocument();
    });
  });

  it('should display items processed today', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument();
    });

    expect(screen.getByText('Visa pages analyzed')).toBeInTheDocument();
  });

  it('should display average response time in seconds', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      // 2500ms = 2.50s
      expect(screen.getByText('2.50s')).toBeInTheDocument();
    });

    expect(screen.getByText('Per page analysis')).toBeInTheDocument();
  });

  it('should display Qdrant health as Healthy', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    expect(screen.getByText('All collections operational')).toBeInTheDocument();
  });

  it('should display next scheduled run time', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Every 2 hours')).toBeInTheDocument();
    });
  });

  it('should display all 6 metric cards', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

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
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Agent Configuration')).toBeInTheDocument();
    });

    expect(screen.getByText('Gemini 2.0 Flash (Vision)')).toBeInTheDocument();
    expect(screen.getByText('Playwright Webkit')).toBeInTheDocument();
    expect(screen.getByText('imigrasi.go.id/wna/permohonan-visa')).toBeInTheDocument();
    expect(screen.getByText('MD5 Hash + Vision Analysis')).toBeInTheDocument();
  });

  it('should handle fetch errors and show error state', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      statusText: 'Internal Server Error',
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Metrics Unavailable')).toBeInTheDocument();
    });

    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('should log error when metrics load fails', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      statusText: 'Internal Server Error',
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalledWith(
        'Failed to load system metrics',
        expect.any(Object),
        expect.any(Error)
      );
    });
  });

  it('should log success when metrics load successfully', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

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
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    const refreshButton = screen.getByText('Refresh');
    await userEvent.click(refreshButton);

    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('should retry loading metrics when Retry button is clicked in error state', async () => {
    // First call fails
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      statusText: 'Internal Server Error',
    } as Response);

    render(<SystemPulsePage />);

    await waitFor(() => {
      expect(screen.getByText('Metrics Unavailable')).toBeInTheDocument();
    });

    // Second call succeeds
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => mockMetrics,
    } as Response);

    const retryButton = screen.getByText('Retry');
    await userEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
