/**
 * Optimized Hooks Barrel Export
 *
 * Performance-optimized React hooks
 */

export { useDebounce, useDebouncedCallback } from "./useDebounce";
export { useThrottledCallback, useThrottle } from "./useThrottle";
export {
  useIntersectionObserver,
  useIsVisible,
  useHasEnteredViewport,
} from "./useIntersectionObserver";
export { useLocalStorage, useSessionStorage } from "./useLocalStorage";
export {
  useMediaQuery,
  breakpoints,
  useIsMobile,
  useIsTablet,
  useIsDesktop,
  usePrefersReducedMotion,
  usePrefersDarkMode,
} from "./useMediaQuery";
export { usePrevious, usePreviousWithCompare, useHistory } from "./usePrevious";

// Web Worker hook for INP optimization
export { useWebWorker, type UseWebWorkerReturn } from "../useWebWorker";
