import { useCallback } from "react";
import { logger } from "@/lib/logger";

interface UseEdgeSanitizerReturn {
  sanitize: (text: string) => Promise<string>;
  isReady: boolean;
  status: string;
}

/**
 * Edge sanitizer hook for PII redaction.
 * Uses deterministic regex-based redaction for fast client-side sanitization.
 *
 * Note: AI-based sanitization temporarily disabled (useGeminiNano removed).
 * Regex-based approach provides reliable, fast PII detection.
 */
export const useEdgeSanitizer = (): UseEdgeSanitizerReturn => {
  const sanitize = useCallback(async (text: string): Promise<string> => {
    if (!text) return "";

    // Regex-based Redaction (Deterministic)
    // Fast client-side PII detection without AI dependencies

    // Email pattern
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;

    // Phone pattern (10-15 digits)
    const phoneRegex = /\b\d{10,15}\b/g;

    // Indonesian phone pattern (+62 or 08)
    const idPhoneRegex = /\b(\+62|62|0)8[1-9][0-9]{7,11}\b/g;

    // Tax ID / NPWP pattern (Indonesian)
    const npwpRegex =
      /\b\d{2}[\s.]?\d{3}[\s.]?\d{3}[\s.]?\d{1}[\s-]?\d{3}[\s.]?\d{3}\b/g;

    const sanitized = text
      .replace(emailRegex, "[EMAIL]")
      .replace(idPhoneRegex, "[PHONE]")
      .replace(phoneRegex, "[PHONE]")
      .replace(npwpRegex, "[NPWP]");

    logger.debug("Text sanitized");

    return sanitized;
  }, []);

  return {
    sanitize,
    isReady: true, // Always ready - uses regex only
    status: "ready",
  };
};
