"use client";

/**
 * PortalErrorBoundary Component
 *
 * Error boundary specifico per il client portal
 * Più user-friendly rispetto a quello del workspace
 */

import React from "react";
import { logger } from "@/lib/logger";
import { AlertTriangle, RefreshCw, Home, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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

export class PortalErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logger.error(
      `Portal Error in ${this.props.section || "unknown"}`,
      { note: errorInfo.componentStack ?? undefined },
      error,
    );
    this.setState({ errorInfo });

    // Send to error tracking
    if (typeof window !== "undefined" && (window as any).Sentry) {
      (window as any).Sentry.captureException(error, {
        extra: {
          componentStack: errorInfo.componentStack,
          section: this.props.section,
          isPortal: true,
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
    window.location.href = "/portal";
  };

  handleContactSupport = () => {
    window.location.href = "/portal/messages?new=true";
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[500px] flex items-center justify-center p-4">
          <Card className="w-full max-w-md border-red-200 dark:border-red-900">
            <CardHeader className="text-center">
              <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-950 rounded-full flex items-center justify-center mb-4">
                <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
              </div>
              <CardTitle className="text-xl">Something went wrong</CardTitle>
              <CardDescription>
                We apologize for the inconvenience. Our team has been notified.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {process.env.NODE_ENV === "development" && this.state.error && (
                <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded-md text-sm">
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    Technical details:
                  </p>
                  <p className="text-gray-600 dark:text-gray-400 font-mono text-xs mt-1">
                    {this.state.error.message}
                  </p>
                </div>
              )}

              <div className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
                <p>What you can do:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Try refreshing the page</li>
                  <li>Return to your dashboard</li>
                  <li>Contact our support team</li>
                </ul>
              </div>
            </CardContent>

            <CardFooter className="flex flex-col gap-2">
              <div className="flex gap-2 w-full">
                <Button
                  variant="outline"
                  onClick={this.handleGoHome}
                  className="flex-1 gap-2"
                >
                  <Home className="w-4 h-4" />
                  Dashboard
                </Button>
                <Button onClick={this.handleReset} className="flex-1 gap-2">
                  <RefreshCw className="w-4 h-4" />
                  Try Again
                </Button>
              </div>
              <Button
                variant="secondary"
                onClick={this.handleContactSupport}
                className="w-full gap-2"
              >
                <MessageCircle className="w-4 h-4" />
                Contact Support
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
 * HOC per wrappare componenti portal con ErrorBoundary
 */
export function withPortalErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  section?: string,
) {
  return function WithPortalErrorBoundaryWrapper(props: P) {
    return (
      <PortalErrorBoundary section={section}>
        <Component {...props} />
      </PortalErrorBoundary>
    );
  };
}

// Uses portal design tokens (rgba(30,30,35,0.7) glass + var(--bz-border)) so
// skeletons match the actual card surface instead of reading as a different
// shade of gray. Every page had its own hand-rolled skeleton before this.
const PORTAL_SKELETON_CARD: React.CSSProperties = {
  background: "rgba(30,30,35,0.7)",
  borderColor: "rgba(255,255,255,0.05)",
  backdropFilter: "blur(24px)",
};

/**
 * Skeleton loader per card del portale
 */
export function PortalCardSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={`rounded-xl border p-6 animate-pulse ${className ?? ""}`}
      style={PORTAL_SKELETON_CARD}
    >
      <div
        className="h-5 w-1/3 rounded mb-4"
        style={{ background: "var(--bz-border)" }}
      />
      <div className="space-y-3">
        <div
          className="h-4 w-full rounded"
          style={{ background: "var(--bz-border)", opacity: 0.6 }}
        />
        <div
          className="h-4 w-2/3 rounded"
          style={{ background: "var(--bz-border)", opacity: 0.4 }}
        />
      </div>
    </div>
  );
}

/**
 * Skeleton loader per liste del portale
 */
export function PortalListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="h-20 rounded-xl border animate-pulse"
          style={PORTAL_SKELETON_CARD}
        />
      ))}
    </div>
  );
}

/**
 * Loading state per pagine portal
 */
export function PortalPageLoader() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div
          className="w-10 h-10 border-2 rounded-full animate-spin"
          style={{
            borderColor: "var(--bz-accent-warm)",
            borderTopColor: "transparent",
          }}
        />
        <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
          Loading…
        </p>
      </div>
    </div>
  );
}
