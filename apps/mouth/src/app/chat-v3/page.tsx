'use client';

import {
  useState,
  useEffect,
  useOptimistic,
  useTransition,
  useRef,
  useCallback,
  startTransition,
} from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import {
  Send,
  ImageIcon,
  Menu,
  Bell,
  ChevronDown,
  Mic,
  Camera,
  Clock,
  Paperclip,
  Copy,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  X,
  MessageSquare,
  Settings,
  HelpCircle,
  Home,
  User,
  History,
  Star,
  Plus,
  Trash2,
  Loader2,
  Search,
} from 'lucide-react';

// API & Hooks
import { api } from '@/lib/api';
import { useConversations } from '@/hooks/useConversations';
import { useTeamStatus } from '@/hooks/useTeamStatus';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';
import { ThinkingIndicator } from '@/components/chat/ThinkingIndicator';
import { SearchDocsModal } from '@/components/search/SearchDocsModal';

// Server Actions
import {
  sendMessageStream,
  saveConversation,
  type ChatMessage,
  type Source,
  type StreamEvent,
} from '../chat/actions';

// Types
interface OptimisticMessage extends ChatMessage {
  isPending?: boolean;
  isStreaming?: boolean;
}

// Utilities
const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
const generateSessionId = () => `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

/**
 * Chat V3 - Hybrid UI with full backend integration
 */
export default function ChatV3Page() {
  const router = useRouter();
  const isMountedRef = useRef(true);

  // Core state
  const [messages, setMessages] = useState<OptimisticMessage[]>([]);
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [currentStatus, setCurrentStatus] = useState<string>('');
  const [input, setInput] = useState('');
  const [thinkingElapsedTime, setThinkingElapsedTime] = useState(0);

  // UI state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userName, setUserName] = useState<string>('');
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isSearchDocsOpen, setIsSearchDocsOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Transitions
  const [isPending, startMessageTransition] = useTransition();

  // Custom Hooks
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
    toggleClock,
    loadClockStatus,
  } = useTeamStatus();

  const { isRecording, startRecording, stopRecording, audioBlob, recordingTime, audioMimeType } =
    useAudioRecorder();

  // useOptimistic for instant message display
  const [optimisticMessages, addOptimisticMessage] = useOptimistic<
    OptimisticMessage[],
    OptimisticMessage
  >(messages, (state, newMessage) => [...state, newMessage]);

  // ============================================
  // Auth & Initial Data Load
  // ============================================
  const loadUserProfile = useCallback(async () => {
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile && isMountedRef.current) {
        setUserName(storedProfile.name || storedProfile.email.split('@')[0]);
        return;
      }
      const profile = await api.getProfile();
      if (isMountedRef.current) {
        setUserName(profile.name || profile.email.split('@')[0]);
      }
    } catch (error) {
      if (isMountedRef.current) {
        console.error('Failed to load profile:', error);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

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

  // Avatar Load from localStorage
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
  }, [messages, optimisticMessages]);

  // Thinking elapsed time tracker
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (isPending) {
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
  }, [isPending]);

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => {
        if (isMountedRef.current) setToast(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // ============================================
  // Helpers
  // ============================================
  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
  }, []);

  // Handle avatar upload
  const handleAvatarChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        showToast('Please select an image file', 'error');
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        showToast('Image must be less than 5MB', 'error');
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result as string;
        setUserAvatar(base64String);
        localStorage.setItem('user_avatar', base64String);
        showToast('Avatar updated', 'success');
      };
      reader.readAsDataURL(file);
    }
  }, [showToast]);

  // User avatar component
  const UserAvatarDisplay = ({ size = 'sm' }: { size?: 'sm' | 'md' }) => {
    const sizeClasses = size === 'sm' ? 'w-8 h-8' : 'w-9 h-9';

    if (userAvatar) {
      return (
        <Image
          src={userAvatar}
          alt="User"
          width={size === 'sm' ? 32 : 36}
          height={size === 'sm' ? 32 : 36}
          className={`${sizeClasses} rounded-full object-cover`}
        />
      );
    }
    return (
      <div className={`${sizeClasses} rounded-full bg-[#2a2a2a] flex items-center justify-center`}>
        <span className="text-gray-300 font-medium text-sm">
          {userName ? userName.substring(0, 2).toUpperCase() : 'U'}
        </span>
      </div>
    );
  };

  // ============================================
  // Send Message with Streaming
  // ============================================
  const handleSend = useCallback(async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput || isPending) return;

    const userProfile = api.getUserProfile();
    const userId = userProfile?.email || 'anonymous';

    setInput('');

    const userMessage: OptimisticMessage = {
      id: generateId(),
      role: 'user',
      content: trimmedInput,
      timestamp: new Date(),
      isPending: false,
    };

    const assistantMessage: OptimisticMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isPending: true,
      isStreaming: true,
    };

    startTransition(() => {
      addOptimisticMessage(userMessage);
      addOptimisticMessage(assistantMessage);
    });

    const newMessages = [...messages, userMessage, assistantMessage];
    setMessages(newMessages);

    try {
      const stream = await sendMessageStream(
        newMessages.filter(m => !m.isStreaming),
        sessionId,
        userId
      );

      const reader = stream.getReader();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const event = value as StreamEvent;

        switch (event.type) {
          case 'token':
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantMessage.id
                  ? { ...m, content: event.data as string, isPending: false }
                  : m
              )
            );
            break;

          case 'status':
            setCurrentStatus(event.data as string);
            break;

          case 'sources':
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantMessage.id
                  ? { ...m, sources: event.data as Source[] }
                  : m
              )
            );
            break;

          case 'error':
            throw new Error(event.data as string);

          case 'done':
            break;
        }
      }

      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMessage.id
            ? { ...m, isStreaming: false, isPending: false }
            : m
        )
      );

      setCurrentStatus('');

      startTransition(async () => {
        await saveConversation(
          messages.filter(m => !m.isStreaming),
          sessionId
        );
      });

    } catch (error) {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMessage.id
            ? {
                ...m,
                content: 'Sorry, there was an error processing your request. Please try again.',
                isPending: false,
                isStreaming: false,
              }
            : m
        )
      );
      setCurrentStatus('');
      showToast('Failed to send message', 'error');
    }
  }, [input, isPending, messages, sessionId, addOptimisticMessage, showToast]);

  // ============================================
  // Conversation Management
  // ============================================
  const handleNewChat = useCallback(() => {
    setMessages([]);
    setCurrentStatus('');
    setSessionId(generateSessionId());
    setCurrentConversationId(null);
    setSidebarOpen(false);
  }, [setCurrentConversationId]);

  const handleConversationClick = useCallback(
    async (id: number) => {
      setCurrentConversationId(id);
      // Load conversation messages
      try {
        const conv = await api.getConversation(id);
        if (conv && conv.messages) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          setMessages(conv.messages.map((m: any) => ({
            id: m.id || generateId(),
            role: m.role as 'user' | 'assistant',
            content: m.content || '',
            timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
            sources: m.sources,
          })));
          if (conv.session_id) {
            setSessionId(conv.session_id);
          }
        }
      } catch (error) {
        console.error('Failed to load conversation:', error);
      }
      if (window.innerWidth < 768) setSidebarOpen(false);
    },
    [setCurrentConversationId]
  );

  const handleDeleteConversation = useCallback(
    async (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!window.confirm('Delete this conversation?')) return;
      await deleteConversation(id);
      if (currentConversationId === id) handleNewChat();
    },
    [deleteConversation, currentConversationId, handleNewChat]
  );

  // ============================================
  // Audio Recording
  // ============================================
  const handleMicClick = useCallback(async () => {
    if (isRecording) {
      stopRecording();
    } else {
      try {
        await startRecording();
      } catch {
        showToast('Microphone access denied', 'error');
      }
    }
  }, [isRecording, startRecording, stopRecording, showToast]);

  // Audio transcription
  useEffect(() => {
    const processAudio = async () => {
      if (audioBlob) {
        try {
          setInput('Transcribing...');
          const text = await api.transcribeAudio(audioBlob, audioMimeType);
          if (text) {
            setInput(text);
          } else {
            setInput('');
            showToast('Could not transcribe audio', 'error');
          }
        } catch {
          setInput('');
          showToast('Transcription failed', 'error');
        }
      }
    };
    processAudio();
  }, [audioBlob, audioMimeType, showToast]);

  // ============================================
  // Keyboard shortcuts
  // ============================================
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Loading state
  if (isInitialLoading) {
    return (
      <div className="flex h-screen bg-[#202020] text-white items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#202020] text-white overflow-hidden">
      {/* Hidden file input for avatar upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleAvatarChange}
        accept="image/*"
        className="hidden"
      />

      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-[100] px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 animate-in slide-in-from-top-2 ${
            toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
          }`}
        >
          <span className="text-sm text-white">{toast.message}</span>
          <button onClick={() => setToast(null)} className="hover:opacity-70">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed left-0 top-0 h-full w-72 bg-[#1a1a1a] border-r border-white/5 z-50 transform transition-transform duration-300 ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div className="flex flex-col h-full">
          {/* Sidebar Header */}
          <div className="h-14 border-b border-white/5 flex items-center justify-between px-4">
            <div className="flex items-center gap-3">
              <Image
                src="/images/logo_zan.png"
                alt="Zantara"
                width={32}
                height={32}
                className="drop-shadow-[0_0_12px_rgba(255,255,255,0.3)]"
              />
              <span className="font-medium text-white/90">Zantara</span>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>

          {/* New Chat Button */}
          <div className="p-4">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center gap-3 px-4 py-3 bg-white/5 hover:bg-white/10 rounded-xl transition-colors text-gray-300"
            >
              <Plus className="w-5 h-5" />
              <span>New Chat</span>
            </button>
          </div>

          {/* Chat History */}
          <div className="flex-1 overflow-y-auto px-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Recent Chats</p>
            {isConversationsLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
              </div>
            ) : conversations.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">No conversations yet</p>
            ) : (
              <div className="space-y-1">
                {conversations.slice(0, 10).map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => handleConversationClick(conv.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors text-left group ${
                      currentConversationId === conv.id ? 'bg-white/10' : ''
                    }`}
                  >
                    <MessageSquare className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="text-sm text-gray-400 truncate flex-1">{conv.title || 'Untitled'}</span>
                    <button
                      onClick={(e) => handleDeleteConversation(conv.id, e)}
                      className="p-1 hover:bg-white/10 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-gray-500 hover:text-red-400" />
                    </button>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Sidebar Footer */}
          <div className="border-t border-white/5 p-4 space-y-1">
            <button
              onClick={() => setIsSearchDocsOpen(true)}
              className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors"
            >
              <Search className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-400">Search Docs</span>
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors">
              <Settings className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-400">Settings</span>
            </button>
            <button className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors">
              <HelpCircle className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-400">Help</span>
            </button>
            <button
              onClick={() => router.push('/dashboard')}
              className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 rounded-lg transition-colors text-blue-400"
            >
              <Home className="w-4 h-4" />
              <span className="text-sm">Dashboard</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Search Docs Modal */}
      <SearchDocsModal
        open={isSearchDocsOpen}
        onClose={() => setIsSearchDocsOpen(false)}
        onInsert={(text) => setInput((prev) => (prev ? `${prev}\n${text}` : text))}
        initialQuery={input}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <header className="h-14 border-b border-white/5 bg-[#202020] flex-shrink-0">
          <div className="h-full max-w-4xl mx-auto px-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              >
                <Menu className="w-5 h-5 text-gray-400" />
              </button>
              <button
                onClick={toggleClock}
                disabled={isClockLoading}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  isClockIn
                    ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                    : 'bg-gray-500/10 border border-gray-500/20 text-gray-400'
                }`}
              >
                {isClockLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span className={`w-2 h-2 rounded-full ${isClockIn ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
                    <span>{isClockIn ? 'Online' : 'Offline'}</span>
                  </>
                )}
              </button>
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 rounded-full">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-gray-400 text-sm">{messages.length} msgs</span>
              </div>
            </div>

            <div className="absolute left-1/2 -translate-x-1/2">
              <Image
                src="/images/logo_zan.png"
                alt="Zantara"
                width={44}
                height={44}
                className="drop-shadow-[0_0_20px_rgba(255,255,255,0.4)] brightness-110"
              />
            </div>

            <div className="flex items-center gap-2">
              <button className="p-2 hover:bg-white/5 rounded-lg transition-colors relative">
                <Bell className="w-5 h-5 text-gray-400" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-blue-500 rounded-full" />
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors group"
                title="Click to change avatar"
              >
                <div className="relative">
                  <UserAvatarDisplay size="sm" />
                  <div className="absolute inset-0 bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <User className="w-4 h-4 text-white" />
                  </div>
                </div>
                <span className="text-sm text-gray-400 hidden sm:block">{userName}</span>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </button>
            </div>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto pb-44">
          {optimisticMessages.length === 0 ? (
            /* Welcome Screen */
            <div className="flex-1 flex flex-col items-center justify-center p-4 min-h-[60vh]">
              <div className="relative mb-8">
                <div className="absolute inset-0 bg-white/10 blur-[60px] rounded-full animate-pulse" />
                <Image
                  src="/images/logo_zan.png"
                  alt="Zantara"
                  width={120}
                  height={120}
                  className="relative z-10 drop-shadow-[0_0_30px_rgba(255,255,255,0.4)]"
                />
              </div>

              <div className="space-y-4 text-center mb-12">
                <h1 className="text-3xl font-light tracking-[0.3em] text-white/90 uppercase">
                  Zantara
                </h1>
                <div className="flex items-center justify-center gap-4">
                  <div className="h-[1px] w-16 bg-gradient-to-r from-transparent to-white/30" />
                  <p className="text-xs text-white/60 tracking-[0.4em] uppercase font-medium">
                    Garda Depan Leluhur
                  </p>
                  <div className="h-[1px] w-16 bg-gradient-to-l from-transparent to-white/30" />
                </div>
                <p className="text-sm text-gray-500 mt-4">The Ancestral Vanguard</p>
              </div>

              <div className="flex flex-wrap justify-center gap-3">
                {['What can you do?', 'My Tasks', 'Search docs'].map((q, i) => (
                  <button
                    key={q}
                    onClick={() => {
                      if (i === 2) {
                        setIsSearchDocsOpen(true);
                      } else {
                        setInput(q);
                        setTimeout(() => handleSend(), 10);
                      }
                    }}
                    className="px-4 py-2.5 rounded-xl border border-white/10 hover:border-white/30 hover:bg-white/5 transition-all text-sm text-gray-300 flex items-center gap-2"
                  >
                    <span>{['💡', '📋', '🔍'][i]}</span> {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Chat Messages */
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
              {/* Show ThinkingIndicator when processing */}
              {isPending && (
                <ThinkingIndicator
                  isVisible={isPending}
                  currentStatus={currentStatus}
                  elapsedTime={thinkingElapsedTime}
                />
              )}

              {optimisticMessages.map((message) => (
                <div key={message.id} className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {message.role === 'assistant' && (
                    <div className="relative flex-shrink-0">
                      <Image
                        src="/images/logo_zan.png"
                        alt="Zantara"
                        width={52}
                        height={52}
                        className="relative z-10 drop-shadow-[0_0_15px_rgba(255,255,255,0.4)]"
                      />
                    </div>
                  )}

                  <div className={`max-w-[75%] ${message.role === 'user' ? 'order-1' : ''}`}>
                    {message.role === 'assistant' && !message.isStreaming && (
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 bg-blue-500/15 text-blue-400 text-xs font-medium rounded flex items-center gap-1">
                          ✨ ULTRA
                        </span>
                        <span className="px-2 py-0.5 bg-white/5 text-gray-500 text-xs rounded">
                          {thinkingElapsedTime}s
                        </span>
                        {message.sources && message.sources.length > 0 && (
                          <span className="px-2 py-0.5 bg-green-500/10 text-green-400 text-xs rounded">
                            ✓ {message.sources.length} sources
                          </span>
                        )}
                      </div>
                    )}

                    <div className={`rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-[#2a2a2a] rounded-br-md'
                        : 'bg-[#2a2a2a] rounded-bl-md border border-white/[0.06]'
                    } ${message.isPending ? 'opacity-70' : ''}`}>
                      {message.isStreaming && !message.content ? (
                        <div className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                          <span className="text-sm text-gray-400">
                            {currentStatus || 'Thinking...'}
                          </span>
                        </div>
                      ) : (
                        <div className="text-sm whitespace-pre-wrap leading-relaxed text-gray-100">
                          {message.content.split('**').map((part, i) =>
                            i % 2 === 1 ? <strong key={i} className="text-white">{part}</strong> : part
                          )}
                        </div>
                      )}
                    </div>

                    {message.role === 'assistant' && !message.isStreaming && (
                      <div className="flex items-center gap-1 mt-2 opacity-0 hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(message.content);
                            showToast('Copied to clipboard', 'success');
                          }}
                          className="p-1.5 hover:bg-white/5 rounded text-gray-500 hover:text-gray-300"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        <button className="p-1.5 hover:bg-white/5 rounded text-gray-500 hover:text-gray-300">
                          <ThumbsUp className="w-3.5 h-3.5" />
                        </button>
                        <button className="p-1.5 hover:bg-white/5 rounded text-gray-500 hover:text-gray-300">
                          <ThumbsDown className="w-3.5 h-3.5" />
                        </button>
                        <button className="p-1.5 hover:bg-white/5 rounded text-gray-500 hover:text-gray-300">
                          <RefreshCw className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}

                    <div className="text-xs text-gray-600 mt-1.5 px-1">
                      {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>

                  {message.role === 'user' && (
                    <div className="flex-shrink-0">
                      <UserAvatarDisplay size="md" />
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="fixed bottom-0 left-0 right-0 p-4 pointer-events-none z-10">
          <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-[#202020] via-[#202020]/80 to-transparent pointer-events-none" />

          <div className="max-w-3xl mx-auto pointer-events-auto relative">
            <div className="bg-[#333333] rounded-2xl border border-white/[0.1] shadow-xl shadow-black/30 overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06]">
                <div className="flex items-center gap-1">
                  <button className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all">
                    <Paperclip className="w-4 h-4" />
                  </button>
                  <button className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all">
                    <ImageIcon className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleMicClick}
                    className={`p-2 rounded-lg transition-all ${
                      isRecording ? 'text-red-400 bg-red-500/10 animate-pulse' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                    }`}
                  >
                    <Mic className="w-4 h-4" />
                  </button>
                  <button className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all">
                    <Camera className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  {isRecording && (
                    <span className="text-xs text-red-400">{recordingTime}s</span>
                  )}
                  <span className="text-xs text-gray-500">ULTRA mode</span>
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                </div>
              </div>

              <div className="flex items-end gap-3 p-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Zantara anything..."
                  rows={1}
                  disabled={isPending}
                  className="flex-1 bg-transparent border-0 focus:outline-none resize-none min-h-[44px] max-h-[120px] py-2.5 text-sm text-white placeholder:text-gray-500 disabled:opacity-50"
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isPending}
                  className={`p-2.5 rounded-xl transition-all ${
                    input.trim() && !isPending
                      ? 'bg-white text-black shadow-lg shadow-white/20'
                      : 'bg-white/10 text-gray-500'
                  }`}
                >
                  {isPending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-center gap-4 mt-3">
              <span className="text-xs text-gray-600">
                <kbd className="px-1.5 py-0.5 bg-white/5 rounded text-gray-500 font-mono text-[10px]">Enter</kbd>
                <span className="ml-1">send</span>
              </span>
              <span className="text-xs text-gray-600">
                <kbd className="px-1.5 py-0.5 bg-white/5 rounded text-gray-500 font-mono text-[10px]">Shift+Enter</kbd>
                <span className="ml-1">new line</span>
              </span>
            </div>
          </div>
        </div>
      </main>

      <div className="fixed top-4 right-4 z-50">
        <div className="px-3 py-1.5 bg-gradient-to-r from-blue-500 to-purple-500 text-white text-xs font-bold rounded-full shadow-lg">
          V3 - CONNECTED
        </div>
      </div>
    </div>
  );
}
