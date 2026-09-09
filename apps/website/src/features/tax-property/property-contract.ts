import { validCoordinates } from "./coordinates";

export type Fields = Record<string, string | number | boolean | null>;
export interface PropertyAnalysis {
  status: string;
  zone: Fields | null;
  verdict: {
    label: string;
    score: number | null;
    risk_level: string;
    can_invest: boolean | null;
    hard_blocks: string[];
    modifiers: string[];
    breakdown: Record<string, { score: number | null; max: number | null }>;
  } | null;
  opportunities: {
    title_en: string;
    category_en: string;
    pma_open: boolean | null;
  }[];
  kbli: Fields | null;
  roi: Fields | null;
  property_tax: Fields | null;
  overlays: Fields;
  sea_distance_m: number | null;
}
export function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function textValue(value: unknown): string {
  return typeof value === "string" ? value.slice(0, 2000) : "";
}
export function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function fields(value: unknown, keys: string[]): Fields | null {
  const source = record(value),
    result: Fields = {};
  for (const key of keys) {
    const v = source[key];
    if (typeof v === "string") result[key] = textValue(v);
    else if (typeof v === "boolean") result[key] = v;
    else if (numberValue(v) !== null) result[key] = v as number;
  }
  return Object.keys(result).length ? result : null;
}
function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value
        .filter((v): v is string => typeof v === "string")
        .slice(0, 60)
        .map(textValue)
    : [];
}
/** Explicit public projection: client identity, intel articles, raw errors and
 * unrecognised upstream fields never reach the website response. No scoring here. */
