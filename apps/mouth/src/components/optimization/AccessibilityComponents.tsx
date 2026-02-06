/**
 * Accessibility Components & Utilities
 * 
 * A11y best practices:
 * - Semantic HTML
 * - ARIA labels
 * - Keyboard navigation
 * - Focus management
 * - Screen reader support
 */

import React, { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';

interface SkipLinkProps {
  href: string;
  children: React.ReactNode;
}

/**
 * Skip Link for Keyboard Navigation
 * Allows keyboard users to skip to main content
 */
export function SkipLink({ href, children }: SkipLinkProps) {
  return (
    <a
      href={href}
      className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 
                 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground
                 focus:rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2"
    >
      {children}
    </a>
  );
}

interface VisuallyHiddenProps {
  children: React.ReactNode;
}

/**
 * Visually Hidden Content
 * Visible to screen readers, hidden from sighted users
 */
export function VisuallyHidden({ children }: VisuallyHiddenProps) {
  return (
    <span className="sr-only">
      {children}
    </span>
  );
}

interface AccessibleButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  isLoading?: boolean;
  loadingText?: string;
}

/**
 * Accessible Button with Loading State
 * Announces loading state to screen readers
 */
export function AccessibleButton({
  children,
  isLoading,
  loadingText = 'Loading...',
  disabled,
  'aria-label': ariaLabel,
  ...props
}: AccessibleButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || isLoading}
      aria-label={isLoading ? loadingText : ariaLabel}
      aria-busy={isLoading}
    >
      {isLoading ? (
        <>
          <span className="sr-only">{loadingText}</span>
          <span aria-hidden="true">{children}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}

interface LiveRegionProps {
  children: React.ReactNode;
  assertive?: boolean;
  className?: string;
}

/**
 * ARIA Live Region
 * Announces dynamic content changes to screen readers
 */
export function LiveRegion({ children, assertive = false, className }: LiveRegionProps) {
  return (
    <div
      role="status"
      aria-live={assertive ? 'assertive' : 'polite'}
      aria-atomic="true"
      className={cn('sr-only', className)}
    >
      {children}
    </div>
  );
}

interface FocusTrapProps {
  children: React.ReactNode;
  isActive: boolean;
  onEscape?: () => void;
}

/**
 * Focus Trap for Modals/Dialogs
 * Traps focus within a container for keyboard navigation
 */
export function FocusTrap({ children, isActive, onEscape }: FocusTrapProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isActive) return;

    const container = containerRef.current;
    if (!container) return;

    // Get all focusable elements
    const focusableElements = container.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    // Focus first element
    firstElement?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onEscape) {
        onEscape();
        return;
      }

      if (e.key !== 'Tab') return;

      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement?.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement?.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isActive, onEscape]);

  if (!isActive) return <>{children}</>;

  return (
    <div ref={containerRef} role="dialog" aria-modal="true">
      {children}
    </div>
  );
}

interface AccessibleFormProps {
  children: React.ReactNode;
  onSubmit: (e: React.FormEvent) => void;
  'aria-label'?: string;
  'aria-labelledby'?: string;
}

/**
 * Accessible Form
 * Proper form semantics and ARIA attributes
 */
export function AccessibleForm({
  children,
  onSubmit,
  'aria-label': ariaLabel,
  'aria-labelledby': ariaLabelledBy,
}: AccessibleFormProps) {
  return (
    <form
      onSubmit={onSubmit}
      aria-label={ariaLabel}
      aria-labelledby={ariaLabelledBy}
      noValidate
    >
      {children}
    </form>
  );
}

interface FormFieldProps {
  id: string;
  label: string;
  children: React.ReactNode;
  error?: string;
  hint?: string;
  required?: boolean;
}

/**
 * Accessible Form Field
 * Proper label association and error messaging
 */
export function FormField({
  id,
  label,
  children,
  error,
  hint,
  required,
}: FormFieldProps) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
        {required && <span aria-label="required"> *</span>}
      </label>
      
      {hint && (
        <div id={hintId} className="text-sm text-muted-foreground">
          {hint}
        </div>
      )}
      
      {React.cloneElement(children as React.ReactElement<any>, {
        id,
        'aria-describedby': `${hint ? hintId : ''} ${error ? errorId : ''}`.trim() || undefined,
        'aria-invalid': error ? 'true' : undefined,
        'aria-required': required,
      })}
      
      {error && (
        <div id={errorId} role="alert" className="text-sm text-destructive">
          {error}
        </div>
      )}
    </div>
  );
}

// Accessibility utilities
export const a11yUtils = {
  /**
   * Announce message to screen readers
   */
  announce: (message: string, assertive = false) => {
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', assertive ? 'assertive' : 'polite');
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = message;
    
    document.body.appendChild(announcement);
    setTimeout(() => document.body.removeChild(announcement), 1000);
  },

  /**
   * Trap focus within element
   */
  trapFocus: (element: HTMLElement) => {
    const focusableElements = element.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    return {
      first: focusableElements[0],
      last: focusableElements[focusableElements.length - 1],
    };
  },

  /**
   * Check if element is focusable
   */
  isFocusable: (element: HTMLElement): boolean => {
    return element.matches(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
  },
};
