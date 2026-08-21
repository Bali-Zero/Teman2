const ALLOWED_COCKPIT_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/**
 * Extract a hostname from an HTTP Host header without accepting proxy lists.
 * The cockpit binds to loopback. Host validation provides DNS-rebinding and
 * origin hygiene only; it is not a substitute for socket-level loopback
 * isolation and must never be described as remote-address enforcement.
 */
export function cockpitHostname(hostHeader: string | null): string | null {
  if (!hostHeader || hostHeader.includes(",")) return null;
  const value = hostHeader.trim().toLowerCase();
  if (!value) return null;

  if (value.startsWith("[")) {
    const closingBracket = value.indexOf("]");
    if (closingBracket === -1) return null;
    const hostname = value.slice(0, closingBracket + 1);
    const suffix = value.slice(closingBracket + 1);
    if (suffix && !/^:\d+$/.test(suffix)) return null;
    return hostname;
  }

  const firstColon = value.indexOf(":");
  if (firstColon === -1) return value;
  if (value.indexOf(":", firstColon + 1) !== -1) return null;
  const suffix = value.slice(firstColon);
  if (!/^:\d+$/.test(suffix)) return null;
  return value.slice(0, firstColon);
}

export function isAllowedCockpitHost(hostHeader: string | null): boolean {
  const hostname = cockpitHostname(hostHeader);
  return hostname !== null && ALLOWED_COCKPIT_HOSTS.has(hostname);
}
