import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

export const GARUDA_PREVIEW_MAX_REQUEST_BYTES = 4 * 1024;
const GARUDA_PREVIEW_MAX_OUTPUT_BYTES = 64 * 1024;
const GARUDA_PREVIEW_TIMEOUT_MS = 5_000;
const GARUDA_PREVIEW_MODULE =
  "backend.services.garuda_flow.internal_preview_cli";

const OFFICIAL_PRICE_KEYS = new Set([
  "B1 Visa on Arrival (VOA)",
  "B1 Visa on Arrival Extension",
]);
const CHECKPOINT_LABELS = new Set(["D-10", "D-3", "D-1"]);
const DECLINE_CODES = new Set([
  "NATIONALITY_NOT_ELIGIBLE",
  "PURPOSE_NOT_ELIGIBLE",
  "GROUP_CASE",
  "PASSPORT_TYPE",
  "PASSPORT_VALIDITY",
  "NOT_SELF_PAY",
  "FEEDBACK_REQUIRED",
  "URGENT_CASE",
  "SPECIAL_PASSPORT",
  "PRIOR_ISSUE",
  "FASTLANE_REQUEST",
  "EXPIRY_UNKNOWN",
  "EXPIRES_TOO_SOON",
  "EXTENSION_ALREADY_USED",
  "ARRIVAL_TOO_SOON",
  "ARRIVAL_DATE_UNCONFIRMED",
]);
const BASE_WARNINGS = [
  "Internal preliminary pre-screen only; it is not an immigration decision or an approval guarantee.",
  "Nationality and entry-point eligibility are not yet checked against an authoritative dataset and require manual verification.",
  "Passport type, document authenticity, and prior overstay, refusal, or blacklist history require human review.",
] as const;
const ESTIMATED_EXPIRY_WARNING =
  "The expiry is an estimate; the printed immigration expiry is authoritative and must be verified before action.";
const EXTENSION_WARNING =
  "Extension processing requires office-specific verification and an in-person photo/interview step.";
const CALENDAR_WARNING =
  "The operating calendar does not cover this entry date. No issuance deadline is shown; staff must verify the applicable decree manually.";
const PRICE_WARNING =
  "The official catalogue price is unavailable. No price is shown; staff must confirm the price rather than invent one.";
const SUCCESS_KEYS = [
  "decision",
  "reason_codes",
  "case_type",
  "entry_date",
  "expiry_date",
  "computed_stay_end",
  "expiry_is_estimated",
  "published_filing_deadline",
  "submit_by_date",
  "internal_checkpoints",
  "price_idr",
  "price_source",
  "price_status",
  "price_warning",
  "generated_at",
  "calendar_coverage_start",
  "calendar_coverage_end",
  "calendar_status",
  "calendar_warning",
  "warnings",
] as const;
const CHECKPOINT_KEYS = ["label", "at", "kind", "note"] as const;
const MAX_REASON_CODES = 32;

export class GarudaPreviewAdapterError extends Error {
  constructor(
    readonly code:
      "invalid_request" | "preview_unavailable" | "preview_misconfigured",
    message: string,
  ) {
    super(message);
    this.name = "GarudaPreviewAdapterError";
  }
}

export interface GarudaProcessConfig {
  backendRoot: string;
  pythonExecutable: string;
  modulePath: string;
  trustedCwd: string;
}

export interface GarudaInternalCheckpoint {
  label: "D-10" | "D-3" | "D-1";
  at: string;
  kind: "internal";
  note: string | null;
}

export interface GarudaPreviewResult {
  decision: "ACCEPT" | "DECLINE";
  reason_codes: string[];
  case_type: "issuance" | "extension";
  entry_date: string;
  expiry_date: string;
  computed_stay_end: string;
  expiry_is_estimated: boolean;
  published_filing_deadline: string | null;
  submit_by_date: string | null;
  internal_checkpoints: GarudaInternalCheckpoint[];
  price_idr: number | null;
  price_source: string | null;
  price_status: "confirmed" | "unavailable";
  price_warning: string | null;
  generated_at: string;
  calendar_coverage_start: string;
  calendar_coverage_end: string;
  calendar_status: "confirmed" | "uncovered" | "not_applicable";
  calendar_warning: string | null;
  warnings: string[];
}

