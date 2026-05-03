/**
 * Funnel Analytics Types
 * Type-safe definitions for funnel analytics service
 */

export interface FunnelAnalyticsReturn {
  startFunnel: (funnelId: string, userId: string) => void;
  completeStep: (funnelId: string, stepId: string, userId: string) => void;
  getUserProgress: (
    funnelId: string,
    userId: string,
  ) => {
    userId: string;
    funnelId: string;
    currentStage: string;
    currentStep: string;
    completedSteps: string[];
    startTime: string;
    lastActivity: string;
    totalTime: number;
    completed: boolean;
  } | null;
  getFunnelAnalytics: (funnelId: string) => {
    funnelId: string;
    totalUsers: number;
    completedUsers: number;
    currentUsers: Map<string, unknown>;
    stageAnalytics: Map<
      string,
      {
        entered: number;
        completed: number;
        dropped: number;
        averageTime: number;
      }
    >;
    stepAnalytics: Map<
      string,
      {
        attempts: number;
        completions: number;
        errors: number;
        averageTime: number;
      }
    >;
  } | null;
  getConversionRates: (funnelId: string) => Record<string, number>;
  getDropOffPoints: (
    funnelId: string,
  ) => Array<{ stage: string; dropOffRate: number }>;
  getCompletionRate: (funnelId: string) => number;
  getAverageCompletionTime: (funnelId: string) => number;
}
