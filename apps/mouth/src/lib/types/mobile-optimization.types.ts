/**
 * Mobile Optimization Types
 * Type-safe definitions for mobile optimization service
 */

export interface MobileOptimizationReturn {
  breakpoint: "mobile" | "tablet" | "desktop";
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isClient: boolean;
  getVariant: (experimentName: string) => string | null;
  getMobileConfig: (experimentName: string) => {
    layout: "stacked" | "tabbed" | "carousel" | "grid";
    navigation: "bottom" | "side" | "hamburger";
    widgets: string[];
    interactions: "swipe" | "tap" | "longpress";
    animations: boolean;
    compactMode: boolean;
  } | null;
  getResponsiveClasses: (baseClasses: string) => string;
  getMobileWidgets: () => string[];
  getNavigationStyle: () => "bottom" | "side" | "hamburger";
  getInteractionMode: () => "swipe" | "tap" | "longpress";
  areAnimationsEnabled: () => boolean;
  isCompactMode: () => boolean;
}
