/**
 * Unit tests for useChatSidebar hook
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useChatSidebar } from '../useChatSidebar';

// Mock logger
vi.mock('@/lib/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock analytics
vi.mock('@/lib/analytics', () => ({
  trackEvent: vi.fn(),
}));

// Mock api
vi.mock('@/lib/api', () => ({
  api: {
    getUserProfile: vi.fn(() => ({ email: 'test@example.com' })),
  },
}));

describe('useChatSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should initialize with closed sidebar', () => {
    const { result } = renderHook(() => useChatSidebar());

    expect(result.current.sidebarOpen).toBe(false);
    expect(result.current.isSearchDocsOpen).toBe(false);
  });

  it('should open sidebar', () => {
    const { result } = renderHook(() => useChatSidebar());

    act(() => {
      result.current.openSidebar();
    });

    expect(result.current.sidebarOpen).toBe(true);
  });

  it('should close sidebar', () => {
    const { result } = renderHook(() => useChatSidebar());

    act(() => {
      result.current.openSidebar();
      result.current.closeSidebar();
    });

    expect(result.current.sidebarOpen).toBe(false);
  });

  it('should toggle sidebar', () => {
    const { result } = renderHook(() => useChatSidebar());

    act(() => {
      result.current.toggleSidebar();
    });

    expect(result.current.sidebarOpen).toBe(true);

    act(() => {
      result.current.toggleSidebar();
    });

    expect(result.current.sidebarOpen).toBe(false);
  });

  it('should open search docs modal', () => {
    const { result } = renderHook(() => useChatSidebar());

    act(() => {
      result.current.openSearchDocs();
    });

    expect(result.current.isSearchDocsOpen).toBe(true);
  });

  it('should close search docs modal', () => {
    const { result } = renderHook(() => useChatSidebar());

    act(() => {
      result.current.openSearchDocs();
      result.current.closeSearchDocs();
    });

    expect(result.current.isSearchDocsOpen).toBe(false);
  });

  it('should track analytics events', () => {
    const { result } = renderHook(() => useChatSidebar());
    const { trackEvent } = require('@/lib/analytics');

    act(() => {
      result.current.openSidebar();
    });

    expect(trackEvent).toHaveBeenCalledWith('chat_sidebar_opened', {}, 'test@example.com');

    act(() => {
      result.current.closeSidebar();
    });

    expect(trackEvent).toHaveBeenCalledWith('chat_sidebar_closed', {}, 'test@example.com');

    act(() => {
      result.current.openSearchDocs();
    });

    expect(trackEvent).toHaveBeenCalledWith('chat_search_docs_opened', {}, 'test@example.com');
  });
});
