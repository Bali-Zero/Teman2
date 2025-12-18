import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { waitFor, fireEvent } from '@testing-library/dom';
import userEvent from '@testing-library/user-event';
import AdminPage from './page';

// Mock functions
const {
  mockIsAuthenticated,
  mockIsAdmin,
  mockGetTeamStatus,
  mockGetDailyHours,
  mockGetWeeklySummary,
  mockExportTimesheet,
} = vi.hoisted(() => ({
  mockIsAuthenticated: vi.fn(),
  mockIsAdmin: vi.fn(),
  mockGetTeamStatus: vi.fn(),
  mockGetDailyHours: vi.fn(),
  mockGetWeeklySummary: vi.fn(),
  mockExportTimesheet: vi.fn(),
}));

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  api: {
    isAuthenticated: () => mockIsAuthenticated(),
    isAdmin: () => mockIsAdmin(),
    getTeamStatus: () => mockGetTeamStatus(),
    getDailyHours: (date?: string) => mockGetDailyHours(date),
    getWeeklySummary: () => mockGetWeeklySummary(),
    exportTimesheet: (start: string, end: string) => mockExportTimesheet(start, end),
  },
}));

const mockTeamMembers = [
  {
    user_id: '1',
    email: 'alice@example.com',
    is_online: true,
    last_action: new Date().toISOString(),
    last_action_type: 'clock_in',
  },
  {
    user_id: '2',
    email: 'bob@example.com',
    is_online: false,
    last_action: new Date().toISOString(),
    last_action_type: 'clock_out',
  },
];

const mockDailyHoursData = [
  {
    user_id: '1',
    email: 'alice@example.com',
    date: '2024-01-15',
    clock_in: '2024-01-15T09:00:00Z',
    clock_out: '2024-01-15T17:00:00Z',
    hours_worked: 8,
  },
];

