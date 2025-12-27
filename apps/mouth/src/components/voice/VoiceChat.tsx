/**
 * Voice Chat Component
 * Speech-to-text input and text-to-speech output
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { AudioVoice } from '@/lib/api/zantara-sdk/types';
import { ZantaraSDK } from '@/lib/api/zantara-sdk';
import { cn } from '@/lib/utils';

export interface VoiceChatProps {
  sdk: ZantaraSDK;
  onTranscribe?: (text: string) => void;
  onSpeak?: (text: string) => void;
  onVoiceChange?: (voice: AudioVoice) => void;
  voice?: AudioVoice;
  disabled?: boolean;
}

const VOICES: { value: AudioVoice; label: string; description: string }[] = [
  { value: 'alloy', label: 'Alloy', description: 'Neutral and balanced' },
  { value: 'echo', label: 'Echo', description: 'Warm and deep' },
  { value: 'fable', label: 'Fable', description: 'British and expressive' },
  { value: 'onyx', label: 'Onyx', description: 'Deep and authoritative' },
  { value: 'nova', label: 'Nova', description: 'Professional and clear' },
  { value: 'shimmer', label: 'Shimmer', description: 'Clear and bright' },
];

export function VoiceChat({
  sdk,
  onTranscribe,
  onSpeak,
  onVoiceChange,
  voice = 'alloy',
  disabled = false,
}: VoiceChatProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [transcribedText, setTranscribedText] = useState('');
  const [textToSpeak, setTextToSpeak] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentVoice, setCurrentVoice] = useState<AudioVoice>(voice);
  const [recordingTime, setRecordingTime] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      // Cleanup
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRecording]);

  const startRecording = async () => {
    try {
      setError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Determine supported mime type
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') 
        ? 'audio/webm' 
        : 'audio/mp4';
        
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        await handleTranscribe(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to access microphone');
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleTranscribe = async (audioBlob: Blob) => {
    setIsProcessing(true);
    setError(null);
    try {
      const extension = audioBlob.type.includes('webm') ? 'webm' : 'm4a';
      const audioFile = new File([audioBlob], `recording.${extension}`, { type: audioBlob.type });
      
      const result = await sdk.transcribeAudio({
        file: audioFile,
      });

      const text = result.text || '';
      setTranscribedText(text);
      onTranscribe?.(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcription failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSpeak = async () => {
    if (!textToSpeak.trim()) return;

    setIsProcessing(true);
    setError(null);
    try {
      const audioBlob = await sdk.generateSpeech({
        text: textToSpeak,
        voice: currentVoice,
      });

      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = () => {
        setError('Failed to play audio');
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
      setIsPlaying(true);
      onSpeak?.(textToSpeak);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Speech generation failed');
      setIsPlaying(false);
    } finally {
      setIsProcessing(false);
    }
  };

  const stopSpeaking = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlaying(false);
    }
  };

  const handleVoiceChange = (value: string) => {
    const newVoice = value as AudioVoice;
    setCurrentVoice(newVoice);
    onVoiceChange?.(newVoice);
  };

  return (
    <div className="space-y-6 p-4 border rounded-xl bg-card">
      {/* Transcription Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-foreground">Voice Input</label>
          {isRecording && (
            <span className="text-xs font-mono text-destructive animate-pulse flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-destructive" />
              {formatTime(recordingTime)}
            </span>
          )}
        </div>
        
        <div className="flex flex-wrap gap-3 items-center">
          <Button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={disabled || (isProcessing && !isRecording)}
            variant={isRecording ? 'destructive' : 'default'}
            className={cn(
              "flex items-center gap-2 min-w-[160px] transition-all",
              isRecording && "ring-2 ring-destructive ring-offset-2"
            )}
          >
            {isRecording ? (
              <>
                <MicOff className="h-4 w-4" />
                Stop Recording
              </>
            ) : (
              <>
                <Mic className="h-4 w-4" />
                Start Recording
              </>
            )}
          </Button>
          
          {isProcessing && !isRecording && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Processing audio...
            </div>
          )}
        </div>

        {transcribedText && (
          <div className="p-4 bg-muted/50 rounded-lg border border-border animate-in fade-in slide-in-from-top-1">
            <p className="text-sm leading-relaxed">{transcribedText}</p>
          </div>
        )}
      </div>

      <div className="h-px bg-border" />

      {/* Text-to-Speech Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-foreground">Text-to-Speech</label>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Voice:</span>
            <Select 
              value={currentVoice} 
              onValueChange={handleVoiceChange}
              disabled={disabled || isProcessing || isPlaying}
            >
              <SelectTrigger className="h-8 w-[140px] text-xs">
                <SelectValue placeholder="Select voice" />
              </SelectTrigger>
              <SelectContent>
                {VOICES.map((v) => (
                  <SelectItem key={v.value} value={v.value} className="text-xs">
                    <div className="flex flex-col">
                      <span>{v.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex gap-2">
          <Input
            value={textToSpeak}
            onChange={(e) => setTextToSpeak(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!isPlaying) handleSpeak();
              }
            }}
            placeholder="Type what you want me to say..."
            disabled={disabled || isProcessing}
            className="flex-1"
          />
          {isPlaying ? (
            <Button onClick={stopSpeaking} variant="outline" className="shrink-0 border-destructive text-destructive hover:bg-destructive/10">
              <VolumeX className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={handleSpeak}
              disabled={disabled || isProcessing || !textToSpeak.trim()}
              className="shrink-0"
            >
              {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Volume2 className="h-4 w-4" />}
            </Button>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex gap-2 items-start animate-in shake">
          <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
          <p className="text-sm text-destructive font-medium">{error}</p>
        </div>
      )}
    </div>
  );
}





