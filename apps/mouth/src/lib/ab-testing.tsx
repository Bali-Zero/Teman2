/**
 * A/B Testing System for Dashboard Layout and Features
 * Enterprise-grade experimentation framework with GA4 integration
 */

interface Experiment {
  name: string;
  variants: Variant[];
  trafficAllocation: number; // 0-1, percentage of traffic to include
  targeting?: {
    userRoles?: string[];
    userProperties?: Record<string, any>;
  };
}

interface Variant {
  id: string;
  name: string;
  weight: number; // 0-1, relative weight within experiment
  config: Record<string, any>;
}

interface ExperimentConfig {
  experiments: Experiment[];
  forceVariants?: Record<string, string>; // For testing/debugging
}

class ABTestingService {
  private experiments: Map<string, Experiment> = new Map();
  private assignedVariants: Map<string, string> = new Map();
  private userId: string | null = null;

  initialize(config: ExperimentConfig, userId: string) {
    this.userId = userId;
    
    // Load experiments
    config.experiments.forEach(experiment => {
      this.experiments.set(experiment.name, experiment);
    });

    // Load saved variant assignments from localStorage
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('ab_test_variants');
      if (saved) {
        this.assignedVariants = new Map(JSON.parse(saved));
      }
    }

    // Apply forced variants (for testing)
    if (config.forceVariants) {
      Object.entries(config.forceVariants).forEach(([experiment, variant]) => {
        this.assignedVariants.set(experiment, variant);
      });
    }
  }

  // Get the variant assigned to a user for a specific experiment
  getVariant(experimentName: string): string | null {
    const experiment = this.experiments.get(experimentName);
    if (!experiment) return null;

    // Check if user is already assigned
    if (this.assignedVariants.has(experimentName)) {
      return this.assignedVariants.get(experimentName)!;
    }

    // Check if user should be included in experiment
    if (!this.shouldIncludeUser(experiment)) {
      return null;
    }

    // Assign variant based on weighted random selection
    const variant = this.assignVariant(experiment);
    if (variant) {
      this.assignedVariants.set(experimentName, variant);
      this.saveAssignments();
      
      // Track experiment view
      if (typeof window !== 'undefined' && window.gtag) {
        window.gtag('event', 'experiment_view', {
          experiment_name: experimentName,
          variant: variant,
        });
      }
    }

    return variant;
  }

  // Get the configuration for a specific variant
  getVariantConfig(experimentName: string, variantId?: string): Record<string, any> {
    const variant = variantId || this.getVariant(experimentName);
    if (!variant) return {};

    const experiment = this.experiments.get(experimentName);
    if (!experiment) return {};

    const variantConfig = experiment.variants.find(v => v.id === variant);
    return variantConfig?.config || {};
  }

  // Check if a user should be included in an experiment
  private shouldIncludeUser(experiment: Experiment): boolean {
    if (!this.userId) return false;

    // Check traffic allocation
    const hash = this.hashString(this.userId + experiment.name);
    const normalizedHash = hash / 0xFFFFFFFF;
    if (normalizedHash > experiment.trafficAllocation) {
      return false;
    }

    // Check targeting criteria
    if (experiment.targeting) {
      // TODO: Implement targeting logic based on user properties
      // For now, include all users in allocated traffic
    }

    return true;
  }

  // Assign a variant to a user based on weights
  private assignVariant(experiment: Experiment): string | null {
    const totalWeight = experiment.variants.reduce((sum, v) => sum + v.weight, 0);
    if (totalWeight === 0) return null;

    const hash = this.hashString(this.userId + experiment.name + Date.now().toString());
    const normalizedHash = hash / 0xFFFFFFFF;
    const randomValue = normalizedHash * totalWeight;

    let cumulativeWeight = 0;
    for (const variant of experiment.variants) {
      cumulativeWeight += variant.weight;
      if (randomValue <= cumulativeWeight) {
        return variant.id;
      }
    }

    return experiment.variants[0]?.id || null;
  }

  // Simple hash function for consistent assignment
  private hashString(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }

  // Save assignments to localStorage
  private saveAssignments() {
    if (typeof window !== 'undefined') {
      localStorage.setItem('ab_test_variants', JSON.stringify(Array.from(this.assignedVariants.entries())));
    }
  }

  // Track conversion for an experiment
  trackConversion(experimentName: string, goal: string, value?: number) {
    const variant = this.getVariant(experimentName);
    if (!variant) return;

    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'conversion', {
        experiment_name: experimentName,
        variant: variant,
        goal: goal,
        value: value,
      });
    }
  }

  // Get all active experiments for the current user
  getActiveExperiments(): Array<{ name: string; variant: string }> {
    const active: Array<{ name: string; variant: string }> = [];
    
    this.experiments.forEach((experiment, name) => {
      const variant = this.getVariant(name);
      if (variant) {
        active.push({ name, variant });
      }
    });

    return active;
  }
}

