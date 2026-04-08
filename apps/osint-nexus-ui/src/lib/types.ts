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
  pangkat: string | null;
  angkatan: string | null;
  asal: string | null;
  agama: string | null;
  ttl: string | null;
  kantors: string[];
  has_lhkpn: boolean;
  total_assets: number;
  asset_count: number;
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

export interface ConnectionItem {
  name: string;
  type: string;
}

export interface FamilyConnection {
  name: string;
  type: string;
  notes: string | null;
  person_type: string | null;
}

export interface MetWithConnection {
  name: string;
  type: string;
  context: string | null;
  predicate: string | null;
}

export interface SupervisionConnection {
  name: string;
  jabatan: string | null;
}

export interface AlumniConnection {
  name: string;
  angkatan: string | null;
}

export interface WorkplaceConnection {
  name: string;
  type: string;
  jabatan: string | null;
  context: string | null;
}

export interface OfficialConnections {
  family: FamilyConnection[];
  met_with: MetWithConnection[];
  subordinates: SupervisionConnection[];
  supervisors: SupervisionConnection[];
  alumni: AlumniConnection[];
  children: { name: string }[];
  workplaces: WorkplaceConnection[];
}

export interface OfficialProfile {
  name: string;
  jabatan: string;
  nip: string | null;
  kantor: string;
  pangkat: string | null;
  angkatan: string | null;
  asal: string | null;
  agama: string | null;
  ttl: string | null;
  kantors: string[];
}

export interface OfficialDetail {
  profile: OfficialProfile;
  connections: OfficialConnections;
  lhkpn_years: number[];
  assets_by_year: Record<number, YearlyAssets>;
  delta: { from_year: number; to_year: number; pct_change: number }[];
}

export interface NodesByType {
  Officials: number;
  Properties: number;
  Vehicles: number;
  BankAccounts: number;
  Organizations: number;
  Kanim_Office: number;
  Persons: number;
}

export interface RelsByType {
  OWNS: number;
  WORKS_AT: number;
  FAMILY_OF: number;
  MET_WITH: number;
  SUPERVISES: number;
  PART_OF: number;
}

export interface GraphStats {
  nodes: number;
  relationships: number;
  officials: number;
  lhkpn_reports: number;
  nodes_by_type: NodesByType;
  rels_by_type: RelsByType;
}

/** Organization data */
export interface OrganizationData {
  name: string;
  tipe: string | null;
  lokasi: string | null;
  official_count: number;
  officials: string[];
}

/** Hierarchy chain node */
export interface HierarchyNode {
  name: string;
  type: string;
}

/** PART_OF chain */
export interface HierarchyChain {
  chain: HierarchyNode[];
}

/** SUPERVISES chain */
export interface SupervisesChain {
  chain: { name: string; jabatan: string | null }[];
}

/** Relationship intel for StatsOverview */
export interface RelationshipIntel {
  from: string;
  to: string;
  type: string;
  context: string | null;
  predicate: string | null;
  notes: string | null;
}

/** Person entity */
export interface PersonData {
  name: string;
  person_type: string | null;
  notes: string | null;
  relationship_to_us: string | null;
  connected_to: string[];
}
