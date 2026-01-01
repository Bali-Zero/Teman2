'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Database,
  Calculator,
  Globe,
  FileText,
  Users,
  CheckCircle2,
  Loader2,
  Sparkles,
  BookOpen,
  Scale,
  Zap,
  Lightbulb,
  ShieldAlert,
  Network,
  DollarSign,
  Brain,
} from 'lucide-react';
import Image from 'next/image';
import { AgentStep } from '@/types';

// Generic step type for flexible event handling
interface GenericStep {
  type: string;
  data?: unknown;
  timestamp?: Date;
}

interface ThinkingIndicatorProps {
  isVisible: boolean;
  currentStatus?: string;
  steps?: GenericStep[] | AgentStep[];
  elapsedTime?: number;
  maxSteps?: number; // Maximum steps (default 3)
  currentStep?: number; // Current step number
}

// Collection display names for user-friendly messages
const COLLECTION_NAMES: Record<string, string> = {
  visa_oracle: 'documenti visti',
  legal_unified: 'normativa legale',
  legal_unified_hybrid: 'normativa legale',
  kbli_unified: 'codici KBLI',
  tax_genius: 'regolamenti fiscali',
  tax_genius_hybrid: 'regolamenti fiscali',
  bali_zero_pricing: 'listino prezzi',
  bali_zero_team: 'team Bali Zero',
  collective_memories: 'memoria condivisa',
  training_conversations: 'conversazioni precedenti',
};

// Generate dynamic status message based on tool and arguments
function getDynamicToolMessage(toolName: string, args: Record<string, unknown>): string {
  const query = typeof args?.query === 'string' ? args.query : '';
  const collection = typeof args?.collection === 'string' ? args.collection : '';
  const shortQuery = query.length > 40 ? query.slice(0, 40) + '...' : query;

  switch (toolName) {
    case 'vector_search': {
      if (collection && COLLECTION_NAMES[collection]) {
        return `Cerco "${shortQuery}" in ${COLLECTION_NAMES[collection]}...`;
      }
      return `Cerco "${shortQuery}" nella knowledge base...`;
    }
    case 'knowledge_graph_search': {
      const entity = typeof args?.entity_name === 'string' ? args.entity_name : query;
      return `Esploro connessioni per "${entity}"...`;
    }
    case 'calculator': {
      const expr = typeof args?.expression === 'string' ? args.expression : '';
      return `Calcolo: ${expr.slice(0, 30)}${expr.length > 30 ? '...' : ''}`;
    }
    case 'get_pricing': {
      const service = typeof args?.service_name === 'string' ? args.service_name : 'servizio';
      return `Recupero prezzo per "${service}"...`;
    }
    case 'team_knowledge':
    case 'search_team_member':
    case 'get_team_members_list': {
      return 'Consulto il team Bali Zero...';
    }
    case 'web_search': {
      return `Cerco sul web: "${shortQuery}"...`;
    }
    case 'generate_image': {
      return 'Genero immagine...';
    }
    default:
      return `Elaboro con ${toolName}...`;
  }
}

// Map tool names to icons
const TOOL_ICONS: Record<string, React.ReactNode> = {
  vector_search: <Search className="w-3.5 h-3.5" />,
  knowledge_graph_search: <Network className="w-3.5 h-3.5" />,
  database_query: <Database className="w-3.5 h-3.5" />,
  web_search: <Globe className="w-3.5 h-3.5" />,
  calculator: <Calculator className="w-3.5 h-3.5" />,
  get_pricing: <DollarSign className="w-3.5 h-3.5" />,
  team_knowledge: <Users className="w-3.5 h-3.5" />,
  search_team_member: <Users className="w-3.5 h-3.5" />,
  get_team_members_list: <Users className="w-3.5 h-3.5" />,
  generate_image: <Sparkles className="w-3.5 h-3.5" />,
};

