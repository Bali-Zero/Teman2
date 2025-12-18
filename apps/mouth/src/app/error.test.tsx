import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
// Import with alias to avoid conflict with built-in Error class
import ErrorPage from './error';

describe('Error', () => {
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

  beforeEach(() => {
    consoleErrorSpy.mockClear();
  });

  afterAll(() => {
    consoleErrorSpy.mockRestore();
  });

  it('should render error message', () => {
    const mockError = new Error('Test error') as Error & { digest?: string };
    const mockReset = vi.fn();

    render(<ErrorPage error={mockError} reset={mockReset} />);

    expect(screen.getByText('Something went wrong!')).toBeInTheDocument();
    expect(
      screen.getByText('We apologize for the inconvenience. An unexpected error has occurred.')
    ).toBeInTheDocument();
  });

  it('should render try again button', () => {
    const mockError = new Error('Test error') as Error & { digest?: string };
    const mockReset = vi.fn();

    render(<ErrorPage error={mockError} reset={mockReset} />);

    const tryAgainButton = screen.getByText('Try again');
    expect(tryAgainButton).toBeInTheDocument();
  });

  it('should render reload page button', () => {
    const mockError = new Error('Test error') as Error & { digest?: string };
    const mockReset = vi.fn();

    render(<ErrorPage error={mockError} reset={mockReset} />);

    const reloadButton = screen.getByText('Reload Page');
    expect(reloadButton).toBeInTheDocument();
  });

  it('should call reset when try again button is clicked', async () => {
    const user = userEvent.setup();
    const mockError = new Error('Test error') as Error & { digest?: string };
    const mockReset = vi.fn();

    render(<ErrorPage error={mockError} reset={mockReset} />);

    const tryAgainButton = screen.getByText('Try again');
    await user.click(tryAgainButton);

    expect(mockReset).toHaveBeenCalledTimes(1);
  });

  it('should log error to console', () => {
    const mockError = new Error('Test error');
    const mockReset = vi.fn();

    render(<ErrorPage error={mockError} reset={mockReset} />);

    expect(consoleErrorSpy).toHaveBeenCalledWith(mockError);
  });

  it('should handle error with digest', () => {
    const mockError = { message: 'Test error', digest: 'abc123' } as Error & { digest?: string };
    const mockReset = vi.fn();

    render(<ErrorPage error={mockError} reset={mockReset} />);

    expect(screen.getByText('Something went wrong!')).toBeInTheDocument();
  });

  it('should render error icon', () => {
    const mockError = new Error('Test error') as Error & { digest?: string };
    const mockReset = vi.fn();

    const { container } = render(<ErrorPage error={mockError} reset={mockReset} />);

    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });
});
