'use client';

import { useReducer, useCallback, useEffect, createContext, useContext } from 'react';
import type { NavigationState, NavigationAction } from '@/lib/types';

const initialState: NavigationState = {
  level: 'orbital',
  province: null,
  institution: null,
  selectedOfficial: null,
};

function navigationReducer(state: NavigationState, action: NavigationAction): NavigationState {
  switch (action.type) {
    case 'DIVE_PROVINCE':
      return { ...state, level: 'provincial', province: action.province, institution: null, selectedOfficial: null };
    case 'DIVE_INSTITUTION':
      return { ...state, level: 'authority', institution: action.institution, selectedOfficial: null };
    case 'SELECT_OFFICIAL':
      return { ...state, selectedOfficial: action.name };
    case 'BACK':
      if (state.level === 'authority') return { ...state, level: 'provincial', institution: null, selectedOfficial: null };
      if (state.level === 'provincial') return { ...state, level: 'orbital', province: null, institution: null, selectedOfficial: null };
      return state;
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

interface LevelContextValue {
  state: NavigationState;
  dispatch: React.Dispatch<NavigationAction>;
  goBack: () => void;
}

export const LevelContext = createContext<LevelContextValue | null>(null);

export function useLevel() {
  const ctx = useContext(LevelContext);
  if (!ctx) throw new Error('useLevel must be used within LevelProvider');
  return ctx;
}

export function useLevelReducer() {
  const [state, dispatch] = useReducer(navigationReducer, initialState);

  const goBack = useCallback(() => dispatch({ type: 'BACK' }), []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') goBack();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [goBack]);

  return { state, dispatch, goBack };
}
