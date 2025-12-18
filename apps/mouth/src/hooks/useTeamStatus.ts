import { useState, useCallback } from 'react';
import { api } from '@/lib/api';

const logError = (...args: unknown[]) => {
  console.error(...args);
};

export function useTeamStatus() {
  const [isClockIn, setIsClockIn] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadClockStatus = useCallback(async () => {
    try {
      const status = await api.getClockStatus();
      setIsClockIn(status.is_clocked_in);
    } catch (err) {
      logError('Failed to load clock status:', err);
    }
  }, []);

  const toggleClock = async () => {
    if (isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      if (isClockIn) {
        const result = await api.clockOut();
        if (result.success) {
          setIsClockIn(false);
        } else {
          throw new Error(result.message || 'Clock out failed');
        }
      } else {
        const result = await api.clockIn();
        if (result.success) {
          setIsClockIn(true);
        } else {
          throw new Error(result.message || 'Clock in failed');
        }
      }
    } catch (err) {
      logError('Clock toggle failed:', err);
      setError(err instanceof Error ? err.message : 'Clock toggle failed');
    } finally {
      setIsLoading(false);
    }
  };

  return {
    isClockIn,
    isLoading,
    error,
    loadClockStatus,
    toggleClock,
  };
}
