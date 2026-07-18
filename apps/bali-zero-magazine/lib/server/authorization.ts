export type Role = "reader" | "analyst" | "operator";

export type Permission =
  | "magazine:read"
  | "research:create"
  | "research:cancel-own"
  | "ops:read"
  | "ops:create"
  | "story:quarantine";

export type Viewer = Readonly<{
  actorKey: string;
  role: Role;
  roleConfigVersion: string;
}>;

export type RoleAllowlist = Readonly<{
  version: string;
  analysts: readonly string[];
  operators: readonly string[];
}>;

export type AuthorizationDecision = Readonly<{
  allowed: boolean;
  effectiveRole: Role;
  roleConfigVersion: string;
  reason: "allowed" | "permission_denied";
}>;

const ROLE_PERMISSIONS: Readonly<Record<Role, ReadonlySet<Permission>>> = {
  reader: new Set(["magazine:read"]),
  analyst: new Set(["magazine:read", "research:create", "research:cancel-own"]),
  operator: new Set([
    "magazine:read",
    "ops:read",
    "ops:create",
    "story:quarantine",
  ]),
};

export function validateRoleAllowlist(
  allowlist: RoleAllowlist | undefined,
): asserts allowlist is RoleAllowlist {
  if (allowlist === undefined) {
    throw new TypeError("current role allowlist is required");
  }
  if (!allowlist.version || allowlist.version.trim() !== allowlist.version) {
    throw new TypeError("invalid role allowlist version");
  }
  if (
    !Array.isArray(allowlist.analysts) ||
    !Array.isArray(allowlist.operators)
  ) {
    throw new TypeError("invalid role allowlist memberships");
  }
  const memberships = [...allowlist.analysts, ...allowlist.operators];
  for (const actorKey of memberships) {
    if (typeof actorKey !== "string" || !/^[a-f0-9]{64}$/.test(actorKey)) {
      throw new TypeError("invalid actor key in role allowlist");
    }
  }
  if (new Set(memberships).size !== memberships.length) {
    throw new TypeError("duplicate actor key in role allowlist");
  }
}

export function effectiveRole(
  actorKey: string,
  allowlist: RoleAllowlist,
): Role {
  if (allowlist.operators.includes(actorKey)) return "operator";
  if (allowlist.analysts.includes(actorKey)) return "analyst";
  return "reader";
}

export function authorize(
  viewer: Viewer,
  permission: Permission,
  currentAllowlist: RoleAllowlist,
): AuthorizationDecision {
  validateRoleAllowlist(currentAllowlist);
  const role = effectiveRole(viewer.actorKey, currentAllowlist);
  const allowed = ROLE_PERMISSIONS[role].has(permission);
  return {
    allowed,
    effectiveRole: role,
    roleConfigVersion: currentAllowlist.version,
    reason: allowed ? "allowed" : "permission_denied",
  };
}
