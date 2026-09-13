import { ApiError } from "@/lib/api/error-handler";

/**
 * Turn a thrown api error into the exact text a reviewer should see.
 *
 * `overrides` replaces the text for one status on one call site, so a surface
 * with its own wording for a status (the profile panel's 409, which must read
 * as "no company on file" rather than the register's "already decided") still
 * goes through this single mapping instead of branching on `statusCode` again.
 */
export function describeError(
  e: unknown,
  fallback: string,
  overrides?: Readonly<Record<number, string>>,
): string {
  if (e instanceof ApiError) {
    const override = overrides?.[e.statusCode];
    if (override) return override;
    if (e.statusCode === 401 || e.statusCode === 403) return "Admin only.";
    if (e.statusCode === 404) return e.message || "Not found.";
    if (e.statusCode === 409)
      return e.message || "Conflict — this row was already decided.";
    return e.message || fallback;
  }
  if (e instanceof Error) return e.message || fallback;
  return fallback;
}
