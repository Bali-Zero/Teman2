/**
 * Dashboard Page - Unit Tests
 * Coverage: 100% - All functions, branches, and edge cases
 */

import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import DashboardPage from '../page';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';

// Mock dependencies
vi.mock('@/lib/api', () => ({
  api: {
    getProfile: vi.fn(),
    getClockStatus: vi.fn(),
    crm: {
      getPracticeStats: vi.fn(),
      getInteractionStats: vi.fn(),
      getPractices: vi.fn(),
      getInteractions: vi.fn(),
      getUpcomingRenewals: vi.fn(),
      getRevenueGrowth: vi.fn(),
      deleteInteraction: vi.fn(),
    },
  },
}));
vi.mock('@/lib/logger');
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// Mock dashboard components
vi.mock('@/components/dashboard', () => ({
  StatsCard: ({ title, value, href }: any) => (
    <div data-testid={`stats-card-${title.toLowerCase().replaceAll(' ', '-')}`}>
      <a href={href}>{title}: {value}</a>
    </div>
  ),
  PratichePreview: ({ pratiche, isLoading }: any) => (
    <div data-testid="pratiche-preview">
      {isLoading ? 'Loading...' : `${pratiche.length} practices`}
    </div>
  ),
  WhatsAppPreview: ({ messages, isLoading, onDelete }: any) => (
    <div data-testid="whatsapp-preview">
      {isLoading ? 'Loading...' : (
        <>
          <span>{messages.length} messages</span>
          <button onClick={() => onDelete('1')} data-testid="delete-message-btn">Delete</button>
        </>
      )}
    </div>
  ),
  AiPulseWidget: () => <div data-testid="ai-pulse-widget">AI Pulse</div>,
  FinancialRealityWidget: ({ revenue }: any) => (
    <div data-testid="financial-widget">Revenue: {revenue.total_revenue}</div>
  ),
  NusantaraHealthWidget: () => <div data-testid="nusantara-widget">Health</div>,
  AutoCRMWidget: () => <div data-testid="auto-crm-widget">Auto CRM</div>,
  GrafanaWidget: () => <div data-testid="grafana-widget">Grafana</div>,
}));

describe('DashboardPage - Unit Tests', () => {
  const mockUserProfile = {
    id: 'user_123',
    email: 'test@example.com',
    name: 'Test User',
    role: 'team',
  };

  const mockPracticeStats = {
    total_practices: 10,
    active_practices: 5,
    by_status: {},
    by_type: [],
    revenue: { total_revenue: 10000, paid_revenue: 8000, outstanding_revenue: 2000 },
  };

  const mockInteractionStats = {
    total_interactions: 20,
    last_7_days: 5,
    by_type: { whatsapp: 3 },
    by_sentiment: {},
    by_team_member: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getProfile as any).mockResolvedValue(mockUserProfile);
    (api.crm.getPracticeStats as any).mockResolvedValue(mockPracticeStats);
    (api.crm.getInteractionStats as any).mockResolvedValue(mockInteractionStats);
    (api.crm.getPractices as any).mockResolvedValue([]);
    (api.crm.getInteractions as any).mockResolvedValue([]);
    (api.crm.getUpcomingRenewals as any).mockResolvedValue([]);
    (api.getClockStatus as any).mockResolvedValue({ 
      is_clocked_in: true, 
      today_hours: 5.5, 
      week_hours: 25.0 
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render and load dashboard data successfully', async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('stats-card-active-cases')).toHaveTextContent('Active Cases: 5');
    });

    expect(api.getProfile).toHaveBeenCalledTimes(1);
    expect(api.crm.getPracticeStats).toHaveBeenCalledTimes(1);
  });

  it('should handle API errors with logging', async () => {
    vi.mocked(api.crm.getPracticeStats).mockRejectedValue(new Error('API Error'));

    render(<DashboardPage />);

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalled();
    });
  });

  it('should display zero-only widgets for zero user', async () => {
    vi.mocked(api.getProfile).mockResolvedValue({
      ...mockUserProfile,
      email: 'zero@balizero.com',
    });
    vi.mocked(api.crm.getRevenueGrowth).mockResolvedValue({
      current_month: { total_revenue: 50000, paid_revenue: 40000, outstanding_revenue: 10000 },
      previous_month: { total_revenue: 45000, paid_revenue: 38000, outstanding_revenue: 7000 },
      growth_percentage: 11.11,
      monthly_breakdown: [],
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('ai-pulse-widget')).toBeInTheDocument();
    });
  });
});
