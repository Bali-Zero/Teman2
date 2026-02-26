// =============================================================================
// KBLI Code → Bali Zero Article mapping
// Links KBLI Navigator pages back to full editorial articles on balizero.com
// =============================================================================

export interface KBLIArticle {
  slug: string;
  title: string;
  /** Emoji icon for the sector */
  icon: string;
  /** Two CSS gradient colors [from, to] — vibrant, unique per sector */
  gradient: [string, string];
}

/**
 * Maps KBLI 2025 code prefixes (2-digit sector) → relevant article.
 * A code like "56101" matches the "56" entry first.
 * Exact 5-digit codes take priority over prefix matches.
 */
const KBLI_ARTICLE_MAP: Record<string, KBLIArticle> = {
  "56": {
    slug: "kbli-2025-food-beverage-fnb",
    title:
      "KBLI 2025 Food & Beverage Codes: Restaurant, Cafe, Bar & Catering Licenses",
    icon: "🍽",
    gradient: ["#e85d04", "#f48c06"],
  },
  "55": {
    slug: "kbli-2025-hospitality-accommodation",
    title:
      "KBLI 2025 Hospitality & Accommodation: Hotels, Villas & Guesthouses in Bali",
    icon: "🏨",
    gradient: ["#7b2cbf", "#c77dff"],
  },
  "68": {
    slug: "kbli-2025-real-estate-property",
    title:
      "KBLI 2025 Real Estate Codes: Property Development, Management & Investment",
    icon: "🏗",
    gradient: ["#0077b6", "#48cae4"],
  },
  "47": {
    slug: "kbli-2025-retail-ecommerce",
    title:
      "KBLI 2025 Retail & E-Commerce: Online Selling, Boutiques & Specialty Shops",
    icon: "🛍",
    gradient: ["#d00000", "#e85d04"],
  },
  "62": {
    slug: "kbli-2025-it-services-software",
    title:
      "KBLI 2025 IT & Software: Tech Startup, SaaS & Digital Agency Licenses",
    icon: "💻",
    gradient: ["#3a0ca3", "#7209b7"],
  },
  "63": {
    slug: "kbli-2025-it-services-software",
    title:
      "KBLI 2025 IT & Software: Tech Startup, SaaS & Digital Agency Licenses",
    icon: "💻",
    gradient: ["#3a0ca3", "#7209b7"],
  },
  "79": {
    slug: "kbli-2025-tourism-travel-services",
    title:
      "KBLI 2025 Tourism & Travel: Tour Operators, Travel Agents & Guide Services",
    icon: "✈️",
    gradient: ["#006d77", "#83c5be"],
  },
  "01": {
    slug: "kbli-2025-agriculture-agritourism",
    title:
      "KBLI 2025 Agriculture & Agritourism: Farming, Plantation & Eco-Tourism",
    icon: "🌿",
    gradient: ["#2d6a4f", "#52b788"],
  },
  "41": {
    slug: "kbli-2025-construction-building",
    title:
      "KBLI 2025 Construction: Building Development, Villa Projects & Prefab",
    icon: "🔨",
    gradient: ["#774936", "#c6893e"],
  },
  "42": {
    slug: "kbli-2025-construction-building",
    title:
      "KBLI 2025 Construction: Building Development, Villa Projects & Prefab",
    icon: "🔨",
    gradient: ["#774936", "#c6893e"],
  },
  "43": {
    slug: "kbli-2025-construction-building",
    title:
      "KBLI 2025 Construction: Building Development, Villa Projects & Prefab",
    icon: "🔨",
    gradient: ["#774936", "#c6893e"],
  },
  "70": {
    slug: "kbli-2025-consulting-professional-services",
    title:
      "KBLI 2025 Consulting & Professional Services: The Safest Sector for Foreign Investors",
    icon: "📊",
    gradient: ["#1d3557", "#457b9d"],
  },
  "73": {
    slug: "kbli-2025-creative-design-industry",
    title:
      "KBLI 2025 Creative Industry: Design, Photography, Film, Gaming & Content",
    icon: "🎨",
    gradient: ["#f72585", "#b5179e"],
  },
  "74": {
    slug: "kbli-2025-creative-design-industry",
    title:
      "KBLI 2025 Creative Industry: Design, Photography, Film, Gaming & Content",
    icon: "🎨",
    gradient: ["#f72585", "#b5179e"],
  },
  "59": {
    slug: "kbli-2025-creative-design-industry",
    title:
      "KBLI 2025 Creative Industry: Design, Photography, Film, Gaming & Content",
    icon: "🎬",
    gradient: ["#f72585", "#b5179e"],
  },
  "60": {
    slug: "kbli-2025-streaming-digital-media",
    title:
      "KBLI 2025 Streaming & Digital Media: Audio, Video & Social Platforms in Indonesia",
    icon: "📡",
    gradient: ["#560bad", "#9d4edd"],
  },
  "85": {
    slug: "kbli-2025-education-training",
    title:
      "KBLI 2025 Education & Training: Schools, Language Centers & Training",
    icon: "🎓",
    gradient: ["#0466c8", "#7fb3e3"],
  },
  "86": {
    slug: "kbli-2025-healthcare-wellness",
    title:
      "KBLI 2025 Healthcare & Wellness: Hospital, Clinic & Medical Business Codes",
    icon: "🏥",
    gradient: ["#38b000", "#70e000"],
  },
  "96": {
    slug: "kbli-2025-healthcare-wellness",
    title:
      "KBLI 2025 Healthcare & Wellness: Hospital, Clinic & Medical Business Codes",
    icon: "💆",
    gradient: ["#38b000", "#70e000"],
  },
  "10": {
    slug: "kbli-2025-manufacturing-production",
    title: "KBLI 2025 Manufacturing & Production: Industrial Business Codes",
    icon: "🏭",
    gradient: ["#495057", "#adb5bd"],
  },
  "38": {
    slug: "kbli-2025-green-economy-waste",
    title:
      "KBLI 2025 Green Economy: Waste Management, Recycling & Environmental Business",
    icon: "♻️",
    gradient: ["#1b4332", "#40916c"],
  },
  "77": {
    slug: "kbli-2025-retail-ecommerce",
    title:
      "KBLI 2025 Retail & E-Commerce: Online Selling, Boutiques & Specialty Shops",
    icon: "🛍",
    gradient: ["#d00000", "#e85d04"],
  },
  "11": {
    slug: "kbli-2025-manufacturing-production",
    title: "KBLI 2025 Manufacturing & Production: Industrial Business Codes",
    icon: "🏭",
    gradient: ["#495057", "#adb5bd"],
  },
  "16": {
    slug: "kbli-2025-manufacturing-production",
    title: "KBLI 2025 Manufacturing & Production: Industrial Business Codes",
    icon: "🪵",
    gradient: ["#495057", "#adb5bd"],
  },
  "23": {
    slug: "kbli-2025-manufacturing-production",
    title: "KBLI 2025 Manufacturing & Production: Industrial Business Codes",
    icon: "🪨",
    gradient: ["#495057", "#adb5bd"],
  },
  "32": {
    slug: "kbli-2025-manufacturing-production",
    title: "KBLI 2025 Manufacturing & Production: Industrial Business Codes",
    icon: "💎",
    gradient: ["#495057", "#adb5bd"],
  },
  "93": {
    slug: "kbli-2025-tourism-travel-services",
    title:
      "KBLI 2025 Tourism & Travel: Tour Operators, Travel Agents & Guide Services",
    icon: "🏖",
    gradient: ["#006d77", "#83c5be"],
  },
  "46": {
    slug: "kbli-2025-retail-ecommerce",
    title:
      "KBLI 2025 Retail & E-Commerce: Online Selling, Boutiques & Specialty Shops",
    icon: "📦",
    gradient: ["#d00000", "#e85d04"],
  },
};

const BALIZERO_BASE = "https://balizero.com/business";

/**
 * Get the related article for a KBLI code.
 * Tries exact 5-digit match first, then falls back to 2-digit sector prefix.
 */
export function getRelatedArticle(
  code: string,
): (KBLIArticle & { url: string }) | null {
  const exact = KBLI_ARTICLE_MAP[code];
  if (exact) {
    return { ...exact, url: `${BALIZERO_BASE}/${exact.slug}` };
  }

  const prefix = code.slice(0, 2);
  const byPrefix = KBLI_ARTICLE_MAP[prefix];
  if (byPrefix) {
    return { ...byPrefix, url: `${BALIZERO_BASE}/${byPrefix.slug}` };
  }

  return null;
}
