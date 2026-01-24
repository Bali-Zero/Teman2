/**
 * Unit tests for DriveInfoPanel component
 *
 * Tests cover:
 * - Rendering when open/closed
 * - File details display
 * - Folder details display
 * - Quick action buttons
 * - Date formatting
 * - Size formatting
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DriveInfoPanel } from '../DriveInfoPanel';
import type { FileItem } from '@/lib/api/drive/drive.types';

describe('DriveInfoPanel', () => {
  const mockFile: FileItem = {
    id: 'file-1',
    name: 'test-document.pdf',
    mime_type: 'application/pdf',
    size: 1024 * 1024 * 2.5, // 2.5 MB
    is_folder: false,
    modified_time: '2026-01-20T10:30:00Z',
    web_view_link: 'https://drive.google.com/file/d/file-1/view',
  };

  const mockFolder: FileItem = {
    id: 'folder-1',
    name: 'Test Folder',
    mime_type: 'application/vnd.google-apps.folder',
    is_folder: true,
    modified_time: '2026-01-19T14:00:00Z',
  };

  const defaultProps = {
    file: mockFile,
    isOpen: true,
    onClose: vi.fn(),
    onPreview: vi.fn(),
    onDownload: vi.fn(),
    onDelete: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Visibility', () => {
    it('should render when isOpen is true and file is provided', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('test-document.pdf')).toBeTruthy();
    });

    it('should not render when isOpen is false', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} isOpen={false} />);

      // Panel should not be in DOM
      expect(container.querySelector('.border-l')).toBeFalsy();
    });

    it('should not render when file is null', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} file={null} />);

      expect(container.querySelector('.border-l')).toBeFalsy();
    });
  });

  describe('File Details', () => {
    it('should display file name in header', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('test-document.pdf')).toBeTruthy();
    });

    it('should display file type', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('Type')).toBeTruthy();
      expect(screen.getByText('pdf')).toBeTruthy();
    });

    it('should display file size for non-folder items', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('Size')).toBeTruthy();
      expect(screen.getByText('2.5 MB')).toBeTruthy();
    });

    it('should display modified date', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('Modified')).toBeTruthy();
      // Date should be formatted in English locale (e.g. "Jan 20, 2026, 10:30 AM")
      expect(screen.getByText(/Jan 20, 2026/)).toBeTruthy();
    });

    it('should display Google Drive link', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('Link')).toBeTruthy();
      expect(screen.getByText('Open in Google Drive')).toBeTruthy();

      const link = screen.getByText('Open in Google Drive');
      expect(link.getAttribute('href')).toBe('https://drive.google.com/file/d/file-1/view');
    });
  });

  describe('Folder Details', () => {
    it('should display "Folder" for folder type', () => {
      render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      expect(screen.getByText('Folder')).toBeTruthy();
    });

    it('should not display size for folders', () => {
      render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      expect(screen.queryByText('Size')).toBeFalsy();
    });
  });

  describe('Quick Actions', () => {
    it('should render preview button for files', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const previewButton = container.querySelector('button[title="Preview"]');
      expect(previewButton).toBeTruthy();
    });

    it('should not render preview button for folders', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      const previewButton = container.querySelector('button[title="Preview"]');
      expect(previewButton).toBeFalsy();
    });

    it('should render download button for files', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const downloadButton = container.querySelector('button[title="Download"]');
      expect(downloadButton).toBeTruthy();
    });

    it('should not render download button for folders', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      const downloadButton = container.querySelector('button[title="Download"]');
      expect(downloadButton).toBeFalsy();
    });

    it('should render delete button', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const deleteButton = container.querySelector('button[title="Delete"]');
      expect(deleteButton).toBeTruthy();
    });

    it('should call onClose when close button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      // Find the X button (close)
      const closeButton = container.querySelector('.rounded-full.hover\\:bg-\\[\\#f5f5f5\\]');
      fireEvent.click(closeButton!);

      expect(defaultProps.onClose).toHaveBeenCalled();
    });

    it('should call onPreview when preview button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const previewButton = container.querySelector('button[title="Preview"]');
      fireEvent.click(previewButton!);

      expect(defaultProps.onPreview).toHaveBeenCalledWith(mockFile);
    });

    it('should call onDownload when download button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const downloadButton = container.querySelector('button[title="Download"]');
      fireEvent.click(downloadButton!);

      expect(defaultProps.onDownload).toHaveBeenCalledWith(mockFile);
    });

    it('should call onDelete when delete button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const deleteButton = container.querySelector('button[title="Delete"]');
      fireEvent.click(deleteButton!);

      expect(defaultProps.onDelete).toHaveBeenCalledWith(mockFile);
    });
  });

  describe('Size Formatting', () => {
    it('should format bytes correctly', () => {
      const fileWithBytes: FileItem = { ...mockFile, size: 500 };
      render(<DriveInfoPanel {...defaultProps} file={fileWithBytes} />);

      expect(screen.getByText('500.0 B')).toBeTruthy();
    });

    it('should format KB correctly', () => {
      const fileWithKB: FileItem = { ...mockFile, size: 1024 * 5 };
      render(<DriveInfoPanel {...defaultProps} file={fileWithKB} />);

      expect(screen.getByText('5.0 KB')).toBeTruthy();
    });

    it('should format MB correctly', () => {
      const fileWithMB: FileItem = { ...mockFile, size: 1024 * 1024 * 10 };
      render(<DriveInfoPanel {...defaultProps} file={fileWithMB} />);

      expect(screen.getByText('10.0 MB')).toBeTruthy();
    });

    it('should format GB correctly', () => {
      const fileWithGB: FileItem = { ...mockFile, size: 1024 * 1024 * 1024 * 1.5 };
      render(<DriveInfoPanel {...defaultProps} file={fileWithGB} />);

      expect(screen.getByText('1.5 GB')).toBeTruthy();
    });

    it('should show "--" for undefined size', () => {
      const fileWithoutSize: FileItem = { ...mockFile, size: undefined };
      render(<DriveInfoPanel {...defaultProps} file={fileWithoutSize} />);

      expect(screen.getByText('--')).toBeTruthy();
    });
  });
});
