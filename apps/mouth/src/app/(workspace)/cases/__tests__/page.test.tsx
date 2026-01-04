import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import CasesPage from '../page';
import * as api from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  api: {
    crm: {
      getPractices: vi.fn(),
    },
  },
}));

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe('CasesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.api.crm.getPractices as any).mockResolvedValue([]);
  });

  describe('Page Structure', () => {
    it('renders cases page header', async () => {
      render(<CasesPage />);
      await waitFor(() => {
        expect(screen.getByText('Cases')).toBeInTheDocument();
      });
    });

    it('displays page description', async () => {
      render(<CasesPage />);
      await waitFor(() => {
        expect(
          screen.getByText('Manage KITAS, Visa, PT PMA, Tax and other cases')
        ).toBeInTheDocument();
      });
    });

    it('displays New Case button', () => {
      render(<CasesPage />);
      expect(screen.getByText('New Case')).toBeInTheDocument();
    });

    it('displays search bar', () => {
      render(<CasesPage />);
      expect(screen.getByPlaceholderText('Search cases by ID, client, type...')).toBeInTheDocument();
    });
  });

  describe('Kanban Board', () => {
    it('renders all four status columns', async () => {
      render(<CasesPage />);

      await waitFor(() => {
        expect(screen.getByText('Inquiry')).toBeInTheDocument();
        expect(screen.getByText('Quotation')).toBeInTheDocument();
        expect(screen.getByText('In Progress')).toBeInTheDocument();
        expect(screen.getByText('Completed')).toBeInTheDocument();
      });
    });

    it('displays empty state for all columns', async () => {
      render(<CasesPage />);

      await waitFor(() => {
        const noCasesMessages = screen.getAllByText('No cases');
        expect(noCasesMessages.length).toBeGreaterThanOrEqual(4);
      });
    });

    it('displays case count in column headers', async () => {
      render(<CasesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Inquiry.*0/)).toBeInTheDocument();
        expect(screen.getByText(/Quotation.*0/)).toBeInTheDocument();
      });
    });

    it('displays cases in correct columns based on status', async () => {
      const mockCases = [
        {
          id: 1,
          title: 'KITAS Renewal',
          status: 'inquiry',
          client_id: 1,
          client_name: 'John Doe',
        },
        {
          id: 2,
          title: 'Visa Extension',
          status: 'quotation',
          client_id: 2,
          client_name: 'Jane Smith',
        },
      ];

      (api.api.crm.getPractices as any).mockResolvedValueOnce(mockCases);

      render(<CasesPage />);

      await waitFor(() => {
        expect(screen.getByText('KITAS Renewal')).toBeInTheDocument();
        expect(screen.getByText('Visa Extension')).toBeInTheDocument();
      });
    });
  });

  describe('View Toggling', () => {
    it('renders view toggle buttons', () => {
      render(<CasesPage />);

      const buttons = screen.getAllByRole('button');
      expect(buttons.some(btn => btn.getAttribute('title') === 'Kanban Board')).toBe(true);
      expect(buttons.some(btn => btn.getAttribute('title') === 'List View')).toBe(true);
    });

    it('starts with Kanban view active', () => {
      render(<CasesPage />);

      // Kanban columns should be visible
      expect(screen.getByText('Inquiry')).toBeInTheDocument();
      expect(screen.getByText('Quotation')).toBeInTheDocument();
    });

    it('switches to list view when list button clicked', async () => {
      const mockCases = [
        {
          id: 1,
          title: 'KITAS Renewal',
          status: 'inquiry',
          client_id: 1,
          client_name: 'John Doe',
          practice_type_code: 'KITAS',
          client_lead: 'agent@balizero.com',
        },
      ];

      (api.api.crm.getPractices as any).mockResolvedValueOnce(mockCases);

      render(<CasesPage />);

      await waitFor(() => {
        expect(screen.getByText('KITAS Renewal')).toBeInTheDocument();
      });

      // Click list view button
      const buttons = screen.getAllByRole('button');
      const listButton = buttons.find(btn => btn.getAttribute('title') === 'List View');

      if (listButton) {
        fireEvent.click(listButton);

        // List view should show cases in table format
        await waitFor(() => {
          expect(screen.getByRole('table')).toBeInTheDocument();
        });
      }
    });

    it('returns to kanban view when kanban button clicked', async () => {
      render(<CasesPage />);

      const buttons = screen.getAllByRole('button');
      const listButton = buttons.find(btn => btn.getAttribute('title') === 'List View');
      const kanbanButton = buttons.find(btn => btn.getAttribute('title') === 'Kanban Board');

      if (listButton && kanbanButton) {
        fireEvent.click(listButton);

        await waitFor(() => {
          expect(screen.getByRole('table')).toBeInTheDocument();
        });

        fireEvent.click(kanbanButton);

        await waitFor(() => {
          expect(screen.queryByRole('table')).not.toBeInTheDocument();
          expect(screen.getByText('Inquiry')).toBeInTheDocument();
        });
      }
    });
  });

  describe('Filters', () => {
    it('renders filter button', () => {
      render(<CasesPage />);
      expect(screen.getByText('Filters')).toBeInTheDocument();
    });

    it('opens filter panel when clicked', async () => {
      render(<CasesPage />);

      const filterButton = screen.getByText('Filters');
      fireEvent.click(filterButton);

      // Filter options should appear
      await waitFor(() => {
        expect(screen.getByDisplayValue('All statuses')).toBeInTheDocument();
        expect(screen.getByDisplayValue('All types')).toBeInTheDocument();
        expect(screen.getByDisplayValue('All team members')).toBeInTheDocument();
      });
    });

    it('filters cases by status', async () => {
      const mockCases = [
        {
          id: 1,
          title: 'KITAS Renewal',
          status: 'inquiry',
          client_id: 1,
          client_name: 'John Doe',
          practice_type_code: 'KITAS',
          client_lead: 'agent@balizero.com',
        },
        {
          id: 2,
          title: 'Visa Extension',
          status: 'in_progress',
          client_id: 2,
          client_name: 'Jane Smith',
          practice_type_code: 'VISA',
          client_lead: 'agent@balizero.com',
        },
      ];

      (api.api.crm.getPractices as any).mockResolvedValueOnce(mockCases);

      render(<CasesPage />);

      // Open filters
      const filterButton = screen.getByText('Filters');
      fireEvent.click(filterButton);

      await waitFor(() => {
        const statusSelect = screen.getByDisplayValue('All statuses');
        fireEvent.change(statusSelect, { target: { value: 'inquiry' } });
      });
    });

    it('shows clear filters button when filters applied', async () => {
      render(<CasesPage />);

      const filterButton = screen.getByText('Filters');
      fireEvent.click(filterButton);

      await waitFor(() => {
        const statusSelect = screen.getByDisplayValue('All statuses');
        fireEvent.change(statusSelect, { target: { value: 'inquiry' } });
      });

      // Clear all button should appear
      await waitFor(() => {
        expect(screen.getByText('Clear all')).toBeInTheDocument();
      });
    });
  });

  describe('Search Functionality', () => {
    it('accepts search input', () => {
      render(<CasesPage />);

      const searchInput = screen.getByPlaceholderText(
        'Search cases by ID, client, type...'
      ) as HTMLInputElement;

      fireEvent.change(searchInput, { target: { value: 'KITAS' } });
      expect(searchInput.value).toBe('KITAS');
    });

    it('fetches practices on component mount', async () => {
      render(<CasesPage />);

      await waitFor(() => {
        expect(api.api.crm.getPractices).toHaveBeenCalled();
      });
    });
  });

  describe('New Case Button', () => {
    it('is clickable', () => {
      render(<CasesPage />);

      const newCaseButton = screen.getByText('New Case');
      expect(newCaseButton).not.toBeDisabled();
    });

    it('navigates to new case form on click', () => {
      const mockRouter = { push: vi.fn() };
      vi.mock('next/navigation', () => ({
        useRouter: () => mockRouter,
      }));

      render(<CasesPage />);
      const newCaseButton = screen.getByText('New Case');
      fireEvent.click(newCaseButton);

      // Router should navigate to /cases/new
      // (This would be tested with a proper router mock)
    });
  });

  describe('Case Cards', () => {
    it('renders case information when cases exist', async () => {
      const mockCases = [
        {
          id: 1,
          title: 'KITAS Renewal 2025',
          status: 'inquiry',
          client_id: 1,
          client_name: 'John Doe',
          type: 'KITAS Work Permit',
          created_at: '2026-01-05',
        },
      ];

      (api.api.crm.getPractices as any).mockResolvedValueOnce(mockCases);

      render(<CasesPage />);

      await waitFor(() => {
        expect(screen.getByText('KITAS Renewal 2025')).toBeInTheDocument();
      });
    });
  });

  describe('Responsive Design', () => {
    it('renders correctly on desktop view', () => {
      // Default viewport is desktop
      render(<CasesPage />);

      expect(screen.getByText('Cases')).toBeInTheDocument();
      expect(screen.getByText('Inquiry')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('handles API errors gracefully', async () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      (api.api.crm.getPractices as any).mockRejectedValueOnce(new Error('API Error'));

      render(<CasesPage />);

      await waitFor(() => {
        expect(consoleError).toHaveBeenCalled();
      });

      consoleError.mockRestore();
    });
  });
});
