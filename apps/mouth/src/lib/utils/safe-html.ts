/**
 * Safe HTML sanitization utilities for dangerouslySetInnerHTML.
 *
 * Uses DOMPurify to prevent XSS when rendering HTML from external sources
 * (API responses, user input, AI-generated content).
 *
 * Usage:
 *   <div dangerouslySetInnerHTML={safeHtml(apiHtmlContent)} />
 */

import DOMPurify from "dompurify";

/** DOMPurify config subset used by our sanitizers. */
interface SanitizeConfig {
  ALLOWED_TAGS?: string[];
  ALLOWED_ATTR?: string[];
  ALLOW_DATA_ATTR?: boolean;
  ADD_ATTR?: string[];
  RETURN_DOM?: false;
  RETURN_DOM_FRAGMENT?: false;
}

/**
 * Default DOMPurify configuration for rich HTML content.
 * Allows safe formatting tags while blocking scripts, event handlers, etc.
 */
const DEFAULT_CONFIG: SanitizeConfig = {
  ALLOWED_TAGS: [
    // Text formatting
    "b",
    "i",
    "em",
    "strong",
    "u",
    "s",
    "sub",
    "sup",
    "mark",
    "small",
    // Block elements
    "p",
    "br",
    "hr",
    "div",
    "span",
    "blockquote",
    // Lists
    "ul",
    "ol",
    "li",
    // Code
    "code",
    "pre",
    // Links
    "a",
    // Headings
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    // Tables
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    // Images (for rich content like LKPM reports)
    "img",
  ],
  ALLOWED_ATTR: [
    "href",
    "target",
    "rel",
    "class",
    "style",
    "src",
    "alt",
    "width",
    "height",
    "colspan",
    "rowspan",
  ],
  ALLOW_DATA_ATTR: false,
  ADD_ATTR: ["target"],
  RETURN_DOM: false,
  RETURN_DOM_FRAGMENT: false,
};

/**
 * Sanitize HTML content and return an object compatible with
 * React's dangerouslySetInnerHTML prop.
 *
 * @param html - Raw HTML string from an external source
 * @param config - Optional DOMPurify config override
 * @returns Object with sanitized __html property
 *
 * @example
 * ```tsx
 * <div dangerouslySetInnerHTML={safeHtml(pack.html_content)} />
 * ```
 */
export function safeHtml(
  html: string,
  config?: SanitizeConfig,
): { __html: string } {
  if (typeof window === "undefined") {
    // Server-side: escape all HTML to prevent SSR XSS
    return { __html: escapeHtmlEntities(html || "") };
  }

  const sanitized = DOMPurify.sanitize(html || "", {
    ...DEFAULT_CONFIG,
    ...config,
    RETURN_DOM: false,
    RETURN_DOM_FRAGMENT: false,
  });

  return { __html: sanitized as string };
}

/**
 * Sanitize HTML with a restrictive config suitable for chat messages.
 * Only allows inline formatting: bold, italic, links, line breaks.
 */
export function safeHtmlChat(html: string): { __html: string } {
  return safeHtml(html, {
    ALLOWED_TAGS: ["b", "strong", "i", "em", "a", "br", "code", "span"],
    ALLOWED_ATTR: ["href", "target", "rel", "class"],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Sanitize the output of renderMiniMarkdown.
 * The input is already partially escaped (< > &), but we still run
 * DOMPurify to ensure no edge-case injection through the bold/link regex.
 */
export function safeMiniMarkdown(
  rendered: { __html: string },
): { __html: string } {
  if (typeof window === "undefined") {
    return rendered; // Already escaped by renderMiniMarkdown
  }

  const sanitized = DOMPurify.sanitize(rendered.__html, {
    ALLOWED_TAGS: ["strong", "a", "br"],
    ALLOWED_ATTR: ["href", "target", "rel", "class", "style"],
    ALLOW_DATA_ATTR: false,
    RETURN_DOM: false,
    RETURN_DOM_FRAGMENT: false,
  });

  return { __html: sanitized as string };
}

/**
 * Server-safe HTML entity escaping.
 */
function escapeHtmlEntities(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
