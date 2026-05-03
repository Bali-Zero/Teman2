// Maps both province names AND kota names to centroids.
// Neo4j stores k.kota which may be "Badung"/"Denpasar" rather than "Bali".
export const PROVINCE_CENTROIDS: Record<string, { lat: number; lng: number }> = {
  'Bali':              { lat: -8.4095, lng: 115.1889 },
  'Badung':            { lat: -8.5820, lng: 115.1770 },
  'Denpasar':          { lat: -8.6500, lng: 115.2167 },
  'Gianyar':           { lat: -8.5353, lng: 115.3317 },
  'Tabanan':           { lat: -8.5410, lng: 115.1259 },
  'Buleleng':          { lat: -8.1120, lng: 115.0882 },
  'Karangasem':        { lat: -8.4484, lng: 115.6127 },
  'Klungkung':         { lat: -8.5402, lng: 115.4044 },
  'Bangli':            { lat: -8.4545, lng: 115.3536 },
  'Jembrana':          { lat: -8.3600, lng: 114.6413 },
  'DKI Jakarta':       { lat: -6.2088, lng: 106.8456 },
  'Jakarta':           { lat: -6.2088, lng: 106.8456 },
  'Jawa Barat':        { lat: -6.9175, lng: 107.6191 },
  'Jawa Tengah':       { lat: -7.1510, lng: 110.1403 },
  'Jawa Timur':        { lat: -7.5361, lng: 112.2384 },
  'Sumatera Utara':    { lat:  2.1154, lng:  99.5451 },
  'Sulawesi Selatan':  { lat: -3.6688, lng: 119.9741 },
  'Kalimantan Timur':  { lat:  1.6407, lng: 116.4194 },
};

export interface BaliInstitution {
  name: string;
  type: string;
  lat: number;
  lng: number;
}

export const BALI_INSTITUTIONS: BaliInstitution[] = [
  { name: 'Kantor Imigrasi Kelas I TPI Ngurah Rai', type: 'kanim', lat: -8.7467, lng: 115.1667 },
  { name: 'Kantor Imigrasi Kelas II TPI Singaraja', type: 'kanim', lat: -8.1161, lng: 115.0920 },
  { name: 'Kantor Gubernur Bali', type: 'pemprov', lat: -8.6561, lng: 115.2179 },
  { name: 'DPRD Provinsi Bali', type: 'dprd', lat: -8.6548, lng: 115.2197 },
  { name: 'Polda Bali', type: 'polri', lat: -8.6501, lng: 115.2166 },
  { name: 'Pengadilan Tinggi Denpasar', type: 'pengadilan', lat: -8.6543, lng: 115.2231 },
  { name: 'Kejaksaan Tinggi Bali', type: 'kejaksaan', lat: -8.6502, lng: 115.2195 },
  { name: 'BPK Perwakilan Bali', type: 'bpk', lat: -8.6565, lng: 115.2280 },
  { name: 'Kanwil Kemenkumham Bali', type: 'kemenkumham', lat: -8.6326, lng: 115.2447 },
  { name: 'KPP Pratama Denpasar Barat', type: 'pajak', lat: -8.6608, lng: 115.2048 },
  { name: 'KPP Pratama Denpasar Timur', type: 'pajak', lat: -8.6725, lng: 115.2445 },
  { name: 'BPN Kota Denpasar', type: 'bpn', lat: -8.6547, lng: 115.2352 },
];

export const PROVINCIAL_CAMERAS: Record<string, { lat: number; lng: number; range: number; tilt: number }> = {
  'Bali': { lat: -8.65, lng: 115.22, range: 120_000, tilt: 45 },
};

export const ORBITAL_CAMERA = {
  center: { lat: -2.5, lng: 118.0 },
  tilt: 25,
  range: 4_500_000,
  heading: 0,
};

export const PYLON_COLORS: Record<string, { beam: string; ring: string }> = {
  kanim:       { beam: '#8b9cf7', ring: 'rgba(139, 156, 247, 0.20)' },
  pemprov:     { beam: '#d4845a', ring: 'rgba(212, 132, 90, 0.20)' },
  dprd:        { beam: '#d4845a', ring: 'rgba(212, 132, 90, 0.15)' },
  polri:       { beam: '#e8a849', ring: 'rgba(232, 168, 73, 0.15)' },
  pengadilan:  { beam: '#8b9cf7', ring: 'rgba(139, 156, 247, 0.15)' },
  kejaksaan:   { beam: 'rgba(212, 132, 90, 0.6)', ring: 'rgba(212, 132, 90, 0.10)' },
  bpk:         { beam: 'rgba(139, 156, 247, 0.6)', ring: 'rgba(139, 156, 247, 0.10)' },
  kemenkumham: { beam: '#8b9cf7', ring: 'rgba(139, 156, 247, 0.15)' },
  pajak:       { beam: 'rgba(139, 156, 247, 0.6)', ring: 'rgba(139, 156, 247, 0.10)' },
  bpn:         { beam: 'rgba(139, 156, 247, 0.6)', ring: 'rgba(139, 156, 247, 0.10)' },
};