export interface GarudaSanitizedError {
  ok: false;
  error: "invalid_request" | "request_too_large";
}

export function resolveGarudaProcessConfig(
  repoRoot: string | undefined = process.env.COCKPIT_REPO_ROOT,
): GarudaProcessConfig {
  if (!repoRoot || !path.isAbsolute(repoRoot)) {
    throw new GarudaPreviewAdapterError(
      "preview_misconfigured",
      "COCKPIT_REPO_ROOT must be an absolute path",
    );
  }
  const normalizedRepoRoot = path.resolve(repoRoot);
  const backendRoot = path.join(normalizedRepoRoot, "apps", "backend-rag");
  const pythonExecutable = path.join(backendRoot, ".venv", "bin", "python");
  const modulePath = path.join(
    backendRoot,
    "backend",
    "services",
    "garuda_flow",
    "internal_preview_cli.py",
  );
  const trustedCwd = path.dirname(modulePath);
  if (!existsSync(pythonExecutable) || !existsSync(modulePath)) {
    throw new GarudaPreviewAdapterError(
      "preview_misconfigured",
      "GARUDA preview runtime is unavailable",
    );
  }
  if (existsSync(path.join(trustedCwd, ".env"))) {
    throw new GarudaPreviewAdapterError(
      "preview_misconfigured",
      "GARUDA preview runtime directory must not contain a .env file",
    );
  }
  return { backendRoot, pythonExecutable, modulePath, trustedCwd };
}

export function buildGarudaChildEnvironment(
  backendRoot: string,
  source: NodeJS.ProcessEnv = process.env,
): Record<string, string> {
  if (!path.isAbsolute(backendRoot)) {
    throw new GarudaPreviewAdapterError(
      "preview_misconfigured",
      "GARUDA backend root must be absolute",
    );
  }
  const childEnv: Record<string, string> = {
    PYTHONPATH: path.resolve(backendRoot),
    PYTHONIOENCODING: "utf-8",
    PYTHONUTF8: "1",
  };
  for (const key of ["PATH", "LANG", "LC_ALL", "LC_CTYPE"] as const) {
    const value = source[key];
    if (value) childEnv[key] = value;
  }
  return childEnv;
}

function invalidEngineResponse(): GarudaPreviewAdapterError {
  return new GarudaPreviewAdapterError(
    "preview_unavailable",
    "GARUDA engine returned an invalid response",
  );
}

function parseObject(stdout: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw invalidEngineResponse();
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw invalidEngineResponse();
  }
  return parsed as Record<string, unknown>;
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value);
  return (
    actual.length === expected.length &&
    actual.every((key) => expected.includes(key))
  );
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value
  );
}

function isIsoDateTime(value: unknown): value is string {
  if (
    typeof value !== "string" ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      value,
    )
  ) {
    return false;
  }
  return !Number.isNaN(Date.parse(value));
}

function isNullableDate(value: unknown): value is string | null {
  return value === null || isIsoDate(value);
}

function isReasonCodeArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= MAX_REASON_CODES &&
    new Set(value).size === value.length &&
    value.every((item) => typeof item === "string" && DECLINE_CODES.has(item))
  );
}

function normaliseForbiddenMarkers(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/[\u2010-\u2015\u2212]/g, "-")
    .toUpperCase();
}

function containsForbiddenMarker(value: unknown): boolean {
  if (typeof value === "string") {
    const normalized = normaliseForbiddenMarkers(value);
    return normalized.includes("D-14") || normalized.includes("D14");
  }
  if (Array.isArray(value)) return value.some(containsForbiddenMarker);
  if (value && typeof value === "object") {
    return Object.entries(value).some(
      ([key, nested]) =>
        containsForbiddenMarker(key) || containsForbiddenMarker(nested),
    );
  }
  return false;
}

