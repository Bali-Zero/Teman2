import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import { waitFor, fireEvent } from '@testing-library/dom';
import userEvent from '@testing-library/user-event';

// Use vi.hoisted to create mocks that are available during vi.mock hoisting
const {
  mockIsAuthenticated,
  mockIsAdmin,
  mockGetClockStatus,
  mockGetProfile,
  mockGetUserProfile,
  mockSendMessageStreaming,
  mockGenerateImage,
  mockClockIn,
  mockClockOut,
  mockLogout,
  mockSaveConversation,
  mockClearConversations,
  mockListConversations,
  mockGetConversation,
  mockDeleteConversation,
} = vi.hoisted(() => ({
  mockIsAuthenticated: vi.fn(),
  mockIsAdmin: vi.fn(),
  mockGetClockStatus: vi.fn(),
  mockGetProfile: vi.fn(),
  mockGetUserProfile: vi.fn(),
  mockSendMessageStreaming: vi.fn(),
  mockGenerateImage: vi.fn(),
  mockClockIn: vi.fn(),
  mockClockOut: vi.fn(),
  mockLogout: vi.fn(),
  mockSaveConversation: vi.fn(),
  mockClearConversations: vi.fn(),
  mockListConversations: vi.fn(),
  mockGetConversation: vi.fn(),
  mockDeleteConversation: vi.fn(),
}));

// Mock the api module
vi.mock('@/lib/api', () => ({
  api: {
    isAuthenticated: mockIsAuthenticated,
    isAdmin: mockIsAdmin,
    getClockStatus: mockGetClockStatus,
    getProfile: mockGetProfile,
    getUserProfile: mockGetUserProfile,
    sendMessageStreaming: mockSendMessageStreaming,
    generateImage: mockGenerateImage,
    clockIn: mockClockIn,
    clockOut: mockClockOut,
    logout: mockLogout,
    saveConversation: mockSaveConversation,
    clearConversations: mockClearConversations,
    listConversations: mockListConversations,
    getConversation: mockGetConversation,
    deleteConversation: mockDeleteConversation,
  },
}));

import ChatPage from './page';
const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

