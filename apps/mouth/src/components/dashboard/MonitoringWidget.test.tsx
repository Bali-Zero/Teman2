import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MonitoringWidget } from './MonitoringWidget';

// Mock monitoring modules
vi.mock('@/lib/monitoring', () => ({
  conversationMonitor: {
    getSummary: vi.fn(() => ({
      activeSessions: 2,
      totalTurns: 10,
      totalErrors: 1,
      totalTimeouts: 0,
      totalRateLimitHits: 0,
    })),
    getActiveSessions: vi.fn(() => [
      {
        sessionId: 'test-session-1',
        turnCount: 5,
        errors: [],
        timeouts: 0,
        rateLimitHits: 0,
        startTime: new Date(),
        lastMessageTime: new Date(),
      },
    ]),
  },
}));

vi.mock('@/lib/monitoring-dashboard', () => ({
  monitoringDashboard: {
    showSummary: vi.fn(),
  },
}));

describe('MonitoringWidget', () => {
  const mockLocalStorage = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  };

  beforeEach(() => {
    vi.stubGlobal('localStorage', mockLocalStorage);
    mockLocalStorage.getItem.mockReturnValue('true'); // enable widget
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('should not render when flag is false', () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    const { container } = render(<MonitoringWidget />);
    expect(container.firstChild).toBeNull();
  });

  it('should render when flag is true', async () => {
    render(<MonitoringWidget />);

    await waitFor(
      () => {
        expect(screen.getByText('📊 Monitoring')).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  it('should display monitoring stats', async () => {
    render(<MonitoringWidget />);

    await waitFor(
      () => {
        expect(screen.getByText('Active Sessions:')).toBeInTheDocument();
        expect(screen.getByText('Total Turns:')).toBeInTheDocument();
        expect(screen.getByText('Errors:')).toBeInTheDocument();
      },
      { timeout: 6000 }
    );
  });

  it('should have close button', async () => {
    render(<MonitoringWidget />);

    await waitFor(
      () => {
        const closeButton = screen.getByLabelText('Close monitoring widget');
        expect(closeButton).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  it('should call showSummary when view details button is clicked', async () => {
    const { monitoringDashboard } = await import('@/lib/monitoring-dashboard');

    render(<MonitoringWidget />);

    await waitFor(
      () => {
        const viewDetailsButton = screen.getByText('View Details in Console →');
        expect(viewDetailsButton).toBeInTheDocument();
      },
      { timeout: 6000 }
    );

    const viewDetailsButton = screen.getByText('View Details in Console →');
    viewDetailsButton.click();

    expect(monitoringDashboard.showSummary).toHaveBeenCalled();
  });
});
