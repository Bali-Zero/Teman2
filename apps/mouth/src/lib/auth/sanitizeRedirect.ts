const ALLOWED_PREFIXES = ["/portal/", "/workspace/"] as const;

export function sanitizeRedirect(
  raw: string | undefined | null,
): string | null {
  if (!raw) return null;
  if (/[\x00-\x1f\x7f]/.test(raw)) return null;
  if (raw.includes("\\")) return null;
  if (raw.startsWith("//")) return null;
  if (/^[a-z][a-z0-9+.\-]*:/i.test(raw)) return null;
  if (!raw.startsWith("/")) return null;
  if (raw.includes("/../") || raw.endsWith("/..")) return null;
  if (
    !ALLOWED_PREFIXES.some((p) => raw.startsWith(p) || raw === p.slice(0, -1))
  ) {
    return null;
  }
  return raw;
}
