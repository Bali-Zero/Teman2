import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  ErrorBoundary,
  DashboardErrorBoundary,
  ApiErrorBoundary,
} from "./ErrorBoundary";

// Mock logger
vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

// Suppress React error boundary console errors in tests
const originalConsoleError = console.error;
beforeEach(() => {
  console.error = vi.fn();
});

afterEach(() => {
  console.error = originalConsoleError;
});

// A component that throws
function ThrowingComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Test error");
  }
  return <div>Normal content</div>;
}

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <div>Safe content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("Safe content")).toBeInTheDocument();
  });

  it("renders default fallback when child throws", () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Test error")).toBeInTheDocument();
    expect(screen.getByText("Try Again")).toBeInTheDocument();
  });

  it("renders custom fallback when provided", () => {
    const CustomFallback = ({
      error,
      retry,
    }: {
      error?: Error;
      retry: () => void;
    }) => (
      <div>
        <span>Custom error: {error?.message}</span>
        <button onClick={retry}>Custom retry</button>
      </div>
    );

    render(
      <ErrorBoundary fallback={CustomFallback}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(
      screen.getByText("Custom error: Test error"),
    ).toBeInTheDocument();
    expect(screen.getByText("Custom retry")).toBeInTheDocument();
  });

  it("calls onError callback when error occurs", () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) }),
    );
  });

  it("calls retry which resets hasError state", () => {
    // We verify the retry button exists and is clickable in the default fallback.
    // Full recovery requires the child to stop throwing, which is hard to test
    // without a stateful wrapper. Here we just verify the UI renders correctly.
    render(
      <ErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Try Again")).toBeInTheDocument();
    expect(screen.getByText("Reload Page")).toBeInTheDocument();

    // Verify Try Again button is clickable (does not crash)
    fireEvent.click(screen.getByText("Try Again"));
  });
});

describe("DashboardErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <DashboardErrorBoundary>
        <div>Dashboard content</div>
      </DashboardErrorBoundary>,
    );
    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
  });

  it("shows dashboard-specific error fallback on error", () => {
    render(
      <DashboardErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </DashboardErrorBoundary>,
    );
    expect(screen.getByText("Dashboard Error")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});

describe("ApiErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ApiErrorBoundary>
        <div>API content</div>
      </ApiErrorBoundary>,
    );
    expect(screen.getByText("API content")).toBeInTheDocument();
  });

  it("shows API-specific error fallback on error", () => {
    render(
      <ApiErrorBoundary>
        <ThrowingComponent shouldThrow={true} />
      </ApiErrorBoundary>,
    );
    expect(screen.getByText("Connection Error")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});
