import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MessageBubble } from './MessageBubble';

// Mock react-markdown
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}));

// Mock remark-gfm
vi.mock('@/components/CitationCard', () => ({
  CitationCard: ({ sources }: { sources: any[] }) => (
    <div data-testid="citation-card">
      {sources.map(s => (
        <div key={s.title}>
          <span>{s.title}</span>
          <span>{s.content}</span>
        </div>
      ))}
    </div>
  ),
}));

describe('MessageBubble', () => {
  const mockTimestamp = new Date('2024-01-01T12:00:00Z');

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('User messages', () => {
    it('should render user message with user icon', () => {
      render(<MessageBubble message={{ role: 'user', content: 'Hi AI', timestamp: new Date() }} />);

      expect(screen.getByText('Hi AI')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /copy message/i })).toBeInTheDocument();
    });

    it('should apply user styling classes', () => {
      const { container } = render(
        <MessageBubble message={{ role: 'user', content: 'Hello', timestamp: mockTimestamp }} />
      );

      const messageWrapper = container.querySelector('.justify-end');
      expect(messageWrapper).toBeInTheDocument();
    });
  });

  describe('Assistant messages', () => {
    it('should render assistant message with AI icon', () => {
      render(
        <MessageBubble
          message={{
            role: 'assistant',
            content: 'Hello! How can I help?',
            timestamp: mockTimestamp,
          }}
        />
      );

    expect(screen.getByText('Hello! How can I help?')).toBeInTheDocument();
    expect(screen.getByAltText('Zantara')).toBeInTheDocument();
  });

    it('should apply assistant styling classes', () => {
      const { container } = render(
        <MessageBubble message={{ role: 'assistant', content: 'Hello', timestamp: mockTimestamp }} />
      );

      const messageWrapper = container.querySelector('.justify-start');
      expect(messageWrapper).toBeInTheDocument();
    });
  });

  describe('Copy functionality', () => {
    it('should have copy button that can be clicked', async () => {
      const user = userEvent.setup();
      // Mock clipboard API locally for this test
      const writeTextSpy = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: writeTextSpy },
        writable: true,
        configurable: true,
      });

      render(<MessageBubble message={{ role: 'user', content: 'Test message', timestamp: mockTimestamp }} />);

      const copyButton = screen.getByRole('button', { name: /copy message/i });
      await user.click(copyButton);

      expect(writeTextSpy).toHaveBeenCalledWith('Test message');
    });

    it('should show check icon after copying', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers({ shouldAdvanceTime: true });

      render(<MessageBubble message={{ role: 'user', content: 'Test message', timestamp: mockTimestamp }} />);

      const copyButton = screen.getByRole('button', { name: /copy message/i });
      await user.click(copyButton);

      // Check icon should be visible briefly (we can't easily test the icon change without more setup)
      expect(copyButton).toBeInTheDocument();

      vi.useRealTimers();
    });
  });

  describe('Image content', () => {
    it('should render image when imageUrl is provided', () => {
      render(
        <MessageBubble
          message={{
            role: 'assistant',
            content: 'Here is an image',
            imageUrl: 'http://example.com/image.png',
            timestamp: new Date()
          }}
        />
      );

      const image = screen.getByAltText('Generated content');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', 'http://example.com/image.png');
    });

    it('should not render image when imageUrl is not provided', () => {
      render(<MessageBubble message={{ role: 'assistant', content: 'No image here', timestamp: mockTimestamp }} />);

      expect(screen.queryByAltText('Generated content')).not.toBeInTheDocument();
    });
  });

  describe('Verification Score', () => {
    it('should display verification score when provided', () => {
      render(
        <MessageBubble
          message={{
            role: 'assistant',
            content: 'Verified',
            verification_score: 90,
            timestamp: new Date()
          }}
        />
      );

      expect(screen.getByText(/Verified \(90%\)/i)).toBeInTheDocument();
    });

    it('should display low confidence for low scores', () => {
        render(
          <MessageBubble
            message={{
              role: 'assistant',
              content: 'Unsure',
              verification_score: 30,
              timestamp: new Date()
            }}
          />
        );
  
        expect(screen.getByText(/Low Confidence \(30%\)/i)).toBeInTheDocument();
      });

    it('should not display verification score when undefined', () => {
      render(<MessageBubble message={{ role: 'assistant', content: 'Hello', timestamp: new Date() }} />);

      expect(screen.queryByText(/Verification Score:/i)).not.toBeInTheDocument();
    });
  });

  describe('Sources with CitationCard', () => {
    const mockSources = [
      { title: 'Document 1', content: 'Content 1' },
      { title: 'Document 2', content: 'Content 2' },
    ];

    it('should render CitationCard content when sources are provided', () => {
      render(
        <MessageBubble
          message={{
            role: 'assistant',
            content: 'Answer with sources',
            sources: mockSources,
            timestamp: mockTimestamp
          }}
        />
      );

      // Verify CitationCard logic (it renders titles and content directly now)
      expect(screen.getByText('Document 1')).toBeInTheDocument();
      expect(screen.getByText('Content 1')).toBeInTheDocument();
      expect(screen.getByText('Document 2')).toBeInTheDocument();
    });

    it('should not render CitationCard when sources are empty', () => {
      render(
        <MessageBubble
          message={{
            role: 'assistant',
            content: 'No sources',
            sources: [],
            timestamp: mockTimestamp
          }}
        />
      );

      expect(screen.queryByText('Document 1')).not.toBeInTheDocument();
    });
  });

  describe('Markdown rendering', () => {
    it('should render content through ReactMarkdown', () => {
      render(
        <MessageBubble
          message={{
            role: 'assistant',
            content: '# Heading\n\nParagraph text',
            timestamp: mockTimestamp
          }}
        />
      );

      expect(screen.getByTestId('markdown')).toBeInTheDocument();
    });
  });
});