// Legacy static config for backward compatibility
const TOOL_CONFIG: Record<string, { icon: React.ReactNode; label: string }> = {
  vector_search: { icon: <Search className="w-3.5 h-3.5" />, label: 'Searching Knowledge Base' },
  database_query: { icon: <Database className="w-3.5 h-3.5" />, label: 'Reading Full Document' },
  web_search: { icon: <Globe className="w-3.5 h-3.5" />, label: 'Searching the Web' },
  calculator: { icon: <Calculator className="w-3.5 h-3.5" />, label: 'Calculating' },
  get_pricing: { icon: <DollarSign className="w-3.5 h-3.5" />, label: 'Fetching Pricing Info' },
  team_knowledge: { icon: <Users className="w-3.5 h-3.5" />, label: 'Looking Up Team Info' },
  graph_traversal: { icon: <Network className="w-3.5 h-3.5" />, label: 'Exploring Knowledge Graph' },
  knowledge_graph_search: { icon: <Network className="w-3.5 h-3.5" />, label: 'Exploring Knowledge Graph' },
};

const DEFAULT_TOOL = { icon: <Brain className="w-3.5 h-3.5" />, label: 'Processing' };

// Fun thinking phrases that rotate (English, professional)
const THINKING_PHRASES = [
  { text: 'Analyzing your question...', icon: <Sparkles className="w-4 h-4" /> },
  { text: 'Consulting Indonesian regulations...', icon: <Scale className="w-4 h-4" /> },
  { text: 'Searching through documents...', icon: <BookOpen className="w-4 h-4" /> },
  { text: 'Cross-referencing sources...', icon: <Search className="w-4 h-4" /> },
  { text: 'Building your answer...', icon: <Zap className="w-4 h-4" /> },
];

