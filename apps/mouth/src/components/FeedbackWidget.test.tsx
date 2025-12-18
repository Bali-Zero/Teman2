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
      expect(screen.getByText(/Come sta andando la conversazione?/)).toBeInTheDocument();
    });
  });

  it('should not render if feedback already submitted', () => {
    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'feedbackSubmitted') return 'true';
      return null;
    });

    const { container } = render(<FeedbackWidget sessionId="test-session" turnCount={10} />);
    expect(container.firstChild).toBeNull();
  });

  it('should show feedback type buttons', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText('Sta andando bene')).toBeInTheDocument();
      expect(screen.getByText('Ho riscontrato problemi')).toBeInTheDocument();
      expect(screen.getByText('Ho trovato un bug')).toBeInTheDocument();
    });
  });

  it('should allow selecting feedback type', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/Come sta andando la conversazione?/)).toBeInTheDocument();
    });

    await user.click(screen.getByText('Sta andando bene'));
  });

  it('should allow typing message', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await user.click(screen.getByText('Sta andando bene'));
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Scrivi qui...')).toBeInTheDocument();
    });
    const textarea = screen.getByPlaceholderText('Scrivi qui...');
    await user.type(textarea, 'Test feedback message');

    expect(textarea).toHaveValue('Test feedback message');
  });

  it('should handle dismiss', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockReturnValue(null);

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/Come sta andando la conversazione?/)).toBeInTheDocument();
    });

    const closeButton = screen.getByLabelText('Dismiss feedback');
    await user.click(closeButton);

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith('feedbackDismissed', 'true');
  });

  it('should submit feedback successfully', async () => {
    const user = userEvent.setup();
    mockLocalStorage.getItem.mockImplementation((key) => {
      if (key === 'conversationFeedback') return '[]';
      return null;
    });

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/Come sta andando la conversazione?/)).toBeInTheDocument();
    });

    await user.click(screen.getByText('Sta andando bene'));

    // Type message
    const textarea = screen.getByPlaceholderText('Scrivi qui...');
    await user.type(textarea, 'Great service!');

    // Submit
    const submitButton = screen.getByText('Invia Feedback');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('feedbackSubmitted', 'true');
    });
  });

  it('should handle submit error', async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockLocalStorage.getItem.mockReturnValue(null);
    mockLocalStorage.setItem.mockImplementation(() => {
      throw new Error('localStorage error');
    });

    render(<FeedbackWidget sessionId="test-session" turnCount={8} />);

    await waitFor(() => {
      expect(screen.getByText(/Come sta andando la conversazione?/)).toBeInTheDocument();
    });

    // Try to submit (will fail due to localStorage error)
    await user.click(screen.getByText('Sta andando bene'));

    const textarea = screen.getByPlaceholderText('Scrivi qui...');
    await user.type(textarea, 'Test');

    const submitButton = screen.getByText('Invia Feedback');
    await user.click(submitButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });
});
