'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { MonitoringWidget } from '@/components/MonitoringWidget';
import { FeedbackWidget } from '@/components/FeedbackWidget';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useChat } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';
import { useTeamStatus } from '@/hooks/useTeamStatus';
import { useClickOutside } from '@/hooks/useClickOutside';
import { TIMEOUTS, FILE_LIMITS, UI } from '@/constants';
import {
  Send,
  ImageIcon,
  Plus,
  LogOut,
  Loader2,
  Clock,
  User,
  Menu,
  X,
  Shield,
  Bell,
  ChevronDown,
  Upload,
  Settings,
  Camera,
  Mic,
} from 'lucide-react';

import { Sidebar } from '@/components/layout/Sidebar';
import { SearchDocsModal } from '@/components/search/SearchDocsModal';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';

export default function ChatPage() {
  const router = useRouter();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [userName, setUserName] = useState<string>('');
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [isSearchDocsOpen, setIsSearchDocsOpen] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachMenuRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
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
    loadConversation: loadChatConversation, // Renamed to avoid conflict with useConversations' loadConversation
    handleFileUpload,
  } = useChat();

  const {
    conversations,
    isLoading: isConversationsLoading,
    currentConversationId,
    setCurrentConversationId,
    loadConversationList,
    deleteConversation,
    clearHistory,
  } = useConversations();

  const {
    isClockIn,
    isLoading: isClockLoading,
    error: clockError,
    loadClockStatus,
    toggleClock,
  } = useTeamStatus();

  // WebSocket Integration
  const { isConnected: isWsConnected } = useWebSocket({
    onMessage: () => {
      // Handle future real-time messages
    },
    onConnect: () => {},
    onDisconnect: () => {},
  });

  // Load User Profile
  const loadUserProfile = useCallback(async () => {
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile) {
        setUserName(storedProfile.name || storedProfile.email.split('@')[0]);
        return;
      }
      const profile = await api.getProfile();
      setUserName(profile.name || profile.email.split('@')[0]);
    } catch (error) {
      console.error('Failed to load profile:', error);
    }
  }, []);

  // Initial Data Load
  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push('/login');
      return;
    }

    const loadInitialData = async () => {
      setIsInitialLoading(true);
      await Promise.all([loadConversationList(), loadClockStatus(), loadUserProfile()]);
      setIsInitialLoading(false);
    };
    loadInitialData();
  }, [router, loadConversationList, loadClockStatus, loadUserProfile]);

  // Avatar Load
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedAvatar = localStorage.getItem('user_avatar');
      if (savedAvatar) {
        setUserAvatar(savedAvatar);
      }
    }
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Audio Recording Hook - Logic moved down below showToast definition

  // Click outside handlers for menus
  useClickOutside(attachMenuRef, () => setShowAttachMenu(false), showAttachMenu);
  useClickOutside(userMenuRef, () => setShowUserMenu(false), showUserMenu);

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

  // --- AUDIO LOGIC MOVED HERE TO FIX SCOPE ISSUES ---
  const { isRecording, startRecording, stopRecording, audioBlob, recordingTime, audioMimeType } =
    useAudioRecorder();

  const handleStartRecording = useCallback(async () => {
    try {
      await startRecording();
    } catch (e) {
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
          const originalPlaceholder = input;
          setInput('Transcribing audio...');

          const text = await api.transcribeAudio(audioBlob, audioMimeType);

          if (text) {
            setInput((prev) => {
              if (prev === 'Transcribing audio...') return text;
              return prev.replace('Transcribing audio...', '') + text;
            });
          } else {
            setInput(originalPlaceholder);
            showToast('Could not transcribe audio', 'error');
          }
        } catch (err) {
          console.error('Transcription error:', err);
          showToast('Transcription failed', 'error');
          setInput((prev) => prev.replace('Transcribing audio...', ''));
        }
      }
    };
    processAudio();
  }, [audioBlob, audioMimeType, setInput, showToast]);
  // ------------------------------------------------

  const openSearchDocs = useCallback(() => {
    setIsSearchDocsOpen(true);
  }, []);

  const handleAvatarUpload = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      // SECURITY: Validate MIME type
      if (!file.type.startsWith('image/')) {
        showToast('Please select an image file', 'error');
        event.target.value = '';
        return;
      }

      // SECURITY: Validate file size
      if (file.size > FILE_LIMITS.MAX_FILE_SIZE) {
        showToast(`Image must be less than ${FILE_LIMITS.MAX_FILE_SIZE_MB}MB`, 'error');
        event.target.value = '';
        return;
      }

      // SECURITY: Validate actual file content (magic bytes) to prevent malicious file uploads
      const arrayBuffer = await file.arrayBuffer();
      const uint8Array = new Uint8Array(arrayBuffer);

      // Check magic bytes for common image formats
      const isValidImage =
        // JPEG: FF D8 FF
        (uint8Array[0] === 0xff && uint8Array[1] === 0xd8 && uint8Array[2] === 0xff) ||
        // PNG: 89 50 4E 47
        (uint8Array[0] === 0x89 &&
          uint8Array[1] === 0x50 &&
          uint8Array[2] === 0x4e &&
          uint8Array[3] === 0x47) ||
        // GIF: 47 49 46 38
        (uint8Array[0] === 0x47 &&
          uint8Array[1] === 0x49 &&
          uint8Array[2] === 0x46 &&
          uint8Array[3] === 0x38) ||
        // WebP: RIFF...WEBP (check first 4 bytes are RIFF and bytes 8-11 are WEBP)
        (uint8Array[0] === 0x52 &&
          uint8Array[1] === 0x49 &&
          uint8Array[2] === 0x46 &&
          uint8Array[3] === 0x46 &&
          uint8Array.length > 11 &&
          String.fromCharCode(uint8Array[8], uint8Array[9], uint8Array[10], uint8Array[11]) ===
            'WEBP');

      if (!isValidImage) {
        showToast(
          'Invalid image file. Please upload a valid JPEG, PNG, GIF, or WebP image.',
          'error'
        );
        event.target.value = '';
        return;
      }

      // SECURITY: Validate image dimensions to prevent extremely large images
      const reader = new FileReader();
      reader.onloadend = () => {
        const img = document.createElement('img');
        img.onload = () => {
          // Validate dimensions
          if (
            img.width > FILE_LIMITS.MAX_IMAGE_DIMENSION ||
            img.height > FILE_LIMITS.MAX_IMAGE_DIMENSION
          ) {
            showToast(
              `Image dimensions must be less than ${FILE_LIMITS.MAX_IMAGE_DIMENSION}x${FILE_LIMITS.MAX_IMAGE_DIMENSION}px`,
              'error'
            );
            event.target.value = '';
            return;
          }

          // All validations passed - set avatar
          const base64String = reader.result as string;
          setUserAvatar(base64String);
          localStorage.setItem('user_avatar', base64String);
          showToast('Avatar updated successfully', 'success');
        };
        img.onerror = () => {
          showToast('Failed to load image. Please try another file.', 'error');
          event.target.value = '';
        };
        img.src = reader.result as string;
      };
      reader.readAsDataURL(file);
      event.target.value = '';
    },
    [showToast]
  );

  const handleNewChat = useCallback(() => {
    clearMessages();
    setCurrentConversationId(null);
  }, [clearMessages, setCurrentConversationId]);

  const handleConversationClick = useCallback(
    async (id: number) => {
      setCurrentConversationId(id);
      await loadChatConversation(id);
      if (window.innerWidth < 768) {
        setIsSidebarOpen(false);
      }
    },
    [setCurrentConversationId, loadChatConversation, setIsSidebarOpen]
  );

  const handleDeleteConversationWrapper = useCallback(
    async (id: number) => {
      if (!window.confirm('Delete this conversation?')) return;
      await deleteConversation(id);
      if (currentConversationId === id) {
        handleNewChat();
      }
    },
    [deleteConversation, currentConversationId, handleNewChat]
  );

  const handleClearHistoryWrapper = async () => {
    if (!window.confirm('Clear all conversation history? This cannot be undone.')) return;
    await clearHistory();
    handleNewChat();
  };

  const handleLogout = async () => {
    if (!window.confirm('Are you sure you want to logout?')) return;
    try {
      await api.logout();
    } finally {
      router.push('/login');
    }
  };

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
    <div className="flex h-screen bg-[var(--background)] relative isolate">
      {/* Background Image (Low Opacity) */}
      <div className="fixed inset-0 z-[-1] opacity-[0.08] pointer-events-none">
        <Image
          src="/images/monas-bg.jpg"
          alt="Background"
          fill
          className="object-cover object-center"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[var(--background)]/80 via-transparent to-[var(--background)]" />
      </div>
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-[100] px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 animate-in slide-in-from-top-2 duration-300 ${
            toast.type === 'success'
              ? 'bg-[var(--success)] text-white'
              : 'bg-[var(--error)] text-white'
          }`}
        >
          <span className="text-sm">{toast.message}</span>
          <button
            onClick={() => setToast(null)}
            className="ml-2 hover:opacity-70"
            aria-label="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onNewChat={handleNewChat}
        isLoading={isInitialLoading}
        isConversationsLoading={isConversationsLoading}
        conversations={conversations}
        currentConversationId={currentConversationId}
        onConversationClick={handleConversationClick}
        onDeleteConversation={handleDeleteConversationWrapper}
        clockError={clockError}
        onClearHistory={handleClearHistoryWrapper}
      />

      <SearchDocsModal
        open={isSearchDocsOpen}
        onClose={() => setIsSearchDocsOpen(false)}
        onInsert={(text) => setInput((prev) => (prev ? `${prev}\n${text}` : text))}
        initialQuery={input}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <header className="h-14 border-b border-[var(--border)] bg-[var(--background)] flex-shrink-0">
          <div className="h-full max-w-5xl mx-auto px-4 md:px-6 flex items-center justify-between">
            {/* Left: Menu + Clock In */}
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                aria-label={isSidebarOpen ? 'Close sidebar' : 'Open sidebar'}
                className="flex-shrink-0"
              >
                <Menu className="w-5 h-5" />
              </Button>
              <Button
                onClick={toggleClock}
                variant={isClockIn ? 'default' : 'outline'}
                size="sm"
                disabled={isClockLoading}
                className={`gap-2 ${isClockIn ? 'bg-[var(--success)] hover:bg-[var(--success)]/90' : ''}`}
              >
                {isClockLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Clock className="w-4 h-4" />
                )}
                <span className="hidden sm:inline">{isClockIn ? 'Clock Out' : 'Clock In'}</span>
                {isClockIn && <span className="w-2 h-2 rounded-full bg-white animate-pulse" />}
              </Button>
            </div>

            {/* Center: Logo */}
            <div
              className={`absolute left-1/2 -translate-x-1/2 transition-all duration-500 ease-in-out ${
                messages.length > 0
                  ? 'opacity-100 translate-y-0'
                  : 'opacity-0 -translate-y-4 pointer-events-none'
              }`}
            >
              <Image
                src="/images/logo_zan.png"
                alt="Zantara"
                width={48}
                height={48}
                className="drop-shadow-[0_0_12px_rgba(255,255,255,0.6)]"
              />
            </div>

            {/* Right: Notifications + Avatar */}
            <div className="flex items-center gap-2">
              {/* WS Connection indicator */}
              {isWsConnected && (
                <span
                  className="w-2 h-2 rounded-full bg-green-500 hidden sm:block"
                  title="Real-time connected"
                />
              )}

              {/* Notifications */}
              <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
                <Bell className="w-5 h-5" />
                {/* Notification badge - uncomment when notifications exist */}
                {/* <span className="absolute -top-1 -right-1 w-4 h-4 bg-[var(--error)] text-white text-xs rounded-full flex items-center justify-center">3</span> */}
              </Button>

              {/* User Avatar with Dropdown Menu */}
              <input
                type="file"
                ref={avatarInputRef}
                onChange={handleAvatarUpload}
                accept="image/*"
                className="hidden"
                aria-label="Upload avatar image"
              />
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-[var(--background-elevated)] transition-colors"
                  aria-label="User menu"
                >
                  <div className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center text-white font-medium overflow-hidden relative">
                    {userAvatar ? (
                      <Image
                        src={userAvatar}
                        alt="User avatar"
                        fill
                        className="object-cover"
                        sizes="32px"
                      />
                    ) : userName ? (
                      userName.charAt(0).toUpperCase()
                    ) : (
                      <User className="w-4 h-4" />
                    )}
                  </div>
                  <ChevronDown
                    className={`w-4 h-4 text-[var(--foreground-muted)] hidden sm:block transition-transform ${showUserMenu ? 'rotate-180' : ''}`}
                  />
                </button>

                {/* User Dropdown Menu */}
                {showUserMenu && (
                  <div className="absolute right-0 top-full mt-2 w-56 bg-[var(--background-secondary)] rounded-xl border border-[var(--border)] shadow-lg overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200 z-50">
                    {/* User Info */}
                    <div className="px-4 py-3 border-b border-[var(--border)]">
                      <p className="text-sm font-medium text-[var(--foreground)]">
                        {userName || 'User'}
                      </p>
                      <p className="text-xs text-[var(--foreground-muted)]">Online</p>
                    </div>

                    {/* Menu Items */}
                    <div className="py-1">
                      <button
                        onClick={() => {
                          avatarInputRef.current?.click();
                          setShowUserMenu(false);
                        }}
                        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--background-elevated)] transition-colors text-sm text-[var(--foreground)]"
                      >
                        <Camera className="w-4 h-4" />
                        Change Avatar
                      </button>
                      <button
                        onClick={() => {
                          showToast('Settings coming soon!', 'success');
                          setShowUserMenu(false);
                        }}
                        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--background-elevated)] transition-colors text-sm text-[var(--foreground)]"
                      >
                        <Settings className="w-4 h-4" />
                        Settings
                      </button>
                      {api.isAdmin() && (
                        <button
                          onClick={() => {
                            router.push('/admin');
                            setShowUserMenu(false);
                          }}
                          className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--background-elevated)] transition-colors text-sm text-[var(--foreground)]"
                        >
                          <Shield className="w-4 h-4" />
                          Admin Dashboard
                        </button>
                      )}
                    </div>

                    {/* Logout */}
                    <div className="border-t border-[var(--border)] py-1">
                      <button
                        onClick={() => {
                          setShowUserMenu(false);
                          handleLogout();
                        }}
                        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--error)]/10 transition-colors text-sm text-[var(--error)]"
                      >
                        <LogOut className="w-4 h-4" />
                        Logout
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto pb-48">
          {messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-4 min-h-0 relative z-10">
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
                className="relative mb-8"
              >
                {/* Mystical Glow */}
                <div className="absolute inset-0 bg-white/20 blur-[50px] rounded-full animate-pulse-slow" />
                <Image
                  src="/images/logo_zan.png"
                  alt="Zantara Logo"
                  width={120}
                  height={120}
                  priority
                  className="relative z-10 drop-shadow-[0_0_25px_rgba(255,255,255,0.3)] opacity-90"
                />
              </motion.div>

              <div className="space-y-4 text-center mb-12">
                <h1 className="text-2xl font-light tracking-[0.2em] text-white/90 uppercase">
                  Zantara
                </h1>
                <div className="flex items-center justify-center gap-4">
                  <div className="h-[1px] w-12 bg-gradient-to-r from-transparent to-white/30" />
                  <p className="text-xs text-[var(--foreground-muted)] tracking-[0.4em] uppercase font-medium">
                    Garda Depan Leluhur
                  </p>
                  <div className="h-[1px] w-12 bg-gradient-to-l from-transparent to-white/30" />
                </div>
              </div>

              {/* Quick Actions in Welcome */}
              <div className="flex flex-wrap justify-center gap-3 mb-6">
                <Button
                  variant="outline"
                  size="lg"
                  className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all"
                  onClick={() => setInput('What can you help me with?')}
                >
                  <span className="text-lg">💡</span>
                  <span>What can you do?</span>
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all"
                  onClick={() => setInput('Summarize my tasks for today')}
                >
                  <span className="text-lg">📋</span>
                  <span>My Tasks</span>
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  className="rounded-xl gap-2 hover:bg-[var(--accent)]/10 hover:border-[var(--accent)] transition-all"
                  onClick={openSearchDocs}
                >
                  <span className="text-lg">🔍</span>
                  <span>Search docs</span>
                </Button>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
              {messages.map((message) => (
                <MessageBubble
                  key={message.id || message.timestamp.getTime()}
                  message={message}
                  userAvatar={userAvatar}
                />
              ))}

              {/* Show loading dots when waiting for response */}

              {/* Thinking Indicator - Shows when backend is processing but before stream starts */}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Floating Input Bar */}
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
            <div className="bg-[#f5f5f5] rounded-2xl shadow-2xl border border-white/20 p-2 relative overflow-hidden group">
              {/* Subtle inner glow */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

              {/* Quick Media Bar */}
              <div className="flex items-center gap-1 px-2 pt-1 pb-1 mb-1 border-b border-[var(--border)]/50">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 rounded-full text-zinc-600 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]"
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
                  onMouseDown={handleStartRecording}
                  onMouseUp={handleStopRecording}
                  onMouseLeave={handleStopRecording} // Stop if user drags out
                  onTouchStart={(e) => {
                    e.preventDefault();
                    handleStartRecording();
                  }}
                  onTouchEnd={(e) => {
                    e.preventDefault();
                    handleStopRecording();
                  }}
                  title="Hold to Record"
                >
                  <Mic className={`w-3.5 h-3.5 ${isRecording ? 'animate-bounce' : ''}`} />
                </Button>

                {/* Visualizer / Timer Overlay */}
                {isRecording && (
                  <div className="absolute left-1/2 -translate-x-1/2 top-[-40px] bg-black/80 text-white px-3 py-1 rounded-full text-xs font-mono flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    {formatTime(recordingTime)}
                    <span className="ml-2 opacity-50 text-[10px]">Release to send</span>
                  </div>
                )}

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 rounded-full text-zinc-600 hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]"
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
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const result = await handleFileUpload(file);
                      if (result && result.success) {
                        const attachmentText = `\n[FILEUPLOAD] ${result.filename} (${result.url})`;
                        setInput((prev) => prev + attachmentText);
                        showToast(`Uploaded ${result.filename}`, 'success');
                      } else {
                        showToast('Upload failed', 'error');
                      }
                    }
                    e.target.value = '';
                  }}
                  className="hidden"
                  aria-label="Upload file"
                />
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={showImagePrompt ? 'Describe your image...' : 'Type your message...'}
                  disabled={isChatLoading}
                  rows={1}
                  className="flex-1 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 resize-none min-h-[40px] max-h-[120px] py-2 px-3 text-sm text-black placeholder:text-gray-500 font-medium"
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
                  onClick={showImagePrompt ? handleImageGenerate : handleSend}
                  disabled={!input.trim() || isChatLoading}
                  size="icon"
                  className="rounded-xl flex-shrink-0"
                  aria-label={
                    isChatLoading
                      ? 'Sending...'
                      : showImagePrompt
                        ? 'Generate image'
                        : 'Send message'
                  }
                >
                  {isChatLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </Button>
              </div>
            </div>

            {/* Quick Actions (hide on empty state to avoid duplicate with welcome) */}
            {messages.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2 mt-3">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={() => setInput('Summarize my tasks for today')}
                >
                  📋 My Tasks
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={() => setInput('What can you help me with?')}
                >
                  💡 What can you do?
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full text-xs hidden sm:inline-flex"
                  onClick={openSearchDocs}
                >
                  🔍 Search docs
                </Button>
              </div>
            )}
            {/* Quick Actions (hide on empty state to avoid duplicate with welcome) */}
            {messages.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2 mt-3">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={() => setInput('Summarize my tasks for today')}
                >
                  📋 My Tasks
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={() => setInput('What can you help me with?')}
                >
                  💡 What can you do?
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full text-xs hidden sm:inline-flex"
                  onClick={openSearchDocs}
                >
                  🔍 Search docs
                </Button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Monitoring Widget (dev only) */}
      <MonitoringWidget />

      {/* Feedback Widget */}
      <FeedbackWidget
        sessionId={currentSessionId || null}
        turnCount={Math.floor(messages.length / 2)}
      />
    </div>
  );
}
