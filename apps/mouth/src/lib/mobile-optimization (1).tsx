/**
 * Mobile optimization with responsive A/B testing
 * Adapts dashboard layout and features for mobile devices
 */

import React from 'react';

interface MobileExperiment {
  name: string;
  variants: MobileVariant[];
  deviceTypes: ('mobile' | 'tablet' | 'desktop')[];
  breakpoints: {
    mobile: number;
    tablet: number;
    desktop: number;
  };
}

interface MobileVariant {
  id: string;
  name: string;
  weight: number;
  config: {
    layout: 'stacked' | 'tabbed' | 'carousel' | 'grid';
    navigation: 'bottom' | 'side' | 'hamburger';
    widgets: string[];
    interactions: 'swipe' | 'tap' | 'longpress';
    animations: boolean;
    compactMode: boolean;
  };
}

class MobileOptimizationService {
  private experiments: Map<string, MobileExperiment> = new Map();
  private currentBreakpoint: 'mobile' | 'tablet' | 'desktop' = 'desktop';
  private assignedVariants: Map<string, string> = new Map();
  private listeners: Set<() => void> = new Set();

  constructor() {
    this.initializeExperiments();
    this.setupBreakpointListener();
    this.detectCurrentBreakpoint();
  }

  // Initialize mobile-specific experiments
  private initializeExperiments(): void {
    const mobileExperiments: MobileExperiment[] = [
      {
        name: 'mobile_layout',
        deviceTypes: ['mobile', 'tablet'],
        breakpoints: { mobile: 768, tablet: 1024, desktop: 1200 },
        variants: [
          {
            id: 'stacked',
            name: 'Stacked Layout',
            weight: 0.4,
            config: {
              layout: 'stacked',
              navigation: 'bottom',
              widgets: ['stats', 'quick_actions', 'recent_items'],
              interactions: 'swipe',
              animations: true,
              compactMode: true,
            },
          },
          {
            id: 'tabbed',
            name: 'Tabbed Layout',
            weight: 0.35,
            config: {
              layout: 'tabbed',
              navigation: 'bottom',
              widgets: ['stats', 'quick_actions', 'notifications'],
              interactions: 'tap',
              animations: true,
              compactMode: true,
            },
          },
          {
            id: 'carousel',
            name: 'Carousel Layout',
            weight: 0.25,
            config: {
              layout: 'carousel',
              navigation: 'side',
              widgets: ['stats', 'quick_actions'],
              interactions: 'swipe',
              animations: true,
              compactMode: false,
            },
          },
        ],
      },
      {
        name: 'mobile_navigation',
        deviceTypes: ['mobile'],
        breakpoints: { mobile: 768, tablet: 1024, desktop: 1200 },
        variants: [
          {
            id: 'bottom_nav',
            name: 'Bottom Navigation',
            weight: 0.6,
            config: {
              layout: 'grid',
              navigation: 'bottom',
              widgets: ['home', 'cases', 'email', 'settings'],
              interactions: 'tap',
              animations: true,
              compactMode: true,
            },
          },
          {
            id: 'hamburger',
            name: 'Hamburger Menu',
            weight: 0.4,
            config: {
              layout: 'grid',
              navigation: 'hamburger',
              widgets: ['home', 'cases', 'email', 'settings'],
              interactions: 'tap',
              animations: false,
              compactMode: true,
            },
          },
        ],
      },
      {
        name: 'mobile_interactions',
        deviceTypes: ['mobile', 'tablet'],
        breakpoints: { mobile: 768, tablet: 1024, desktop: 1200 },
        variants: [
          {
            id: 'swipe_gestures',
            name: 'Swipe Gestures',
            weight: 0.5,
            config: {
              layout: 'stacked',
              navigation: 'bottom',
              widgets: ['stats', 'quick_actions'],
              interactions: 'swipe',
              animations: true,
              compactMode: true,
            },
          },
          {
            id: 'tap_only',
            name: 'Tap Only',
            weight: 0.5,
            config: {
              layout: 'stacked',
              navigation: 'bottom',
              widgets: ['stats', 'quick_actions'],
              interactions: 'tap',
              animations: false,
              compactMode: true,
            },
          },
        ],
      },
    ];

    mobileExperiments.forEach(experiment => {
      this.experiments.set(experiment.name, experiment);
    });
  }

