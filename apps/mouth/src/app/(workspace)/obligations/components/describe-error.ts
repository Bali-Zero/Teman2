import { ApiError } from "@/lib/api/error-handler";

/** Turn a thrown api error into the exact text a reviewer should see. */
export function describeError(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    if (e.statusCode === 401 || e.statusCode === 403) return "Admin only.";
    if (e.statusCode === 404) return e.message || "Not found.";
    if (e.statusCode === 409)
      return e.message || "Conflict — this row was already decided.";
    return e.message || fallback;
  }
  if (e instanceof Error) return e.message || fallback;
  return fallback;
}
