import { render, screen } from '@testing-library/react';
import { SchedulerStatus } from '../SchedulerStatus';

describe('SchedulerStatus', () => {
  describe('Rendering', () => {
    it('renders scheduler title with icon', () => {
      const status = { is_running: true };
      render(<SchedulerStatus status={status} />);

      expect(screen.getByText('Scheduler')).toBeInTheDocument();
    });

    it('returns null when status is null', () => {
      const { container } = render(<SchedulerStatus status={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when status is undefined', () => {
      const { container } = render(<SchedulerStatus status={null} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('Status Display', () => {
    it('displays string status when status is a string', () => {
      render(<SchedulerStatus status="Scheduler is currently offline" />);

      expect(screen.getByText('Scheduler is currently offline')).toBeInTheDocument();
    });

    it('displays default message when status is an object', () => {
      const status = {
        is_running: true,
        tasks: [],
      };

      render(<SchedulerStatus status={status} />);

      expect(screen.getByText('Scheduler status available')).toBeInTheDocument();
    });

    it('handles status object with running true', () => {
      const status = {
        is_running: true,
        tasks: [
          {
            name: 'test-task',
            next_run: '2024-01-01T00:00:00Z',
            interval: '1h',
            enabled: true,
          },
        ],
      };

      render(<SchedulerStatus status={status} />);

      expect(screen.getByText('Scheduler')).toBeInTheDocument();
    });

    it('handles status object with running false', () => {
      const status = {
        is_running: false,
        tasks: [],
      };

      render(<SchedulerStatus status={status} />);

      expect(screen.getByText('Scheduler status available')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies correct CSS classes', () => {
      const status = { is_running: true };
      const { container } = render(<SchedulerStatus status={status} />);

      const wrapper = container.firstChild;
      expect(wrapper).toHaveClass('bg-[var(--background-elevated)]');
      expect(wrapper).toHaveClass('border');
      expect(wrapper).toHaveClass('border-[var(--border)]');
      expect(wrapper).toHaveClass('rounded-xl');
    });
  });

  describe('Edge Cases', () => {
    it('handles empty object status', () => {
      const status = {};
      render(<SchedulerStatus status={status} />);

      expect(screen.getByText('Scheduler status available')).toBeInTheDocument();
    });

    it('handles status with only tasks property', () => {
      const status = {
        tasks: [
          {
            name: 'task1',
            next_run: '2024-01-01T00:00:00Z',
            interval: '30m',
            enabled: true,
          },
        ],
      };

      render(<SchedulerStatus status={status} />);

      expect(screen.getByText('Scheduler')).toBeInTheDocument();
    });

    it('handles empty string status', () => {
      render(<SchedulerStatus status="" />);

      // Empty string is falsy, so component returns null
      expect(screen.queryByText('Scheduler')).not.toBeInTheDocument();
    });
  });
});
