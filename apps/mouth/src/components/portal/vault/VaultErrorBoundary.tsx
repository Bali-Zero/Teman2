"use client";
import React from "react";
import { logger } from "@/lib/logger";

interface State {
  hasError: boolean;
}

interface BProps {
  children: React.ReactNode;
}

export class VaultErrorBoundary extends React.Component<BProps, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    logger.error(
      "[VaultErrorBoundary]",
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
          className="bz-product-panel rounded-lg p-6 text-center"
        >
          <p className="text-sm text-[var(--bz-text-2)] mb-4">
            Unable to load your vault. Our team has been notified.
          </p>
          <button
            onClick={this.handleRetry}
            className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text)] hover:underline"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