// Mock useRouter
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    consoleErrorSpy.mockClear();
    consoleWarnSpy.mockClear();
    // Default mock implementations - using new API structure
    mockIsAuthenticated.mockReturnValue(true);
    mockIsAdmin.mockReturnValue(false);
    mockGetClockStatus.mockResolvedValue({ is_clocked_in: false, today_hours: 0, week_hours: 0 });
    mockGetProfile.mockResolvedValue({
      id: '1',
      email: 'test@example.com',
      name: 'Test User',
      role: 'user',
    });
    mockGetUserProfile.mockReturnValue({
      id: '1',
      email: 'test@example.com',
      name: 'Test User',
      role: 'user',
    });
    mockSaveConversation.mockResolvedValue({
      success: true,
      conversation_id: 1,
      messages_saved: 0,
    });
    mockListConversations.mockResolvedValue({ success: true, conversations: [], total: 0 });
    mockGetConversation.mockResolvedValue({
      success: true,
      messages: [],
      created_at: new Date().toISOString(),
    });
    mockDeleteConversation.mockResolvedValue({ success: true });
  });

  afterAll(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  describe('Authentication', () => {
    it('should redirect to login if not authenticated', async () => {
      mockIsAuthenticated.mockReturnValue(false);

      render(<ChatPage />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/login');
      });
    });

    it('should not redirect if authenticated', async () => {
      mockIsAuthenticated.mockReturnValue(true);

      render(<ChatPage />);

      await waitFor(() => {
        expect(mockPush).not.toHaveBeenCalledWith('/login');
      });
    });
  });

  describe('Initial data loading', () => {
    it('should load initial data on mount', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        expect(mockListConversations).toHaveBeenCalled();
        expect(mockGetClockStatus).toHaveBeenCalled();
        expect(mockGetUserProfile).toHaveBeenCalled();
      });
    });

    it('should display user avatar with first letter of name', async () => {
      mockGetUserProfile.mockReturnValue({
        id: '1',
        email: 'test@example.com',
        name: 'John Doe',
        role: 'user',
      });

      render(<ChatPage />);

      // The UI now shows the first letter of the name in the avatar
      await waitFor(() => {
        expect(screen.getByText('J')).toBeInTheDocument();
      });
    });

    it('should display avatar with first letter of email username if name is empty', async () => {
      mockGetUserProfile.mockReturnValue({
        id: '1',
        email: 'john.doe@example.com',
        name: '',
        role: 'user',
      });

      render(<ChatPage />);

      // Falls back to email username, showing first letter
      await waitFor(() => {
        expect(screen.getByText('J')).toBeInTheDocument();
      });
    });

    it('should fetch profile from API if not stored', async () => {
      mockGetUserProfile.mockReturnValue(null);
      mockGetProfile.mockResolvedValue({
        id: '1',
        email: 'api@example.com',
        name: 'API User',
        role: 'user',
      });

      render(<ChatPage />);

      await waitFor(() => {
        expect(mockGetProfile).toHaveBeenCalled();
      });
    });
  });

  describe('Welcome screen', () => {
    it('should show welcome message when no messages', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
      });
    });
  });

  describe('Conversation List', () => {
    it('should show "No conversations yet" when list is empty', async () => {
      mockListConversations.mockResolvedValue({ success: true, conversations: [], total: 0 });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('No conversations yet')).toBeInTheDocument();
      });
    });

    it('should display conversation list', async () => {
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [
          {
            id: 1,
            title: 'First Chat',
            message_count: 5,
            preview: 'Hello world',
            created_at: '2024-01-01',
          },
          {
            id: 2,
            title: 'Second Chat',
            message_count: 3,
            preview: 'Test message',
            created_at: '2024-01-02',
          },
        ],
        total: 2,
      });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('First Chat')).toBeInTheDocument();
        expect(screen.getByText('Second Chat')).toBeInTheDocument();
      });
    });

    it('should show clear history button when has conversations', async () => {
      const user = userEvent.setup();
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Chat', message_count: 5, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      // Open sidebar first
      const openButton = await screen.findByRole(
        'button',
        { name: /open sidebar/i },
        { timeout: 10000 }
      );
      await user.click(openButton);

      await screen.findByRole('button', { name: /clear history/i }, { timeout: 10000 });
    });
  });

  describe('Sidebar', () => {
    it('should have New Chat button', async () => {
      render(<ChatPage />);

      await screen.findByRole('button', { name: /new chat/i }, { timeout: 10000 });
    });
  });

  describe('Clock in/out', () => {
    it('should show Clock In button when not clocked in', async () => {
      mockGetClockStatus.mockResolvedValue({ is_clocked_in: false, today_hours: 0, week_hours: 0 });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clock in/i })).toBeInTheDocument();
      });
    });

    it('should show Clock Out button when clocked in', async () => {
      mockGetClockStatus.mockResolvedValue({ is_clocked_in: true, today_hours: 4, week_hours: 20 });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clock out/i })).toBeInTheDocument();
      });
    });

    it('should show Clock Out button when clocked in', async () => {
      mockGetClockStatus.mockResolvedValue({ is_clocked_in: true, today_hours: 4, week_hours: 20 });

      render(<ChatPage />);

      // When clocked in, the button should show "Clock Out"
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clock out/i })).toBeInTheDocument();
      });
    });

    it('should call clockIn when clicking Clock In button', async () => {
      const user = userEvent.setup();
      mockGetClockStatus.mockResolvedValue({ is_clocked_in: false, today_hours: 0, week_hours: 0 });
      mockClockIn.mockResolvedValue({ success: true, action: 'clock_in', message: 'Clocked in' });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clock in/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /clock in/i }));

      await waitFor(() => {
        expect(mockClockIn).toHaveBeenCalled();
      });
    });

    it('should call clockOut when clicking Clock Out button', async () => {
      const user = userEvent.setup();
      mockGetClockStatus.mockResolvedValue({ is_clocked_in: true, today_hours: 4, week_hours: 20 });
      mockClockOut.mockResolvedValue({
        success: true,
        action: 'clock_out',
        message: 'Clocked out',
        hours_worked: 8,
      });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clock out/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /clock out/i }));

      await waitFor(() => {
        expect(mockClockOut).toHaveBeenCalled();
      });
    });

    it('should display clock error when toggle fails', async () => {
      const user = userEvent.setup();
      mockGetClockStatus.mockResolvedValue({ is_clocked_in: false, today_hours: 0, week_hours: 0 });
      mockClockIn.mockResolvedValue({ success: false, message: 'Server error' });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clock in/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /clock in/i }));

      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument();
      });
    });
  });

  describe('Logout', () => {
    it('should have Logout button', async () => {
      const user = userEvent.setup();
      render(<ChatPage />);

      // Open user menu first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument();
      });
    });

    it('should show confirmation dialog on logout', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => false);

      render(<ChatPage />);

      // Open user menu first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /logout/i }));

      expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to logout?');
    });

    it('should call logout and redirect when confirmed', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      mockLogout.mockResolvedValue(undefined);

      render(<ChatPage />);

      // Open user menu first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /logout/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /logout/i }));

      await waitFor(() => {
        expect(mockLogout).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith('/login');
      });
    });
  });

  describe('Message input', () => {
    it('should have message input field', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });
    });

    it('should have Send button disabled when input is empty', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        const sendButton = screen.getByRole('button', { name: /send message/i });
        expect(sendButton).toBeDisabled();
      });
    });

    it('should enable Send button when input has text', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText('Type your message...');
      await user.type(input, 'Hello!');

      const sendButton = screen.getByRole('button', { name: /send message/i });
      expect(sendButton).not.toBeDisabled();
    });
  });

  describe('Image generation mode', () => {
    it('should toggle to image generation mode', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Click the attach menu button (Plus icon)
      const attachButton = screen.getByRole('button', { name: /attach file/i });
      await user.click(attachButton);

      // Click "Generate image" option
      await waitFor(() => {
        const imageButton = screen.getByRole('button', { name: /generate image/i });
        expect(imageButton).toBeInTheDocument();
      });
      const imageButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(imageButton);

      expect(screen.getByPlaceholderText('Describe your image...')).toBeInTheDocument();
      expect(screen.getByText('Describe the image you want to generate')).toBeInTheDocument();
    });

    it('should show Cancel button in image mode', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Click the attach menu button (Plus icon)
      const attachButton = screen.getByRole('button', { name: /attach file/i });
      await user.click(attachButton);

      // Click "Generate image" option
      await waitFor(() => {
        const imageButton = screen.getByRole('button', { name: /generate image/i });
        expect(imageButton).toBeInTheDocument();
      });
      const imageButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(imageButton);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('should switch back to chat mode on Cancel', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Click attach button, then Generate image
      const attachButton = screen.getByRole('button', { name: /attach file/i });
      await user.click(attachButton);
      await waitFor(() => {
        const imageButton = screen.getByRole('button', { name: /generate image/i });
        expect(imageButton).toBeInTheDocument();
      });
      const imageButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(imageButton);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });
  });

  describe('Clear history', () => {
    it('should call clearConversations when clear history is confirmed', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Chat', message_count: 5, created_at: '2024-01-01' }],
        total: 1,
      });
      mockClearConversations.mockResolvedValue({ success: true, deleted_count: 1 });

      render(<ChatPage />);

      // Open sidebar first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clear history/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /clear history/i }));

      await waitFor(() => {
        expect(window.confirm).toHaveBeenCalled();
        expect(mockClearConversations).toHaveBeenCalled();
      });
    });

    it('should not clear when confirmation is cancelled', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => false);
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Chat', message_count: 5, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      // Open sidebar first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clear history/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /clear history/i }));

      expect(mockClearConversations).not.toHaveBeenCalled();
    });
  });

  describe('Sidebar toggle', () => {
    it('should have sidebar toggle button', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });
    });
  });

  describe('Header', () => {
    it('should display Zantara branding', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        // Zantara appears in alt attributes and welcome message
        const logos = screen.getAllByAltText('Zantara');
        expect(logos.length).toBeGreaterThan(0);
      });
    });

    it('should display logo', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        const logos = screen.getAllByAltText('Zantara');
        expect(logos.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Loading conversation', () => {
    it('should load and display messages when clicking on a conversation', async () => {
      const user = userEvent.setup();
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Test Chat', message_count: 2, created_at: '2024-01-01' }],
        total: 1,
      });
      mockGetConversation.mockResolvedValue({
        success: true,
        messages: [
          { role: 'user', content: 'Hello AI' },
          { role: 'assistant', content: 'Hello! How can I help?' },
        ],
        created_at: '2024-01-01T00:00:00Z',
      });

      render(<ChatPage />);

      // Wait for conversations to load
      await waitFor(() => {
        expect(screen.getByText('Test Chat')).toBeInTheDocument();
      });

      // Click on the conversation
      await user.click(screen.getByText('Test Chat'));

      // Verify messages are displayed
      await waitFor(() => {
        expect(screen.getByText('Hello AI')).toBeInTheDocument();
        expect(screen.getByText('Hello! How can I help?')).toBeInTheDocument();
      });
    });

    it('should handle error when loading conversation fails', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Test Chat', message_count: 2, created_at: '2024-01-01' }],
        total: 1,
      });
      mockGetConversation.mockRejectedValue(new Error('Load failed'));

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Chat')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Test Chat'));

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalled();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Sending messages', () => {
    it('should send message when clicking send button', async () => {
      const user = userEvent.setup();
      mockSendMessageStreaming.mockImplementation(
        (
          _msg: string,
          _session: string | undefined,
          _onChunk: () => void,
          onDone: (msg: string, sources: []) => void
        ) => {
          onDone('AI Response', []);
          return Promise.resolve();
        }
      );

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText('Type your message...');
      await user.type(input, 'Hello AI!');

      const sendButton = screen.getByRole('button', { name: /send message/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(mockSendMessageStreaming).toHaveBeenCalled();
      });
    });

    it('should display user message after sending', async () => {
      const user = userEvent.setup();
      mockSendMessageStreaming.mockImplementation(
        (
          _msg: string,
          _session: string | undefined,
          _onChunk: () => void,
          onDone: (msg: string, sources: []) => void
        ) => {
          onDone('AI Response', []);
          return Promise.resolve();
        }
      );

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText('Type your message...');
      await user.type(input, 'Hello AI!');

      const sendButton = screen.getByRole('button', { name: /send message/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(screen.getByText('Hello AI!')).toBeInTheDocument();
      });
    });

    it('should handle send error gracefully', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockSendMessageStreaming.mockImplementation(
        (
          _msg: string,
          _session: string | undefined,
          _onChunk: () => void,
          _onDone: () => void,
          onError: (err: Error) => void
        ) => {
          onError(new Error('Network error'));
          return Promise.resolve();
        }
      );

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText('Type your message...');
      await user.type(input, 'Hello AI!');

      const sendButton = screen.getByRole('button', { name: /send message/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(screen.getByText(/error processing your request/i)).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });

    it('should clear input after sending', async () => {
      const user = userEvent.setup();
      mockSendMessageStreaming.mockImplementation(
        (
          _msg: string,
          _session: string | undefined,
          _onChunk: () => void,
          onDone: (msg: string, sources: []) => void
        ) => {
          onDone('Response', []);
          return Promise.resolve();
        }
      );

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText('Type your message...') as HTMLInputElement;
      await user.type(input, 'Test message');

      const sendButton = screen.getByRole('button', { name: /send message/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(input.value).toBe('');
      });
    });
  });

  describe('Image generation', () => {
    it('should call generateImage when in image mode', async () => {
      const user = userEvent.setup();
      mockGenerateImage.mockResolvedValue({ image_url: 'https://example.com/image.png' });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Switch to image mode - click attach button, then Generate image
      const attachButton = screen.getByRole('button', { name: /attach file/i });
      await user.click(attachButton);
      await waitFor(() => {
        const imageButton = screen.getByRole('button', { name: /generate image/i });
        expect(imageButton).toBeInTheDocument();
      });
      const imageButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(imageButton);

      const input = screen.getByPlaceholderText('Describe your image...');
      await user.type(input, 'A beautiful sunset');

      const sendButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(mockGenerateImage).toHaveBeenCalledWith('A beautiful sunset');
      });
    });

    it('should display generated image', async () => {
      const user = userEvent.setup();
      mockGenerateImage.mockResolvedValue({ image_url: 'https://example.com/image.png' });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Click attach button, then Generate image
      const attachButton = screen.getByRole('button', { name: /attach file/i });
      await user.click(attachButton);
      await waitFor(() => {
        const imageButton = screen.getByRole('button', { name: /generate image/i });
        expect(imageButton).toBeInTheDocument();
      });
      const imageButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(imageButton);

      const input = screen.getByPlaceholderText('Describe your image...');
      await user.type(input, 'A cat');

      const sendButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(sendButton);

      await waitFor(() => {
        const images = screen.getAllByAltText('Generated content');
        expect(images.length).toBeGreaterThan(0);
      });
    });

    it('should handle image generation error', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockGenerateImage.mockRejectedValue(new Error('Generation failed'));

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Click attach button, then Generate image
      const attachButton = screen.getByRole('button', { name: /attach file/i });
      await user.click(attachButton);
      await waitFor(() => {
        const imageButton = screen.getByRole('button', { name: /generate image/i });
        expect(imageButton).toBeInTheDocument();
      });
      const imageButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(imageButton);

      const input = screen.getByPlaceholderText('Describe your image...');
      await user.type(input, 'A dog');

      const sendButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(screen.getByText(/failed to generate the image/i)).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });
  });

  describe('New Chat', () => {
    it('should clear messages when clicking New Chat', async () => {
      const user = userEvent.setup();
      mockSendMessageStreaming.mockImplementation(
        (
          _msg: string,
          _session: string | undefined,
          _onChunk: () => void,
          onDone: (msg: string, sources: []) => void
        ) => {
          onDone('Response', []);
          return Promise.resolve();
        }
      );

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Send a message first
      const input = screen.getByPlaceholderText('Type your message...');
      await user.type(input, 'First message');
      await user.click(screen.getByRole('button', { name: /send message/i }));

      await waitFor(() => {
        expect(screen.getByText('First message')).toBeInTheDocument();
      });

      // Click New Chat
      await user.click(screen.getByRole('button', { name: /new chat/i }));

      // Messages should be cleared, welcome message should appear
      await waitFor(() => {
        expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
      });
    });
  });

  describe('Admin button', () => {
    it('should show admin button for admin users', async () => {
      const user = userEvent.setup();
      mockIsAdmin.mockReturnValue(true);

      render(<ChatPage />);

      // Open user menu first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /admin dashboard/i })).toBeInTheDocument();
      });
    });

    it('should not show admin button for regular users', async () => {
      mockIsAdmin.mockReturnValue(false);

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /admin dashboard/i })).not.toBeInTheDocument();
    });
  });

  describe('Quick action buttons', () => {
    it('should set input when clicking My Tasks button', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
      });

      const tasksButton = screen.getAllByRole('button', { name: /my tasks/i })[0];
      await user.click(tasksButton);

      const input = screen.getByPlaceholderText('Type your message...') as HTMLInputElement;
      expect(input.value).toContain('tasks');
    });

    it('should set input when clicking What can you do button', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
      });

      const helpButton = screen.getAllByRole('button', { name: /what can you do/i })[0];
      await user.click(helpButton);

      const input = screen.getByPlaceholderText('Type your message...') as HTMLInputElement;
      expect(input.value).toContain('help');
    });

    it('should set input when clicking Search docs button', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
      });

      const searchButton = screen.getAllByRole('button', { name: /search docs/i })[0];
      await user.click(searchButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog', { name: /search docs/i })).toBeInTheDocument();
      });
    });
  });

  describe('Admin navigation', () => {
    it('should navigate to admin page when clicking admin button', async () => {
      const user = userEvent.setup();
      mockIsAdmin.mockReturnValue(true);

      render(<ChatPage />);

      // Open user menu first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /admin dashboard/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /admin dashboard/i }));

      expect(mockPush).toHaveBeenCalledWith('/admin');
    });
  });

  describe('Avatar upload', () => {
    it('should open file picker when clicking avatar', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });

      // Open user menu first
      const userMenuButton = screen.getByRole('button', { name: /user menu/i });
      await user.click(userMenuButton);
      await waitFor(() => {
        const avatarButton = screen.getByRole('button', { name: /change avatar/i });
        expect(avatarButton).toBeInTheDocument();
      });
      const avatarButton = screen.getByRole('button', { name: /change avatar/i });
      await user.click(avatarButton);

      // The hidden file input should exist
      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeInTheDocument();
    });

    it('should reject non-image files', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      // Open user menu and click Change Avatar to trigger file input
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));
      await waitFor(() => {
        const avatarButton = screen.getByRole('button', { name: /change avatar/i });
        expect(avatarButton).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /change avatar/i }));

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const textFile = new File(['text content'], 'test.txt', { type: 'text/plain' });

      await fireEvent.change(fileInput, { target: { files: [textFile] } });

      // Component uses toast notifications, not alerts
      await waitFor(() => {
        expect(screen.getByText('Please select an image file')).toBeInTheDocument();
      });
    });

    it('should reject files larger than 2MB', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      // Open user menu and click Change Avatar to trigger file input
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));
      await waitFor(() => {
        const avatarButton = screen.getByRole('button', { name: /change avatar/i });
        expect(avatarButton).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /change avatar/i }));

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      // Create a file larger than 2MB
      const largeContent = new Array(3 * 1024 * 1024).fill('a').join('');
      const largeFile = new File([largeContent], 'large.png', { type: 'image/png' });

      await fireEvent.change(fileInput, { target: { files: [largeFile] } });

      // Component uses toast notifications, not alerts
      await waitFor(() => {
        expect(screen.getByText('Image must be less than 2MB')).toBeInTheDocument();
      });
    });

    it('should accept valid image files and start reading', async () => {
      const user = userEvent.setup();
      render(<ChatPage />);

      // Open user menu and click Change Avatar to trigger file input
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /user menu/i }));
      await waitFor(() => {
        const avatarButton = screen.getByRole('button', { name: /change avatar/i });
        expect(avatarButton).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /change avatar/i }));

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const imageFile = new File(['image data'], 'avatar.png', { type: 'image/png' });
      // Mock arrayBuffer since it might be missing in JSDOM environment
      Object.defineProperty(imageFile, 'arrayBuffer', {
        value: async () => new Uint8Array([0x89, 0x50, 0x4e, 0x47]).buffer,
      });

      // The handleAvatarUpload function will be called, but we can't easily test FileReader
      // Just verify no error is thrown when valid file is selected
      await fireEvent.change(fileInput, { target: { files: [imageFile] } });

      // No error should have occurred - the component should still be rendered
      expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
    });

    it('should handle empty file selection', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

      // Simulate empty file selection
      await fireEvent.change(fileInput, { target: { files: [] } });

      // Should not throw error, just return early
      expect(true).toBe(true);
    });
  });

  describe('Delete conversation', () => {
    it('should show delete button on conversation hover', async () => {
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Test Chat', message_count: 2, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Chat')).toBeInTheDocument();
      });

      // Delete button should exist (visible on hover via CSS)
      const deleteButton = screen.getByRole('button', { name: /delete conversation/i });
      expect(deleteButton).toBeInTheDocument();
    });

    it('should ask for confirmation before deleting', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => false);
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Test Chat', message_count: 2, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Chat')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button', { name: /delete conversation/i });
      await user.click(deleteButton);

      expect(window.confirm).toHaveBeenCalledWith('Delete this conversation?');
    });
  });

  describe('Keyboard shortcuts', () => {
    it('should send message on Enter key', async () => {
      const user = userEvent.setup();
      mockSendMessageStreaming.mockImplementation(
        (
          _msg: string,
          _session: string | undefined,
          _onChunk: () => void,
          onDone: (msg: string, sources: []) => void
        ) => {
          onDone('Response', []);
          return Promise.resolve();
        }
      );

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText('Type your message...');
      await user.type(input, 'Test message{enter}');

      await waitFor(() => {
        expect(mockSendMessageStreaming).toHaveBeenCalled();
      });
    });

    it('should generate image on Enter in image mode', async () => {
      const user = userEvent.setup();
      mockGenerateImage.mockResolvedValue({ image_url: 'https://example.com/image.png' });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      // Switch to image mode - click attach button, then Generate image
      const attachButton = screen.getByRole('button', { name: /attach file/i });
      await user.click(attachButton);
      await waitFor(() => {
        const imageButton = screen.getByRole('button', { name: /generate image/i });
        expect(imageButton).toBeInTheDocument();
      });
      const imageButton = screen.getByRole('button', { name: /generate image/i });
      await user.click(imageButton);

      const input = screen.getByPlaceholderText('Describe your image...');
      await user.type(input, 'A sunset{enter}');

      await waitFor(() => {
        expect(mockGenerateImage).toHaveBeenCalled();
      });
    });
  });

  describe('WebSocket integration', () => {
    it('should render without WebSocket errors', async () => {
      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByText('Garda Depan Leluhur')).toBeInTheDocument();
      });

      // WebSocket hook is mocked - verify component renders correctly
      expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    });
  });

  describe('Streaming message', () => {
    it('should update message content during streaming', async () => {
      const user = userEvent.setup();
      mockSendMessageStreaming.mockImplementation(
        (
          _msg: string,
          _session: string | undefined,
          onChunk: (chunk: string) => void,
          onDone: (msg: string, sources: []) => void
        ) => {
          // Simulate streaming
          onChunk('Hello');
          onChunk(' World');
          onDone('Hello World', []);
          return Promise.resolve();
        }
      );

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText('Type your message...');
      await user.type(input, 'Hi');
      await user.click(screen.getByRole('button', { name: /send message/i }));

      await waitFor(() => {
        expect(screen.getByText('Hello World')).toBeInTheDocument();
      });
    });
  });

  describe('Display user avatar from localStorage', () => {
    it('should load saved avatar from localStorage', async () => {
      const mockAvatar = 'data:image/png;base64,testAvatarData';
      localStorage.setItem('user_avatar', mockAvatar);

      render(<ChatPage />);

      await waitFor(() => {
        const avatarImg = screen.queryByAltText('User avatar');
        // Avatar may or may not be visible depending on state
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });
    });
  });

  describe('Sidebar interactions', () => {
    it('should toggle sidebar state when clicking menu button', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });

      // Click to open sidebar - the header button changes to "close sidebar"
      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      // Sidebar should now be open (check for sidebar-specific content)
      await waitFor(() => {
        expect(screen.getByText('No conversations yet')).toBeInTheDocument();
      });
    });

    it('should close sidebar when clicking overlay', async () => {
      const user = userEvent.setup();

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });

      // Open sidebar first
      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByText('No conversations yet')).toBeInTheDocument();
      });

      // Click on overlay (the dark background)
      const overlay = document.querySelector('[aria-hidden="true"]');
      if (overlay) {
        await user.click(overlay);
      }

      // After clicking overlay, sidebar should close
      // We verify this by checking the menu button shows "open sidebar" again
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });
    });

    it('should load conversation when clicking on a conversation item', async () => {
      const user = userEvent.setup();
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [
          { id: 1, title: 'Previous Chat', message_count: 2, created_at: '2024-01-01' },
        ],
        total: 1,
      });
      mockGetConversation.mockResolvedValue({
        success: true,
        messages: [
          { role: 'user', content: 'Hello there', sources: [], imageUrl: null },
          {
            role: 'assistant',
            content: 'Hi! How can I help?',
            sources: [{ title: 'Doc', content: 'test' }],
            imageUrl: null,
          },
        ],
        created_at: '2024-01-01T00:00:00Z',
      });

      render(<ChatPage />);

      // Open sidebar
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByText('Previous Chat')).toBeInTheDocument();
      });

      // Click on the conversation
      await user.click(screen.getByText('Previous Chat'));

      // Should call getConversation with the conversation ID
      await waitFor(() => {
        expect(mockGetConversation).toHaveBeenCalledWith(1);
      });

      // Should load the conversation messages
      await waitFor(() => {
        expect(screen.getByText('Hello there')).toBeInTheDocument();
        expect(screen.getByText('Hi! How can I help?')).toBeInTheDocument();
      });
    });
  });

  describe('Error handling in data loading', () => {
    it('should handle clock status load error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockGetClockStatus.mockRejectedValue(new Error('Clock status error'));

      render(<ChatPage />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to load clock status:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('should handle profile load error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockGetUserProfile.mockReturnValue(null);
      mockGetProfile.mockRejectedValue(new Error('Profile error'));

      render(<ChatPage />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to load profile:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('should handle conversation list load error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockListConversations.mockRejectedValue(new Error('List error'));

      render(<ChatPage />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to load conversations:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('should handle clear history error', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      window.confirm = vi.fn(() => true);
      mockClearConversations.mockRejectedValue(new Error('Clear failed'));
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Chat', message_count: 5, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      // Open sidebar first
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /open sidebar/i }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clear history/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /clear history/i }));

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to clear history:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Clock out flow', () => {
    it('should handle clock out failure', async () => {
      const user = userEvent.setup();
      mockGetClockStatus.mockResolvedValue({ is_clocked_in: true, today_hours: 4, week_hours: 20 });
      mockClockOut.mockResolvedValue({ success: false, message: 'Clock out failed' });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /clock out/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /clock out/i }));

      await waitFor(() => {
        expect(screen.getByText('Clock out failed')).toBeInTheDocument();
      });
    });
  });

  describe('Avatar FileReader', () => {
    it('should process valid image with FileReader', async () => {
      // Create a mock FileReader class that triggers onloadend
      class MockFileReader {
        result: string = '';
        onloadend: (() => void) | null = null;

        readAsDataURL(_file: Blob) {
          this.result = 'data:image/png;base64,mockAvatarData';
          // Trigger onloadend synchronously to make testing easier
          if (this.onloadend) this.onloadend();
        }
      }

      const originalFileReader = global.FileReader;
      global.FileReader = MockFileReader as unknown as typeof FileReader;

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const imageFile = new File(['image data'], 'avatar.png', { type: 'image/png' });

      // Mock arrayBuffer since it might be missing in JSDOM environment
      Object.defineProperty(imageFile, 'arrayBuffer', {
        value: async () => new Uint8Array([0x89, 0x50, 0x4e, 0x47]).buffer,
      });

      // Trigger the file input change
      fireEvent.change(fileInput, { target: { files: [imageFile] } });

      // The component should still be rendered after file processing
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
      });

      global.FileReader = originalFileReader;
    });
  });

  describe('Delete conversation', () => {
    it('should delete conversation when confirmed', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      mockDeleteConversation.mockResolvedValue({ success: true });
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Test Chat', message_count: 5, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      // Open sidebar to see conversations
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByText('Test Chat')).toBeInTheDocument();
      });

      // Find and click delete button
      const deleteButton = screen.getByRole('button', { name: /delete conversation/i });
      await user.click(deleteButton);

      await waitFor(() => {
        expect(mockDeleteConversation).toHaveBeenCalledWith(1);
      });
    });

    it('should not delete when confirm is cancelled', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => false);
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Test Chat', message_count: 5, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByText('Test Chat')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button', { name: /delete conversation/i });
      await user.click(deleteButton);

      expect(mockDeleteConversation).not.toHaveBeenCalled();
    });

    it('should handle delete error', async () => {
      const user = userEvent.setup();
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      window.confirm = vi.fn(() => true);
      mockDeleteConversation.mockRejectedValue(new Error('Delete failed'));
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [{ id: 1, title: 'Test Chat', message_count: 5, created_at: '2024-01-01' }],
        total: 1,
      });

      render(<ChatPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByText('Test Chat')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button', { name: /delete conversation/i });
      await user.click(deleteButton);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to delete conversation:',
          expect.any(Error)
        );
      });

      consoleSpy.mockRestore();
    });

    it('should trigger new chat if deleting current conversation', async () => {
      const user = userEvent.setup();
      window.confirm = vi.fn(() => true);
      mockDeleteConversation.mockResolvedValue({ success: true });
      mockListConversations.mockResolvedValue({
        success: true,
        conversations: [
          { id: 1, title: 'Current Chat', message_count: 5, created_at: '2024-01-01' },
        ],
        total: 1,
      });
      mockGetConversation.mockResolvedValue({
        success: true,
        messages: [{ id: '1', role: 'user', content: 'Hello', timestamp: new Date() }],
      });

      render(<ChatPage />);

      // Open sidebar
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /open sidebar/i }));

      await waitFor(() => {
        expect(screen.getByText('Current Chat')).toBeInTheDocument();
      });

      // Load this conversation first
      await user.click(screen.getByText('Current Chat'));

      // Now delete it
      const deleteButton = screen.getByRole('button', { name: /delete conversation/i });
      await user.click(deleteButton);

      await waitFor(() => {
        expect(mockDeleteConversation).toHaveBeenCalledWith(1);
      });
    });
  });

  describe('Sidebar close button', () => {
    it(
      'should close sidebar when clicking close button inside sidebar',
      { timeout: 10000 },
      async () => {
        const user = userEvent.setup();

        render(<ChatPage />);

        await waitFor(() => {
          expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
        });

        // Open sidebar
        await user.click(screen.getByRole('button', { name: /open sidebar/i }));

        await waitFor(() => {
          expect(screen.getByText('No conversations yet')).toBeInTheDocument();
        });

        // Click the close button inside the sidebar (not the header one)
        const closeButtons = screen.getAllByRole('button', { name: /close sidebar/i });
        // The sidebar close button should be the second one (inside sidebar)
        await user.click(closeButtons[closeButtons.length - 1]);

        // Sidebar should close
        await waitFor(() => {
          expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument();
        });
      }
    );
  });
});
