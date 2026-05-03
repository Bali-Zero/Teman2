/**
 * ThinkingIndicator - Re-export from modular structure
 *
 * This file maintains backward compatibility with existing imports.
 * The component has been refactored into smaller modules under ./thinking/
 *
 * Structure:
 * - thinking/types.ts         - Type definitions
 * - thinking/constants.tsx    - Configuration and static data
 * - thinking/utils.ts         - Utility functions
 * - thinking/ThinkingAvatar.tsx    - Animated avatar component
 * - thinking/ThinkingProgress.tsx  - Progress bar component
 * - thinking/ThinkingActivities.tsx - Activity list component
 * - thinking/ThinkingPhases.tsx    - Phase visualizer component
 * - thinking/ThinkingIndicator.tsx - Main component
 */

export { ThinkingIndicator } from "./thinking";
export type { ThinkingIndicatorProps, GenericStep, Activity } from "./thinking";
