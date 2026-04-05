import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { FolderSidebar } from '../FolderSidebar';
import type { EmailFolder } from '@/lib/email.types';

// Mock lucide-react icons
vi.mock('lucide-react', () => {
  const createIcon = (name: string) => {
    const Icon = (props: Record<string, unknown>) => (
      <svg data-testid={`icon-${name}`} {...props} />
    );
    Icon.displayName = name;
    return Icon;
  };
  return {
    Inbox: createIcon('Inbox'),
    Send: createIcon('Send'),
    FileText: createIcon('FileText'),
    Trash2: createIcon('Trash2'),
    AlertOctagon: createIcon('AlertOctagon'),
    Folder: createIcon('Folder'),
    Plus: createIcon('Plus'),
    RefreshCw: createIcon('RefreshCw'),
    LogOut: createIcon('LogOut'),
  };
});

// Mock cn utility
vi.mock('@/lib/utils', () => ({
  cn: (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(' '),
}));

const mockFolders: EmailFolder[] = [
  {
    folder_id: 'inbox-1',
    folder_name: 'Inbox',
    folder_path: '/Inbox',
    folder_type: 'inbox',
    unread_count: 5,
    total_count: 100,
  },
  {
    folder_id: 'sent-1',
    folder_name: 'Sent',
    folder_path: '/Sent',
    folder_type: 'sent',
    unread_count: 0,
    total_count: 50,
  },
  {
    folder_id: 'drafts-1',
    folder_name: 'Drafts',
    folder_path: '/Drafts',
    folder_type: 'drafts',
    unread_count: 2,
    total_count: 10,
  },
  {
    folder_id: 'trash-1',
    folder_name: 'Trash',
    folder_path: '/Trash',
    folder_type: 'trash',
    unread_count: 0,
    total_count: 20,
  },
];

const defaultProps = {
  folders: mockFolders,
  selectedFolderId: 'inbox-1',
  onSelectFolder: vi.fn(),
  onCompose: vi.fn(),
  onRefresh: vi.fn(),
  onDisconnect: vi.fn(),
};

describe('FolderSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Compose button', () => {
    render(<FolderSidebar {...defaultProps} />);
    expect(screen.getByText('Compose')).toBeInTheDocument();
  });

  it('calls onCompose when Compose is clicked', () => {
    const onCompose = vi.fn();
    render(<FolderSidebar {...defaultProps} onCompose={onCompose} />);
    fireEvent.click(screen.getByText('Compose'));
    expect(onCompose).toHaveBeenCalledTimes(1);
  });

  it('renders all folder names', () => {
    render(<FolderSidebar {...defaultProps} />);
    expect(screen.getByText('Inbox')).toBeInTheDocument();
    expect(screen.getByText('Sent')).toBeInTheDocument();
    expect(screen.getByText('Drafts')).toBeInTheDocument();
    expect(screen.getByText('Trash')).toBeInTheDocument();
  });

  it('sorts folders in standard order: inbox, sent, drafts, trash', () => {
    const { container } = render(<FolderSidebar {...defaultProps} />);
    const buttons = container.querySelectorAll("button[class*='w-full']");
    // First button after Compose should be in order
    const folderButtons = Array.from(buttons).filter((b) =>
      b.textContent?.match(/^(Inbox|Sent|Drafts|Trash)/)
    );
    expect(folderButtons[0]).toHaveTextContent('Inbox');
    expect(folderButtons[1]).toHaveTextContent('Sent');
    expect(folderButtons[2]).toHaveTextContent('Drafts');
    expect(folderButtons[3]).toHaveTextContent('Trash');
  });

  it('shows unread count badge for folders with unread emails', () => {
    render(<FolderSidebar {...defaultProps} />);
    expect(screen.getByText('5')).toBeInTheDocument(); // Inbox unread
    expect(screen.getByText('2')).toBeInTheDocument(); // Drafts unread
  });

  it('does not show unread badge when count is 0', () => {
    render(<FolderSidebar {...defaultProps} />);
    // Sent has 0 unread - verify no badge in sent area
    const sentButton = screen.getByText('Sent').closest('button')!;
    expect(sentButton.querySelector('.rounded-full')).toBeNull();
  });

  it('marks selected folder with aria-current', () => {
    render(<FolderSidebar {...defaultProps} selectedFolderId="inbox-1" />);
    const inboxButton = screen.getByText('Inbox').closest('button')!;
    expect(inboxButton).toHaveAttribute('aria-current', 'page');
  });

  it('calls onSelectFolder when a folder is clicked', () => {
    const onSelectFolder = vi.fn();
    render(<FolderSidebar {...defaultProps} onSelectFolder={onSelectFolder} />);
    fireEvent.click(screen.getByText('Sent'));
    expect(onSelectFolder).toHaveBeenCalledWith('sent-1');
  });

  it('renders refresh button', () => {
    render(<FolderSidebar {...defaultProps} />);
    expect(screen.getByLabelText('Aggiorna lista email')).toBeInTheDocument();
  });

  it('calls onRefresh when refresh is clicked', () => {
    const onRefresh = vi.fn();
    render(<FolderSidebar {...defaultProps} onRefresh={onRefresh} />);
    fireEvent.click(screen.getByLabelText('Aggiorna lista email'));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('renders disconnect button', () => {
    render(<FolderSidebar {...defaultProps} />);
    expect(screen.getByLabelText('Disconnetti account Zoho Mail')).toBeInTheDocument();
  });

  it('calls onDisconnect when disconnect is clicked', () => {
    const onDisconnect = vi.fn();
    render(<FolderSidebar {...defaultProps} onDisconnect={onDisconnect} />);
    fireEvent.click(screen.getByLabelText('Disconnetti account Zoho Mail'));
    expect(onDisconnect).toHaveBeenCalledTimes(1);
  });

  it('displays connected email when provided', () => {
    render(<FolderSidebar {...defaultProps} connectedEmail="user@balizero.com" />);
    expect(screen.getByText('user@balizero.com')).toBeInTheDocument();
  });

  it('shows loading skeletons when isLoading is true', () => {
    const { container } = render(<FolderSidebar {...defaultProps} isLoading={true} />);
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBe(5);
  });

  it('renders navigation landmark', () => {
    render(<FolderSidebar {...defaultProps} />);
    expect(screen.getByRole('navigation', { name: 'Cartelle email' })).toBeInTheDocument();
  });

  it('shows 99+ for very high unread counts', () => {
    const foldersWithHighCount: EmailFolder[] = [
      {
        ...mockFolders[0],
        unread_count: 150,
      },
    ];
    render(<FolderSidebar {...defaultProps} folders={foldersWithHighCount} />);
    expect(screen.getByText('99+')).toBeInTheDocument();
  });
});
