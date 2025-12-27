'use client';

import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import Image from 'next/image';
import { AgentStep } from '@/types';

interface ThinkingIndicatorProps {
  isVisible: boolean;
  currentStatus?: string;
  steps?: AgentStep[];
  elapsedTime?: number;
}

// Map tool names to icons and friendly labels
const TOOL_CONFIG: Record<string, { icon: React.ReactNode; label: string }> = {
  vector_search: { icon: <Search className="w-3.5 h-3.5" />, label: 'Searching Knowledge Base' },
  database_query: { icon: <Database className="w-3.5 h-3.5" />, label: 'Reading Full Document' },
  web_search: { icon: <Globe className="w-3.5 h-3.5" />, label: 'Searching the Web' },
  calculator: { icon: <Calculator className="w-3.5 h-3.5" />, label: 'Calculating' },
  get_pricing: { icon: <FileText className="w-3.5 h-3.5" />, label: 'Fetching Pricing Info' },
  team_knowledge: { icon: <Users className="w-3.5 h-3.5" />, label: 'Looking Up Team Info' },
  graph_traversal: { icon: <Database className="w-3.5 h-3.5" />, label: 'Exploring Knowledge Graph' },
};

const DEFAULT_TOOL = { icon: <FileText className="w-3.5 h-3.5" />, label: 'Processing' };

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

  // Get tool starts and ends from steps
  const toolStarts = steps.filter((s) => s.type === 'tool_start');
  const toolEnds = steps.filter((s) => s.type === 'tool_end');
  
  // Detect active phase and reasoning steps
  const phases = steps.filter((s) => s.type === 'phase');
  const reasoningSteps = steps.filter((s) => s.type === 'reasoning_step');
  
  const latestPhase = phases.length > 0 ? phases[phases.length - 1] : null;
  const latestReasoning = reasoningSteps.length > 0 ? reasoningSteps[reasoningSteps.length - 1] : null;
  
  // Determine current phase name from either standard phase event or reasoning step
  // @ts-ignore
  const currentPhaseName = latestReasoning?.data?.phase || latestPhase?.data?.name || null;
  // @ts-ignore
  const currentMessage = latestReasoning?.data?.message || null;

  // Build activity list from steps
  const activities = toolStarts.map((step, idx) => {
    if (step.type !== 'tool_start') return null;
    const toolName = step.data.name;
    const config = TOOL_CONFIG[toolName] || DEFAULT_TOOL;
    const isCompleted = idx < toolEnds.length;
    const isCurrent = idx === toolStarts.length - 1 && !isCompleted;

    return {
      key: `${toolName}-${idx}`,
      icon: config.icon,
      label: config.label,
      isCompleted,
      isCurrent,
    };
  }).filter(Boolean);

  const currentPhrase = THINKING_PHRASES[phraseIndex];

  // Reasoning Details Component
  const ReasoningDetails = () => {
    if (!latestReasoning || !latestReasoning.data.details) return null;
    // Cast details to a more specific type to avoid "unknown" errors
    const details = latestReasoning.data.details as {
      key_points?: unknown[];
      corrections?: unknown[];
    };
    const isGiant = latestReasoning.data.phase === 'giant';
    const isCell = latestReasoning.data.phase === 'cell';

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

            {/* Header */}
            <div className="relative flex items-center gap-3 mb-4">
              <div className="flex-1">
                <span className="text-sm font-semibold text-[var(--foreground)]">
                  {currentPhaseName ? `Phase: ${currentPhaseName.charAt(0).toUpperCase() + currentPhaseName.slice(1)}` : 'Zantara is thinking'}
                </span>
                <motion.span
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                  className="text-[var(--accent)]"
                >
                  ...
                </motion.span>
              </div>
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

            {/* Phase Visualizer (deprecated - kept for backward compatibility) */}
            {currentPhaseName && <PhaseVisualizer />}

            {/* Multi-color Progress Bar (Fallback if no phases) */}
            {!currentPhaseName && (
              <div className="relative h-1.5 bg-[var(--background)] rounded-full overflow-hidden mb-4">
                <motion.div
                  className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-500 via-blue-500 to-cyan-500"
                  initial={{ width: '0%' }}
                  animate={{ width: '100%' }}
                  transition={{ duration: 40, ease: 'linear' }}
                />
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                  animate={{ x: ['-100%', '100%'] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                />
              </div>
            )}

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
