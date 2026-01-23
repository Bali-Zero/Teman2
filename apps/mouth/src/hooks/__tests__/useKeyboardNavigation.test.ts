/**
 * Unit tests for useKeyboardNavigation hook
 *
 * Tests cover:
 * - Arrow key navigation (up/down)
 * - Enter to open
 * - Delete/Backspace to delete
 * - Cmd/Ctrl+A to select all
 * - Space to toggle selection
 * - Escape to clear selection
 * - Shift+Arrow for range selection
 * - Home/End navigation
 * - Input field exclusion
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useKeyboardNavigation } from '../useKeyboardNavigation';
import type { FileItem } from '@/lib/api/drive/drive.types';

describe('useKeyboardNavigation', () => {
  const mockFiles: FileItem[] = [
    { id: '1', name: 'File 1', is_folder: false, mime_type: 'text/plain' },
    { id: '2', name: 'File 2', is_folder: false, mime_type: 'text/plain' },
    { id: '3', name: 'Folder 1', is_folder: true, mime_type: 'application/vnd.google-apps.folder' },
    { id: '4', name: 'File 3', is_folder: false, mime_type: 'text/plain' },
    { id: '5', name: 'File 4', is_folder: false, mime_type: 'text/plain' },
  ];

  const defaultProps = {
    files: mockFiles,
    selectedFiles: new Set<string>(),
    onSelect: vi.fn(),
    onOpen: vi.fn(),
    onDelete: vi.fn(),
    enabled: true,
  };

  const dispatchKeyEvent = (key: string, options: Partial<KeyboardEvent> = {}) => {
    const event = new KeyboardEvent('keydown', {
      key,
      bubbles: true,
      ...options,
    });
    window.dispatchEvent(event);
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Clean up
  });

  describe('Arrow Navigation', () => {
    it('should select first file on ArrowDown when nothing selected', () => {
      renderHook(() => useKeyboardNavigation(defaultProps));

      act(() => {
        dispatchKeyEvent('ArrowDown');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['1']));
    });

    it('should select next file on ArrowDown', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowDown');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['3']));
    });

    it('should select previous file on ArrowUp', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['3']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowUp');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['2']));
    });

    it('should not go below first item on ArrowUp', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['1']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowUp');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['1']));
    });

    it('should not go above last item on ArrowDown', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['5']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowDown');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['5']));
    });

    it('should handle ArrowLeft like ArrowUp', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowLeft');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['1']));
    });

    it('should handle ArrowRight like ArrowDown', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowRight');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['3']));
    });
  });

  describe('Shift+Arrow Range Selection', () => {
    it('should extend selection downward with Shift+ArrowDown', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowDown', { shiftKey: true });
      });

      // Should select from 2 to 3
      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['2', '3']));
    });

    it('should extend selection upward with Shift+ArrowUp', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['3']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowUp', { shiftKey: true });
      });

      // Should select from 2 to 3
      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['2', '3']));
    });
  });

  describe('Enter to Open', () => {
    it('should call onOpen with selected file when Enter is pressed', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('Enter');
      });

      expect(defaultProps.onOpen).toHaveBeenCalledWith(mockFiles[1]);
    });

    it('should not call onOpen when multiple files are selected', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['1', '2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('Enter');
      });

      expect(defaultProps.onOpen).not.toHaveBeenCalled();
    });

    it('should not call onOpen when no files are selected', () => {
      renderHook(() => useKeyboardNavigation(defaultProps));

      act(() => {
        dispatchKeyEvent('Enter');
      });

      expect(defaultProps.onOpen).not.toHaveBeenCalled();
    });
  });

  describe('Space to Toggle Selection', () => {
    it('should toggle selection on Space key', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent(' '); // Space key
      });

      // Should remove the selected item
      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set());
    });
  });

  describe('Select All', () => {
    it('should select all files on Cmd+A (Mac)', () => {
      renderHook(() => useKeyboardNavigation(defaultProps));

      act(() => {
        dispatchKeyEvent('a', { metaKey: true });
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['1', '2', '3', '4', '5']));
    });

    it('should select all files on Ctrl+A (Windows/Linux)', () => {
      renderHook(() => useKeyboardNavigation(defaultProps));

      act(() => {
        dispatchKeyEvent('a', { ctrlKey: true });
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['1', '2', '3', '4', '5']));
    });
  });

  describe('Escape to Clear Selection', () => {
    it('should clear selection on Escape', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['1', '2', '3']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('Escape');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set());
    });
  });

  describe('Delete', () => {
    it('should call onDelete with selected files on Delete key', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['1', '2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('Delete');
      });

      expect(defaultProps.onDelete).toHaveBeenCalledWith([mockFiles[0], mockFiles[1]]);
    });

    it('should call onDelete on Backspace key', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['3']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('Backspace');
      });

      expect(defaultProps.onDelete).toHaveBeenCalledWith([mockFiles[2]]);
    });

    it('should not call onDelete when nothing is selected', () => {
      renderHook(() => useKeyboardNavigation(defaultProps));

      act(() => {
        dispatchKeyEvent('Delete');
      });

      expect(defaultProps.onDelete).not.toHaveBeenCalled();
    });
  });

  describe('Home/End Navigation', () => {
    it('should select first file on Home key', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['4']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('Home');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['1']));
    });

    it('should select last file on End key', () => {
      const props = { ...defaultProps, selectedFiles: new Set(['2']) };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('End');
      });

      expect(defaultProps.onSelect).toHaveBeenCalledWith(new Set(['5']));
    });
  });

  describe('Disabled State', () => {
    it('should not respond to keyboard events when disabled', () => {
      const props = { ...defaultProps, enabled: false };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowDown');
      });

      expect(defaultProps.onSelect).not.toHaveBeenCalled();
    });
  });

  describe('Empty Files Array', () => {
    it('should not respond when files array is empty', () => {
      const props = { ...defaultProps, files: [] };
      renderHook(() => useKeyboardNavigation(props));

      act(() => {
        dispatchKeyEvent('ArrowDown');
      });

      expect(defaultProps.onSelect).not.toHaveBeenCalled();
    });
  });

  describe('Input Field Exclusion', () => {
    it('should not intercept events when target is an input', () => {
      renderHook(() => useKeyboardNavigation(defaultProps));

      // Create a mock input element
      const input = document.createElement('input');
      document.body.appendChild(input);
      input.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'ArrowDown',
        bubbles: true,
      });
      Object.defineProperty(event, 'target', { value: input, writable: false });

      act(() => {
        window.dispatchEvent(event);
      });

      expect(defaultProps.onSelect).not.toHaveBeenCalled();

      document.body.removeChild(input);
    });

    it('should not intercept events when target is a textarea', () => {
      renderHook(() => useKeyboardNavigation(defaultProps));

      const textarea = document.createElement('textarea');
      document.body.appendChild(textarea);
      textarea.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'ArrowDown',
        bubbles: true,
      });
      Object.defineProperty(event, 'target', { value: textarea, writable: false });

      act(() => {
        window.dispatchEvent(event);
      });

      expect(defaultProps.onSelect).not.toHaveBeenCalled();

      document.body.removeChild(textarea);
    });
  });
});
