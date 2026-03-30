'use client';

import React from 'react';
import { CheckCircle, Circle, Loader, User } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ProcessTimelineStep } from '@/lib/api/portal/portal.types';

interface ProcessStepperProps {
  steps: ProcessTimelineStep[];
  className?: string;
}

export function ProcessStepper({ steps, className }: ProcessStepperProps) {
  if (steps.length === 0) return null;

  return (
    <div className={cn('relative', className)}>
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1;

        return (
          <div key={`${step.status}-${index}`} className="flex gap-3">
            {/* Vertical line + dot */}
            <div className="flex flex-col items-center">
              {step.completed ? (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(16,185,129,0.15)' }}
                >
                  <CheckCircle className="w-4 h-4" style={{ color: '#34d399' }} />
                </div>
              ) : step.is_current ? (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 animate-pulse"
                  style={{ background: 'rgba(59,130,246,0.15)' }}
                >
                  <Loader className="w-4 h-4 animate-spin" style={{ color: '#60a5fa' }} />
                </div>
              ) : (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(255,255,255,0.05)' }}
                >
                  <Circle className="w-3 h-3" style={{ color: 'var(--bz-text-3)' }} />
                </div>
              )}
              {!isLast && (
                <div
                  className="w-0.5 flex-1 min-h-[24px]"
                  style={{
                    background: step.completed
                      ? 'rgba(16,185,129,0.3)'
                      : 'rgba(255,255,255,0.05)',
                  }}
                />
              )}
            </div>

            {/* Content */}
            <div className={cn('pb-4 flex-1 min-w-0', isLast && 'pb-0')}>
              <p
                className={cn(
                  'text-sm font-medium',
                  step.is_current && 'text-blue-400',
                  step.completed && 'text-[var(--bz-text-1)]',
                  !step.completed && !step.is_current && 'text-[var(--bz-text-3)]',
                )}
              >
                {step.label}
              </p>
              {step.changed_at && (
                <p className="text-xs mt-0.5" style={{ color: 'var(--bz-text-3)' }}>
                  {new Date(step.changed_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                  {step.changed_by && step.changed_by !== 'system' && (
                    <span className="ml-1.5">
                      <User className="w-3 h-3 inline -mt-0.5" style={{ color: 'var(--bz-text-3)' }} /> {step.changed_by.split('@')[0]}
                    </span>
                  )}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
