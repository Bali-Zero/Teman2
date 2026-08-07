import {
  parseVisaOracleEvaluateResponse,
  type VisaOracleResponseError,
} from "./engine-response";
import {
  parseStrictJson,
  StrictJsonError,
  VISA_ORACLE_MAX_RESPONSE_BYTES,
} from "./strict-json";
import type {
  VisaOracleEvaluateRequest,
  VisaOracleEvaluateResponse,
} from "./visa-oracle-contract";

export const VISA_ORACLE_EVALUATE_URL = "/api/visa-oracle/evaluate";
export const VISA_ORACLE_MAX_REQUEST_BYTES = 32 * 1_024;
export const VISA_ORACLE_DEFAULT_TIMEOUT_MS = 12_000;

const IDEMPOTENCY_KEY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);

export function isVisaOracleRetryableHttpStatus(
  status: number | undefined,
): boolean {
  return status !== undefined && RETRYABLE_STATUS.has(status);
}

export type VisaOracleClientErrorCode =
  | "INVALID_REQUEST"
  | "ABORTED"
  | "TIMEOUT"
  | "NETWORK_FAILURE"
  | "HTTP_ERROR"
  | "MALFORMED_RESPONSE";

export class VisaOracleClientError extends Error {
  constructor(
    public readonly code: VisaOracleClientErrorCode,
    public readonly status?: number,
  ) {
    super(code);
    this.name = "VisaOracleClientError";
  }
}

export interface EvaluateVisaOracleOptions {
  request: VisaOracleEvaluateRequest;
  idempotencyKey: string;
  signal?: AbortSignal;
  timeoutMs?: number;
  maxRetries?: number;
  fetchImpl?: typeof fetch;
  waitBeforeRetry?: (attempt: number) => Promise<void>;
}

async function readResponseText(response: Response): Promise<string> {
  const declaredLength = response.headers.get("content-length");
  if (declaredLength !== null) {
    if (!/^\d+$/.test(declaredLength)) {
      throw new VisaOracleClientError("MALFORMED_RESPONSE");
    }
    if (Number(declaredLength) > VISA_ORACLE_MAX_RESPONSE_BYTES) {
      throw new VisaOracleClientError("MALFORMED_RESPONSE");
    }
  }

  if (!response.body) {
    const text = await response.text();
    if (
      new TextEncoder().encode(text).byteLength > VISA_ORACLE_MAX_RESPONSE_BYTES
    ) {
      throw new VisaOracleClientError("MALFORMED_RESPONSE");
    }
    return text;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let received = 0;
  let text = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > VISA_ORACLE_MAX_RESPONSE_BYTES) {
        await reader.cancel();
        throw new VisaOracleClientError("MALFORMED_RESPONSE");
      }
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
    return text;
  } catch (error) {
    if (error instanceof VisaOracleClientError) throw error;
    throw new VisaOracleClientError("MALFORMED_RESPONSE");
  } finally {
    reader.releaseLock();
  }
}

function parseResponseBody(source: string): VisaOracleEvaluateResponse {
  try {
    return parseVisaOracleEvaluateResponse(parseStrictJson(source));
  } catch (error) {
    if (
      error instanceof StrictJsonError ||
      (error as VisaOracleResponseError | undefined)?.name ===
        "VisaOracleResponseError"
    ) {
      throw new VisaOracleClientError("MALFORMED_RESPONSE");
    }
    throw error;
  }
}

interface AttemptResult {
  response?: VisaOracleEvaluateResponse;
  retryable: boolean;
  error?: VisaOracleClientError;
}

async function runAttempt(
  url: string,
  body: string,
  options: EvaluateVisaOracleOptions,
  timeoutMs: number,
): Promise<AttemptResult> {
  if (options.signal?.aborted) {
    return {
      retryable: false,
      error: new VisaOracleClientError("ABORTED"),
    };
  }

  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort();
  options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await (options.fetchImpl ?? fetch)(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "Idempotency-Key": options.idempotencyKey,
      },
      body,
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
    });

    if (response.status !== 200) {
      return {
        retryable: isVisaOracleRetryableHttpStatus(response.status),
        error: new VisaOracleClientError("HTTP_ERROR", response.status),
      };
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (
      contentType.split(";", 1)[0].trim().toLowerCase() !== "application/json"
    ) {
      return {
        retryable: false,
        error: new VisaOracleClientError("MALFORMED_RESPONSE"),
      };
    }

    const responseBody = await readResponseText(response);
    return { response: parseResponseBody(responseBody), retryable: false };
  } catch (error) {
    if (options.signal?.aborted) {
      return {
        retryable: false,
        error: new VisaOracleClientError("ABORTED"),
      };
    }
    if (timedOut) {
      return {
        retryable: true,
        error: new VisaOracleClientError("TIMEOUT"),
      };
    }
    if (error instanceof VisaOracleClientError) {
      return { retryable: false, error };
    }
    return {
      retryable: true,
      error: new VisaOracleClientError("NETWORK_FAILURE"),
    };
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

/**
 * Bounded, replay-safe client. Every retry reuses the exact serialized body
 * and durable Idempotency-Key; callers cannot opt into retry without a key.
 */
export async function evaluateVisaOracle(
  options: EvaluateVisaOracleOptions,
): Promise<VisaOracleEvaluateResponse> {
  const timeoutMs = options.timeoutMs ?? VISA_ORACLE_DEFAULT_TIMEOUT_MS;
  const maxRetries = options.maxRetries ?? 1;
  if (
    !IDEMPOTENCY_KEY.test(options.idempotencyKey) ||
    !Number.isFinite(timeoutMs) ||
    timeoutMs <= 0 ||
    !Number.isSafeInteger(maxRetries) ||
    maxRetries < 0 ||
    maxRetries > 2
  ) {
    throw new VisaOracleClientError("INVALID_REQUEST");
  }

  let body: string;
  try {
    body = JSON.stringify(options.request);
  } catch {
    throw new VisaOracleClientError("INVALID_REQUEST");
  }
  if (
    new TextEncoder().encode(body).byteLength > VISA_ORACLE_MAX_REQUEST_BYTES
  ) {
    throw new VisaOracleClientError("INVALID_REQUEST");
  }

  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    const result = await runAttempt(
      VISA_ORACLE_EVALUATE_URL,
      body,
      options,
      timeoutMs,
    );
    if (result.response) return result.response;
    if (!result.retryable || attempt === maxRetries) {
      throw result.error ?? new VisaOracleClientError("NETWORK_FAILURE");
    }
    await (options.waitBeforeRetry?.(attempt + 1) ??
      new Promise<void>((resolve) => setTimeout(resolve, 150 * (attempt + 1))));
  }
  throw new VisaOracleClientError("NETWORK_FAILURE");
}