// Indonesian interjections - casual, friendly phrases
const INDONESIAN_INTERJECTIONS = [
  'Sabar ya, Pak/Bu...',
  'Ditunggu sebentar...',
  'Sedang diproses...',
  'Bentar lagi siap...',
  'Lagi dicari dulu...',
  'Mohon tunggu ya...',
  'Sebentar lagi...',
  'Santai dulu...',
];

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({
  isVisible,
  currentStatus,
  steps = [],
  elapsedTime = 0,
  maxSteps = 3,
  currentStep = 0,
}) => {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [interjectionIndex, setInterjectionIndex] = useState(0);

  // Rotate through thinking phrases every 4 seconds
  useEffect(() => {
    if (!isVisible) return;
    const interval = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % THINKING_PHRASES.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [isVisible]);

  // Rotate through Indonesian interjections every 3 seconds (different timing for variety)
  useEffect(() => {
    if (!isVisible) return;
    const interval = setInterval(() => {
      setInterjectionIndex((prev) => (prev + 1) % INDONESIAN_INTERJECTIONS.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [isVisible]);

  if (!isVisible) return null;

  // Get tool events from steps
  const toolCalls = steps.filter((s) => s.type === 'tool_call' || s.type === 'tool_start');
  const toolEnds = steps.filter((s) => s.type === 'tool_end');
  const thinkingSteps = steps.filter((s) => s.type === 'thinking');

  // Detect active phase and reasoning steps
  const phases = steps.filter((s) => s.type === 'phase');
  const reasoningSteps = steps.filter((s) => s.type === 'reasoning_step');

  const latestPhase = phases.length > 0 ? phases[phases.length - 1] : null;
  const latestReasoning = reasoningSteps.length > 0 ? reasoningSteps[reasoningSteps.length - 1] : null;

  // Determine current phase name from either standard phase event or reasoning step
  // Type-safe data extraction
  const latestReasoningData = latestReasoning?.data as Record<string, unknown> | undefined;
  const latestPhaseData = latestPhase?.data as Record<string, unknown> | undefined;
  const currentPhaseName = (latestReasoningData?.phase as string) || (latestPhaseData?.name as string) || null;
  const currentMessage = (latestReasoningData?.message as string) || null;

  // Calculate actual step from thinking events
  const actualStep = thinkingSteps.length > 0 ? thinkingSteps.length : (currentStep || 1);
  const progressPercent = Math.min((actualStep / maxSteps) * 100, 100);

  // Build activity list with DYNAMIC messages from actual tool arguments
  const activities = toolCalls.map((step, idx) => {
    // Handle both tool_call and tool_start event formats
    // Type-safe data extraction
    const stepData = step.data as Record<string, unknown> | undefined;
    const toolName = (stepData?.tool as string) || (stepData?.name as string) || 'unknown';
    const toolArgs = (stepData?.args as Record<string, unknown>) || {};
    const icon = TOOL_ICONS[toolName] || DEFAULT_TOOL.icon;
    // Generate dynamic message based on actual arguments
    const dynamicLabel = getDynamicToolMessage(toolName, toolArgs);
    const isCompleted = idx < toolEnds.length;
    const isCurrent = idx === toolCalls.length - 1 && !isCompleted;

    return {
      key: `${toolName}-${idx}`,
      icon,
      label: dynamicLabel,
      toolName,
      isCompleted,
      isCurrent,
    };
  }).filter(Boolean);

  const currentPhrase = THINKING_PHRASES[phraseIndex];

  // Reasoning Details Component
  const ReasoningDetails = () => {
    if (!latestReasoning || !latestReasoningData?.details) return null;
    // Cast details to a more specific type to avoid "unknown" errors
    const details = latestReasoningData.details as {
      key_points?: unknown[];
      corrections?: unknown[];
    };
    const isGiant = latestReasoningData?.phase === 'giant';
    const isCell = latestReasoningData?.phase === 'cell';

    return (
      <motion.div 
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: 'auto' }}
        className="mt-3 bg-[var(--background)]/50 rounded-lg p-2 text-xs border border-[var(--border)]"
      >
        {isGiant && details.key_points && Array.isArray(details.key_points) && (
          <div className="flex items-center gap-2 text-[var(--accent)]">
            <Lightbulb className="w-3 h-3" />
            <span>Identified {details.key_points.length} key strategic points</span>
          </div>
        )}
        {isCell && details.corrections && Array.isArray(details.corrections) && (
          <div className="flex items-center gap-2 text-[var(--warning)]">
            <ShieldAlert className="w-3 h-3" />
            <span>Applied {details.corrections.length} corrections</span>
          </div>
        )}
      </motion.div>
    );
  };

  // Phase Visualizer (deprecated - kept for backward compatibility)
  const PhaseVisualizer = () => {
    if (!currentPhaseName) return null;
    
    const phases = [
      { id: 'giant', label: 'Giant', icon: <BookOpen className="w-3 h-3" /> },
      { id: 'cell', label: 'Cell', icon: <Scale className="w-3 h-3" /> },
      { id: 'zantara', label: 'Zantara', icon: <Sparkles className="w-3 h-3" /> },
    ];

    const currentIndex = phases.findIndex(p => p.id === currentPhaseName);

    return (
      <div className="flex flex-col mb-3 px-1">
        <div className="flex items-center justify-between z-10 relative">
          {phases.map((phase, idx) => {
            const isActive = phase.id === currentPhaseName;
            const isCompleted = currentIndex > idx;
            
            return (
              <div key={phase.id} className="flex flex-col items-center gap-1">
                <motion.div
                  initial={false}
                  animate={{
                    backgroundColor: isActive ? 'rgba(var(--accent-rgb), 0.2)' : isCompleted ? 'rgba(var(--success-rgb), 0.2)' : 'rgba(var(--foreground-rgb), 0.05)',
                    borderColor: isActive ? 'var(--accent)' : isCompleted ? 'var(--success)' : 'transparent',
                    scale: isActive ? 1.1 : 1
                  }}
                  className={`
                    w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors bg-[var(--background)]
                    ${isActive ? 'text-[var(--accent)]' : isCompleted ? 'text-[var(--success)]' : 'text-[var(--foreground-muted)]'}
                  `}
                >
                  {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : phase.icon}
                </motion.div>
                <span className={`text-[10px] font-medium ${isActive ? 'text-[var(--accent)]' : 'text-[var(--foreground-muted)]'}`}>
                  {phase.label}
                </span>
              </div>
            );
          })}
          {/* Progress Line */}
          <div className="absolute left-4 right-4 top-4 h-0.5 bg-[var(--border)] -z-10">
            <motion.div 
              className="h-full bg-[var(--accent)]"
              initial={{ width: '0%' }}
              animate={{ width: `${(currentIndex / 2) * 100}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
        
        {/* Current Message Display */}
        {currentMessage && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            key={currentMessage}
            className="mt-3 text-center text-xs text-[var(--foreground-secondary)] font-medium"
          >
            {currentMessage}
          </motion.div>
        )}

        <ReasoningDetails />
      </div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="flex w-full justify-start mb-6"
    >
      <div className="flex max-w-[85%] md:max-w-[75%] gap-3">
        {/* Animated Avatar */}
        <div className="flex-shrink-0 w-14 h-14 -ml-2 relative">
          {/* Pulsing glow effect */}
          <motion.div
            className="absolute inset-0 rounded-full bg-gradient-to-r from-purple-500/30 to-blue-500/30 blur-xl"
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.5, 0.8, 0.5],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
          {/* Orbiting particles */}
          <motion.div
            className="absolute inset-0"
            animate={{ rotate: 360 }}
            transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
          >
            <div className="absolute top-0 left-1/2 w-1.5 h-1.5 -ml-0.75 bg-purple-400 rounded-full" />
            <div className="absolute bottom-0 left-1/2 w-1 h-1 -ml-0.5 bg-blue-400 rounded-full" />
          </motion.div>
          <motion.div
            className="absolute inset-0"
            animate={{ rotate: -360 }}
            transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
          >
            <div className="absolute left-0 top-1/2 w-1 h-1 -mt-0.5 bg-cyan-400 rounded-full" />
            <div className="absolute right-0 top-1/2 w-1.5 h-1.5 -mt-0.75 bg-pink-400 rounded-full" />
          </motion.div>
          {/* Logo */}
          <div className="relative w-full h-full">
            <Image
              src="/images/logo_zan.png"
              alt="Zantara"
              fill
              className="object-contain brightness-110 drop-shadow-[0_0_20px_rgba(100,100,255,0.5)] scale-125"
            />
          </div>
        </div>

        {/* Thinking Card */}
        <div className="flex flex-col items-start min-w-0">
          <motion.div
            className="
              relative px-5 py-4 rounded-2xl shadow-lg
              bg-gradient-to-br from-[var(--background-elevated)] to-[var(--background-secondary)]
              text-[var(--foreground)]
              rounded-tl-sm border border-[var(--accent)]/20
              min-w-[300px] overflow-hidden
            "
          >
            {/* Animated shimmer effect */}
            <motion.div
              className="absolute inset-0 opacity-20"
              style={{
                background: 'linear-gradient(45deg, transparent 0%, rgba(139, 92, 246, 0.1) 50%, transparent 100%)',
              }}
              animate={{
                x: ['-100%', '100%'],
              }}
              transition={{
                duration: 3,
                repeat: Infinity,
                ease: 'linear',
              }}
            />

            {/* Header with Step Counter */}
            <div className="relative flex items-center gap-3 mb-3">
              <div className="flex-1">
                <span className="text-sm font-semibold text-[var(--foreground)]">
                  Zantara sta ragionando
                </span>
                <motion.span
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                  className="text-[var(--accent)]"
                >
                  ...
                </motion.span>
              </div>
              <div className="flex items-center gap-2">
                {/* Step counter badge */}
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="px-2 py-1 rounded-full bg-[var(--accent)]/20 text-[10px] font-bold text-[var(--accent)] border border-[var(--accent)]/30"
                >
                  Step {actualStep}/{maxSteps}
                </motion.div>
                {elapsedTime > 0 && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="px-2 py-1 rounded-full bg-[var(--background)] text-[10px] font-mono text-[var(--foreground-muted)]"
                  >
                    {elapsedTime}s
                  </motion.div>
                )}
              </div>
            </div>

            {/* Step Progress Bar */}
            <div className="relative h-2 bg-[var(--background)] rounded-full overflow-hidden mb-4">
              {/* Background segments for each step */}
              <div className="absolute inset-0 flex">
                {Array.from({ length: maxSteps }).map((_, i) => (
                  <div
                    key={i}
                    className={`flex-1 ${i > 0 ? 'border-l border-[var(--border)]/30' : ''}`}
                  />
                ))}
              </div>
              {/* Filled progress */}
              <motion.div
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-500 via-blue-500 to-cyan-500"
                initial={{ width: '0%' }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
              {/* Shimmer effect */}
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                animate={{ x: ['-100%', '100%'] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
              />
            </div>

            {/* Phase Visualizer (deprecated - kept for backward compatibility) */}
            {currentPhaseName && <PhaseVisualizer />}

            {/* Activity List or Rotating Status */}
            <AnimatePresence mode="wait">
              {activities.length > 0 ? (
                <motion.div
                  key="activities"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-2.5"
                >
                  {activities.map((activity, idx) => activity && (
                    <motion.div
                      key={activity.key}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.1 }}
                      className={`
                        flex items-center gap-2.5 text-xs p-2 rounded-lg
                        ${activity.isCompleted
                          ? 'bg-[var(--success)]/10 text-[var(--success)]'
                          : activity.isCurrent
                            ? 'bg-[var(--accent)]/10 text-[var(--accent)]'
                            : 'text-[var(--foreground-muted)]'
                        }
                      `}
                    >
                      {activity.isCompleted ? (
                        <motion.div
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ type: 'spring' }}
                        >
                          <CheckCircle2 className="w-4 h-4" />
                        </motion.div>
                      ) : activity.isCurrent ? (
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        >
                          <Loader2 className="w-4 h-4" />
                        </motion.div>
                      ) : (
                        activity.icon
                      )}
                      <span className="font-medium">{activity.label}</span>
                      {activity.isCompleted && (
                        <motion.span
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          className="text-[10px] ml-auto opacity-70"
                        >
                          Done
                        </motion.span>
                      )}
                    </motion.div>
                  ))}
                </motion.div>
              ) : (
                /* Rotating thinking phrases + Indonesian interjection */
                <div className="space-y-2">
                  <motion.div
                    key={`phrase-${phraseIndex}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="flex items-center gap-2.5 text-sm text-[var(--foreground-muted)] p-2 rounded-lg bg-[var(--background)]/50"
                  >
                    <motion.div
                      animate={{ rotate: [0, 10, -10, 0] }}
                      transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 2 }}
                      className="text-[var(--accent)]"
                    >
                      {currentPhrase.icon}
                    </motion.div>
                    <span>{currentPhaseName ? `${currentPhaseName === 'giant' ? 'Analyzing complex regulations...' : currentPhaseName === 'cell' ? 'Calibrating with local data...' : 'Finalizing answer...'}` : currentPhrase.text}</span>
                  </motion.div>
                  {/* Indonesian interjection - casual friendly touch */}
                  <motion.div
                    key={`interjection-${interjectionIndex}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="text-xs text-[var(--foreground-muted)]/70 italic pl-2"
                  >
                    💬 {INDONESIAN_INTERJECTIONS[interjectionIndex]}
                  </motion.div>
                </div>
              )}
            </AnimatePresence>

            {/* Sources counter with animation */}
            {toolEnds.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-4 pt-3 border-t border-[var(--border)]/30 flex items-center gap-2"
              >
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 0.5 }}
                  className="w-5 h-5 rounded-full bg-[var(--success)]/20 flex items-center justify-center"
                >
                  <span className="text-[10px] font-bold text-[var(--success)]">{toolEnds.length}</span>
                </motion.div>
                <span className="text-xs text-[var(--foreground-muted)]">
                  {toolEnds.length === 1 ? 'source' : 'sources'} found
                </span>
              </motion.div>
            )}
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
};
