'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { useChat } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';
import { TIMEOUTS, FILE_LIMITS, UI } from '@/constants';
import {
  Send,
  ImageIcon,
  Plus,
  Loader2,
  X,
  Upload,
  Camera,
  Mic,
  History,
  MessageSquare,
  Trash2,
} from 'lucide-react';
import { SearchDocsModal } from '@/components/search/SearchDocsModal';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';

export default function ZantaraChatPage() {
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [isSearchDocsOpen, setIsSearchDocsOpen] = useState(false);
  const [showConversations, setShowConversations] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachMenuRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Custom Hooks
  const {
    messages,
    input,
    setInput,
    isLoading: isChatLoading,
    currentSessionId,
    showImagePrompt,
    setShowImagePrompt,
    handleSend,
    handleImageGenerate,
    clearMessages,
    loadConversation: loadChatConversation,
    handleFileUpload,
  } = useChat();

  const {
    conversations,
    isLoading: isConversationsLoading,
    currentConversationId,
    setCurrentConversationId,
    loadConversationList,
    deleteConversation,
  } = useConversations();

  // Load conversations
  useEffect(() => {
    loadConversationList();
  }, [loadConversationList]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), TIMEOUTS.TOAST_AUTO_DISMISS);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
  }, []);

  // Audio recording
  const { isRecording, startRecording, stopRecording, audioBlob, recordingTime } =
    useAudioRecorder();

  const handleStartRecording = useCallback(async () => {
    try {
      await startRecording();
    } catch {
      showToast('Access to microphone denied', 'error');
    }
  }, [startRecording, showToast]);

  const handleStopRecording = useCallback(() => {
    stopRecording();
  }, [stopRecording]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    const processAudio = async () => {
      if (audioBlob) {
        try {
          setInput('Transcribing audio...');
          const text = await api.transcribeAudio(audioBlob);
          if (text) {
            setInput(text);
          } else {
            setInput('');
            showToast('Could not transcribe audio', 'error');
          }
        } catch {
          showToast('Transcription failed', 'error');
          setInput('');
        }
      }
    };
    processAudio();
  }, [audioBlob, setInput, showToast]);

  const handleNewChat = useCallback(() => {
    clearMessages();
    setCurrentConversationId(null);
    setShowConversations(false);
  }, [clearMessages, setCurrentConversationId]);

  const handleConversationClick = useCallback(
    async (id: number) => {
      setCurrentConversationId(id);
      await loadChatConversation(id);
      setShowConversations(false);
    },
    [setCurrentConversationId, loadChatConversation]
  );

  const handleDeleteConversation = useCallback(
    async (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!window.confirm('Delete this conversation?')) return;
      await deleteConversation(id);
      if (currentConversationId === id) {
        handleNewChat();
      }
    },
    [deleteConversation, currentConversationId, handleNewChat]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (showImagePrompt) {
        handleImageGenerate();
      } else {
        handleSend();
      }
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-20 right-4 z-[100] px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 ${
            toast.type === 'success'
              ? 'bg-[var(--success)] text-white'
              : 'bg-[var(--error)] text-white'
          }`}
        >
          <span className="text-sm">{toast.message}</span>
          <button onClick={() => setToast(null)} className="ml-2 hover:opacity-70">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Conversations Panel (Desktop) */}
      <div className="hidden lg:flex flex-col w-64 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
        <div className="p-3 border-b border-[var(--border)]">
          <Button
            onClick={handleNewChat}
            className="w-full justify-start gap-2"
            variant="default"
          >
            <Plus className="w-4 h-4" />
            Nuova Chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {isConversationsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--foreground-muted)]" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-8">
              <History className="w-8 h-8 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">Nessuna conversazione</p>
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`group relative p-2 rounded-lg cursor-pointer transition-all ${
                    currentConversationId === conv.id
                      ? 'bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/20'
                      : 'hover:bg-[var(--background-elevated)]/50 text-[var(--foreground)] border border-transparent'
                  }`}
                  onClick={() => handleConversationClick(conv.id)}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{conv.title}</p>
                      <p className="text-xs truncate text-[var(--foreground-muted)]">
                        {conv.preview || `${conv.message_count} messages`}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    className="absolute right-2 top-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-[var(--error)]/10 text-[var(--foreground-muted)] hover:text-[var(--error)]"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden">
        {/* Mobile Conversations Toggle */}
        <div className="lg:hidden flex items-center gap-2 p-3 border-b border-[var(--border)]">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowConversations(!showConversations)}
          >
            <History className="w-4 h-4 mr-2" />
            Cronologia
          </Button>
          <Button variant="default" size="sm" onClick={handleNewChat}>
            <Plus className="w-4 h-4 mr-2" />
            Nuova
          </Button>
        </div>

        {/* Mobile Conversations Dropdown */}
        {showConversations && (
          <div className="lg:hidden border-b border-[var(--border)] max-h-48 overflow-y-auto p-2">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`p-2 rounded cursor-pointer ${
                  currentConversationId === conv.id
                    ? 'bg-[var(--accent)]/10'
                    : 'hover:bg-[var(--background-elevated)]/50'
                }`}
                onClick={() => handleConversationClick(conv.id)}
              >
                <p className="text-sm truncate">{conv.title}</p>
              </div>
            ))}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full p-4">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.8 }}
                className="relative mb-6"
              >
                <div className="absolute inset-0 bg-white/20 blur-[50px] rounded-full" />
                <Image
                  src="/images/logo_zan.png"
                  alt="Zantara"
                  width={100}
                  height={100}
                  priority
                  className="relative z-10 drop-shadow-[0_0_25px_rgba(255,255,255,0.3)]"
                />
              </motion.div>
              <h1 className="text-xl font-light tracking-[0.2em] text-white/90 uppercase mb-2">
                Zantara AI
              </h1>
              <p className="text-sm text-[var(--foreground-muted)] mb-6">
                Come posso aiutarti oggi?
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                  onClick={() => setInput('Quali sono i requisiti per il KITAS E33G?')}
                >
                  KITAS info
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                  onClick={() => setInput('Come si apre una PT PMA?')}
                >
                  PT PMA
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                  onClick={() => setIsSearchDocsOpen(true)}
                >
                  Cerca docs
                </Button>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
              {messages.map((message) => (
                <MessageBubble
                  key={message.id || message.timestamp.getTime()}
                  message={message}
                  userAvatar={null}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-[var(--border)]">
          {showImagePrompt && (
            <div className="mb-2 p-2 bg-[var(--background)] rounded-lg flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-[var(--accent)]" />
              <span className="text-sm text-[var(--foreground-secondary)]">
                Descrivi l&apos;immagine da generare
              </span>
              <Button variant="ghost" size="sm" onClick={() => setShowImagePrompt(false)} className="ml-auto">
                Annulla
              </Button>
            </div>
          )}

          <div className="bg-[#f5f5f5] rounded-xl p-2">
            {/* Quick actions */}
            <div className="flex items-center gap-1 px-2 pb-2 border-b border-[var(--border)]/30">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 rounded-full text-zinc-600 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 w-7 p-0 rounded-full ${
                  isRecording
                    ? 'bg-red-500 text-white animate-pulse'
                    : 'text-zinc-600 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]'
                }`}
                onMouseDown={handleStartRecording}
                onMouseUp={handleStopRecording}
                onMouseLeave={handleStopRecording}
              >
                <Mic className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 rounded-full text-zinc-600 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]"
                onClick={() => setShowImagePrompt(!showImagePrompt)}
              >
                <Camera className="w-3.5 h-3.5" />
              </Button>
              {isRecording && (
                <span className="text-xs text-red-500 font-mono ml-2">
                  {formatTime(recordingTime)}
                </span>
              )}
            </div>

            <div className="flex items-end gap-2 pt-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const result = await handleFileUpload(file);
                    if (result?.success) {
                      setInput((prev) => prev + `\n[FILE] ${result.filename}`);
                      showToast(`Uploaded ${result.filename}`, 'success');
                    }
                  }
                  e.target.value = '';
                }}
                className="hidden"
              />
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={showImagePrompt ? 'Descrivi l\'immagine...' : 'Scrivi messaggio...'}
                disabled={isChatLoading}
                rows={1}
                className="flex-1 border-0 bg-transparent focus-visible:ring-0 resize-none min-h-[40px] max-h-[120px] py-2 px-3 text-sm text-black placeholder:text-gray-500"
                style={{ height: 'auto' }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = Math.min(target.scrollHeight, 120) + 'px';
                }}
              />
              <Button
                onClick={showImagePrompt ? handleImageGenerate : handleSend}
                disabled={!input.trim() || isChatLoading}
                size="icon"
                className="rounded-xl flex-shrink-0"
              >
                {isChatLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <SearchDocsModal
        open={isSearchDocsOpen}
        onClose={() => setIsSearchDocsOpen(false)}
        onInsert={(text) => setInput((prev) => (prev ? `${prev}\n${text}` : text))}
        initialQuery={input}
      />
    </div>
  );
}
