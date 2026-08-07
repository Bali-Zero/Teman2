import { isIP } from "node:net";

export const REQUIRED_SYNTHETIC_CONTRACTS = [
  "MY_PORTAL_SYNTHETIC_CLIENT_EMAIL",
  "MY_PORTAL_SYNTHETIC_CLIENT_PIN",
  "MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_EMAIL",
  "MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN",
  "MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_EMAIL",
  "MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_PIN",
  "MY_PORTAL_SYNTHETIC_PARTNER_EMAIL",
  "MY_PORTAL_SYNTHETIC_PARTNER_PIN",
  "MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT",
  "MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE",
  "MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID",
  "MY_PORTAL_SYNTHETIC_EXPIRED_SESSION",
] as const;

const REQUIRED_ENDPOINT_CONTRACTS = [
  "NUZANTARA_API_URL",
  "MY_PORTAL_BACKEND_HEALTH_URL",
  "MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL",
  "MY_PORTAL_MAGIC_LINK_INBOX_URL",
  "MY_PORTAL_QA_DOCUMENT_SINK_URL",
  "INTERNAL_EMAIL_API_URL",
] as const;

export const REQUIRED_MAGIC_LINK_CONTRACTS = [
  "MY_PORTAL_MAGIC_LINK_SINK_KEY",
  "NUZANTARA_API_KEY",
] as const;

export const REQUIRED_DOCUMENT_SINK_CONTRACTS = [
  "MY_PORTAL_QA_DOCUMENT_SINK_KEY",
] as const;

const ALLOWED_HOSTS_ENV = "MY_PORTAL_PRODLIKE_ALLOWED_HOSTS";
const FORBIDDEN_PRODUCTION_HOSTS = new Set([
  "my.balizero.com",
  "nuzantara-rag.fly.dev",
]);
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);
const SAFE_REQUEST_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const SAFE_PAGE_ERROR_NAMES = new Set([
  "AbortError",
  "Error",
  "NetworkError",
  "NotAllowedError",
  "NotSupportedError",
  "SecurityError",
  "TimeoutError",
  "TypeError",
]);
const WEBKIT_ACCESS_CONTROL_SUFFIX = " due to access control checks.";
const HARNESS_ONLY_MIDDLEWARE_FLAG = "MY_PORTAL_PRODLIKE_ENFORCE_MIDDLEWARE";

type RequiredSyntheticContract = (typeof REQUIRED_SYNTHETIC_CONTRACTS)[number];
type RequiredEndpointContract = (typeof REQUIRED_ENDPOINT_CONTRACTS)[number];
type RequiredMagicLinkContract = (typeof REQUIRED_MAGIC_LINK_CONTRACTS)[number];
type RequiredDocumentSinkContract =
  (typeof REQUIRED_DOCUMENT_SINK_CONTRACTS)[number];
type RequiredContract =
  | RequiredSyntheticContract
  | RequiredEndpointContract
  | RequiredMagicLinkContract
  | RequiredDocumentSinkContract;

export type EnvironmentSource = Readonly<Record<string, string | undefined>>;

export interface ProdlikeEnvironment {
  readonly backendApiUrl: string;
  readonly backendHealthUrl: string;
  readonly clientEmail: string;
  readonly clientPin: string;
  readonly documentFixtureName: string;
  readonly documentSinkFailureUrl: string;
  readonly documentSinkHealthUrl: string;
  readonly documentSinkKey: string;
  readonly documentSinkReceiptUrl: string;
  readonly documentSinkUrl: string;
  readonly disabledClientEmail: string;
  readonly disabledClientPin: string;
  readonly emptyClientEmail: string;
  readonly emptyClientPin: string;
  readonly expiredSessionToken: string;
  readonly frontendPort: number;
  readonly magicLinkInboxUrl: string;
  readonly magicLinkMailSinkUrl: string;
  readonly magicLinkSinkHealthUrl: string;
  readonly magicLinkSinkKey: string;
  readonly partnerEmail: string;
  readonly partnerPin: string;
  readonly supportMailReceiptUrl: string;
}

export class ProdlikePreflightError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProdlikePreflightError";
  }
}

export function isUnsafeWriteRequest(
  method: string,
  requestUrl: string,
  allowedOrigins: ReadonlySet<string>,
): boolean {
  if (SAFE_REQUEST_METHODS.has(method.toUpperCase())) return false;
  return !allowedOrigins.has(new URL(requestUrl).origin);
}

