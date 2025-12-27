/**
 * @deprecated This hook was for the legacy Cell-Giant architecture.
 * Use useAgenticRAGStream or useChat instead.
 *
 * This file is kept for backward compatibility only.
 */

import { useCallback, useState } from 'react';

// Deprecated types - kept for backward compatibility
export type LegacyPhase = 'giant' | 'cell' | 'zantara';
export type PhaseStatus = 'started' | 'complete';

export interface LegacyStreamState {
  phase: LegacyPhase | null;
  phaseStatus: PhaseStatus | null;
  keepaliveElapsed: number;
  metadata: Record<string, unknown> | null;
  tokens: string;
  isStreaming: boolean;
  isComplete: boolean;
  error: string | null;
  executionTime: number | null;
}

const initialState: LegacyStreamState = {
  phase: null,
  phaseStatus: null,
  keepaliveElapsed: 0,
  metadata: null,
  tokens: '',
  isStreaming: false,
  isComplete: false,
  error: null,
  executionTime: null,
};

/**
 * @deprecated Use useAgenticRAGStream or useChat instead.
 * This hook is kept for backward compatibility only.
 */
export function useCellGiantStream(_baseUrl: string, _apiKey?: string) {
  const [state] = useState<LegacyStreamState>(initialState);

  const stream = useCallback(async () => {
    throw new Error('useCellGiantStream is deprecated. Use useAgenticRAGStream or useChat instead.');
  }, []);

  const stop = useCallback(() => {}, []);

  const reset = useCallback(() => {}, []);

  return {
    ...state,
    stream,
    stop,
    reset,
  };
}



