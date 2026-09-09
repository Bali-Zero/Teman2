/** Adapted from current Mouth parse-coordinates.ts; same supported formats,
 * with whole-input and geographic-range validation at the public boundary. */
export interface Coordinate {
  lat: number;
  lng: number;
}
export function validCoordinates(lat: unknown, lng: unknown): boolean {
  return (
    typeof lat === "number" &&
    Number.isFinite(lat) &&
    lat >= -90 &&
    lat <= 90 &&
    typeof lng === "number" &&
    Number.isFinite(lng) &&
    lng >= -180 &&
    lng <= 180
  );
}
export function parseCoordinates(input: string): Coordinate | null {
  let raw = input.trim().replace(/−/g, "-");
  if (!raw || raw.length > 2048) return null;
  if (/^https?:\/\//i.test(raw)) {
    try {
      const url = new URL(raw);
      if (!/(^|\.)(google\.[a-z.]+|maps\.app\.goo\.gl)$/.test(url.hostname))
        return null;
      raw =
        url.searchParams.get("q") ??
        url.searchParams.get("query") ??
        url.pathname.match(/@(-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?)/)?.[1] ??
        "";
    } catch {
      return null;
    }
  }
  // Retain the legacy longitude-first DMS format, then use one parser.
  const reversed = raw.match(/^(.+[EW])\s*[, ]+\s*(.+[NS])$/i);
  if (reversed) raw = `${reversed[2]}, ${reversed[1]}`;
  const dms =
    /^(\d+(?:\.\d+)?)\s*°\s*(?:(\d+(?:\.\d+)?)\s*['′]\s*)?(?:(\d+(?:\.\d+)?)\s*["″]\s*)?([NS])\s*[, ]+\s*(\d+(?:\.\d+)?)\s*°\s*(?:(\d+(?:\.\d+)?)\s*['′]\s*)?(?:(\d+(?:\.\d+)?)\s*["″]\s*)?([EW])$/i;
  const m = raw.match(dms);
  let lat: number, lng: number;
  if (m) {
    if ([m[2], m[3], m[6], m[7]].some((v) => v && Number(v) >= 60)) return null;
    lat =
      (Number(m[1]) + Number(m[2] ?? 0) / 60 + Number(m[3] ?? 0) / 3600) *
      (m[4].toUpperCase() === "S" ? -1 : 1);
    lng =
      (Number(m[5]) + Number(m[6] ?? 0) / 60 + Number(m[7] ?? 0) / 3600) *
      (m[8].toUpperCase() === "W" ? -1 : 1);
  } else {
    const decimal = raw.match(
      /^(-?\d+(?:\.\d+)?)(?:\s*,\s*|\s+)(-?\d+(?:\.\d+)?)$/,
    );
    if (!decimal) return null;
    lat = Number(decimal[1]);
    lng = Number(decimal[2]);
  }
  return validCoordinates(lat, lng) ? { lat, lng } : null;
}