  // Setup breakpoint listener
  private setupBreakpointListener(): void {
    const updateBreakpoint = () => {
      const newBreakpoint = this.detectBreakpoint();
      if (newBreakpoint !== this.currentBreakpoint) {
        this.currentBreakpoint = newBreakpoint;
        this.notifyListeners();
        console.log(`📱 Breakpoint changed to: ${newBreakpoint}`);
      }
    };

    // Listen for window resize
    window.addEventListener('resize', updateBreakpoint);
    window.addEventListener('orientationchange', updateBreakpoint);
  }

  // Detect current breakpoint
  private detectBreakpoint(): 'mobile' | 'tablet' | 'desktop' {
    const width = window.innerWidth;
    if (width < 768) return 'mobile';
    if (width < 1024) return 'tablet';
    return 'desktop';
  }

  private detectCurrentBreakpoint(): void {
    this.currentBreakpoint = this.detectBreakpoint();
  }

  // Get variant for current device
  getVariant(experimentName: string): string | null {
    const experiment = this.experiments.get(experimentName);
    if (!experiment) return null;

    // Check if experiment applies to current device
    if (!experiment.deviceTypes.includes(this.currentBreakpoint)) {
      return null;
    }

    // Check if already assigned
    if (this.assignedVariants.has(experimentName)) {
      return this.assignedVariants.get(experimentName)!;
    }

    // Assign variant based on device and user
    const variant = this.assignVariant(experiment);
    if (variant) {
      this.assignedVariants.set(experimentName, variant);
      this.saveAssignments();
    }

    return variant;
  }

  // Get mobile-specific configuration
  getMobileConfig(experimentName: string): Record<string, any> {
    const variant = this.getVariant(experimentName);
    if (!variant) return {};

    const experiment = this.experiments.get(experimentName);
    if (!experiment) return {};

    const variantConfig = experiment.variants.find(v => v.id === variant);
    return variantConfig?.config || {};
  }

  // Assign variant based on device and user
  private assignVariant(experiment: MobileExperiment): string | null {
    const userId = this.getUserId();
    if (!userId) return null;

    // Use device-specific hashing for consistent assignment
    const deviceKey = `${userId}_${experiment.name}_${this.currentBreakpoint}`;
    const hash = this.hashString(deviceKey);
    const normalizedHash = hash / 0xFFFFFFFF;

    // Weighted selection
    let cumulativeWeight = 0;
    for (const variant of experiment.variants) {
      cumulativeWeight += variant.weight;
      if (normalizedHash <= cumulativeWeight) {
        return variant.id;
      }
    }

    return experiment.variants[0]?.id || null;
  }

