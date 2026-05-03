import { jwtVerify, errors as joseErrors } from 'jose';

/**
 * Organo: admin-dashboard middleware
 *   → consuma JWT emesso dal backend (apps/backend-rag/backend/app/routers/auth.py)
 *   → protegge route DB/Qdrant/KG da accesso non autorizzato (scar: audit 2026-04-18 CRIT-1)
 */

export type AdminRole = 'admin' | 'super_admin' | 'owner';

const ADMIN_ROLES = new Set<AdminRole>(['admin', 'super_admin', 'owner']);

export type VerifyOutcome =
  | { ok: true; email: string; role: AdminRole }
  | { ok: false; reason: 'missing_cookie' | 'bad_token' | 'forbidden_role' };

export interface AdminJwtPayload {
  email?: string;
  sub?: string;
  role?: string;
  type?: string;
  exp?: number;
}

function getSecret(): Uint8Array {
  const raw = process.env.JWT_SECRET_KEY || process.env.JWT_SECRET;
  if (!raw) {
    throw new Error('verify-admin: JWT_SECRET_KEY (or JWT_SECRET) env var missing');
  }
  return new TextEncoder().encode(raw);
}

function getAllowedEmails(): Set<string> | null {
  const raw = process.env.ADMIN_EMAILS;
  if (!raw) return null;
  const emails = raw
    .split(',')
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
  if (emails.length === 0) return null;
  return new Set(emails);
}

/**
 * Verifica cookie JWT per l'admin-dashboard.
 *
 * Regole (cfr. audit 2026-04-18 CRIT-1):
 *  1. Cookie `nz_access_token` presente (stessa SSO degli altri satelliti).
 *  2. JWT HS256 firmato con JWT_SECRET_KEY del backend.
 *  3. Claim `type` deve essere "access" (o assente per backward-compat).
 *  4. Claim `role` ∈ {admin, super_admin, owner}.
 *  5. Se `ADMIN_EMAILS` è configurato, anche l'email deve essere nella lista
 *     (difesa in profondità: protegge se un account team_members viene promosso
 *     a role=admin per errore).
 */
export async function verifyAdminToken(
  token: string | undefined,
  options?: { allowedEmails?: Set<string> | null; secret?: Uint8Array }
): Promise<VerifyOutcome> {
  if (!token) {
    return { ok: false, reason: 'missing_cookie' };
  }

  let payload: AdminJwtPayload;
  try {
    const secret = options?.secret ?? getSecret();
    const verified = await jwtVerify(token, secret, {
      algorithms: ['HS256'],
    });
    payload = verified.payload as AdminJwtPayload;
  } catch (err) {
    // JWTExpired, JWSSignatureVerificationFailed, JWSInvalid, etc.
    // We collapse all of them into a single reason — the middleware never
    // leaks the specific failure mode to the client.
    if (err instanceof joseErrors.JOSEError) {
      return { ok: false, reason: 'bad_token' };
    }
    return { ok: false, reason: 'bad_token' };
  }

  if (payload.type !== undefined && payload.type !== 'access') {
    return { ok: false, reason: 'bad_token' };
  }

  const role = (payload.role ?? '').toLowerCase();
  if (!ADMIN_ROLES.has(role as AdminRole)) {
    return { ok: false, reason: 'forbidden_role' };
  }

  const email = (payload.email ?? payload.sub ?? '').toLowerCase();
  if (!email) {
    return { ok: false, reason: 'bad_token' };
  }

  const allowed = options?.allowedEmails ?? getAllowedEmails();
  if (allowed !== null && allowed !== undefined && !allowed.has(email)) {
    return { ok: false, reason: 'forbidden_role' };
  }

  return { ok: true, email, role: role as AdminRole };
}
