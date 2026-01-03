/**
 * Newsletter Service with Zoho Email Integration
 * Handles newsletter subscriptions, sending, and Zoho CRM sync
 */

import type {
  Article,
  ArticleCategory,
  ArticleListItem,
  NewsletterSubscriber,
  NewsletterSubscribeRequest,
  CATEGORY_METADATA,
} from './types';

const ZANTARA_API = process.env.NEXT_PUBLIC_ZANTARA_API_URL || process.env.ZANTARA_API_URL;
const ZANTARA_API_KEY = process.env.ZANTARA_API_KEY;
const ZOHO_API_URL = process.env.ZOHO_MAIL_API_URL;
const ZOHO_ACCESS_TOKEN = process.env.ZOHO_ACCESS_TOKEN;

// ============================================================================
// Newsletter Service
// ============================================================================

export class NewsletterService {
  /**
   * Subscribe to newsletter
   */
  static async subscribe(request: NewsletterSubscribeRequest): Promise<{
    success: boolean;
    subscriberId?: string;
    message: string;
  }> {
    try {
      // 1. Create subscriber in database
      const response = await fetch(`${ZANTARA_API}/api/blog/newsletter/subscribe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const error = await response.json();
        return {
          success: false,
          message: error.message || 'Subscription failed',
        };
      }

      const { subscriber } = await response.json();

      // 2. Sync to Zoho CRM
      await this.syncToZoho(subscriber);

      // 3. Send confirmation email
      await this.sendConfirmationEmail(subscriber);

      return {
        success: true,
        subscriberId: subscriber.id,
        message: 'Please check your email to confirm your subscription.',
      };
    } catch (error) {
      console.error('Newsletter subscription failed:', error);
      return {
        success: false,
        message: 'An error occurred. Please try again.',
      };
    }
  }

  /**
   * Confirm subscription (after email click)
   */
  static async confirmSubscription(
    subscriberId: string,
    token: string
  ): Promise<boolean> {
    try {
      const response = await fetch(
        `${ZANTARA_API}/api/blog/newsletter/confirm`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ subscriberId, token }),
        }
      );

      return response.ok;
    } catch (error) {
      console.error('Confirmation failed:', error);
      return false;
    }
  }

  /**
   * Unsubscribe from newsletter
   */
  static async unsubscribe(subscriberId: string): Promise<boolean> {
    try {
      const response = await fetch(
        `${ZANTARA_API}/api/blog/newsletter/unsubscribe`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ subscriberId }),
        }
      );

      return response.ok;
    } catch (error) {
      console.error('Unsubscribe failed:', error);
      return false;
    }
  }

  /**
   * Update subscriber preferences
   */
  static async updatePreferences(
    subscriberId: string,
    preferences: Partial<Pick<NewsletterSubscriber, 'categories' | 'frequency' | 'language'>>
  ): Promise<boolean> {
    try {
      const response = await fetch(
        `${ZANTARA_API}/api/blog/newsletter/preferences`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ subscriberId, ...preferences }),
        }
      );

      return response.ok;
    } catch (error) {
      console.error('Preference update failed:', error);
      return false;
    }
  }

  /**
   * Send newsletter for new article
   */
  static async sendArticleNewsletter(articleId: string): Promise<{
    sent: number;
    failed: number;
  }> {
    // Fetch article
    const articleResponse = await fetch(
      `${ZANTARA_API}/api/blog/articles/${articleId}`,
      {
        headers: { Authorization: `Bearer ${ZANTARA_API_KEY}` },
      }
    );

    if (!articleResponse.ok) {
      throw new Error('Article not found');
    }

    const article: Article = await articleResponse.json();

    // Get subscribers interested in this category
    const subscribersResponse = await fetch(
      `${ZANTARA_API}/api/blog/newsletter/subscribers?category=${article.category}&confirmed=true`,
      {
        headers: { Authorization: `Bearer ${ZANTARA_API_KEY}` },
      }
    );

    if (!subscribersResponse.ok) {
      throw new Error('Failed to fetch subscribers');
    }

    const { subscribers }: { subscribers: NewsletterSubscriber[] } =
      await subscribersResponse.json();

    if (subscribers.length === 0) {
      return { sent: 0, failed: 0 };
    }

    // Generate email HTML
    const emailHtml = this.generateArticleEmail(article);

    // Send in batches via Zoho
    let sent = 0;
    let failed = 0;
    const batches = this.chunkArray(subscribers, 50);

    for (const batch of batches) {
      const results = await Promise.allSettled(
        batch.map((subscriber) =>
          this.sendViaZoho({
            to: subscriber.email,
            subject: `New Insight: ${article.title}`,
            html: this.personalizeEmail(emailHtml, subscriber),
          })
        )
      );

      results.forEach((result) => {
        if (result.status === 'fulfilled') sent++;
        else failed++;
      });

      // Rate limit delay
      await this.delay(1000);
    }

    // Log send
    await fetch(`${ZANTARA_API}/api/blog/newsletter/log`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${ZANTARA_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        articleId,
        recipientCount: subscribers.length,
        sentCount: sent,
        failedCount: failed,
      }),
    });

    return { sent, failed };
  }

  /**
   * Send weekly digest
   */
  static async sendWeeklyDigest(): Promise<{
    sent: number;
    articlesIncluded: number;
  }> {
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

    // Fetch week's articles
    const articlesResponse = await fetch(
      `${ZANTARA_API}/api/blog/articles?status=published&publishedAfter=${weekAgo.toISOString()}&sort=viewCount&limit=10`,
      {
        headers: { Authorization: `Bearer ${ZANTARA_API_KEY}` },
      }
    );

    if (!articlesResponse.ok) {
      throw new Error('Failed to fetch articles');
    }

    const { articles }: { articles: ArticleListItem[] } =
      await articlesResponse.json();

    if (articles.length === 0) {
      return { sent: 0, articlesIncluded: 0 };
    }

    // Get weekly digest subscribers
    const subscribersResponse = await fetch(
      `${ZANTARA_API}/api/blog/newsletter/subscribers?frequency=weekly&confirmed=true`,
      {
        headers: { Authorization: `Bearer ${ZANTARA_API_KEY}` },
      }
    );

    if (!subscribersResponse.ok) {
      throw new Error('Failed to fetch subscribers');
    }

    const { subscribers }: { subscribers: NewsletterSubscriber[] } =
      await subscribersResponse.json();

    let sent = 0;

    for (const subscriber of subscribers) {
      // Filter articles by subscriber interests
      const relevantArticles = articles.filter((a) =>
        subscriber.categories.includes(a.category)
      );

      if (relevantArticles.length > 0) {
        const emailHtml = this.generateDigestEmail(
          relevantArticles,
          subscriber
        );

        try {
          await this.sendViaZoho({
            to: subscriber.email,
            subject: `Your Weekly Bali Zero Digest`,
            html: emailHtml,
          });
          sent++;
        } catch (error) {
          console.error(
            `Failed to send digest to ${subscriber.email}:`,
            error
          );
        }
      }
    }

    return { sent, articlesIncluded: articles.length };
  }

  /**
   * Notify relevant Zantara clients about new article
   */
  static async notifyRelevantClients(articleId: string): Promise<number> {
    // Fetch article
    const articleResponse = await fetch(
      `${ZANTARA_API}/api/blog/articles/${articleId}`,
      {
        headers: { Authorization: `Bearer ${ZANTARA_API_KEY}` },
      }
    );

    if (!articleResponse.ok) {
      return 0;
    }

    const article: Article = await articleResponse.json();

    if (!article.autoNotifyClients) {
      return 0;
    }

    // Find matching clients
    const clientsResponse = await fetch(
      `${ZANTARA_API}/api/crm/clients/match`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${ZANTARA_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          category: article.category,
          tags: article.tags,
        }),
      }
    );

    if (!clientsResponse.ok) {
      return 0;
    }

    const { clients } = await clientsResponse.json();

    // Send WhatsApp notifications via Zantara
    let notified = 0;

    for (const client of clients) {
      if (!client.whatsapp) continue;

      try {
        await fetch(`${ZANTARA_API}/api/whatsapp/send`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${ZANTARA_API_KEY}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            to: client.whatsapp,
            template: 'new_article_notification',
            params: {
              clientName: client.name || 'there',
              articleTitle: article.title,
              articleUrl: `https://balizero.com/insights/${article.category}/${article.slug}`,
              category: article.category,
            },
          }),
        });
        notified++;
      } catch (error) {
        console.error(`Failed to notify client ${client.id}:`, error);
      }
    }

    return notified;
  }

  // ============================================================================
  // Private Helper Methods
  // ============================================================================

  private static async syncToZoho(subscriber: NewsletterSubscriber): Promise<void> {
    if (!ZOHO_API_URL || !ZOHO_ACCESS_TOKEN) {
      console.warn('Zoho integration not configured');
      return;
    }

    try {
      // Create/update contact in Zoho CRM
      await fetch(`${ZOHO_API_URL}/crm/v2/Contacts`, {
        method: 'POST',
        headers: {
          Authorization: `Zoho-oauthtoken ${ZOHO_ACCESS_TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          data: [
            {
              Email: subscriber.email,
              First_Name: subscriber.name?.split(' ')[0] || '',
              Last_Name: subscriber.name?.split(' ').slice(1).join(' ') || '',
              Newsletter_Subscriber: true,
              Newsletter_Categories: subscriber.categories.join(';'),
              Newsletter_Frequency: subscriber.frequency,
              Preferred_Language: subscriber.language,
              Lead_Source: 'Blog Newsletter',
            },
          ],
          trigger: ['workflow'],
        }),
      });
    } catch (error) {
      console.error('Zoho sync failed:', error);
    }
  }

  private static async sendConfirmationEmail(
    subscriber: NewsletterSubscriber
  ): Promise<void> {
    const confirmUrl = `https://balizero.com/newsletter/confirm?id=${subscriber.id}`;

    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: 'Inter', sans-serif; background: #0a0a0a; color: #ffffff; margin: 0; padding: 0; }
          .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
          .header { text-align: center; margin-bottom: 40px; }
          .logo { height: 50px; }
          h1 { font-family: 'Playfair Display', serif; font-size: 28px; margin: 24px 0; }
          p { color: #a0a0a0; line-height: 1.6; }
          .cta {
            display: inline-block;
            background: linear-gradient(135deg, #8b5cf6, #ec4899);
            color: white !important;
            padding: 14px 32px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            margin: 24px 0;
          }
          .footer { text-align: center; margin-top: 40px; padding-top: 24px; border-top: 1px solid #222; color: #666; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <img src="https://balizero.com/logo.png" alt="Bali Zero" class="logo" />
          </div>

          <h1>Welcome to Bali Zero Insights!</h1>

          <p>Thanks for subscribing to our newsletter. You're one click away from receiving the best insights about business, immigration, and living in Bali.</p>

          <p>Please confirm your subscription by clicking the button below:</p>

          <a href="${confirmUrl}" class="cta">Confirm Subscription</a>

          <p style="font-size: 14px; color: #666;">If you didn't subscribe to this newsletter, you can safely ignore this email.</p>

          <div class="footer">
            <p>&copy; 2026 Bali Zero Insights. All rights reserved.</p>
          </div>
        </div>
      </body>
      </html>
    `;

    await this.sendViaZoho({
      to: subscriber.email,
      subject: 'Confirm your Bali Zero Insights subscription',
      html,
    });
  }

  private static async sendViaZoho(options: {
    to: string;
    subject: string;
    html: string;
  }): Promise<void> {
    // Use Zantara's email service which wraps Zoho
    await fetch(`${ZANTARA_API}/api/email/send`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${ZANTARA_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        fromAddress: 'insights@balizero.com',
        fromName: 'Bali Zero Insights',
        toAddress: options.to,
        subject: options.subject,
        content: options.html,
        contentType: 'html',
      }),
    });
  }

  private static generateArticleEmail(article: Article): string {
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: #0a0a0a; color: #ffffff; margin: 0; padding: 0; }
          .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
          .header { text-align: center; margin-bottom: 32px; }
          .logo { height: 40px; }
          .cover { width: 100%; border-radius: 12px; margin-bottom: 24px; }
          .category {
            display: inline-block;
            background: rgba(139, 92, 246, 0.2);
            color: #a78bfa;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
          }
          h1 {
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 26px;
            line-height: 1.3;
            margin: 0 0 16px 0;
            color: #ffffff;
          }
          .excerpt { color: #a0a0a0; line-height: 1.6; margin-bottom: 24px; font-size: 15px; }
          .meta { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; color: #666; font-size: 13px; }
          .author-avatar { width: 36px; height: 36px; border-radius: 50%; }
          .cta {
            display: inline-block;
            background: linear-gradient(135deg, #8b5cf6, #ec4899);
            color: white !important;
            padding: 14px 28px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
          }
          .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 24px;
            border-top: 1px solid #222;
            color: #666;
            font-size: 12px;
          }
          .footer a { color: #888; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <img src="https://balizero.com/logo.png" alt="Bali Zero" class="logo" />
          </div>

          <img src="${article.coverImage}" alt="${article.coverImageAlt}" class="cover" />

          <span class="category">${article.category.replace('-', ' & ')}</span>

          <h1>${article.title}</h1>

          <p class="excerpt">${article.excerpt}</p>

          <div class="meta">
            <img src="${article.author.avatar}" alt="${article.author.name}" class="author-avatar" />
            <span>By ${article.author.name}</span>
            <span>&bull;</span>
            <span>${article.readingTime} min read</span>
          </div>

          <a href="https://balizero.com/insights/${article.category}/${article.slug}" class="cta">
            Read Full Article &rarr;
          </a>

          <div class="footer">
            <p>&copy; 2026 Bali Zero Insights. All rights reserved.</p>
            <p>
              <a href="{{unsubscribe_url}}">Unsubscribe</a> &bull;
              <a href="https://balizero.com/newsletter/preferences?id={{subscriber_id}}">Manage preferences</a>
            </p>
          </div>
        </div>
      </body>
      </html>
    `;
  }

  private static generateDigestEmail(
    articles: ArticleListItem[],
    subscriber: NewsletterSubscriber
  ): string {
    const articleCards = articles
      .map(
        (article) => `
        <div style="margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid #222;">
          <img src="${article.coverImage}" alt="" style="width: 100%; border-radius: 8px; margin-bottom: 12px;" />
          <span style="display: inline-block; background: rgba(139, 92, 246, 0.2); color: #a78bfa; padding: 2px 8px; border-radius: 12px; font-size: 10px; text-transform: uppercase; letter-spacing: 1px;">${article.category}</span>
          <h3 style="font-family: 'Playfair Display', Georgia, serif; font-size: 18px; margin: 8px 0; color: #ffffff;">${article.title}</h3>
          <p style="color: #888; font-size: 13px; line-height: 1.5; margin: 0 0 12px 0;">${article.excerpt}</p>
          <a href="https://balizero.com/insights/${article.category}/${article.slug}" style="color: #a78bfa; text-decoration: none; font-size: 13px; font-weight: 500;">Read more &rarr;</a>
        </div>
      `
      )
      .join('');

    return `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: 'Inter', sans-serif; background: #0a0a0a; color: #ffffff; margin: 0; padding: 0; }
          .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
          .header { text-align: center; margin-bottom: 32px; }
          .logo { height: 40px; }
          h1 { font-family: 'Playfair Display', serif; font-size: 24px; text-align: center; margin-bottom: 8px; }
          .subtitle { text-align: center; color: #888; margin-bottom: 32px; }
          .footer { text-align: center; margin-top: 32px; padding-top: 24px; border-top: 1px solid #222; color: #666; font-size: 12px; }
          .footer a { color: #888; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <img src="https://balizero.com/logo.png" alt="Bali Zero" class="logo" />
          </div>

          <h1>Your Weekly Digest</h1>
          <p class="subtitle">The top insights from Bali Zero this week</p>

          ${articleCards}

          <div class="footer">
            <p>&copy; 2026 Bali Zero Insights. All rights reserved.</p>
            <p>
              <a href="https://balizero.com/newsletter/unsubscribe?id=${subscriber.id}">Unsubscribe</a> &bull;
              <a href="https://balizero.com/newsletter/preferences?id=${subscriber.id}">Manage preferences</a>
            </p>
          </div>
        </div>
      </body>
      </html>
    `;
  }

  private static personalizeEmail(
    html: string,
    subscriber: NewsletterSubscriber
  ): string {
    return html
      .replace(/\{\{subscriber_name\}\}/g, subscriber.name || 'Reader')
      .replace(/\{\{subscriber_id\}\}/g, subscriber.id)
      .replace(
        /\{\{unsubscribe_url\}\}/g,
        `https://balizero.com/newsletter/unsubscribe?id=${subscriber.id}`
      );
  }

  private static chunkArray<T>(array: T[], size: number): T[][] {
    const chunks: T[][] = [];
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size));
    }
    return chunks;
  }

  private static delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// ============================================================================
// Export utility functions
// ============================================================================

export async function subscribeToNewsletter(request: NewsletterSubscribeRequest) {
  return NewsletterService.subscribe(request);
}

export async function unsubscribeFromNewsletter(subscriberId: string) {
  return NewsletterService.unsubscribe(subscriberId);
}

export async function sendArticleNewsletter(articleId: string) {
  return NewsletterService.sendArticleNewsletter(articleId);
}

export async function sendWeeklyDigest() {
  return NewsletterService.sendWeeklyDigest();
}

export async function notifyClients(articleId: string) {
  return NewsletterService.notifyRelevantClients(articleId);
}
