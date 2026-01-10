/**
 * Bali Zero Insights - Blog System Types
 * "The Chronicle" - Where Ancient Wisdom Meets Modern Intelligence
 */

// ============================================================================
// Article Types
// ============================================================================

export type ArticleStatus = 'draft' | 'review' | 'scheduled' | 'published' | 'archived';

export type ArticleCategory =
  | 'immigration'
  | 'business'
  | 'tax-legal'
  | 'property'
  | 'lifestyle'
  | 'tech';

export type ArticleTone = 'professional' | 'casual' | 'urgent';
export type ArticleLength = 'short' | 'medium' | 'long';

export interface Article {
  id: string;
  slug: string;
  title: string;
  subtitle?: string;
  excerpt: string;
  content: string;                    // MDX content
  coverImage: string;
  coverImageAlt: string;
  category: ArticleCategory;
  tags: string[];

  // Metadata
  author: Author;
  coAuthors?: Author[];
  reviewedBy?: string;                // Legal team verification

  // Timestamps
  createdAt: Date;
  updatedAt: Date;
  publishedAt?: Date;
  scheduledFor?: Date;

  // Status
  status: ArticleStatus;
  featured: boolean;
  trending: boolean;

  // SEO
  seoTitle?: string;
  seoDescription?: string;
  canonicalUrl?: string;

  // Analytics
  readingTime: number;                // minutes
  viewCount: number;
  shareCount: number;
  likeCount: number;
  commentCount: number;

  // AI
  aiGenerated: boolean;
  aiConfidenceScore?: number;
  relatedArticleIds: string[];

  // Multilingual
  locale: 'en' | 'id';
  translations?: ArticleTranslation[];

  // Zantara Integration
  linkedCaseIds?: string[];           // Cases correlati
  linkedClientIds?: string[];         // Clienti interessati
  autoNotifyClients?: boolean;
}

export interface ArticleTranslation {
  locale: 'en' | 'id';
  articleId: string;
}

export interface ArticleListItem {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  coverImage: string;
  category: ArticleCategory;
  author: Author;
  publishedAt: Date;
  readingTime: number;
  viewCount: number;
  featured: boolean;
  trending: boolean;
  aiGenerated: boolean;
}

// ============================================================================
// Author Types
// ============================================================================

export interface Author {
  id: string;
  name: string;
  avatar: string;
  role: string;
  bio?: string;
  isAI: boolean;                      // true = Zantara AI
  socialLinks?: AuthorSocialLinks;
}

export interface AuthorSocialLinks {
  linkedin?: string;
  twitter?: string;
  website?: string;
}

// ============================================================================
// Newsletter Types
// ============================================================================

export interface NewsletterSubscriber {
  id: string;
  email: string;
  name?: string;
  categories: ArticleCategory[];      // Interessi
  frequency: 'daily' | 'weekly' | 'monthly';
  language: 'en' | 'id';
  subscribedAt: Date;
  confirmed: boolean;
  zohoContactId?: string;             // Link a Zoho
}

export interface NewsletterSubscribeRequest {
  email: string;
  name?: string;
  categories: ArticleCategory[];
  frequency: 'daily' | 'weekly' | 'monthly';
  language: 'en' | 'id';
}

export interface NewsletterLog {
  id: string;
  articleId: string;
  recipientCount: number;
  sentAt: Date;
  openRate?: number;
  clickRate?: number;
}

// ============================================================================
// AI Generation Types
// ============================================================================

export interface AIGenerationRequest {
  topic: string;
  category: ArticleCategory;
  tone: ArticleTone;
  targetLength: ArticleLength;
  includeData: boolean;               // Include stats/charts
  sources?: string[];                 // URLs to reference
}

export interface AIGenerationResponse {
  title: string;
  subtitle?: string;
  excerpt: string;
  content: string;
  suggestedTags: string[];
  confidence: number;                 // 0.0 - 1.0
  coverImagePrompt: string;
}

export interface AIContentTrigger {
  id: string;
  source: 'government' | 'news' | 'client_question' | 'manual';
  topic: string;
  category: ArticleCategory;
  urgency: 'low' | 'medium' | 'high';
  sources: string[];
  detectedAt: Date;
  processed: boolean;
}

// ============================================================================
// Search & Filter Types
// ============================================================================

export interface ArticleSearchParams {
  query?: string;
  category?: ArticleCategory;
  tags?: string[];
  authorId?: string;
  status?: ArticleStatus;
  featured?: boolean;
  trending?: boolean;
  aiGenerated?: boolean;
  locale?: 'en' | 'id';
  dateFrom?: Date;
  dateTo?: Date;
  limit?: number;
  offset?: number;
  sortBy?: 'publishedAt' | 'viewCount' | 'readingTime' | 'relevance';
  sortOrder?: 'asc' | 'desc';
}

export interface ArticleSearchResult {
  articles: ArticleListItem[];
  total: number;
  hasMore: boolean;
}

// ============================================================================
// Analytics Types
// ============================================================================

