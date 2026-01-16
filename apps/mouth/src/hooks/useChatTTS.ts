/**
 * Custom hook for managing Text-to-Speech (TTS) functionality
 * 
 * Handles:
 * - TTS generation and playback
 * - Audio state management
 * - Cleanup on unmount
 * - Error handling
 * 
 * @returns TTS state and handlers
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { chatMetrics } from '@/lib/metrics';
import { trackEvent } from '@/lib/analytics';

export interface UseChatTTSReturn {
  // State
  playingMessageId: string | null;
  ttsLoading: string | null;
  
  // Handlers
  handleTTS: (messageId: string, text: string) => Promise<void>;
  stopTTS: () => void;
  
  // Toast callback
  showToast: (message: string, type: 'success' | 'error') => void;
  setShowToast: (callback: (message: string, type: 'success' | 'error') => void) => void;
}

const TTS_VOICE = 'nova';

export function useChatTTS(): UseChatTTSReturn {
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [ttsLoading, setTtsLoading] = useState<string | null>(null);
  const [toastCallback, setToastCallback] = useState<((message: string, type: 'success' | 'error') => void) | null>(null);
  
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const toastCallbackRef = useRef<((message: string, type: 'success' | 'error') => void) | null>(null);

  // Keep ref in sync with state (synchronously for immediate access)
  toastCallbackRef.current = toastCallback;

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    if (toastCallbackRef.current) {
      toastCallbackRef.current(message, type);
    }
  }, []);

  const setShowToastWrapper = useCallback((callback: (message: string, type: 'success' | 'error') => void) => {
    // Wrap in function to avoid React treating callback as updater function
    setToastCallback(() => callback);
  }, []);

  const stopTTS = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setPlayingMessageId(null);
    setTtsLoading(null);
  }, []);

  const handleTTS = useCallback(async (messageId: string, text: string) => {
    // If already playing this message, stop it
    if (playingMessageId === messageId) {
      logger.debug('TTS stopped (already playing)', {
        component: 'useChatTTS',
        action: 'handleTTS',
        metadata: { messageId },
      });
      stopTTS();
      return;
    }

    logger.info('TTS started', {
      component: 'useChatTTS',
      action: 'handleTTS',
      metadata: { messageId, textLength: text.length, voice: TTS_VOICE },
    });

    // Track metrics
    chatMetrics.ttsStarted(messageId);

    // Stop any currently playing audio and cleanup
    stopTTS();

    const ttsStartTime = Date.now();
    try {
      setTtsLoading(messageId);
      const audioBlob = await api.generateSpeech(text, TTS_VOICE);

      // Validate audio blob
      if (!audioBlob || audioBlob.size === 0) {
        throw new Error('Invalid audio blob received');
      }

      const audioUrl = URL.createObjectURL(audioBlob);
      audioUrlRef.current = audioUrl;
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      // Remove old event listeners if they exist (defensive)
      audio.onended = () => {
        if (audioUrlRef.current === audioUrl) {
          const ttsDuration = Date.now() - ttsStartTime;
          logger.info('TTS completed', {
            component: 'useChatTTS',
            action: 'handleTTS',
            metadata: { messageId, duration: ttsDuration },
          });

          // Track metrics
          chatMetrics.ttsCompleted(messageId, ttsDuration / 1000);

          const userProfile = api.getUserProfile();
          trackEvent('chat_tts_completed', { messageId, duration: ttsDuration }, userProfile?.email);

          setPlayingMessageId(null);
          URL.revokeObjectURL(audioUrl);
          audioUrlRef.current = null;
          audioRef.current = null;
        }
      };

      audio.onerror = (e) => {
        const errorMessage = e instanceof Error ? e.message : 'Unknown playback error';
        logger.error('TTS audio playback error', {
          component: 'useChatTTS',
          action: 'handleTTS',
          metadata: { messageId, errorMessage },
        }, e instanceof Error ? e : new Error(String(e)));

        if (audioUrlRef.current === audioUrl) {
          // Track metrics
          chatMetrics.ttsError(messageId, 'playback');

          const userProfile = api.getUserProfile();
          trackEvent('chat_tts_error', { messageId, errorType: 'playback', errorMessage }, userProfile?.email);

          if (toastCallbackRef.current) {
            toastCallbackRef.current('Audio playback failed', 'error');
          }
          setPlayingMessageId(null);
          URL.revokeObjectURL(audioUrl);
          audioUrlRef.current = null;
          audioRef.current = null;
        }
      };

      // Handle play promise rejection
      try {
        setTtsLoading(null);
        setPlayingMessageId(messageId);
        await audio.play();
        
        const userProfile = api.getUserProfile();
        trackEvent('chat_tts_started', { messageId, textLength: text.length }, userProfile?.email);
      } catch (playError) {
        const errorMessage = playError instanceof Error ? playError.message : 'Unknown play error';
        logger.error('TTS audio play error', {
          component: 'useChatTTS',
          action: 'handleTTS',
          metadata: { messageId, errorType: playError instanceof Error ? playError.name : 'Unknown' },
        }, playError instanceof Error ? playError : new Error(String(playError)));

        // Track metrics
        chatMetrics.ttsError(messageId, 'play');

        const userProfile = api.getUserProfile();
        trackEvent('chat_tts_error', { messageId, errorType: 'play', errorMessage }, userProfile?.email);

        // Cleanup on play failure
        URL.revokeObjectURL(audioUrl);
        audioUrlRef.current = null;
        audioRef.current = null;
        setTtsLoading(null);
        setPlayingMessageId(null);
        if (toastCallbackRef.current) {
          toastCallbackRef.current('Failed to play audio. Please try again.', 'error');
        }
      }
    } catch (error) {
      // Cleanup on generation failure
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      audioRef.current = null;
      setTtsLoading(null);
      setPlayingMessageId(null);
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      const errorType = error instanceof Error ? error.name : 'Unknown';
      
      logger.error('TTS generation failed', {
        component: 'useChatTTS',
        action: 'handleTTS',
        metadata: { messageId, errorType, errorMessage },
      }, error instanceof Error ? error : new Error(String(error)));

      if (toastCallbackRef.current) {
        if (errorMessage.includes('timeout') || errorMessage.includes('Timeout')) {
          toastCallbackRef.current('TTS generation timeout. Please try again.', 'error');
        } else if (errorMessage.includes('429') || errorMessage.includes('rate limit')) {
          toastCallbackRef.current('Too many TTS requests. Please wait a moment.', 'error');
        } else {
          toastCallbackRef.current('TTS generation failed. Please try again.', 'error');
        }
      }
    }
  }, [playingMessageId, stopTTS]);

  // Cleanup audio and URLs on unmount
  useEffect(() => {
    return () => {
      // Stop and cleanup audio element
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
        audioRef.current = null;
      }
      // Revoke any pending URLs
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, []);

  return {
    playingMessageId,
    ttsLoading,
    handleTTS,
    stopTTS,
    showToast,
    setShowToast: setShowToastWrapper,
  };
}