const mockWeeklySummaryData = [
  {
    user_id: '1',
    email: 'alice@example.com',
    week_start: '2024-01-15',
    days_worked: 5,
    total_hours: 40,
    avg_hours_per_day: 8,
  },
];

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated.mockReturnValue(true);
    mockIsAdmin.mockReturnValue(true);
    mockGetTeamStatus.mockResolvedValue(mockTeamMembers);
    mockGetDailyHours.mockResolvedValue(mockDailyHoursData);
    mockGetWeeklySummary.mockResolvedValue(mockWeeklySummaryData);
  });

  describe('Authentication and Authorization', () => {
    it('should redirect to login if not authenticated', async () => {
      mockIsAuthenticated.mockReturnValue(false);
      render(<AdminPage />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/login');
      });
    });

    it('should redirect to chat if not admin', async () => {
      mockIsAuthenticated.mockReturnValue(true);
      mockIsAdmin.mockReturnValue(false);
      render(<AdminPage />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/chat');
      });
    });

    it('should load data if authenticated and admin', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(mockGetTeamStatus).toHaveBeenCalled();
        expect(mockGetDailyHours).toHaveBeenCalled();
        expect(mockGetWeeklySummary).toHaveBeenCalled();
      });
    });
  });

  describe('Header', () => {
    it('should render admin dashboard header', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
      });
    });

    it('should have back to chat button', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        const backButton = screen.getByRole('button', { name: /back to chat/i });
        expect(backButton).toBeInTheDocument();
      });
    });

    it('should navigate back to chat when back button clicked', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back to chat/i });
      await user.click(backButton);

      expect(mockPush).toHaveBeenCalledWith('/chat');
    });

    it('should have refresh and export buttons', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Refresh')).toBeInTheDocument();
        expect(screen.getByText('Export CSV')).toBeInTheDocument();
      });
    });
  });

  describe('Stats cards', () => {
    it('should display team online count', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Team Online')).toBeInTheDocument();
        expect(screen.getByText('1 / 2')).toBeInTheDocument();
      });
    });

    it('should display hours today', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Hours Today')).toBeInTheDocument();
        expect(screen.getByText('8.0h')).toBeInTheDocument();
      });
    });

    it('should display hours this week', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Hours This Week')).toBeInTheDocument();
        expect(screen.getByText('40.0h')).toBeInTheDocument();
      });
    });
  });

  describe('Tabs', () => {
    it('should render all three tabs', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Team Status')).toBeInTheDocument();
        expect(screen.getByText('Daily Hours')).toBeInTheDocument();
        expect(screen.getByText('Weekly Summary')).toBeInTheDocument();
      });
    });

    it('should show team status tab by default', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText(/Team Members/)).toBeInTheDocument();
      });
    });

    it('should switch to daily hours tab when clicked', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Daily Hours')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Daily Hours'));

      await waitFor(() => {
        expect(screen.getByText('Clock In')).toBeInTheDocument();
        expect(screen.getByText('Clock Out')).toBeInTheDocument();
      });
    });

    it('should switch to weekly summary tab when clicked', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Weekly Summary')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /weekly summary/i }));

      await waitFor(() => {
        expect(screen.getByText('Days Worked')).toBeInTheDocument();
        expect(screen.getByText('Total Hours')).toBeInTheDocument();
        expect(screen.getByText('Avg Hours/Day')).toBeInTheDocument();
      });
    });
  });

  describe('Team Status Tab', () => {
    it('should display team members', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('alice')).toBeInTheDocument();
        expect(screen.getByText('bob')).toBeInTheDocument();
      });
    });

    it('should show online status for members', async () => {
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Online')).toBeInTheDocument();
        expect(screen.getByText('Offline')).toBeInTheDocument();
      });
    });

    it('should show empty state when no team members', async () => {
      mockGetTeamStatus.mockResolvedValue([]);
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('No team members found')).toBeInTheDocument();
      });
    });
  });

  describe('Daily Hours Tab', () => {
    it('should show daily hours table', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Daily Hours')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Daily Hours'));

      await waitFor(() => {
        expect(screen.getByText('Team Member')).toBeInTheDocument();
        expect(screen.getByText('Hours Worked')).toBeInTheDocument();
      });
    });

    it('should show empty state when no records', async () => {
      const user = userEvent.setup();
      mockGetDailyHours.mockResolvedValue([]);
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Daily Hours')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Daily Hours'));

      await waitFor(() => {
        expect(screen.getByText('No records for this date')).toBeInTheDocument();
      });
    });

    it('should have date picker', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Daily Hours')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Daily Hours'));

      await waitFor(() => {
        // Date inputs have type="date"
        const datePicker = document.querySelector('input[type="date"]');
        expect(datePicker).toBeInTheDocument();
      });
    });

    it('should call getDailyHours when date is changed', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Daily Hours')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Daily Hours'));

      await waitFor(() => {
        const datePicker = document.querySelector('input[type="date"]');
        expect(datePicker).toBeInTheDocument();
      });

      const datePicker = document.querySelector('input[type="date"]') as HTMLInputElement;
      await fireEvent.change(datePicker, { target: { value: '2024-02-15' } });

      await waitFor(() => {
        expect(mockGetDailyHours).toHaveBeenCalledWith('2024-02-15');
      });
    });
  });

  describe('Weekly Summary Tab', () => {
    it('should show weekly summary table', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Weekly Summary')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /weekly summary/i }));

      await waitFor(() => {
        expect(screen.getByText('Days Worked')).toBeInTheDocument();
        expect(screen.getByText('5')).toBeInTheDocument();
      });
    });

    it('should show empty state when no data', { timeout: 10000 }, async () => {
      const user = userEvent.setup();
      mockGetWeeklySummary.mockResolvedValue([]);
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Weekly Summary')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /weekly summary/i }));

      await waitFor(() => {
        expect(screen.getByText('No data for this week')).toBeInTheDocument();
      });
    });
  });

  describe('Refresh functionality', () => {
    it('should reload data when refresh clicked', { timeout: 10000 }, async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Refresh')).toBeInTheDocument();
      });

      // Clear call counts after initial load
      mockGetTeamStatus.mockClear();
      mockGetDailyHours.mockClear();
      mockGetWeeklySummary.mockClear();

      await user.click(screen.getByText('Refresh'));

      await waitFor(() => {
        expect(mockGetTeamStatus).toHaveBeenCalled();
        expect(mockGetDailyHours).toHaveBeenCalled();
        expect(mockGetWeeklySummary).toHaveBeenCalled();
      });
    });
  });

  describe('Export functionality', () => {
    it('should call export API when export clicked', async () => {
      const user = userEvent.setup();
      const mockBlob = new Blob(['test'], { type: 'text/csv' });
      mockExportTimesheet.mockResolvedValue(mockBlob);

      // Mock URL.createObjectURL and URL.revokeObjectURL
      const createObjectURL = vi.fn().mockReturnValue('blob:test');
      const revokeObjectURL = vi.fn();
      global.URL.createObjectURL = createObjectURL;
      global.URL.revokeObjectURL = revokeObjectURL;

      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Export CSV')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Export CSV'));

      await waitFor(() => {
        expect(mockExportTimesheet).toHaveBeenCalled();
      });
    });

    it('should handle export failure gracefully', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockExportTimesheet.mockRejectedValue(new Error('Export failed'));

      render(<AdminPage />);

      // Wait for data to load first (team members visible)
      await waitFor(() => {
        expect(screen.getByText('alice')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Export CSV'));

      // Verify error was logged
      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Export failed:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Loading state', () => {
    it('should show loading indicator while loading', async () => {
      // Make the API calls hang
      mockGetTeamStatus.mockImplementation(() => new Promise(() => {}));

      render(<AdminPage />);

      // The loader should be visible initially
      await waitFor(() => {
        const loader = document.querySelector('.animate-spin');
        expect(loader).toBeInTheDocument();
      });
    });
  });

  describe('Error handling', () => {
    it('should handle API errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockGetTeamStatus.mockRejectedValue(new Error('API Error'));

      render(<AdminPage />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalled();
      });

      consoleSpy.mockRestore();
    });

    it('should handle daily hours load error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockGetDailyHours.mockRejectedValue(new Error('Daily hours error'));

      render(<AdminPage />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to load daily hours:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('should handle weekly summary load error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockGetWeeklySummary.mockRejectedValue(new Error('Weekly summary error'));

      render(<AdminPage />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to load weekly summary:',
          expect.any(Error)
        );
      });

      consoleSpy.mockRestore();
    });

    it('should log errors when loadAllData fails', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      // Make all API calls fail to trigger the catch block in loadAllData
      mockGetTeamStatus.mockRejectedValue(new Error('Team status failed'));
      mockGetDailyHours.mockRejectedValue(new Error('Daily hours failed'));
      mockGetWeeklySummary.mockRejectedValue(new Error('Weekly failed'));

      render(<AdminPage />);

      await waitFor(() => {
        // The error console logs should be called
        expect(consoleSpy).toHaveBeenCalled();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Tab navigation', () => {
    it('should switch to Team Status tab', async () => {
      const user = userEvent.setup();
      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText('Team Status')).toBeInTheDocument();
      });

      // Click on Team Status tab (should be default but click to ensure coverage)
      await user.click(screen.getByText('Team Status'));

      await waitFor(() => {
        expect(screen.getByText('alice')).toBeInTheDocument();
      });
    });
  });
});
