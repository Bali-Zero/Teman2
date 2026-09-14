"use client";

import {
  useState,
  useEffect,
  createContext,
  useContext,
  useCallback,
  useId,
  useRef,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Info,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Toast Types
/**
 * `slip` is the R19 addition (SAETTA-R19K K1c2): the paper slip that follows a
 * completed row and offers to take it back. The four existing variants are
 * untouched — a shared component gains a key, it does not get restyled under
 * the products already using it.
 */
export type ToastVariant = "success" | "error" | "warning" | "info" | "slip";

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
  addToast: (toast: Omit<Toast, "id">) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;
  /** Hold a toast's auto-dismiss open (true) or let it go again (false). */
  holdToast: (id: string, held: boolean) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

/**
 * Toast Provider - Wrap your app with this to enable toasts
 */
/**
 * How long an optimistic action can be taken back. Six seconds is the frozen
 * concept's window, and it is exported because the row that starts the action
 * has to schedule its commit against the SAME number — two clocks would let a
 * click land after the row was already gone.
 */
export const SLIP_UNDO_MS = 6000;

/**
 * How long a toast stays, as a pure function of what it is. Pulled out of the
 * provider so the window can be read and asserted without a clock: a duration
 * that can only be observed by waiting is a duration nobody checks.
 */
export function toastDuration(
  variant: ToastVariant,
  explicit?: number,
): number {
  if (explicit !== undefined) return explicit;
  if (variant === "error") return 8000;
  // The slip's six seconds ARE the Undo window: when the slip goes, the chance
  // goes, so the two can never be set to different numbers.
  if (variant === "slip") return SLIP_UNDO_MS;
  return 5000;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<
    Map<string, { handle: ReturnType<typeof setTimeout>; remaining: number }>
  >(new Map());

  const addToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const newToast: Toast = {
      ...toast,
      id,
      duration: toastDuration(toast.variant, toast.duration),
      dismissible: toast.dismissible ?? true,
    };

    setToasts((prev) => [...prev, newToast]);

    // Auto-dismiss. The handle is kept so a SLIP can be held open while the
    // person is reaching for its Undo — see holdToast below. The four shipped
    // variants never call that, so their timer behaves exactly as before.
    if (newToast.duration && newToast.duration > 0) {
      const handle = setTimeout(() => {
        timers.current.delete(id);
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, newToast.duration);
      timers.current.set(id, { handle, remaining: newToast.duration });
    }

    return id;
  }, []);

  /**
   * Hold a toast open, or let it go again.
   *
   * WCAG 2.2.1 (Timing Adjustable): the slip offers an ACTION on a six-second
   * clock, and a clock that cannot be stopped is a clock that outruns anyone
   * navigating by keyboard or screen reader. Found by the council's second
   * seat. Pointer and focus both hold it, because the mouse is not the only
   * way to arrive.
   *
   * Deliberately NOT a full remaining-time accounting: on release the window
   * restarts at its full length. That is more generous than the spec asks and
   * far simpler than tracking elapsed time across renders — and being generous
   * with an Undo window is the safe direction to err.
   */
  const holdToast = useCallback((id: string, held: boolean) => {
    const entry = timers.current.get(id);
    if (!entry) return;
    if (held) {
      clearTimeout(entry.handle);
      return;
    }
    const handle = setTimeout(() => {
      timers.current.delete(id);
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, entry.remaining);
    timers.current.set(id, { handle, remaining: entry.remaining });
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearToasts = useCallback(() => {
    setToasts([]);
  }, []);

  return (
    <ToastContext.Provider
      value={{ toasts, addToast, removeToast, clearToasts, holdToast }}
    >
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
    throw new Error("useToast must be used within a ToastProvider");
  }

  const { addToast, removeToast, clearToasts } = context;
  const success = useCallback(
    (title: string, description?: string) =>
      addToast({ title, description, variant: "success" }),
    [addToast],
  );
  const error = useCallback(
    (title: string, description?: string, action?: Toast["action"]) =>
      addToast({ title, description, variant: "error", action }),
    [addToast],
  );
  const warning = useCallback(
    (title: string, description?: string) =>
      addToast({ title, description, variant: "warning" }),
    [addToast],
  );
  /**
   * The slip: a completed row, and six seconds to take it back. The action is
   * required — a slip with nothing to undo is just an info toast wearing
   * different paper.
   */
  const slip = useCallback(
    (
      title: string,
      action: NonNullable<Toast["action"]>,
      description?: string,
    ) => addToast({ title, description, variant: "slip", action }),
    [addToast],
  );
  const info = useCallback(
    (title: string, description?: string) =>
      addToast({ title, description, variant: "info" }),
    [addToast],
  );

  return {
    toast: addToast,
    dismiss: removeToast,
    clear: clearToasts,
    success,
    error,
    warning,
    info,
    slip,
  };
}

/**
 * Toast Container - Renders all active toasts
 */
function ToastContainer() {
  const context = useContext(ToastContext);
  if (!context) return null;

  const { toasts, removeToast, holdToast } = context;

  return (
    <div
      className="fixed bottom-4 right-4 z-[var(--z-toast)] flex flex-col gap-2 pointer-events-none"
      role="region"
      aria-label="Notifications"
      aria-live="polite"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <ToastItem
            key={toast.id}
            toast={toast}
            onDismiss={() => removeToast(toast.id)}
            onHold={(held) => holdToast(toast.id, held)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

/**
 * Individual Toast Item
 */
function ToastItem({
  toast,
  onDismiss,
  onHold,
}: {
  toast: Toast;
  onDismiss: () => void;
  onHold?: (held: boolean) => void;
}) {
  const id = useId();

  const variantConfig = {
    success: {
      icon: CheckCircle,
      iconClass: "text-[var(--success)]",
      borderClass: "border-l-[var(--success)]",
      bgClass: "bg-[var(--success-muted)]",
    },
    error: {
      icon: AlertCircle,
      iconClass: "text-[var(--error)]",
      borderClass: "border-l-[var(--error)]",
      bgClass: "bg-[var(--error-muted)]",
    },
    warning: {
      icon: AlertTriangle,
      iconClass: "text-[var(--warning)]",
      borderClass: "border-l-[var(--warning)]",
      bgClass: "bg-[var(--warning-muted)]",
    },
    info: {
      icon: Info,
      iconClass: "text-[var(--info)]",
      borderClass: "border-l-[var(--info)]",
      bgClass: "bg-[var(--info-muted)]",
    },
    slip: {
      // No icon and no coloured bar: a slip is paper, and what it says is in
      // the words. The four above keep theirs exactly as they were.
      icon: null,
      iconClass: "",
      borderClass: "",
      bgClass: "",
    },
  };

  const config = variantConfig[toast.variant];
  const Icon = config.icon;
  const isSlip = toast.variant === "slip";

  return (
    <motion.div
      layout
      // WCAG 2.2.1 — only the slip holds, because only the slip puts an ACTION
      // on a clock. Pointer AND focus, since the mouse is not the only way to
      // reach a button. The other four never call this, so their timing is
      // byte-identical to what shipped.
      onMouseEnter={isSlip && onHold ? () => onHold(true) : undefined}
      onMouseLeave={isSlip && onHold ? () => onHold(false) : undefined}
      onFocusCapture={isSlip && onHold ? () => onHold(true) : undefined}
      onBlurCapture={isSlip && onHold ? () => onHold(false) : undefined}
      initial={{ opacity: 0, x: 50, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 50, scale: 0.9 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn(
        "pointer-events-auto flex items-start gap-3 p-4 pr-10",
        "min-w-[300px] max-w-[420px]",
        isSlip
          ? // Square, on the control boundary, on the card ground: the R19
            // slip is printed, not floated.
            "rounded-none border border-[var(--line-control)] bg-[var(--bz-card)]"
          : "rounded-lg border border-[var(--border)] border-l-4 bg-[var(--background-elevated)] shadow-lg",
        config.borderClass,
      )}
      role="alert"
      aria-labelledby={`${id}-title`}
      aria-describedby={toast.description ? `${id}-desc` : undefined}
    >
      {/* Icon */}
      {Icon && (
        <div className={cn("flex-shrink-0 mt-0.5", config.iconClass)}>
          <Icon size={20} aria-hidden="true" />
        </div>
      )}

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
              "mt-2 inline-flex items-center gap-1.5 text-xs font-medium",
              isSlip
                ? "min-h-11 rounded-none border border-[var(--line-control)] px-3 font-[700] text-[var(--tx-pure)] transition-colors focus-ring"
                : "text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors focus-ring rounded",
            )}
          >
            {/* The refresh glyph means "try again"; an Undo is not a retry. */}
            {!isSlip && <RefreshCw size={12} />}
            {toast.action.label}
          </button>
        )}
      </div>

      {/* Dismiss button */}
      {toast.dismissible && (
        <button
          onClick={onDismiss}
          className={cn(
            "absolute top-3 right-3 p-1 rounded",
            "text-[var(--foreground-muted)] hover:text-[var(--foreground)]",
            "hover:bg-[var(--background-hover)] transition-colors",
            "focus-ring",
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
