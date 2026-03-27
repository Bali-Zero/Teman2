'use client';

/**
 * CRMErrorBoundary Component
 *
 * Error boundary specifico per sezioni CRM
 */

import React from 'react';
import { logger } from '@/lib/logger';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onReset?: () => void;
  section?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class CRMErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logger.error(`CRM Error in ${this.props.section || 'unknown'}`, { note: errorInfo.componentStack ?? undefined }, error);
    this.setState({ errorInfo });

    // Send to error tracking service
    if (typeof window !== 'undefined' && (window as any).Sentry) {
      (window as any).Sentry.captureException(error, {
        extra: {
          componentStack: errorInfo.componentStack,
          section: this.props.section,
        },
      });
    }
  }

  handleReset = () => {
    this.props.onReset?.();
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/clients';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[400px] flex items-center justify-center p-4">
          <Card className="w-full max-w-lg">
            <CardHeader className="text-center">
              <div className="mx-auto w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-4">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <CardTitle className="text-xl">Something went wrong</CardTitle>
              <CardDescription>
                {this.props.section
                  ? `An error occurred in the ${this.props.section} section.`
                  : 'An unexpected error occurred in the CRM.'}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {this.state.error && (
                <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded-md text-sm">
                  <p className="font-medium text-gray-900 dark:text-gray-100">Error details:</p>
                  <p className="text-gray-600 dark:text-gray-400 font-mono text-xs mt-1">
                    {this.state.error.message}
                  </p>
                  {process.env.NODE_ENV === 'development' && this.state.errorInfo && (
                    <pre className="mt-2 text-xs text-gray-500 dark:text-gray-500 overflow-auto max-h-32">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  )}
                </div>
              )}

              <div className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
                <p>You can try:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Refreshing the page</li>
                  <li>Going back to the clients list</li>
                  <li>Contacting support if the problem persists</li>
                </ul>
              </div>
            </CardContent>

            <CardFooter className="flex flex-wrap gap-2 justify-center">
              <Button variant="outline" onClick={this.handleGoHome} className="gap-2">
                <Home className="w-4 h-4" />
                Go to Clients
              </Button>
              <Button onClick={this.handleReset} className="gap-2">
                <RefreshCw className="w-4 h-4" />
                Try Again
              </Button>
              <Button variant="secondary" onClick={this.handleReload}>
                Reload Page
              </Button>
            </CardFooter>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * HOC per wrappare componenti CRM con ErrorBoundary
 */
export function withCRMErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  section?: string
) {
  return function WithCRMErrorBoundaryWrapper(props: P) {
    return (
      <CRMErrorBoundary section={section}>
        <Component {...props} />
      </CRMErrorBoundary>
    );
  };
}

/**
 * Fallback component per stati di caricamento/errore
 */
export function CRMErrorFallback({
  message = 'Unable to load data',
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="w-full">
      <CardContent className="pt-6 text-center">
        <AlertTriangle className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
        <p className="text-gray-600 dark:text-gray-400">{message}</p>
        {onRetry && (
          <Button onClick={onRetry} variant="outline" className="mt-4">
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton loader per liste CRM
 */
export function CRMSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-20 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}
