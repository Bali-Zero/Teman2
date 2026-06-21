const AUTH_COOKIE_NAME = "nz_access_token";
const AUTH_PROFILE_TIMEOUT_MS = 5_000;
const EXTERNAL_ROLES = new Set(["client", "partner"]);
const INTERNAL_EMAIL_DOMAINS = [
  "@balizero.com",
  "@zantara.io",
  "@nuzantara.com",
];
const INTERNAL_ROLES = new Set([
  "accounting",
  "admin",
  "board",
  "board member",
  "ceo",
  "finance",
  "founder",
  "marketing",
  "member",
  "operations",
  "ops",
  "owner",
  "sales",
  "tax",
  "team",
  "zero",
]);
const INTERNAL_JOB_TITLE_ROLES = new Set([
  "consultant",
  "executive consultant",
]);

interface VoiceConciergeAuthOptions {
  technicalTokenEnv?: string;
}

interface ProfileEnvelope {
  data?: unknown;
}

interface UserProfileLike {
  email?: unknown;
  role?: unknown;
  role_level?: unknown;
}

interface HeaderReader {
  get(name: string): string | null;
}

export function isProduction(): boolean {
  return process.env.NODE_ENV === "production";
}

export function getVoiceConciergeInternalApiKey(): string | undefined {
  return process.env.VOICE_CONCIERGE_BACKEND_API_KEY?.trim() || undefined;
}

export function getVoiceConciergeBackendBaseUrl(): string | undefined {
  const raw =
    process.env.VOICE_CONCIERGE_BACKEND_URL || process.env.NUZANTARA_API_URL;
  if (!raw) return undefined;
  return raw.replace(/\/+$/, "").replace(/\/api$/, "");
}

export async function canAccessVoiceConcierge(
  request: Request,
  options: VoiceConciergeAuthOptions = {},
): Promise<boolean> {
  return canAccessVoiceConciergeHeaders(request.headers, options);
}

export async function canAccessVoiceConciergeHeaders(
  headers: HeaderReader,
  options: VoiceConciergeAuthOptions = {},
): Promise<boolean> {
  if (!isProduction()) return true;
  if (hasTechnicalToken(headers, options.technicalTokenEnv)) return true;

  const sessionToken = getSessionToken(headers);
  if (!sessionToken) return false;

  const backendBaseUrl = getVoiceConciergeBackendBaseUrl();
  if (!backendBaseUrl) return false;

  try {
    const response = await fetch(`${backendBaseUrl}/api/auth/profile`, {
      method: "GET",
      headers: { Authorization: `Bearer ${sessionToken}` },
      redirect: "error",
      signal: AbortSignal.timeout(AUTH_PROFILE_TIMEOUT_MS),
    });

    if (!response.ok) return false;

    const payload = (await response.json().catch(() => null)) as unknown;
    return isInternalProfile(extractProfile(payload));
  } catch {
    return false;
  }
}

function hasTechnicalToken(
  headers: HeaderReader,
  technicalTokenEnv: string | undefined,
): boolean {
  if (!technicalTokenEnv) return false;

  const token = process.env[technicalTokenEnv]?.trim();
  if (!token) return false;

  return (
    headers.get("authorization") === `Bearer ${token}` ||
    headers.get("x-voice-lab-token") === token
  );
}

function getSessionToken(headers: HeaderReader): string | undefined {
  const authorization = headers.get("authorization");
  const bearerToken = authorization?.match(/^Bearer\s+(.+)$/i)?.[1]?.trim();
  if (bearerToken) return bearerToken;

  return getCookieValue(headers.get("cookie"), AUTH_COOKIE_NAME);
}

function getCookieValue(
  cookieHeader: string | null,
  cookieName: string,
): string | undefined {
  if (!cookieHeader) return undefined;

  for (const part of cookieHeader.split(";")) {
    const [rawName, ...rawValue] = part.trim().split("=");
    if (rawName !== cookieName) continue;

    const value = rawValue.join("=").trim();
    return value || undefined;
  }

  return undefined;
}

function extractProfile(payload: unknown): UserProfileLike | undefined {
  if (!isRecord(payload)) return undefined;

  const envelope = payload as ProfileEnvelope;
  if (isRecord(envelope.data)) return envelope.data as UserProfileLike;

  return payload as UserProfileLike;
}

function isInternalProfile(profile: UserProfileLike | undefined): boolean {
  if (!profile) return false;

  // Backend UserProfile defaults role_level to "member", so it is not
  // authoritative enough for this production access decision.
  const roles = [profile.role].flatMap((value) => {
    const normalized = normalizeProfileString(value);
    return normalized ? [normalized] : [];
  });

  const hasInternalEmail = isInternalEmail(profile.email);

  if (roles.some((role) => EXTERNAL_ROLES.has(role))) return false;
  if (roles.some((role) => INTERNAL_ROLES.has(role))) return true;
  if (roles.some((role) => INTERNAL_JOB_TITLE_ROLES.has(role))) {
    return hasInternalEmail;
  }

  return hasInternalEmail;
}

function isInternalEmail(value: unknown): boolean {
  const email = normalizeProfileString(value);
  if (!email) return false;

  return INTERNAL_EMAIL_DOMAINS.some((domain) => email.endsWith(domain));
}

function normalizeProfileString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;

  const normalized = value.trim().toLowerCase();
  return normalized || undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
