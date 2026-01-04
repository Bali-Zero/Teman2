import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VisaOraclePage from './page';
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

const mockItems: StagingItem[] = [
  {
    id: 'visa-1',
    type: 'visa',
    title: 'New Visa Regulation',
    status: 'pending',
    detected_at: '2025-01-01T10:00:00Z',
    source: 'https://imigrasi.go.id/test',
    detection_type: 'NEW',
  },
  {
    id: 'visa-2',
    type: 'visa',
    title: 'Updated Visa Policy',
    status: 'pending',
    detected_at: '2025-01-02T11:00:00Z',
    source: 'https://imigrasi.go.id/test2',
    detection_type: 'UPDATED',
  },
];

describe('VisaOraclePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(intelligenceApi.getPendingItems).mockResolvedValue({
      items: mockItems,
      count: 2,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should log component mount', async () => {
    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(logger.componentMount).toHaveBeenCalledWith('VisaOraclePage');
    });
  });

  it('should log component unmount', async () => {
    const { unmount } = render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.queryByText('Scanning Intelligence Feed...')).not.toBeInTheDocument();
    });

    unmount();

    expect(logger.componentUnmount).toHaveBeenCalledWith('VisaOraclePage');
  });

  it('should show loading state initially', () => {
    render(<VisaOraclePage />);

    expect(screen.getByText('Scanning Intelligence Feed...')).toBeInTheDocument();
  });

  it('should load and display pending items', async () => {
    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    expect(screen.getByText('Updated Visa Policy')).toBeInTheDocument();
    expect(intelligenceApi.getPendingItems).toHaveBeenCalledWith('visa');
  });

  it('should show empty state when no items', async () => {
    vi.mocked(intelligenceApi.getPendingItems).mockResolvedValue({
      items: [],
      count: 0,
    });

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('All Caught Up!')).toBeInTheDocument();
    });

    expect(screen.getByText(/No pending visa updates detected/i)).toBeInTheDocument();
  });

  it('should display stats bar with correct counts', async () => {
    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText(/2 items pending review/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/1 new/i)).toBeInTheDocument();
    expect(screen.getByText(/1 updated/i)).toBeInTheDocument();
  });

  it('should display NEW badge for new regulations', async () => {
    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('✨ NEW REGULATION')).toBeInTheDocument();
    });
  });

  it('should display UPDATED badge for updated policies', async () => {
    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('📝 UPDATED POLICY')).toBeInTheDocument();
    });
  });

  it('should open preview when "View Content" is clicked', async () => {
    vi.mocked(intelligenceApi.getPreview).mockResolvedValue({
      ...mockItems[0],
      content: 'Full regulation content here',
    });

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByText('View Content');
    await userEvent.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Content Preview')).toBeInTheDocument();
    });

    expect(screen.getByText('Full regulation content here')).toBeInTheDocument();
    expect(intelligenceApi.getPreview).toHaveBeenCalledWith('visa', 'visa-1');
  });

  it('should close preview when "Hide Preview" is clicked', async () => {
    vi.mocked(intelligenceApi.getPreview).mockResolvedValue({
      ...mockItems[0],
      content: 'Full regulation content here',
    });

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    // Open preview
    const viewButtons = screen.getAllByText('View Content');
    await userEvent.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Content Preview')).toBeInTheDocument();
    });

    // Close preview
    const hideButton = screen.getByText('Hide Preview');
    await userEvent.click(hideButton);

    await waitFor(() => {
      expect(screen.queryByText('Content Preview')).not.toBeInTheDocument();
    });
  });

  it('should handle approve confirmation and workflow', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(intelligenceApi.approveItem).mockResolvedValue({
      success: true,
      message: 'Approved',
      id: 'visa-1',
    });

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    const approveButtons = screen.getAllByText('Approve & Ingest');
    await userEvent.click(approveButtons[0]);

    expect(confirmSpy).toHaveBeenCalled();

    await waitFor(() => {
      expect(intelligenceApi.approveItem).toHaveBeenCalledWith('visa', 'visa-1');
    });

    expect(logger.info).toHaveBeenCalledWith('Starting approval process', expect.any(Object));
    expect(logger.info).toHaveBeenCalledWith('Approval completed successfully', expect.any(Object));

    confirmSpy.mockRestore();
  });

  it('should cancel approval if user declines confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    const approveButtons = screen.getAllByText('Approve & Ingest');
    await userEvent.click(approveButtons[0]);

    expect(confirmSpy).toHaveBeenCalled();
    expect(intelligenceApi.approveItem).not.toHaveBeenCalled();
    expect(logger.info).toHaveBeenCalledWith('Approval cancelled by user', expect.any(Object));

    confirmSpy.mockRestore();
  });

  it('should remove item from list after successful approval', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(intelligenceApi.approveItem).mockResolvedValue({
      success: true,
      message: 'Approved',
      id: 'visa-1',
    });

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    const approveButtons = screen.getAllByText('Approve & Ingest');
    await userEvent.click(approveButtons[0]);

    await waitFor(() => {
      expect(screen.queryByText('New Visa Regulation')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Updated Visa Policy')).toBeInTheDocument();

    confirmSpy.mockRestore();
  });

  it('should handle reject confirmation and workflow', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(intelligenceApi.rejectItem).mockResolvedValue({
      success: true,
      message: 'Rejected',
      id: 'visa-2',
    });

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('Updated Visa Policy')).toBeInTheDocument();
    });

    const rejectButtons = screen.getAllByText('Reject');
    await userEvent.click(rejectButtons[1]);

    expect(confirmSpy).toHaveBeenCalled();

    await waitFor(() => {
      expect(intelligenceApi.rejectItem).toHaveBeenCalledWith('visa', 'visa-2');
    });

    expect(logger.info).toHaveBeenCalledWith('Starting rejection process', expect.any(Object));
    expect(logger.info).toHaveBeenCalledWith('Rejection completed successfully', expect.any(Object));

    confirmSpy.mockRestore();
  });

  it('should cancel rejection if user declines confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('Updated Visa Policy')).toBeInTheDocument();
    });

    const rejectButtons = screen.getAllByText('Reject');
    await userEvent.click(rejectButtons[0]);

    expect(confirmSpy).toHaveBeenCalled();
    expect(intelligenceApi.rejectItem).not.toHaveBeenCalled();
    expect(logger.info).toHaveBeenCalledWith('Rejection cancelled by user', expect.any(Object));

    confirmSpy.mockRestore();
  });

  it('should handle approval errors gracefully', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const mockError = new Error('Approval failed');
    vi.mocked(intelligenceApi.approveItem).mockRejectedValue(mockError);

    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    const approveButtons = screen.getAllByText('Approve & Ingest');
    await userEvent.click(approveButtons[0]);

    await waitFor(() => {
      expect(logger.error).toHaveBeenCalledWith('Approval failed', expect.any(Object), mockError);
    });

    confirmSpy.mockRestore();
  });

  it('should refresh items when refresh button is clicked', async () => {
    render(<VisaOraclePage />);

    await waitFor(() => {
      expect(screen.getByText('New Visa Regulation')).toBeInTheDocument();
    });

    const refreshButton = screen.getByText('Refresh');
    await userEvent.click(refreshButton);

    expect(intelligenceApi.getPendingItems).toHaveBeenCalledTimes(2);
  });
});
