import { describe, it, expect } from "vitest";
import { ApiError } from "./error-handler";

describe("ApiError — correlationId extraction", () => {
  it("reads request_id from a production 5xx body", () => {
    // Verified production shape (not the local exception_handlers.py's
    // correlation_id field — the two have drifted).
    const body = {
      detail: "Internal server error",
      request_id: "req-abc123",
      error: "Something went wrong",
    };
    const err = new ApiError("Internal server error", 500, body);

    expect(err.correlationId).toBe("req-abc123");
    expect(err.detail).toBe("Internal server error");
  });

  it("falls back to correlation_id when request_id is absent", () => {
    const body = { detail: "Company not found", correlation_id: "corr-xyz" };
    const err = new ApiError("Company not found", 404, body);

    expect(err.correlationId).toBe("corr-xyz");
  });

  it("prefers request_id over correlation_id when both are present", () => {
    const body = {
      detail: "Internal server error",
      request_id: "req-abc123",
      correlation_id: "corr-xyz",
    };
    const err = new ApiError("Internal server error", 500, body);

    expect(err.correlationId).toBe("req-abc123");
  });

  it("leaves correlationId undefined when neither field is present", () => {
    const err = new ApiError("Invalid request", 400, { detail: "Bad input" });

    expect(err.correlationId).toBeUndefined();
  });
});
