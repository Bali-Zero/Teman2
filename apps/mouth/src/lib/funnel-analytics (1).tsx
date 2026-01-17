/**
 * Advanced analytics with funnel tracking
 * Tracks user journey through dashboard and business processes
 */

import React from 'react';

interface FunnelStep {
  id: string;
  name: string;
  description: string;
  required: boolean;
  estimatedTime: number; // seconds
}

interface FunnelStage {
  id: string;
  name: string;
  steps: FunnelStep[];
  conversionRate: number;
  dropOffRate: number;
}

interface UserFunnelProgress {
  userId: string;
  funnelId: string;
  currentStage: string;
  currentStep: string;
  completedSteps: string[];
  startTime: string;
  lastActivity: string;
  totalTime: number;
  completed: boolean;
}

interface FunnelAnalytics {
  funnelId: string;
  totalUsers: number;
  completedUsers: number;
  currentUsers: Map<string, UserFunnelProgress>;
  stageAnalytics: Map<string, {
    entered: number;
    completed: number;
    dropped: number;
    averageTime: number;
  }>;
  stepAnalytics: Map<string, {
    attempts: number;
    completions: number;
    errors: number;
    averageTime: number;
  }>;
}

class FunnelAnalyticsService {
  private funnels: Map<string, FunnelStage[]> = new Map();
  private userProgress: Map<string, UserFunnelProgress> = new Map();
  private analytics: Map<string, FunnelAnalytics> = new Map();

  constructor() {
    this.initializeFunnels();
  }

  // Initialize business process funnels
  private initializeFunnels(): void {
    // Case Management Funnel
    this.funnels.set('case_management', [
      {
        id: 'case_creation',
        name: 'Create New Case',
        steps: [
          { id: 'select_case_type', name: 'Select Case Type', description: 'Choose visa type or service', required: true, estimatedTime: 30 },
          { id: 'fill_basic_info', name: 'Basic Information', description: 'Client and case details', required: true, estimatedTime: 120 },
          { id: 'upload_documents', name: 'Upload Documents', description: 'Required paperwork', required: true, estimatedTime: 180 },
          { id: 'review_submit', name: 'Review & Submit', description: 'Final review', required: true, estimatedTime: 60 },
        ],
        conversionRate: 0,
        dropOffRate: 0,
      },
      {
        id: 'case_processing',
        name: 'Process Case',
        steps: [
          { id: 'initial_review', name: 'Initial Review', description: 'Document verification', required: true, estimatedTime: 300 },
          { id: 'government_submission', name: 'Submit to Government', description: 'Official submission', required: true, estimatedTime: 600 },
          { id: 'follow_up', name: 'Follow Up', description: 'Track progress', required: false, estimatedTime: 180 },
          { id: 'completion', name: 'Case Completion', description: 'Final approval', required: true, estimatedTime: 120 },
        ],
        conversionRate: 0,
        dropOffRate: 0,
      },
    ]);

    // Client Onboarding Funnel
    this.funnels.set('client_onboarding', [
      {
        id: 'registration',
        name: 'Client Registration',
        steps: [
          { id: 'create_account', name: 'Create Account', description: 'Basic registration', required: true, estimatedTime: 60 },
          { id: 'verify_email', name: 'Verify Email', description: 'Email confirmation', required: true, estimatedTime: 30 },
          { id: 'complete_profile', name: 'Complete Profile', description: 'Personal details', required: true, estimatedTime: 180 },
          { id: 'select_services', name: 'Select Services', description: 'Choose needed services', required: true, estimatedTime: 120 },
        ],
        conversionRate: 0,
        dropOffRate: 0,
      },
      {
        id: 'first_case',
        name: 'First Case Setup',
        steps: [
          { id: 'consultation', name: 'Initial Consultation', description: 'Discovery call', required: true, estimatedTime: 1800 },
          { id: 'document_collection', name: 'Document Collection', description: 'Gather paperwork', required: true, estimatedTime: 3600 },
          { id: 'case_start', name: 'Start Case', description: 'Begin processing', required: true, estimatedTime: 300 },
        ],
        conversionRate: 0,
        dropOffRate: 0,
      },
    ]);

    // Email Management Funnel
    this.funnels.set('email_management', [
      {
        id: 'email_setup',
        name: 'Email Setup',
        steps: [
          { id: 'connect_account', name: 'Connect Email Account', description: 'Zoho integration', required: true, estimatedTime: 120 },
          { id: 'sync_emails', name: 'Sync Emails', description: 'Initial sync', required: true, estimatedTime: 300 },
          { id: 'configure_filters', name: 'Configure Filters', description: 'Email rules', required: false, estimatedTime: 180 },
        ],
        conversionRate: 0,
        dropOffRate: 0,
      },
      {
        id: 'email_processing',
        name: 'Email Processing',
        steps: [
          { id: 'review_inbox', name: 'Review Inbox', description: 'Check new emails', required: true, estimatedTime: 60 },
          { id: 'categorize', name: 'Categorize Emails', description: 'Sort and tag', required: true, estimatedTime: 180 },
          { id: 'respond_action', name: 'Respond or Action', description: 'Handle emails', required: true, estimatedTime: 300 },
        ],
        conversionRate: 0,
        dropOffRate: 0,
      },
    ]);
  }

