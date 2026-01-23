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

    it('should render all navigation items', () => {
      render(<DriveSidebar {...defaultProps} />);

      expect(screen.getByText('Il mio Drive')).toBeTruthy();
      expect(screen.getByText('Recenti')).toBeTruthy();
      expect(screen.getByText('Speciali')).toBeTruthy();
      expect(screen.getByText('Cestino')).toBeTruthy();
    });

    it('should highlight active navigation item', () => {
      const { container } = render(<DriveSidebar {...defaultProps} activeView="my-drive" />);

      // Active item should have blue background
      const activeItem = container.querySelector('.bg-\\[\\#e8f0fe\\]');
      expect(activeItem).toBeTruthy();
      expect(activeItem?.textContent).toContain('Il mio Drive');
    });

    it('should call onNewClick when "Nuovo" button is clicked', () => {
      render(<DriveSidebar {...defaultProps} />);

      const nuovoButton = screen.getByText('Nuovo').closest('button');
      fireEvent.click(nuovoButton!);

      expect(defaultProps.onNewClick).toHaveBeenCalled();
    });

    it('should call onViewChange when navigation item is clicked', () => {
      render(<DriveSidebar {...defaultProps} />);

      const myDriveButton = screen.getByText('Il mio Drive').closest('button');
      fireEvent.click(myDriveButton!);

      expect(defaultProps.onViewChange).toHaveBeenCalledWith('my-drive');
    });

    it('should show disabled state for non-implemented views', () => {
      render(<DriveSidebar {...defaultProps} />);

      // Recenti, Speciali, Cestino should be disabled
      const prestoLabels = screen.getAllByText('Presto');
      expect(prestoLabels.length).toBe(3); // 3 disabled items
    });

    it('should render storage indicator', () => {
      render(<DriveSidebar {...defaultProps} storageUsed={5 * 1024 * 1024 * 1024} />);

      expect(screen.getByText('Spazio di archiviazione')).toBeTruthy();
      expect(screen.getByText(/5\.0 GB/)).toBeTruthy();
    });

    it('should show progress bar with correct color for low usage', () => {
      const { container } = render(
        <DriveSidebar
          {...defaultProps}
          storageUsed={1 * 1024 * 1024 * 1024}
          storageTotal={15 * 1024 * 1024 * 1024}
        />
      );

      // Low usage should be blue
      const progressBar = container.querySelector('.bg-\\[\\#1a73e8\\]');
      expect(progressBar).toBeTruthy();
    });

    it('should show yellow progress bar for medium usage (70-90%)', () => {
      const { container } = render(
        <DriveSidebar
          {...defaultProps}
          storageUsed={12 * 1024 * 1024 * 1024}
          storageTotal={15 * 1024 * 1024 * 1024}
        />
      );

      // Medium usage should be yellow
      const progressBar = container.querySelector('.bg-\\[\\#fbbc04\\]');
      expect(progressBar).toBeTruthy();
    });

    it('should show red progress bar for high usage (>90%)', () => {
      const { container } = render(
        <DriveSidebar
          {...defaultProps}
          storageUsed={14 * 1024 * 1024 * 1024}
          storageTotal={15 * 1024 * 1024 * 1024}
        />
      );

      // High usage should be red
      const progressBar = container.querySelector('.bg-\\[\\#ea4335\\]');
      expect(progressBar).toBeTruthy();
    });
  });

  describe('Collapsed State', () => {
    it('should render compact "New" button in collapsed state', () => {
      const { container } = render(<DriveSidebar {...defaultProps} isCollapsed />);

      // Should have a plus icon button
      const plusButton = container.querySelector('.w-12.h-12');
      expect(plusButton).toBeTruthy();
    });

    it('should render icon-only navigation in collapsed state', () => {
      const { container } = render(<DriveSidebar {...defaultProps} isCollapsed />);

      // Should have icon buttons but no text labels visible
      const navButtons = container.querySelectorAll('.rounded-full.p-3');
      expect(navButtons.length).toBe(4); // 4 nav items
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
