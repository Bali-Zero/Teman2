/**
 * Zantara AI Content Generator
 * Automated article generation and content management
 */

import type {
  Article,
  ArticleCategory,
  AIGenerationRequest,
  AIGenerationResponse,
  AIContentTrigger,
  Author,
  ArticleListItem,
  READING_SPEED_WPM,
  ZANTARA_AI_AUTHOR,
} from './types';

const ZANTARA_API = process.env.NEXT_PUBLIC_ZANTARA_API_URL || process.env.ZANTARA_API_URL;
const ZANTARA_API_KEY = process.env.ZANTARA_API_KEY;

// ============================================================================
// Zantara AI Writer Service
// ============================================================================

export class ZantaraAIWriter {
  /**
   * Generate a complete article with Zantara AI
   */
  static async generateArticle(
    request: AIGenerationRequest
  ): Promise<Partial<Article>> {
    const response = await fetch(`${ZANTARA_API}/api/blog/ai-generate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ZANTARA_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: this.buildPrompt(request),
        maxTokens: this.getTokenLimit(request.targetLength),
        temperature: 0.7,
        includeStructure: true,
      }),
    });

    if (!response.ok) {
      throw new Error(`AI generation failed: ${response.statusText}`);
    }

    const aiContent: AIGenerationResponse = await response.json();

    // Generate cover image with AI
    const coverImage = await this.generateCoverImage(request.topic, request.category);

    // Generate SEO metadata
    const seoData = this.generateSEO(aiContent.title, aiContent.excerpt);

    // Find related articles
    const relatedIds = await this.findRelatedArticles(request.topic, request.category);

    return {
      title: aiContent.title,
      subtitle: aiContent.subtitle,
      excerpt: aiContent.excerpt,
      content: aiContent.content,
      coverImage,
      coverImageAlt: `Cover image for: ${aiContent.title}`,
      category: request.category,
      tags: aiContent.suggestedTags,
      readingTime: this.calculateReadingTime(aiContent.content),
      seoTitle: seoData.title,
      seoDescription: seoData.description,
      aiGenerated: true,
      aiConfidenceScore: aiContent.confidence,
      relatedArticleIds: relatedIds,
      status: 'review', // Always review AI-generated content
      author: {
        id: 'zantara-ai',
        name: 'Zantara AI',
        avatar: '/static/zantara-avatar.png',
        role: 'AI Research Assistant',
        isAI: true,
      },
      featured: false,
      trending: false,
      viewCount: 0,
      shareCount: 0,
      locale: 'en',
    };
  }

  /**
   * Monitor sources and auto-generate articles
   */
  static async monitorAndGenerate(): Promise<{
    processed: number;
    generated: number;
    triggers: AIContentTrigger[];
  }> {
    const triggers: AIContentTrigger[] = [];

    // 1. Check government APIs for new regulations
    const newRegulations = await this.checkGovernmentSources();
    triggers.push(...newRegulations);

    // 2. Check news feeds
    const relevantNews = await this.checkNewsSources();
    triggers.push(...relevantNews);

    // 3. Analyze client questions for content gaps
    const commonQuestions = await this.analyzeClientQuestions();
    triggers.push(...commonQuestions);

    let generated = 0;

    for (const trigger of triggers) {
      // Check if similar article exists
      const exists = await this.checkSimilarArticleExists(trigger.topic);

      if (!exists) {
        try {
          const article = await this.generateArticle({
            topic: trigger.topic,
            category: trigger.category,
            tone: trigger.urgency === 'high' ? 'urgent' : 'professional',
            targetLength: 'medium',
            includeData: true,
            sources: trigger.sources,
          });

          // Save draft via API
          await fetch(`${ZANTARA_API}/api/blog/articles`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${ZANTARA_API_KEY}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              ...article,
              status: 'review',
              metadata: {
                triggerSource: trigger.source,
                triggerDate: new Date(),
              },
            }),
          });

          // Notify editorial team
          await this.notifyEditorialTeam(article, trigger);

          trigger.processed = true;
          generated++;
        } catch (error) {
          console.error(`Failed to generate article for trigger: ${trigger.topic}`, error);
        }
      }
    }

    return {
      processed: triggers.length,
      generated,
      triggers,
    };
  }

  /**
   * Get personalized article recommendations for a client
   */
  static async getPersonalizedRecommendations(
    clientId: string,
    limit = 5
  ): Promise<ArticleListItem[]> {
    // Fetch client profile from Zantara
    const clientResponse = await fetch(`${ZANTARA_API}/api/crm/clients/${clientId}`, {
      headers: { 'Authorization': `Bearer ${ZANTARA_API_KEY}` },
    });

    if (!clientResponse.ok) {
      return [];
    }

    const client = await clientResponse.json();

    // Analyze interests
    const interests = await this.analyzeClientInterests(client);

    // Get matching articles
    const articlesResponse = await fetch(`${ZANTARA_API}/api/blog/articles/recommend`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ZANTARA_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        categories: interests.categories,
        tags: interests.tags,
        excludeRead: interests.readArticleIds,
        limit: limit * 2, // Fetch more for scoring
      }),
    });

    if (!articlesResponse.ok) {
      return [];
    }

    const { articles } = await articlesResponse.json();

    // Score and rank
    const scored = articles.map((article: ArticleListItem) => ({
      article,
      score: this.calculateRelevanceScore(article, interests),
    }));

    return scored
      .sort((a: { score: number }, b: { score: number }) => b.score - a.score)
      .slice(0, limit)
      .map((s: { article: ArticleListItem }) => s.article);
  }

  /**
   * Generate article translation
   */
  static async translateArticle(
    articleId: string,
    targetLocale: 'en' | 'id'
  ): Promise<Partial<Article>> {
    const response = await fetch(`${ZANTARA_API}/api/blog/ai-translate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${ZANTARA_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        articleId,
        targetLocale,
      }),
    });

    if (!response.ok) {
      throw new Error(`Translation failed: ${response.statusText}`);
    }

    return response.json();
  }

  // ============================================================================
  // Private Helper Methods
  // ============================================================================

  private static buildPrompt(request: AIGenerationRequest): string {
    const toneInstructions = {
      professional: 'Use a professional, authoritative tone with clear explanations.',
      casual: 'Use a friendly, conversational tone that is easy to understand.',
      urgent: 'Use an urgent tone emphasizing time-sensitive information and immediate action.',
    };

    const lengthGuides = {
      short: '800-1200 words',
      medium: '1500-2500 words',
      long: '3000-5000 words',
    };

    return `
You are Zantara AI, the expert content writer for Bali Zero Insights - "The Chronicle".

Write a comprehensive article about: ${request.topic}
Category: ${request.category}
Target length: ${lengthGuides[request.targetLength]}

${toneInstructions[request.tone]}

Requirements:
- Focus on Indonesia/Bali business context
- Include actionable insights and practical advice
- Cite official sources when possible (government websites, regulations)
- Use clear headings and well-structured content
- Include practical examples and real scenarios
${request.includeData ? '- Include relevant statistics and data points where applicable' : ''}
${request.sources?.length ? `- Reference these sources: ${request.sources.join(', ')}` : ''}

Target audience: Expats, digital nomads, and entrepreneurs in Bali/Indonesia

Output format (JSON):
{
  "title": "Compelling headline (max 70 chars)",
  "subtitle": "Supporting subheadline",
  "excerpt": "Engaging summary (max 200 chars)",
  "content": "Full MDX article with ## headings, **bold**, lists, etc.",
  "suggestedTags": ["tag1", "tag2", "tag3"],
  "confidence": 0.0-1.0 (your confidence in accuracy),
  "coverImagePrompt": "Description for generating cover image"
}

Important: Ensure all information is accurate and up-to-date. If uncertain about specific details (prices, deadlines), note that they should be verified.
    `.trim();
  }

  private static getTokenLimit(length: 'short' | 'medium' | 'long'): number {
    return { short: 2000, medium: 4000, long: 8000 }[length];
  }

  private static calculateReadingTime(content: string): number {
    const wordsPerMinute = 200;
    const words = content.split(/\s+/).length;
    return Math.max(1, Math.ceil(words / wordsPerMinute));
  }

  private static async generateCoverImage(
    topic: string,
    category: ArticleCategory
  ): Promise<string> {
    const categoryThemes: Record<ArticleCategory, string> = {
      immigration: 'passport, travel documents, airport, visa stamp',
      business: 'office building, business meeting, corporate, professional',
      'tax-legal': 'legal documents, scales of justice, contract, official',
      property: 'luxury villa, Bali architecture, real estate, tropical home',
      lifestyle: 'Bali sunset, rice terraces, beach, tropical paradise',
      tech: 'laptop, digital nomad workspace, modern technology, coworking',
    };

    try {
      const response = await fetch(`${ZANTARA_API}/api/v1/image/generate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${ZANTARA_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: `Professional editorial photography for article about ${topic}.
                   Theme: ${categoryThemes[category]}, Bali Indonesia.
                   Style: cinematic, moody lighting, premium magazine quality.
                   Aspect ratio: 16:9, high quality.`,
          style: 'editorial',
          aspectRatio: '16:9',
        }),
      });

      if (response.ok) {
        const { images } = await response.json();
        return images?.[0]?.url || this.getDefaultCoverImage(category);
      }
    } catch (error) {
      console.error('Image generation failed:', error);
    }

    return this.getDefaultCoverImage(category);
  }

  private static getDefaultCoverImage(category: ArticleCategory): string {
    const defaults: Record<ArticleCategory, string> = {
      immigration: '/static/blog/default-immigration.jpg',
      business: '/static/blog/default-business.jpg',
      'tax-legal': '/static/blog/default-tax-legal.jpg',
      property: '/static/blog/default-property.jpg',
      lifestyle: '/static/blog/default-lifestyle.jpg',
      tech: '/static/blog/default-tech.jpg',
    };
    return defaults[category];
  }

  private static generateSEO(
    title: string,
    excerpt: string
  ): { title: string; description: string } {
    return {
      title: title.length > 60 ? title.slice(0, 57) + '...' : title,
      description: excerpt.length > 160 ? excerpt.slice(0, 157) + '...' : excerpt,
    };
  }

  private static async findRelatedArticles(
    topic: string,
    category: ArticleCategory
  ): Promise<string[]> {
    try {
      const response = await fetch(`${ZANTARA_API}/api/blog/articles/similar`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${ZANTARA_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: topic, category, limit: 5 }),
      });

      if (response.ok) {
        const { articleIds } = await response.json();
        return articleIds || [];
      }
    } catch (error) {
      console.error('Failed to find related articles:', error);
    }

    return [];
  }

  private static async checkGovernmentSources(): Promise<AIContentTrigger[]> {
    // Monitor Indonesian government APIs/websites
    // - imigrasi.go.id
    // - oss.go.id
    // - pajak.go.id
    // - djkn.kemenkeu.go.id

    try {
      const response = await fetch(`${ZANTARA_API}/api/intel/monitor/government`, {
        headers: { 'Authorization': `Bearer ${ZANTARA_API_KEY}` },
      });

      if (response.ok) {
        const { updates } = await response.json();
        return updates.map((update: {
          title: string;
          category: ArticleCategory;
          urgency: 'low' | 'medium' | 'high';
          sourceUrl: string;
        }) => ({
          id: crypto.randomUUID(),
          source: 'government' as const,
          topic: update.title,
          category: update.category,
          urgency: update.urgency,
          sources: [update.sourceUrl],
          detectedAt: new Date(),
          processed: false,
        }));
      }
    } catch (error) {
      console.error('Failed to check government sources:', error);
    }

    return [];
  }

  private static async checkNewsSources(): Promise<AIContentTrigger[]> {
    try {
      const response = await fetch(`${ZANTARA_API}/api/intel/monitor/news`, {
        headers: { 'Authorization': `Bearer ${ZANTARA_API_KEY}` },
      });

      if (response.ok) {
        const { articles } = await response.json();
        return articles
          .filter((a: { relevanceScore: number }) => a.relevanceScore > 0.7)
          .map((article: {
            title: string;
            category: ArticleCategory;
            url: string;
          }) => ({
            id: crypto.randomUUID(),
            source: 'news' as const,
            topic: article.title,
            category: article.category,
            urgency: 'medium' as const,
            sources: [article.url],
            detectedAt: new Date(),
            processed: false,
          }));
      }
    } catch (error) {
      console.error('Failed to check news sources:', error);
    }

    return [];
  }

  private static async analyzeClientQuestions(): Promise<AIContentTrigger[]> {
    try {
      const response = await fetch(`${ZANTARA_API}/api/analytics/faq-gaps`, {
        headers: { 'Authorization': `Bearer ${ZANTARA_API_KEY}` },
      });

      if (response.ok) {
        const { gaps } = await response.json();
        return gaps.map((gap: {
          question: string;
          frequency: number;
          category: ArticleCategory;
        }) => ({
          id: crypto.randomUUID(),
          source: 'client_question' as const,
          topic: gap.question,
          category: gap.category,
          urgency: gap.frequency > 10 ? 'high' : 'medium',
          sources: [],
          detectedAt: new Date(),
          processed: false,
        }));
      }
    } catch (error) {
      console.error('Failed to analyze client questions:', error);
    }

    return [];
  }

  private static async checkSimilarArticleExists(topic: string): Promise<boolean> {
    try {
      const response = await fetch(`${ZANTARA_API}/api/blog/articles/check-duplicate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${ZANTARA_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ topic, similarityThreshold: 0.85 }),
      });

      if (response.ok) {
        const { exists } = await response.json();
        return exists;
      }
    } catch (error) {
      console.error('Failed to check for duplicates:', error);
    }

    return false;
  }

  private static async notifyEditorialTeam(
    article: Partial<Article>,
    trigger: AIContentTrigger
  ): Promise<void> {
    try {
      await fetch(`${ZANTARA_API}/api/notifications/editorial`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${ZANTARA_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: 'ai_article_generated',
          title: `New AI Article: ${article.title}`,
          message: `Zantara AI generated a new article based on ${trigger.source} trigger. Please review.`,
          articleData: {
            title: article.title,
            category: article.category,
            confidence: article.aiConfidenceScore,
          },
          triggerData: {
            source: trigger.source,
            topic: trigger.topic,
            urgency: trigger.urgency,
          },
        }),
      });
    } catch (error) {
      console.error('Failed to notify editorial team:', error);
    }
  }

  private static async analyzeClientInterests(client: {
    visaType?: string;
    businessType?: string;
    interests?: string[];
    conversations?: Array<{ topics: string[] }>;
    readArticles?: string[];
  }): Promise<{
    categories: ArticleCategory[];
    tags: string[];
    readArticleIds: string[];
  }> {
    const categories: Set<ArticleCategory> = new Set();
    const tags: Set<string> = new Set();

    // Analyze visa type
    if (client.visaType) {
      categories.add('immigration');
      tags.add(client.visaType.toLowerCase());
    }

    // Analyze business type
    if (client.businessType) {
      categories.add('business');
      tags.add(client.businessType.toLowerCase());
    }

    // Add explicit interests
    if (client.interests) {
      client.interests.forEach(interest => {
        const categoryMap: Record<string, ArticleCategory> = {
          visa: 'immigration',
          immigration: 'immigration',
          company: 'business',
          business: 'business',
          tax: 'tax-legal',
          legal: 'tax-legal',
          property: 'property',
          real_estate: 'property',
          lifestyle: 'lifestyle',
          tech: 'tech',
        };
        const category = categoryMap[interest.toLowerCase()];
        if (category) categories.add(category);
        tags.add(interest.toLowerCase());
      });
    }

    // Analyze conversation topics
    if (client.conversations) {
      client.conversations.forEach(conv => {
        conv.topics?.forEach(topic => tags.add(topic.toLowerCase()));
      });
    }

    return {
      categories: Array.from(categories),
      tags: Array.from(tags),
      readArticleIds: client.readArticles || [],
    };
  }

  private static calculateRelevanceScore(
    article: ArticleListItem,
    interests: {
      categories: ArticleCategory[];
      tags: string[];
      readArticleIds: string[];
    }
  ): number {
    let score = 0;

    // Category match (+30 points)
    if (interests.categories.includes(article.category)) {
      score += 30;
    }

    // Tag matches (+10 points each, max 40)
    // const articleTags = article.tags || [];
    // const matchingTags = articleTags.filter(tag =>
    //   interests.tags.some(t => t.toLowerCase() === tag.toLowerCase())
    // );
    // score += Math.min(matchingTags.length * 10, 40);

    // Trending bonus (+15 points)
    if (article.trending) {
      score += 15;
    }

    // Featured bonus (+10 points)
    if (article.featured) {
      score += 10;
    }

    // Recency bonus (up to +20 points)
    const daysSincePublished = Math.floor(
      (Date.now() - new Date(article.publishedAt).getTime()) / (1000 * 60 * 60 * 24)
    );
    score += Math.max(0, 20 - daysSincePublished);

    // Already read penalty (-100 points)
    if (interests.readArticleIds.includes(article.id)) {
      score -= 100;
    }

    return score;
  }
}

// ============================================================================
// Export utility functions
// ============================================================================

export async function generateArticle(request: AIGenerationRequest) {
  return ZantaraAIWriter.generateArticle(request);
}

export async function getRecommendations(clientId: string, limit?: number) {
  return ZantaraAIWriter.getPersonalizedRecommendations(clientId, limit);
}

export async function runContentMonitor() {
  return ZantaraAIWriter.monitorAndGenerate();
}

export async function translateArticle(articleId: string, targetLocale: 'en' | 'id') {
  return ZantaraAIWriter.translateArticle(articleId, targetLocale);
}
