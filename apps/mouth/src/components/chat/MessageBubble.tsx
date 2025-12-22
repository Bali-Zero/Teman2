'use client';

import React, { useState, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  User,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  BrainCircuit,
  ShieldCheck,
  ShieldAlert,
  Shield,
  Zap,
  Clock,
  Database,
  Sparkles,
  HeartHandshake,
  HelpCircle,
  BookOpen,
} from 'lucide-react';
import { CitationCard } from '@/components/CitationCard';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';

import { formatMessageTime } from '@/lib/utils';
import { Message } from '@/types';
import { PricingTable } from './PricingTable';
import { PricingResponse } from '@/types/pricing';
import { TIMEOUTS, ANIMATION } from '@/constants';

interface MessageBubbleProps {
  message: Message;
  userAvatar?: string | null;
}

const VerificationBadge = ({ score }: { score: number }) => {
  let colorClass = 'text-[var(--error)] border-[var(--error)]/30 bg-[var(--error)]/10';
  let icon = <ShieldAlert className="w-3 h-3" />;
  let label = 'Low Confidence';

  if (score >= 80) {
    colorClass = 'text-[var(--success)] border-[var(--success)]/30 bg-[var(--success)]/10';
    icon = <ShieldCheck className="w-3 h-3" />;
    label = 'Verified';
  } else if (score >= 50) {
    colorClass = 'text-[var(--warning)] border-[var(--warning)]/30 bg-[var(--warning)]/10';
    icon = <Shield className="w-3 h-3" />;
    label = 'Medium Confidence';
  }

  return (
    <div
      className={`
      inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
      text-[10px] font-medium border ${colorClass}
      mt-2 select-none
    `}
    >
      {icon}
      <span>
        {label} ({score}%)
      </span>
    </div>
  );
};

const TrustHeader = ({ metadata }: { metadata: NonNullable<Message['metadata']> }) => {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[10px] font-medium text-[var(--foreground-muted)] mb-3 select-none">
      {metadata.route_used && (
        <div className="flex items-center gap-1 bg-[var(--background-secondary)] px-1.5 py-0.5 rounded border border-[var(--border)]">
          <Zap
            size={10}
            className={metadata.route_used.includes('deep') ? 'text-purple-400' : 'text-blue-400'}
          />
          <span>
            {metadata.route_used.toLowerCase().includes('fast')
              ? 'FAST (ZAN 1.2)'
              : metadata.route_used.toLowerCase().includes('pro')
                ? 'PRO (ZAN 1.2)'
                : metadata.route_used.toLowerCase().includes('deep')
                  ? 'ULTRA (ZAN 1.2)'
                  : metadata.route_used.toUpperCase()}
          </span>
        </div>
      )}
      {metadata.execution_time && (
        <div className="flex items-center gap-1 px-1.5 py-0.5">
          <Clock size={10} />
          <span>{metadata.execution_time.toFixed(1)}s</span>
        </div>
      )}
      {metadata.context_length && (
        <div className="flex items-center gap-1 px-1.5 py-0.5">
          <Database size={10} />
          <span>{Math.round(metadata.context_length / 100) / 10}k ctx</span>
        </div>
      )}
    </div>
  );
};

