"use client";

export const STANDARD_FOLDERS: Record<string, { label: string; icon: string }> =
  {
    "00_Profile": { label: "Profile", icon: "\u{1F464}" },
    "01_Immigration": { label: "Immigration", icon: "\u{1F6C2}" },
    "02_Company": { label: "Company", icon: "\u{1F3E2}" },
    "03_Tax": { label: "Tax", icon: "\u{1F4B0}" },
    "04_Family": {
      label: "Family",
      icon: "\u{1F468}\u200D\u{1F469}\u200D\u{1F467}\u200D\u{1F466}",
    },
    "99_Misc": { label: "Misc", icon: "\u{1F4C1}" },
  };

// Status badge colors
export const STATUS_COLORS: Record<string, string> = {
  inquiry: "bg-blue-500/20 text-blue-400",
  quotation_sent: "bg-yellow-500/20 text-yellow-400",
  sending_invoice: "bg-yellow-500/20 text-yellow-400",
  payment_pending: "bg-orange-500/20 text-orange-400",
  waiting_payment: "bg-orange-500/20 text-orange-400",
  in_progress: "bg-purple-500/20 text-purple-400",
  on_process: "bg-purple-500/20 text-purple-400",
  waiting_documents: "bg-pink-500/20 text-pink-400",
  submitted_to_gov: "bg-indigo-500/20 text-indigo-400",
  approved: "bg-emerald-500/20 text-emerald-400",
  completed: "bg-green-500/20 text-green-400",
  cancelled: "bg-red-500/20 text-red-400",
};

// Alert color styles
export const ALERT_COLORS: Record<string, string> = {
  green: "bg-green-500/20 text-green-400 border-green-500/30",
  yellow: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  red: "bg-red-500/20 text-red-400 border-red-500/30",
  expired: "bg-red-600/30 text-red-300 border-red-600/50",
};

// Document category colors
export const CATEGORY_COLORS: Record<string, string> = {
  visas: "bg-blue-500/20 text-blue-400",
  pma: "bg-purple-500/20 text-purple-400",
  tax: "bg-emerald-500/20 text-emerald-400",
  personal: "bg-orange-500/20 text-orange-400",
  other: "bg-gray-500/20 text-gray-400",
};

// NOTE: Visa prices MUST come from PricingTool/backend API, never hardcoded (Golden Rule).
// This map is only used as a display-name fallback -- price values are intentionally omitted.
export const VISA_DISPLAY_NAMES: Record<string, string> = {
  c1: "C1 Tourist Visa",
  c1_visa: "C1 Tourist Visa",
  d12: "D12 Business Visa",
  voa: "Visa on Arrival",
  e33e: "Retirement KITAS",
  e33g: "Digital Nomad KITAS",
  e28a: "Investor KITAS",
  kitas: "KITAS",
  kitap: "KITAP",
};

// TEAM MEMBERS - Should fetch from API but hardcoded for now as per NewClientPage
export const TEAM_MEMBERS = [
  {
    value: "adit@balizero.com",
    label: "Adit",
    avatar: "/avatars/team/adit.png",
  },
  { value: "ari@balizero.com", label: "Ari", avatar: "/avatars/team/ari.png" },
  {
    value: "krisna@balizero.com",
    label: "Krisna",
    avatar: "/avatars/team/krisna.png",
  },
  { value: "dea@balizero.com", label: "Dea", avatar: "/avatars/team/dea.png" },
  { value: "zero@balizero.com", label: "Anton" },
  { value: "damar@balizero.com", label: "Damar" },
  { value: "vino@balizero.com", label: "Vino" },
  {
    value: "ruslana@balizero.com",
    label: "Ruslana",
    avatar: "/avatars/team/ruslana.jpg",
  },
  {
    value: "anna@balizero.com",
    label: "Anna",
    avatar: "/avatars/team/anna.jpeg",
  },
  {
    value: "marta@balizero.com",
    label: "Marta",
    avatar: "/avatars/team/marta.jpeg",
  },
  {
    value: "olena@balizero.com",
    label: "Olena",
    avatar: "/avatars/team/olena.jpeg",
  },
  { value: "veronika@balizero.com", label: "Veronika" },
  { value: "dewaayu@balizero.com", label: "Dewa Ayu" },
  { value: "faysha@balizero.com", label: "Faysha" },
  { value: "kadek@balizero.com", label: "Kadek" },
  { value: "angel@balizero.com", label: "Angel" },
  { value: "surya@balizero.com", label: "Surya" },
  {
    value: "sahira@balizero.com",
    label: "Sahira",
    avatar: "/avatars/team/sahira.png",
  },
];

// Helper to get team member avatar
export const getTeamMemberAvatar = (email: string): string | undefined => {
  return TEAM_MEMBERS.find((m) => m.value === email)?.avatar;
};
