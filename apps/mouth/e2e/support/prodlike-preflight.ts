import { isIP } from "node:net";

export const REQUIRED_SYNTHETIC_CONTRACTS = [
  "MY_PORTAL_SYNTHETIC_CLIENT_EMAIL",
  "MY_PORTAL_SYNTHETIC_CLIENT_PIN",
  "MY_PORTAL_SYNTHETIC_TENANT_ID",
  "MY_PORTAL_SYNTHETIC_ACTIVE_ACCOUNT",
  "MY_PORTAL_SYNTHETIC_EMPTY_ACCOUNT",
  "MY_PORTAL_SYNTHETIC_EXPIRED_SESSION",
  "MY_PORTAL_SYNTHETIC_WRONG_TENANT_SESSION",
  "MY_PORTAL_SYNTHETIC_MAGIC_LINK_INBOX",
  "MY_PORTAL_MAGIC_LINK_MAIL_SINK",
  "MY_PORTAL_SUPPORT_MAIL_SINK",
  "MY_PORTAL_SYNTHETIC_DOCUMENT_FIXTURE",
  "MY_PORTAL_EXTERNAL_SIDE_EFFECT_SINK",
] as const;

const REQUIRED_ENDPOINT_CONTRACTS = [
  "NUZANTARA_API_URL",
  "MY_PORTAL_BACKEND_HEALTH_URL",
] as const;

const ALLOWED_HOSTS_ENV = "MY_PORTAL_PRODLIKE_ALLOWED_HOSTS";
const FORBIDDEN_PRODUCTION_HOSTS = new Set([
  "my.balizero.com",
  "nuzantara-rag.fly.dev",
]);
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);
const SAFE_REQUEST_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

type RequiredSyntheticContract = (typeof REQUIRED_SYNTHETIC_CONTRACTS)[number];
type RequiredEndpointContract = (typeof REQUIRED_ENDPOINT_CONTRACTS)[number];
type RequiredContract = RequiredSyntheticContract | RequiredEndpointContract;

export type EnvironmentSource = Readonly<Record<string, string | undefined>>;

export interface ProdlikeEnvironment {
  readonly backendApiUrl: string;
  readonly backendHealthUrl: string;
  readonly clientEmail: string;
  readonly clientPin: string;
  readonly frontendPort: number;
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

function normalizeHostname(hostname: string): string {
  return hostname.toLowerCase().replace(/\.$/, "");
}

function missingContracts(environment: EnvironmentSource): RequiredContract[] {
  return [
    ...REQUIRED_SYNTHETIC_CONTRACTS,
    ...REQUIRED_ENDPOINT_CONTRACTS,
  ].filter((name) => !environment[name]?.trim());
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

export function loadProdlikeEnvironment(
  environment: EnvironmentSource,
): ProdlikeEnvironment {
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
  const backendApiUrl = normalizeBackendApiUrl(backendApi);
  const frontendPort = parseFrontendPort(environment);

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

  return Object.freeze({
    backendApiUrl,
    backendHealthUrl: backendHealth.toString(),
    clientEmail: environment.MY_PORTAL_SYNTHETIC_CLIENT_EMAIL!.trim(),
    clientPin: environment.MY_PORTAL_SYNTHETIC_CLIENT_PIN!.trim(),
    frontendPort,
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
