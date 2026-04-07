import type { Nationality } from './types';

/**
 * Countries that require a Calling Visa (sponsor + interview at Jakarta Immigration).
 * Nationals from these countries cannot get regular eVisa or VOA.
 */
export const CALLING_VISA_COUNTRIES = new Set([
  'Afghanistan',
  'Israel',
  'Liberia',
  'Nigeria',
  'North Korea',
  'Somalia',
]);

/**
 * Countries that require a guarantor/sponsor for eVisa processing.
 * They can enter Indonesia but need company sponsorship.
 */
export const GUARANTOR_REQUIRED_COUNTRIES = new Set([
  'Bangladesh',
  'Cameroon',
  'Congo Republic',
  'El Salvador',
  'Guinea',
  'Iran',
  'Niger',
  'Palestine',
  'Sri Lanka',
  'Sudan',
  'Syria',
  'Yemen',
]);

/** Check if nationality requires calling visa */
export function isCallingVisa(nationality: string): boolean {
  return CALLING_VISA_COUNTRIES.has(nationality);
}

/** Check if nationality requires guarantor sponsor */
export function isGuarantorRequired(nationality: string): boolean {
  return GUARANTOR_REQUIRED_COUNTRIES.has(nationality);
}

export const TOP_NATIONALITIES: Nationality[] = [
  { code: 'AU', name: 'Australia', flag: '🇦🇺' },
  { code: 'US', name: 'USA', flag: '🇺🇸' },
  { code: 'GB', name: 'UK', flag: '🇬🇧' },
  { code: 'RU', name: 'Russia', flag: '🇷🇺' },
  { code: 'CN', name: 'China', flag: '🇨🇳' },
  { code: 'KR', name: 'South Korea', flag: '🇰🇷' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: 'FR', name: 'France', flag: '🇫🇷' },
  { code: 'NL', name: 'Netherlands', flag: '🇳🇱' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦' },
  { code: 'IN', name: 'India', flag: '🇮🇳' },
  { code: 'BR', name: 'Brazil', flag: '🇧🇷' },
  { code: 'IT', name: 'Italy', flag: '🇮🇹' },
  { code: 'SG', name: 'Singapore', flag: '🇸🇬' },
];

const ADDITIONAL_NATIONALITIES: Nationality[] = [
  { code: 'AF', name: 'Afghanistan', flag: '🇦🇫' },
  { code: 'AR', name: 'Argentina', flag: '🇦🇷' },
  { code: 'AT', name: 'Austria', flag: '🇦🇹' },
  { code: 'BD', name: 'Bangladesh', flag: '🇧🇩' },
  { code: 'BE', name: 'Belgium', flag: '🇧🇪' },
  { code: 'CM', name: 'Cameroon', flag: '🇨🇲' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭' },
  { code: 'CL', name: 'Chile', flag: '🇨🇱' },
  { code: 'CO', name: 'Colombia', flag: '🇨🇴' },
  { code: 'CG', name: 'Congo Republic', flag: '🇨🇬' },
  { code: 'CZ', name: 'Czech Republic', flag: '🇨🇿' },
  { code: 'DK', name: 'Denmark', flag: '🇩🇰' },
  { code: 'EG', name: 'Egypt', flag: '🇪🇬' },
  { code: 'SV', name: 'El Salvador', flag: '🇸🇻' },
  { code: 'ES', name: 'Spain', flag: '🇪🇸' },
  { code: 'FI', name: 'Finland', flag: '🇫🇮' },
  { code: 'GR', name: 'Greece', flag: '🇬🇷' },
  { code: 'GN', name: 'Guinea', flag: '🇬🇳' },
  { code: 'HK', name: 'Hong Kong', flag: '🇭🇰' },
  { code: 'HU', name: 'Hungary', flag: '🇭🇺' },
  { code: 'ID', name: 'Indonesia', flag: '🇮🇩' },
  { code: 'IE', name: 'Ireland', flag: '🇮🇪' },
  { code: 'IR', name: 'Iran', flag: '🇮🇷' },
  { code: 'IL', name: 'Israel', flag: '🇮🇱' },
  { code: 'LR', name: 'Liberia', flag: '🇱🇷' },
  { code: 'MX', name: 'Mexico', flag: '🇲🇽' },
  { code: 'MY', name: 'Malaysia', flag: '🇲🇾' },
  { code: 'NE', name: 'Niger', flag: '🇳🇪' },
  { code: 'NG', name: 'Nigeria', flag: '🇳🇬' },
  { code: 'NO', name: 'Norway', flag: '🇳🇴' },
  { code: 'KP', name: 'North Korea', flag: '🇰🇵' },
  { code: 'NZ', name: 'New Zealand', flag: '🇳🇿' },
  { code: 'PK', name: 'Pakistan', flag: '🇵🇰' },
  { code: 'PS', name: 'Palestine', flag: '🇵🇸' },
  { code: 'PH', name: 'Philippines', flag: '🇵🇭' },
  { code: 'PL', name: 'Poland', flag: '🇵🇱' },
  { code: 'PT', name: 'Portugal', flag: '🇵🇹' },
  { code: 'RO', name: 'Romania', flag: '🇷🇴' },
  { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' },
  { code: 'SE', name: 'Sweden', flag: '🇸🇪' },
  { code: 'SO', name: 'Somalia', flag: '🇸🇴' },
  { code: 'LK', name: 'Sri Lanka', flag: '🇱🇰' },
  { code: 'SD', name: 'Sudan', flag: '🇸🇩' },
  { code: 'SY', name: 'Syria', flag: '🇸🇾' },
  { code: 'TH', name: 'Thailand', flag: '🇹🇭' },
  { code: 'TR', name: 'Turkey', flag: '🇹🇷' },
  { code: 'TW', name: 'Taiwan', flag: '🇹🇼' },
  { code: 'UA', name: 'Ukraine', flag: '🇺🇦' },
  { code: 'VN', name: 'Vietnam', flag: '🇻🇳' },
  { code: 'YE', name: 'Yemen', flag: '🇾🇪' },
  { code: 'ZA', name: 'South Africa', flag: '🇿🇦' },
  { code: 'AE', name: 'UAE', flag: '🇦🇪' },
];

export const ALL_NATIONALITIES: Nationality[] = [
  ...TOP_NATIONALITIES,
  ...ADDITIONAL_NATIONALITIES,
].sort((a, b) => a.name.localeCompare(b.name));