  // Start funnel for user
  startFunnel(userId: string, funnelId: string): void {
    const funnel = this.funnels.get(funnelId);
    if (!funnel || funnel.length === 0) return;

    const firstStage = funnel[0];
    const firstStep = firstStage.steps[0];

    const progress: UserFunnelProgress = {
      userId,
      funnelId,
      currentStage: firstStage.id,
      currentStep: firstStep.id,
      completedSteps: [],
      startTime: new Date().toISOString(),
      lastActivity: new Date().toISOString(),
      totalTime: 0,
      completed: false,
    };

    this.userProgress.set(`${userId}_${funnelId}`, progress);
    this.initializeAnalytics(funnelId);
    this.trackFunnelEvent(userId, funnelId, 'funnel_started', {
      stage: firstStage.id,
      step: firstStep.id,
    });
  }

  // Track step completion
  completeStep(userId: string, funnelId: string, stepId: string, success: boolean = true, error?: string): void {
    const progressKey = `${userId}_${funnelId}`;
    const progress = this.userProgress.get(progressKey);
    if (!progress) return;

    const funnel = this.funnels.get(funnelId);
    if (!funnel) return;

    const currentStage = funnel.find(s => s.id === progress.currentStage);
    if (!currentStage) return;

    const step = currentStage.steps.find(s => s.id === stepId);
    if (!step) return;

    // Update progress
    if (success && !progress.completedSteps.includes(stepId)) {
      progress.completedSteps.push(stepId);
    }

    progress.lastActivity = new Date().toISOString();
    const stepTime = this.calculateStepTime(progress, stepId);
    
    // Update analytics
    this.updateStepAnalytics(funnelId, stepId, success, stepTime, error);

    // Track event
    this.trackFunnelEvent(userId, funnelId, success ? 'step_completed' : 'step_failed', {
      stepId,
      stepName: step.name,
      stageId: progress.currentStage,
      time: stepTime,
      error,
    });

    // Move to next step or stage
    if (success) {
      this.moveToNextStep(userId, funnelId);
    }
  }

  // Move to next step in funnel
  private moveToNextStep(userId: string, funnelId: string): void {
    const progressKey = `${userId}_${funnelId}`;
    const progress = this.userProgress.get(progressKey);
    if (!progress) return;

    const funnel = this.funnels.get(funnelId);
    if (!funnel) return;

    const currentStageIndex = funnel.findIndex(s => s.id === progress.currentStage);
    if (currentStageIndex === -1) return;

    const currentStage = funnel[currentStageIndex];
    const currentStepIndex = currentStage.steps.findIndex(s => s.id === progress.currentStep);
    
    // Move to next step in current stage
    if (currentStepIndex < currentStage.steps.length - 1) {
      progress.currentStep = currentStage.steps[currentStepIndex + 1].id;
    }
    // Move to next stage
    else if (currentStageIndex < funnel.length - 1) {
      const nextStage = funnel[currentStageIndex + 1];
      progress.currentStage = nextStage.id;
      progress.currentStep = nextStage.steps[0].id;
    }
    // Complete funnel
    else {
      progress.completed = true;
      progress.totalTime = this.calculateTotalTime(progress);
      this.trackFunnelEvent(userId, funnelId, 'funnel_completed', {
        totalTime: progress.totalTime,
      });
    }

    this.userProgress.set(progressKey, progress);
  }

  // Get user's current progress
  getUserProgress(userId: string, funnelId: string): UserFunnelProgress | null {
    return this.userProgress.get(`${userId}_${funnelId}`) || null;
  }

  // Get funnel analytics
  getFunnelAnalytics(funnelId: string): FunnelAnalytics | null {
    return this.analytics.get(funnelId) || null;
  }

  // Get conversion rates
  getConversionRates(funnelId: string): Map<string, number> {
    const analytics = this.analytics.get(funnelId);
    if (!analytics) return new Map();

    const rates = new Map<string, number>();
    
    analytics.stageAnalytics.forEach((stageData, stageId) => {
      const rate = stageData.entered > 0 ? stageData.completed / stageData.entered : 0;
      rates.set(stageId, rate);
    });

    return rates;
  }

