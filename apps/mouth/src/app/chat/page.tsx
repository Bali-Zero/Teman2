'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { X } from 'lucide-react';
import { api } from '@/lib/api';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useChat } from '@/hooks/useChat';
import { useConversations } from '@/hooks/useConversations';
import { useTeamStatus } from '@/hooks/useTeamStatus';
import { useClickOutside } from '@/hooks/useClickOutside';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';
import { TIMEOUTS, FILE_LIMITS } from '@/constants';

import { Sidebar } from '@/components/layout/Sidebar';
import { SearchDocsModal } from '@/components/search/SearchDocsModal';
import { MonitoringWidget } from '@/components/dashboard/MonitoringWidget';
import { FeedbackWidget } from '@/components/chat/FeedbackWidget';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatInputBar } from '@/components/chat/ChatInputBar';
import { ChatMessageList } from '@/components/chat/ChatMessageList';

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
  const [thinkingElapsedTime, setThinkingElapsedTime] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isMountedRef = useRef(true);

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
    clearHistory,
  } = useConversations();

  const {
    isClockIn,
    isLoading: isClockLoading,
    error: clockError,
    loadClockStatus,
    toggleClock,
  } = useTeamStatus();

  const { isConnected: isWsConnected } = useWebSocket({
    onMessage: () => {},
    onConnect: () => {},
    onDisconnect: () => {},
  });

  const { isRecording, startRecording, stopRecording, audioBlob, recordingTime, audioMimeType } =
    useAudioRecorder();

  // Load User Profile
  const loadUserProfile = useCallback(async () => {
    const isMounted = isMountedRef.current;
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile) {
        if (isMounted && isMountedRef.current) {
          setUserName(storedProfile.name || storedProfile.email.split('@')[0]);
        }
        return;
      }
      const profile = await api.getProfile();
      if (isMounted && isMountedRef.current) {
        setUserName(profile.name || profile.email.split('@')[0]);
      }
    } catch (error) {
      if (isMounted && isMountedRef.current) {
        console.error('Failed to load profile:', error);
      }
    }
  }, []);

  // Component mount/unmount tracking
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
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
      if (isMountedRef.current) {
        setIsInitialLoading(false);
      }
    };
    loadInitialData();
  }, [router, loadConversationList, loadClockStatus, loadUserProfile]);

  // Avatar Load
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedAvatar = localStorage.getItem('user_avatar');
      if (savedAvatar && isMountedRef.current) {
        setUserAvatar(savedAvatar);
      }
    }
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Thinking elapsed time tracker
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (isChatLoading) {
      setThinkingElapsedTime(0);
      interval = setInterval(() => {
        setThinkingElapsedTime((prev) => prev + 1);
      }, 1000);
    } else {
      setThinkingElapsedTime(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isChatLoading]);

  // Click outside handlers
  useClickOutside(attachMenuRef, () => setShowAttachMenu(false), showAttachMenu);
  useClickOutside(userMenuRef, () => setShowUserMenu(false), showUserMenu);

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        if (isMountedRef.current) setToast(null);
      }, TIMEOUTS.TOAST_AUTO_DISMISS);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
  }, []);

  // Audio recording handlers
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

  // Audio transcription
  useEffect(() => {
    const processAudio = async () => {
      if (audioBlob) {
        try {
          const currentInput = input;
          if (!isMountedRef.current) return;
          setInput('Transcribing audio...');
          const text = await api.transcribeAudio(audioBlob, audioMimeType);
          if (!isMountedRef.current) return;
          if (text) {
            setInput((prev) => (prev === 'Transcribing audio...' ? text : prev + text));
          } else {
            setInput(currentInput);
            if (isMountedRef.current) showToast('Could not transcribe audio', 'error');
          }
        } catch (err) {
          if (!isMountedRef.current) return;
          console.error('Transcription error:', err);
          showToast('Transcription failed', 'error');
          setInput((prev) => prev.replace('Transcribing audio...', ''));
        }
      }
    };
    processAudio();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioBlob, audioMimeType, showToast]);

  const openSearchDocs = useCallback(() => setIsSearchDocsOpen(true), []);

  const handleAvatarUpload = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) {
        showToast('Please select an image file', 'error');
        event.target.value = '';
        return;
      }
      if (file.size > FILE_LIMITS.MAX_FILE_SIZE) {
        showToast(`Image must be less than ${FILE_LIMITS.MAX_FILE_SIZE_MB}MB`, 'error');
        event.target.value = '';
        return;
      }
      const arrayBuffer = await file.arrayBuffer();
      if (!isMountedRef.current) return;
      const uint8Array = new Uint8Array(arrayBuffer);
      const isValidImage =
        (uint8Array[0] === 0xff && uint8Array[1] === 0xd8 && uint8Array[2] === 0xff) ||
        (uint8Array[0] === 0x89 && uint8Array[1] === 0x50 && uint8Array[2] === 0x4e && uint8Array[3] === 0x47) ||
        (uint8Array[0] === 0x47 && uint8Array[1] === 0x49 && uint8Array[2] === 0x46 && uint8Array[3] === 0x38) ||
        (uint8Array[0] === 0x52 && uint8Array[1] === 0x49 && uint8Array[2] === 0x46 && uint8Array[3] === 0x46 &&
          uint8Array.length > 11 && String.fromCharCode(uint8Array[8], uint8Array[9], uint8Array[10], uint8Array[11]) === 'WEBP');
      if (!isValidImage) {
        showToast('Invalid image file. Please upload a valid JPEG, PNG, GIF, or WebP image.', 'error');
        event.target.value = '';
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        if (!isMountedRef.current) return;
        const img = document.createElement('img');
        img.onload = () => {
          if (!isMountedRef.current) return;
          if (img.width > FILE_LIMITS.MAX_IMAGE_DIMENSION || img.height > FILE_LIMITS.MAX_IMAGE_DIMENSION) {
            showToast(`Image dimensions must be less than ${FILE_LIMITS.MAX_IMAGE_DIMENSION}x${FILE_LIMITS.MAX_IMAGE_DIMENSION}px`, 'error');
            event.target.value = '';
            return;
          }
          const base64String = reader.result as string;
          setUserAvatar(base64String);
          localStorage.setItem('user_avatar', base64String);
          showToast('Avatar updated successfully', 'success');
        };
        img.onerror = () => {
          if (!isMountedRef.current) return;
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
      if (window.innerWidth < 768) setIsSidebarOpen(false);
    },
    [setCurrentConversationId, loadChatConversation]
  );

  const handleDeleteConversationWrapper = useCallback(
    async (id: number) => {
      if (!window.confirm('Delete this conversation?')) return;
      await deleteConversation(id);
      if (currentConversationId === id) handleNewChat();
    },
    [deleteConversation, currentConversationId, handleNewChat]
  );

  const handleClearHistoryWrapper = async () => {
    if (!window.confirm('Clear all conversation history? This cannot be undone.')) return;
    await clearHistory();
    handleNewChat();
  };

  const handleFollowUpClick = useCallback(
    (question: string) => {
      setInput(question);
      setTimeout(() => handleSend(), 10);
    },
    [handleSend, setInput]
  );

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        const result = await handleFileUpload(file);
        if (!isMountedRef.current) return;
        if (result && result.success) {
          const attachmentText = `\n[FILEUPLOAD] ${result.filename} (${result.url})`;
          setInput((prev) => prev + attachmentText);
          showToast(`Uploaded ${result.filename}`, 'success');
        } else {
          showToast('Upload failed', 'error');
        }
      }
      e.target.value = '';
    },
    [handleFileUpload, setInput, showToast]
  );

  return (
    <div className="flex h-screen bg-[var(--background)] relative isolate">
      {/* Background Image */}
      <div className="fixed inset-0 z-[-1] opacity-[0.08] pointer-events-none">
        <Image src="/images/monas-bg.jpg" alt="Background" fill className="object-cover object-center" priority />
        <div className="absolute inset-0 bg-gradient-to-b from-[var(--background)]/80 via-transparent to-[var(--background)]" />
      </div>

      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-[100] px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 animate-in slide-in-from-top-2 duration-300 ${
            toast.type === 'success' ? 'bg-[var(--success)] text-white' : 'bg-[var(--error)] text-white'
          }`}
        >
          <span className="text-sm">{toast.message}</span>
          <button onClick={() => setToast(null)} className="ml-2 hover:opacity-70" aria-label="Dismiss">
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
        <ChatHeader
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
          isClockIn={isClockIn}
          isClockLoading={isClockLoading}
          onToggleClock={toggleClock}
          messagesCount={messages.length}
          isWsConnected={isWsConnected}
          userName={userName}
          userAvatar={userAvatar}
          showUserMenu={showUserMenu}
          onToggleUserMenu={() => setShowUserMenu(!showUserMenu)}
          userMenuRef={userMenuRef}
          avatarInputRef={avatarInputRef}
          onAvatarUpload={handleAvatarUpload}
          onShowToast={showToast}
        />

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto pb-48">
          <ChatMessageList
            messages={messages}
            isLoading={isChatLoading}
            thinkingElapsedTime={thinkingElapsedTime}
            userAvatar={userAvatar}
            messagesEndRef={messagesEndRef}
            onFollowUpClick={handleFollowUpClick}
            onSetInput={setInput}
            onOpenSearchDocs={openSearchDocs}
          />
        </div>

        <ChatInputBar
          input={input}
          setInput={setInput}
          isLoading={isChatLoading}
          showImagePrompt={showImagePrompt}
          setShowImagePrompt={setShowImagePrompt}
          onSend={handleSend}
          onImageGenerate={handleImageGenerate}
          showAttachMenu={showAttachMenu}
          setShowAttachMenu={setShowAttachMenu}
          attachMenuRef={attachMenuRef}
          fileInputRef={fileInputRef}
          onFileChange={handleFileChange}
          isRecording={isRecording}
          recordingTime={recordingTime}
          onStartRecording={handleStartRecording}
          onStopRecording={handleStopRecording}
        />
      </main>

      <MonitoringWidget />
      <FeedbackWidget sessionId={currentSessionId || null} turnCount={Math.floor(messages.length / 2)} />
    </div>
  );
}
