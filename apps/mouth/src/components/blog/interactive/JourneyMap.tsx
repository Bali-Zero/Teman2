'use client';

import * as React from 'react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  Clock,
  DollarSign,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Info,
  Zap
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface JourneyStep {
  id: string;
  title: string;
  shortTitle?: string;
  description: string;
  /** Duration in days or text */
  duration?: string | number;
  /** Cost in IDR or text */
  cost?: string | number;
  /** Required documents */
  documents?: string[];
  /** Tips for this step */
  tips?: string[];
  /** Warnings */
  warnings?: string[];
  /** Status */
  status?: 'pending' | 'current' | 'completed';
  /** Icon */
  icon?: string;
}

export interface JourneyMapProps {
  /** Title */
  title: string;
  /** Subtitle */
  subtitle?: string;
  /** Steps */
  steps: JourneyStep[];
  /** Total estimated duration */
  totalDuration?: string;
  /** Total estimated cost */
  totalCost?: string | number;
  /** Show fast track option */
  showFastTrack?: boolean;
  /** Fast track steps (alternative) */
  fastTrackSteps?: JourneyStep[];
  /** Fast track additional cost */
  fastTrackPremium?: string;
  /** Custom class */
  className?: string;
}

// ============================================================================
// Main Component
// ============================================================================

