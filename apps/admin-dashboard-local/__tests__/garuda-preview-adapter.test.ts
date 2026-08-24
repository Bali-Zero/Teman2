import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  execFile: vi.fn(),
  existsSync: vi.fn((_candidate: string) => true),
  stdinEnd: vi.fn(),
}));

vi.mock("node:child_process", () => ({ execFile: mocks.execFile }));
vi.mock("node:fs", () => ({ existsSync: mocks.existsSync }));

import {
  buildGarudaChildEnvironment,
  GarudaPreviewAdapterError,
  resolveGarudaProcessConfig,
  runGarudaPreview,
} from "@/lib/garuda-preview-adapter";

const VALID_RESULT = {
  decision: "ACCEPT",
  reason_codes: [],
  case_type: "issuance",
  entry_date: "2026-08-24",
  expiry_date: "2026-09-23",
  computed_stay_end: "2026-09-23",
  expiry_is_estimated: true,
  published_filing_deadline: "2026-09-16",
  submit_by_date: "2026-08-21",
  internal_checkpoints: [],
  price_idr: 790_000,
  price_source: "B1 Visa on Arrival (VOA)",
  price_status: "confirmed",
  price_warning: null,
  generated_at: "2026-08-19T08:00:00Z",
  calendar_coverage_start: "2026-07-28",
  calendar_coverage_end: "2026-12-31",
  calendar_status: "confirmed",
  calendar_warning: null,
  warnings: [
    "Internal preliminary pre-screen only; it is not an immigration decision or an approval guarantee.",
    "The nationality code is checked against the decree-sourced VOA list; this pre-screen does not collect an entry point, so staff must confirm entry-point eligibility.",
    "Passport type, document authenticity, and prior overstay, refusal, or blacklist history require human review.",
    "The expiry is an estimate; the printed immigration expiry is authoritative and must be verified before action.",
  ],
};

const VALID_UNCOVERED_RESULT = {
  ...VALID_RESULT,
  decision: "DECLINE",
  reason_codes: ["ARRIVAL_DATE_UNCONFIRMED"],
  entry_date: "2027-01-10",
  expiry_date: "2027-02-09",
  computed_stay_end: "2027-02-09",
  published_filing_deadline: "2027-02-02",
  submit_by_date: null,
  calendar_status: "uncovered",
  calendar_warning:
    "The operating calendar does not cover this entry date. No issuance deadline is shown; staff must verify the applicable decree manually.",
};

function engineResult(
  result: object,
  error: Error | null = null,
): { stdin: { end: typeof mocks.stdinEnd } } {
  mocks.execFile.mockImplementationOnce((...args: unknown[]) => {
    const callback = args.at(-1) as (
      callbackError: Error | null,
      stdout: string,
    ) => void;
    queueMicrotask(() => callback(error, JSON.stringify(result)));
    return { stdin: { end: mocks.stdinEnd } };
  });
  return { stdin: { end: mocks.stdinEnd } };
}

