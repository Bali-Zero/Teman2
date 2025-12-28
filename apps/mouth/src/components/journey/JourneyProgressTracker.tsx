/**
 * Journey Progress Tracker Component
 * Visualizes client journey progress with step-by-step tracking
 */

'use client';

import { useState, useEffect } from 'react';
import { CheckCircle2, Circle, Clock, AlertCircle, Lock } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import type {
  ClientJourney,
  JourneyProgress,
  JourneyStep,
  StepStatus,
} from '@/lib/api/zantara-sdk/types';
import { ZantaraSDK } from '@/lib/api/zantara-sdk';

export interface JourneyProgressTrackerProps {
  journeyId: string;
  sdk: ZantaraSDK;
  onStepClick?: (step: JourneyStep) => void;
}

const statusIcons: Record<StepStatus, typeof CheckCircle2> = {
  completed: CheckCircle2,
  in_progress: Clock,
  blocked: AlertCircle,
  pending: Lock,
  skipped: Circle,
};

const statusColors: Record<StepStatus, string> = {
  completed: 'text-green-600',
  in_progress: 'text-blue-600',
  blocked: 'text-red-600',
  pending: 'text-gray-400',
  skipped: 'text-gray-300',
};

export function JourneyProgressTracker({
  journeyId,
  sdk,
  onStepClick,
}: JourneyProgressTrackerProps) {
  const [journey, setJourney] = useState<ClientJourney | null>(null);
  const [progress, setProgress] = useState<JourneyProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadJourney();
  }, [journeyId]);

  const loadJourney = async () => {
    setLoading(true);
    setError(null);
    try {
      const [journeyData, progressData] = await Promise.all([
        sdk.getJourney(journeyId),
        sdk.getJourneyProgress(journeyId),
      ]);
      setJourney(journeyData);
      setProgress(progressData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load journey');
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteStep = async (stepId: string) => {
    try {
      await sdk.completeStep(journeyId, stepId);
      await loadJourney();
    } catch (err) {
      console.error('Failed to complete step:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-muted-foreground">Loading journey...</p>
      </div>
    );
  }

  if (error || !journey || !progress) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-destructive">Error: {error || 'Journey not found'}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">{journey.title}</h2>
          <span className="px-3 py-1 text-sm bg-muted rounded-full">
            {progress.status}
          </span>
        </div>
        {journey.description && (
          <p className="text-muted-foreground">{journey.description}</p>
        )}
      </div>

      {/* Progress Overview */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span>Overall Progress</span>
          <span className="font-semibold">{progress.progress_percentage}%</span>
        </div>
        <Progress value={progress.progress_percentage} className="h-2" />
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>{progress.completed_steps} completed</span>
          <span>{progress.in_progress_steps} in progress</span>
          {progress.blocked_steps > 0 && (
            <span className="text-red-600">{progress.blocked_steps} blocked</span>
          )}
          <span>{progress.total_steps} total</span>
        </div>
      </div>

      {/* Timeline Estimate */}
      {progress.estimated_days_remaining > 0 && (
        <div className="p-4 bg-muted rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Estimated Time Remaining</span>
            <span className="text-sm font-semibold">
              {progress.estimated_days_remaining} days
            </span>
          </div>
          {progress.estimated_completion && (
            <p className="text-xs text-muted-foreground mt-1">
              Target completion: {new Date(progress.estimated_completion).toLocaleDateString()}
            </p>
          )}
        </div>
      )}

      {/* Steps */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Steps</h3>
        {journey.steps.map((step, index) => {
          const Icon = statusIcons[step.status];
          const colorClass = statusColors[step.status];
          const canComplete =
            step.status === 'pending' || step.status === 'in_progress';

          return (
            <div
              key={step.step_id}
              className={`p-4 border rounded-lg ${
                step.status === 'blocked' ? 'border-red-300 bg-red-50' : ''
              } ${onStepClick ? 'cursor-pointer hover:bg-muted' : ''}`}
              onClick={() => onStepClick?.(step)}
            >
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                  <Icon className={`h-6 w-6 ${colorClass}`} />
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium">
                        {step.step_number}. {step.title}
                      </h4>
                      {step.description && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {step.description}
                        </p>
                      )}
                    </div>
                    <span className="px-2 py-1 text-xs bg-muted rounded">
                      {step.status}
                    </span>
                  </div>

                  {/* Prerequisites */}
                  {step.prerequisites.length > 0 && (
                    <div className="text-xs text-muted-foreground">
                      <span className="font-medium">Prerequisites: </span>
                      {step.prerequisites.join(', ')}
                    </div>
                  )}

                  {/* Required Documents */}
                  {step.required_documents.length > 0 && (
                    <div className="text-xs">
                      <span className="font-medium text-muted-foreground">
                        Required Documents:
                      </span>
                      <ul className="list-disc list-inside mt-1 space-y-0.5">
                        {step.required_documents.map((doc, docIndex) => (
                          <li key={docIndex} className="text-muted-foreground">
                            {doc}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Timeline */}
                  {step.estimated_duration_days > 0 && (
                    <div className="text-xs text-muted-foreground">
                      Estimated duration: {step.estimated_duration_days} days
                    </div>
                  )}

                  {/* Blocked Reason */}
                  {step.blocked_reason && (
                    <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                      <span className="font-medium">Blocked: </span>
                      {step.blocked_reason}
                    </div>
                  )}

                  {/* Notes */}
                  {step.notes.length > 0 && (
                    <div className="text-xs">
                      <span className="font-medium text-muted-foreground">Notes:</span>
                      <ul className="list-disc list-inside mt-1 space-y-0.5">
                        {step.notes.map((note, noteIndex) => (
                          <li key={noteIndex} className="text-muted-foreground">
                            {note}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Completion Dates */}
                  {step.completed_at && (
                    <div className="text-xs text-green-600">
                      Completed: {new Date(step.completed_at).toLocaleDateString()}
                    </div>
                  )}
                  {step.started_at && !step.completed_at && (
                    <div className="text-xs text-blue-600">
                      Started: {new Date(step.started_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Next Steps */}
      {progress.next_steps.length > 0 && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h4 className="font-medium text-blue-900 mb-2">Next Steps</h4>
          <ul className="list-disc list-inside space-y-1 text-sm text-blue-800">
            {progress.next_steps.map((stepId, index) => {
              const step = journey.steps.find((s) => s.step_id === stepId);
              return (
                <li key={index}>
                  {step ? `${step.step_number}. ${step.title}` : stepId}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}







