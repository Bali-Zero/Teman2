export interface PricingItem {
  price?: string;
  price_1y?: string;
  price_2y?: string;
  price_1y_off?: string;
  price_1y_on?: string;
  offshore?: string;
  onshore?: string;
  notes?: string;
  description?: string;
  requirements?: string[];
  legacy_names?: string[];
  [key: string]: any;
}

export interface PricingCategory {
  [serviceName: string]: PricingItem;
}

export interface PricingResponse {
  official_notice?: string;
  single_entry_visas?: PricingCategory;
  multiple_entry_visas?: PricingCategory;
  kitas_permits?: PricingCategory;
  business_legal_services?: PricingCategory;
  taxation_services?: PricingCategory;
  quick_quotes?: PricingCategory;
  contact_info?: Record<string, string>;
  disclaimer?: Record<string, string>;
  important_warnings?: Record<string, string>;
  search_query?: string;
  results?: Record<string, PricingCategory>; // For search results
  error?: string;
}