  // Simple hash function
  private hashString(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash);
  }

  // Get user ID
  private getUserId(): string {
    return localStorage.getItem('userId') || 'anonymous';
  }

  // Save assignments to localStorage
  private saveAssignments(): void {
    const key = `mobile_ab_variants_${this.currentBreakpoint}`;
    localStorage.setItem(key, JSON.stringify(Array.from(this.assignedVariants.entries())));
  }

  // Load assignments from localStorage
  private loadAssignments(): void {
    const key = `mobile_ab_variants_${this.currentBreakpoint}`;
    const saved = localStorage.getItem(key);
    if (saved) {
      this.assignedVariants = new Map(JSON.parse(saved));
    }
  }

  // Notify listeners of changes
  private notifyListeners(): void {
    this.listeners.forEach(listener => listener());
  }

  // Subscribe to breakpoint changes
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  // Get current breakpoint
  getCurrentBreakpoint(): 'mobile' | 'tablet' | 'desktop' {
    return this.currentBreakpoint;
  }

  // Check if mobile
  isMobile(): boolean {
    return this.currentBreakpoint === 'mobile';
  }

  // Check if tablet
  isTablet(): boolean {
    return this.currentBreakpoint === 'tablet';
  }

  // Check if desktop
  isDesktop(): boolean {
    return this.currentBreakpoint === 'desktop';
  }

  // Get responsive classes
  getResponsiveClasses(baseClasses: string, mobileClasses?: string, tabletClasses?: string): string {
    const classes = [baseClasses];
    if (mobileClasses && this.isMobile()) classes.push(mobileClasses);
    if (tabletClasses && this.isTablet()) classes.push(tabletClasses);
    return classes.join(' ');
  }

  // Get mobile-optimized widget list
  getMobileWidgets(): string[] {
    const config = this.getMobileConfig('mobile_layout');
    return config.widgets || ['stats', 'quick_actions'];
  }

  // Get navigation style
  getNavigationStyle(): 'bottom' | 'side' | 'hamburger' {
    const config = this.getMobileConfig('mobile_navigation');
    return config.navigation || 'bottom';
  }

  // Get interaction mode
  getInteractionMode(): 'swipe' | 'tap' | 'longpress' {
    const config = this.getMobileConfig('mobile_interactions');
    return config.interactions || 'tap';
  }

  // Check if animations are enabled
  areAnimationsEnabled(): boolean {
    const config = this.getMobileConfig('mobile_layout');
    return config.animations !== false;
  }

  // Check if compact mode is enabled
  isCompactMode(): boolean {
    const config = this.getMobileConfig('mobile_layout');
    return config.compactMode === true;
  }
}

// Singleton instance
export const mobileOptimization = new MobileOptimizationService();

// React hook for mobile optimization
export function useMobileOptimization() {
  const [breakpoint, setBreakpoint] = React.useState<'mobile' | 'tablet' | 'desktop'>('desktop');
  const [isClient, setIsClient] = React.useState(false);

  React.useEffect(() => {
    setIsClient(true);
    setBreakpoint(mobileOptimization.getCurrentBreakpoint());

    const unsubscribe = mobileOptimization.subscribe(() => {
      setBreakpoint(mobileOptimization.getCurrentBreakpoint());
    });

    return unsubscribe;
  }, []);

  return {
    breakpoint,
    isMobile: breakpoint === 'mobile',
    isTablet: breakpoint === 'tablet',
    isDesktop: breakpoint === 'desktop',
    isClient,
    getVariant: mobileOptimization.getVariant.bind(mobileOptimization),
    getMobileConfig: mobileOptimization.getMobileConfig.bind(mobileOptimization),
    getResponsiveClasses: mobileOptimization.getResponsiveClasses.bind(mobileOptimization),
    getMobileWidgets: mobileOptimization.getMobileWidgets.bind(mobileOptimization),
    getNavigationStyle: mobileOptimization.getNavigationStyle.bind(mobileOptimization),
    getInteractionMode: mobileOptimization.getInteractionMode.bind(mobileOptimization),
    areAnimationsEnabled: mobileOptimization.areAnimationsEnabled.bind(mobileOptimization),
    isCompactMode: mobileOptimization.isCompactMode.bind(mobileOptimization),
  };
}

// Higher-order component for mobile optimization
export function withMobileOptimization<P extends object>(
  Component: React.ComponentType<P & { mobile?: any }>
) {
  const WrappedComponent = (props: P) => {
    const mobile = useMobileOptimization();

    return <Component {...props} mobile={mobile} />;
  };

  WrappedComponent.displayName = `withMobileOptimization(${Component.displayName || Component.name})`;
  return WrappedComponent;
}
