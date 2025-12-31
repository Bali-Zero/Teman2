'use client';

import { Component, ReactNode } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, RefreshCw, Home, Bug } from 'lucide-react';
import { Button } from './button';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  showDetails?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

/**
 * Error Boundary component with retry capability and detailed error display.
 * Catches JavaScript errors anywhere in child component tree.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });
    this.props.onError?.(error, errorInfo);

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('ErrorBoundary caught an error:', error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleGoHome = () => {
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorFallback
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          onRetry={this.handleRetry}
          onGoHome={this.handleGoHome}
          showDetails={this.props.showDetails}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * Default error fallback UI
 */
interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
  onRetry: () => void;
  onGoHome: () => void;
  showDetails?: boolean;
}

function ErrorFallback({
  error,
  errorInfo,
  onRetry,
  onGoHome,
  showDetails = process.env.NODE_ENV === 'development',
}: ErrorFallbackProps) {
  return (
    <div className="min-h-[400px] flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full text-center"
      >
        {/* Error Icon */}
        <div className="mb-6 flex justify-center">
          <div className="p-4 rounded-full bg-[var(--error-muted)]">
            <AlertTriangle className="w-12 h-12 text-[var(--error)]" />
          </div>
        </div>

        {/* Error Title */}
        <h2 className="text-xl font-semibold text-[var(--foreground)] mb-2">
          Something went wrong
        </h2>

        {/* Error Description */}
        <p className="text-sm text-[var(--foreground-muted)] mb-6">
          We encountered an unexpected error. Please try again or return to the home page.
        </p>

        {/* Error Details (Development) */}
        {showDetails && error && (
          <details className="mb-6 text-left">
            <summary className="cursor-pointer text-xs font-medium text-[var(--foreground-muted)] hover:text-[var(--foreground)] flex items-center gap-2 justify-center">
              <Bug size={14} />
              View error details
            </summary>
            <div className="mt-3 p-4 rounded-lg bg-[var(--background-secondary)] border border-[var(--border)] overflow-auto">
              <p className="text-xs font-mono text-[var(--error)] mb-2">
                {error.name}: {error.message}
              </p>
              {errorInfo?.componentStack && (
                <pre className="text-[10px] font-mono text-[var(--foreground-muted)] whitespace-pre-wrap max-h-[200px] overflow-auto">
                  {errorInfo.componentStack}
                </pre>
              )}
            </div>
          </details>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 justify-center">
          <Button
            onClick={onRetry}
            className="gap-2 focus-ring"
            aria-label="Try again"
          >
            <RefreshCw size={16} />
            Try Again
          </Button>
          <Button
            variant="outline"
            onClick={onGoHome}
            className="gap-2 focus-ring"
            aria-label="Go to home page"
          >
            <Home size={16} />
            Go Home
          </Button>
        </div>
      </motion.div>
    </div>
  );
}

/**
 * Functional wrapper for ErrorBoundary (for easier use in RSC)
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name || 'Component'})`;

  return WrappedComponent;
}

export default ErrorBoundary;
