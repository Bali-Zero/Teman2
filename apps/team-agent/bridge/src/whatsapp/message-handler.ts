export function normalizeJid(jid: string): string {
  return jid.split("@")[0] || "";
}

export function isGroupJid(jid: string): boolean {
  return jid.endsWith("@g.us");
}

export function shouldProcessMessage(
  jid: string,
  whitelistNumber: string,
): boolean {
  if (!jid || !whitelistNumber) return false;
  if (isGroupJid(jid)) return false;
  return normalizeJid(jid) === whitelistNumber;
}
