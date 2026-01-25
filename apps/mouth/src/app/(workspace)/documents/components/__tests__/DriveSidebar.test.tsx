/**
 * Unit tests for DriveSidebar component
 *
 * Tests cover:
 * - Rendering in expanded state
 * - Rendering in collapsed state
 * - Navigation items
 * - New button functionality
 * - Storage indicator
 * - Active state styling
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DriveSidebar } from '../DriveSidebar';

describe('DriveSidebar', () => {
  const defaultProps = {
    activeView: 'my-drive' as const,
    onViewChange: vi.fn(),
    onNewClick: vi.fn(),
    onUploadClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Expanded State', () => {
    it('should render "Nuovo" button', () => {
      render(<DriveSidebar {...defaultProps} />);

      expect(screen.getByText('Nuovo')).toBeTruthy();
    });

    it('should render navigation items', () => {
      render(<DriveSidebar {...defaultProps} />);

      expect(screen.getByText('Bali Zero Drive')).toBeTruthy();
    });

    it('should highlight active navigation item', () => {
      const { container } = render(<DriveSidebar {...defaultProps} activeView="my-drive" />);

      // Active item should have blue background (bg-blue-50)
      const activeItem = container.querySelector('.bg-blue-50');
      expect(activeItem).toBeTruthy();
      expect(activeItem?.textContent).toContain('Bali Zero Drive');
    });

    it('should call onNewClick when "Nuovo" button is clicked', () => {
      render(<DriveSidebar {...defaultProps} />);

      const newButton = screen.getByText('Nuovo').closest('button');
      fireEvent.click(newButton!);

      expect(defaultProps.onNewClick).toHaveBeenCalled();
    });

    it('should call onViewChange when navigation item is clicked', () => {
      render(<DriveSidebar {...defaultProps} />);

      const myDriveButton = screen.getByText('Bali Zero Drive').closest('button');
      fireEvent.click(myDriveButton!);

      expect(defaultProps.onViewChange).toHaveBeenCalledWith('my-drive');
    });

    it('should render storage indicator', () => {
      render(<DriveSidebar {...defaultProps} storageUsed={5 * 1024 * 1024 * 1024} />);

      expect(screen.getByText('Spazio')).toBeTruthy();
      expect(screen.getByText(/utilizzati/)).toBeTruthy();
    });

    it('should show progress bar with blue color', () => {
      const { container } = render(
        <DriveSidebar
          {...defaultProps}
          storageUsed={1 * 1024 * 1024 * 1024}
          storageTotal={15 * 1024 * 1024 * 1024}
        />
      );

      // Progress bar should be blue
      const progressBar = container.querySelector('.bg-blue-500');
      expect(progressBar).toBeTruthy();
    });

    it('should show storage usage text', () => {
      render(
        <DriveSidebar
          {...defaultProps}
          storageUsed={11 * 1024 * 1024 * 1024}
          storageTotal={15 * 1024 * 1024 * 1024}
        />
      );

      expect(screen.getByText(/utilizzati/)).toBeTruthy();
    });

    it('should show total storage', () => {
      render(
        <DriveSidebar
          {...defaultProps}
          storageUsed={14 * 1024 * 1024 * 1024}
          storageTotal={15 * 1024 * 1024 * 1024}
        />
      );

      expect(screen.getByText(/15\.0 GB/)).toBeTruthy();
    });
  });

  describe('Collapsed State', () => {
    it('should render compact "New" button in collapsed state', () => {
      const { container } = render(<DriveSidebar {...defaultProps} isCollapsed />);

      // Should have a plus icon button with specific size
      const plusButton = container.querySelector('.w-12.h-12');
      expect(plusButton).toBeTruthy();
    });

    it('should render icon-only navigation in collapsed state', () => {
      const { container } = render(<DriveSidebar {...defaultProps} isCollapsed />);

      // Should have icon buttons but no text labels visible
      const navButtons = container.querySelectorAll('.rounded-full.p-3');
      expect(navButtons.length).toBe(1); // Only 'Bali Zero Drive' exists now
    });

    it('should have title attributes for accessibility in collapsed state', () => {
      const { container } = render(<DriveSidebar {...defaultProps} isCollapsed />);

      const buttons = container.querySelectorAll('button[title]');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Storage Formatting', () => {
    it('should format MB correctly', () => {
      render(<DriveSidebar {...defaultProps} storageUsed={500 * 1024 * 1024} />);

      expect(screen.getByText(/500 MB/)).toBeTruthy();
    });

    it('should format GB correctly', () => {
      render(<DriveSidebar {...defaultProps} storageUsed={2.5 * 1024 * 1024 * 1024} />);

      expect(screen.getByText(/2\.5 GB/)).toBeTruthy();
    });
  });
});
