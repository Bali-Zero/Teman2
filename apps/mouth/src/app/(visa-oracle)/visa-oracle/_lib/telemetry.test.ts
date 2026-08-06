import { beforeEach, describe, expect, it, vi } from "vitest";

const trackEvent = vi.hoisted(() => vi.fn());
vi.mock("@/lib/analytics", () => ({ trackEvent }));

import { emitVisaOracleTelemetry, nonReversibleHash } from "./telemetry";

describe("Visa Oracle PII-free telemetry boundary", () => {
  beforeEach(() => trackEvent.mockReset());

  it("hashes correlators without exposing the input", async () => {
    const hash = await nonReversibleHash(
      '{"nationality":"ID","family":"sensitive"}',
    );
    expect(hash).toMatch(/^[a-f0-9]{64}$/);
    expect(hash).not.toContain("nationality");
    expect(hash).toBe(
      await nonReversibleHash('{"nationality":"ID","family":"sensitive"}'),
    );
  });

  it("emits only state and a valid SHA-256 hash", () => {
    const hash = "a".repeat(64);
    emitVisaOracleTelemetry({
      event: "visa_oracle_v2_engine_result",
      state: "NEEDS_INPUT",
      correlationHash: hash,
    });
    expect(trackEvent).toHaveBeenCalledWith("visa_oracle_v2_engine_result", {
      state: "NEEDS_INPUT",
      correlation_hash: hash,
    });
  });

  it("drops an invalid correlator instead of forwarding it", () => {
    emitVisaOracleTelemetry({
      event: "visa_oracle_v2_network_failure",
      state: "TEMPORARILY_UNAVAILABLE",
      correlationHash: "raw-payload",
    });
    expect(trackEvent).toHaveBeenCalledWith("visa_oracle_v2_network_failure", {
      state: "TEMPORARILY_UNAVAILABLE",
    });
  });
});
