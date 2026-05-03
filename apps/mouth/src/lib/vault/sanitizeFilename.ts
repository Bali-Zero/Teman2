/**
 * Strip path separators, traversal sequences, reserved characters, and
 * length-cap filenames before upload. Returns "unnamed" for empty input.
 */
export function sanitizeFilename(raw: string): string {
  const cleaned = raw
    .replace(/[\/\\]/g, "_") // path separators
    .replace(/\.\./g, "_") // traversal
    .replace(/[<>:"|?*\x00-\x1f]/g, "_") // reserved + control
    .replace(/^\.+/, "_") // leading dots
    .trim()
    .slice(0, 240);
  return cleaned.length > 0 ? cleaned : "unnamed";
}