export function isDisallowedNetworkRequest(
  requestUrl: string,
  allowedOrigins: ReadonlySet<string>,
): boolean {
  const parsed = new URL(requestUrl);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return false;
  }
  return !allowedOrigins.has(parsed.origin);
}

export function classifyPageError(error: Error): string {
  if (error.message.endsWith(WEBKIT_ACCESS_CONTROL_SUFFIX)) {
    return "unhandled page error [AccessControlError]";
  }
  const safeName = SAFE_PAGE_ERROR_NAMES.has(error.name)
    ? error.name
    : "OtherError";
  return `unhandled page error [${safeName}]`;
}

function normalizeHostname(hostname: string): string {
  return hostname.toLowerCase().replace(/\.$/, "");
}

function missingContracts(environment: EnvironmentSource): RequiredContract[] {
  return [
    ...REQUIRED_SYNTHETIC_CONTRACTS,
    ...REQUIRED_ENDPOINT_CONTRACTS,
    ...REQUIRED_MAGIC_LINK_CONTRACTS,
    ...REQUIRED_DOCUMENT_SINK_CONTRACTS,
  ].filter((name) => !environment[name]?.trim());
}

function validateSyntheticContracts(environment: EnvironmentSource): void {
  const activeEmail = environment
    .MY_PORTAL_SYNTHETIC_CLIENT_EMAIL!.trim()
    .toLowerCase();
  const emptyEmail = environment
    .MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_EMAIL!.trim()
    .toLowerCase();
  const disabledEmail = environment
    .MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_EMAIL!.trim()
    .toLowerCase();
  const partnerEmail = environment
    .MY_PORTAL_SYNTHETIC_PARTNER_EMAIL!.trim()
    .toLowerCase();
  const supportEmail = environment
    .MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT!.trim()
    .toLowerCase();
  const activePin = environment.MY_PORTAL_SYNTHETIC_CLIENT_PIN!.trim();
  const emptyPin = environment.MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN!.trim();
  const disabledPin =
    environment.MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_PIN!.trim();
  const partnerPin = environment.MY_PORTAL_SYNTHETIC_PARTNER_PIN!.trim();
  const documentFixture =
    environment.MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE!.trim();
  const invoiceFileId = environment.MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID!.trim();

  for (const [name, email] of [
    ["MY_PORTAL_SYNTHETIC_CLIENT_EMAIL", activeEmail],
    ["MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_EMAIL", emptyEmail],
    ["MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_EMAIL", disabledEmail],
    ["MY_PORTAL_SYNTHETIC_PARTNER_EMAIL", partnerEmail],
    ["MY_PORTAL_QA_SUPPORT_MAIL_RECIPIENT", supportEmail],
  ] as const) {
    if (!/^[^@\s]+@example\.com$/.test(email)) {
      throw new ProdlikePreflightError(
        `QA-E2E-001 preflight rejected ${name}: use the reserved example.com domain.`,
      );
    }
  }
  const accountEmails = [activeEmail, emptyEmail, disabledEmail, partnerEmail];
  if (new Set(accountEmails).size !== accountEmails.length) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected the synthetic account contract: portal account emails must be distinct.",
    );
  }
  if (accountEmails.includes(supportEmail)) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected the synthetic mail contract: support and portal account recipients must be distinct.",
    );
  }
  for (const [name, pin] of [
    ["MY_PORTAL_SYNTHETIC_CLIENT_PIN", activePin],
    ["MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN", emptyPin],
    ["MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_PIN", disabledPin],
    ["MY_PORTAL_SYNTHETIC_PARTNER_PIN", partnerPin],
  ] as const) {
    if (!/^\d{4,6}$/.test(pin)) {
      throw new ProdlikePreflightError(
        `QA-E2E-001 preflight rejected ${name}: use a 4-6 digit synthetic PIN.`,
      );
    }
  }
  if (!/^synthetic-portal-[a-z0-9-]+\.pdf$/.test(documentFixture)) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE: use a reserved synthetic PDF fixture name.",
    );
  }
  if (!/^synthetic_invoice_pdf_[a-z0-9_-]{10,200}$/.test(invoiceFileId)) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID: use the reserved synthetic invoice sink namespace.",
    );
  }

  validateExpiredSessionContract(
    environment.MY_PORTAL_SYNTHETIC_EXPIRED_SESSION!.trim(),
  );
}

