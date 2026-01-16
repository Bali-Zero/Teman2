/**
 * Unit tests for useChatInput hook
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatInput } from '../useChatInput';

// Mock logger
vi.mock('@/lib/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

describe('useChatInput', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should initialize with empty state', () => {
    const { result } = renderHook(() => useChatInput());

    expect(result.current.input).toBe('');
    expect(result.current.attachedImages).toEqual([]);
    expect(result.current.imageGenPrompt).toBe('');
    expect(result.current.fileInputRef.current).toBeNull();
    expect(result.current.imageInputRef.current).toBeNull();
  });

  it('should update input value', () => {
    const { result } = renderHook(() => useChatInput());

    act(() => {
      result.current.setInput('Hello world');
    });

    expect(result.current.input).toBe('Hello world');
  });

  it('should clear input', () => {
    const { result } = renderHook(() => useChatInput());

    act(() => {
      result.current.setInput('Hello');
      result.current.clearInput();
    });

    expect(result.current.input).toBe('');
  });

  it('should handle image attachment', async () => {
    const { result } = renderHook(() => useChatInput());

    // Mock FileReader
    let onloadendCallback: (() => void) | null = null;
    const mockFileReader = {
      readAsDataURL: vi.fn(function(this: any, file: File) {
        // Simulate async read
        setTimeout(() => {
          if (this.onloadend) {
            this.onloadend();
          }
        }, 0);
      }),
      result: 'data:image/png;base64,test',
      onloadend: null as any,
      onerror: null as any,
    };

    global.FileReader = vi.fn(function(this: any) {
      Object.assign(this, mockFileReader);
      return this;
    }) as any;

    // Create mock file
    const file = new File(['test'], 'test.png', { type: 'image/png' });
    Object.defineProperty(file, 'size', { value: 1000 });
    
    const fileList = {
      0: file,
      length: 1,
      item: (index: number) => (index === 0 ? file : null),
      [Symbol.iterator]: function* () {
        yield file;
      },
    } as FileList;

    const event = {
      target: {
        files: fileList,
        value: '',
      },
    } as any;

    act(() => {
      result.current.handleImageAttach(event);
    });

    // Wait for FileReader to complete
    await waitFor(() => {
      expect(result.current.attachedImages.length).toBeGreaterThan(0);
    }, { timeout: 1000 });

    expect(result.current.attachedImages.length).toBe(1);
    expect(result.current.attachedImages[0].name).toBe('test.png');
  });

  it('should reject non-image files', async () => {
    const { result } = renderHook(() => useChatInput());
    const showToast = vi.fn();
    
    // Set toast callback first
    act(() => {
      result.current.setShowToast(showToast);
    });

    // Wait for state to update - verify callback is set by calling showToast
    await waitFor(() => {
      result.current.showToast('test', 'success');
      return showToast.mock.calls.length > 0;
    });

    // Reset mock
    showToast.mockClear();

    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    Object.defineProperty(file, 'size', { value: 1000 });
    
    const fileList = {
      0: file,
      length: 1,
      item: (index: number) => (index === 0 ? file : null),
      [Symbol.iterator]: function* () {
        yield file;
      },
    } as FileList;

    const event = {
      target: {
        files: fileList,
        value: '',
      },
    } as any;

    act(() => {
      result.current.handleImageAttach(event);
    });

    // Toast is called synchronously during validation
    expect(showToast).toHaveBeenCalledWith('Please select an image file', 'error');
    expect(result.current.attachedImages.length).toBe(0);
  });

  it('should reject files larger than 10MB', async () => {
    const { result } = renderHook(() => useChatInput());
    const showToast = vi.fn();
    
    // Set toast callback first
    act(() => {
      result.current.setShowToast(showToast);
    });

    // Wait for state to update - verify callback is set by calling showToast
    await waitFor(() => {
      result.current.showToast('test', 'success');
      return showToast.mock.calls.length > 0;
    });

    // Reset mock
    showToast.mockClear();

    // Create a file larger than 10MB
    const largeFile = new File(['x'], 'large.png', { type: 'image/png' });
    Object.defineProperty(largeFile, 'size', { value: 11 * 1024 * 1024 });

    const fileList = {
      0: largeFile,
      length: 1,
      item: (index: number) => (index === 0 ? largeFile : null),
      [Symbol.iterator]: function* () {
        yield largeFile;
      },
    } as FileList;

    const event = {
      target: {
        files: fileList,
        value: '',
      },
    } as any;

    act(() => {
      result.current.handleImageAttach(event);
    });

    // Toast is called synchronously during validation
    expect(showToast).toHaveBeenCalledWith('Image must be less than 10MB', 'error');
  });

  it('should remove attached image', () => {
    const { result } = renderHook(() => useChatInput());

    act(() => {
      result.current.setAttachedImages([
        { id: '1', base64: 'data:image/png;base64,test1', name: 'test1.png', size: 1000 },
        { id: '2', base64: 'data:image/png;base64,test2', name: 'test2.png', size: 2000 },
      ]);
      result.current.removeAttachedImage('1');
    });

    expect(result.current.attachedImages.length).toBe(1);
    expect(result.current.attachedImages[0].id).toBe('2');
  });

  it('should clear attachments', () => {
    const { result } = renderHook(() => useChatInput());

    act(() => {
      result.current.setAttachedImages([
        { id: '1', base64: 'data:image/png;base64,test1', name: 'test1.png', size: 1000 },
      ]);
      result.current.clearAttachments();
    });

    expect(result.current.attachedImages.length).toBe(0);
  });

  it('should handle image button click', () => {
    const { result } = renderHook(() => useChatInput());

    // Create a mock input element
    const mockInput = document.createElement('input');
    mockInput.click = vi.fn();
    result.current.imageInputRef.current = mockInput;

    act(() => {
      result.current.handleImageButtonClick();
    });

    expect(mockInput.click).toHaveBeenCalled();
  });

  it('should update image generation prompt', () => {
    const { result } = renderHook(() => useChatInput());

    act(() => {
      result.current.setImageGenPrompt('A beautiful sunset');
    });

    expect(result.current.imageGenPrompt).toBe('A beautiful sunset');
  });

  it('should call toast callback when set', async () => {
    const { result } = renderHook(() => useChatInput());
    const showToast = vi.fn();

    act(() => {
      result.current.setShowToast(showToast);
    });

    // Wait for state to update - verify callback is set by calling showToast
    await waitFor(() => {
      result.current.showToast('test', 'success');
      return showToast.mock.calls.length > 0;
    });

    // Reset mock
    showToast.mockClear();

    act(() => {
      result.current.showToast('Test message', 'success');
    });

    expect(showToast).toHaveBeenCalledWith('Test message', 'success');
  });
});
