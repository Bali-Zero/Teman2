import { useState, useRef, useCallback, useEffect } from 'react';

export interface AudioRecorderState {
  isRecording: boolean;
  isPaused: boolean;
  recordingTime: number; // in seconds
  audioBlob: Blob | null;
}

export const useAudioRecorder = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioMimeType, setAudioMimeType] = useState<string>('audio/webm');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);

  // #region agent log
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location: 'useAudioRecorder.ts:cleanup',
          message: 'Component unmounted',
          data: {
            hasTimer: timerRef.current !== null,
            isRecording: isRecording,
            hasMediaRecorder: mediaRecorderRef.current !== null,
          },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'D',
        }),
      }).catch(() => {});
    };
  }, [isRecording]);
  // #endregion

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Determine supported mime type
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4'; // Safari support
      }
      setAudioMimeType(mimeType);

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setAudioBlob(blob);

        // Stop all tracks to release microphone
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(200); // Collect chunks every 200ms for responsiveness if needed
      setIsRecording(true);
      setIsPaused(false);
      setRecordingTime(0);
      setAudioBlob(null);

      // Start timer
      timerRef.current = setInterval(() => {
        // #region agent log
        if (!isMountedRef.current) {
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              location: 'useAudioRecorder.ts:timer:unmounted',
              message: 'Timer callback after unmount',
              data: {},
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'run1',
              hypothesisId: 'D',
            }),
          }).catch(() => {});
          return;
        }
        // #endregion
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('Error accessing microphone:', error);
      throw error;
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsPaused(false);

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [isRecording]);

  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsPaused(false);
      setAudioBlob(null);
      setRecordingTime(0);
      chunksRef.current = []; // Clear chunks

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [isRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location: 'useAudioRecorder.ts:cleanup:effect',
          message: 'Cleanup effect running',
          data: {
            hasTimer: timerRef.current !== null,
            isRecording: isRecording,
            hasMediaRecorder: mediaRecorderRef.current !== null,
            recorderState: mediaRecorderRef.current?.state,
          },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'D',
        }),
      }).catch(() => {});
      // #endregion

      isMountedRef.current = false;
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try {
          mediaRecorderRef.current.stop();
        } catch (e) {
          // Ignore errors if already stopped
        }
        mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      }
      chunksRef.current = [];
    };
  }, [isRecording]);

  return {
    isRecording,
    isPaused,
    recordingTime,
    audioBlob,
    audioMimeType,
    startRecording,
    stopRecording,
    cancelRecording,
  };
};
