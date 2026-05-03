import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { debug, warn, error, createLogger } from "./console";

describe("console utilities (development mode)", () => {
  let logSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    logSpy.mockRestore();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  it("debug logs with [DEBUG] prefix in non-production", () => {
    debug("test message", { key: "value" });
    expect(logSpy).toHaveBeenCalledWith("[DEBUG]", "test message", {
      key: "value",
    });
  });

  it("warn logs with [WARN] prefix in non-production", () => {
    warn("warning message");
    expect(warnSpy).toHaveBeenCalledWith("[WARN]", "warning message");
  });

  it("error logs with [ERROR] prefix always", () => {
    error("error message");
    expect(errorSpy).toHaveBeenCalledWith("[ERROR]", "error message");
  });
});

describe("createLogger", () => {
  let logSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;
  let errorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    logSpy.mockRestore();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  it("creates a namespaced logger with debug, warn, error methods", () => {
    const log = createLogger("MyModule");
    expect(log).toHaveProperty("debug");
    expect(log).toHaveProperty("warn");
    expect(log).toHaveProperty("error");
  });

  it("prefixes debug output with namespace", () => {
    const log = createLogger("CRM");
    log.debug("loading clients");
    expect(logSpy).toHaveBeenCalledWith("[CRM]", "loading clients");
  });

  it("prefixes warn output with namespace", () => {
    const log = createLogger("CRM");
    log.warn("stale data");
    expect(warnSpy).toHaveBeenCalledWith("[CRM]", "stale data");
  });

  it("prefixes error output with namespace", () => {
    const log = createLogger("CRM");
    log.error("failed to load");
    expect(errorSpy).toHaveBeenCalledWith("[CRM]", "failed to load");
  });
});
