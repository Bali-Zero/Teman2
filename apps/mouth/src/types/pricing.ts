export interface PricingItem {
  // 2026 schema fields
  name?: string;
  description_en?: string;
  icon_id?: string;
  // ``tier_range`` is a [low, high] pair (e.g. ["1.800.000 IDR", "2.000.000 IDR"])
  // when the entry is a price range instead of a single price; ``null`` otherwise.
  tier_range?: [string, string] | null;
  // Legacy / shared fields
  price?: string;
  duration?: string;
  validity?: string;
  notes?: string;
  description?: string;
  requirements?: string[];
  legacy_names?: string[];
  // Legacy 2025 multi-tier price hints (kept for cached-payload tolerance)
  price_1y?: string;
  price_2y?: string;
  price_1y_off?: string;
  price_1y_on?: string;
  offshore?: string;
  onshore?: string;
  [key: string]:
    | string
    | string[]
    | number
    | boolean
    | null
    | undefined
    | [string, string];
}

export interface PricingCategory {
  [serviceName: string]: PricingItem;
}

// ``tax_accounting`` (2026) has one extra nesting level: each sub-block
// (monthly_tax_basic / monthly_tax_bundled / annual_basic_packages /
//  annual_standalone) is itself a ``{name: PricingItem}`` map.
export interface NestedPricingCategory {
  [subBlockName: string]: PricingCategory;
}

export interface PricingResponse {
  official_notice?: string;
  // 2026 categories
  single_entry_visas?: PricingCategory;
  multiple_entry_visas?: PricingCategory;
  kitas_permits?: PricingCategory;
  kitap_permits?: PricingCategory;
  tax_accounting?: NestedPricingCategory;
  company_services?: PricingCategory;
  consultant_services?: PricingCategory;
  other_process?: PricingCategory;
  urgent_processing?: PricingCategory;
  // Legacy 2025 keys (kept so cached payloads + Mouth chat renderer still parse)
  visa_extensions?: PricingCategory;
  business_legal_services?: PricingCategory;
  taxation_services?: PricingCategory;
  urgent_services?: PricingCategory;
  quick_quotes?: PricingCategory;
  // Metadata
  contact_info?: Record<string, string>;
  disclaimer?: Record<string, string>;
  important_warnings?: Record<string, string>;
  search_query?: string;
  results?: Record<string, PricingCategory>; // For search results
  error?: string;
}
