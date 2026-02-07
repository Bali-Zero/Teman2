'use client';

/**
 * DocumentsErrorBoundary Component
 *
 * Error boundary specifico per la sezione documenti
 * con recovery options specifici per Google Drive
 */

import React from 'react';
import {
  AlertTriangle,
  RefreshCw,
  CloudOff,
  Cloud,
  WifiOff,
  HelpCircle,
  AlertOctagon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { logger } from '@/lib/logger';

interface Props {
  children: React.ReactNode;
  onReset?: () => void;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorType: 'network' | 'auth' | 'rate_limit' | 'permission' | 'unknown';
  errorId: string;
}

/**
 * Generate unique error ID for tracking
 */
function generateErrorId(): string {
  return `doc-err-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Classify error type based on error message and code
 */
function classifyError(error: Error | null): State['errorType'] {
  if (!error) return 'unknown';

  const message = error.message.toLowerCase();

  if (
    message.includes('network') ||
    message.includes('fetch') ||
    message.includes('offline') ||
    message.includes('failed to fetch')
  ) {
    return 'network';
  }

  if (
    message.includes('401') ||
    message.includes('403') ||
    message.includes('unauthorized') ||
    message.includes('auth')
  ) {
    return 'auth';
  }

  if (
    message.includes('429') ||
    message.includes('rate') ||
    message.includes('quota') ||
    message.includes('too many')
  ) {
    return 'rate_limit';
  }

  if (
    message.includes('403') ||
    message.includes('permission') ||
    message.includes('forbidden') ||
    message.includes('access denied')
  ) {
    return 'permission';
  }

  return 'unknown';
}

export class DocumentsErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorType: 'unknown',
      errorId: generateErrorId(),
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorType: classifyError(error),
      errorId: generateErrorId(),
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const { errorId, errorType } = this.state;

    // Log structured error
    logger.error('Documents section error caught', {
      component: 'DocumentsErrorBoundary',
      action: 'error_caught',
      metadata: {
        errorId,
        errorType,
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
      },
    });

    // Send to error tracking service
    if (typeof window !== 'undefined' && (window as any).Sentry) {
      (window as any).Sentry.captureException(error, {
        extra: {
          errorId,
          errorType,
          componentStack: errorInfo.componentStack,
          section: 'documents',
        },
        tags: {
          section: 'documents',
          error_type: errorType,
        },
      });
    }
  }

  handleReset = () => {
    logger.info('User initiated error recovery', {
      component: 'DocumentsErrorBoundary',
      action: 'retry',
      metadata: { errorId: this.state.errorId },
    });

    this.props.onReset?.();
    this.setState({
      hasError: false,
      error: null,
      errorType: 'unknown',
      errorId: generateErrorId(),
    });
  };

  handleReload = () => {
    logger.info('User initiated page reload', {
      component: 'DocumentsErrorBoundary',
      action: 'reload',
      metadata: { errorId: this.state.errorId },
    });
    window.location.reload();
  };

  handleReconnect = () => {
    logger.info('User initiated Drive reconnection', {
      component: 'DocumentsErrorBoundary',
      action: 'reconnect',
      metadata: { errorId: this.state.errorId },
    });
    window.location.href = '/api/drive/auth';
  };

  handleReportIssue = () => {
    const { errorId, errorType, error } = this.state;

    // Open support link with error context
    const supportUrl = new URL('https://support.google.com/drive');
    supportUrl.searchParams.set('error_id', errorId);
    supportUrl.searchParams.set('error_type', errorType);

    logger.info('User opened support documentation', {
      component: 'DocumentsErrorBoundary',
      action: 'support',
      metadata: { errorId },
    });

    window.open(supportUrl.toString(), '_blank');
  };

  render() {
    if (this.state.hasError) {
      // Allow custom fallback
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorFallback
          error={this.state.error}
          errorType={this.state.errorType}
          errorId={this.state.errorId}
          onRetry={this.handleReset}
          onReload={this.handleReload}
          onReconnect={this.handleReconnect}
          onReportIssue={this.handleReportIssue}
        />
      );
    }

    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error: Error | null;
  errorType: State['errorType'];
  errorId: string;
  onRetry: () => void;
  onReload: () => void;
  onReconnect: () => void;
  onReportIssue: () => void;
}

function ErrorFallback({
  error,
  errorType,
  errorId,
  onRetry,
  onReload,
  onReconnect,
  onReportIssue,
}: ErrorFallbackProps) {
  const configs = {
    network: {
      icon: WifiOff,
      title: 'Connection Lost',
      description:
        'Unable to connect to Google Drive. Please check your internet connection and try again.',
      primaryAction: { label: 'Try Again', onClick: onRetry, icon: RefreshCw },
      secondaryAction: { label: 'Reload Page', onClick: onReload },
      color: 'text-orange-500',
      bgColor: 'bg-orange-500/10',
    },
    auth: {
      icon: CloudOff,
      title: 'Session Expired',
      description:
        'Your Google Drive connection has expired. Please reconnect your account to continue.',
      primaryAction: { label: 'Reconnect Drive', onClick: onReconnect, icon: Cloud },
      secondaryAction: { label: 'Try Again', onClick: onRetry },
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/10',
    },
    rate_limit: {
      icon: AlertOctagon,
      title: 'Too Many Requests',
      description: "You've made too many requests. Please wait a moment and try again.",
      primaryAction: { label: 'Wait & Retry', onClick: onRetry, icon: RefreshCw },
      secondaryAction: { label: 'Reload Page', onClick: onReload },
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-500/10',
    },
    permission: {
      icon: AlertTriangle,
      title: 'Access Denied',
      description:
        "You don't have permission to access this file or folder. Contact your administrator.",
      primaryAction: { label: 'Go to Root Folder', onClick: onRetry, icon: RefreshCw },
      secondaryAction: { label: 'Reload Page', onClick: onReload },
      color: 'text-red-500',
      bgColor: 'bg-red-500/10',
    },
    unknown: {
      icon: AlertTriangle,
      title: 'Something Went Wrong',
      description:
        "An unexpected error occurred while loading your documents. We've logged this issue.",
      primaryAction: { label: 'Try Again', onClick: onRetry, icon: RefreshCw },
      secondaryAction: { label: 'Reload Page', onClick: onReload },
      color: 'text-red-500',
      bgColor: 'bg-red-500/10',
    },
  };

  const config = configs[errorType];
  const Icon = config.icon;

  return (
    <div className="min-h-[500px] flex items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div
            className={`mx-auto w-16 h-16 ${config.bgColor} rounded-full flex items-center justify-center mb-4`}
          >
            <Icon className={`w-8 h-8 ${config.color}`} />
          </div>
          <CardTitle className="text-xl">{config.title}</CardTitle>
          <CardDescription>{config.description}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Error ID for support */}
          <div className="bg-slate-50 dark:bg-slate-900 p-3 rounded-md">
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">
              Error Reference ID
            </p>
            <code className="text-sm font-mono text-slate-700 dark:text-slate-300">{errorId}</code>
            <p className="text-xs text-slate-400 mt-1">Include this ID when contacting support</p>
          </div>

          {/* Development error details */}
          {process.env.NODE_ENV === 'development' && error && (
            <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded-md text-sm">
              <p className="font-medium text-gray-900 dark:text-gray-100">Error details:</p>
              <p className="text-gray-600 dark:text-gray-400 font-mono text-xs mt-1">
                {error.message}
              </p>
              {error.stack && (
                <pre className="mt-2 text-xs text-gray-500 overflow-auto max-h-32">
                  {error.stack.split('\n').slice(0, 5).join('\n')}
                </pre>
              )}
            </div>
          )}

          {/* Rate limit specific guidance */}
          {errorType === 'rate_limit' && (
            <div className="bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-200 dark:border-yellow-900 p-3 rounded-md">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                <strong>Tip:</strong> Google Drive API has rate limits. Large operations may need to
                be done in batches. Wait 60 seconds before retrying.
              </p>
            </div>
          )}

          {/* Permission specific guidance */}
          {errorType === 'permission' && (
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 p-3 rounded-md">
              <p className="text-sm text-red-800 dark:text-red-200">
                <strong>Note:</strong> If you believe this is an error, verify that you have been
                granted access to this folder in Google Drive.
              </p>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex flex-col gap-2">
          <Button onClick={config.primaryAction.onClick} className="w-full gap-2">
            <config.primaryAction.icon className="w-4 h-4" />
            {config.primaryAction.label}
          </Button>

          <Button variant="outline" onClick={config.secondaryAction.onClick} className="w-full">
            {config.secondaryAction.label}
          </Button>

          <Button
            variant="ghost"
            onClick={onReportIssue}
            className="w-full gap-2 text-muted-foreground"
          >
            <HelpCircle className="w-4 h-4" />
            Get Help
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

/**
 * Inline error component for smaller errors
 */
export function DocumentsInlineError({
  message,
  errorId,
  onRetry,
  showReportButton = false,
}: {
  message: string;
  errorId?: string;
  onRetry?: () => void;
  showReportButton?: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      <AlertTriangle className="w-10 h-10 text-amber-500 mb-3" />
      <p className="text-sm font-medium text-slate-600 dark:text-slate-400 text-center">
        {message}
      </p>
      {errorId && (
        <code className="mt-2 text-xs font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
          ID: {errorId}
        </code>
      )}
      {onRetry && (
        <Button onClick={onRetry} variant="outline" size="sm" className="mt-4 gap-2">
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </Button>
      )}
    </div>
  );
}

/**
 * Error logging utility for async operations
 */
export function logDocumentsError(
  operation: string,
  error: unknown,
  context?: Record<string, any>
) {
  const errorMessage = error instanceof Error ? error.message : String(error);
  const errorId = generateErrorId();

  logger.error(`Documents operation failed: ${operation}`, {
    component: 'Documents',
    action: operation,
    metadata: {
      errorId,
      error: errorMessage,
      ...context,
    },
  });

  return errorId;
}
