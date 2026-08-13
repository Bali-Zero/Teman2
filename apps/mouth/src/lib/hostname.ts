/**
 * Canonical host normalisation for this app.
 *
 * There is exactly one predicate for the question "which host is this
 * request for", and both consumers ask it here:
 *
 *   - `src/proxy.ts`   — routes every request by hostname
 *   - `src/app/robots.ts` — serves per-host robots.txt rules
 *
 * They used to answer it two different ways: proxy.ts stripped a trailing
 * FQDN dot, the port and IPv6 brackets; robots.ts only lowercased. The
 * practical exposure was small (crawlers do not send `Host: example.com.`),
 * but the shape is the recurring defect this repo keeps paying for — two
 * modules deciding the same entity with two different rules drift apart
 * silently, and one starts saying "this is the internal host" while the
 * other says it is not. One question, one place to answer it.
 */
export function normalizeHostname(host: string): string {
  const normalized = host.trim().toLowerCase().replace(/\.$/, "");
  // IPv6 literal: `[::1]:3000` → `::1`
  if (normalized.startsWith("[")) {
    return normalized.slice(1, normalized.indexOf("]"));
  }
  return normalized.split(":", 1)[0];
}
