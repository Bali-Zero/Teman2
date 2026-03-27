/**
 * Composite hook for Chat Page orchestration
 *
 * Combines all chat-related hooks and provides a unified interface
 * for the ChatPage component.
 */

import { useState, useEffect, useRef, useCallback, useOptimistic, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { v4 as uuidv4 } from 'uuid';
import { api } from '@/lib/api';
import { toast as sonnerToast } from 'sonner';
import { logger } from '@/lib/logger';
import { chatMetrics } from '@/lib/metrics';
import { trackEvent } from '@/lib/analytics';
import { saveConversation } from '@/app/chat/actions';
import { useChatInput } from './useChatInput';
import { useChatSidebar } from './useChatSidebar';
import { useChatSend } from './useChatSend';
import { useConversations } from './useConversations';
import { useTeamStatus } from './useTeamStatus';
import { useConversationPersistence } from './useConversationPersistence';
import type { ChatMessage, Source } from '@/app/chat/actions';
import type { AgentStep } from '@/types';

import type { SingleConversationResponse } from '@/lib/api/conversations/conversations.types';

/**
 * Type guard for conversation message from API
 * Uses SingleConversationResponse type from API
 */
type ApiConversationMessage = SingleConversationResponse['messages'][number] & {
  id?: string;
  timestamp?: string | Date;
  images?: Array<{ id: string; base64: string; name: string; size: number }>;
  steps?: AgentStep[];
  metadata?: unknown;
};

function isApiConversationMessage(value: unknown): value is ApiConversationMessage {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const msg = value as Record<string, unknown>;
  return typeof msg.role === 'string' && typeof msg.content === 'string';
}

export interface OptimisticMessage extends ChatMessage {
  isPending?: boolean;
  isStreaming?: boolean;
}

const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
const generateSessionId = () => `session_${uuidv4()}`;

export interface UseChatPageReturn {
  // State
  sessionId: string;
  messages: OptimisticMessage[];
  displayMessages: OptimisticMessage[];
  isInitialLoading: boolean;
  userName: string;
  userAvatar: string | null;
  showUserMenu: boolean;
  toast: { message: string; type: 'success' | 'error' } | null;
  isPending: boolean;
  currentStatus: string;
  streamingSteps: Array<AgentStep>;
  imageModalOpen: boolean;

  // Refs
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isMountedRef: React.MutableRefObject<boolean>;

  // Hooks
  chatInput: ReturnType<typeof useChatInput>;
  sidebar: ReturnType<typeof useChatSidebar>;
  conversations: ReturnType<typeof useConversations>;
  teamStatus: ReturnType<typeof useTeamStatus>;

  // Handlers
  handleSend: () => Promise<void>;
  handleNewChat: () => void;
  handleConversationClick: (id: number) => Promise<void>;
  handleDeleteConversation: (id: number, e: React.MouseEvent) => void;
  handleAvatarChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleImageGenSubmit: () => void;
  toggleClock: () => Promise<void>;
  showToast: (message: string, type: 'success' | 'error') => void;
  setShowUserMenu: (show: boolean) => void;
  setToast: (toast: { message: string; type: 'success' | 'error' } | null) => void;
  setImageModalOpen: (open: boolean) => void;
}

export function useChatPage(): UseChatPageReturn {
  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isMountedRef = useRef(true);
  const isAbortedRef = useRef(false);

  const { sessionId, setSessionId, isLoading: isSessionLoading } = useConversationPersistence();
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [messages, setMessages] = useState<OptimisticMessage[]>([]);

  // Update loading state when session is ready
  useEffect(() => {
    if (!isSessionLoading) {
      setIsInitialLoading(false);
    }
  }, [isSessionLoading]);

  // Load conversation history when sessionId is restored from sessionStorage
  useEffect(() => {
    if (!sessionId || isSessionLoading) return;
    if (messages.length > 0) return;

    const loadHistory = async () => {
      setIsHistoryLoading(true);
      try {
        const history = await api.getConversationHistory(sessionId);
        if (history.success && history.messages.length > 0 && isMountedRef.current) {
          setMessages(
            history.messages.map((m) => ({
              id: generateId(),
              role: m.role as 'user' | 'assistant',
              content: m.content,
              sources: m.sources as Source[] | undefined,
              imageUrl: m.imageUrl,
              timestamp: new Date(),
              isPending: false,
            }))
          );
          logger.info('Conversation history restored', {
            component: 'useChatPage',
            action: 'loadHistory',
            metadata: { sessionId, messageCount: history.messages.length },
          });
        }
      } catch (error) {
        logger.warn('Could not load conversation history', {
          component: 'useChatPage',
          action: 'loadHistory',
          metadata: { sessionId, error: String(error) },
        });
      } finally {
        if (isMountedRef.current) {
          setIsHistoryLoading(false);
        }
      }
    };

    loadHistory();
  }, [sessionId, isSessionLoading]);

  const [currentStatus, setCurrentStatus] = useState('');
  const [streamingSteps, setStreamingSteps] = useState<Array<AgentStep>>([]);
  const [userName, setUserName] = useState<string>('');
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    type: 'success' | 'error';
  } | null>(null);
  const [imageModalOpen, setImageModalOpen] = useState(false);

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
  }, []);

  // Custom Hooks
  const chatInput = useChatInput();
  const sidebar = useChatSidebar();
  const conversations = useConversations();
  const teamStatus = useTeamStatus();

  // Setup toast callbacks
  useEffect(() => {
    chatInput.setShowToast(showToast);
    // setShowToast reference available for child hooks
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // ← Run only once on mount to avoid infinite loop

  // Optimistic messages (Source of Truth dal React Context dei messaggi reali)
  const [optimisticMessages, addOptimisticMessage] = useOptimistic<
    OptimisticMessage[],
    OptimisticMessage
  >(messages, (state, newMessage) => [...state, newMessage]);

  const displayMessages = optimisticMessages;
  const [isPending, startTransition] = useTransition();

  // Chat send hook delegato
  const chatSend = useChatSend({
    sessionId,
    conversationHistory: messages
      .filter((m) => !m.isStreaming)
      .map((m) => ({ role: m.role, content: m.content || '' })),
    isMountedRef,
    isAbortedRef,
    onToast: showToast,
    onChunk: (chunk: string) => {
      setMessages((prev) => {
        if (prev.length === 0) return prev;
        const newMsgs = [...prev];
        const lastMsg = newMsgs[newMsgs.length - 1];
        if (lastMsg.role === 'assistant') {
          lastMsg.content = (lastMsg.content || '') + chunk;
        }
        return newMsgs;
      });
    },
    onStep: (step: AgentStep) => {
      // Gestito in streamingSteps da useChatSend
    },
    onComplete: async (
      fullResponse: string,
      sources: any[],
      metadata?: ChatMessage['metadata']
    ) => {
      setMessages((prev) => {
        if (prev.length === 0) return prev;
        const newMsgs = [...prev];
        const lastMsg = newMsgs[newMsgs.length - 1];
        if (lastMsg.role === 'assistant') {
          lastMsg.content = fullResponse;
          lastMsg.sources = sources;
          lastMsg.isStreaming = false;
          if (metadata) lastMsg.metadata = metadata;
        }
        return newMsgs;
      });

      // Salvataggio conversazione
      try {
        const title =
          messages.length === 0
            ? chatInput.input.slice(0, 50) + (chatInput.input.length > 50 ? '...' : '')
            : 'Nuova Conversazione';

        // L'API di actions.ts si aspetta un oggetto con title, messages, e options

        // L'API di actions.ts (saveConversation) richiede: sessionId (string) e messages (ChatMessage[])

        // Force types
        await saveConversation(
          sessionId as any,
          [
            ...(messages.map((m) => ({
              role: m.role,
              content: m.content || '',
            })) as any),
            { role: 'assistant', content: fullResponse } as any,
          ] as any
        );
      } catch (e) {
        logger.error('Save error', {}, e as Error);
      }
    },
    onError: (error: Error) => {
      logger.error('Chat error', { component: 'useChatPage' }, error);
    },
  });

  // Handle send message (Thin delegator)
  const handleSend = useCallback(async () => {
    const trimmedInput = chatInput.input.trim();
    const hasImages = chatInput.attachedImages.length > 0;

    if ((!trimmedInput && !hasImages) || isPending || chatSend.isStreaming) {
      return;
    }

    const userMsg: OptimisticMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: trimmedInput,
      timestamp: new Date(),
      isPending: true,
      images: chatInput.attachedImages,
    };

    startTransition(() => {
      addOptimisticMessage(userMsg);
    });

    setMessages((prev) => [...prev, { ...userMsg, isPending: false }]);
    setMessages((prev) => [
      ...prev,
      {
        id: `ast_${Date.now()}`,
        role: 'assistant',
        content: '',
        isStreaming: true,
        timestamp: new Date(),
      },
    ]);

    chatInput.setInput('');
    chatInput.setAttachedImages([]);
    chatInput.setImageGenPrompt('');

    setTimeout(() => {
      const textarea = document.querySelector('textarea');
      textarea?.focus();
    }, 100);

    await chatSend.sendMessage(trimmedInput, chatInput.attachedImages);
  }, [chatInput, isPending, chatSend, addOptimisticMessage]);

  // Load user profile
  const loadUserProfile = useCallback(async () => {
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile && isMountedRef.current) {
        const name =
          storedProfile.name || (storedProfile.email ? storedProfile.email.split('@')[0] : 'User');
        setUserName(name);
        if (storedProfile.avatar) setUserAvatar(storedProfile.avatar);
        return;
      }
      const profile = await api.getProfile();
      if (isMountedRef.current) {
        if (!profile || !profile.email) {
          setUserName('User');
          return;
        }
        const name = profile.name || (profile.email ? profile.email.split('@')[0] : 'User');
        setUserName(name);
        if (profile.avatar) setUserAvatar(profile.avatar);
      }
    } catch (error) {
      logger.error(
        'Failed to load user profile',
        { component: 'useChatPage', action: 'loadUserProfile' },
        error instanceof Error ? error : new Error(String(error))
      );
      // Set default user name on error
      if (isMountedRef.current) {
        setUserName('User');
      }
    }
  }, []);

  // Handle avatar upload
  const handleAvatarChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

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
      reader.onerror = () => showToast('Failed to read image file', 'error');
      reader.readAsDataURL(file);
    },
    [showToast]
  );

  // Initial data load
  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push('/login');
      return;
    }

    const loadInitialData = async () => {
      setIsInitialLoading(true);
      try {
        await Promise.all([
          conversations.loadConversationList(),
          teamStatus.loadClockStatus(),
          loadUserProfile(),
        ]);
        if (isMountedRef.current) setIsInitialLoading(false);
      } catch (error) {
        if (isMountedRef.current) setIsInitialLoading(false);
        logger.error(
          'Failed to load initial data',
          { component: 'useChatPage', action: 'loadInitialData' },
          error instanceof Error ? error : new Error(String(error))
        );
      }
    };
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // ← Run only once on mount to avoid infinite loop

  // Load avatar from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedAvatar = localStorage.getItem('user_avatar');
      if (savedAvatar && isMountedRef.current) setUserAvatar(savedAvatar);
    }
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayMessages]);

  // Handle new chat
  const handleNewChat = useCallback(() => {
    logger.info('New chat created', {
      component: 'useChatPage',
      action: 'handleNewChat',
      metadata: { previousSessionId: sessionId },
    });
    // trackEvent now imported at top
    const userProfile = api.getUserProfile();
    trackEvent('chat_new_conversation', { previousSessionId: sessionId }, userProfile?.email);

    const newSessionId = generateSessionId();
    setMessages([]);
    setCurrentStatus('');
    setSessionId(newSessionId);
    conversations.setCurrentConversationId(null);
    sidebar.closeSidebar();
  }, [sessionId, conversations, sidebar]);

  // Handle conversation click
  const handleConversationClick = useCallback(
    async (id: number) => {
      conversations.setCurrentConversationId(id);
      try {
        const conv = await api.getConversation(id);
        if (conv && conv.messages) {
          setMessages(
            conv.messages.filter(isApiConversationMessage).map((m): ChatMessage => {
              const role = (m.role === 'user' || m.role === 'assistant' ? m.role : 'assistant') as
                | 'user'
                | 'assistant';
              const timestamp = m.timestamp
                ? typeof m.timestamp === 'string'
                  ? new Date(m.timestamp)
                  : (m.timestamp as Date)
                : new Date();
              const sources: Source[] | undefined = m.sources?.map(
                (s: { title?: string; content?: string }) => ({
                  title: s.title || '',
                  content: s.content,
                })
              );
              return {
                id: m.id || generateId(),
                role,
                content: m.content || '',
                timestamp,
                sources,
              };
            })
          );
          if (conv.session_id) setSessionId(conv.session_id);

          // Track metrics
          chatMetrics.conversationLoaded(id, conv.messages.length);

          // trackEvent now imported at top
          const userProfile = api.getUserProfile();
          trackEvent(
            'chat_conversation_loaded',
            { conversationId: id, messageCount: conv.messages.length },
            userProfile?.email
          );
        }
      } catch (error) {
        logger.error(
          'Failed to load conversation',
          {
            component: 'useChatPage',
            action: 'handleConversationClick',
            metadata: { conversationId: id },
          },
          error instanceof Error ? error : new Error(String(error))
        );
      }
      if (window.innerWidth < 768) sidebar.closeSidebar();
    },
    [conversations, sidebar]
  );

  // Handle delete conversation
  const handleDeleteConversation = useCallback(
    (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      sonnerToast('Delete this conversation?', {
        action: {
          label: 'Delete',
          onClick: async () => {
            try {
              await conversations.deleteConversation(id);
              const userProfile = api.getUserProfile();
              trackEvent('chat_conversation_deleted', { conversationId: id }, userProfile?.email);
              if (conversations.currentConversationId === id) handleNewChat();
            } catch (error) {
              logger.error(
                'Failed to delete conversation',
                {
                  component: 'useChatPage',
                  action: 'handleDeleteConversation',
                  metadata: { conversationId: id },
                },
                error instanceof Error ? error : new Error(String(error))
              );
            }
          },
        },
        cancel: { label: 'Cancel', onClick: () => {} },
      });
    },
    [conversations, handleNewChat]
  );

  // Handle clock toggle
  const toggleClock = useCallback(async () => {
    try {
      await teamStatus.toggleClock();
    } catch (error) {
      logger.error(
        'Clock status toggle failed',
        { component: 'useChatPage', action: 'toggleClock' },
        error instanceof Error ? error : new Error(String(error))
      );
    }
  }, [teamStatus]);

  // Handle image generation submit
  const handleImageGenSubmit = useCallback(() => {
    if (!chatInput.imageGenPrompt.trim()) return;

    logger.info('Image generation modal submitted', {
      component: 'useChatPage',
      action: 'handleImageGenSubmit',
      metadata: { promptLength: chatInput.imageGenPrompt.trim().length },
    });

    chatInput.setInput(`Genera un'immagine: ${chatInput.imageGenPrompt.trim()}`);
    chatInput.setImageGenPrompt('');
    setTimeout(() => {
      const textarea = document.querySelector('textarea');
      textarea?.focus();
    }, 100);
  }, [chatInput]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  return {
    sessionId,
    messages,
    displayMessages,
    isInitialLoading: isInitialLoading || isHistoryLoading,
    userName,
    userAvatar,
    showUserMenu,
    toast,
    isPending: isPending || chatSend.isStreaming,
    currentStatus,
    streamingSteps,
    imageModalOpen,
    messagesEndRef,
    fileInputRef,
    isMountedRef,
    chatInput,
    sidebar,
    conversations,
    teamStatus,
    handleSend,
    handleNewChat,
    handleConversationClick,
    handleDeleteConversation,
    handleAvatarChange,
    handleImageGenSubmit,
    toggleClock,
    showToast,
    setShowUserMenu,
    setToast,
    setImageModalOpen,
  };
}
