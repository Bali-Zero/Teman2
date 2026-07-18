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
  currentAllowlist?: RoleAllowlist,
): AuthorizationDecision {
  const role = currentAllowlist
    ? effectiveRole(viewer.actorKey, currentAllowlist)
    : viewer.role;
  const version = currentAllowlist?.version ?? viewer.roleConfigVersion;
  const allowed = ROLE_PERMISSIONS[role].has(permission);
  return {
    allowed,
    effectiveRole: role,
    roleConfigVersion: version,
    reason: allowed ? "allowed" : "permission_denied",
  };
}
