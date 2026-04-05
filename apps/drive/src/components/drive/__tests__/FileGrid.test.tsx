import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { FileGrid } from '../FileGrid';
import type { FileItem } from '@/lib/api/drive/drive.types';

// Mock useDrive hook
vi.mock('@/hooks/useDrive', () => ({
  usePrefetchFolder: () => ({
    prefetchFolder: vi.fn(),
  }),
}));

// Mock file-icon utilities
vi.mock('../file-icon', () => ({
  getFileIcon: (file: FileItem, _size: string) => (
    <span data-testid={`file-icon-${file.id}`}>{file.is_folder ? 'folder' : 'file'}</span>
  ),
  getDepartmentInfo: () => null,
  DEPARTMENT_COLORS: {},
}));

const mockFolders: FileItem[] = [
  {
    id: 'folder-1',
    name: 'Documents',
    mime_type: 'application/vnd.google-apps.folder',
    is_folder: true,
  },
  {
    id: 'folder-2',
    name: 'Images',
    mime_type: 'application/vnd.google-apps.folder',
    is_folder: true,
  },
];

const mockFiles: FileItem[] = [
  {
    id: 'file-1',
    name: 'report.pdf',
    mime_type: 'application/pdf',
    size: 1024 * 1024 * 2.5,
    modified_time: new Date().toISOString(),
    is_folder: false,
  },
  {
    id: 'file-2',
    name: 'photo.jpg',
    mime_type: 'image/jpeg',
    size: 512000,
    modified_time: new Date(Date.now() - 86400000).toISOString(),
    is_folder: false,
  },
];

const allItems = [...mockFolders, ...mockFiles];

const defaultProps = {
  files: allItems,
  selectedFiles: new Set<string>(),
  onFileClick: vi.fn(),
  onFileDoubleClick: vi.fn(),
  onContextMenu: vi.fn(),
};

describe('FileGrid', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders folders section with correct heading', () => {
    render(<FileGrid {...defaultProps} />);
    expect(screen.getByText('Cartelle')).toBeInTheDocument();
  });

  it('renders files section with correct heading', () => {
    render(<FileGrid {...defaultProps} />);
    expect(screen.getByText('File')).toBeInTheDocument();
  });

  it('renders all folder names', () => {
    render(<FileGrid {...defaultProps} />);
    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('Images')).toBeInTheDocument();
  });

  it('renders all file names', () => {
    render(<FileGrid {...defaultProps} />);
    expect(screen.getByText('report.pdf')).toBeInTheDocument();
    expect(screen.getByText('photo.jpg')).toBeInTheDocument();
  });

  it('shows empty state when no files provided', () => {
    render(<FileGrid {...defaultProps} files={[]} />);
    expect(screen.getByText('Questa cartella è vuota')).toBeInTheDocument();
    expect(
      screen.getByText('Trascina file qui o clicca "Nuovo" per creare contenuti')
    ).toBeInTheDocument();
  });

  it('calls onFileClick when a file card is clicked', () => {
    const onFileClick = vi.fn();
    render(<FileGrid {...defaultProps} onFileClick={onFileClick} />);

    fireEvent.click(screen.getByText('report.pdf').closest("[class*='cursor-pointer']")!);
    expect(onFileClick).toHaveBeenCalled();
  });

  it('calls onFileDoubleClick when a file card is double-clicked', () => {
    const onFileDoubleClick = vi.fn();
    render(<FileGrid {...defaultProps} onFileDoubleClick={onFileDoubleClick} />);

    fireEvent.doubleClick(screen.getByText('Documents').closest("[class*='cursor-pointer']")!);
    expect(onFileDoubleClick).toHaveBeenCalled();
  });

  it('shows selection indicator for selected files', () => {
    const selectedFiles = new Set(['file-1']);
    render(<FileGrid {...defaultProps} selectedFiles={selectedFiles} />);

    // The selected file card should have the selection ring class
    const fileCard = screen.getByText('report.pdf').closest("[class*='cursor-pointer']")!;
    expect(fileCard.className).toContain('ring-1');
  });

  it('renders context menu button with correct aria-label', () => {
    render(<FileGrid {...defaultProps} />);
    const menuButtons = screen.getAllByLabelText(/Azioni per/);
    expect(menuButtons.length).toBe(allItems.length);
  });

  it('shows file size for non-folder items', () => {
    render(<FileGrid {...defaultProps} />);
    expect(screen.getByText('2.5 MB')).toBeInTheDocument();
  });

  it('displays loading indicator when fetching next page', () => {
    render(<FileGrid {...defaultProps} isFetchingNextPage={true} hasNextPage={true} />);
    expect(screen.getByText('Loading more files...')).toBeInTheDocument();
  });

  it("shows 'All files loaded' when no more pages and enough files", () => {
    const manyFiles = Array.from({ length: 50 }, (_, i) => ({
      id: `file-${i}`,
      name: `file-${i}.txt`,
      mime_type: 'text/plain',
      size: 100,
      is_folder: false,
    }));
    render(<FileGrid {...defaultProps} files={manyFiles} hasNextPage={false} />);
    expect(screen.getByText('All files loaded')).toBeInTheDocument();
  });

  it('does not render sections when only folders exist', () => {
    render(<FileGrid {...defaultProps} files={mockFolders} />);
    expect(screen.getByText('Cartelle')).toBeInTheDocument();
    expect(screen.queryByText('File')).not.toBeInTheDocument();
  });

  it('does not render sections when only files exist', () => {
    render(<FileGrid {...defaultProps} files={mockFiles} />);
    expect(screen.queryByText('Cartelle')).not.toBeInTheDocument();
    expect(screen.getByText('File')).toBeInTheDocument();
  });
});
