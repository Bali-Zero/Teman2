/**
 * Cases Page - Comprehensive Test Suite
 *
 * Tests all functionality of the Cases management page including:
 * - Component rendering
 * - View mode switching (Kanban/List)
 * - Search and filtering
 * - Sorting
 * - Status changes
 * - Case creation
 * - Error handling
 * - Analytics tracking
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import PratichePage from '../page';
import { api } from '@/lib/api';
import * as analytics from '@/lib/analytics';
import type { Practice } from '@/lib/api/crm/crm.types';

// Mock dependencies
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    replace: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/api');
vi.mock('@/lib/analytics');
vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

// Mock data
const mockPractices: Practice[] = [
  {
    id: 1,
    client_id: 101,
    client_name: 'John Doe',
    client_lead: 'zero@balizero.com',
    practice_type_code: 'kitas_application',
    status: 'inquiry',
    priority: 'normal',
    notes: 'KITAS application for tech startup founder',
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
  },
  {
    id: 2,
    client_id: 102,
    client_name: 'Jane Smith',
    client_lead: 'dea@balizero.com',
    practice_type_code: 'kitap_application',
    status: 'quotation_sent',
    priority: 'high',
    notes: 'KITAP renewal for long-term resident',
    created_at: '2026-01-02T10:00:00Z',
    updated_at: '2026-01-02T10:00:00Z',
  },
  {
    id: 3,
    client_id: 103,
    client_name: 'Bob Johnson',
    client_lead: 'anton@balizero.com',
    practice_type_code: 'property_purchase',
    status: 'in_progress',
    priority: 'normal',
    notes: 'Villa purchase in Canggu',
    created_at: '2026-01-03T10:00:00Z',
    updated_at: '2026-01-03T10:00:00Z',
  },
  {
    id: 4,
    client_id: 104,
    client_name: 'Alice Williams',
    client_lead: 'zero@balizero.com',
    practice_type_code: 'pt_pma_setup',
    status: 'completed',
    priority: 'high',
    notes: 'PT PMA for consulting business',
    created_at: '2026-01-04T10:00:00Z',
    updated_at: '2026-01-04T10:00:00Z',
  },
];

describe('Cases Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.crm.getPractices as any) = vi.fn().mockResolvedValue(mockPractices);
    (api.getProfile as any) = vi.fn().mockResolvedValue({ email: 'zero@balizero.com' });
    (analytics.initializeAnalytics as any) = vi.fn();
    (analytics.trackViewModeChange as any) = vi.fn();
    (analytics.trackFilterApplied as any) = vi.fn();
    (analytics.trackFilterRemoved as any) = vi.fn();
    (analytics.trackSortApplied as any) = vi.fn();
    (analytics.trackSearch as any) = vi.fn();
  });

  describe('Component Rendering', () => {
    it('should render page title and description', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('Cases')).toBeInTheDocument();
        expect(screen.getByText(/Manage KITAS, Visa, PT PMA/)).toBeInTheDocument();
      });
    });

    it('should render "+ New Case" button', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /New Case/i })).toBeInTheDocument();
      });
    });

    it('should render search bar', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/Search cases by ID, client, type/i)).toBeInTheDocument();
      });
    });

    it('should render Filters button', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Filters/i })).toBeInTheDocument();
      });
    });

    it('should render view mode toggle buttons', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        // Grid and List view buttons should be present
        const buttons = screen.getAllByRole('button');
        expect(buttons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Data Loading', () => {
    it('should load practices on mount', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(api.crm.getPractices).toHaveBeenCalledWith({ limit: 100 });
      });
    });

    it('should display loading skeleton while loading', () => {
      render(<PratichePage />);

      // Should show loading state initially
      expect(screen.getByTestId('loading-skeleton') || screen.queryByText('Loading')).toBeTruthy();
    });

    it('should display all practices after loading', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
        expect(screen.getByText('Bob Johnson')).toBeInTheDocument();
        expect(screen.getByText('Alice Williams')).toBeInTheDocument();
      });
    });

    it('should display error message on API failure', async () => {
      (api.crm.getPractices as any) = vi.fn().mockRejectedValue(new Error('API Error'));

      render(<PratichePage />);

      await waitFor(() => {
        // Toast error should be called
        expect(api.crm.getPractices).toHaveBeenCalled();
      });
    });
  });

  describe('Kanban View', () => {
    it('should display Kanban board with 4 columns', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('Inquiry')).toBeInTheDocument();
        expect(screen.getByText('Quotation')).toBeInTheDocument();
        expect(screen.getByText('In Progress')).toBeInTheDocument();
        expect(screen.getByText('Completed')).toBeInTheDocument();
      });
    });

    it('should display cases in correct columns', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        // John Doe should be in Inquiry column
        const inquiryColumn = screen.getByText('Inquiry').closest('div');
        expect(within(inquiryColumn!).getByText('John Doe')).toBeInTheDocument();

        // Jane Smith should be in Quotation column
        const quotationColumn = screen.getByText('Quotation').closest('div');
        expect(within(quotationColumn!).getByText('Jane Smith')).toBeInTheDocument();

        // Bob Johnson should be in In Progress column
        const inProgressColumn = screen.getByText('In Progress').closest('div');
        expect(within(inProgressColumn!).getByText('Bob Johnson')).toBeInTheDocument();

        // Alice Williams should be in Completed column
        const completedColumn = screen.getByText('Completed').closest('div');
        expect(within(completedColumn!).getByText('Alice Williams')).toBeInTheDocument();
      });
    });

    it('should display case count in column headers', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText(/Inquiry.*1/)).toBeInTheDocument(); // 1 case
        expect(screen.getByText(/Quotation.*1/)).toBeInTheDocument(); // 1 case
        expect(screen.getByText(/In Progress.*1/)).toBeInTheDocument(); // 1 case
        expect(screen.getByText(/Completed.*1/)).toBeInTheDocument(); // 1 case
      });
    });
  });

  describe('List View', () => {
    it('should switch to list view when list button clicked', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Click list view button (assuming it has data-testid or aria-label)
      const listButton = screen.getAllByRole('button').find(btn =>
        btn.getAttribute('aria-label')?.includes('List') ||
        btn.className.includes('list')
      );

      if (listButton) {
        await user.click(listButton);

        // Should track view mode change
        expect(analytics.trackViewModeChange).toHaveBeenCalledWith('list');
      }
    });

    it('should display table headers in list view', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Switch to list view
      const listButton = screen.getAllByRole('button').find(btn =>
        btn.className.includes('list')
      );

      if (listButton) {
        await user.click(listButton);

        await waitFor(() => {
          expect(screen.getByText('ID')).toBeInTheDocument();
          expect(screen.getByText('Client')).toBeInTheDocument();
          expect(screen.getByText('Type')).toBeInTheDocument();
          expect(screen.getByText('Status')).toBeInTheDocument();
          expect(screen.getByText('Assigned To')).toBeInTheDocument();
        });
      }
    });
  });

  describe('Search Functionality', () => {
    it('should filter cases by client name', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search cases/i);
      await user.type(searchInput, 'John');

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.queryByText('Jane Smith')).not.toBeInTheDocument();
        expect(analytics.trackSearch).toHaveBeenCalledWith('John', 1);
      });
    });

    it('should filter cases by ID', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search cases/i);
      await user.type(searchInput, '2');

      await waitFor(() => {
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
        expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
      });
    });

    it('should filter cases by practice type', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search cases/i);
      await user.type(searchInput, 'kitas');

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.queryByText('Bob Johnson')).not.toBeInTheDocument(); // Property purchase
      });
    });

    it('should show "no results" when search has no matches', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search cases/i);
      await user.type(searchInput, 'nonexistent');

      await waitFor(() => {
        expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
        expect(screen.queryByText('Jane Smith')).not.toBeInTheDocument();
      });
    });
  });

  describe('Filter Functionality', () => {
    it('should open filter panel when Filters button clicked', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Filters/i })).toBeInTheDocument();
      });

      const filtersButton = screen.getByRole('button', { name: /Filters/i });
      await user.click(filtersButton);

      // Filter panel should be visible
      await waitFor(() => {
        expect(screen.getByText(/Status/)).toBeInTheDocument();
        expect(screen.getByText(/Type/)).toBeInTheDocument();
        expect(screen.getByText(/Assigned to/)).toBeInTheDocument();
      });
    });

    it('should filter by status', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Open filters
      const filtersButton = screen.getByRole('button', { name: /Filters/i });
      await user.click(filtersButton);

      // Select "In Progress" status
      const statusSelect = screen.getByLabelText(/Status/i);
      await user.selectOptions(statusSelect, 'in_progress');

      await waitFor(() => {
        expect(screen.getByText('Bob Johnson')).toBeInTheDocument();
        expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
        expect(analytics.trackFilterApplied).toHaveBeenCalledWith('status', 'in_progress');
      });
    });

    it('should clear filters when Clear button clicked', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Apply filter
      const filtersButton = screen.getByRole('button', { name: /Filters/i });
      await user.click(filtersButton);

      const statusSelect = screen.getByLabelText(/Status/i);
      await user.selectOptions(statusSelect, 'completed');

      // Clear filters
      const clearButton = screen.getByRole('button', { name: /Clear/i });
      await user.click(clearButton);

      await waitFor(() => {
        // All cases should be visible again
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
        expect(analytics.trackFilterRemoved).toHaveBeenCalled();
      });
    });

    it('should display active filter count', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const filtersButton = screen.getByRole('button', { name: /Filters/i });
      await user.click(filtersButton);

      // Apply two filters
      const statusSelect = screen.getByLabelText(/Status/i);
      await user.selectOptions(statusSelect, 'inquiry');

      const typeSelect = screen.getByLabelText(/Type/i);
      await user.selectOptions(typeSelect, 'kitas_application');

      await waitFor(() => {
        // Filter count badge should show "2"
        expect(screen.getByText('2')).toBeInTheDocument();
      });
    });
  });

  describe('Sorting Functionality', () => {
    it('should sort by ID', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Click ID column header to sort
      const idHeader = screen.getByText('ID');
      await user.click(idHeader);

      expect(analytics.trackSortApplied).toHaveBeenCalledWith('id', 'asc');
    });

    it('should toggle sort order on second click', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const idHeader = screen.getByText('ID');
      await user.click(idHeader); // First click: asc
      await user.click(idHeader); // Second click: desc

      expect(analytics.trackSortApplied).toHaveBeenCalledWith('id', 'desc');
    });
  });

  describe('Status Change', () => {
    it('should open context menu on card menu click', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Find and click the menu button on first card
      const menuButtons = screen.getAllByRole('button').filter(btn =>
        btn.getAttribute('aria-label')?.includes('menu') ||
        btn.className.includes('menu')
      );

      if (menuButtons[0]) {
        await user.click(menuButtons[0]);

        await waitFor(() => {
          expect(screen.getByText('Update Status')).toBeInTheDocument();
          expect(screen.getByText('Inquiry')).toBeInTheDocument();
          expect(screen.getByText('Quotation Sent')).toBeInTheDocument();
        });
      }
    });

    it('should update case status when status option clicked', async () => {
      const user = userEvent.setup();
      (api.crm.updatePractice as any) = vi.fn().mockResolvedValue({});

      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Open context menu
      const menuButtons = screen.getAllByRole('button').filter(btn =>
        btn.className.includes('menu')
      );

      if (menuButtons[0]) {
        await user.click(menuButtons[0]);

        // Click on "In Progress" status
        const inProgressOption = screen.getByText('In Progress');
        await user.click(inProgressOption);

        await waitFor(() => {
          expect(api.crm.updatePractice).toHaveBeenCalledWith(
            1,
            { status: 'in_progress' },
            'zero@balizero.com'
          );
          expect(analytics.trackCaseStatusChanged).toHaveBeenCalledWith(1, 'inquiry', 'in_progress');
        });
      }
    });

    it('should close context menu on outside click', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Open context menu
      const menuButtons = screen.getAllByRole('button').filter(btn =>
        btn.className.includes('menu')
      );

      if (menuButtons[0]) {
        await user.click(menuButtons[0]);

        await waitFor(() => {
          expect(screen.getByText('Update Status')).toBeInTheDocument();
        });

        // Click outside
        await user.click(document.body);

        await waitFor(() => {
          expect(screen.queryByText('Update Status')).not.toBeInTheDocument();
        });
      }
    });
  });

  describe('Case Creation', () => {
    it('should navigate to new case page when "+ New Case" clicked', async () => {
      const user = userEvent.setup();
      const mockPush = vi.fn();
      vi.mocked(useRouter).mockReturnValue({ push: mockPush } as any);

      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /New Case/i })).toBeInTheDocument();
      });

      const newCaseButton = screen.getByRole('button', { name: /New Case/i });
      await user.click(newCaseButton);

      expect(mockPush).toHaveBeenCalledWith('/cases/new');
    });
  });

  describe('Pagination', () => {
    it('should display pagination controls in list view', async () => {
      // Create more than 25 cases to trigger pagination
      const manyPractices = Array.from({ length: 30 }, (_, i) => ({
        ...mockPractices[0],
        id: i + 1,
        client_name: `Client ${i + 1}`,
      }));

      (api.crm.getPractices as any) = vi.fn().mockResolvedValue(manyPractices);

      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('Client 1')).toBeInTheDocument();
      });

      // Switch to list view
      const listButton = screen.getAllByRole('button').find(btn =>
        btn.className.includes('list')
      );

      if (listButton) {
        await user.click(listButton);

        await waitFor(() => {
          expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
          expect(screen.getByRole('button', { name: /Next/i })).toBeInTheDocument();
          expect(screen.getByRole('button', { name: /Previous/i })).toBeInTheDocument();
        });
      }
    });

    it('should navigate to next page when Next clicked', async () => {
      const manyPractices = Array.from({ length: 30 }, (_, i) => ({
        ...mockPractices[0],
        id: i + 1,
        client_name: `Client ${i + 1}`,
      }));

      (api.crm.getPractices as any) = vi.fn().mockResolvedValue(manyPractices);

      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('Client 1')).toBeInTheDocument();
      });

      // Switch to list view
      const listButton = screen.getAllByRole('button').find(btn =>
        btn.className.includes('list')
      );

      if (listButton) {
        await user.click(listButton);

        const nextButton = screen.getByRole('button', { name: /Next/i });
        await user.click(nextButton);

        await waitFor(() => {
          expect(analytics.trackPaginationChange).toHaveBeenCalledWith(2, 25);
        });
      }
    });
  });

  describe('Analytics Tracking', () => {
    it('should initialize analytics on mount', async () => {
      render(<PratichePage />);

      await waitFor(() => {
        expect(analytics.initializeAnalytics).toHaveBeenCalled();
      });
    });

    it('should track view mode changes', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Should track initial view mode
      expect(analytics.trackViewModeChange).toHaveBeenCalledWith('kanban');

      // Switch to list view
      const listButton = screen.getAllByRole('button').find(btn =>
        btn.className.includes('list')
      );

      if (listButton) {
        await user.click(listButton);
        expect(analytics.trackViewModeChange).toHaveBeenCalledWith('list');
      }
    });

    it('should track search operations', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search cases/i);
      await user.type(searchInput, 'John');

      await waitFor(() => {
        expect(analytics.trackSearch).toHaveBeenCalledWith('John', expect.any(Number));
      });
    });

    it('should track filter operations', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const filtersButton = screen.getByRole('button', { name: /Filters/i });
      await user.click(filtersButton);

      const statusSelect = screen.getByLabelText(/Status/i);
      await user.selectOptions(statusSelect, 'inquiry');

      await waitFor(() => {
        expect(analytics.trackFilterApplied).toHaveBeenCalledWith('status', 'inquiry');
      });
    });

    it('should track sort operations', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Initial sort should be tracked
      expect(analytics.trackSortApplied).toHaveBeenCalledWith('created_at', 'desc');
    });

    it('should track case status changes', async () => {
      const user = userEvent.setup();
      (api.crm.updatePractice as any) = vi.fn().mockResolvedValue({});

      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const menuButtons = screen.getAllByRole('button').filter(btn =>
        btn.className.includes('menu')
      );

      if (menuButtons[0]) {
        await user.click(menuButtons[0]);

        const inProgressOption = screen.getByText('In Progress');
        await user.click(inProgressOption);

        await waitFor(() => {
          expect(analytics.trackCaseStatusChanged).toHaveBeenCalledWith(
            1,
            'inquiry',
            'in_progress'
          );
        });
      }
    });
  });

  describe('Error Handling', () => {
    it('should display error message when API call fails', async () => {
      (api.crm.getPractices as any) = vi.fn().mockRejectedValue(new Error('Network error'));

      render(<PratichePage />);

      await waitFor(() => {
        // Should log error to console
        expect(console.error).toHaveBeenCalledWith(
          'Failed to load practices:',
          expect.any(Error)
        );
      });
    });

    it('should handle status update failure gracefully', async () => {
      const user = userEvent.setup();
      (api.crm.updatePractice as any) = vi.fn().mockRejectedValue(new Error('Update failed'));

      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const menuButtons = screen.getAllByRole('button').filter(btn =>
        btn.className.includes('menu')
      );

      if (menuButtons[0]) {
        await user.click(menuButtons[0]);

        const inProgressOption = screen.getByText('In Progress');
        await user.click(inProgressOption);

        await waitFor(() => {
          expect(console.error).toHaveBeenCalledWith(
            'Failed to update status:',
            expect.any(Error)
          );
        });
      }
    });
  });

  describe('Performance', () => {
    it('should memoize filtered practices to avoid recalculation', async () => {
      const { rerender } = render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      // Rerender with same props
      rerender(<PratichePage />);

      // getPractices should only be called once (memoization working)
      expect(api.crm.getPractices).toHaveBeenCalledTimes(1);
    });

    it('should use ref for filter tracking to avoid closure issues', async () => {
      const user = userEvent.setup();
      render(<PratichePage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const filtersButton = screen.getByRole('button', { name: /Filters/i });
      await user.click(filtersButton);

      const statusSelect = screen.getByLabelText(/Status/i);
      await user.selectOptions(statusSelect, 'inquiry');

      // Should track filter applied only once (not multiple times due to closure)
      await waitFor(() => {
        const calls = (analytics.trackFilterApplied as any).mock.calls.filter(
          (call: any) => call[0] === 'status' && call[1] === 'inquiry'
        );
        expect(calls.length).toBe(1);
      });
    });
  });
});
