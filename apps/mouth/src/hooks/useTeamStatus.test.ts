import { describe, it, expect, vi, beforeEach, afterAll } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useTeamStatus } from './useTeamStatus';

// Mock the api module
const mockGetClockStatus = vi.fn();
const mockClockIn = vi.fn();
const mockClockOut = vi.fn();

vi.mock('@/lib/api', () => ({
  api: {
    getClockStatus: (...args: unknown[]) => mockGetClockStatus(...args),
    clockIn: (...args: unknown[]) => mockClockIn(...args),
    clockOut: (...args: unknown[]) => mockClockOut(...args),
  },
}));

describe('useTeamStatus', () => {
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

  beforeEach(() => {
    vi.clearAllMocks();
    consoleErrorSpy.mockClear();
    mockGetClockStatus.mockResolvedValue({
      is_clocked_in: false,
      today_hours: 0,
      week_hours: 0,
    });
  });

  afterAll(() => {
    consoleErrorSpy.mockRestore();
  });

  describe('loadClockStatus', () => {
    it('should load clock status successfully', async () => {
      mockGetClockStatus.mockResolvedValue({
        is_clocked_in: true,
        today_hours: 4,
        week_hours: 20,
      });

      const { result } = renderHook(() => useTeamStatus());

      await act(async () => {
        await result.current.loadClockStatus();
      });

      await waitFor(() => {
        expect(result.current.isClockIn).toBe(true);
      });
    });

    it('should handle loadClockStatus error', async () => {
      mockGetClockStatus.mockRejectedValue(new Error('Failed to load'));

      const { result } = renderHook(() => useTeamStatus());

      await act(async () => {
        await result.current.loadClockStatus();
      });

      expect(consoleErrorSpy).toHaveBeenCalled();
    });
  });

  describe('toggleClock', () => {
    it('should clock in successfully', async () => {
      mockClockIn.mockResolvedValue({ success: true, message: 'Clocked in' });

      const { result } = renderHook(() => useTeamStatus());

      expect(result.current.isClockIn).toBe(false);

      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.isClockIn).toBe(true);
        expect(result.current.isLoading).toBe(false);
        expect(result.current.error).toBeNull();
      });
    });

    it('should clock out successfully', async () => {
      mockGetClockStatus.mockResolvedValue({
        is_clocked_in: true,
        today_hours: 4,
        week_hours: 20,
      });
      mockClockOut.mockResolvedValue({ success: true, message: 'Clocked out' });

      const { result } = renderHook(() => useTeamStatus());

      // Load initial state
      await act(async () => {
        await result.current.loadClockStatus();
      });

      await waitFor(() => {
        expect(result.current.isClockIn).toBe(true);
      });

      // Clock out
      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.isClockIn).toBe(false);
        expect(result.current.isLoading).toBe(false);
        expect(result.current.error).toBeNull();
      });
    });

    it('should handle clock in failure', async () => {
      mockClockIn.mockResolvedValue({ success: false, message: 'Clock in failed' });

      const { result } = renderHook(() => useTeamStatus());

      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Clock in failed');
        expect(result.current.isLoading).toBe(false);
        expect(result.current.isClockIn).toBe(false);
      });
    });

    it('should handle clock out failure', async () => {
      mockGetClockStatus.mockResolvedValue({
        is_clocked_in: true,
        today_hours: 4,
        week_hours: 20,
      });
      mockClockOut.mockResolvedValue({ success: false, message: 'Clock out failed' });

      const { result } = renderHook(() => useTeamStatus());

      // Load initial state
      await act(async () => {
        await result.current.loadClockStatus();
      });

      await waitFor(() => {
        expect(result.current.isClockIn).toBe(true);
      });

      // Try to clock out
      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Clock out failed');
        expect(result.current.isLoading).toBe(false);
        expect(result.current.isClockIn).toBe(true); // Should remain clocked in
      });
    });

    it('should handle clock in error without message', async () => {
      mockClockIn.mockResolvedValue({ success: false });

      const { result } = renderHook(() => useTeamStatus());

      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Clock in failed');
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('should handle clock out error without message', async () => {
      mockGetClockStatus.mockResolvedValue({
        is_clocked_in: true,
        today_hours: 4,
        week_hours: 20,
      });
      mockClockOut.mockResolvedValue({ success: false });

      const { result } = renderHook(() => useTeamStatus());

      await act(async () => {
        await result.current.loadClockStatus();
      });

      await waitFor(() => {
        expect(result.current.isClockIn).toBe(true);
      });

      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Clock out failed');
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('should handle network error', async () => {
      mockClockIn.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useTeamStatus());

      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
        expect(result.current.isLoading).toBe(false);
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
    });

    it('should handle non-Error exception', async () => {
      mockClockIn.mockRejectedValue('String error');

      const { result } = renderHook(() => useTeamStatus());

      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Clock toggle failed');
        expect(result.current.isLoading).toBe(false);
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
    });

    it('should not toggle when already loading', async () => {
      mockClockIn.mockImplementation(() => new Promise(() => {})); // Never resolves

      const { result } = renderHook(() => useTeamStatus());

      // Start first toggle
      act(() => {
        result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(true);
      });

      // Try to toggle again while loading
      const initialClockIn = result.current.isClockIn;
      act(() => {
        result.current.toggleClock();
      });

      // Should not change state
      expect(result.current.isClockIn).toBe(initialClockIn);
      expect(mockClockIn).toHaveBeenCalledTimes(1); // Only called once
    });

    it('should clear error on new toggle attempt', async () => {
      mockClockIn.mockResolvedValueOnce({ success: false, message: 'First error' });
      mockClockIn.mockResolvedValueOnce({ success: true, message: 'Success' });

      const { result } = renderHook(() => useTeamStatus());

      // First attempt fails
      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBe('First error');
      });

      // Second attempt succeeds
      await act(async () => {
        await result.current.toggleClock();
      });

      await waitFor(() => {
        expect(result.current.error).toBeNull();
        expect(result.current.isClockIn).toBe(true);
      });
    });
  });
});
