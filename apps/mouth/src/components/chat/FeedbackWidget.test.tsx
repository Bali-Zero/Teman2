import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { FeedbackWidget } from './FeedbackWidget';

describe('FeedbackWidget', () => {
  const mockLocalStorage = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  };
  const mockAlert = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('localStorage', mockLocalStorage);
    vi.stubGlobal('alert', mockAlert);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it('should not render when turnCount is less than 8', () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    const { container } = render(<FeedbackWidget sessionId="test-session" turnCount={5} />);
    expect(container.firstChild).toBeNull();
  });

  it('should render when turnCount is 8 or more', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/How is your experience?/)).toBeInTheDocument();
    });
  });

  it('should not render if feedback already submitted', () => {
    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'zantara_feedback_submitted') return 'true';
      return null;
    });

    const { container } = render(<FeedbackWidget sessionId="test-session" turnCount={10} />);
    expect(container.firstChild).toBeNull();
  });

  it('should not render if feedback already dismissed', () => {
    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'zantara_feedback_dismissed') return 'true';
      return null;
    });

    const { container } = render(<FeedbackWidget sessionId="test-session" turnCount={10} />);
    expect(container.firstChild).toBeNull();
  });

  it('should show feedback type buttons', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText("It's going well")).toBeInTheDocument();
      expect(screen.getByText('I had some issues')).toBeInTheDocument();
      expect(screen.getByText('I found a bug')).toBeInTheDocument();
    });
  });

  it('should allow selecting feedback type', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/How is your experience?/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("It's going well"));
  });

  it('should allow typing message', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await user.click(screen.getByText("It's going well"));
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Tell us more...')).toBeInTheDocument();
    });
    const textarea = screen.getByPlaceholderText('Tell us more...');
    await user.type(textarea, 'Test feedback message');

    expect(textarea).toHaveValue('Test feedback message');
  });

  it('should handle dismiss', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/How is your experience?/)).toBeInTheDocument();
    });

    const closeButton = screen.getByLabelText('Dismiss feedback');
    await user.click(closeButton);

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('zantara_feedback_dismissed', 'true');
  });

  it('should submit feedback successfully', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    // Mock fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/How is your experience?/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("It's going well"));

    // Type message (optional)
    const textarea = screen.getByPlaceholderText('Tell us more...');
    await user.type(textarea, 'Great service!');

    // Submit
    const submitButton = screen.getByText('Send Feedback');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('zantara_feedback_submitted', 'true');
    });
  });

  it('should submit without message (optional)', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    // Mock fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/How is your experience?/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("It's going well"));

    // Submit without typing message
    const submitButton = screen.getByText('Send Feedback');
    await user.click(submitButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });
  });

  it('should handle submit error', async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockLocalStorage.getItem.mockReturnValue(null);

    // Mock fetch to fail
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/How is your experience?/)).toBeInTheDocument();
    });

    await user.click(screen.getByText("It's going well"));

    const submitButton = screen.getByText('Send Feedback');
    await user.click(submitButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });
});