export function JourneyMap({
  title,
  subtitle,
  steps,
  totalDuration,
  totalCost,
  showFastTrack = false,
  fastTrackSteps,
  fastTrackPremium,
  className,
}: JourneyMapProps) {
  const [selectedStep, setSelectedStep] = useState<string | null>(null);
  const [isFastTrack, setIsFastTrack] = useState(false);

  const activeSteps = isFastTrack && fastTrackSteps ? fastTrackSteps : steps;
  const selectedStepData = activeSteps.find((s) => s.id === selectedStep);

  // Calculate totals
  const calculatedDuration = activeSteps.reduce((acc, step) => {
    if (typeof step.duration === 'number') return acc + step.duration;
    return acc;
  }, 0);

  const calculatedCost = activeSteps.reduce((acc, step) => {
    if (typeof step.cost === 'number') return acc + step.cost;
    return acc;
  }, 0);

  return (
    <div className={cn('bg-black/40 rounded-2xl border border-white/10 overflow-hidden', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10 bg-gradient-to-r from-purple-500/10 to-transparent">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-serif text-xl font-semibold text-white">{title}</h3>
            {subtitle && <p className="text-white/60 text-sm mt-1">{subtitle}</p>}
          </div>

          {/* Fast track toggle */}
          {showFastTrack && fastTrackSteps && (
            <button
              onClick={() => setIsFastTrack(!isFastTrack)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                isFastTrack
                  ? 'bg-amber-500/20 text-amber-400'
                  : 'bg-white/5 text-white/60 hover:bg-white/10'
              )}
            >
              <Zap className="w-4 h-4" />
              <span>Fast Track</span>
              {fastTrackPremium && isFastTrack && (
                <span className="text-xs opacity-60">+{fastTrackPremium}</span>
              )}
            </button>
          )}
        </div>

        {/* Summary stats */}
        <div className="flex items-center gap-6 mt-4">
          <div className="flex items-center gap-2 text-white/60">
            <Clock className="w-4 h-4" />
            <span className="text-sm">
              {totalDuration || `~${calculatedDuration} days`}
            </span>
          </div>
          <div className="flex items-center gap-2 text-white/60">
            <DollarSign className="w-4 h-4" />
            <span className="text-sm">
              {typeof totalCost === 'number'
                ? `Rp ${totalCost.toLocaleString('id-ID')}`
                : totalCost || `Rp ${calculatedCost.toLocaleString('id-ID')}`}
            </span>
          </div>
          <div className="flex items-center gap-2 text-white/60">
            <FileText className="w-4 h-4" />
            <span className="text-sm">{activeSteps.length} steps</span>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="p-6">
        <div className="relative">
          {/* Connection line */}
          <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-white/10" />

          {/* Steps */}
          <div className="space-y-4">
            {activeSteps.map((step, index) => {
              const isSelected = selectedStep === step.id;
              const isCompleted = step.status === 'completed';
              const isCurrent = step.status === 'current';

              return (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="relative"
                >
                  {/* Step indicator */}
                  <div className="flex items-start gap-4">
                    {/* Circle */}
                    <div
                      className={cn(
                        'relative z-10 w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 transition-colors',
                        isCompleted && 'bg-emerald-500/20 border-2 border-emerald-500/50',
                        isCurrent && 'bg-[#2251ff]/20 border-2 border-[#2251ff]/50 animate-pulse',
                        !isCompleted && !isCurrent && 'bg-white/5 border-2 border-white/20'
                      )}
                    >
                      {step.icon ? (
                        <span className="text-xl">{step.icon}</span>
                      ) : isCompleted ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      ) : (
                        <span className={cn(
                          'font-bold',
                          isCurrent ? 'text-[#2251ff]' : 'text-white/60'
                        )}>
                          {index + 1}
                        </span>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 pb-4">
                      <button
                        onClick={() => setSelectedStep(isSelected ? null : step.id)}
                        className="w-full text-left group"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className={cn(
                              'font-medium transition-colors',
                              isCompleted && 'text-emerald-400',
                              isCurrent && 'text-[#2251ff]',
                              !isCompleted && !isCurrent && 'text-white group-hover:text-[#2251ff]'
                            )}>
                              {step.title}
                            </h4>
                            <p className="text-white/50 text-sm mt-0.5">{step.description}</p>
                          </div>

                          {/* Quick stats */}
                          <div className="flex items-center gap-4 text-xs text-white/40">
                            {step.duration && (
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {typeof step.duration === 'number'
                                  ? `${step.duration} days`
                                  : step.duration}
                              </span>
                            )}
                            {step.cost && (
                              <span className="flex items-center gap-1">
                                <DollarSign className="w-3 h-3" />
                                {typeof step.cost === 'number'
                                  ? `Rp ${(step.cost / 1000000).toFixed(1)}M`
                                  : step.cost}
                              </span>
                            )}
                            <ChevronRight
                              className={cn(
                                'w-4 h-4 transition-transform',
                                isSelected && 'rotate-90'
                              )}
                            />
                          </div>
                        </div>
                      </button>

                      {/* Expanded details */}
                      <AnimatePresence>
                        {isSelected && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="mt-4 p-4 rounded-xl bg-white/5 border border-white/10 space-y-4">
                              {/* Documents */}
                              {step.documents && step.documents.length > 0 && (
                                <div>
                                  <h5 className="text-sm font-medium text-white/80 mb-2 flex items-center gap-2">
                                    <FileText className="w-4 h-4" />
                                    Required Documents
                                  </h5>
                                  <ul className="space-y-1">
                                    {step.documents.map((doc, i) => (
                                      <li key={i} className="text-sm text-white/60 flex items-center gap-2">
                                        <span className="w-1.5 h-1.5 rounded-full bg-white/30" />
                                        {doc}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {/* Tips */}
                              {step.tips && step.tips.length > 0 && (
                                <div>
                                  <h5 className="text-sm font-medium text-emerald-400/80 mb-2 flex items-center gap-2">
                                    <Info className="w-4 h-4" />
                                    Pro Tips
                                  </h5>
                                  <ul className="space-y-1">
                                    {step.tips.map((tip, i) => (
                                      <li key={i} className="text-sm text-white/60 flex items-start gap-2">
                                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                                        {tip}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              {/* Warnings */}
                              {step.warnings && step.warnings.length > 0 && (
                                <div>
                                  <h5 className="text-sm font-medium text-amber-400/80 mb-2 flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4" />
                                    Watch Out
                                  </h5>
                                  <ul className="space-y-1">
                                    {step.warnings.map((warning, i) => (
                                      <li key={i} className="text-sm text-amber-400/60 flex items-start gap-2">
                                        <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                        {warning}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
