/**
 * Chat Page - Refactored Modular Architecture
 *
 * This is a lightweight orchestrator that composes:
 * - Custom hooks for business logic
 * - UI components for rendering
 *
 * Responsibilities:
 * - Layout and composition
 * - Initial data loading
 * - User profile management
 * - Toast notifications
 *
 * @module ChatPage
 */

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

// Custom Hooks
import { useChatMessages } from '@/hooks/useChatMessages';
import { useChatInput } from '@/hooks/useChatInput';
import { useChatTTS } from '@/hooks/useChatTTS';
import { useChatSidebar } from '@/hooks/useChatSidebar';
import { useConversations } from '@/hooks/useConversations';
import { useTeamStatus } from '@/hooks/useTeamStatus';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';

// Components
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import { ChatInputBar } from '@/components/chat/ChatInputBar';
import { ImageGenModal } from '@/components/chat/ImageGenModal';
import { SearchDocsModal } from '@/components/search/SearchDocsModal';
import { Toast } from '@/components/chat/Toast';

// API & Utils
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { saveConversation } from './actions';
import type { ChatMessage } from './actions';
import type { Message, AgentStep } from '@/types';

/**
 * Type guard for conversation message from API
 */
interface ApiConversationMessage {
  id?: string;
  role: string;
  content?: string;
  timestamp?: string | Date;
  sources?: Array<{ title?: string; content?: string; url?: string; score?: number }>;
  images?: Array<{ id: string; base64: string; name: string; size: number }>;
  steps?: Array<{ type: string; data: unknown; timestamp: Date }>;
  metadata?: unknown;
  imageUrl?: string;
}

/**
 * Type guard to check if a message is from API
 */
function isApiConversationMessage(msg: unknown): msg is ApiConversationMessage {
  return (
    typeof msg === 'object' &&
    msg !== null &&
    'role' in msg &&
    typeof (msg as ApiConversationMessage).role === 'string'
  );
}

// Types
interface OptimisticMessage extends ChatMessage {
  isPending?: boolean;
  isStreaming?: boolean;
}

