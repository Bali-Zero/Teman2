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
  HelpCircle
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

interface Props {
  children: React.ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorType: 'network' | 'auth' | 'rate_limit' | 'unknown';
}

export class DocumentsErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorType: 'unknown' };
  }

  static getDerivedStateFromError(error: Error): State {
    const errorMessage = error.message.toLowerCase();
    let errorType: State['errorType'] = 'unknown';

    if (errorMessage.includes('network') || errorMessage.includes('fetch') || errorMessage.includes('offline')) {
      errorType = 'network';
    } else if (errorMessage.includes('401') || errorMessage.includes('403') || errorMessage.includes('auth')) {
      errorType = 'auth';
    } else if (errorMessage.includes('429') || errorMessage.includes('rate') || errorMessage.includes('quota')) {
      errorType = 'rate_limit';
    }

    return { hasError: true, error, errorType };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Documents Error:', error, errorInfo);

    // Send to error tracking
    if (typeof window !== 'undefined' && (window as any).Sentry) {
      (window as any).Sentry.captureException(error, {
        extra: {
          componentStack: errorInfo.componentStack,
          section: 'documents',
          errorType: this.state.errorType,
        },
        tags: {
          section: 'documents',
        },
      });
    }
  }

  handleReset = () => {
    this.props.onReset?.();
    this.setState({ hasError: false, error: null, errorType: 'unknown' });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleReconnect = () => {
    // Try to reconnect to Google Drive
    window.location.href = '/api/drive/auth';
  };

  render() {
    if (this.state.hasError) {
      return <ErrorFallback 
        error={this.state.error}
        errorType={this.state.errorType}
        onRetry={this.handleReset}
        onReload={this.handleReload}
        onReconnect={this.handleReconnect}
      />;
    }

    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error: Error | null;
  errorType: 'network' | 'auth' | 'rate_limit' | 'unknown';
  onRetry: () => void;
  onReload: () => void;
  onReconnect: () => void;
}

function ErrorFallback({ error, errorType, onRetry, onReload, onReconnect }: ErrorFallbackProps) {
  const configs = {
    network: {
      icon: WifiOff,
      title: 'Connection Lost',
      description: 'Unable to connect to Google Drive. Please check your internet connection.',
      primaryAction: { label: 'Try Again', onClick: onRetry, icon: RefreshCw },
      secondaryAction: { label: 'Reload Page', onClick: onReload },
    },
    auth: {
      icon: CloudOff,
      title: 'Session Expired',
      description: 'Your Google Drive connection has expired. Please reconnect your account.',
      primaryAction: { label: 'Reconnect Drive', onClick: onReconnect, icon: Cloud },
      secondaryAction: { label: 'Try Again', onClick: onRetry },
    },
    rate_limit: {
      icon: AlertTriangle,
      title: 'Too Many Requests',
      description: 'You\'ve made too many requests. Please wait a moment and try again.',
      primaryAction: { label: 'Wait & Retry', onClick: onRetry, icon: RefreshCw },
      secondaryAction: { label: 'Reload Page', onClick: onReload },
    },
    unknown: {
      icon: AlertTriangle,
      title: 'Something Went Wrong',
      description: 'An unexpected error occurred while loading your documents.',
      primaryAction: { label: 'Try Again', onClick: onRetry, icon: RefreshCw },
      secondaryAction: { label: 'Reload Page', onClick: onReload },
    },
  };

  const config = configs[errorType];
  const Icon = config.icon;

  return (
    <div className="min-h-[500px] flex items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-950 rounded-full flex items-center justify-center mb-4">
            <Icon className="w-8 h-8 text-red-600 dark:text-red-400" />
          </div>
          <CardTitle className="text-xl">{config.title}</CardTitle>
          <CardDescription>{config.description}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {process.env.NODE_ENV === 'development' && error && (
            <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded-md text-sm">
              <p className="font-medium text-gray-900 dark:text-gray-100">Error details:</p>
              <p className="text-gray-600 dark:text-gray-400 font-mono text-xs mt-1">
                {error.message}
              </p>
            </div>
          )}

          {errorType === 'rate_limit' && (
            <div className="bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-200 dark:border-yellow-900 p-3 rounded-md">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                <strong>Tip:</strong> Google Drive API has rate limits. 
                Large operations may need to be done in batches.
              </p>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex flex-col gap-2">
          <Button 
            onClick={config.primaryAction.onClick} 
            className="w-full gap-2"
          >
            <config.primaryAction.icon className="w-4 h-4" />
            {config.primaryAction.label}
          </Button>
          
          <Button 
            variant="outline" 
            onClick={config.secondaryAction.onClick}
            className="w-full"
          >
            {config.secondaryAction.label}
          </Button>

          <Button 
            variant="ghost" 
            onClick={() => window.open('https://support.google.com/drive', '_blank')}
            className="w-full gap-2 text-muted-foreground"
          >
            <HelpCircle className="w-4 h-4" />
            Google Drive Help
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
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4">
      <AlertTriangle className="w-10 h-10 text-amber-500 mb-3" />
      <p className="text-sm font-medium text-slate-600 dark:text-slate-400 text-center">
        {message}
      </p>
      {onRetry && (
        <Button onClick={onRetry} variant="outline" size="sm" className="mt-4 gap-2">
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </Button>
      )}
    </div>
  );
}
