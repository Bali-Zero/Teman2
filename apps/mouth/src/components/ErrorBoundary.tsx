'use client';

import React from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error?: Error; retry: () => void }>;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ error, errorInfo });
    
    // Log error for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
    
    // Track error for analytics
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'exception', {
        description: error.message,
        fatal: false,
      });
    }
  }

  retry = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError) {
      const FallbackComponent = this.props.fallback || DefaultErrorFallback;
      return <FallbackComponent error={this.state.error} retry={this.retry} />;
    }

    return this.props.children;
  }
}

function DefaultErrorFallback({ error, retry }: { error?: Error; retry: () => void }) {
  return (
    <div className="min-h-[400px] flex items-center justify-center">
      <div className="text-center space-y-4 p-6 rounded-lg border border-red-500/20 bg-red-500/10 max-w-md">
        <div className="w-16 h-16 mx-auto bg-red-500/20 rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <div>
          <h3 className="text-lg font-semibold text-red-500">Something went wrong</h3>
          <p className="text-sm text-red-500/80 mt-1">
            {error?.message || 'An unexpected error occurred'}
          </p>
        </div>
        <div className="space-y-2">
          <button
            onClick={retry}
            className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
          >
            Try Again
          </button>
          <button
            onClick={() => window.location.reload()}
            className="ml-2 px-4 py-2 border border-red-500 text-red-500 rounded-lg hover:bg-red-500/10 transition-colors"
          >
            Reload Page
          </button>
        </div>
        {process.env.NODE_ENV === 'development' && error && (
          <details className="mt-4 text-left">
            <summary className="text-xs text-red-500/60 cursor-pointer">Error Details</summary>
            <pre className="text-xs text-red-500/40 mt-2 whitespace-pre-wrap">
              {error.stack}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

// Specialized error boundaries for different parts of the app
export function DashboardErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary
      fallback={DashboardErrorFallback}
      onError={(error, errorInfo) => {
        // Track dashboard-specific errors
        console.error('Dashboard Error:', error, errorInfo);
      }}
    >
      {children}
    </ErrorBoundary>
  );
}

function DashboardErrorFallback({ error, retry }: { error?: Error; retry: () => void }) {
  return (
    <div className="space-y-8">
      <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-yellow-500/20 rounded-full flex items-center justify-center">
            <svg className="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-yellow-500">Dashboard Error</h3>
            <p className="text-sm text-yellow-500/80">
              Failed to load dashboard data. Please try again.
            </p>
          </div>
          <button
            onClick={retry}
            className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    </div>
  );
}

export function ApiErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary
      fallback={ApiErrorFallback}
      onError={(error, errorInfo) => {
        // Track API-specific errors
        console.error('API Error:', error, errorInfo);
      }}
    >
      {children}
    </ErrorBoundary>
  );
}

function ApiErrorFallback({ error, retry }: { error?: Error; retry: () => void }) {
  return (
    <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-red-500/20 rounded-full flex items-center justify-center">
          <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <div className="flex-1">
          <h4 className="font-semibold text-red-500">Connection Error</h4>
          <p className="text-sm text-red-500/80">
            Unable to connect to the server. Please check your connection.
          </p>
        </div>
        <button
          onClick={retry}
          className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600 transition-colors"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