function validateExpiredSessionContract(token: string): void {
  const parts = token.split(".");
  const fail = (): never => {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_SYNTHETIC_EXPIRED_SESSION: use a signed, already-expired synthetic client JWT.",
    );
  };
  if (
    token.length > 8_192 ||
    parts.length !== 3 ||
    parts.some((part) => !/^[A-Za-z0-9_-]+$/.test(part))
  ) {
    fail();
  }

  let payload: unknown;
  try {
    payload = JSON.parse(
      Buffer.from(parts[1]!, "base64url").toString("utf8"),
    ) as unknown;
  } catch {
    fail();
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    fail();
  }

  const claims = payload as Record<string, unknown>;
  const nowSeconds = Math.floor(Date.now() / 1_000);
  if (
    typeof claims.exp !== "number" ||
    !Number.isInteger(claims.exp) ||
    claims.exp >= nowSeconds ||
    typeof claims.sub !== "string" ||
    typeof claims.email !== "string" ||
    !/^[^@\s]+@example\.com$/.test(claims.email.toLowerCase()) ||
    claims.role !== "client" ||
    typeof claims.client_id !== "number" ||
    !Number.isInteger(claims.client_id)
  ) {
    fail();
  }
}

function parseAllowedHosts(
  environment: EnvironmentSource,
): ReadonlySet<string> {
  const raw = environment[ALLOWED_HOSTS_ENV]?.trim();
  if (!raw) return new Set();

  const hosts = raw
    .split(",")
    .map((host) => normalizeHostname(host.trim()))
    .filter(Boolean);

  for (const host of hosts) {
    if (
      host.includes("://") ||
      host.includes("/") ||
      host.includes(":") ||
      isIP(host) !== 0 ||
      FORBIDDEN_PRODUCTION_HOSTS.has(host)
    ) {
      throw new ProdlikePreflightError(
        `QA-E2E-001 preflight rejected ${ALLOWED_HOSTS_ENV}: entries must be non-production hostnames without schemes, paths, ports, or IP literals.`,
      );
    }
  }

  return new Set(hosts);
}

function parseSafeUrl(
  value: string,
  variableName: RequiredEndpointContract,
  allowedHosts: ReadonlySet<string>,
): URL {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new ProdlikePreflightError(
      `QA-E2E-001 preflight rejected ${variableName}: an explicit absolute URL is required.`,
    );
  }

  const hostname = normalizeHostname(parsed.hostname);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new ProdlikePreflightError(
      `QA-E2E-001 preflight rejected ${variableName}: only HTTP(S) endpoints are allowed.`,
    );
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new ProdlikePreflightError(
      `QA-E2E-001 preflight rejected ${variableName}: credentials, query strings, and fragments are forbidden.`,
    );
  }
  if (FORBIDDEN_PRODUCTION_HOSTS.has(hostname)) {
    throw new ProdlikePreflightError(
      `QA-E2E-001 preflight rejected ${variableName}: a production endpoint is forbidden.`,
    );
  }

  if (LOOPBACK_HOSTS.has(hostname)) {
    if (!parsed.port) {
      throw new ProdlikePreflightError(
        `QA-E2E-001 preflight rejected ${variableName}: loopback endpoints require an explicit port.`,
      );
    }
  } else {
    if (isIP(hostname) !== 0 || !allowedHosts.has(hostname)) {
      throw new ProdlikePreflightError(
        `QA-E2E-001 preflight rejected ${variableName}: use loopback or an explicitly allowlisted non-production hostname.`,
      );
    }
  }

  return parsed;
}

function normalizeBackendApiUrl(parsed: URL): string {
  if (parsed.pathname !== "/" && parsed.pathname !== "/api") {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected NUZANTARA_API_URL: the backend base path must be / or /api.",
    );
  }

  parsed.pathname = "";
  return parsed.origin;
}

function parseFrontendPort(environment: EnvironmentSource): number {
  const portValue = environment.MY_PORTAL_PRODLIKE_PORT?.trim() || "3101";
  const port = Number(portValue);
  if (!Number.isInteger(port) || port < 1024 || port > 65_535) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_PRODLIKE_PORT: use an unprivileged numeric port.",
    );
  }
  return port;
}

