import { useCallback, useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { useAudioRecorder } from './useAudioRecorder';

export interface UseChatAudioOptions {
  onTranscriptionStart?: () => void;
  onTranscriptionComplete?: (text: string) => void;
  onTranscriptionError?: (error: Error) => void;
  isMountedRef?: React.MutableRefObject<boolean>;
}

export interface UseChatAudioReturn {
  isRecording: boolean;
  isPaused: boolean;
  recordingTime: number;
  audioBlob: Blob | null;
  audioMimeType: string;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  cancelRecording: () => void;
  transcribeAudio: (blob: Blob, mimeType: string) => Promise<string | null>;
}

export function useChatAudio(options: UseChatAudioOptions = {}): UseChatAudioReturn {
  const {
    onTranscriptionStart,
    onTranscriptionComplete,
    onTranscriptionError,
    isMountedRef: externalMountedRef,
  } = options;

  const internalMountedRef = useRef(true);
  const isMountedRef = externalMountedRef || internalMountedRef;

  useEffect(() => {
    if (!externalMountedRef) {
      internalMountedRef.current = true;
      return () => {
        internalMountedRef.current = false;
      };
    }
  }, [externalMountedRef]);

  const {
    isRecording,
    isPaused,
    recordingTime,
    audioBlob,
    audioMimeType,
    startRecording: baseStartRecording,
    stopRecording,
    cancelRecording,
  } = useAudioRecorder();

  const startRecording = useCallback(async () => {
    try {
      await baseStartRecording();
    } catch (error) {
      throw error;
    }
  }, [baseStartRecording]);

  const transcribeAudio = useCallback(
    async (blob: Blob, mimeType: string): Promise<string | null> => {
      if (!isMountedRef.current) return null;

      try {
        onTranscriptionStart?.();
        const text = await api.transcribeAudio(blob, mimeType);

        if (!isMountedRef.current) return null;

        if (text) {
          onTranscriptionComplete?.(text);
          return text;
        } else {
          const error = new Error('Could not transcribe audio');
          onTranscriptionError?.(error);
          return null;
        }
      } catch (err) {
        if (!isMountedRef.current) return null;
        console.error('Transcription error:', err);
        onTranscriptionError?.(err as Error);
        return null;
      }
    },
    [isMountedRef, onTranscriptionStart, onTranscriptionComplete, onTranscriptionError]
  );

  // Auto-transcribe when audioBlob changes
  useEffect(() => {
    if (audioBlob && isMountedRef.current) {
      transcribeAudio(audioBlob, audioMimeType);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioBlob, audioMimeType]);

  return {
    isRecording,
    isPaused,
    recordingTime,
    audioBlob,
    audioMimeType,
    startRecording,
    stopRecording,
    cancelRecording,
    transcribeAudio,
  };
}
