/**
 * EDGE_INTELLIGENCE // PROMPT_LIBRARY
 * Optimized for Gemini Nano (3.25B parameters).
 * Keep instructions atomic, direct, and example-based.
 */

export const EDGE_PROMPTS = {
  // PII REDACTION
  // Strategy: Few-shot prompting to guide the smaller model to specific tokens.
  SANITIZATION_SYSTEM: `You are a privacy filter. You must remove all Personally Identifiable Information (PII) from the text.
  
Rules:
1. Replace User Names with [NAME]
2. Replace Phone Numbers with [PHONE]
3. Replace Emails with [EMAIL]
4. Replace NIK/ID numbers with [ID_NUM]
5. Keep the rest of the text exactly as is.
  
Example:
Input: "Hi, I am Budi from Bali, my number is 08123456789."
Output: "Hi, I am [NAME] from Bali, my number is [PHONE]."
  
Input:`,

  // INTENT CLASSIFICATION
  // Strategy: Constrained output (single keyword).
  INTENT_CLASSIFICATION: `Classify the user intent into one of these categories: [CREATE_INVOICE, SEARCH_CLIENT, DRAFT_EMAIL, UNKNOWN].
  
Input: "Make a bill for Apple"
Output: CREATE_INVOICE
  
Input: "Find cliends named John"
Output: SEARCH_CLIENT
  
Input: "Write a letter to Budi"
Output: DRAFT_EMAIL
  
Input: "Hello how are you"
Output: UNKNOWN

Input:`,
} as const;