// Default experiment configurations
const DEFAULT_EXPERIMENTS: ExperimentConfig = {
  experiments: [
    {
      name: 'dashboard_layout',
      trafficAllocation: 1.0, // 100% of users
      variants: [
        {
          id: 'control',
          name: 'Current Layout',
          weight: 0.5,
          config: {
            widgetLayout: 'grid',
            showEmailStats: true,
            compactMode: false,
          },
        },
        {
          id: 'compact',
          name: 'Compact Layout',
          weight: 0.25,
          config: {
            widgetLayout: 'compact',
            showEmailStats: true,
            compactMode: true,
          },
        },
        {
          id: 'minimal',
          name: 'Minimal Layout',
          weight: 0.25,
          config: {
            widgetLayout: 'minimal',
            showEmailStats: false,
            compactMode: true,
          },
        },
      ],
    },
    {
      name: 'email_integration',
      trafficAllocation: 0.5, // 50% of users
      variants: [
        {
          id: 'enabled',
          name: 'Email Enabled',
          weight: 0.7,
          config: {
            showEmailWidget: true,
            emailNotifications: true,
            emailActions: ['delete', 'read', 'reply'],
          },
        },
        {
          id: 'limited',
          name: 'Limited Email',
          weight: 0.3,
          config: {
            showEmailWidget: true,
            emailNotifications: false,
            emailActions: ['delete', 'read'],
          },
        },
      ],
    },
    {
      name: 'widget_order',
      trafficAllocation: 0.3, // 30% of users
      variants: [
        {
          id: 'default',
          name: 'Default Order',
          weight: 0.6,
          config: {
            order: ['stats', 'practices', 'interactions', 'email'],
          },
        },
        {
          id: 'email_first',
          name: 'Email First',
          weight: 0.4,
          config: {
            order: ['email', 'stats', 'practices', 'interactions'],
          },
        },
      ],
    },
  ],
};

// Singleton instance
export const abTesting = new ABTestingService();

// React hook for A/B testing
export function useABTesting() {
  return {
    getVariant: abTesting.getVariant.bind(abTesting),
    getVariantConfig: abTesting.getVariantConfig.bind(abTesting),
    trackConversion: abTesting.trackConversion.bind(abTesting),
    getActiveExperiments: abTesting.getActiveExperiments.bind(abTesting),
  };
}

// Higher-order component for A/B testing
import React from 'react';

export function withABTesting<P extends object>(
  Component: React.ComponentType<P & { abTestConfig?: Record<string, any> }>,
  experimentName: string
) {
  const WrappedComponent = (props: P) => {
    const { getVariantConfig } = useABTesting();
    const config = getVariantConfig(experimentName);

    return <Component {...props} abTestConfig={config} />;
  };

  WrappedComponent.displayName = `withABTesting(${Component.displayName || Component.name})`;
  return WrappedComponent;
}

// Initialize A/B testing
export function initializeABTesting(userId: string, customConfig?: ExperimentConfig) {
  const config = customConfig || DEFAULT_EXPERIMENTS;
  abTesting.initialize(config, userId);
}
