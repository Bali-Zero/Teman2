'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { format } from 'date-fns';
import { MDXRemoteSerializeResult } from 'next-mdx-remote';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { MDXContent } from '@/components/blog/MDXContent';
import {
  Clock,
  Eye,
  Calendar,
  Share2,
  Bookmark,
  Twitter,
  Linkedin,
  Link2,
  ChevronLeft,
  Sparkles,
  User,
} from 'lucide-react';
import {
  CategoryBadge,
  TableOfContents,
  FloatingToc,
  ReadingProgress,
  ArticleCard,
  NewsletterSidebar,
} from '@/components/blog';
import { cn } from '@/lib/utils';
import type { Article, ArticleListItem } from '@/lib/blog/types';

// Extended article type with serialized MDX
interface ArticleWithMDX extends Article {
  mdxSource?: MDXRemoteSerializeResult;
}

// Strip JSX components from content for markdown fallback
function stripJsxComponents(content: string): string {
  // Remove self-closing JSX tags like <Component />
  let stripped = content.replace(/<[A-Z][a-zA-Z]*\s*[^>]*\/>/g, '');
  // Remove opening and closing JSX tags with content like <Component>...</Component>
  stripped = stripped.replace(/<[A-Z][a-zA-Z]*[^>]*>[\s\S]*?<\/[A-Z][a-zA-Z]*>/g, '');
  // Remove multi-line JSX tags (opening tag on one line, attributes span multiple lines)
  stripped = stripped.replace(/<[A-Z][a-zA-Z]*\s*\n[\s\S]*?\/>/gm, '');
  stripped = stripped.replace(/<[A-Z][a-zA-Z]*\s*\n[\s\S]*?>[\s\S]*?<\/[A-Z][a-zA-Z]*>/gm, '');
  // Clean up extra newlines
  stripped = stripped.replace(/\n{3,}/g, '\n\n');
  return stripped.trim();
}

