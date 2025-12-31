/**
 * Visa Types API Types
 * Professional visa cards for Bali Zero Knowledge Base
 */

export interface VisaType {
  id: number;
  code: string;
  name: string;
  category: string;
  duration: string | null;
  extensions: string | null;
  total_stay: string | null;
  renewable: boolean;
  processing_time_normal: string | null;
  processing_time_express: string | null;
  processing_timeline: Record<string, unknown> | null;
  cost_visa: string | null;
  cost_extension: string | null;
  cost_details: {
    government_fees?: string;
    service_fee?: string;
    express_surcharge?: string;
    dpkk_fee?: string;
    visa_fee?: string;
    extension_govt?: string;
    extension_service?: string;
  } | null;
  requirements: string[];
  restrictions: string[];
  allowed_activities: string[];
  benefits: string[];
  process_steps: string[];
  tips: string[];
  foreign_eligible: boolean;
  metadata: {
    popularity?: string;
    difficulty?: string;
    bali_zero_recommended?: boolean;
    age_requirement?: number;
    financial_requirement?: number;
    new_visa?: boolean;
    prerequisite?: string;
    requirement?: string;
  } | null;
  last_updated: string | null;
  created_at: string | null;
}

export interface VisaTypeListResponse {
  items: VisaType[];
  total: number;
  categories: string[];
}

export type VisaCategory = 'KITAS' | 'KITAP' | 'Tourist' | 'Business' | 'Other';

export type VisaDifficulty = 'very_low' | 'low' | 'medium' | 'high' | 'very_high';

export type VisaPopularity = 'low' | 'medium' | 'high' | 'very_high';
