// Content Types
export type ContentStatus =
  | 'intake'
  | 'draft'
  | 'review'
  | 'approved'
  | 'scheduled'
  | 'published'
  | 'archived';

export type ContentType =
  | 'article'
  | 'social_post'
  | 'newsletter'
  | 'podcast_script'
  | 'video_script'
  | 'thread';

export type ContentPriority = 'low' | 'normal' | 'high' | 'urgent';

export type ContentCategory =
  | 'immigration'
  | 'tax'
  | 'business'
  | 'property'
  | 'legal'
  | 'bali_news'
  | 'lifestyle'
  | 'general';

export interface Content {
  id: string;
  title: string;
  slug: string;
  type: ContentType;
  status: ContentStatus;
  category: ContentCategory;
  priority: ContentPriority;
  body: string;
  summary?: string;
  author_id: string;
  author_name: string;
  created_at: string;
  updated_at: string;
  published_at?: string;
  scheduled_at?: string;
  metadata: ContentMetadata;
  distributions: Distribution[];
  intel_source_id?: string;
  tags: string[];
}

export interface ContentMetadata {
  word_count: number;
  reading_time_minutes: number;
  ai_generated: boolean;
  ai_model?: string;
  language: string;
  seo_title?: string;
  seo_description?: string;
  cover_image_url?: string;
}

// Distribution Types
export type DistributionPlatform =
  | 'twitter'
  | 'linkedin'
  | 'instagram'
  | 'tiktok'
  | 'telegram'
  | 'whatsapp'
  | 'newsletter'
  | 'website'
  | 'youtube';

export type DistributionStatus = 'pending' | 'scheduled' | 'published' | 'failed';

export interface Distribution {
  id: string;
  content_id: string;
  platform: DistributionPlatform;
  status: DistributionStatus;
  scheduled_at?: string;
  published_at?: string;
  platform_post_id?: string;
  platform_url?: string;
  error_message?: string;
  metrics?: DistributionMetrics;
}

export interface DistributionMetrics {
  impressions: number;
  engagements: number;
  clicks: number;
  shares: number;
}

// Intel Signal Types
export type IntelPriority = 'high' | 'medium' | 'low';

export interface IntelSignal {
  id: string;
  title: string;
  source_name: string;
  source_url: string;
  category: ContentCategory;
  priority: IntelPriority;
  summary: string;
  detected_at: string;
  processed: boolean;
  content_id?: string;
}

// Calendar Types
export interface CalendarEntry {
  id: string;
  title: string;
  type: 'content' | 'distribution' | 'event' | 'deadline';
  date: string;
  time?: string;
  content_id?: string;
  platform?: DistributionPlatform;
  description?: string;
}

// Analytics Types
export interface DashboardMetrics {
  today: {
    published: number;
    scheduled: number;
    in_review: number;
    intel_signals: number;
  };
  week: {
    total_published: number;
    total_engagements: number;
    new_leads: number;
    top_content: Content[];
  };
  platforms: PlatformMetrics[];
}

export interface PlatformMetrics {
  platform: DistributionPlatform;
  followers: number;
  posts_this_week: number;
  engagement_rate: number;
  growth_percent: number;
}

// User Types
export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'editor' | 'writer' | 'viewer';
  avatar_url?: string;
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}