export interface ArticleAnalytics {
  articleId: string;
  views: number;
  uniqueViews: number;
  avgReadTime: number;                // seconds
  completionRate: number;             // percentage who finished
  shares: ShareAnalytics;
  referrers: ReferrerAnalytics[];
  deviceBreakdown: DeviceBreakdown;
}

export interface ShareAnalytics {
  total: number;
  byPlatform: Record<string, number>;
}

export interface ReferrerAnalytics {
  source: string;
  views: number;
  percentage: number;
}

export interface DeviceBreakdown {
  desktop: number;
  mobile: number;
  tablet: number;
}

export interface BlogOverviewStats {
  totalArticles: number;
  publishedArticles: number;
  totalViews: number;
  subscriberCount: number;
  avgReadTime: number;
  topCategories: CategoryStat[];
  recentActivity: ActivityItem[];
}

export interface CategoryStat {
  category: ArticleCategory;
  articleCount: number;
  viewCount: number;
}

export interface ActivityItem {
  type: 'article_published' | 'article_updated' | 'subscriber_joined';
  description: string;
  timestamp: Date;
}

// ============================================================================
// Component Props Types
// ============================================================================

export interface ArticleCardProps {
  article: ArticleListItem;
  variant?: 'default' | 'featured' | 'compact' | 'horizontal';
  index?: number;
  showCategory?: boolean;
  showAuthor?: boolean;
  showReadTime?: boolean;
  className?: string;
}

export interface ArticleGridProps {
  articles: ArticleListItem[];
  variant?: 'masonry' | 'grid' | 'list';
  columns?: 2 | 3 | 4;
  showFeatured?: boolean;
  className?: string;
}

export interface CategoryNavProps {
  categories?: ArticleCategory[];
  activeCategory?: ArticleCategory;
  onCategoryChange?: (category: ArticleCategory | undefined) => void;
  showCounts?: boolean;
  categoryCounts?: Record<ArticleCategory, number>;
  className?: string;
}

export interface NewsletterFormProps {
  variant?: 'inline' | 'modal' | 'sidebar';
  defaultCategories?: ArticleCategory[];
  onSuccess?: () => void;
  className?: string;
}

export interface SearchBarProps {
  placeholder?: string;
  defaultValue?: string;
  onSearch?: (query: string) => void;
  showFilters?: boolean;
  className?: string;
}

export interface TableOfContentsProps {
  content: string;
  className?: string;
}

export interface ReadingProgressProps {
  className?: string;
}

export interface ShareButtonsProps {
  article: Article;
  className?: string;
}

export interface RelatedArticlesProps {
  articleIds: string[];
  currentArticleId: string;
  maxItems?: number;
  className?: string;
}

export interface AIRecommendationsProps {
  clientId?: string;
  maxItems?: number;
  className?: string;
}

// ============================================================================
// API Response Types
// ============================================================================

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
  pageSize: number;
  hasMore: boolean;
}

// ============================================================================
// Category Metadata
// ============================================================================

export const CATEGORY_METADATA: Record<ArticleCategory, {
  label: string;
  description: string;
  icon: string;
  color: string;
  gradient: string;
}> = {
  immigration: {
    label: 'Immigration',
    description: 'Visas, permits, and relocation guides',
    icon: 'Plane',
    color: 'cyan',
    gradient: 'from-blue-500/20 to-cyan-500/20',
  },
  business: {
    label: 'Business',
    description: 'Company setup, KBLI codes, and regulations',
    icon: 'Building2',
    color: 'emerald',
    gradient: 'from-emerald-500/20 to-teal-500/20',
  },
  'tax-legal': {
    label: 'Tax & Legal',
    description: 'Tax obligations and legal compliance',
    icon: 'Scale',
    color: 'amber',
    gradient: 'from-amber-500/20 to-orange-500/20',
  },
  property: {
    label: 'Property',
    description: 'Real estate and property ownership',
    icon: 'Home',
    color: 'rose',
    gradient: 'from-rose-500/20 to-pink-500/20',
  },
  lifestyle: {
    label: 'Lifestyle',
    description: 'Living in Bali and Indonesia',
    icon: 'Sun',
    color: 'violet',
    gradient: 'from-violet-500/20 to-purple-500/20',
  },
  tech: {
    label: 'Tech',
    description: 'Digital nomad and tech industry insights',
    icon: 'Cpu',
    color: 'fuchsia',
    gradient: 'from-fuchsia-500/20 to-pink-500/20',
  },
};

// ============================================================================
// Constants
// ============================================================================

export const ZANTARA_AI_AUTHOR: Author = {
  id: 'zantara-ai',
  name: 'Zantara AI',
  avatar: '/static/zantara-avatar.png',
  role: 'AI Research Assistant',
  bio: 'Zantara AI is the intelligent assistant powering Bali Zero Insights, providing accurate and up-to-date information about business and immigration in Indonesia.',
  isAI: true,
};

export const READING_SPEED_WPM = 200;
export const MAX_EXCERPT_LENGTH = 200;
export const MAX_SEO_TITLE_LENGTH = 60;
export const MAX_SEO_DESCRIPTION_LENGTH = 160;