export function projectAnalysis(input: unknown): PropertyAnalysis {
  const data = record(input),
    verdict = record(data.verdict),
    roi = record(data.roi);
  const breakdown: NonNullable<PropertyAnalysis["verdict"]>["breakdown"] = {};
  for (const key of [
    "roi",
    "zone_kbli_fit",
    "building_capacity",
    "break_even",
    "risk",
    "flood_risk",
    "market",
    "regulatory",
    "amenity",
  ]) {
    const factor = record(record(verdict.breakdown)[key]);
    if (Object.keys(factor).length)
      breakdown[key] = {
        score: numberValue(factor.score),
        max: numberValue(factor.max),
      };
  }
  const opportunities: PropertyAnalysis["opportunities"] = [];
  const seen = new Set<string>();
  for (const item of Array.isArray(data.opportunities)
    ? data.opportunities
    : []) {
    const o = record(item),
      title = textValue(o.title_en),
      category = textValue(o.category_en),
      key = `${title}|${category}`.toLowerCase();
    if (!title || seen.has(key)) continue;
    seen.add(key);
    opportunities.push({
      title_en: title,
      category_en: category,
      pma_open: typeof o.pma_open === "boolean" ? o.pma_open : null,
    });
    if (opportunities.length === 100) break;
  }
  return {
    status: textValue(data.status) || "unavailable",
    zone: fields(data.zone, [
      "code",
      "zone_code",
      "name",
      "zone_name",
      "source",
      "desa",
      "kecamatan",
      "kdb",
      "klb",
      "kdh",
      "tb",
      "gsb",
      "confidence",
      "is_restricted",
    ]),
    verdict: Object.keys(verdict).length
      ? {
          label: textValue(verdict.label),
          score: numberValue(verdict.score),
          risk_level: textValue(verdict.risk_level),
          can_invest:
            typeof verdict.can_invest === "boolean" ? verdict.can_invest : null,
          hard_blocks: strings(verdict.hard_blocks),
          modifiers: strings(verdict.modifiers),
          breakdown,
        }
      : null,
    opportunities,
    kbli: fields(data.kbli, [
      "code",
      "title",
      "state",
      "reason",
      "oss_risk",
      "max_foreign_ownership",
    ]),
    roi: Object.keys(roi).length
      ? {
          ...fields(roi, ["total_investment_idr", "roi", "bey"]),
          ...fields(roi.golden_strategy, ["roi", "bey"]),
          available: roi.available !== false && !roi.error,
        }
      : null,
    property_tax: fields(data.property_tax, [
      "annual_pbb",
      "pbb_rate_pct",
      "acquisition_bphtb",
      "npoptkp_applied",
      "njop_used",
    ]),
    overlays:
      fields(record(data.zone).overlays ?? data.overlays, [
        "kkop",
        "lp2b",
        "tsunami",
        "heritage",
        "evac_center",
        "flood_risk",
        "temple_buffer",
        "kkop_status",
        "lp2b_status",
        "KKOP_1",
        "LP2B_2",
        "SEMPDN",
        "KRB_03",
        "RESAIR",
        "TEB_05",
        "CAGBUD",
        "HANKAM",
      ]) ?? {},
    sea_distance_m: numberValue(data.sea_distance_m),
  };
}
export interface AnalyzeInput {
  lat: number;
  lng: number;
  kbli_code?: string;
  is_pma?: boolean;
  land_size_m2?: number;
  price_idr?: number;
}
export function parseAnalyzeInput(input: unknown): AnalyzeInput | null {
  const data = record(input);
  if (!validCoordinates(data.lat, data.lng)) return null;
  if (
    data.kbli_code !== undefined &&
    (typeof data.kbli_code !== "string" || !/^\d{5}$/.test(data.kbli_code))
  )
    return null;
  if (data.is_pma !== undefined && typeof data.is_pma !== "boolean")
    return null;
  if (
    [data.land_size_m2, data.price_idr].some(
      (v) =>
        v !== undefined &&
        (typeof v !== "number" || !Number.isFinite(v) || v <= 0 || v > 1e16),
    )
  )
    return null;
  return {
    lat: data.lat as number,
    lng: data.lng as number,
    ...(data.kbli_code ? { kbli_code: data.kbli_code as string } : {}),
    ...(typeof data.is_pma === "boolean" ? { is_pma: data.is_pma } : {}),
    ...(data.land_size_m2 ? { land_size_m2: data.land_size_m2 as number } : {}),
    ...(data.price_idr ? { price_idr: data.price_idr as number } : {}),
  };
}
export interface ZoneFeature {
  type: "Feature";
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: number[][][] | number[][][][];
  };
  properties: Fields;
}
export interface ZoneCollection {
  type: "FeatureCollection";
  features: ZoneFeature[];
}
export function projectZones(input: unknown): ZoneCollection {
  const features: ZoneFeature[] = [];
  for (const value of Array.isArray(record(input).features)
    ? (record(input).features as unknown[])
    : []) {
    const source = record(value),
      geometry = record(source.geometry),
      type = geometry.type;
    if (type !== "Polygon" && type !== "MultiPolygon") continue;
    let points = 0;
    const valid = (v: unknown, depth: number): boolean => {
      if (!Array.isArray(v) || !v.length) return false;
      if (!depth) {
        points++;
        return (
          points <= 100_000 && v.length >= 2 && validCoordinates(v[1], v[0])
        );
      }
      return v.every((item) => valid(item, depth - 1));
    };
    if (!valid(geometry.coordinates, type === "Polygon" ? 2 : 3)) continue;
    const ring = (points: number[][]): number[][] =>
      points.map((point) => [point[0], point[1]]);
    const coordinates =
      type === "Polygon"
        ? (geometry.coordinates as number[][][]).map(ring)
        : (geometry.coordinates as number[][][][]).map((polygon) =>
            polygon.map(ring),
          );
    const properties =
      fields(source.properties, [
        "zone_code",
        "zone_type",
        "max_floors",
        "max_height_meters",
        "kdb",
      ]) ?? {};
    const color = textValue(record(source.properties).color);
    if (/^#[a-f\d]{6}$/i.test(color)) properties.color = color;
    features.push({
      type: "Feature",
      geometry: { type, coordinates },
      properties,
    });
    if (features.length >= 5000) break;
  }
  return { type: "FeatureCollection", features };
}
