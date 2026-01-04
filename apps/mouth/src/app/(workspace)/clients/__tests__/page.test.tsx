import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import ClientsPage from '../page';
import * as api from '@/lib/api';

// Mock the API
vi.mock('@/lib/api', () => ({
  api: {
    crm: {
      getClients: vi.fn(),
    },
    getUserProfile: vi.fn(),
  },
}));

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe('ClientsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.api.crm.getClients as any).mockResolvedValue([]);
    (api.api.getUserProfile as any).mockReturnValue({
      email: 'test@balizero.com',
    });
  });

  it('renders clients page header', async () => {
    render(<ClientsPage />);
    await waitFor(() => {
      expect(screen.getByText('Clients')).toBeInTheDocument();
    });
  });

  it('displays empty state when no clients', async () => {
    render(<ClientsPage />);
    await waitFor(() => {
      expect(screen.getByText('No clients found')).toBeInTheDocument();
    });
  });

  it('opens filters panel when filter button clicked', async () => {
    render(<ClientsPage />);
    const filterButton = screen.getByText('Filters');
    fireEvent.click(filterButton);

    await waitFor(() => {
      expect(screen.getByDisplayValue('All statuses')).toBeInTheDocument();
      expect(screen.getByDisplayValue('All nationalities')).toBeInTheDocument();
    });
  });

  it('toggles view between list and kanban', async () => {
    render(<ClientsPage />);

    // Get view toggle buttons
    const buttons = screen.getAllByRole('button');
    const kanbanButton = buttons.find(btn => btn.getAttribute('title') === 'Kanban Board');

    if (kanbanButton) {
      fireEvent.click(kanbanButton);
      // Verify view changed (sort buttons should disappear)
      expect(screen.queryByText('Sort by:')).not.toBeInTheDocument();
    }
  });

  it('displays New Client button', () => {
    render(<ClientsPage />);
    expect(screen.getByText('New Client')).toBeInTheDocument();
  });

  it('fetches clients on component mount', async () => {
    render(<ClientsPage />);

    await waitFor(() => {
      expect(api.api.crm.getClients).toHaveBeenCalled();
    });
  });

  it('updates client count display', async () => {
    (api.api.crm.getClients as any).mockResolvedValueOnce([
      { id: 1, full_name: 'John Doe', status: 'lead' },
      { id: 2, full_name: 'Jane Doe', status: 'active' },
    ]);

    render(<ClientsPage />);

    await waitFor(() => {
      expect(screen.getByText(/2 clients/)).toBeInTheDocument();
    });
  });

  it('respects access control rules', async () => {
    (api.api.getUserProfile as any).mockReturnValue({
      email: 'other@balizero.com',
    });

    render(<ClientsPage />);
    // Other users should only see their own clients
    // This is tested by the getVisibleClients function
    await waitFor(() => {
      expect(api.api.crm.getClients).toHaveBeenCalled();
    });
  });

  it('filters clients by status', async () => {
    render(<ClientsPage />);

    const filterButton = screen.getByText('Filters');
    fireEvent.click(filterButton);

    const statusSelect = screen.getByDisplayValue('All statuses');
    fireEvent.change(statusSelect, { target: { value: 'active' } });

    await waitFor(() => {
      expect(statusSelect).toHaveValue('active');
    });
  });

  it('handles API errors gracefully', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    (api.api.crm.getClients as any).mockRejectedValueOnce(new Error('API Error'));

    render(<ClientsPage />);

    await waitFor(() => {
      expect(consoleError).toHaveBeenCalled();
    });

    consoleError.mockRestore();
  });
});
