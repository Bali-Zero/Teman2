"use client";

import { useChatLocale } from "@/hooks/useChatLocale";

export interface ChatRecordingOverlayProps {
  isRecording: boolean;
  recordingTime: number;
}

const LABELS = {
  en: {
    recording: "Recording",
    release: "Release to send",
  },
  it: {
    recording: "Registrazione",
    release: "Rilascia per inviare",
  },
  id: {
    recording: "Merekam",
    release: "Lepas untuk mengirim",
  },
  fr: {
    recording: "Enregistrement",
    release: "Relâcher pour envoyer",
  },
  ru: {
    recording: "Запись",
    release: "Отпустите, чтобы отправить",
  },
} as const;

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function ChatRecordingOverlay({
  isRecording,
  recordingTime,
}: ChatRecordingOverlayProps) {
  const locale = useChatLocale();
  const L = LABELS[locale as keyof typeof LABELS] || LABELS.en;

  if (!isRecording) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="absolute left-1/2 -translate-x-1/2 top-[-40px] bg-black/80 text-white px-3 py-1 rounded-full text-xs font-mono flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2"
    >
      <span className="sr-only">{L.recording}</span>
      <span
        className="w-2 h-2 rounded-full bg-red-500 animate-pulse"
        aria-hidden="true"
      />
      {formatTime(recordingTime)}
      <span className="ml-2 opacity-50 text-[10px]">{L.release}</span>
    </div>
  );
}
