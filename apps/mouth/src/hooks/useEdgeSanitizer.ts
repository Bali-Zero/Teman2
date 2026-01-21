import { useCallback } from 'react';
import { useGeminiNano } from './useGeminiNano';
import { EDGE_PROMPTS } from '../lib/edge/prompts';
import { logger } from '@/lib/logger';

interface UseEdgeSanitizerReturn {
  sanitize: (text: string) => Promise<string>;
  isReady: boolean;
  status: string;
}

export const useEdgeSanitizer = (): UseEdgeSanitizerReturn => {
  const { generate, isReady, status } = useGeminiNano();

  const sanitize = useCallback(
    async (text: string): Promise<string> => {
      if (!text) return '';

      // 1. Fast Pass: Regex Redaction (Deterministic)
      // We do this first to catch obvious structured data immediately and reduce hallucination risk for these patterns.
      const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
      // Basic phone regex for finding numbers with 10-15 digits
      const phoneRegex = /\b\d{10,15}\b/g;

      let preProcessed = text.replace(emailRegex, '[EMAIL]').replace(phoneRegex, '[PHONE]');

      // 2. Intelligent Pass: Gemini Nano
      // Catches context-dependent entities like Names or Addresses.
      if (isReady) {
        try {
          const prompt = `${EDGE_PROMPTS.SANITIZATION_SYSTEM} "${preProcessed}"\nOutput:`;
          const result = await generate(prompt);
          return result.trim();
        } catch (error) {
          logger.warn('Edge Sanitization failed, returning regex-cleaned text', { component: 'useEdgeSanitizer', action: 'sanitize' }, error instanceof Error ? error : new Error(String(error)));
          return preProcessed;
        }
      }

      return preProcessed;
    },
    [generate, isReady]
  );

  return {
    sanitize,
    isReady,
    status,
  };
};
