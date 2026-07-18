// Node's type-stripping test runner executes the TypeScript source directly.
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import {
  effectiveRole,
  validateRoleAllowlist,
  type RoleAllowlist,
  type Viewer,
} from "./authorization.ts";
// @ts-expect-error TypeScript requires allowImportingTsExtensions for this runtime-safe import.
import { hmacSha256Hex } from "./security.ts";

export type IdentityConfig = Readonly<{
  actorKeySecret: string;
  roleAllowlist: RoleAllowlist;
}>;

function normalizeWorkspaceEmail(raw: string): string {
  const normalized = raw.trim().normalize("NFC").toLowerCase();
  if (
    normalized.length > 254 ||
    normalized.includes(",") ||
    /[\u0000-\u001f\u007f\s]/.test(normalized) ||
    !/^[^@]+@[^@]+$/.test(normalized)
  ) {
    throw new TypeError("invalid authenticated user email");
  }
  return normalized;
}

export async function requireViewer(
  headers: Headers,
  config: IdentityConfig,
): Promise<Viewer> {
  const rawEmail = headers.get("oai-authenticated-user-email");
  if (rawEmail === null || rawEmail.trim() === "") {
    throw new TypeError("authenticated user is required");
  }
  if (!config.actorKeySecret)
    throw new TypeError("actor key secret is required");
  validateRoleAllowlist(config.roleAllowlist);
  const actorKey = await hmacSha256Hex(
    config.actorKeySecret,
    normalizeWorkspaceEmail(rawEmail),
  );
  return {
    actorKey,
    role: effectiveRole(actorKey, config.roleAllowlist),
    roleConfigVersion: config.roleAllowlist.version,
  };
}
