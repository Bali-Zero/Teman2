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
          className="rounded-lg p-6 text-center border border-white/10"
        >
          <p className="text-sm text-[#c9a96e]/70 mb-4">
            Unable to load details. Our team has been notified.
          </p>
          <button
            onClick={this.handleRetry}
            className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
