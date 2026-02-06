/**
 * Unit tests for ComparisonModal component
 *
 * Tests cover:
 * - Closed state (no render)
 * - Open state rendering
 * - Loading state
 * - API calls for each code
 * - Table data after loading
 * - Error handling for failed fetches
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ComparisonModal from '../ComparisonModal';
import { kbliApi } from '@/lib/api/kbli.api';
import type { KBLIDetail } from '@/lib/api/kbli.api';

// Mock the API
vi.mock('@/lib/api/kbli.api', () => ({
  kbliApi: {
    inspect: vi.fn(),
  },
  KBLIApi: vi.fn(),
}));

const mockDetail: KBLIDetail = {
  code: '56101',
  title: 'Restoran',
  description: 'Penyediaan makanan',
  pma_status: 'TERBUKA',
  licensing_status: 'Perizinan Berusaha',
  sector: 'Akomodasi',
  risk_profile: 'Menengah',
  licenses: [{ type: 'NIB', scale: ['Mikro'], risk_level: 'Rendah', sla: '1 hari', requirements: [] }],
  related_codes: [],
};

describe('ComparisonModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should not render title when closed', () => {
    render(
      <ComparisonModal codes={['56101']} open={false} onOpenChange={vi.fn()} />,
    );
    expect(screen.queryByText('Compare KBLI Codes')).toBeNull();
  });

  it('should call inspect API for each code when open', () => {
    vi.mocked(kbliApi.inspect).mockResolvedValue(mockDetail);

    render(
      <ComparisonModal codes={['56101', '56102']} open={true} onOpenChange={vi.fn()} />,
    );

    expect(kbliApi.inspect).toHaveBeenCalledWith('56101');
    expect(kbliApi.inspect).toHaveBeenCalledWith('56102');
    expect(kbliApi.inspect).toHaveBeenCalledTimes(2);
  });

  it('should show title when open', () => {
    vi.mocked(kbliApi.inspect).mockResolvedValue(mockDetail);

    render(
      <ComparisonModal codes={['56101']} open={true} onOpenChange={vi.fn()} />,
    );

    expect(screen.getByText('Compare KBLI Codes')).toBeTruthy();
  });

  it('should show loading state while fetching', () => {
    vi.mocked(kbliApi.inspect).mockReturnValue(new Promise(() => {}));

    render(
      <ComparisonModal codes={['56101']} open={true} onOpenChange={vi.fn()} />,
    );

    expect(screen.getByText('Loading details...')).toBeTruthy();
  });

  it('should render table data after loading', async () => {
    vi.mocked(kbliApi.inspect).mockResolvedValue(mockDetail);

    render(
      <ComparisonModal codes={['56101']} open={true} onOpenChange={vi.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByText('Restoran')).toBeTruthy();
    });
  });

  it('should display description with code count', () => {
    vi.mocked(kbliApi.inspect).mockResolvedValue(mockDetail);

    render(
      <ComparisonModal codes={['56101', '56102', '56103']} open={true} onOpenChange={vi.fn()} />,
    );

    expect(screen.getByText(/3 business codes/)).toBeTruthy();
  });

  it('should handle failed API calls gracefully', async () => {
    vi.mocked(kbliApi.inspect).mockRejectedValue(new Error('Not found'));

    render(
      <ComparisonModal codes={['99999']} open={true} onOpenChange={vi.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getAllByText('Error').length).toBeGreaterThan(0);
    });
  });

  it('should not call API when closed', () => {
    vi.mocked(kbliApi.inspect).mockResolvedValue(mockDetail);

    render(
      <ComparisonModal codes={['56101']} open={false} onOpenChange={vi.fn()} />,
    );

    expect(kbliApi.inspect).not.toHaveBeenCalled();
  });
});