function validateMagicLinkSinkKey(environment: EnvironmentSource): string {
  const key = environment.MY_PORTAL_MAGIC_LINK_SINK_KEY!.trim();
  if (!/^[A-Za-z0-9_-]{32,256}$/.test(key)) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_MAGIC_LINK_SINK_KEY: use a strong synthetic sink key.",
    );
  }
  const internalApiKey = environment.NUZANTARA_API_KEY!.trim();
  if (!/^[A-Za-z0-9_-]{32,256}$/.test(internalApiKey)) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected NUZANTARA_API_KEY: use a strong synthetic sink key.",
    );
  }
  if (key !== internalApiKey) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected the mail sink keys: browser and backend contracts must match.",
    );
  }
  return key;
}

function validateDocumentSinkKey(environment: EnvironmentSource): string {
  const key = environment.MY_PORTAL_QA_DOCUMENT_SINK_KEY!.trim();
  if (!/^[A-Za-z0-9_-]{32,256}$/.test(key)) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_QA_DOCUMENT_SINK_KEY: use a strong synthetic sink key.",
    );
  }
  return key;
}

export function loadProdlikeEnvironment(
  environment: EnvironmentSource,
): ProdlikeEnvironment {
  if (environment[HARNESS_ONLY_MIDDLEWARE_FLAG] !== undefined) {
    throw new ProdlikePreflightError(
      `QA-E2E-001 preflight rejected ${HARNESS_ONLY_MIDDLEWARE_FLAG}: the harness injects this loopback-only flag itself.`,
    );
  }

  const missing = missingContracts(environment);
  if (missing.length > 0) {
    throw new ProdlikePreflightError(
      [
        "QA-E2E-001 preflight failed before browser or network startup.",
        "Missing required environment variable names:",
        ...missing.map((name) => `- ${name}`),
        "No environment values were included in this diagnostic.",
      ].join("\n"),
    );
  }
  validateSyntheticContracts(environment);

  const allowedHosts = parseAllowedHosts(environment);
  const backendApi = parseSafeUrl(
    environment.NUZANTARA_API_URL!,
    "NUZANTARA_API_URL",
    allowedHosts,
  );
  const backendHealth = parseSafeUrl(
    environment.MY_PORTAL_BACKEND_HEALTH_URL!,
    "MY_PORTAL_BACKEND_HEALTH_URL",
    allowedHosts,
  );
  const magicLinkMailSink = parseSafeUrl(
    environment.MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL!,
    "MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL",
    allowedHosts,
  );
  const magicLinkInbox = parseSafeUrl(
    environment.MY_PORTAL_MAGIC_LINK_INBOX_URL!,
    "MY_PORTAL_MAGIC_LINK_INBOX_URL",
    allowedHosts,
  );
  const documentSink = parseSafeUrl(
    environment.MY_PORTAL_QA_DOCUMENT_SINK_URL!,
    "MY_PORTAL_QA_DOCUMENT_SINK_URL",
    allowedHosts,
  );
  const internalEmailApi = parseSafeUrl(
    environment.INTERNAL_EMAIL_API_URL!,
    "INTERNAL_EMAIL_API_URL",
    allowedHosts,
  );
  const backendApiUrl = normalizeBackendApiUrl(backendApi);
  const frontendPort = parseFrontendPort(environment);
  const magicLinkSinkKey = validateMagicLinkSinkKey(environment);
  const documentSinkKey = validateDocumentSinkKey(environment);

  if (backendHealth.pathname === "/") {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_BACKEND_HEALTH_URL: an explicit health path is required.",
    );
  }
  if (backendHealth.origin !== backendApiUrl) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_BACKEND_HEALTH_URL: it must use the same origin as NUZANTARA_API_URL.",
    );
  }
  if (
    magicLinkMailSink.protocol !== "http:" ||
    magicLinkInbox.protocol !== "http:" ||
    !LOOPBACK_HOSTS.has(normalizeHostname(magicLinkMailSink.hostname)) ||
    !LOOPBACK_HOSTS.has(normalizeHostname(magicLinkInbox.hostname))
  ) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected the magic-link sink: only explicit loopback HTTP endpoints are allowed.",
    );
  }
  if (magicLinkMailSink.pathname !== "/api/notifications/send-email") {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_MAGIC_LINK_MAIL_SINK_URL: the notification path is invalid.",
    );
  }
  if (magicLinkInbox.pathname !== "/qa/latest-magic-link") {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_MAGIC_LINK_INBOX_URL: the inbox path is invalid.",
    );
  }
  if (magicLinkMailSink.origin !== magicLinkInbox.origin) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected the magic-link sink: notification and inbox endpoints must share one origin.",
    );
  }
  if (internalEmailApi.toString() !== magicLinkMailSink.toString()) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected INTERNAL_EMAIL_API_URL: backend and browser mail sink contracts must match.",
    );
  }
  if (
    documentSink.protocol !== "http:" ||
    !LOOPBACK_HOSTS.has(normalizeHostname(documentSink.hostname)) ||
    documentSink.pathname !== "/"
  ) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected MY_PORTAL_QA_DOCUMENT_SINK_URL: use an explicit loopback HTTP origin without a path.",
    );
  }
  if (documentSink.origin === magicLinkMailSink.origin) {
    throw new ProdlikePreflightError(
      "QA-E2E-001 preflight rejected the document sink: use a dedicated loopback origin.",
    );
  }

  return Object.freeze({
    backendApiUrl,
    backendHealthUrl: backendHealth.toString(),
    clientEmail: environment.MY_PORTAL_SYNTHETIC_CLIENT_EMAIL!.trim(),
    clientPin: environment.MY_PORTAL_SYNTHETIC_CLIENT_PIN!.trim(),
    documentFixtureName:
      environment.MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE!.trim(),
    documentSinkFailureUrl: `${documentSink.origin}/qa/fail-next-upload`,
    documentSinkHealthUrl: `${documentSink.origin}/health`,
    documentSinkKey,
    documentSinkReceiptUrl: `${documentSink.origin}/qa/receipt`,
    documentSinkUrl: documentSink.origin,
    disabledClientEmail:
      environment.MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_EMAIL!.trim(),
    disabledClientPin:
      environment.MY_PORTAL_SYNTHETIC_DISABLED_CLIENT_PIN!.trim(),
    emptyClientEmail:
      environment.MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_EMAIL!.trim(),
    emptyClientPin: environment.MY_PORTAL_SYNTHETIC_EMPTY_CLIENT_PIN!.trim(),
    expiredSessionToken:
      environment.MY_PORTAL_SYNTHETIC_EXPIRED_SESSION!.trim(),
    frontendPort,
    magicLinkInboxUrl: magicLinkInbox.toString(),
    magicLinkMailSinkUrl: magicLinkMailSink.toString(),
    magicLinkSinkHealthUrl: `${magicLinkMailSink.origin}/health`,
    magicLinkSinkKey,
    partnerEmail: environment.MY_PORTAL_SYNTHETIC_PARTNER_EMAIL!.trim(),
    partnerPin: environment.MY_PORTAL_SYNTHETIC_PARTNER_PIN!.trim(),
    supportMailReceiptUrl: `${magicLinkMailSink.origin}/qa/support-mail-receipt`,
  });
}

