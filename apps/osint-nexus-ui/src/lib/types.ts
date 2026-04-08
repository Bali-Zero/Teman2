// Navigation
export type Level = 'orbital' | 'provincial' | 'authority';

export interface NavigationState {
  level: Level;
  province: string | null;
  institution: string | null;
  selectedOfficial: string | null;
}

export type NavigationAction =
  | { type: 'DIVE_PROVINCE'; province: string }
  | { type: 'DIVE_INSTITUTION'; institution: string }
  | { type: 'SELECT_OFFICIAL'; name: string }
  | { type: 'BACK' }
  | { type: 'RESET' };

// Data from API
export interface ProvinceData {
  name: string;
  official_count: number;
  lhkpn_count: number;
  total_assets: number;
  centroid: { lat: number; lng: number };
}

export interface InstitutionData {
  name: string;
  type: InstitutionType;
  lat: number;
  lng: number;
  official_count: number;
  anomaly_count: number;
}

export type InstitutionType =
  | 'kanim' | 'pemprov' | 'dprd' | 'polri'
  | 'pengadilan' | 'kejaksaan' | 'bpk'
  | 'kemenkumham' | 'pajak' | 'bpn';

export interface ProvinceDetail {
  institutions: InstitutionData[];
  stats: { officials: number; lhkpn: number; total_assets: number };
  top_holders: { name: string; jabatan: string; total_assets: number }[];
  anomalies: { official: string; type: string; delta_pct: number; year: number }[];
}

export interface OfficialData {
  name: string;
  jabatan: string;
  nip: string | null;
  has_lhkpn: boolean;
  total_assets: number;
  anomaly: boolean;
}

export interface InstitutionDetail {
  officials: OfficialData[];
  relationships: { from: string; to: string; type: string }[];
}

export interface PropertyItem {
  lokasi: string;
  luas_tanah_m2: number;
  luas_bangunan_m2: number;
  nilai: number;
  sumber: string;
}

export interface VehicleItem {
  jenis: string;
  merk_model: string;
  tahun_perolehan: number;
  nilai: number;
  sumber: string;
}

export interface YearlyAssets {
  properties: PropertyItem[];
  vehicles: VehicleItem[];
  cash: number;
  total: number;
}

export interface OfficialDetail {
  profile: { name: string; jabatan: string; nip: string | null; kantor: string };
  lhkpn_years: number[];
  assets_by_year: Record<number, YearlyAssets>;
  delta: { from_year: number; to_year: number; pct_change: number }[];
}

export interface GraphStats {
  nodes: number;
  relationships: number;
  officials: number;
  lhkpn_reports: number;
}
