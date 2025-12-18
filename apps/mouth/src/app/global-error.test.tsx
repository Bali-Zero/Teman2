import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import GlobalError from './global-error';

const mockCaptureException = vi.fn();
const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

vi.mock('@sentry/nextjs', () => ({
  captureException: (error: Error) => mockCaptureException(error),
}));

describe('GlobalError', () => {
  const mockReset = vi.fn();
  const mockError = new Error('Test error');

  beforeEach(() => {
    vi.clearAllMocks();
    consoleErrorSpy.mockClear();
    consoleWarnSpy.mockClear();
  });

  afterAll(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  it('should render error message', () => {
    render(<GlobalError error={mockError} reset={mockReset} />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(
      screen.getByText("We've been notified and are working on fixing this.")
    ).toBeInTheDocument();
  });

  it('should render try again button', () => {
    render(<GlobalError error={mockError} reset={mockReset} />);

    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('should call reset when try again button is clicked', async () => {
    const user = userEvent.setup();
    render(<GlobalError error={mockError} reset={mockReset} />);

    await user.click(screen.getByRole('button', { name: /try again/i }));

    expect(mockReset).toHaveBeenCalledTimes(1);
  });

  it('should capture exception to Sentry on mount', () => {
    render(<GlobalError error={mockError} reset={mockReset} />);

    expect(mockCaptureException).toHaveBeenCalledWith(mockError);
  });

  it('should capture new exception when error changes', () => {
    const { rerender } = render(<GlobalError error={mockError} reset={mockReset} />);

    expect(mockCaptureException).toHaveBeenCalledTimes(1);

    const newError = new Error('New error');
    rerender(<GlobalError error={newError} reset={mockReset} />);

    expect(mockCaptureException).toHaveBeenCalledTimes(2);
    expect(mockCaptureException).toHaveBeenLastCalledWith(newError);
  });

  it('should handle error with digest property', () => {
    const errorWithDigest = Object.assign(new Error('Digest error'), { digest: 'abc123' });
    render(<GlobalError error={errorWithDigest} reset={mockReset} />);

    expect(mockCaptureException).toHaveBeenCalledWith(errorWithDigest);
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });
});