export default function ArticlePage() {
  const params = useParams();
  const slug = params.slug as string;
  const category = params.category as string;

  const [article, setArticle] = React.useState<ArticleWithMDX | null>(null);
  const [relatedArticles, setRelatedArticles] = React.useState<ArticleListItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [copied, setCopied] = React.useState(false);

  // Fetch article
  React.useEffect(() => {
    async function fetchArticle() {
      setLoading(true);
      try {
        const response = await fetch(`/api/blog/articles/${category}/${slug}`);
        if (response.ok) {
          const data = await response.json();
          // API returns article directly, not wrapped
          setArticle(data);
          setRelatedArticles(data.relatedArticles || []);
        } else {
          // Use mock for demo
          setArticle(MOCK_ARTICLE);
        }
      } catch (error) {
        console.error('Failed to fetch article:', error);
        // Use mock for demo
        setArticle(MOCK_ARTICLE);
      } finally {
        setLoading(false);
      }
    }

    fetchArticle();
  }, [slug, category]);

  // Copy link to clipboard
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  // Share functions
  const shareOnTwitter = () => {
    const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(article?.title || '')}&url=${encodeURIComponent(window.location.href)}`;
    window.open(url, '_blank');
  };

  const shareOnLinkedIn = () => {
    const url = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(window.location.href)}`;
    window.open(url, '_blank');
  };

  if (loading) {
    return (
      <div className="min-h-screen">
        <div className="max-w-4xl mx-auto px-4 py-16 animate-pulse">
          <div className="h-8 w-32 bg-white/5 rounded mb-4" />
          <div className="h-12 w-3/4 bg-white/5 rounded mb-8" />
          <div className="aspect-[21/9] bg-white/5 rounded-2xl mb-8" />
          <div className="space-y-4">
            <div className="h-4 bg-white/5 rounded" />
            <div className="h-4 bg-white/5 rounded w-5/6" />
            <div className="h-4 bg-white/5 rounded w-4/6" />
          </div>
        </div>
      </div>
    );
  }

  if (!article) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">Article not found</h1>
          <Link href="/insights" className="text-[#2251ff] hover:text-[#4d73ff]">
            Back to Insights
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Reading progress */}
      <ReadingProgress />

      {/* Floating TOC for mobile */}
      <FloatingToc content={article.content} />

      {/* Hero */}
      <section className="relative pt-8 pb-12 md:pt-12 md:pb-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Back link */}
          <Link
            href="/insights"
            className="inline-flex items-center gap-2 text-sm text-white/50 hover:text-white transition-colors mb-8"
          >
            <ChevronLeft className="w-4 h-4" />
            Back to Insights
          </Link>

          {/* Category & badges */}
          <div className="flex flex-wrap items-center gap-3 mb-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <CategoryBadge category={article.category} />
            {article.aiGenerated && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#2251ff]/20 text-[#2251ff]">
                <Sparkles className="w-3 h-3" />
                AI Generated
              </span>
            )}
            {article.reviewedBy && (
              <span className="text-xs text-white/50">
                Verified by {article.reviewedBy}
              </span>
            )}
          </div>

          {/* Title */}
          <h1 className="font-serif text-3xl md:text-5xl font-bold text-white mb-4 leading-tight animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
            {article.title}
          </h1>

          {/* Subtitle */}
          {article.subtitle && (
            <p className="text-lg md:text-xl text-white/60 mb-6 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-150">
              {article.subtitle}
            </p>
          )}

          {/* Meta */}
          <div className="flex flex-wrap items-center gap-6 text-sm text-white/50 mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
            {/* Author */}
            <div className="flex items-center gap-3">
              {article.author.avatar ? (
                <Image
                  src={article.author.avatar}
                  alt={article.author.name}
                  width={40}
                  height={40}
                  className="rounded-full"
                />
              ) : (
                <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center">
                  <User className="w-5 h-5" />
                </div>
              )}
              <div>
                <p className="text-white font-medium">{article.author.name}</p>
                <p className="text-xs">{article.author.role}</p>
              </div>
            </div>

            {/* Stats */}
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                {format(new Date(article.publishedAt || article.createdAt), 'MMM d, yyyy')}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {article.readingTime} min read
              </span>
              <span className="flex items-center gap-1">
                <Eye className="w-4 h-4" />
                {article.viewCount.toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Cover image */}
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-300">
          <div className="relative aspect-[21/9] rounded-2xl overflow-hidden">
            <Image
              src={article.coverImage}
              alt={article.coverImageAlt}
              fill
              className="object-cover"
              priority
              sizes="(max-width: 1280px) 100vw, 1200px"
            />
          </div>
        </div>
      </section>

      {/* Content */}
      <section className="py-8 md:py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
            {/* Sidebar - TOC */}
            <aside className="hidden lg:block lg:col-span-3">
              <div className="sticky top-24 space-y-8">
                <TableOfContents content={article.content} />

                {/* Share buttons */}
                <div className="space-y-3">
                  <p className="text-xs font-medium uppercase tracking-wider text-white/60">
                    Share
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={shareOnTwitter}
                      className="p-2 rounded-lg bg-white/5 text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                    >
                      <Twitter className="w-4 h-4" />
                    </button>
                    <button
                      onClick={shareOnLinkedIn}
                      className="p-2 rounded-lg bg-white/5 text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                    >
                      <Linkedin className="w-4 h-4" />
                    </button>
                    <button
                      onClick={copyLink}
                      className={cn(
                        'p-2 rounded-lg transition-colors',
                        copied
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-white/5 text-white/60 hover:text-white hover:bg-white/10'
                      )}
                    >
                      <Link2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </aside>

            {/* Main content */}
            <article className="lg:col-span-6">
              <div className="prose prose-invert prose-lg max-w-none">
                {article.mdxSource ? (
                  <MDXContent source={article.mdxSource} />
                ) : (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({children}) => <h1 className="font-serif text-3xl md:text-4xl font-bold text-white mt-12 mb-6 first:mt-0">{children}</h1>,
                      h2: ({children}) => <h2 className="font-serif text-2xl md:text-3xl font-bold text-white mt-10 mb-4 scroll-mt-24">{children}</h2>,
                      h3: ({children}) => <h3 className="font-serif text-xl md:text-2xl font-semibold text-white mt-8 mb-3 scroll-mt-24">{children}</h3>,
                      p: ({children}) => <p className="text-white/80 leading-relaxed mb-4">{children}</p>,
                      ul: ({children}) => <ul className="list-disc list-outside ml-6 mb-4 space-y-2 text-white/80">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal list-outside ml-6 mb-4 space-y-2 text-white/80">{children}</ol>,
                      li: ({children}) => <li className="leading-relaxed pl-2">{children}</li>,
                      a: ({href, children}) => <a href={href} className="text-[#2251ff] hover:text-[#4d73ff] underline underline-offset-2 transition-colors">{children}</a>,
                      blockquote: ({children}) => <blockquote className="border-l-4 border-[#2251ff] pl-6 py-2 my-6 italic text-white/70 bg-white/5 rounded-r-lg">{children}</blockquote>,
                      code: ({children, className}) => className ? <code className="font-mono text-sm">{children}</code> : <code className="px-1.5 py-0.5 bg-white/10 rounded text-[#ff6b6b] font-mono text-sm">{children}</code>,
                      pre: ({children}) => <pre className="bg-[#0a1929] border border-white/10 rounded-xl p-4 overflow-x-auto my-6 text-sm">{children}</pre>,
                      table: ({children}) => <div className="overflow-x-auto my-6 rounded-xl border border-white/10"><table className="w-full text-left">{children}</table></div>,
                      thead: ({children}) => <thead className="bg-white/5 border-b border-white/10">{children}</thead>,
                      th: ({children}) => <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-white/60">{children}</th>,
                      td: ({children}) => <td className="px-4 py-3 text-white/80">{children}</td>,
                      strong: ({children}) => <strong className="font-semibold text-white">{children}</strong>,
                      hr: () => <hr className="my-8 border-white/10" />,
                    }}
                  >
                    {stripJsxComponents(article.content)}
                  </ReactMarkdown>
                )}
              </div>

              {/* Tags */}
              {article.tags.length > 0 && (
                <div className="mt-12 pt-8 border-t border-white/10">
                  <p className="text-xs font-medium uppercase tracking-wider text-white/60 mb-3">
                    Topics
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {article.tags.map((tag) => (
                      <Link
                        key={tag}
                        href={`/insights?tag=${tag}`}
                        className="px-3 py-1 rounded-full bg-white/5 text-white/70 text-sm hover:bg-white/10 hover:text-white transition-colors"
                      >
                        {tag}
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* Author card */}
              <div className="mt-12 p-6 rounded-2xl bg-white/5 border border-white/10">
                <div className="flex items-start gap-4">
                  {article.author.avatar ? (
                    <Image
                      src={article.author.avatar}
                      alt={article.author.name}
                      width={64}
                      height={64}
                      className="rounded-full"
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center">
                      <User className="w-8 h-8" />
                    </div>
                  )}
                  <div>
                    <p className="font-medium text-white">{article.author.name}</p>
                    <p className="text-sm text-white/60 mb-2">{article.author.role}</p>
                    {article.author.bio && (
                      <p className="text-sm text-white/50">{article.author.bio}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Mobile share buttons */}
              <div className="lg:hidden mt-8 flex items-center justify-center gap-4">
                <button
                  onClick={shareOnTwitter}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <Twitter className="w-4 h-4" />
                  Share
                </button>
                <button
                  onClick={copyLink}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-lg transition-colors',
                    copied
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-white/5 text-white/70 hover:text-white hover:bg-white/10'
                  )}
                >
                  <Link2 className="w-4 h-4" />
                  {copied ? 'Copied!' : 'Copy link'}
                </button>
              </div>
            </article>

            {/* Right sidebar */}
            <aside className="lg:col-span-3">
              <div className="sticky top-24 space-y-8">
                {/* Newsletter */}
                <NewsletterSidebar defaultCategories={[article.category]} />
              </div>
            </aside>
          </div>
        </div>
      </section>

      {/* Related articles */}
      {relatedArticles.length > 0 && (
        <section className="py-12 md:py-16 bg-[#031219] border-t border-white/10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="font-serif text-2xl md:text-3xl font-bold text-white mb-8">
              Related Articles
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
              {relatedArticles.slice(0, 3).map((related, index) => (
                <ArticleCard
                  key={related.id}
                  article={related}
                  index={index}
                />
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

// Mock article for demo
const MOCK_ARTICLE: Article = {
  id: '1',
  slug: 'golden-visa-revolution',
  title: "The Golden Visa Revolution: Indonesia's $350K Bet on Global Talent",
  subtitle: 'A comprehensive guide to Indonesia\'s new premium residency program',
  excerpt: 'Indonesia launches its Golden Visa program, offering 5-10 year stays for investors and high-net-worth individuals.',
  content: `
## What is Indonesia's Golden Visa?

Indonesia's Golden Visa is a premium residency program launched in late 2024, designed to attract foreign investors, entrepreneurs, and high-net-worth individuals. This program offers extended stay permits of 5 to 10 years, significantly longer than traditional visa options.

## Who is Eligible?

The Golden Visa targets several categories of applicants:

### Investors
- Minimum investment of $350,000 USD in Indonesian companies or government bonds
- Must maintain the investment throughout the visa validity period

### Entrepreneurs
- Founders of companies with significant valuations
- Tech startup founders with proven track records

### High-Net-Worth Individuals
- Proof of substantial assets (typically $2M+ net worth)
- Stable income from overseas sources

## Benefits of the Golden Visa

1. **Extended Stay** - 5 to 10 year validity
2. **Multiple Entry** - No restrictions on travel
3. **Work Authorization** - Ability to work without additional permits
4. **Family Inclusion** - Spouse and children can be included
5. **Path to Permanent Residency** - Potential conversion to KITAP

## Application Process

The application process involves several steps:

1. Submit initial application to BKPM
2. Provide proof of investment/qualification
3. Complete background checks
4. Pay applicable fees
5. Receive Golden Visa approval

## Investment Options

### Option A: Direct Investment
Invest directly in Indonesian companies through:
- Stock purchases in publicly traded companies
- Direct investment in private enterprises
- Joint ventures with local partners

### Option B: Government Bonds
Purchase Indonesian government bonds with:
- Minimum holding period requirements
- Competitive interest rates
- Safe, government-backed returns

## Comparison with Other Countries

| Country | Minimum Investment | Validity |
|---------|-------------------|----------|
| Indonesia | $350,000 | 5-10 years |
| Portugal | $500,000 | 5 years |
| Thailand | $500,000 | 5 years |
| UAE | $544,000 | 10 years |

## Conclusion

Indonesia's Golden Visa represents a significant opportunity for those looking to establish a long-term presence in Southeast Asia. With competitive investment thresholds and generous validity periods, it's worth serious consideration for qualified applicants.

For personalized guidance on your Golden Visa application, contact our team at Bali Zero.
  `,
  coverImage: '/images/blog/golden-visa.jpg',
  coverImageAlt: 'Indonesia Golden Visa program illustration',
  category: 'immigration',
  tags: ['golden-visa', 'investment', 'residency', 'indonesia'],
  author: {
    id: 'zantara-ai',
    name: 'Zantara AI',
    avatar: '/images/zantara-avatar.png',
    role: 'AI Research Assistant',
    bio: 'Zantara AI provides accurate, up-to-date information about business and immigration in Indonesia.',
    isAI: true,
  },
  createdAt: new Date('2024-12-20'),
  updatedAt: new Date('2024-12-20'),
  publishedAt: new Date('2024-12-20'),
  status: 'published',
  featured: true,
  trending: true,
  readingTime: 12,
  viewCount: 15420,
  shareCount: 432,
  aiGenerated: true,
  aiConfidenceScore: 0.92,
  relatedArticleIds: ['2', '3', '5'],
  locale: 'en',
  reviewedBy: 'Legal Team',
};
