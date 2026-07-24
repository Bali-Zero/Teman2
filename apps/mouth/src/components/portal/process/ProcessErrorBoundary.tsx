"use client";
import React from "react";
import { logger } from "@/lib/logger";

interface State {
  hasError: boolean;
}

interface BProps {
  children: React.ReactNode;
}

export class ProcessErrorBoundary extends React.Component<BProps, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    logger.error(
      "[ProcessErrorBoundary]",
      { note: info.componentStack ?? undefined },
      error,
    );
  }

  handleRetry = () => this.setState({ hasError: false });

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="rounded-lg p-6 text-center border"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <p className="text-sm text-[var(--bz-copper-text,var(--tx-secondary))] mb-4">
            Unable to load details. Our team has been notified.
          </p>
          <button
            onClick={this.handleRetry}
            className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] hover:underline"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
