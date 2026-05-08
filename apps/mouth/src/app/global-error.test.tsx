import { fireEvent, render, screen } from "@testing-library/react";
import * as Sentry from "@sentry/nextjs";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GlobalError from "./global-error";

vi.mock("@sentry/nextjs", () => ({
  captureException: vi.fn(),
}));

describe("global error boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("captures the thrown error and exposes a reset action", () => {
    const reset = vi.fn();
    const error = new Error("global failure");
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    try {
      render(<GlobalError error={error} reset={reset} />);

      expect(Sentry.captureException).toHaveBeenCalledWith(error);
      expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
      expect(screen.getByText(/we've been notified/i)).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /try again/i }));

      expect(reset).toHaveBeenCalledTimes(1);
    } finally {
      consoleError.mockRestore();
    }
  });
});
