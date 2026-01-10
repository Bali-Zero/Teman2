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
  Sparkles,
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
  Volume2,
  VolumeX,
  Square,
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
import { logger } from '@/lib/logger';
import { useConversations } from '@/hooks/useConversations';
import { useTeamStatus } from '@/hooks/useTeamStatus';
import { useAudioRecorder } from '@/hooks/useAudioRecorder';
import { ThinkingIndicator } from '@/components/chat/ThinkingIndicator';
import { SearchDocsModal } from '@/components/search/SearchDocsModal';

// Server Actions & Types
import {
  saveConversation,
  type ChatMessage,
  type ChatImage,
  type Source,
} from './actions';

// Types
interface OptimisticMessage extends ChatMessage {
  isPending?: boolean;
  isStreaming?: boolean;
}

// Utilities
const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
const generateSessionId = () => `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

/**
 * Chat Page - Hybrid UI with full backend integration
 */
export default function ChatPage() {
  const router = useRouter();
  const isMountedRef = useRef(true);

  // Core state
  const [messages, setMessages] = useState<OptimisticMessage[]>([]);
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [currentStatus, setCurrentStatus] = useState<string>('');
  const [input, setInput] = useState('');
  const [thinkingElapsedTime, setThinkingElapsedTime] = useState(0);
  const [streamingSteps, setStreamingSteps] = useState<Array<{ type: string; data: unknown; timestamp: Date }>>([]);

  // UI state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userName, setUserName] = useState<string>('');
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isSearchDocsOpen, setIsSearchDocsOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [isImageGenOpen, setIsImageGenOpen] = useState(false);
  const [imageGenPrompt, setImageGenPrompt] = useState('');

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Image attachment state
  const [attachedImages, setAttachedImages] = useState<Array<{ id: string; base64: string; name: string; size: number }>>([]);

  // TTS (Text-to-Speech) state
  const [playingMessageId, setPlayingMessageId] = useState<string | null>(null);
  const [ttsLoading, setTtsLoading] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null); // Track audio URLs for cleanup

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
    toggleClock: originalToggleClock,
    loadClockStatus,
  } = useTeamStatus();

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
      logger.error('Clock status toggle failed', {
        component: 'ChatPage',
        action: 'toggleClock',
      }, error instanceof Error ? error : new Error(String(error)));
    }
  }, [isClockIn, originalToggleClock]);

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
    logger.debug('Loading user profile', {
      component: 'ChatPage',
      action: 'loadUserProfile',
    });
    
    try {
      const storedProfile = api.getUserProfile();
      if (storedProfile && isMountedRef.current) {
        setUserName(storedProfile.name || storedProfile.email.split('@')[0]);
        // Load avatar from profile if available
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
        // Load avatar from profile if available
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
        logger.error('Failed to load user profile', {
          component: 'ChatPage',
          action: 'loadUserProfile',
        }, error instanceof Error ? error : new Error(String(error)));
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    logger.componentMount('ChatPage', { component: 'ChatPage' });
    const userProfile = api.getUserProfile();
    
    return () => {
      isMountedRef.current = false;
      logger.componentUnmount('ChatPage', { component: 'ChatPage' });
    };
  }, [sessionId]);

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
          logger.error('Failed to load initial data', {
            component: 'ChatPage',
            action: 'loadInitialData',
          }, error instanceof Error ? error : new Error(String(error)));
        }
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
        logger.debug('Avatar loaded from localStorage', {
          component: 'ChatPage',
          action: 'loadAvatar',
        });
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

  // Cleanup streaming steps to prevent memory leak
  useEffect(() => {
    if (!isPending && streamingSteps.length > 10) {
      setStreamingSteps(prev => prev.slice(-10));
    }
  }, [isPending, streamingSteps.length]);

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
        showToast('Please select an image file', 'error');
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        logger.warn('Avatar file too large', {
          component: 'ChatPage',
          action: 'handleAvatarChange',
          metadata: { fileSize: file.size },
        });
        showToast('Image must be less than 5MB', 'error');
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
        showToast('Avatar updated', 'success');
      };
      reader.onerror = () => {
        logger.error('Failed to read avatar file', {
          component: 'ChatPage',
          action: 'handleAvatarChange',
        }, new Error('FileReader error'));
        showToast('Failed to read image file', 'error');
      };
      reader.readAsDataURL(file);
    }
  }, [showToast]);

  // Handle image attachment for chat
  const handleImageAttach = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    logger.debug('Image attachment started', {
      component: 'ChatPage',
      action: 'handleImageAttach',
      metadata: { fileCount: files.length, currentImageCount: attachedImages.length },
    });

    let attachedCount = 0;
    let totalSize = 0;
    
    Array.from(files).forEach(file => {
      if (!file.type.startsWith('image/')) {
        logger.warn('Invalid file type for image attachment', {
          component: 'ChatPage',
          action: 'handleImageAttach',
          metadata: { fileType: file.type, fileName: file.name },
        });
        showToast('Please select an image file', 'error');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        logger.warn('Image file too large', {
          component: 'ChatPage',
          action: 'handleImageAttach',
          metadata: { fileSize: file.size, fileName: file.name },
        });
        showToast('Image must be less than 10MB', 'error');
        return;
      }
      if (attachedImages.length + attachedCount >= 5) {
        logger.warn('Maximum images limit reached', {
          component: 'ChatPage',
          action: 'handleImageAttach',
          metadata: { currentCount: attachedImages.length, attemptCount: attachedCount },
        });
        showToast('Maximum 5 images allowed', 'error');
        return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result as string;
        setAttachedImages(prev => {
          const newImages = [
            ...prev,
            {
              id: `img_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
              base64: base64String,
              name: file.name,
              size: file.size,
            },
          ];
          logger.info('Image attached successfully', {
            component: 'ChatPage',
            action: 'handleImageAttach',
            metadata: { imageCount: newImages.length, fileName: file.name, fileSize: file.size },
          });
          return newImages;
        });
      };
      reader.onerror = () => {
        logger.error('Failed to read image file', {
          component: 'ChatPage',
          action: 'handleImageAttach',
          metadata: { fileName: file.name },
        }, new Error('FileReader error'));
        showToast('Failed to read image file', 'error');
      };
      reader.readAsDataURL(file);
      attachedCount++;
      totalSize += file.size;
    });

    // Reset input to allow selecting same file again
    e.target.value = '';
  }, [attachedImages.length, showToast]);

  // Remove attached image
  const removeAttachedImage = useCallback((imageId: string) => {
    logger.debug('Removing attached image', {
      component: 'ChatPage',
      action: 'removeAttachedImage',
      metadata: { imageId, currentCount: attachedImages.length },
    });
    setAttachedImages(prev => {
      const newImages = prev.filter(img => img.id !== imageId);
      return newImages;
    });
  }, [attachedImages.length]);

  // Handle image button clicks
  const handleImageButtonClick = useCallback(() => {
    imageInputRef.current?.click();
  }, []);

  // Handle screenshot/camera button (opens file picker for now)
  const handleScreenshotClick = useCallback(() => {
    imageInputRef.current?.click();
  }, []);

  // Handle image generation submit
  const handleImageGenSubmit = useCallback(() => {
    if (!imageGenPrompt.trim()) return;
    
    logger.info('Image generation requested', {
      component: 'ChatPage',
      action: 'handleImageGenSubmit',
      metadata: { promptLength: imageGenPrompt.trim().length },
    });
    
    
    // Set the input to the generation request and close modal
    setInput(`Genera un'immagine: ${imageGenPrompt.trim()}`);
    setImageGenPrompt('');
    setIsImageGenOpen(false);
    // Focus textarea to allow user to send
    setTimeout(() => {
      const textarea = document.querySelector('textarea');
      textarea?.focus();
    }, 100);
  }, [imageGenPrompt]);

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
  // Send Message with Streaming (Client-side API)
  // ============================================
  const handleSend = useCallback(async () => {
    const trimmedInput = input.trim();
    const hasImages = attachedImages.length > 0;

    // Allow sending if there's text OR images
    if ((!trimmedInput && !hasImages) || isPending) return;

    const userProfile = api.getUserProfile();
    const userId = userProfile?.email || 'anonymous';
    const messageStartTime = Date.now();

    // Capture images before clearing
    const imagesToSend = [...attachedImages];

    logger.info('Message send started', {
      component: 'ChatPage',
      action: 'handleSend',
      metadata: {
        sessionId,
        textLength: trimmedInput.length,
        hasImages: imagesToSend.length > 0,
        imageCount: imagesToSend.length,
        messageCount: messages.length,
      },
    });


    setInput('');
    setAttachedImages([]); // Clear images after capturing
    setStreamingSteps([]); // Clear steps for new message

    const userMessage: OptimisticMessage = {
      id: generateId(),
      role: 'user',
      content: trimmedInput || (hasImages ? '[Image attached]' : ''),
      images: imagesToSend.length > 0 ? imagesToSend : undefined,
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

    // Build conversation history for context
    const conversationHistory = newMessages
      .filter(m => !m.isStreaming)
      .map(m => ({ role: m.role, content: m.content }));

    // Track accumulated content for streaming
    let accumulatedContent = '';

    try {
      // Use client-side API with callbacks (fixes Server Action stream issue)
      await api.sendMessageStreaming(
        trimmedInput || '[Image attached]',
        sessionId,
        // onChunk - called for each token
        (chunk: string) => {
          accumulatedContent = chunk; // API already accumulates
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMessage.id
                ? { ...m, content: chunk, isPending: false }
                : m
            )
          );
        },
        // onDone - called when complete
        (fullResponse, sources, metadata) => {
          const messageDuration = Date.now() - messageStartTime;
          
          // Handle generated image from metadata (cast to access generated_image)
          const typedMeta = metadata as {
            generated_image?: string;
            followup_questions?: string[];
            execution_time?: number;
            route_used?: string;
          } | undefined;
          const imageUrl = typedMeta?.generated_image;
          const followupQuestions = typedMeta?.followup_questions;
          const executionTime = typedMeta?.execution_time || messageDuration / 1000;

          logger.info('Message received successfully', {
            component: 'ChatPage',
            action: 'handleSend',
            metadata: {
              sessionId,
              responseLength: fullResponse.length,
              executionTime,
              routeUsed: typedMeta?.route_used,
              hasSources: (sources?.length || 0) > 0,
              sourceCount: sources?.length || 0,
              hasGeneratedImage: !!imageUrl,
              hasFollowupQuestions: (followupQuestions?.length || 0) > 0,
              totalDuration: messageDuration,
            },
          });

          // Track metric for received message
          const { trackEvent } = require('@/lib/analytics');
          trackEvent('chat_message_received', {
            sessionId,
            responseLength: fullResponse.length,
            executionTime,
            routeUsed: typedMeta?.route_used,
            hasSources: (sources?.length || 0) > 0,
            sourceCount: sources?.length || 0,
            hasGeneratedImage: !!imageUrl,
          }, userId);

          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMessage.id
                ? {
                    ...m,
                    content: fullResponse,
                    sources: sources as Source[],
                    isStreaming: false,
                    isPending: false,
                    // Add imageUrl if image was generated
                    ...(imageUrl ? { imageUrl } : {}),
                    // Add follow-up questions for proactivity
                    ...(followupQuestions && followupQuestions.length > 0
                      ? { metadata: { followup_questions: followupQuestions } }
                      : {})
                  }
                : m
            )
          );
          setCurrentStatus('');

          // Save conversation
          startTransition(async () => {
            try {
              logger.debug('Saving conversation', {
                component: 'ChatPage',
                action: 'saveConversation',
                metadata: { sessionId, messageCount: newMessages.length },
              });
              
              await saveConversation(
                newMessages.filter(m => !m.isStreaming).map(m => ({
                  ...m,
                  content: m.id === assistantMessage.id ? fullResponse : m.content
                })),
                sessionId
              );
              
              logger.info('Conversation saved successfully', {
                component: 'ChatPage',
                action: 'saveConversation',
                metadata: { sessionId, messageCount: newMessages.length },
              });

              trackEvent('chat_conversation_saved', {
                sessionId,
                messageCount: newMessages.length
              }, userId);
              
            } catch (error) {
              logger.error('Failed to save conversation', {
                component: 'ChatPage',
                action: 'saveConversation',
                metadata: { sessionId },
              }, error instanceof Error ? error : new Error(String(error)));
            }
          });
        },
        // onError - called on error
        (error: Error) => {
          const errorType = error instanceof Error ? error.name : 'Unknown';
          const errorMessage = error instanceof Error ? error.message : String(error);
          
          logger.error('Message send error', {
            component: 'ChatPage',
            action: 'handleSend',
            metadata: {
              sessionId,
              errorType,
              errorMessage,
              hasImages: imagesToSend.length > 0,
              messageLength: trimmedInput.length,
            },
          }, error instanceof Error ? error : new Error(String(error)));


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
        },
        // onStep - called for all step events (thinking, tool_call, observation, status)
        (step) => {
          // Track all steps for progress visualization
          setStreamingSteps(prev => [...prev, step]);
          // Update status text for display
          if (step.type === 'status' && typeof step.data === 'string') {
            setCurrentStatus(step.data);
          }
        },
        120000, // timeoutMs
        conversationHistory, // conversation history for context
        undefined, // abortSignal
        undefined, // correlationId
        60000, // idleTimeoutMs
        600000, // maxTotalTimeMs
        // Transform images for vision: extract base64 and name only
        imagesToSend.length > 0
          ? imagesToSend.map(img => ({
              base64: img.base64.replace(/^data:image\/[^;]+;base64,/, ''), // Remove data URL prefix
              name: img.name
            }))
          : undefined
      );

    } catch (error) {
      logger.error('Message send failed', {
        component: 'ChatPage',
        action: 'handleSend',
        metadata: {
          sessionId,
          hasImages: imagesToSend.length > 0,
          messageLength: trimmedInput.length,
        },
      }, error instanceof Error ? error : new Error(String(error)));
      
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
      setStreamingSteps([]);
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      showToast(`Failed to send message: ${errorMessage}`, 'error');
    }
  }, [input, isPending, messages, sessionId, addOptimisticMessage, showToast, attachedImages]);

  // ============================================
  // Conversation Management
  // ============================================
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
    setMessages([]);
    setCurrentStatus('');
    setSessionId(newSessionId);
    setCurrentConversationId(null);
    setSidebarOpen(false);
    
  }, [setCurrentConversationId, sessionId]);

  const handleConversationClick = useCallback(
    async (id: number) => {
      logger.debug('Loading conversation', {
        component: 'ChatPage',
        action: 'handleConversationClick',
        metadata: { conversationId: id },
      });
      
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
          
          logger.info('Conversation loaded successfully', {
            component: 'ChatPage',
            action: 'handleConversationClick',
            metadata: { conversationId: id, messageCount: conv.messages.length, sessionId: conv.session_id },
          });

          const { trackEvent } = require('@/lib/analytics');
          const userProfile = api.getUserProfile();
          trackEvent('chat_conversation_loaded', { conversationId: id, messageCount: conv.messages.length }, userProfile?.email);
          
        }
      } catch (error) {
        logger.error('Failed to load conversation', {
          component: 'ChatPage',
          action: 'handleConversationClick',
          metadata: { conversationId: id },
        }, error instanceof Error ? error : new Error(String(error)));
        
      }
      if (window.innerWidth < 768) setSidebarOpen(false);
    },
    [setCurrentConversationId]
  );

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
        logger.error('Failed to delete conversation', {
          component: 'ChatPage',
          action: 'handleDeleteConversation',
          metadata: { conversationId: id },
        }, error instanceof Error ? error : new Error(String(error)));
        
      }
    },
    [deleteConversation, currentConversationId, handleNewChat]
  );

  // ============================================
  // Audio Recording
  // ============================================
  const handleMicClick = useCallback(async () => {
    if (isRecording) {
      logger.info('Audio recording stopped', {
        component: 'ChatPage',
        action: 'handleMicClick',
        metadata: { recordingTime, mimeType: audioMimeType },
      });
      
      const { trackEvent } = require('@/lib/analytics');
      const userProfile = api.getUserProfile();
      trackEvent('chat_audio_recording_stopped', { duration: recordingTime, mimeType: audioMimeType }, userProfile?.email);

      stopRecording();
      
    } else {
      logger.info('Audio recording started', {
        component: 'ChatPage',
        action: 'handleMicClick',
      });

      const { trackEvent } = require('@/lib/analytics');
      const userProfile = api.getUserProfile();
      trackEvent('chat_audio_recording_started', {}, userProfile?.email);
      
      try {
        await startRecording();
      } catch (error) {
        // Handle different error types for better UX
        const errorMessage = error instanceof Error ? error.message : String(error);
        const errorType = error instanceof Error ? error.name : 'Unknown';
        
        logger.error('Audio recording failed', {
          component: 'ChatPage',
          action: 'handleMicClick',
          metadata: { errorType, errorMessage },
        }, error instanceof Error ? error : new Error(String(error)));
        
        
        if (errorMessage.includes('Permission denied') || errorMessage.includes('NotAllowedError')) {
          showToast('Microphone access denied. Please allow microphone access in your browser settings.', 'error');
        } else if (errorMessage.includes('NotFoundError') || errorMessage.includes('no microphone')) {
          showToast('No microphone found. Please connect a microphone and try again.', 'error');
        } else if (errorMessage.includes('NotReadableError') || errorMessage.includes('could not start')) {
          showToast('Microphone is already in use. Please close other applications using the microphone.', 'error');
        } else if (errorMessage.includes('OverconstrainedError') || errorMessage.includes('constraint')) {
          showToast('Microphone constraints not supported. Try a different browser.', 'error');
        } else {
          showToast('Failed to access microphone. Please try again.', 'error');
        }
      }
    }
  }, [isRecording, startRecording, stopRecording, showToast, recordingTime, audioMimeType]);

  // Audio transcription
  useEffect(() => {
    const processAudio = async () => {
      if (audioBlob && isMountedRef.current) {
        try {
          // Validate audio blob before sending
          if (audioBlob.size < 1000) {
            setInput('');
            showToast('Recording too short. Please hold the mic button longer.', 'error');
            return;
          }

          // Additional validation: check if blob is actually audio
          if (!audioBlob.type.startsWith('audio/') && !audioMimeType.startsWith('audio/')) {
            setInput('');
            showToast('Invalid audio format. Please try recording again.', 'error');
            return;
          }

          logger.debug('Processing audio blob', {
            component: 'ChatPage',
            action: 'transcribeAudio',
            metadata: { blobSize: audioBlob.size, mimeType: audioMimeType },
          });
          setInput('Transcribing...');

          const transcriptionStartTime = Date.now();
          const text = await api.transcribeAudio(audioBlob, audioMimeType);
          const transcriptionDuration = Date.now() - transcriptionStartTime;
          
          if (!isMountedRef.current) return; // Check if component is still mounted
          
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
            trackEvent('chat_audio_transcribed', {
              blobSize: audioBlob.size,
              textLength: text.length,
              duration: transcriptionDuration,
              success: true
            }, userProfile?.email);

            setInput(text);
          } else {
            logger.warn('No speech detected in audio', {
              component: 'ChatPage',
              action: 'transcribeAudio',
              metadata: { blobSize: audioBlob.size, duration: recordingTime },
            });
            
            
            setInput('');
            showToast('No speech detected. Please speak clearly and try again.', 'error');
          }
        } catch (error) {
          if (!isMountedRef.current) return; // Check if component is still mounted
          
          setInput('');
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          logger.error('Audio transcription failed', {
            component: 'ChatPage',
            action: 'transcribeAudio',
            metadata: { errorMessage },
          }, error instanceof Error ? error : new Error(String(error)));

          // Provide specific error messages
          if (errorMessage.includes('Unrecognized file format') || errorMessage.includes('format not supported')) {
            showToast('Audio format not supported. Try a different browser.', 'error');
          } else if (errorMessage.includes('400') || errorMessage.includes('Bad Request')) {
            showToast('Invalid audio. Please try recording again.', 'error');
          } else if (errorMessage.includes('401') || errorMessage.includes('403') || errorMessage.includes('Unauthorized')) {
            showToast('Authentication error. Please refresh the page.', 'error');
          } else if (errorMessage.includes('413') || errorMessage.includes('too large')) {
            showToast('Audio file too large. Please record a shorter message.', 'error');
          } else if (errorMessage.includes('429') || errorMessage.includes('rate limit')) {
            showToast('Too many requests. Please wait a moment and try again.', 'error');
          } else if (errorMessage.includes('timeout') || errorMessage.includes('Timeout')) {
            showToast('Transcription timeout. Please try again.', 'error');
          } else {
            showToast(`Transcription failed: ${errorMessage}`, 'error');
          }
        }
      }
    };
    processAudio();
  }, [audioBlob, audioMimeType, showToast]);

  // ============================================
  // Text-to-Speech (TTS)
  // ============================================
  const handleTTS = useCallback(async (messageId: string, text: string) => {
    // If already playing this message, stop it
    if (playingMessageId === messageId) {
      logger.debug('TTS stopped (already playing)', {
        component: 'ChatPage',
        action: 'handleTTS',
        metadata: { messageId },
      });
      
      // Cleanup current audio
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = ''; // Clear src to stop playback
        audioRef.current = null;
      }
      // Revoke URL if exists
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      setPlayingMessageId(null);
      return;
    }

    logger.info('TTS started', {
      component: 'ChatPage',
      action: 'handleTTS',
      metadata: { messageId, textLength: text.length, voice: 'nova' },
    });

    // Stop any currently playing audio and cleanup
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = ''; // Clear src to stop playback
      audioRef.current = null;
    }
    // Revoke previous URL if exists
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }

    const ttsStartTime = Date.now();
    try {
      setTtsLoading(messageId);
      const audioBlob = await api.generateSpeech(text, 'nova');

      // Validate audio blob
      if (!audioBlob || audioBlob.size === 0) {
        throw new Error('Invalid audio blob received');
      }

      const audioUrl = URL.createObjectURL(audioBlob);
      audioUrlRef.current = audioUrl; // Track URL for cleanup
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      // Remove old event listeners if they exist (defensive)
      audio.onended = () => {
        if (audioUrlRef.current === audioUrl) {
          const ttsDuration = Date.now() - ttsStartTime;
          logger.info('TTS completed', {
            component: 'ChatPage',
            action: 'handleTTS',
            metadata: { messageId, duration: ttsDuration },
          });

          const { trackEvent } = require('@/lib/analytics');
          const userProfile = api.getUserProfile();
          trackEvent('chat_tts_completed', { messageId, duration: ttsDuration }, userProfile?.email);

          setPlayingMessageId(null);
          URL.revokeObjectURL(audioUrl);
          audioUrlRef.current = null;
          audioRef.current = null;
        }
      };

      audio.onerror = (e) => {
        const errorMessage = e instanceof Error ? e.message : 'Unknown playback error';
        logger.error('TTS audio playback error', {
          component: 'ChatPage',
          action: 'handleTTS',
          metadata: { messageId, errorMessage },
        }, e instanceof Error ? e : new Error(String(e)));

        if (audioUrlRef.current === audioUrl) {
          const { trackEvent } = require('@/lib/analytics');
          const userProfile = api.getUserProfile();
          trackEvent('chat_tts_error', { messageId, errorType: 'playback', errorMessage }, userProfile?.email);

          showToast('Audio playback failed', 'error');
          setPlayingMessageId(null);
          URL.revokeObjectURL(audioUrl);
          audioUrlRef.current = null;
          audioRef.current = null;
        }
      };

      // Handle play promise rejection
      try {
        setTtsLoading(null);
        setPlayingMessageId(messageId);
        await audio.play();
        
        const { trackEvent } = require('@/lib/analytics');
        const userProfile = api.getUserProfile();
        trackEvent('chat_tts_started', { messageId, textLength: text.length }, userProfile?.email);
      } catch (playError) {
        const errorMessage = playError instanceof Error ? playError.message : 'Unknown play error';
        logger.error('TTS audio play error', {
          component: 'ChatPage',
          action: 'handleTTS',
          metadata: { messageId, errorType: playError instanceof Error ? playError.name : 'Unknown' },
        }, playError instanceof Error ? playError : new Error(String(playError)));

        const { trackEvent } = require('@/lib/analytics');
        const userProfile = api.getUserProfile();
        trackEvent('chat_tts_error', { messageId, errorType: 'play', errorMessage }, userProfile?.email);

        // Cleanup on play failure
        URL.revokeObjectURL(audioUrl);
        audioUrlRef.current = null;
        audioRef.current = null;
        setTtsLoading(null);
        setPlayingMessageId(null);
        showToast('Failed to play audio. Please try again.', 'error');
      }
    } catch (error) {
      // Cleanup on generation failure
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      audioRef.current = null;
      setTtsLoading(null);
      setPlayingMessageId(null);
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      const errorType = error instanceof Error ? error.name : 'Unknown';
      
      logger.error('TTS generation failed', {
        component: 'ChatPage',
        action: 'handleTTS',
        metadata: { messageId, errorType, errorMessage },
      }, error instanceof Error ? error : new Error(String(error)));

      if (errorMessage.includes('timeout') || errorMessage.includes('Timeout')) {
        showToast('TTS generation timeout. Please try again.', 'error');
      } else if (errorMessage.includes('429') || errorMessage.includes('rate limit')) {
        showToast('Too many TTS requests. Please wait a moment.', 'error');
      } else {
        showToast('TTS generation failed. Please try again.', 'error');
      }
    }
  }, [playingMessageId, showToast]);

  // ============================================
  // UI Interactions
  // ============================================
  const handleSidebarOpen = useCallback(() => {
    logger.debug('Sidebar opened', {
      component: 'ChatPage',
      action: 'handleSidebarOpen',
    });
    
    const { trackEvent } = require('@/lib/analytics');
    const userProfile = api.getUserProfile();
    trackEvent('chat_sidebar_opened', {}, userProfile?.email);

    setSidebarOpen(true);
  }, []);

  const handleSidebarClose = useCallback(() => {
    logger.debug('Sidebar closed', {
      component: 'ChatPage',
      action: 'handleSidebarClose',
    });
    
    const { trackEvent } = require('@/lib/analytics');
    const userProfile = api.getUserProfile();
    trackEvent('chat_sidebar_closed', {}, userProfile?.email);

    setSidebarOpen(false);
  }, []);

  const handleSearchDocsOpen = useCallback(() => {
    logger.info('Search docs opened', {
      component: 'ChatPage',
      action: 'handleSearchDocsOpen',
      metadata: { hasInput: !!input, inputLength: input.length },
    });
    
    const { trackEvent } = require('@/lib/analytics');
    const userProfile = api.getUserProfile();
    trackEvent('chat_search_docs_opened', { inputLength: input.length }, userProfile?.email);

    setIsSearchDocsOpen(true);
  }, [input]);

  const handleSearchDocsClose = useCallback(() => {
    logger.debug('Search docs closed', {
      component: 'ChatPage',
      action: 'handleSearchDocsClose',
    });
    
    setIsSearchDocsOpen(false);
  }, []);

  // Cleanup audio and URLs on unmount
  useEffect(() => {
    return () => {
      // Stop and cleanup audio element
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = ''; // Clear src
        audioRef.current = null;
      }
      // Revoke any pending URLs
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, []);

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

      {/* Hidden file input for chat image attachments */}
      <input
        type="file"
        ref={imageInputRef}
        onChange={handleImageAttach}
        accept="image/*"
        multiple
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
          onClick={handleSidebarClose}
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
                src="/assets/logo/logo_zan.png"
                alt="Zantara"
                width={32}
                height={32}
                className="drop-shadow-[0_0_12px_rgba(255,255,255,0.3)]"
              />
              <span className="font-medium text-white/90">Zantara</span>
            </div>
            <button
              onClick={handleSidebarClose}
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
              onClick={handleSearchDocsOpen}
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
        onClose={handleSearchDocsClose}
        onInsert={(text) => {
          logger.debug('Text inserted from search docs', {
            component: 'ChatPage',
            action: 'searchDocsInsert',
            metadata: { textLength: text.length },
          });
          setInput((prev) => (prev ? `${prev}\n${text}` : text));
        }}
        initialQuery={input}
      />

      {/* Image Generation Modal */}
      {isImageGenOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#2a2a2a] rounded-2xl border border-white/10 shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="text-white font-semibold">Genera Immagine</h3>
                  <p className="text-xs text-gray-400">Descrivi cosa vuoi creare</p>
                </div>
              </div>
              <button
                onClick={() => setIsImageGenOpen(false)}
                className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="p-5">
              <textarea
                value={imageGenPrompt}
                onChange={(e) => setImageGenPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleImageGenSubmit();
                  }
                }}
                placeholder="Es: Un unicorno magico in una foresta incantata..."
                className="w-full h-28 px-4 py-3 bg-[#1a1a1a] border border-white/10 rounded-xl text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none"
                autoFocus
              />
              <div className="mt-4 flex justify-end gap-3">
                <button
                  onClick={() => setIsImageGenOpen(false)}
                  className="px-4 py-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                >
                  Annulla
                </button>
                <button
                  onClick={handleImageGenSubmit}
                  disabled={!imageGenPrompt.trim()}
                  className="px-5 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  Genera
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <header className="h-14 border-b border-white/5 bg-[#202020] flex-shrink-0">
          <div className="h-full max-w-4xl mx-auto px-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={handleSidebarOpen}
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
                src="/assets/logo/logo_zan.png"
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
                  src="/assets/logo/logo_zan.png"
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
                        handleSearchDocsOpen();
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
              {optimisticMessages.map((message) => {
                // Show ThinkingIndicator for streaming assistant messages without content
                if (message.role === 'assistant' && message.isStreaming && !message.content) {
                  return (
                    <ThinkingIndicator
                      key={message.id}
                      isVisible={true}
                      currentStatus={currentStatus}
                      elapsedTime={thinkingElapsedTime}
                      steps={streamingSteps as Array<{ type: string; data: unknown; timestamp: Date }>}
                      maxSteps={3}
                    />
                  );
                }

                return (
                <div key={message.id} className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {message.role === 'assistant' && (
                    <div className="relative flex-shrink-0">
                      <Image
                        src="/assets/logo/logo_zan.png"
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
                      {/* Display attached images for user messages */}
                      {message.role === 'user' && message.images && message.images.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-2">
                          {message.images.map((img) => (
                            <Image
                              key={img.id}
                              src={img.base64}
                              alt={img.name}
                              width={120}
                              height={120}
                              className="w-32 h-32 object-cover rounded-lg border border-white/10"
                            />
                          ))}
                        </div>
                      )}
                      <div className="text-sm whitespace-pre-wrap leading-relaxed text-gray-100">
                        {message.content.split('**').map((part, i) =>
                          i % 2 === 1 ? <strong key={i} className="text-white">{part}</strong> : part
                        )}
                      </div>

                      {/* Generated image from image generation tool */}
                      {message.imageUrl && (
                        <div className="mt-3 relative rounded-lg overflow-hidden border border-white/10">
                          <Image
                            src={message.imageUrl}
                            alt="Generated content"
                            width={512}
                            height={512}
                            className="w-full h-auto max-w-md"
                            unoptimized
                          />
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
                          title="Copy to clipboard"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleTTS(message.id, message.content)}
                          className={`p-1.5 hover:bg-white/5 rounded transition-colors ${
                            playingMessageId === message.id
                              ? 'text-emerald-400 bg-emerald-400/10'
                              : 'text-gray-500 hover:text-gray-300'
                          }`}
                          title={playingMessageId === message.id ? 'Stop speaking' : 'Read aloud'}
                          disabled={ttsLoading === message.id}
                        >
                          {(() => {
                            if (ttsLoading === message.id) {
                              return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
                            }
                            if (playingMessageId === message.id) {
                              return <Square className="w-3.5 h-3.5" />;
                            }
                            return <Volume2 className="w-3.5 h-3.5" />;
                          })()}
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

                    {/* Follow-up Questions - Proactive Suggestions */}
                    {message.role === 'assistant' && !message.isStreaming && message.metadata?.followup_questions && message.metadata.followup_questions.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-white/5">
                        <div className="flex items-center gap-2 mb-2">
                          <Sparkles className="w-3 h-3 text-purple-400" />
                          <span className="text-xs text-gray-500 uppercase tracking-wide">Domande suggerite</span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {message.metadata.followup_questions.map((question, idx) => (
                            <button
                              key={idx}
                              onClick={() => {
                                setInput(question);
                                setTimeout(() => handleSend(), 10);
                              }}
                              className="px-3 py-1.5 text-xs rounded-lg border border-white/10 text-gray-400 hover:text-white hover:border-purple-500/50 hover:bg-purple-500/10 transition-all"
                            >
                              {question}
                            </button>
                          ))}
                        </div>
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
                );
              })}
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
                  <button
                    onClick={handleImageButtonClick}
                    title="Attach file or image"
                    className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all"
                  >
                    <Paperclip className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setIsImageGenOpen(true)}
                    title="Generate image with AI"
                    className="p-2 rounded-lg text-gray-400 hover:text-purple-400 hover:bg-purple-500/10 transition-all"
                  >
                    <Sparkles className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleMicClick}
                    title="Voice input"
                    className={`p-2 rounded-lg transition-all ${
                      isRecording ? 'text-red-400 bg-red-500/10 animate-pulse' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                    }`}
                  >
                    <Mic className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleScreenshotClick}
                    title="Add screenshot"
                    className="p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all"
                  >
                    <Camera className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  {isRecording && (
                    <span className="text-xs text-red-400">{recordingTime}s</span>
                  )}
                  <div className="w-1.5 h-1.5 rounded-full bg-green-500" title="Online" />
                </div>
              </div>

              {/* Image Preview Area */}
              {attachedImages.length > 0 && (
                <div className="px-3 py-2 border-b border-white/[0.06]">
                  <div className="flex flex-wrap gap-2">
                    {attachedImages.map((img) => (
                      <div key={img.id} className="relative group">
                        <Image
                          src={img.base64}
                          alt={img.name}
                          width={80}
                          height={80}
                          className="w-20 h-20 object-cover rounded-lg border border-white/10"
                        />
                        <button
                          onClick={() => removeAttachedImage(img.id)}
                          className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X className="w-3 h-3 text-white" />
                        </button>
                        <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-[10px] text-gray-300 px-1 py-0.5 rounded-b-lg truncate">
                          {img.name.length > 12 ? img.name.slice(0, 12) + '...' : img.name}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-end gap-3 p-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={attachedImages.length > 0 ? "Add a message about this image..." : "Ask Zantara anything..."}
                  rows={1}
                  disabled={isPending}
                  className="flex-1 bg-transparent border-none outline-none shadow-none focus:outline-none focus:ring-0 focus:border-none focus:shadow-none resize-none min-h-[44px] max-h-[120px] py-2.5 text-sm text-white placeholder:text-gray-500 disabled:opacity-50"
                  style={{ boxShadow: 'none', border: 'none', outline: 'none' }}
                />
                <button
                  onClick={handleSend}
                  disabled={(!input.trim() && attachedImages.length === 0) || isPending}
                  className={`p-2.5 rounded-xl transition-all ${
                    (input.trim() || attachedImages.length > 0) && !isPending
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

    </div>
  );
}
