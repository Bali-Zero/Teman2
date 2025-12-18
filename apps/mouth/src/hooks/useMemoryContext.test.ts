import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useMemoryContext, formatMemoryForDisplay, getMemorySummary } from './useMemoryContext';
import { api } from '@/lib/api';
import { UserMemoryContext } from '@/types';

// Mock the api module
vi.mock('@/lib/api', () => ({
  api: {
    isAuthenticated: vi.fn(),
    getUserMemoryContext: vi.fn(),
  },
}));

describe('useMemoryContext', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('should return null when user is not authenticated', async () => {
    vi.mocked(api.isAuthenticated).mockReturnValue(false);

    const { result } = renderHook(() => useMemoryContext());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.memoryContext).toBeNull();
    expect(result.current.hasMemory).toBe(false);
    expect(api.getUserMemoryContext).not.toHaveBeenCalled();
  });

  it('should fetch memory context when authenticated', async () => {
    const mockContext: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: ['Name: Roberto', 'Location: Torino'],
      summary: 'Interested in real estate',
      counters: { conversations: 5, searches: 10, tasks: 2 },
      has_data: true,
    };

    vi.mocked(api.isAuthenticated).mockReturnValue(true);
    vi.mocked(api.getUserMemoryContext).mockResolvedValue(mockContext);

    const { result } = renderHook(() => useMemoryContext());

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.memoryContext).toEqual(mockContext);
    expect(result.current.hasMemory).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('should handle API errors gracefully', async () => {
    vi.mocked(api.isAuthenticated).mockReturnValue(true);
    vi.mocked(api.getUserMemoryContext).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useMemoryContext());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.memoryContext).toBeNull();
    expect(result.current.error).toBe('Network error');
    expect(result.current.hasMemory).toBe(false);
  });

  it('should refresh memory context when refresh is called', async () => {
    const mockContext: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: ['Fact 1'],
      counters: {},
      has_data: true,
    };

    vi.mocked(api.isAuthenticated).mockReturnValue(true);
    vi.mocked(api.getUserMemoryContext).mockResolvedValue(mockContext);

    const { result } = renderHook(() => useMemoryContext());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Initial fetch
    expect(api.getUserMemoryContext).toHaveBeenCalledTimes(1);

    // Trigger refresh
    await act(async () => {
      await result.current.refresh();
    });

    expect(api.getUserMemoryContext).toHaveBeenCalledTimes(2);
  });
});

describe('formatMemoryForDisplay', () => {
  it('should return empty array when context is null', () => {
    expect(formatMemoryForDisplay(null)).toEqual([]);
  });

  it('should return empty array when has_data is false', () => {
    const context: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: ['Should not appear'],
      counters: {},
      has_data: false,
    };
    expect(formatMemoryForDisplay(context)).toEqual([]);
  });

  it('should format profile facts', () => {
    const context: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: ['Name: Roberto', 'Location: Torino'],
      counters: {},
      has_data: true,
    };
    expect(formatMemoryForDisplay(context)).toEqual(['Name: Roberto', 'Location: Torino']);
  });

  it('should include summary when present', () => {
    const context: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: ['Name: Roberto'],
      summary: 'Interested in eco-resorts',
      counters: {},
      has_data: true,
    };
    const result = formatMemoryForDisplay(context);
    expect(result).toContain('Name: Roberto');
    expect(result).toContain('Summary: Interested in eco-resorts');
  });
});

describe('getMemorySummary', () => {
  it('should return "No memory stored yet" when context is null', () => {
    expect(getMemorySummary(null)).toBe('No memory stored yet');
  });

  it('should return "No memory stored yet" when has_data is false', () => {
    const context: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: [],
      counters: {},
      has_data: false,
    };
    expect(getMemorySummary(context)).toBe('No memory stored yet');
  });

  it('should return "Getting to know you..." when no facts yet', () => {
    const context: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: [],
      counters: { conversations: 1 },
      has_data: true,
    };
    expect(getMemorySummary(context)).toBe('Getting to know you...');
  });

  it('should format summary with singular fact and conversation', () => {
    const context: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: ['Name: Roberto'],
      counters: { conversations: 1 },
      has_data: true,
    };
    expect(getMemorySummary(context)).toBe('1 fact learned from 1 conversation');
  });

  it('should format summary with plural facts and conversations', () => {
    const context: UserMemoryContext = {
      success: true,
      user_id: 'test@test.com',
      profile_facts: ['Name: Roberto', 'Location: Torino', 'Age: 45'],
      counters: { conversations: 5 },
      has_data: true,
    };
    expect(getMemorySummary(context)).toBe('3 facts learned from 5 conversations');
  });
});
