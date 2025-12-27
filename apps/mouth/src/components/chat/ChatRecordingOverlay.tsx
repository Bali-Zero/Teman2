'use client';

export interface ChatRecordingOverlayProps {
  isRecording: boolean;
  recordingTime: number;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function ChatRecordingOverlay({
  isRecording,
  recordingTime,
}: ChatRecordingOverlayProps) {
  if (!isRecording) {
    return null;
  }

  return (
    <div className="absolute left-1/2 -translate-x-1/2 top-[-40px] bg-black/80 text-white px-3 py-1 rounded-full text-xs font-mono flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
      {formatTime(recordingTime)}
      <span className="ml-2 opacity-50 text-[10px]">Release to send</span>
    </div>
  );
}
