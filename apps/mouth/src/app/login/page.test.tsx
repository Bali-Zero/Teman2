import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { waitFor, fireEvent } from '@testing-library/dom';
import userEvent from '@testing-library/user-event';
import LoginPage from './page';

// Mock the api module
const mockLogin = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    login: (...args: unknown[]) => mockLogin(...args),
  },
}));

// Mock useRouter
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render login form', () => {
    render(<LoginPage />);

    expect(screen.getAllByText(/Unlock/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Unleash Potential/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText(/Pin/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('should render logo', () => {
    render(<LoginPage />);

    const logo = screen.getByAltText('Zantara Logo');
    expect(logo).toBeInTheDocument();
  });

  it('should have disabled submit button initially', () => {
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: /sign in/i });
    expect(submitButton).toBeDisabled();
  });

  it('should enable submit button when email and 6-digit PIN are entered', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '123456');

    expect(submitButton).not.toBeDisabled();
  });

  it('should keep submit button disabled with less than 6-digit PIN', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '12345'); // Only 5 digits

    expect(submitButton).toBeDisabled();
  });

  it('should only allow numeric input in PIN field', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const pinInput = screen.getByLabelText(/Pin/i) as HTMLInputElement;

    await user.type(pinInput, 'abc123def456');

    // Should only contain numbers
    expect(pinInput.value).toBe('123456');
  });

  it('should limit PIN to 6 characters', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const pinInput = screen.getByLabelText(/Pin/i) as HTMLInputElement;

    await user.type(pinInput, '12345678');

    expect(pinInput.value).toBe('123456');
  });

  it('should call login API on form submit', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce({
      access_token: 'token',
      user: { id: '1', email: 'test@example.com', name: 'Test', role: 'user' },
    });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '123456');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('test@example.com', '123456');
    });
  });

  it('should redirect to /chat on successful login', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce({
      access_token: 'token',
      user: { id: '1', email: 'test@example.com', name: 'Test', role: 'user' },
    });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '123456');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/chat');
    });
  });

  it('should display error message on login failure', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'));

    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '123456');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });

  it('should show loading state while submitting', async () => {
    const user = userEvent.setup();
    // Create a promise that won't resolve immediately
    let resolveLogin: (value: unknown) => void;
    mockLogin.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveLogin = resolve;
        })
    );

    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '123456');
    await user.click(submitButton);

    // Should show loading state
    expect(screen.getByText('Signing in...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled();

    // Resolve the login
    resolveLogin!({
      access_token: 'token',
      user: { id: '1', email: 'test@example.com', name: 'Test', role: 'user' },
    });

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/chat');
    });
  });

  it('should have proper aria-label on submit button', () => {
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: /sign in to your account/i });
    expect(submitButton).toBeInTheDocument();
  });

  it('should have email input with correct type and autocomplete', () => {
    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    expect(emailInput).toHaveAttribute('type', 'email');
    expect(emailInput).toHaveAttribute('autocomplete', 'email');
  });

  it('should have PIN input with password type and numeric inputMode', () => {
    render(<LoginPage />);

    const pinInput = screen.getByLabelText(/Pin/i);
    expect(pinInput).toHaveAttribute('type', 'password');
    expect(pinInput).toHaveAttribute('inputmode', 'numeric');
  });

  it('should clear error when resubmitting', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce(new Error('First error')).mockResolvedValueOnce({
      access_token: 'token',
      user: { id: '1', email: 'test@example.com', name: 'Test', role: 'user' },
    });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    // First submit - should fail
    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '123456');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('First error')).toBeInTheDocument();
    });

    // Second submit - error should clear
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.queryByText('First error')).not.toBeInTheDocument();
    });
  });

  it('should render footer text', () => {
    render(<LoginPage />);

    expect(screen.getByText('Bali Zero @2020')).toBeInTheDocument();
  });

  it('should handle Enter key to submit form', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce({
      access_token: 'token',
      user: { id: '1', email: 'test@example.com', name: 'Test', role: 'user' },
    });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText('Email');
    const pinInput = screen.getByLabelText(/Pin/i);

    await user.type(emailInput, 'test@example.com');
    await user.type(pinInput, '123456');

    // Press Enter while focused on PIN input
    fireEvent.submit(pinInput.closest('form')!);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('test@example.com', '123456');
    });
  });
});