describe("GARUDA Python execFile adapter", () => {
  beforeEach(() => {
    process.env.COCKPIT_REPO_ROOT = "/synthetic/repo";
    mocks.execFile.mockReset();
    mocks.existsSync
      .mockReset()
      .mockImplementation((candidate: string) => !candidate.endsWith("/.env"));
    mocks.stdinEnd.mockReset();
  });

  it("resolves and validates only the fixed backend runtime", () => {
    expect(resolveGarudaProcessConfig()).toEqual({
      backendRoot: "/synthetic/repo/apps/backend-rag",
      pythonExecutable: "/synthetic/repo/apps/backend-rag/.venv/bin/python",
      modulePath:
        "/synthetic/repo/apps/backend-rag/backend/services/garuda_flow/internal_preview_cli.py",
      trustedCwd:
        "/synthetic/repo/apps/backend-rag/backend/services/garuda_flow",
    });
    expect(mocks.existsSync).toHaveBeenCalledTimes(3);
  });

  it("fails configuration when the fixed CLI module is absent", () => {
    mocks.existsSync.mockReturnValueOnce(true).mockReturnValueOnce(false);

    expect(() => resolveGarudaProcessConfig()).toThrow(
      GarudaPreviewAdapterError,
    );
  });

  it("fails closed when the trusted child cwd contains a .env", () => {
    mocks.existsSync.mockReset().mockReturnValue(true);

    expect(() => resolveGarudaProcessConfig()).toThrowError(
      "GARUDA preview runtime directory must not contain a .env file",
    );
  });

  it("invokes the fixed module with minimal env and one JSON stdin", async () => {
    process.env.COCKPIT_HMAC_KEY = "must-not-cross";
    process.env.COCKPIT_SESSION_KEY = "must-not-cross";
    process.env.DATABASE_URL = "must-not-cross";
    engineResult(VALID_RESULT);

    const body = JSON.stringify({ case_type: "extension" });
    await expect(runGarudaPreview(body)).resolves.toEqual(VALID_RESULT);
    const [executable, args, options] = mocks.execFile.mock.calls[0];
    expect(executable).toBe(
      "/synthetic/repo/apps/backend-rag/.venv/bin/python",
    );
    expect(args).toEqual([
      "-m",
      "backend.services.garuda_flow.internal_preview_cli",
    ]);
    expect(options).toMatchObject({
      cwd: "/synthetic/repo/apps/backend-rag/backend/services/garuda_flow",
      timeout: 5_000,
      maxBuffer: 65_536,
    });
    expect(options.env).toEqual(
      buildGarudaChildEnvironment("/synthetic/repo/apps/backend-rag"),
    );
    expect(options.env.PYTHONPATH).toBe("/synthetic/repo/apps/backend-rag");
    expect(options.env).not.toHaveProperty("COCKPIT_HMAC_KEY");
    expect(options.env).not.toHaveProperty("COCKPIT_SESSION_KEY");
    expect(options.env).not.toHaveProperty("DATABASE_URL");
    expect(options.env).not.toHaveProperty("FLY_TUNNEL_URL");
    expect(mocks.stdinEnd).toHaveBeenCalledWith(body, "utf8");

    delete process.env.COCKPIT_HMAC_KEY;
    delete process.env.COCKPIT_SESSION_KEY;
    delete process.env.DATABASE_URL;
  });

  it("rejects oversized input before process creation", async () => {
    await expect(runGarudaPreview("x".repeat(4_097))).rejects.toMatchObject({
      code: "invalid_request",
    });
    expect(mocks.execFile).not.toHaveBeenCalled();
  });

  it("rejects malformed and partial success objects", async () => {
    mocks.execFile.mockImplementationOnce((...args: unknown[]) => {
      const callback = args.at(-1) as (
        error: Error | null,
        stdout: string,
      ) => void;
      queueMicrotask(() => callback(null, "not-json"));
      return { stdin: { end: mocks.stdinEnd } };
    });
    await expect(runGarudaPreview("{}")).rejects.toBeInstanceOf(
      GarudaPreviewAdapterError,
    );

    engineResult({ decision: "ACCEPT", reason_codes: [] });
    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it.each([
    { decline_reasons: ["internal prose"] },
    { request: { nationality: "USA" } },
    { "D-14": "2026-09-09" },
    { filesystem: "/private/path" },
    { env: { COCKPIT_HMAC_KEY: "secret" } },
  ])("rejects unknown success fields: %o", async (extra) => {
    engineResult({ ...VALID_RESULT, ...extra });

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it.each([
    { price_idr: null },
    { price_source: null },
    { price_source: "B1 Visa on Arrival Extension" },
    { case_type: "extension", calendar_status: "not_applicable" },
  ])("rejects an inconsistent official price pair: %o", async (change) => {
    engineResult({ ...VALID_RESULT, ...change });

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it.each([
    {
      price_status: "unavailable",
      price_warning:
        "The official catalogue price is unavailable. No price is shown; staff must confirm the price rather than invent one.",
    },
    {
      price_status: "confirmed",
      price_warning:
        "The official catalogue price is unavailable. No price is shown; staff must confirm the price rather than invent one.",
    },
    {
      price_idr: null,
      price_source: null,
      price_status: "unavailable",
      price_warning: "Official price lookup failed.",
    },
  ])("rejects an inconsistent official price status: %o", async (change) => {
    engineResult({ ...VALID_RESULT, ...change });

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it.each([
    { decision: "ACCEPT", reason_codes: ["ARRIVAL_TOO_SOON"] },
    { decision: "DECLINE", reason_codes: [] },
    { decision: "DECLINE", reason_codes: ["not bounded code prose"] },
    { decision: "DECLINE", reason_codes: ["D14_INTERNAL_WINDOW"] },
  ])("rejects inconsistent or unbounded decision codes: %o", async (change) => {
    engineResult({ ...VALID_RESULT, ...change });

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it.each([
    { reasonCodes: ["PURPOSE_NOT_ELIGIBLE"] },
    { reasonCodes: ["GROUP_CASE"] },
    { reasonCodes: ["ARRIVAL_TOO_FAR"] },
    { reasonCodes: ["PURPOSE_NOT_ELIGIBLE", "GROUP_CASE"] },
  ])(
    "accepts unique bounded decline code sets: $reasonCodes",
    async ({ reasonCodes }) => {
      const result = {
        ...VALID_RESULT,
        decision: "DECLINE",
        reason_codes: reasonCodes,
      };
      engineResult(result);

      await expect(runGarudaPreview("{}")).resolves.toEqual(result);
    },
  );

  it.each([
    { reasonCodes: ["PURPOSE_NOT_ELIGIBLE", "PURPOSE_NOT_ELIGIBLE"] },
    { reasonCodes: ["GROUP_CASE", "GROUP_CASE"] },
    {
      reasonCodes: [
        "PURPOSE_NOT_ELIGIBLE",
        "GROUP_CASE",
        "PURPOSE_NOT_ELIGIBLE",
      ],
    },
  ])(
    "rejects duplicate decline codes: $reasonCodes",
    async ({ reasonCodes }) => {
      engineResult({
        ...VALID_RESULT,
        decision: "DECLINE",
        reason_codes: reasonCodes,
      });

      await expect(runGarudaPreview("{}")).rejects.toMatchObject({
        code: "preview_unavailable",
      });
    },
  );

  it("requires the engine's manual-routing code for uncovered issuance", async () => {
    engineResult(VALID_UNCOVERED_RESULT);
    await expect(runGarudaPreview("{}")).resolves.toEqual(
      VALID_UNCOVERED_RESULT,
    );

    engineResult({
      ...VALID_UNCOVERED_RESULT,
      decision: "ACCEPT",
      reason_codes: [],
    });
    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it("accepts an uncovered far arrival when manual routing is also present", async () => {
    const result = {
      ...VALID_UNCOVERED_RESULT,
      reason_codes: ["ARRIVAL_DATE_UNCONFIRMED", "ARRIVAL_TOO_FAR"],
    };
    engineResult(result);

    await expect(runGarudaPreview("{}")).resolves.toEqual(result);
  });

  it.each([
    { submit_by_date: null },
    { submit_by_date: "2026-07-27" },
    { submit_by_date: VALID_RESULT.entry_date },
    { calendar_warning: VALID_UNCOVERED_RESULT.calendar_warning },
    { calendar_coverage_start: "2027-01-01" },
    { price_idr: Number.MAX_SAFE_INTEGER + 1 },
    {
      internal_checkpoints: [
        { label: "D-10", at: "2026-09-13", kind: "internal", note: null },
      ],
    },
  ])("rejects partial confirmed issuance contracts: %o", async (change) => {
    engineResult({ ...VALID_RESULT, ...change });

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it.each([
    { warnings: ["Leaks internal D-14 marker"] },
    { warnings: ["Leaks internal D‑14 marker"] },
    { warnings: ["Leaks internal D–14 marker"] },
    { warnings: ["Leaks semantic D14 marker"] },
    {
      internal_checkpoints: [
        {
          label: "D-10",
          at: "2026-09-13",
          kind: "internal",
          note: "Derived from D-14",
        },
      ],
    },
    { decision: "DECLINE", reason_codes: ["D-14"] },
  ])("rejects D-14 in any serialized string: %o", async (change) => {
    engineResult({ ...VALID_RESULT, ...change });

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it.each([
    { warnings: ["raw blacklist/refusal decision prose"] },
    {
      internal_checkpoints: [
        {
          label: "D-10",
          at: "2026-09-13",
          kind: "internal",
          note: "raw blacklist/refusal decision prose",
        },
      ],
    },
  ])("rejects arbitrary warning or checkpoint prose: %o", async (change) => {
    engineResult({ ...VALID_RESULT, ...change });

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
    });
  });

  it("preserves only exact sanitized validation JSON on nonzero exit", async () => {
    const validation = { ok: false, error: "invalid_request" };
    engineResult(validation, new Error("process exited 2"));
    await expect(runGarudaPreview("{}")).resolves.toEqual(validation);

    engineResult(
      { ...validation, details: "/private/backend/path" },
      new Error("process exited 2"),
    );
    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
      message: "GARUDA engine is unavailable",
    });
  });

  it("sanitizes failed engine output", async () => {
    engineResult(
      { ok: false, error: "runtime_error" },
      new Error("secret at /private/path"),
    );

    await expect(runGarudaPreview("{}")).rejects.toMatchObject({
      code: "preview_unavailable",
      message: "GARUDA engine is unavailable",
    });
  });
});
