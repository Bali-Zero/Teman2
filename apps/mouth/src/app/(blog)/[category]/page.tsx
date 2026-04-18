import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { BreadcrumbJsonLd } from '@/components/seo';
import type { ArticleCategory } from '@/lib/blog/types';
import CategoryClient from './CategoryClient';

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || 'https://balizero.com';

const CATEGORY_META: Record<
  ArticleCategory,
  { title: string; description: string; label: string }
> = {
  visas: {
    label: 'Visas & Immigration',
    title: 'Indonesia Visas & Immigration — News & Guides',
    description:
      'Visas, permits, KITAS, KITAP, Golden Visa, and everything you need to know about relocating to Indonesia. Expert guides from Bali Zero.',
  },
  business: {
    label: 'Business',
    title: 'Doing Business in Indonesia — Company Setup & KBLI',
    description:
      'Company setup, PT PMA, licensing, KBLI codes, and practical guides to doing business in Indonesia.',
  },
  taxes: {
    label: 'Taxes & Compliance',
    title: 'Taxes & Compliance in Indonesia — Expert Guides',
    description:
      'Tax obligations, legal compliance, PPh, PPN, NPWP, and regulatory updates for individuals and companies in Indonesia.',
  },
  property: {
    label: 'Property',
    title: 'Bali & Indonesia Property — Leasehold, Freehold, Investment',
    description:
      'Real estate, property ownership, leasehold and freehold structures, and investment opportunities across Bali and Indonesia.',
  },
  living: {
    label: 'Living in Indonesia',
    title: 'Living in Bali — Culture, Community & Daily Life',
    description:
      'Living in Bali, culture, community, driving, healthcare, and practical advice for expats and digital nomads.',
  },
  trends: {
    label: 'Trends & Insights',
    title: 'Indonesia Market Trends & Insights',
    description:
      'Digital economy, tech industry, emerging regulations, and market insights for Indonesia and Southeast Asia.',
  },
};

export async function generateStaticParams() {
  return (Object.keys(CATEGORY_META) as ArticleCategory[]).map((category) => ({
    category,
  }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}): Promise<Metadata> {
  const { category } = await params;
  const meta = CATEGORY_META[category as ArticleCategory];
  if (!meta) {
    return { title: 'Category not found', robots: { index: false, follow: false } };
  }
  const url = `${baseUrl}/${category}`;
  return {
    title: meta.title,
    description: meta.description,
    alternates: { canonical: url },
    openGraph: {
      type: 'website',
      locale: 'en_US',
      url,
      title: meta.title,
      description: meta.description,
      siteName: 'Bali Zero',
      images: [
        {
          url: `${baseUrl}/static/og-image.jpg`,
          width: 1200,
          height: 630,
          alt: meta.label,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: meta.title,
      description: meta.description,
      creator: '@balizero',
    },
  };
}

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ category: string }>;
}) {
  const { category } = await params;
  const meta = CATEGORY_META[category as ArticleCategory];
  if (!meta) {
    notFound();
  }
  return (
    <>
      <BreadcrumbJsonLd
        items={[
          { name: 'Home', url: '/' },
          { name: 'News', url: '/news' },
          { name: meta.label, url: `/${category}` },
        ]}
      />
      <CategoryClient category={category as ArticleCategory} />
    </>
  );
}
