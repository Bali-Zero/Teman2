import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatHeader, ChatHeaderProps } from './ChatHeader';
import { createRef } from 'react';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// Mock api
vi.mock('@/lib/api', () => ({
  api: {
    isAdmin: vi.fn(() => false),
    logout: vi.fn().mockResolvedValue(undefined),
  },
}));

describe('ChatHeader', () => {
  const defaultProps: ChatHeaderProps = {
    isSidebarOpen: false,
    onToggleSidebar: vi.fn(),
    isClockIn: false,
    isClockLoading: false,
    onToggleClock: vi.fn(),
    messagesCount: 0,
    isWsConnected: false,
    userName: 'Test User',
    userAvatar: null,
    showUserMenu: false,
    onToggleUserMenu: vi.fn(),
    userMenuRef: createRef<HTMLDivElement>(),
    avatarInputRef: createRef<HTMLInputElement>(),
    onAvatarUpload: vi.fn(),
    onShowToast: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Menu button', () => {
    it('should render menu button', () => {
      render(<ChatHeader {...defaultProps} />);
      expect(screen.getByLabelText('Open sidebar')).toBeInTheDocument();
    });

    it('should call onToggleSidebar when menu clicked', async () => {
      const user = userEvent.setup();
      render(<ChatHeader {...defaultProps} />);

      await user.click(screen.getByLabelText('Open sidebar'));
      expect(defaultProps.onToggleSidebar).toHaveBeenCalledTimes(1);
    });

    it('should show close sidebar label when sidebar is open', () => {
      render(<ChatHeader {...defaultProps} isSidebarOpen={true} />);
      expect(screen.getByLabelText('Close sidebar')).toBeInTheDocument();
    });
  });

  describe('Clock button', () => {
    it('should show Clock In text when not clocked in', () => {
      render(<ChatHeader {...defaultProps} isClockIn={false} />);
      expect(screen.getByText('Clock In')).toBeInTheDocument();
    });

    it('should show Clock Out text when clocked in', () => {
      render(<ChatHeader {...defaultProps} isClockIn={true} />);
      expect(screen.getByText('Clock Out')).toBeInTheDocument();
    });

    it('should call onToggleClock when clicked', async () => {
      const user = userEvent.setup();
      render(<ChatHeader {...defaultProps} />);

      await user.click(screen.getByText('Clock In'));
      expect(defaultProps.onToggleClock).toHaveBeenCalledTimes(1);
    });

    it('should be disabled when loading', () => {
      render(<ChatHeader {...defaultProps} isClockLoading={true} />);
      const button = screen.getByRole('button', { name: /clock/i });
      expect(button).toBeDisabled();
    });
  });

  describe('Logo visibility', () => {
    it('should hide logo when no messages', () => {
      const { container } = render(<ChatHeader {...defaultProps} messagesCount={0} />);
      const logoWrapper = container.querySelector('.opacity-0');
      expect(logoWrapper).toBeInTheDocument();
    });

    it('should show logo when messages exist', () => {
      const { container } = render(<ChatHeader {...defaultProps} messagesCount={5} />);
      const logoWrapper = container.querySelector('.opacity-100');
      expect(logoWrapper).toBeInTheDocument();
    });
  });

  describe('WebSocket indicator', () => {
    it('should show indicator when connected', () => {
      const { container } = render(<ChatHeader {...defaultProps} isWsConnected={true} />);
      expect(container.querySelector('.bg-green-500')).toBeInTheDocument();
    });

    it('should not show indicator when disconnected', () => {
      const { container } = render(<ChatHeader {...defaultProps} isWsConnected={false} />);
      expect(container.querySelector('.bg-green-500')).not.toBeInTheDocument();
    });
  });

  describe('User avatar', () => {
    it('should show user initial when no avatar', () => {
      render(<ChatHeader {...defaultProps} userName="John Doe" userAvatar={null} />);
      expect(screen.getByText('J')).toBeInTheDocument();
    });

    it('should show avatar image when provided', () => {
      render(
        <ChatHeader
          {...defaultProps}
          userAvatar="data:image/png;base64,test"
        />
      );
      expect(screen.getByAltText('User avatar')).toBeInTheDocument();
    });
  });

  describe('User menu', () => {
    it('should not show menu by default', () => {
      render(<ChatHeader {...defaultProps} showUserMenu={false} />);
      expect(screen.queryByText('Change Avatar')).not.toBeInTheDocument();
    });

    it('should show menu when showUserMenu is true', () => {
      render(<ChatHeader {...defaultProps} showUserMenu={true} />);
      expect(screen.getByText('Change Avatar')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('Logout')).toBeInTheDocument();
    });

    it('should toggle menu when avatar clicked', async () => {
      const user = userEvent.setup();
      render(<ChatHeader {...defaultProps} />);

      await user.click(screen.getByLabelText('User menu'));
      expect(defaultProps.onToggleUserMenu).toHaveBeenCalledTimes(1);
    });

    it('should display user name in menu', () => {
      render(<ChatHeader {...defaultProps} showUserMenu={true} userName="Test User" />);
      expect(screen.getByText('Test User')).toBeInTheDocument();
    });
  });

  describe('Notifications', () => {
    it('should render notifications button', () => {
      render(<ChatHeader {...defaultProps} />);
      expect(screen.getByLabelText('Notifications')).toBeInTheDocument();
    });
  });
});