function isInternalCheckpoint(
  value: unknown,
): value is GarudaInternalCheckpoint {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const checkpoint = value as Record<string, unknown>;
  return (
    hasExactKeys(checkpoint, CHECKPOINT_KEYS) &&
    typeof checkpoint.label === "string" &&
    CHECKPOINT_LABELS.has(checkpoint.label) &&
    isIsoDate(checkpoint.at) &&
    checkpoint.kind === "internal" &&
    checkpoint.note === null
  );
}

function hasExactWarnings(
  value: unknown,
  caseType: unknown,
  expiryIsEstimated: unknown,
): value is string[] {
  const expected: string[] = [...BASE_WARNINGS];
  if (expiryIsEstimated === true) expected.push(ESTIMATED_EXPIRY_WARNING);
  if (caseType === "extension") expected.push(EXTENSION_WARNING);
  return (
    Array.isArray(value) &&
    value.length === expected.length &&
    value.every((warning, index) => warning === expected[index])
  );
}

function hasExactCheckpointShape(
  checkpoints: GarudaInternalCheckpoint[],
  caseType: unknown,
): boolean {
  if (caseType === "issuance") return checkpoints.length === 0;
  return (
    caseType === "extension" &&
    checkpoints.length === 3 &&
    checkpoints.every(
      (checkpoint, index) =>
        checkpoint.label === (["D-10", "D-3", "D-1"] as const)[index],
    )
  );
}

function parseEngineSuccess(stdout: string): GarudaPreviewResult {
  const value = parseObject(stdout);
  const calendarStatuses = new Set([
    "confirmed",
    "uncovered",
    "not_applicable",
  ]);
  const priceStatuses = new Set(["confirmed", "unavailable"]);
  if (
    containsForbiddenMarker(value) ||
    !hasExactKeys(value, SUCCESS_KEYS) ||
    (value.decision !== "ACCEPT" && value.decision !== "DECLINE") ||
    !isReasonCodeArray(value.reason_codes) ||
    (value.case_type !== "issuance" && value.case_type !== "extension") ||
    !isIsoDate(value.entry_date) ||
    !isIsoDate(value.expiry_date) ||
    !isIsoDate(value.computed_stay_end) ||
    value.computed_stay_end !== value.expiry_date ||
    typeof value.expiry_is_estimated !== "boolean" ||
    !isNullableDate(value.published_filing_deadline) ||
    !isNullableDate(value.submit_by_date) ||
    !Array.isArray(value.internal_checkpoints) ||
    !value.internal_checkpoints.every(isInternalCheckpoint) ||
    !(
      value.price_idr === null ||
      (typeof value.price_idr === "number" &&
        Number.isSafeInteger(value.price_idr) &&
        value.price_idr > 0)
    ) ||
    !(
      value.price_source === null ||
      (typeof value.price_source === "string" &&
        OFFICIAL_PRICE_KEYS.has(value.price_source))
    ) ||
    typeof value.price_status !== "string" ||
    !priceStatuses.has(value.price_status) ||
    !(value.price_warning === null || value.price_warning === PRICE_WARNING) ||
    !isIsoDateTime(value.generated_at) ||
    !isIsoDate(value.calendar_coverage_start) ||
    !isIsoDate(value.calendar_coverage_end) ||
    typeof value.calendar_status !== "string" ||
    !calendarStatuses.has(value.calendar_status) ||
    !(
      value.calendar_warning === null ||
      value.calendar_warning === CALENDAR_WARNING
    ) ||
    !hasExactWarnings(
      value.warnings,
      value.case_type,
      value.expiry_is_estimated,
    )
  ) {
    throw invalidEngineResponse();
  }

  const entryDate = value.entry_date as string;
  const submitByDate = value.submit_by_date as string | null;
  const coverageStart = value.calendar_coverage_start as string;
  const coverageEnd = value.calendar_coverage_end as string;

  if (
    coverageStart > coverageEnd ||
    (value.decision === "ACCEPT" && value.reason_codes.length !== 0) ||
    (value.decision === "DECLINE" && value.reason_codes.length === 0) ||
    (value.price_idr === null) !== (value.price_source === null) ||
    (value.price_status === "unavailable") !==
      (value.price_warning === PRICE_WARNING) ||
    (value.price_status === "confirmed") !== (value.price_warning === null) ||
    (value.price_status === "unavailable") !== (value.price_idr === null) ||
    (value.price_status === "unavailable") !== (value.price_source === null) ||
    (value.price_source !== null &&
      value.price_source !==
        (value.case_type === "issuance"
          ? "B1 Visa on Arrival (VOA)"
          : "B1 Visa on Arrival Extension")) ||
    (value.case_type === "extension" &&
      (value.calendar_status !== "not_applicable" ||
        value.submit_by_date !== null ||
        value.calendar_warning !== null)) ||
    (value.case_type === "issuance" &&
      value.calendar_status === "not_applicable") ||
    (value.calendar_status === "confirmed" &&
      (submitByDate === null ||
        value.calendar_warning !== null ||
        submitByDate < coverageStart ||
        submitByDate >= entryDate ||
        entryDate > coverageEnd)) ||
    (value.calendar_status === "uncovered" && value.submit_by_date !== null) ||
    (value.calendar_status === "uncovered") !==
      (value.calendar_warning === CALENDAR_WARNING) ||
    (value.case_type === "issuance" &&
      value.calendar_status === "uncovered" &&
      (value.decision !== "DECLINE" ||
        !value.reason_codes.includes("ARRIVAL_DATE_UNCONFIRMED"))) ||
    !hasExactCheckpointShape(
      value.internal_checkpoints as GarudaInternalCheckpoint[],
      value.case_type,
    )
  ) {
    throw invalidEngineResponse();
  }

  return value as unknown as GarudaPreviewResult;
}

