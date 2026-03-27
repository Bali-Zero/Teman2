'use client';

/**
 * Error Boundary Component
 *
 * Catch JavaScript errors anywhere in child component tree
 */

import React, { Component, ReactNode } from 'react';
import { logger } from '@/lib/logger';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to error reporting service
    this.props.onError?.(error, errorInfo);

    logger.error('ErrorBoundary caught error', { note: errorInfo.componentStack ?? undefined }, error);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-6 rounded-lg bg-red-50 border border-red-200">
          <h2 className="text-lg font-semibold text-red-800 mb-2">Something went wrong</h2>
          <p className="text-red-600 text-sm">Please refresh the page or try again later.</p>
          {process.env.NODE_ENV !== 'production' && this.state.error && (
            <pre className="mt-4 p-4 bg-red-100 rounded text-xs overflow-auto text-red-900">
              {this.state.error.message}
              {'\n'}
              {this.state.error.stack}
            </pre>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Simple error boundary with reset
 */
export function ErrorBoundaryWithReset({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const [key, setKey] = React.useState(0);

  return (
    <ErrorBoundary
      key={key}
      fallback={
        fallback || (
          <div className="p-6 text-center">
            <p className="text-gray-600 mb-4">Something went wrong</p>
            <button
              onClick={() => setKey((k) => k + 1)}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Try Again
            </button>
          </div>
        )
      }
    >
      {children}
    </ErrorBoundary>
  );
}
