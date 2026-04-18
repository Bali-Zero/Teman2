import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProcessErrorBoundary } from "./ProcessErrorBoundary";

// Mock logger (the boundary uses @/lib/logger instead of console.error).
vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

function Throw({ when }: { when: boolean }) {
  if (when) throw new Error("boom");
  return <span>ok</span>;
}

describe("ProcessErrorBoundary", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Silence React's own error boundary noise in stderr during tests.
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("renders children when no error", () => {
    render(
      <ProcessErrorBoundary>
        <Throw when={false} />
      </ProcessErrorBoundary>,
    );
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("catches thrown error and shows fallback", () => {
    render(
      <ProcessErrorBoundary>
        <Throw when={true} />
      </ProcessErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByText(
        /Unable to load details\. Our team has been notified\./i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("retry button resets error state", () => {
    // Wrapper lets us flip the child to stop throwing, then click Retry to recover.
    function Wrapper() {
      const [throwing, setThrowing] = React.useState(true);
      return (
        <>
          <button onClick={() => setThrowing(false)}>stop</button>
          <ProcessErrorBoundary>
            <Throw when={throwing} />
          </ProcessErrorBoundary>
        </>
      );
    }

    render(<Wrapper />);
    // Fallback shown
    expect(screen.getByRole("alert")).toBeInTheDocument();

    // Flip the source so the child no longer throws
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    // Click Retry to clear hasError
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    // Child now renders normally
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