function parseEngineError(stdout: string): GarudaSanitizedError {
  const value = parseObject(stdout);
  if (
    !hasExactKeys(value, ["ok", "error"]) ||
    value.ok !== false ||
    (value.error !== "invalid_request" && value.error !== "request_too_large")
  ) {
    throw invalidEngineResponse();
  }
  return value as unknown as GarudaSanitizedError;
}

export async function runGarudaPreview(
  requestJson: string,
): Promise<GarudaPreviewResult | GarudaSanitizedError> {
  if (
    !requestJson ||
    Buffer.byteLength(requestJson, "utf8") > GARUDA_PREVIEW_MAX_REQUEST_BYTES
  ) {
    throw new GarudaPreviewAdapterError(
      "invalid_request",
      "GARUDA preview request is empty or too large",
    );
  }

  const { backendRoot, pythonExecutable, trustedCwd } =
    resolveGarudaProcessConfig();
  return await new Promise<GarudaPreviewResult | GarudaSanitizedError>(
    (resolve, reject) => {
      const child = execFile(
        pythonExecutable,
        ["-m", GARUDA_PREVIEW_MODULE],
        {
          cwd: trustedCwd,
          encoding: "utf8",
          timeout: GARUDA_PREVIEW_TIMEOUT_MS,
          maxBuffer: GARUDA_PREVIEW_MAX_OUTPUT_BYTES,
          windowsHide: true,
          // Next augments ProcessEnv with a required NODE_ENV field. Keep it
          // out of the real child allowlist and narrow-cast only at the Node
          // API boundary.
          env: buildGarudaChildEnvironment(backendRoot) as NodeJS.ProcessEnv,
        },
        (error, stdout) => {
          if (error) {
            try {
              resolve(parseEngineError(stdout));
            } catch {
              reject(
                new GarudaPreviewAdapterError(
                  "preview_unavailable",
                  "GARUDA engine is unavailable",
                ),
              );
            }
            return;
          }
          try {
            resolve(parseEngineSuccess(stdout));
          } catch (parseError) {
            reject(parseError);
          }
        },
      );
      child.stdin?.end(requestJson, "utf8");
    },
  );
}
