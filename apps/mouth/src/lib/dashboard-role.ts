export type DashboardRole =
  | "zero"
  | "team"
  | "tax"
  | "marketing"
  | "accounting";

export const VALID_ROLES: DashboardRole[] = [
  "zero",
  "team",
  "tax",
  "marketing",
  "accounting",
];

/**
 * Normalizes a raw role string from the API into a typed DashboardRole.
 * Admins always get 'zero'. Unknown roles fall back to 'team'.
 */
export function normalizeDashboardRole(
  raw: string | undefined,
  isAdmin: boolean,
): DashboardRole {
  if (isAdmin) return "zero";
  const lower = raw?.toLowerCase() ?? "";
  const found = VALID_ROLES.find((r) => r === lower);
  return found ?? "team";
}
