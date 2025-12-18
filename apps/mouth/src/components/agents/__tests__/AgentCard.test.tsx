import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { AgentCard } from '../AgentCard';

describe('AgentCard', () => {
  const mockOnRun = vi.fn();

  const defaultProps = {
    name: 'Test Agent',
    description: 'Test description',
    status: 'running' as const,
    successRate: 95.5,
    totalRuns: 100,
    onRun: mockOnRun,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders agent name and description', () => {
      render(<AgentCard {...defaultProps} />);

      expect(screen.getByText('Test Agent')).toBeInTheDocument();
      expect(screen.getByText('Test description')).toBeInTheDocument();
    });

    it('displays success rate and total runs when provided', () => {
      render(<AgentCard {...defaultProps} />);

      expect(screen.getByText(/Success: 95\.5%/)).toBeInTheDocument();
      expect(screen.getByText(/Total runs: 100/)).toBeInTheDocument();
    });

    it('does not display metrics when not provided', () => {
      const { container } = render(
        <AgentCard name="Test" description="Test" status="idle" />
      );

      expect(screen.queryByText(/Success:/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Total runs:/)).not.toBeInTheDocument();
    });
  });

  describe('Status Indicators', () => {
    it('displays green indicator for running status', () => {
      const { container } = render(<AgentCard {...defaultProps} status="running" />);
      const indicator = container.querySelector('.bg-green-500');
      expect(indicator).toBeInTheDocument();
    });

    it('displays yellow indicator for idle status', () => {
      const { container } = render(<AgentCard {...defaultProps} status="idle" />);
      const indicator = container.querySelector('.bg-yellow-500');
      expect(indicator).toBeInTheDocument();
    });

    it('displays red indicator for error status', () => {
      const { container } = render(<AgentCard {...defaultProps} status="error" />);
      const indicator = container.querySelector('.bg-red-500');
      expect(indicator).toBeInTheDocument();
    });
  });

  describe('Latest Results', () => {
    it('displays latest result data when provided', () => {
      const latestResult = {
        conversations_analyzed: 47,
        improvements_generated: 3,
      };

      render(<AgentCard {...defaultProps} latestResult={latestResult} />);

      expect(screen.getByText('Latest result')).toBeInTheDocument();
      expect(screen.getByText(/conversations_analyzed:/i)).toBeInTheDocument();
      expect(screen.getByText('47')).toBeInTheDocument();
    });

    it('limits display to 6 result items', () => {
      const latestResult = {
        item1: 1,
        item2: 2,
        item3: 3,
        item4: 4,
        item5: 5,
        item6: 6,
        item7: 7, // Should not be displayed
        item8: 8, // Should not be displayed
      };

      const { container } = render(
        <AgentCard {...defaultProps} latestResult={latestResult} />
      );

      const resultItems = container.querySelectorAll('.grid > div');
      expect(resultItems).toHaveLength(6);
    });

    it('does not display results section when no data', () => {
      render(<AgentCard {...defaultProps} />);
      expect(screen.queryByText('Latest result')).not.toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('calls onRun when Run button is clicked', () => {
      render(<AgentCard {...defaultProps} />);

      const runButton = screen.getByRole('button', { name: /run/i });
      fireEvent.click(runButton);

      expect(mockOnRun).toHaveBeenCalledTimes(1);
    });

    it('does not render Run button when onRun is not provided', () => {
      render(<AgentCard {...defaultProps} onRun={undefined} />);

      expect(screen.queryByRole('button', { name: /run/i })).not.toBeInTheDocument();
    });

    it('renders Details button', () => {
      render(<AgentCard {...defaultProps} />);

      const detailsButton = screen.getByLabelText('Details');
      expect(detailsButton).toBeInTheDocument();
    });
  });

  describe('Props Variants', () => {
    it('handles agent object prop format', () => {
      const agentProp = {
        agent: {
          name: 'Agent Object Test',
          description: 'Testing object format',
          status: 'running' as const,
          success_rate: 98,
          total_runs: 50,
          latest_result: { test: 'value' },
        },
        onRun: mockOnRun,
      };

      render(<AgentCard {...agentProp} />);

      expect(screen.getByText('Agent Object Test')).toBeInTheDocument();
      expect(screen.getByText(/Success: 98\.0%/)).toBeInTheDocument();
    });

    it('uses default values when name/description are missing', () => {
      render(<AgentCard status="idle" />);

      expect(screen.getByText('Agent')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper aria-label for Details button', () => {
      render(<AgentCard {...defaultProps} />);

      const detailsButton = screen.getByLabelText('Details');
      expect(detailsButton).toHaveAttribute('aria-label', 'Details');
    });

    it('truncates long text properly', () => {
      const longName = 'This is a very long agent name that should be truncated';
      const { container } = render(
        <AgentCard {...defaultProps} name={longName} />
      );

      const nameElement = screen.getByText(longName);
      expect(nameElement).toHaveClass('truncate');
    });
  });
});
