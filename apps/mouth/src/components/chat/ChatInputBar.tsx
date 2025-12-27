'use client';

import { Button } from '@/components/ui/button';
import { UI } from '@/constants';
import {
  Send,
  ImageIcon,
  Plus,
  Loader2,
  Upload,
  Camera,
  Mic,
} from 'lucide-react';
import { ChatRecordingOverlay } from './ChatRecordingOverlay';

export interface ChatInputBarProps {
  input: string;
  setInput: (value: string) => void;
  isLoading: boolean;
  showImagePrompt: boolean;
  setShowImagePrompt: (value: boolean) => void;
  onSend: () => void;
  onImageGenerate: () => void;
  showAttachMenu: boolean;
  setShowAttachMenu: (value: boolean) => void;
  attachMenuRef: React.RefObject<HTMLDivElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  isRecording: boolean;
  recordingTime: number;
  onStartRecording: () => void;
  onStopRecording: () => void;
}

export function ChatInputBar({
  input,
  setInput,
  isLoading,
  showImagePrompt,
  setShowImagePrompt,
  onSend,
  onImageGenerate,
  showAttachMenu,
  setShowAttachMenu,
  attachMenuRef,
  fileInputRef,
  onFileChange,
  isRecording,
  recordingTime,
  onStartRecording,
  onStopRecording,
}: ChatInputBarProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (showImagePrompt) {
        onImageGenerate();
      } else {
        onSend();
      }
    }
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 p-4 pointer-events-none z-10">
      <div className="max-w-3xl mx-auto pointer-events-auto">
        {showImagePrompt && (
          <div className="mb-2 p-2 bg-[var(--background-secondary)] rounded-lg flex items-center gap-2 shadow-lg border border-[var(--border)]">
            <ImageIcon className="w-4 h-4 text-[var(--accent)]" />
            <span className="text-sm text-[var(--foreground-secondary)]">
              Describe the image you want to generate
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowImagePrompt(false)}
              className="ml-auto"
            >
              Cancel
            </Button>
          </div>
        )}

        {/* Input Container */}
        <div className="bg-[#202225] rounded-2xl shadow-2xl border border-[#D8D6D0]/30 p-2 relative overflow-hidden group">
          {/* Subtle inner glow */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

          {/* Quick Media Bar */}
          <div className="flex items-center gap-1 px-2 pt-1 pb-1 mb-1 border-b border-[var(--border)]/50">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 rounded-full text-zinc-400 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]"
              onClick={() => fileInputRef.current?.click()}
              title="Upload File"
            >
              <Upload className="w-3.5 h-3.5" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className={`h-7 w-7 p-0 rounded-full transition-all duration-200 ${
                isRecording
                  ? 'bg-red-500 text-white hover:bg-red-600 animate-pulse scale-110'
                  : 'text-zinc-600 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]'
              }`}
              onMouseDown={onStartRecording}
              onMouseUp={onStopRecording}
              onMouseLeave={onStopRecording}
              onTouchStart={(e) => {
                e.preventDefault();
                onStartRecording();
              }}
              onTouchEnd={(e) => {
                e.preventDefault();
                onStopRecording();
              }}
              title="Hold to Record"
            >
              <Mic className={`w-3.5 h-3.5 ${isRecording ? 'animate-bounce' : ''}`} />
            </Button>

            {/* Recording Overlay */}
            <ChatRecordingOverlay isRecording={isRecording} recordingTime={recordingTime} />

            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 rounded-full text-zinc-400 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]"
              onClick={() => setShowImagePrompt(!showImagePrompt)}
              title="Generate/Analyze Image"
            >
              <Camera className="w-3.5 h-3.5" />
            </Button>
          </div>

          <div className="flex items-end gap-2">
            {/* Attachment Menu */}
            <div className="relative" ref={attachMenuRef}>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowAttachMenu(!showAttachMenu)}
                className={`rounded-xl ${showAttachMenu ? 'text-[var(--accent)] bg-[var(--accent)]/10' : ''}`}
                aria-label="Attach file"
              >
                <Plus className="w-5 h-5" />
              </Button>
              {showAttachMenu && (
                <div className="absolute bottom-full left-0 mb-2 bg-[var(--background-secondary)] rounded-xl border border-[var(--border)] shadow-lg overflow-hidden min-w-[160px] animate-in fade-in slide-in-from-bottom-2 duration-200">
                  <button
                    onClick={() => {
                      fileInputRef.current?.click();
                      setShowAttachMenu(false);
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--background-elevated)] transition-colors text-sm"
                  >
                    <Upload className="w-4 h-4" />
                    Upload file
                  </button>
                  <button
                    onClick={() => {
                      setShowImagePrompt(!showImagePrompt);
                      setShowAttachMenu(false);
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[var(--background-elevated)] transition-colors text-sm"
                  >
                    <ImageIcon className="w-4 h-4" />
                    Generate image
                  </button>
                </div>
              )}
            </div>

            <input
              type="file"
              ref={fileInputRef}
              onChange={onFileChange}
              className="hidden"
              aria-label="Upload file"
            />

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={showImagePrompt ? 'Describe your image...' : 'Type your message...'}
              disabled={isLoading}
              rows={1}
              className="flex-1 border-0 bg-transparent focus:ring-0 focus:outline-none focus-visible:ring-0 focus-visible:outline-none focus-visible:ring-offset-0 resize-none min-h-[40px] max-h-[120px] py-2 px-3 text-sm text-[#D8D6D0] placeholder:text-zinc-500 font-medium outline-none ring-0"
              style={{
                height: 'auto',
                overflowY: input.split('\n').length > 3 ? 'auto' : 'hidden',
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height =
                  Math.min(target.scrollHeight, UI.MAX_TEXTAREA_HEIGHT) + 'px';
              }}
            />

            <Button
              onClick={showImagePrompt ? onImageGenerate : onSend}
              disabled={!input.trim() || isLoading}
              size="icon"
              className="rounded-xl flex-shrink-0"
              aria-label={
                isLoading
                  ? 'Sending...'
                  : showImagePrompt
                    ? 'Generate image'
                    : 'Send message'
              }
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
