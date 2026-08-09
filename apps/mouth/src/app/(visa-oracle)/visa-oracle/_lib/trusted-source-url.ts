const EXACT_PRIMARY_SOURCE_HOSTS = new Set([
  "www.imigrasi.go.id",
  "evisa.imigrasi.go.id",
  "kanwilsultra.imigrasi.go.id",
  "kemenimipas.go.id",
  "peraturan.bpk.go.id",
  "www.peraturan.go.id",
]);

function isAllowedHostname(hostname: string): boolean {
  if (hostname.includes("xn--")) return false;
  return EXACT_PRIMARY_SOURCE_HOSTS.has(hostname);
}

/**
 * Return one canonical, render-safe URL only for the official primary-source
 * allowlist. The adapter drops sources that fail this check, so untrusted
 * backend strings cannot become links or decisive evidence in the UI.
 */
export function trustedPrimarySourceUrl(value: string): string | null {
  if (value.trim() !== value || value.length === 0) return null;

  try {
    const parsed = new URL(value);
    const hostname = parsed.hostname.toLowerCase();
    if (parsed.protocol !== "https:") return null;
    if (parsed.username !== "" || parsed.password !== "") return null;
    if (parsed.port !== "") return null;
    if (hostname.endsWith(".")) return null;
    if (!isAllowedHostname(hostname)) return null;
    return parsed.href;
  } catch {
    return null;
  }
}
