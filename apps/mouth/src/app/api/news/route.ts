import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

// News item interface
interface NewsItem {
  id: string;
  title: string;
  summary: string;
  content: string;
  source: string;
  sourceUrl: string;
  category: 'immigration' | 'business' | 'tax' | 'property' | 'lifestyle' | 'tech';
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'approved' | 'rejected';
  publishedAt: string;
  scrapedAt: string;
  imageUrl?: string;
}

// Path to news data file
const NEWS_FILE = path.join(process.cwd(), 'src/data/news.json');

// Ensure data directory exists
async function ensureDataDir() {
  const dir = path.dirname(NEWS_FILE);
  try {
    await fs.access(dir);
  } catch {
    await fs.mkdir(dir, { recursive: true });
  }
}

// Load news from file
async function loadNews(): Promise<NewsItem[]> {
  await ensureDataDir();
  try {
    const data = await fs.readFile(NEWS_FILE, 'utf-8');
    return JSON.parse(data);
  } catch {
    // Return sample data if file doesn't exist
    return getSampleNews();
  }
}

// Save news to file
async function saveNews(news: NewsItem[]) {
  await ensureDataDir();
  await fs.writeFile(NEWS_FILE, JSON.stringify(news, null, 2));
}

// Sample news for initial setup
function getSampleNews(): NewsItem[] {
  return [
    {
      id: 'news_1',
      title: 'E33G Digital Nomad Visa Processing Time Reduced to 3 Days',
      summary: 'Indonesian Immigration announces faster processing for remote worker visas, making Bali even more attractive for digital nomads.',
      content: 'The Directorate General of Immigration has announced that E33G Remote Worker KITAS applications will now be processed within 3 working days, down from the previous 5-7 days. This change is part of Indonesia\'s push to attract more digital nomads and remote workers to the country.',
      source: 'Imigrasi Indonesia',
      sourceUrl: 'https://imigrasi.go.id',
      category: 'immigration',
      priority: 'high',
      status: 'pending',
      publishedAt: new Date().toISOString(),
      scrapedAt: new Date().toISOString(),
    },
    {
      id: 'news_2',
      title: 'New Tax Incentives for Foreign Investors in Indonesia',
      summary: 'Government introduces tax holidays and reduced rates for qualifying foreign investments in priority sectors.',
      content: 'The Indonesian government has announced new tax incentives for foreign investors, including tax holidays of up to 20 years for investments in priority sectors such as technology, renewable energy, and manufacturing. The minimum investment threshold has been reduced to IDR 100 billion.',
      source: 'Kemenkeu',
      sourceUrl: 'https://kemenkeu.go.id',
      category: 'tax',
      priority: 'high',
      status: 'pending',
      publishedAt: new Date().toISOString(),
      scrapedAt: new Date().toISOString(),
    },
    {
      id: 'news_3',
      title: 'Bali Property Market Shows Strong Growth in Q4 2024',
      summary: 'Villa and land prices in popular areas continue to rise as demand from foreign buyers increases.',
      content: 'The Bali property market has shown strong growth in Q4 2024, with villa prices in Canggu and Seminyak increasing by 15-20% year-over-year. Demand from foreign buyers, particularly from Australia and Europe, continues to drive the market.',
      source: 'Property Insider',
      sourceUrl: 'https://propertyinsider.id',
      category: 'property',
      priority: 'medium',
      status: 'pending',
      publishedAt: new Date().toISOString(),
      scrapedAt: new Date().toISOString(),
    },
    {
      id: 'news_4',
      title: 'PT PMA Minimum Capital Requirement Update',
      summary: 'OSS system now enforces stricter capital verification for foreign-owned companies.',
      content: 'The OSS (Online Single Submission) system has implemented stricter verification of minimum capital requirements for PT PMA companies. Foreign-owned businesses must now demonstrate proof of capital deposit within 60 days of company registration.',
      source: 'BKPM',
      sourceUrl: 'https://bkpm.go.id',
      category: 'business',
      priority: 'high',
      status: 'pending',
      publishedAt: new Date().toISOString(),
      scrapedAt: new Date().toISOString(),
    },
  ];
}

// GET - List news
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const status = searchParams.get('status');
  const category = searchParams.get('category');
  const limit = parseInt(searchParams.get('limit') || '20');

  let news = await loadNews();

  // Filter by status
  if (status) {
    news = news.filter(n => n.status === status);
  }

  // Filter by category
  if (category) {
    news = news.filter(n => n.category === category);
  }

  // Sort by priority then date
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  news.sort((a, b) => {
    const pDiff = priorityOrder[a.priority] - priorityOrder[b.priority];
    if (pDiff !== 0) return pDiff;
    return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime();
  });

  // Limit results
  news = news.slice(0, limit);

  return NextResponse.json({
    success: true,
    data: news,
    total: news.length,
  });
}

// POST - Add new news item (from scraper)
export async function POST(request: NextRequest) {
  const body = await request.json();
  const news = await loadNews();

  const newItem: NewsItem = {
    id: `news_${Date.now()}`,
    title: body.title,
    summary: body.summary,
    content: body.content,
    source: body.source,
    sourceUrl: body.sourceUrl,
    category: body.category || 'business',
    priority: body.priority || 'medium',
    status: 'pending', // Always start as pending for review
    publishedAt: body.publishedAt || new Date().toISOString(),
    scrapedAt: new Date().toISOString(),
    imageUrl: body.imageUrl,
  };

  news.unshift(newItem);
  await saveNews(news);

  return NextResponse.json({
    success: true,
    data: newItem,
  });
}

// PATCH - Update news status (approve/reject)
export async function PATCH(request: NextRequest) {
  const body = await request.json();
  const { id, status } = body;

  if (!id || !status) {
    return NextResponse.json(
      { success: false, error: 'id and status are required' },
      { status: 400 }
    );
  }

  const news = await loadNews();
  const index = news.findIndex(n => n.id === id);

  if (index === -1) {
    return NextResponse.json(
      { success: false, error: 'News item not found' },
      { status: 404 }
    );
  }

  news[index].status = status;
  await saveNews(news);

  return NextResponse.json({
    success: true,
    data: news[index],
  });
}
