/**
 * Rebuilds the incoming query string for an internal permanent redirect.
 *
 * A 308 without this is a 308 that DROPS the query, and unlike a 307 the loss
 * is cached per client: `/services/visa?utm_source=…` is exactly the URL a
 * campaign targets. The pattern already existed in this tree at
 * kbli-navigator/[[...retainedPath]]/page.tsx; this is that pattern, shared.
 *
 * Forwarding everything is safe here because the destination path is a literal
 * in the caller — there is no user-controlled target to smuggle.
 */
export function forwardSearchParams(
  source: Record<string, string | string[] | undefined>,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(source)) {
    if (typeof value === "string") query.append(key, value);
    else if (Array.isArray(value))
      for (const item of value) query.append(key, item);
  }
  return query.size ? `?${query}` : "";
}
