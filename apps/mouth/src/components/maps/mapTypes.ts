export interface Coordinate {
  lat: number;
  lng: number;
  altitude?: number;
}

export interface BusinessOpportunity {
  code?: string;
  title_en: string;
  title_id?: string;
  pma_open?: boolean;
  category_en: string;
}

export interface BuildingCodes {
  zone_name_id: string;
  kdb_pct: number;
  klb_ratio: number;
  kdh_pct: number;
  ktb_pct: number;
  height_limit: string;
  max_height_meters: number | null;
  setback: string;
  notes: string;
}

export interface IntelArticle {
  title: string;
  source_url: string;
  category?: string;
  source_name?: string;
  published_at?: string;
  relevance_score?: number;
}

export interface ZoningInfo {
  status: "found" | "outside_coverage" | "error";
  district?: string;
  subdistrict?: string;
  zone_code?: string;
  zone_name?: string;
  zone_label_en?: string;
  zone_color_hex?: string;
  zone_type?: string;
  zone_description_en?: string;
  is_restricted?: boolean;
  businesses?: BusinessOpportunity[];
  overlays?: Record<string, string>;
  building_codes?: BuildingCodes;
  allowed_kbli?: string[];
  risk_score?: number;
  avg_price_per_are?: number;
  intel_articles?: IntelArticle[];
  source?: string;
  message?: string;
}

/** Google Maps 3D Element (beta API — no official typings) */
export interface Map3DElementInstance {
  center: { lat: number; lng: number; altitude: number };
  tilt: number;
  range: number;
  heading: number;
  append: (child: HTMLElement) => void;
  appendChild: (child: Node) => Node;
  addEventListener: (
    type: string,
    handler: (event: Map3DClickEvent) => void,
  ) => void;
}

export interface Map3DClickEvent {
  position?: { lat: number; lng: number };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Google Maps beta constructors from importLibrary have no typings
export type GoogleMapsConstructor = new (...args: unknown[]) => any;

export interface MapLayers {
  zoneColors: boolean;
  extrusion: boolean;
  kkop: boolean;
  lp2b: boolean;
  tsunami: boolean;
  floodRisk: boolean;
  templeBuffer: boolean;
}
