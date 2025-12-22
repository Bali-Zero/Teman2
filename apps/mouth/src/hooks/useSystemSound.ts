'use client';

import { useCallback, useRef } from 'react';

type SoundType = 'auth_start' | 'access_granted' | 'access_denied' | 'focus';

interface UseSystemSoundReturn {
  play: (soundType: SoundType) => void;
}

/**
 * Hook for playing system sounds
 *
 * Currently implements a silent/no-op version that doesn't block the build.
 * Can be extended later with actual audio files or Web Audio API synthesis.
 */
export function useSystemSound(): UseSystemSoundReturn {
  const play = useCallback((soundType: SoundType) => {
    // Silent implementation - doesn't block build
    // Can be extended with actual audio playback later

    // Optional: Log for debugging (can be removed in production)
    if (process.env.NODE_ENV === 'development') {
      console.log(`[SystemSound] Playing: ${soundType}`);
    }

    // Future implementation could:
    // 1. Load audio files from /public/sounds/
    // 2. Use Web Audio API to synthesize sounds
    // 3. Use HTMLAudioElement for simple playback

    // Example future implementation:
    // try {
    //   const audio = new Audio(`/sounds/${soundType}.mp3`);
    //   audio.volume = 0.5;
    //   audio.play().catch(() => {
    //     // Silently fail if audio can't play (user interaction required, etc.)
    //   });
    // } catch (error) {
    //   // Silently fail if audio not supported
    // }
  }, []);

  return { play };
}
