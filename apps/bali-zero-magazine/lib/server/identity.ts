// Node's type-stripping test runner executes the TypeScript source directly.
import {
  effectiveRole,
  validateRoleAllowlist,
  type RoleAllowlist,
  type Viewer,
} from "./authorization.ts";
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
  const normalizedEmail = normalizeWorkspaceEmail(rawEmail);
  validateRoleAllowlist(config.roleAllowlist);
  if (!config.actorKeySecret) {
    if (
      config.roleAllowlist.analysts.length > 0 ||
      config.roleAllowlist.operators.length > 0
    ) {
      throw new TypeError("actor key secret is required for privileged roles");
    }
    return {
      actorKey: "0".repeat(64),
      role: "reader",
      roleConfigVersion: config.roleAllowlist.version,
    };
  }
  const actorKey = await hmacSha256Hex(config.actorKeySecret, normalizedEmail);
  return {
    actorKey,
    role: effectiveRole(actorKey, config.roleAllowlist),
    roleConfigVersion: config.roleAllowlist.version,
  };
}
