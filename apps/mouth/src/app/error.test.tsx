import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RootError from "./error";
import { logger } from "@/lib/logger";

vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
  },
}));

describe("root error boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("logs the error and lets the user retry the failed render", () => {
    const reset = vi.fn();
    const error = new globalThis.Error("render exploded");

    render(<RootError error={error} reset={reset} />);

    expect(screen.getByRole("heading", { name: /something went wrong/i })).toBeInTheDocument();
    expect(screen.getByText(/unexpected error has occurred/i)).toBeInTheDocument();
    expect(vi.mocked(logger).error).toHaveBeenCalledWith("Application Error", {}, error);

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(reset).toHaveBeenCalledTimes(1);
  });
});
