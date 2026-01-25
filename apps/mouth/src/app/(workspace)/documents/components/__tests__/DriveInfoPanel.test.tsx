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

      expect(screen.getByText('Tipo')).toBeTruthy();
      expect(screen.getByText('pdf')).toBeTruthy();
    });

    it('should display file size for non-folder items', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('Dimensione')).toBeTruthy();
      expect(screen.getByText('2.5 MB')).toBeTruthy();
    });

    it('should display modified date', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('Modificato')).toBeTruthy();
    });

    it('should display Google Drive link', () => {
      render(<DriveInfoPanel {...defaultProps} />);

      expect(screen.getByText('Apri in Google Drive')).toBeTruthy();

      const link = screen.getByText('Apri in Google Drive').closest('a');
      expect(link?.getAttribute('href')).toBe('https://drive.google.com/file/d/file-1/view');
    });
  });

  describe('Folder Details', () => {
    it('should display "Cartella" for folder type', () => {
      render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      expect(screen.getByText('Cartella')).toBeTruthy();
    });

    it('should not display size for folders', () => {
      render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      expect(screen.queryByText('Dimensione')).toBeFalsy();
    });
  });

  describe('Quick Actions', () => {
    it('should render preview button for files', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const previewButton = container.querySelector('button[title="Anteprima"]');
      expect(previewButton).toBeTruthy();
    });

    it('should not render preview button for folders', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      const previewButton = container.querySelector('button[title="Anteprima"]');
      expect(previewButton).toBeFalsy();
    });

    it('should render download button for files', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const downloadButton = container.querySelector('button[title="Scarica"]');
      expect(downloadButton).toBeTruthy();
    });

    it('should not render download button for folders', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} file={mockFolder} />);

      const downloadButton = container.querySelector('button[title="Scarica"]');
      expect(downloadButton).toBeFalsy();
    });

    it('should render delete button', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const deleteButton = container.querySelector('button[title="Elimina"]');
      expect(deleteButton).toBeTruthy();
    });

    it('should call onClose when close button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      // Find the close button (first ghost button with X icon in header)
      const buttons = container.querySelectorAll('button');
      const closeButton = buttons[0]; // First button is the close button
      fireEvent.click(closeButton);

      expect(defaultProps.onClose).toHaveBeenCalled();
    });

    it('should call onPreview when preview button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const previewButton = container.querySelector('button[title="Anteprima"]');
      fireEvent.click(previewButton!);

      expect(defaultProps.onPreview).toHaveBeenCalledWith(mockFile);
    });

    it('should call onDownload when download button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const downloadButton = container.querySelector('button[title="Scarica"]');
      fireEvent.click(downloadButton!);

      expect(defaultProps.onDownload).toHaveBeenCalledWith(mockFile);
    });

    it('should call onDelete when delete button is clicked', () => {
      const { container } = render(<DriveInfoPanel {...defaultProps} />);

      const deleteButton = container.querySelector('button[title="Elimina"]');
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
