import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MessageBubble } from './MessageBubble';
import React from 'react';

// Mock the hooks used in MessageBubble
vi.mock('@/hooks/useChatLocale', () => ({
  useChatLocale: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/lib/utils', () => ({
  cn: (...inputs: any[]) => inputs.filter(Boolean).join(' '),
  formatMessageTime: (date: Date) => '12:00 PM',
}));

describe('MessageBubble', () => {
  const mockOnFollowUpClick = vi.fn();
  const mockOnSetInput = vi.fn();
  const mockOnOpenSearchDocs = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const defaultProps = {
    message: {
      id: '1',
      role: 'assistant' as const,
      content: 'Hello world',
      timestamp: new Date(),
    },
    onFollowUpClick: mockOnFollowUpClick,
    onSetInput: mockOnSetInput,
    onOpenSearchDocs: mockOnOpenSearchDocs,
  };

  it('renders semantic list for follow-up questions', () => {
    const messageWithFollowUps = {
      ...defaultProps.message,
      metadata: {
        followup_questions: ['Question 1', 'Question 2'],
      },
    };

    render(<MessageBubble {...defaultProps} message={messageWithFollowUps} />);

    const list = screen.getByRole('list');
    expect(list).toBeDefined();
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('Question 1')).toBeDefined();
    expect(screen.getByText('Question 2')).toBeDefined();
  });

  it('renders semantic list for thinking steps', () => {
    const messageWithSteps = {
      ...defaultProps.message,
      steps: [
        { id: '1', type: 'status' as const, data: 'Step 1' },
      ] as any,
    };

    render(<MessageBubble {...defaultProps} message={messageWithSteps} />);

    // Open thinking process
    const toggleButton = screen.getByText('thinkingProcess');
    fireEvent.click(toggleButton);

    const list = screen.getByRole('list');
    expect(list).toBeDefined();
    expect(screen.getByText('Step 1')).toBeDefined();
  });

  it('updates copy button aria-label after clicking', async () => {
    // Mock navigator.clipboard.writeText
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: mockWriteText,
      },
    });

    render(<MessageBubble {...defaultProps} />);

    const copyButton = screen.getByLabelText('copyMessage');
    expect(copyButton).toBeDefined();

    fireEvent.click(copyButton);

    expect(mockWriteText).toHaveBeenCalledWith('Hello world');

    // Check if aria-label updated
    await waitFor(() => {
      expect(screen.getByLabelText('messageCopied')).toBeDefined();
    });
  });

  it('uses chevron icon with rotation for thinking process toggle', () => {
    const messageWithSteps = {
      ...defaultProps.message,
      steps: [
        { id: '1', type: 'status' as const, data: 'Step 1' },
      ] as any,
    };

    render(<MessageBubble {...defaultProps} message={messageWithSteps} />);

    const chevron = screen.getByTestId('thinking-chevron');
    expect(chevron.getAttribute('class')).toContain('-rotate-90');

    fireEvent.click(screen.getByText('thinkingProcess'));

    expect(chevron.getAttribute('class')).toContain('rotate-0');
  });
});
