import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VaultErrorBoundary } from "./VaultErrorBoundary";

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

describe("VaultErrorBoundary", () => {
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  it("renders children when no error", () => {
    render(
      <VaultErrorBoundary>
        <Throw when={false} />
      </VaultErrorBoundary>,
    );
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("renders fallback on error", () => {
    render(
      <VaultErrorBoundary>
        <Throw when={true} />
      </VaultErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Unable to load your vault/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("retry clears the error state", () => {
    function Wrapper() {
      const [throwing, setThrowing] = React.useState(true);
      return (
        <>
          <button onClick={() => setThrowing(false)}>stop</button>
          <VaultErrorBoundary>
            <Throw when={throwing} />
          </VaultErrorBoundary>
        </>
      );
    }
    render(<Wrapper />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