  // Get drop-off points
  getDropOffPoints(funnelId: string): Array<{ stepId: string; dropOffRate: number; totalUsers: number }> {
    const analytics = this.analytics.get(funnelId);
    if (!analytics) return [];

    const dropOffs: Array<{ stepId: string; dropOffRate: number; totalUsers: number }> = [];

    analytics.stepAnalytics.forEach((stepData, stepId) => {
      const dropOffRate = stepData.attempts > 0 ? (stepData.attempts - stepData.completions) / stepData.attempts : 0;
      dropOffs.push({
        stepId,
        dropOffRate,
        totalUsers: stepData.attempts,
      });
    });

    return dropOffs.sort((a, b) => b.dropOffRate - a.dropOffRate);
  }

  // Track funnel events
  private trackFunnelEvent(userId: string, funnelId: string, event: string, properties: Record<string, any>): void {
    // Send to analytics service
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', event, {
        funnel_id: funnelId,
        user_id: userId,
        ...properties,
      });
    }

    console.log(`📊 Funnel Event: ${event}`, { userId, funnelId, properties });
  }

  // Initialize analytics for funnel
  private initializeAnalytics(funnelId: string): void {
    if (!this.analytics.has(funnelId)) {
      this.analytics.set(funnelId, {
        funnelId,
        totalUsers: 0,
        completedUsers: 0,
        currentUsers: new Map(),
        stageAnalytics: new Map(),
        stepAnalytics: new Map(),
      });
    }
  }

  // Update step analytics
  private updateStepAnalytics(funnelId: string, stepId: string, success: boolean, time: number, error?: string): void {
    const analytics = this.analytics.get(funnelId);
    if (!analytics) return;

    if (!analytics.stepAnalytics.has(stepId)) {
      analytics.stepAnalytics.set(stepId, {
        attempts: 0,
        completions: 0,
        errors: 0,
        averageTime: 0,
      });
    }

    const stepData = analytics.stepAnalytics.get(stepId)!;
    stepData.attempts++;
    
    if (success) {
      stepData.completions++;
    }
    
    if (error) {
      stepData.errors++;
    }

    // Update average time
    stepData.averageTime = (stepData.averageTime * (stepData.attempts - 1) + time) / stepData.attempts;
  }

  // Calculate step time
  private calculateStepTime(progress: UserFunnelProgress, stepId: string): number {
    // Simplified time calculation
    return Math.floor(Math.random() * 300) + 30; // 30-330 seconds
  }

  // Calculate total time
  private calculateTotalTime(progress: UserFunnelProgress): number {
    const startTime = new Date(progress.startTime).getTime();
    const endTime = new Date().getTime();
    return Math.floor((endTime - startTime) / 1000);
  }

  // Get funnel completion rate
  getCompletionRate(funnelId: string): number {
    const analytics = this.analytics.get(funnelId);
    if (!analytics || analytics.totalUsers === 0) return 0;
    
    return analytics.completedUsers / analytics.totalUsers;
  }

  // Get average time to complete
  getAverageCompletionTime(funnelId: string): number {
    const analytics = this.analytics.get(funnelId);
    if (!analytics) return 0;

    let totalTime = 0;
    let completedCount = 0;

    analytics.currentUsers.forEach(progress => {
      if (progress.completed) {
        totalTime += progress.totalTime;
        completedCount++;
      }
    });

    return completedCount > 0 ? totalTime / completedCount : 0;
  }
}

// Singleton instance
export const funnelAnalytics = new FunnelAnalyticsService();

// React hook for funnel analytics
export function useFunnelAnalytics() {
  const [userProgress, setUserProgress] = React.useState<Map<string, UserFunnelProgress>>(new Map());
  const [analytics, setAnalytics] = React.useState<Map<string, FunnelAnalytics>>(new Map());

  return {
    startFunnel: funnelAnalytics.startFunnel.bind(funnelAnalytics),
    completeStep: funnelAnalytics.completeStep.bind(funnelAnalytics),
    getUserProgress: funnelAnalytics.getUserProgress.bind(funnelAnalytics),
    getFunnelAnalytics: funnelAnalytics.getFunnelAnalytics.bind(funnelAnalytics),
    getConversionRates: funnelAnalytics.getConversionRates.bind(funnelAnalytics),
    getDropOffPoints: funnelAnalytics.getDropOffPoints.bind(funnelAnalytics),
    getCompletionRate: funnelAnalytics.getCompletionRate.bind(funnelAnalytics),
    getAverageCompletionTime: funnelAnalytics.getAverageCompletionTime.bind(funnelAnalytics),
  };
}

// Higher-order component for funnel tracking
export function withFunnelTracking<P extends object>(
  Component: React.ComponentType<P & { funnel?: any }>,
  funnelId: string
) {
  const WrappedComponent = (props: P) => {
    const funnel = useFunnelAnalytics();

    React.useEffect(() => {
      // Auto-start funnel for authenticated users
      const userId = localStorage.getItem('userId');
      if (userId) {
        funnel.startFunnel(userId, funnelId);
      }
    }, []);

    return <Component {...props} funnel={funnel} />;
  };

  WrappedComponent.displayName = `withFunnelTracking(${Component.displayName || Component.name})`;
  return WrappedComponent;
}