export async function assertBackendHealthy(
  backendHealthUrl: string,
  fetcher: typeof fetch = globalThis.fetch,
): Promise<void> {
  let response: Response;
  try {
    response = await fetcher(backendHealthUrl, {
      method: "GET",
      headers: { accept: "application/json" },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(5_000),
    });
  } catch {
    throw new ProdlikePreflightError(
      "QA-E2E-001 backend health check failed before browser startup.",
    );
  }

  if (!response.ok) {
    throw new ProdlikePreflightError(
      `QA-E2E-001 backend health check returned HTTP ${response.status} before browser startup.`,
    );
  }
}

export async function assertMagicLinkSinkHealthy(
  sinkHealthUrl: string,
  fetcher: typeof fetch = globalThis.fetch,
): Promise<void> {
  let response: Response;
  try {
    response = await fetcher(sinkHealthUrl, {
      method: "GET",
      headers: { accept: "application/json" },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(5_000),
    });
  } catch {
    throw new ProdlikePreflightError(
      "QA-E2E-001 magic-link sink health check failed before browser startup.",
    );
  }

  if (!response.ok) {
    throw new ProdlikePreflightError(
      `QA-E2E-001 magic-link sink health check returned HTTP ${response.status} before browser startup.`,
    );
  }
}

export async function assertDocumentSinkHealthy(
  sinkHealthUrl: string,
  fetcher: typeof fetch = globalThis.fetch,
): Promise<void> {
  let response: Response;
  try {
    response = await fetcher(sinkHealthUrl, {
      method: "GET",
      headers: { accept: "application/json" },
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(5_000),
    });
  } catch {
    throw new ProdlikePreflightError(
      "QA-E2E-001 document sink health check failed before browser startup.",
    );
  }

  if (!response.ok) {
    throw new ProdlikePreflightError(
      `QA-E2E-001 document sink health check returned HTTP ${response.status} before browser startup.`,
    );
  }
}
