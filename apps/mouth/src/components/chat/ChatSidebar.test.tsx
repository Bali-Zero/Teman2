import { render, screen, fireEvent } from '@testing-library/react';
import { ChatSidebar } from './ChatSidebar';
import { describe, it, expect, vi } from 'vitest';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe('ChatSidebar Accessibility', () => {
  const mockProps = {
    isOpen: true,
    onClose: vi.fn(),
    onNewChat: vi.fn(),
    onConversationClick: vi.fn(),
    onDeleteConversation: vi.fn(),
    onSearchDocsOpen: vi.fn(),
    conversations: [
      { id: 1, title: 'Test Conv', created_at: '2023-01-01' }
    ],
    currentConversationId: null,
    isLoading: false,
  };

  it('renders conversation items with proper ARIA attributes', () => {
    render(<ChatSidebar {...mockProps} />);
    const convItem = screen.getByRole('button', { name: /Test Conv/i });
    expect(convItem).toBeInTheDocument();
    expect(convItem).toHaveAttribute('tabIndex', '0');
  });

  it('calls onConversationClick when Enter is pressed', () => {
    render(<ChatSidebar {...mockProps} />);
    const convItem = screen.getByRole('button', { name: /Test Conv/i });
    fireEvent.keyDown(convItem, { key: 'Enter' });
    expect(mockProps.onConversationClick).toHaveBeenCalledWith(1);
  });

  it('calls onConversationClick when Space is pressed', () => {
    render(<ChatSidebar {...mockProps} />);
    const convItem = screen.getByRole('button', { name: /Test Conv/i });
    fireEvent.keyDown(convItem, { key: ' ' });
    expect(mockProps.onConversationClick).toHaveBeenCalledWith(1);
  });

  it('delete button has aria-label', () => {
    render(<ChatSidebar {...mockProps} />);
    const deleteBtn = screen.getByLabelText('Delete conversation');
    expect(deleteBtn).toBeInTheDocument();
  });

  it('sets aria-current on active conversation', () => {
    render(<ChatSidebar {...mockProps} currentConversationId={1} />);
    const convItem = screen.getByRole('button', { name: /Test Conv/i });
    expect(convItem).toHaveAttribute('aria-current', 'true');
  });
});
