/**
 * API Client - Backward Compatibility Re-export
 * 
 * This file maintains backward compatibility with existing imports.
 * The actual implementation has been refactored into modules under lib/api/
 * 
 * @deprecated Import from '@/lib/api' instead of '@/lib/api.ts' for better tree-shaking
 */
export * from './api/index';