const EmotionalBadge = ({ emotion }: { emotion: string }) => {
  if (emotion === 'NEUTRAL') return null;

  // Map emotions to colors/icons
  const config: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
    URGENT: {
      color: 'text-red-400 bg-red-400/10 border-red-400/20',
      icon: <Zap size={12} />,
      label: 'Priority Mode',
    },
    CONFUSED: {
      color: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
      icon: <HelpCircle size={12} />,
      label: 'Simplified Explanation',
    }, // BreastCheck is not a valid icon, using HelpCircle like or similar
    STRESSED: {
      color: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
      icon: <HeartHandshake size={12} />,
      label: 'Supportive Tone',
    },
    EXCITED: {
      color: 'text-green-400 bg-green-400/10 border-green-400/20',
      icon: <Sparkles size={12} />,
      label: 'Enthusiastic',
    },
  };

  const defaultConf = {
    color: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
    icon: <Sparkles size={12} />,
    label: emotion,
  };
  const { color, icon, label } = config[emotion] || defaultConf;

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wider font-semibold border ${color} mb-2`}
    >
      {icon}
      <span>{label}</span>
    </div>
  );
};

function MessageBubbleComponent({ message, userAvatar }: MessageBubbleProps) {
  const { role, content, sources, imageUrl, timestamp, steps, verification_score } = message;
  const isUser = role === 'user';
  const [copied, setCopied] = useState(false);
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(false);
  const copyTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  React.useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    if (copyTimeoutRef.current) {
      clearTimeout(copyTimeoutRef.current);
    }
    copyTimeoutRef.current = setTimeout(() => {
      setCopied(false);
      copyTimeoutRef.current = null;
    }, TIMEOUTS.COPY_FEEDBACK);
  };

  // Function to extract pricing data from tool steps
  const getPricingData = (): PricingResponse | null => {
    if (!message.steps) return null;

    // Look for get_pricing tool output in steps
    // We reverse to get the latest one if multiple exist
    const toolStep = [...message.steps]
      .reverse()
      .find(
        (step) =>
          step.type === 'tool_end' &&
          step.data.result &&
          (step.data.result.includes('official_notice') ||
            step.data.result.includes('single_entry_visas'))
      );

    if (toolStep && toolStep.type === 'tool_end') {
      try {
        const data = JSON.parse(toolStep.data.result);
        if (data.success && data.data) {
          return data.data as PricingResponse;
        }
        // Handle cases where result is directly the data or wrapped differently
        if (data.official_notice || data.single_entry_visas) {
          return data as PricingResponse;
        }
      } catch {
        // Failed to parse, ignore
      }
    }
    return null;
  };

  const pricingData = getPricingData();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: ANIMATION.FRAMER_DEFAULT, ease: 'easeOut' }}
      className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6 group`}
    >
      <div
        className={`flex max-w-[85%] md:max-w-[75%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
      >
        {/* Avatar */}
        <div
          className={`
          flex-shrink-0 flex items-center justify-center
          ${
            isUser
              ? 'w-8 h-8 rounded-full shadow-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)]'
              : 'w-14 h-14 -ml-2' // Much larger, negative margin to compensate visual weight
          }
        `}
        >
          {isUser ? (
            userAvatar ? (
              <div className="relative w-full h-full rounded-full overflow-hidden">
                <Image src={userAvatar} alt="User" fill className="object-cover" />
              </div>
            ) : (
              <User size={16} />
            )
          ) : (
            <div className="relative w-full h-full"> 
              <Image 
                src="/images/logo_zan.png" 
                alt="Zantara" 
                fill 
                className="object-contain brightness-125 drop-shadow-[0_0_15px_rgba(255,255,255,0.3)] scale-125" 
              />
            </div>
          )}
        </div>

        {/* Message Content */}
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} min-w-0`}>
          <div
            className={`
            relative px-5 py-3.5 rounded-2xl shadow-sm text-sm leading-relaxed
            ${
              isUser
                ? 'bg-[var(--background-secondary)] text-[var(--foreground)] rounded-tr-sm'
                : 'bg-[var(--background-elevated)] text-[var(--foreground)] rounded-tl-sm border border-[var(--border)]/50'
            }
          `}
          >
            {/* Trust Header & Emotional Badge */}
            {!isUser && message.metadata && <TrustHeader metadata={message.metadata} />}
            {!isUser && message.metadata?.emotional_state && (
              <EmotionalBadge emotion={message.metadata.emotional_state} />
            )}

            {/* Thinking Process (for AI) */}
            {!isUser && (steps?.length ?? 0) > 0 && (
              <div className="mb-3">
                <button
                  onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
                  className="flex items-center gap-2 text-xs font-medium text-[var(--foreground-muted)] hover:text-[var(--accent)] transition-colors mb-2"
                >
                  <BrainCircuit className="w-3.5 h-3.5" />
                  <span>Thinking Process</span>
                  {isThinkingExpanded ? (
                    <ChevronDown className="w-3 h-3" />
                  ) : (
                    <ChevronRight className="w-3 h-3" />
                  )}
                </button>

                <AnimatePresence>
                  {isThinkingExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="pl-3 border-l-2 border-[var(--border)] space-y-2 py-1">
                        {steps?.map((step, idx) => (
                          <div key={idx} className="text-xs text-[var(--foreground-secondary)]">
                            <span className="opacity-70 mr-1">{idx + 1}.</span>
                            {step.type === 'status' && <span>{step.data}</span>}

                            {/* STANDARD TOOLS */}
                            {step.type === 'tool_start' && step.data.name !== 'database_query' && (
                              <span className="text-blue-400">
                                Using tool: <strong>{step.data.name}</strong>
                              </span>
                            )}

                            {/* DEEP DIVE (DATABASE QUERY) - SPECIAL RENDERING */}
                            {step.type === 'tool_start' && step.data.name === 'database_query' && (
                              <span className="text-indigo-400 flex items-center gap-1.5 font-medium">
                                <BookOpen size={12} />
                                <span>Deep Reading Document...</span>
                              </span>
                            )}

                            {step.type === 'tool_end' && (
                              <span className="text-emerald-400">Tool Completed</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

            {/* Main Text Content */}
            <div className="prose prose-invert prose-sm max-w-none break-words">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>

            {/* Verification Badge */}
            {!isUser && verification_score !== undefined && (
              <VerificationBadge score={verification_score} />
            )}

            {/* Pricing Table */}
            {!isUser && pricingData && <PricingTable data={pricingData} />}

            {/* Sources */}
            {!isUser && sources && sources.length > 0 && <CitationCard sources={sources} />}

            {/* Image */}
            {imageUrl && (
              <div className="mt-3 relative rounded-lg overflow-hidden border border-[var(--border)]">
                <Image
                  src={imageUrl}
                  alt="Generated content"
                  width={512}
                  height={512}
                  className="w-full h-auto"
                  unoptimized
                />
              </div>
            )}
          </div>

          {/* Footer Metadata */}
          <div className="flex items-center gap-2 mt-1 px-1">
            <span className="text-[10px] text-[var(--foreground-muted)]">
              {formatMessageTime(timestamp)}
            </span>
            <button
              onClick={handleCopy}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-[var(--background-secondary)] rounded"
              aria-label="Copy message"
            >
              {copied ? (
                <Check className="w-3 h-3 text-[var(--success)]" />
              ) : (
                <Copy className="w-3 h-3 text-[var(--foreground-muted)]" />
              )}
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export const MessageBubble = memo(MessageBubbleComponent);
