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
import { logger } from '@/lib/logger';
import { chatMetrics } from '@/lib/metrics';
import { saveConversation } from '@/app/chat/actions';
import { useChatInput } from './useChatInput';
import { useChatTTS } from './useChatTTS';
import { useChatSidebar } from './useChatSidebar';
import { useChatSend } from './useChatSend';
import { useConversations } from './useConversations';
import { useTeamStatus } from './useTeamStatus';
import { useAudioRecorder } from './useAudioRecorder';
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
  chatTTS: ReturnType<typeof useChatTTS>;
  sidebar: ReturnType<typeof useChatSidebar>;
  conversations: ReturnType<typeof useConversations>;
  teamStatus: ReturnType<typeof useTeamStatus>;
  audioRecorder: ReturnType<typeof useAudioRecorder>;

  // Handlers
  handleSend: () => Promise<void>;
  handleNewChat: () => void;
  handleConversationClick: (id: number) => Promise<void>;
  handleDeleteConversation: (id: number, e: React.MouseEvent) => Promise<void>;
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

  // Session state
  const [sessionId, setSessionId] = useState(() => {
    const id = generateSessionId();
    logger.info('Session ID generated with UUID v4', {
      component: 'useChatPage',
      action: 'init_session',
      metadata: { sessionIdFormat: 'uuid_v4', length: id.length },
    });
    return id;
  });
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [messages, setMessages] = useState<OptimisticMessage[]>([]);
  const [currentStatus, setCurrentStatus] = useState('');
  const [streamingSteps, setStreamingSteps] = useState<Array<AgentStep>>([]);
  const [userName, setUserName] = useState<string>('');
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [imageModalOpen, setImageModalOpen] = useState(false);

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
  }, []);

  // Custom Hooks
  const chatInput = useChatInput();
  const chatTTS = useChatTTS();
  const sidebar = useChatSidebar();
  const conversations = useConversations();
  const teamStatus = useTeamStatus();
  const audioRecorder = useAudioRecorder();

  // Setup toast callbacks
  useEffect(() => {
    chatInput.setShowToast(showToast);
    chatTTS.setShowToast(showToast);
  }, [chatInput, chatTTS, showToast]);

  // Optimistic messages
  const [optimisticMessages, addOptimisticMessage] = useOptimistic<
    OptimisticMessage[],
    OptimisticMessage
  >(messages, (state, newMessage) => [...state, newMessage]);

  const displayMessages = optimisticMessages;
  const [isPending, startTransition] = useTransition();

  // Chat send hook
  const chatSend = useChatSend({
    sessionId,
    attachedImages: chatInput.attachedImages,
    conversationHistory: displayMessages
      .filter((m) => !m.isStreaming)
      .map((m) => ({ role: m.role, content: m.content })),
    isMountedRef,
    isAbortedRef,
    onToast: showToast,
    onChunk: (chunk: string) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === displayMessages[displayMessages.length - 1]?.id && m.role === 'assistant'
            ? { ...m, content: chunk, isPending: false }
            : m
        )
      );
    },
    onComplete: (fullResponse, sources, metadata) => {
      const typedMeta = metadata as
        | {
            generated_image?: string;
            followup_questions?: string[];
            execution_time?: number;
            route_used?: string;
          }
        | undefined;

      logger.info('Message received successfully', {
        component: 'useChatPage',
        action: 'onComplete',
        metadata: { sessionId, responseLength: fullResponse.length },
      });

      // Track metrics
      const executionTime = typedMeta?.execution_time || 0;
      chatMetrics.messageReceived(fullResponse.length, executionTime);

      const { trackEvent } = require('@/lib/analytics');
      const userProfile = api.getUserProfile();
      trackEvent(
        'chat_message_received',
        { sessionId, responseLength: fullResponse.length },
        userProfile?.email
      );

      setMessages((prev) =>
        prev.map((m) =>
          m.id === displayMessages[displayMessages.length - 1]?.id && m.role === 'assistant'
            ? {
                ...m,
                content: fullResponse,
                sources: sources as Source[],
                isStreaming: false,
                isPending: false,
                ...(typedMeta?.generated_image ? { imageUrl: typedMeta.generated_image } : {}),
                ...(typedMeta?.followup_questions && typedMeta.followup_questions.length > 0
                  ? { metadata: { followup_questions: typedMeta.followup_questions } }
                  : {}),
              }
            : m
        )
      );
      setCurrentStatus('');

      startTransition(async () => {
        try {
          await saveConversation(
            displayMessages
              .filter((m) => !m.isStreaming)
              .map((m) => ({
                ...m,
                content:
                  m.id === displayMessages[displayMessages.length - 1]?.id
                    ? fullResponse
                    : m.content,
              })),
            sessionId
          );

          // Track metrics
          chatMetrics.conversationSaved(
            sessionId,
            displayMessages.filter((m) => !m.isStreaming).length
          );

          trackEvent('chat_conversation_saved', { sessionId }, userProfile?.email);
        } catch (error) {
          logger.error(
            'Failed to save conversation',
            { component: 'useChatPage', action: 'saveConversation', metadata: { sessionId } },
            error instanceof Error ? error : new Error(String(error))
          );
        }
      });
    },
    onError: (error: Error) => {
      logger.error(
        'Message send error',
        {
          component: 'useChatPage',
          action: 'onError',
          metadata: { sessionId, errorMessage: error.message },
        },
        error
      );
      setMessages((prev) =>
        prev.map((m) =>
          m.id === displayMessages[displayMessages.length - 1]?.id && m.role === 'assistant'
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
    },
    onStep: (step: AgentStep) => {
      setStreamingSteps((prev) => [...prev, step]);
      if (step.type === 'status' && typeof step.data === 'string') {
        setCurrentStatus(step.data);
      }
    },
  });

  // Handle send message
  const handleSend = useCallback(async () => {
    const trimmedInput = chatInput.input.trim();
    const hasImages = chatInput.attachedImages.length > 0;

    if ((!trimmedInput && !hasImages) || isPending || chatSend.isStreaming) return;

    logger.info('Message send started', {
      component: 'useChatPage',
      action: 'handleSend',
      metadata: {
        sessionId,
        textLength: trimmedInput.length,
        hasImages: chatInput.attachedImages.length > 0,
      },
    });

    // Track metrics
    chatMetrics.messageSent(chatInput.attachedImages.length > 0, chatInput.attachedImages.length);
    chatMetrics.streamingStarted(sessionId);

    chatInput.clearInput();
    chatInput.clearAttachments();
    setStreamingSteps([]);
    setCurrentStatus('');

    const userMessage: OptimisticMessage = {
      id: generateId(),
      role: 'user',
      content: trimmedInput || (hasImages ? '[Image attached]' : ''),
      images: chatInput.attachedImages.length > 0 ? chatInput.attachedImages : undefined,
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

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    await chatSend.sendMessage(trimmedInput || '[Image attached]');
  }, [chatInput, isPending, chatSend, sessionId, addOptimisticMessage]);

  // Load user profile
  const loadUserProfile = useCallback(async () => {
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile && isMountedRef.current) {
        setUserName(storedProfile.name || storedProfile.email.split('@')[0]);
        if (storedProfile.avatar) setUserAvatar(storedProfile.avatar);
        return;
      }
      const profile = await api.getProfile();
      if (isMountedRef.current) {
        setUserName(profile.name || profile.email.split('@')[0]);
        if (profile.avatar) setUserAvatar(profile.avatar);
      }
    } catch (error) {
      logger.error(
        'Failed to load user profile',
        { component: 'useChatPage', action: 'loadUserProfile' },
        error instanceof Error ? error : new Error(String(error))
      );
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
  }, [router, conversations, teamStatus, loadUserProfile]);

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
    const { trackEvent } = require('@/lib/analytics');
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

          const { trackEvent } = require('@/lib/analytics');
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
    async (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!window.confirm('Delete this conversation?')) return;

      try {
        await conversations.deleteConversation(id);
        const { trackEvent } = require('@/lib/analytics');
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

  // Handle audio transcription
  useEffect(() => {
    const processAudio = async () => {
      if (!audioRecorder.audioBlob || !isMountedRef.current) return;

      try {
        if (audioRecorder.audioBlob.size < 1000) {
          chatInput.setInput('');
          showToast('Recording too short. Please hold the mic button longer.', 'error');
          return;
        }

        if (
          !audioRecorder.audioBlob.type.startsWith('audio/') &&
          !audioRecorder.audioMimeType.startsWith('audio/')
        ) {
          chatInput.setInput('');
          showToast('Invalid audio format. Please try recording again.', 'error');
          return;
        }

        chatInput.setInput('Transcribing...');
        const transcriptionStart = Date.now();
        const text = await api.transcribeAudio(
          audioRecorder.audioBlob,
          audioRecorder.audioMimeType
        );
        const transcriptionDuration = (Date.now() - transcriptionStart) / 1000;

        if (!isMountedRef.current) return;

        if (text && text.trim()) {
          // Track metrics
          chatMetrics.audioTranscribed(
            audioRecorder.audioBlob.size,
            text.length,
            transcriptionDuration
          );

          const { trackEvent } = require('@/lib/analytics');
          const userProfile = api.getUserProfile();
          trackEvent(
            'chat_audio_transcribed',
            { blobSize: audioRecorder.audioBlob.size, textLength: text.length },
            userProfile?.email
          );
          chatInput.setInput(text);
        } else {
          chatInput.setInput('');
          showToast('No speech detected. Please speak clearly and try again.', 'error');
        }
      } catch (error) {
        if (!isMountedRef.current) return;
        chatInput.setInput('');
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        showToast(`Transcription failed: ${errorMessage}`, 'error');
      }
    };
    processAudio();
  }, [audioRecorder.audioBlob, audioRecorder.audioMimeType, chatInput, showToast]);

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
    isInitialLoading,
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
    chatTTS,
    sidebar,
    conversations,
    teamStatus,
    audioRecorder,
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
