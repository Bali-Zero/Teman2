'use client';

import { useState, useEffect, createContext, useContext, useCallback, useId } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

// Toast Types
export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
  dismissible?: boolean;
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

/**
 * Toast Provider - Wrap your app with this to enable toasts
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const newToast: Toast = {
      ...toast,
      id,
      duration: toast.duration ?? (toast.variant === 'error' ? 8000 : 5000),
      dismissible: toast.dismissible ?? true,
    };

    setToasts((prev) => [...prev, newToast]);

    // Auto-dismiss
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, newToast.duration);
    }

    return id;
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearToasts = useCallback(() => {
    setToasts([]);
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, clearToasts }}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  );
}

/**
 * Hook to use toasts
 */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }

  const { addToast, removeToast, clearToasts } = context;

  return {
    toast: addToast,
    dismiss: removeToast,
    clear: clearToasts,
    // Convenience methods
    success: (title: string, description?: string) =>
      addToast({ title, description, variant: 'success' }),
    error: (title: string, description?: string, action?: Toast['action']) =>
      addToast({ title, description, variant: 'error', action }),
    warning: (title: string, description?: string) =>
      addToast({ title, description, variant: 'warning' }),
    info: (title: string, description?: string) =>
      addToast({ title, description, variant: 'info' }),
  };
}

/**
 * Toast Container - Renders all active toasts
 */
function ToastContainer() {
  const context = useContext(ToastContext);
  if (!context) return null;

  const { toasts, removeToast } = context;

  return (
    <div
      className="fixed bottom-4 right-4 z-[var(--z-toast)] flex flex-col gap-2 pointer-events-none"
      role="region"
      aria-label="Notifications"
      aria-live="polite"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={() => removeToast(toast.id)} />
        ))}
      </AnimatePresence>
    </div>
  );
}

/**
 * Individual Toast Item
 */
function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const id = useId();

  const variantConfig = {
    success: {
      icon: CheckCircle,
      iconClass: 'text-[var(--success)]',
      borderClass: 'border-l-[var(--success)]',
      bgClass: 'bg-[var(--success-muted)]',
    },
    error: {
      icon: AlertCircle,
      iconClass: 'text-[var(--error)]',
      borderClass: 'border-l-[var(--error)]',
      bgClass: 'bg-[var(--error-muted)]',
    },
    warning: {
      icon: AlertTriangle,
      iconClass: 'text-[var(--warning)]',
      borderClass: 'border-l-[var(--warning)]',
      bgClass: 'bg-[var(--warning-muted)]',
    },
    info: {
      icon: Info,
      iconClass: 'text-[var(--info)]',
      borderClass: 'border-l-[var(--info)]',
      bgClass: 'bg-[var(--info-muted)]',
    },
  };

  const config = variantConfig[toast.variant];
  const Icon = config.icon;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 50, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 50, scale: 0.9 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={cn(
        'pointer-events-auto flex items-start gap-3 p-4 pr-10',
        'min-w-[300px] max-w-[420px]',
        'rounded-lg border border-[var(--border)] border-l-4',
        'bg-[var(--background-elevated)] shadow-lg',
        config.borderClass
      )}
      role="alert"
      aria-labelledby={`${id}-title`}
      aria-describedby={toast.description ? `${id}-desc` : undefined}
    >
      {/* Icon */}
      <div className={cn('flex-shrink-0 mt-0.5', config.iconClass)}>
        <Icon size={20} aria-hidden="true" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p
          id={`${id}-title`}
          className="text-sm font-medium text-[var(--foreground)]"
        >
          {toast.title}
        </p>
        {toast.description && (
          <p
            id={`${id}-desc`}
            className="mt-1 text-xs text-[var(--foreground-muted)] line-clamp-2"
          >
            {toast.description}
          </p>
        )}
        {toast.action && (
          <button
            onClick={toast.action.onClick}
            className={cn(
              'mt-2 inline-flex items-center gap-1.5 text-xs font-medium',
              'text-[var(--accent)] hover:text-[var(--accent-hover)]',
              'transition-colors focus-ring rounded'
            )}
          >
            <RefreshCw size={12} />
            {toast.action.label}
          </button>
        )}
      </div>

      {/* Dismiss button */}
      {toast.dismissible && (
        <button
          onClick={onDismiss}
          className={cn(
            'absolute top-3 right-3 p-1 rounded',
            'text-[var(--foreground-muted)] hover:text-[var(--foreground)]',
            'hover:bg-[var(--background-hover)] transition-colors',
            'focus-ring'
          )}
          aria-label="Dismiss notification"
        >
          <X size={14} />
        </button>
      )}
    </motion.div>
  );
}

export default ToastProvider;
