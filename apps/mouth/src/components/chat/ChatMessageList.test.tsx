import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatMessageList, ChatMessageListProps } from './ChatMessageList';
import { createRef } from 'react';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => children,
}));

// Mock MessageBubble
vi.mock('./MessageBubble', () => ({
  MessageBubble: ({ message, onFollowUpClick }: { message: { content: string }; onFollowUpClick?: (q: string) => void }) => (
    <div data-testid="message-bubble">
      <span>{message.content}</span>
      {onFollowUpClick && (
        <button onClick={() => onFollowUpClick('follow-up')}>Follow Up</button>
      )}
    </div>
  ),
}));

// Mock ThinkingIndicator
vi.mock('./ThinkingIndicator', () => ({
  ThinkingIndicator: ({ isVisible }: { isVisible: boolean }) =>
    isVisible ? <div data-testid="thinking-indicator">Thinking...</div> : null,
}));

describe('ChatMessageList', () => {
  const defaultProps: ChatMessageListProps = {
    messages: [],
    isLoading: false,
    thinkingElapsedTime: 0,
    userAvatar: null,
    messagesEndRef: createRef<HTMLDivElement>(),
    onFollowUpClick: vi.fn(),
    onSetInput: vi.fn(),
    onOpenSearchDocs: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Empty state (Welcome screen)', () => {
    it('should show welcome screen when no messages', () => {
      render(<ChatMessageList {...defaultProps} messages={[]} />);

      expect(screen.getByText('Zantara')).toBeInTheDocument();
      expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
    });

    it('should render logo in empty state', () => {
      render(<ChatMessageList {...defaultProps} />);
      expect(screen.getByAltText('Zantara Logo')).toBeInTheDocument();
    });

    it('should render quick action buttons', () => {
      render(<ChatMessageList {...defaultProps} />);

      expect(screen.getByText('What can you do?')).toBeInTheDocument();
      expect(screen.getByText('My Tasks')).toBeInTheDocument();
      expect(screen.getByText('Search docs')).toBeInTheDocument();
    });

    it('should call onSetInput when quick action clicked', async () => {
      const user = userEvent.setup();
      render(<ChatMessageList {...defaultProps} />);

      await user.click(screen.getByText('What can you do?'));
      expect(defaultProps.onSetInput).toHaveBeenCalledWith('What can you help me with?');
    });

    it('should call onOpenSearchDocs when search clicked', async () => {
      const user = userEvent.setup();
      render(<ChatMessageList {...defaultProps} />);

      await user.click(screen.getByText('Search docs'));
      expect(defaultProps.onOpenSearchDocs).toHaveBeenCalledTimes(1);
    });
  });

  describe('Messages rendering', () => {
    const mockMessages = [
      { id: '1', role: 'user' as const, content: 'Hello', timestamp: new Date() },
      { id: '2', role: 'assistant' as const, content: 'Hi there!', timestamp: new Date() },
    ];

    it('should render messages when present', () => {
      render(<ChatMessageList {...defaultProps} messages={mockMessages} />);

      expect(screen.getByText('Hello')).toBeInTheDocument();
      expect(screen.getByText('Hi there!')).toBeInTheDocument();
    });

    it('should render MessageBubble for each message', () => {
      render(<ChatMessageList {...defaultProps} messages={mockMessages} />);

      const bubbles = screen.getAllByTestId('message-bubble');
      expect(bubbles).toHaveLength(2);
    });

    it('should not show welcome screen when messages exist', () => {
      render(<ChatMessageList {...defaultProps} messages={mockMessages} />);

      expect(screen.queryByText('Garda Depan Leluhur')).not.toBeInTheDocument();
    });
  });

  describe('Empty assistant placeholder', () => {
    it('should skip empty assistant message placeholder while loading', () => {
      const messagesWithPlaceholder = [
        { id: '1', role: 'user' as const, content: 'Hello', timestamp: new Date() },
        { id: '2', role: 'assistant' as const, content: '', timestamp: new Date() },
      ];

      render(
        <ChatMessageList
          {...defaultProps}
          messages={messagesWithPlaceholder}
          isLoading={true}
        />
      );

      const bubbles = screen.getAllByTestId('message-bubble');
      expect(bubbles).toHaveLength(1);
    });

    it('should show non-empty assistant message even while loading', () => {
      const messages = [
        { id: '1', role: 'user' as const, content: 'Hello', timestamp: new Date() },
        { id: '2', role: 'assistant' as const, content: 'Response', timestamp: new Date() },
      ];

      render(<ChatMessageList {...defaultProps} messages={messages} isLoading={true} />);

      expect(screen.getByText('Response')).toBeInTheDocument();
    });
  });

  describe('ThinkingIndicator', () => {
    it('should show thinking indicator when loading', () => {
      const messages = [
        { id: '1', role: 'user' as const, content: 'Hello', timestamp: new Date() },
      ];

      render(<ChatMessageList {...defaultProps} messages={messages} isLoading={true} />);

      expect(screen.getByTestId('thinking-indicator')).toBeInTheDocument();
    });

    it('should not show thinking indicator when not loading', () => {
      const messages = [
        { id: '1', role: 'user' as const, content: 'Hello', timestamp: new Date() },
      ];

      render(<ChatMessageList {...defaultProps} messages={messages} isLoading={false} />);

      expect(screen.queryByTestId('thinking-indicator')).not.toBeInTheDocument();
    });
  });

  describe('Follow-up interaction', () => {
    it('should pass onFollowUpClick to MessageBubble', async () => {
      const user = userEvent.setup();
      const messages = [
        { id: '1', role: 'assistant' as const, content: 'Response', timestamp: new Date() },
      ];

      render(<ChatMessageList {...defaultProps} messages={messages} />);

      await user.click(screen.getByText('Follow Up'));
      expect(defaultProps.onFollowUpClick).toHaveBeenCalledWith('follow-up');
    });
  });
});
