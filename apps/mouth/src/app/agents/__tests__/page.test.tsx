import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, Mock } from 'vitest';
import { useRouter } from 'next/navigation';
import AgentsPage from '../page';
import { api } from '@/lib/api';

// Mock dependencies
vi.mock('next/navigation', () => ({
  useRouter: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  api: {
    isAuthenticated: vi.fn(),
    client: {
      autonomousTier1: {
        getAutonomousAgentsStatusApiAutonomousAgentsStatusGet: vi.fn(),
        getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet: vi.fn(),
        runConversationTrainerApiAutonomousAgentsConversationTrainerRunPost: vi.fn(),
        runClientValuePredictorApiAutonomousAgentsClientValuePredictorRunPost: vi.fn(),
        runKnowledgeGraphBuilderApiAutonomousAgentsKnowledgeGraphBuilderRunPost: vi.fn(),
      },
    },
  },
}));

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}));

describe('AgentsPage', () => {
  const mockPush = vi.fn();
  const mockRouterValue = { push: mockPush };

  beforeEach(() => {
    vi.clearAllMocks();
    (useRouter as Mock).mockReturnValue(mockRouterValue);
    (api.isAuthenticated as Mock).mockReturnValue(true);
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Authentication', () => {
    it('redirects to login when not authenticated', () => {
      (api.isAuthenticated as Mock).mockReturnValue(false);

      render(<AgentsPage />);

      expect(mockPush).toHaveBeenCalledWith('/login');
    });

    it('loads data when authenticated', async () => {
      const mockAgentsResponse = Promise.resolve({});
      const mockSchedulerResponse = Promise.resolve({ is_running: true });

      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockReturnValue(mockAgentsResponse);
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockReturnValue(mockSchedulerResponse);

      render(<AgentsPage />);

      await waitFor(() => {
        expect(api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet).toHaveBeenCalled();
        expect(api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet).toHaveBeenCalled();
      });
    });
  });

  describe('Page Rendering', () => {
    beforeEach(async () => {
      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockResolvedValue({});
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockResolvedValue({ is_running: true });
    });

    it('renders page title', async () => {
      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Autonomous Agents Control Center')).toBeInTheDocument();
      });
    });

    it('renders subtitle', async () => {
      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Monitor and control autonomous background agents')).toBeInTheDocument();
      });
    });

    it('renders system status banner', async () => {
      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        expect(screen.getByText(/System Status: HEALTHY/)).toBeInTheDocument();
      });
    });

    it('renders all three agents', async () => {
      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Conversation Quality Trainer')).toBeInTheDocument();
        expect(screen.getByText('Client LTV Predictor')).toBeInTheDocument();
        expect(screen.getByText('Knowledge Graph Builder')).toBeInTheDocument();
      });
    });
  });

  describe('User Interactions', () => {
    beforeEach(() => {
      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockResolvedValue({});
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockResolvedValue({ is_running: true });
    });

    it('navigates back to chat when back button is clicked', async () => {
      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        const backButton = screen.getByLabelText('Back to chat');
        fireEvent.click(backButton);
      });

      expect(mockPush).toHaveBeenCalledWith('/chat');
    });

    it('refreshes data when refresh button is clicked', async () => {
      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        const refreshButton = screen.getByRole('button', { name: /refresh/i });
        expect(refreshButton).toBeInTheDocument();
      });

      const initialCalls = (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock).mock.calls.length;

      await act(async () => {
        const refreshButton = screen.getByRole('button', { name: /refresh/i });
        fireEvent.click(refreshButton);
      });

      await waitFor(() => {
        expect(api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet).toHaveBeenCalledTimes(initialCalls + 1);
      });
    });

    it('runs agent when Run button is clicked', async () => {
      (api.client.autonomousTier1.runConversationTrainerApiAutonomousAgentsConversationTrainerRunPost as Mock)
        .mockResolvedValue({});

      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        const runButtons = screen.getAllByRole('button', { name: /run/i });
        expect(runButtons.length).toBeGreaterThan(0);
      });

      await act(async () => {
        const runButtons = screen.getAllByRole('button', { name: /run/i });
        fireEvent.click(runButtons[0]); // Click first agent's run button
      });

      await waitFor(() => {
        expect(api.client.autonomousTier1.runConversationTrainerApiAutonomousAgentsConversationTrainerRunPost)
          .toHaveBeenCalledWith(7);
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error banner when API call fails', async () => {
      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockRejectedValue(new Error('API Error'));
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockResolvedValue({ is_running: true });

      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Failed to load agents status. Please try again.')).toBeInTheDocument();
      });
    });

    it('dismisses error when close button is clicked', async () => {
      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockRejectedValue(new Error('API Error'));
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockResolvedValue({ is_running: true });

      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        expect(screen.getByText('Failed to load agents status. Please try again.')).toBeInTheDocument();
      });

      const dismissButton = screen.getByLabelText('Dismiss error');
      fireEvent.click(dismissButton);

      await waitFor(() => {
        expect(screen.queryByText('Failed to load agents status. Please try again.')).not.toBeInTheDocument();
      });
    });

    it('displays error when agent run fails', async () => {
      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockResolvedValue({});
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockResolvedValue({ is_running: true });
      (api.client.autonomousTier1.runConversationTrainerApiAutonomousAgentsConversationTrainerRunPost as Mock)
        .mockRejectedValue(new Error('Run failed'));

      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        const runButtons = screen.getAllByRole('button', { name: /run/i });
        expect(runButtons.length).toBeGreaterThan(0);
      });

      await act(async () => {
        const runButtons = screen.getAllByRole('button', { name: /run/i });
        fireEvent.click(runButtons[0]);
      });

      await waitFor(() => {
        expect(screen.getByText(/Failed to run Conversation Quality Trainer/)).toBeInTheDocument();
      });
    });
  });

  describe('Auto-refresh', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    });

    it('auto-refreshes data every 30 seconds', async () => {
      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockResolvedValue({});
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockResolvedValue({ is_running: true });

      await act(async () => {
        render(<AgentsPage />);
      });

      const initialCalls = (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock).mock.calls.length;

      // Advance timers and run all pending timers
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });

      // After 30 seconds, should have been called one more time
      expect(api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet)
        .toHaveBeenCalledTimes(initialCalls + 1);
    }, 10000); // Increase timeout to 10s
  });

  describe('Agent Status Counts', () => {
    it('displays correct count of running agents', async () => {
      (api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet as Mock)
        .mockResolvedValue({});
      (api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet as Mock)
        .mockResolvedValue({ is_running: true });

      await act(async () => {
        render(<AgentsPage />);
      });

      await waitFor(() => {
        // Based on mock data: 2 running, 1 idle
        expect(screen.getByText('2 Running')).toBeInTheDocument();
        expect(screen.getByText('1 Idle')).toBeInTheDocument();
        expect(screen.getByText('0 Error')).toBeInTheDocument();
      });
    });
  });
});