// Utilities
const generateSessionId = () => `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

/**
 * Chat Page Component - Modular Architecture
 *
 * Composes custom hooks and UI components to provide
 * a complete chat experience with streaming, TTS, and more.
 */
export default function ChatPage() {
  const router = useRouter();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Session state
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  // User profile state
  const [userName, setUserName] = useState<string>('');
  const [userAvatar, setUserAvatar] = useState<string | null>(null);

  // Toast state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Custom Hooks
  const {
    messages,
    setMessages,
    addMessage,
    updateLastAssistantMessage,
    clearMessages,
    isMountedRef,
  } = useChatMessages();

  const chatInput = useChatInput();
  const chatTTS = useChatTTS();
  const sidebar = useChatSidebar();

  const {
    conversations,
    isLoading: isConversationsLoading,
    currentConversationId,
    setCurrentConversationId,
    loadConversationList,
    deleteConversation,
  } = useConversations();

  const {
    isClockIn,
    isLoading: isClockLoading,
    toggleClock: originalToggleClock,
    loadClockStatus,
  } = useTeamStatus();

  const { isRecording, startRecording, stopRecording, audioBlob, recordingTime, audioMimeType } =
    useAudioRecorder();

  // Setup toast callbacks
  useEffect(() => {
    chatInput.setShowToast((message, type) => {
      setToast({ message, type });
    });
    chatTTS.setShowToast((message, type) => {
      setToast({ message, type });
    });
  }, [chatInput, chatTTS]);

  // Load user profile
  const loadUserProfile = useCallback(async () => {
    logger.debug('Loading user profile', {
      component: 'ChatPage',
      action: 'loadUserProfile',
    });

    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile && isMountedRef.current) {
        setUserName(storedProfile.name || storedProfile.email.split('@')[0]);
        if (storedProfile.avatar) {
          setUserAvatar(storedProfile.avatar);
        }
        logger.info('User profile loaded from cache', {
          component: 'ChatPage',
          action: 'loadUserProfile',
          metadata: { email: storedProfile.email, hasAvatar: !!storedProfile.avatar },
        });
        return;
      }
      const profile = await api.getProfile();
      if (isMountedRef.current) {
        setUserName(profile.name || profile.email.split('@')[0]);
        if (profile.avatar) {
          setUserAvatar(profile.avatar);
        }
        logger.info('User profile loaded from API', {
          component: 'ChatPage',
          action: 'loadUserProfile',
          metadata: { email: profile.email, hasAvatar: !!profile.avatar },
        });
      }
    } catch (error) {
      if (isMountedRef.current) {
        logger.error(
          'Failed to load user profile',
          {
            component: 'ChatPage',
            action: 'loadUserProfile',
          },
          error instanceof Error ? error : new Error(String(error))
        );
      }
    }
  }, [isMountedRef]);

  // Handle avatar upload
  const handleAvatarChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      logger.debug('Avatar upload started', {
        component: 'ChatPage',
        action: 'handleAvatarChange',
        metadata: { fileName: file.name, fileSize: file.size, fileType: file.type },
      });

      if (!file.type.startsWith('image/')) {
        logger.warn('Invalid file type for avatar', {
          component: 'ChatPage',
          action: 'handleAvatarChange',
          metadata: { fileType: file.type },
        });
        setToast({ message: 'Please select an image file', type: 'error' });
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        logger.warn('Avatar file too large', {
          component: 'ChatPage',
          action: 'handleAvatarChange',
          metadata: { fileSize: file.size },
        });
        setToast({ message: 'Image must be less than 5MB', type: 'error' });
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result as string;
        setUserAvatar(base64String);
        localStorage.setItem('user_avatar', base64String);
        logger.info('Avatar updated successfully', {
          component: 'ChatPage',
          action: 'handleAvatarChange',
          metadata: { fileSize: file.size },
        });
        setToast({ message: 'Avatar updated', type: 'success' });
      };
      reader.onerror = () => {
        logger.error(
          'Failed to read avatar file',
          {
            component: 'ChatPage',
            action: 'handleAvatarChange',
          },
          new Error('FileReader error')
        );
        setToast({ message: 'Failed to read image file', type: 'error' });
      };
      reader.readAsDataURL(file);
    }
  }, []);

  // Initial data load
  useEffect(() => {
    if (!api.isAuthenticated()) {
      logger.warn('User not authenticated, redirecting to login', {
        component: 'ChatPage',
        action: 'authCheck',
      });
      router.push('/login');
      return;
    }

    const loadInitialData = async () => {
      logger.debug('Loading initial data', {
        component: 'ChatPage',
        action: 'loadInitialData',
      });
      setIsInitialLoading(true);
      const startTime = Date.now();

      try {
        await Promise.all([loadConversationList(), loadClockStatus(), loadUserProfile()]);
        const duration = Date.now() - startTime;

        if (isMountedRef.current) {
          setIsInitialLoading(false);
          logger.info('Initial data loaded successfully', {
            component: 'ChatPage',
            action: 'loadInitialData',
            metadata: { duration },
          });
        }
      } catch (error) {
        if (isMountedRef.current) {
          setIsInitialLoading(false);
          logger.error(
            'Failed to load initial data',
            {
              component: 'ChatPage',
              action: 'loadInitialData',
            },
            error instanceof Error ? error : new Error(String(error))
          );
        }
      }
    };
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // ← Execute only once on mount

  // Load avatar from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedAvatar = localStorage.getItem('user_avatar');
      if (savedAvatar && isMountedRef.current) {
        setUserAvatar(savedAvatar);
        logger.debug('Avatar loaded from localStorage', {
          component: 'ChatPage',
          action: 'loadAvatar',
        });
      }
    }
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle new chat
  const handleNewChat = useCallback(() => {
    logger.info('New chat created', {
      component: 'ChatPage',
      action: 'handleNewChat',
      metadata: { previousSessionId: sessionId },
    });

    const { trackEvent } = require('@/lib/analytics');
    const userProfile = api.getUserProfile();
    trackEvent('chat_new_conversation', { previousSessionId: sessionId }, userProfile?.email);

    const newSessionId = generateSessionId();
    clearMessages();
    setSessionId(newSessionId);
    setCurrentConversationId(null);
    sidebar.closeSidebar();
  }, [sessionId, clearMessages, setCurrentConversationId, sidebar]);

  // Handle conversation click
  const handleConversationClick = useCallback(
    async (id: number) => {
      logger.debug('Loading conversation', {
        component: 'ChatPage',
        action: 'handleConversationClick',
        metadata: { conversationId: id },
      });

      setCurrentConversationId(id);
      try {
        const conv = await api.getConversation(id);
        if (conv && conv.messages) {
          setMessages(
            conv.messages.map((m, index): Message => {
              // Validate and convert role
              const role: 'user' | 'assistant' =
                m.role === 'user' || m.role === 'assistant' ? m.role : 'assistant';

              // Generate timestamp (messages from API don't have timestamp, use index-based approximation)
              const timestamp = new Date(Date.now() - (conv.messages.length - index) * 60000);

              // Convert sources to Source[] format
              const sources =
                m.sources?.map((s: { title?: string; content?: string }) => ({
                  title: s.title || '',
                  content: s.content,
                  url: undefined,
                  score: undefined,
                })) || [];

              return {
                id: `msg_${id}_${index}_${Date.now()}`,
                role,
                content: m.content || '',
                timestamp,
                sources,
                imageUrl: m.imageUrl,
              };
            })
          );
          if (conv.session_id) {
            setSessionId(conv.session_id);
          }

          logger.info('Conversation loaded successfully', {
            component: 'ChatPage',
            action: 'handleConversationClick',
            metadata: {
              conversationId: id,
              messageCount: conv.messages.length,
              sessionId: conv.session_id,
            },
          });

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
            component: 'ChatPage',
            action: 'handleConversationClick',
            metadata: { conversationId: id },
          },
          error instanceof Error ? error : new Error(String(error))
        );
      }
      if (window.innerWidth < 768) sidebar.closeSidebar();
    },
    [setCurrentConversationId, setMessages, sidebar]
  );

  // Handle delete conversation
  const handleDeleteConversation = useCallback(
    async (id: number, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!window.confirm('Delete this conversation?')) {
        logger.debug('Conversation deletion cancelled', {
          component: 'ChatPage',
          action: 'handleDeleteConversation',
          metadata: { conversationId: id },
        });
        return;
      }

      logger.info('Deleting conversation', {
        component: 'ChatPage',
        action: 'handleDeleteConversation',
        metadata: { conversationId: id },
      });

      try {
        await deleteConversation(id);
        logger.info('Conversation deleted successfully', {
          component: 'ChatPage',
          action: 'handleDeleteConversation',
          metadata: { conversationId: id },
        });

        const { trackEvent } = require('@/lib/analytics');
        const userProfile = api.getUserProfile();
        trackEvent('chat_conversation_deleted', { conversationId: id }, userProfile?.email);

        if (currentConversationId === id) handleNewChat();
      } catch (error) {
        logger.error(
          'Failed to delete conversation',
          {
            component: 'ChatPage',
            action: 'handleDeleteConversation',
            metadata: { conversationId: id },
          },
          error instanceof Error ? error : new Error(String(error))
        );
      }
    },
    [deleteConversation, currentConversationId, handleNewChat]
  );

  // Handle clock toggle
  const toggleClock = useCallback(async () => {
    logger.info('Clock status toggle started', {
      component: 'ChatPage',
      action: 'toggleClock',
      metadata: { currentStatus: isClockIn ? 'online' : 'offline' },
    });
    try {
      await originalToggleClock();
      logger.info('Clock status toggle successful', {
        component: 'ChatPage',
        action: 'toggleClock',
        metadata: { newStatus: !isClockIn ? 'online' : 'offline' },
      });
    } catch (error) {
      logger.error(
        'Clock status toggle failed',
        {
          component: 'ChatPage',
          action: 'toggleClock',
        },
        error instanceof Error ? error : new Error(String(error))
      );
    }
  }, [isClockIn, originalToggleClock]);

  // Handle image generation submit
  const handleImageGenSubmit = useCallback(() => {
    if (!chatInput.imageGenPrompt.trim()) return;

    logger.info('Image generation requested', {
      component: 'ChatPage',
      action: 'handleImageGenSubmit',
      metadata: { promptLength: chatInput.imageGenPrompt.trim().length },
    });

    chatInput.setInput(`Genera un'immagine: ${chatInput.imageGenPrompt.trim()}`);
    chatInput.setImageGenPrompt('');
    // Focus textarea to allow user to send
    setTimeout(() => {
      const textarea = document.querySelector('textarea');
      textarea?.focus();
    }, 100);
  }, [chatInput]);

  // Handle send message (simplified - will be replaced by useChatSend)
  const handleSend = useCallback(async () => {
    // TODO: Integrate useChatSend hook here
    // For now, this is a placeholder
    console.log('Send message:', chatInput.input);
  }, [chatInput.input]);

  // Handle audio transcription
  useEffect(() => {
    const processAudio = async () => {
      if (audioBlob && isMountedRef.current) {
        try {
          if (audioBlob.size < 1000) {
            chatInput.setInput('');
            setToast({
              message: 'Recording too short. Please hold the mic button longer.',
              type: 'error',
            });
            return;
          }

          if (!audioBlob.type.startsWith('audio/') && !audioMimeType.startsWith('audio/')) {
            chatInput.setInput('');
            setToast({
              message: 'Invalid audio format. Please try recording again.',
              type: 'error',
            });
            return;
          }

          logger.debug('Processing audio blob', {
            component: 'ChatPage',
            action: 'transcribeAudio',
            metadata: { blobSize: audioBlob.size, mimeType: audioMimeType },
          });
          chatInput.setInput('Transcribing...');

          const transcriptionStartTime = Date.now();
          const text = await api.transcribeAudio(audioBlob, audioMimeType);
          const transcriptionDuration = Date.now() - transcriptionStartTime;

          if (!isMountedRef.current) return;

          if (text && text.trim()) {
            logger.info('Audio transcribed successfully', {
              component: 'ChatPage',
              action: 'transcribeAudio',
              metadata: {
                blobSize: audioBlob.size,
                mimeType: audioMimeType,
                textLength: text.length,
                duration: transcriptionDuration,
                recordingTime,
              },
            });

            const { trackEvent } = require('@/lib/analytics');
            const userProfile = api.getUserProfile();
            trackEvent(
              'chat_audio_transcribed',
              {
                blobSize: audioBlob.size,
                textLength: text.length,
                duration: transcriptionDuration,
                success: true,
              },
              userProfile?.email
            );

            chatInput.setInput(text);
          } else {
            logger.warn('No speech detected in audio', {
              component: 'ChatPage',
              action: 'transcribeAudio',
              metadata: { blobSize: audioBlob.size, duration: recordingTime },
            });

            chatInput.setInput('');
            setToast({
              message: 'No speech detected. Please speak clearly and try again.',
              type: 'error',
            });
          }
        } catch (error) {
          if (!isMountedRef.current) return;

          chatInput.setInput('');
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          logger.error(
            'Audio transcription failed',
            {
              component: 'ChatPage',
              action: 'transcribeAudio',
              metadata: { errorMessage },
            },
            error instanceof Error ? error : new Error(String(error))
          );

          if (errorMessage.includes('Unrecognized file format')) {
            setToast({
              message: 'Audio format not supported. Try a different browser.',
              type: 'error',
            });
          } else if (errorMessage.includes('400')) {
            setToast({ message: 'Invalid audio. Please try recording again.', type: 'error' });
          } else if (errorMessage.includes('401') || errorMessage.includes('403')) {
            setToast({ message: 'Authentication error. Please refresh the page.', type: 'error' });
          } else if (errorMessage.includes('413')) {
            setToast({
              message: 'Audio file too large. Please record a shorter message.',
              type: 'error',
            });
          } else if (errorMessage.includes('429')) {
            setToast({
              message: 'Too many requests. Please wait a moment and try again.',
              type: 'error',
            });
          } else if (errorMessage.includes('timeout')) {
            setToast({ message: 'Transcription timeout. Please try again.', type: 'error' });
          } else {
            setToast({ message: `Transcription failed: ${errorMessage}`, type: 'error' });
          }
        }
      }
    };
    processAudio();
  }, [audioBlob, audioMimeType, recordingTime, chatInput, isMountedRef]);

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
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Sidebar */}
      <ChatSidebar
        isOpen={sidebar.sidebarOpen}
        onClose={sidebar.closeSidebar}
        onNewChat={handleNewChat}
        onConversationClick={handleConversationClick}
        onDeleteConversation={handleDeleteConversation}
        onSearchDocsOpen={sidebar.openSearchDocs}
        conversations={conversations}
        currentConversationId={currentConversationId}
        isLoading={isConversationsLoading}
      />

      {/* Search Docs Modal */}
      <SearchDocsModal
        open={sidebar.isSearchDocsOpen}
        onClose={sidebar.closeSearchDocs}
        onInsert={(text) => {
          logger.debug('Text inserted from search docs', {
            component: 'ChatPage',
            action: 'searchDocsInsert',
            metadata: { textLength: text.length },
          });
          chatInput.setInput(chatInput.input ? `${chatInput.input}\n${text}` : text);
        }}
        initialQuery={chatInput.input}
      />

      {/* Image Generation Modal */}
      <ImageGenModal
        isOpen={false} // TODO: Add state for image gen modal
        onClose={() => {}}
        onSubmit={handleImageGenSubmit}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <ChatHeader
          isSidebarOpen={sidebar.sidebarOpen}
          onToggleSidebar={sidebar.toggleSidebar}
          isClockIn={isClockIn}
          isClockLoading={isClockLoading}
          onToggleClock={toggleClock}
          messagesCount={messages.length}
          isWsConnected={true}
          userName={userName}
          userAvatar={userAvatar}
          showUserMenu={false}
          onToggleUserMenu={() => {}}
          userMenuRef={fileInputRef}
          avatarInputRef={fileInputRef}
          onAvatarUpload={handleAvatarChange}
          onShowToast={(message, type) => setToast({ message, type })}
        />

        {/* Messages Area */}
        <ChatMessageList
          messages={messages}
          isLoading={false}
          thinkingElapsedTime={0}
          userAvatar={userAvatar}
          messagesEndRef={messagesEndRef}
          onFollowUpClick={(question) => {
            chatInput.setInput(question);
            setTimeout(() => handleSend(), 10);
          }}
          onSetInput={chatInput.setInput}
          onOpenSearchDocs={sidebar.openSearchDocs}
        />

        {/* Input Bar */}
        <ChatInputBar
          input={chatInput.input}
          setInput={chatInput.setInput}
          isLoading={false}
          showImagePrompt={false}
          setShowImagePrompt={() => {}}
          onSend={handleSend}
          onImageGenerate={() => {}}
          showAttachMenu={false}
          setShowAttachMenu={() => {}}
          attachMenuRef={chatInput.imageInputRef}
          fileInputRef={chatInput.imageInputRef}
          onFileChange={async (e) => {
            chatInput.handleImageAttach(e);
          }}
          isRecording={isRecording}
          recordingTime={recordingTime}
          onStartRecording={startRecording}
          onStopRecording={stopRecording}
          onToggleRecording={async () => {
            if (isRecording) {
              stopRecording();
            } else {
              try {
                await startRecording();
              } catch (error) {
                const errorMessage = error instanceof Error ? error.message : String(error);
                if (errorMessage.includes('Permission denied')) {
                  setToast({
                    message:
                      'Microphone access denied. Please allow microphone access in your browser settings.',
                    type: 'error',
                  });
                } else if (errorMessage.includes('NotFoundError')) {
                  setToast({
                    message: 'No microphone found. Please connect a microphone and try again.',
                    type: 'error',
                  });
                } else {
                  setToast({
                    message: 'Failed to access microphone. Please try again.',
                    type: 'error',
                  });
                }
              }
            }
          }}
        />
      </main>
    </div>
  );
}
