#!/usr/bin/env python3
"""
Unified Article Scraper (Async)
Scrapes articles from 609 sources in unified_sources.json
Uses: httpx + asyncio + newspaper3k + Ollama scoring

Output: data/scraped/YYYYMMDD_HHMMSS_articles.json
"""

import json
import sys
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from dateutil import parser as date_parser

try:
    from newspaper import Article
    import feedparser
    import httpx
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install newspaper3k feedparser beautifulsoup4 lxml httpx")
    sys.exit(1)

import logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("unified_scraper")

# Known RSS feeds for major sources (auto-resolved)
_KNOWN_RSS = {
    'thejakartapost.com': 'https://www.thejakartapost.com/rss/feed.xml',
    'jakartaglobe.id': 'https://jakartaglobe.id/feed',
    'tempo.co': 'https://en.tempo.co/rss/20',
    'kompas.com': 'https://rss.kompas.com/aktual/xml/topheadline.xml',
    'detik.com': 'https://rss.detik.com/index.php/detikcom',
    'cnnindonesia.com': 'https://www.cnnindonesia.com/rss',
    'hukumonline.com': 'https://www.hukumonline.com/rss/berita.xml',
    'indonesiaexpat.id': 'https://indonesiaexpat.id/feed/',
    'reddit.com': None,
    'cnbcindonesia.com': 'https://www.cnbcindonesia.com/rss',
    'ddtc.co.id': 'https://ddtc.co.id/rss',
}

def _resolve_rss(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    if 'youtube.com/feeds/videos.xml' in url:
        return url
    if 'reddit.com/r/' in url:
        path = parsed.path.rstrip('/')
        return f'https://www.reddit.com{path}/.rss'
    for key, rss in _KNOWN_RSS.items():
        if key in domain and rss:
            return rss
    return url

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCES_FILE = PROJECT_ROOT / 'config' / 'unified_sources.json'
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'scraped'
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
TIMEOUT = 30
MIN_SCORE = 40
MAX_AGE_DAYS = 7


class UnifiedScraper:
    def __init__(self, categories: list[str] = None, limit_per_source: int = 5):
        self.categories = categories or ['immigration', 'tax', 'legal']
        self.limit_per_source = limit_per_source
        self.stats = {
            'sources_processed': 0,
            'articles_found': 0,
            'articles_scored': 0,
            'articles_passed': 0,
            'errors': 0
        }
        self.client = httpx.AsyncClient(
            headers={'User-Agent': USER_AGENT},
            timeout=15.0,
            verify=False,
            follow_redirects=True
        )

    async def close(self):
        await self.client.aclose()

    def load_sources(self) -> list[dict]:
        with open(SOURCES_FILE) as f:
            data = json.load(f)
        sources = []
        categories_data = data.get('categories', {})
        for category_name in self.categories:
            if category_name in categories_data:
                category_sources = categories_data[category_name].get('sources', [])
                for source in category_sources:
                    source['category'] = category_name
                    sources.append(source)
        logger.info(f'Loaded {len(sources)} sources from {len(self.categories)} categories')
        return sources

    def _is_recent(self, published_str: str) -> bool:
        if not published_str:
            return True
        try:
            pub_date = date_parser.parse(published_str)
            now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()
            if (now - pub_date).days > MAX_AGE_DAYS:
                return False
        except Exception:
            pass
        return True

    async def _fetch_rss(self, url: str) -> str | None:
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None

    async def extract_articles_from_source(self, source: dict) -> list[dict]:
        url = source.get('url')
        if not url:
            return []

        logger.info(f'Scraping: {source.get("name", url)[:50]}...')

        source_type = source.get('type', 'web')
        if source_type == 'telegram':
            return await asyncio.to_thread(self._extract_telegram, source)
        elif source_type == 'reddit':
            return await asyncio.to_thread(self._extract_reddit, source)
        elif source_type == 'kaskus':
            return await asyncio.to_thread(self._extract_kaskus, source)

        articles = []
        try:
            rss_url = _resolve_rss(url)
            rss_text = await self._fetch_rss(rss_url)
            feed = None
            if rss_text:
                feed = await asyncio.to_thread(feedparser.parse, rss_text)

            if not (feed and feed.entries) and rss_url != url:
                rss_text = await self._fetch_rss(url)
                if rss_text:
                    feed = await asyncio.to_thread(feedparser.parse, rss_text)

            if not (feed and feed.entries):
                try:
                    resp = await self.client.get(url)
                    soup = BeautifulSoup(resp.text, 'lxml')
                    rss_link = soup.find('link', type='application/rss+xml')
                    if rss_link and rss_link.get('href'):
                        discovered = rss_link['href']
                        if discovered.startswith('/'):
                            p = urlparse(url)
                            discovered = f"{p.scheme}://{p.netloc}{discovered}"

                        r_text = await self._fetch_rss(discovered)
                        if r_text:
                            feed = await asyncio.to_thread(feedparser.parse, r_text)
                            if feed.entries:
                                logger.info(f'  ✓ RSS discovered: {discovered}')
                except Exception:
                    pass

            if feed and feed.entries:
                logger.info(f'  ✓ {len(feed.entries)} feed entries')
                for entry in feed.entries[:self.limit_per_source * 2]:
                    published = entry.get('published', '')
                    if not self._is_recent(published):
                        continue
                    article = self._extract_from_feed_entry(entry, source)
                    if article:
                        articles.append(article)
                        if len(articles) >= self.limit_per_source:
                            break

            if not articles:
                articles = await self._extract_from_listing(url, source)

            if not articles:
                logger.warning(f'  ⚠️  No content extracted for {url}')

        except Exception as e:
            logger.error(f'  ❌ Error processing {url}: {str(e)[:100]}')
            self.stats['errors'] += 1

        return articles

    def _extract_from_feed_entry(self, entry, source: dict) -> dict | None:
        try:
            return {
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'summary': entry.get('summary', ''),
                'published': entry.get('published', ''),
                'source_name': source.get('name', ''),
                'source_url': source.get('url', ''),
                'category': source.get('category', ''),
                'tier': source.get('tier', 'T3'),
                'scraped_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f'  Feed entry error: {e}')
            return None

    async def _extract_from_listing(self, url, source):
        articles = []
        try:
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, 'lxml')
            base = urlparse(url).scheme + '://' + urlparse(url).netloc
            seen, candidates = set(), []
            for a in soup.find_all('a', href=True):
                from urllib.parse import urljoin
                href = urljoin(base, a['href'])
                text = a.get_text(strip=True)
                if (len(text) > 30 and href not in seen
                        and href.startswith('http')
                        and urlparse(href).netloc == urlparse(url).netloc
                        and href != url
                        and '#' not in href
                        and 'mailto:' not in href):
                    seen.add(href)
                    candidates.append((href, text))
                if len(candidates) >= self.limit_per_source * 3:
                    break

            def parse_article(href, anchor_text):
                try:
                    art = Article(href)
                    art.config.request_timeout = 8
                    art.download()
                    art.parse()
                    title = art.title or anchor_text
                    published = art.publish_date.isoformat() if art.publish_date else ''
                    if not self._is_recent(published):
                        return None
                    if title and len(art.text) >= 150:
                        return {
                            'title': title, 'url': href,
                            'summary': getattr(art, 'meta_description', '') or art.text[:250],
                            'text': art.text[:2000],
                            'published': published,
                            'source_name': source.get('name',''), 'source_url': source.get('url',''),
                            'category': source.get('category',''), 'tier': source.get('tier','T3'),
                            'scraped_at': datetime.now().isoformat(),
                        }
                except Exception:
                    pass
                return None

            tasks = [asyncio.to_thread(parse_article, h, t) for h, t in candidates]
            results = await asyncio.gather(*tasks)
            articles = [r for r in results if r is not None][:self.limit_per_source]

            if articles:
                logger.info(f'  + Listing: {len(articles)} articles')
        except Exception as e:
            logger.warning(f'  Listing error: {e}')
        return articles

    def score_article(self, article: dict) -> int | None:
        title   = (article.get('title', '') or '').lower()
        summary = (article.get('summary', '') or article.get('text', '') or '').lower()
        source  = (article.get('source_name', '') or '').lower()
        text    = title + ' ' + summary

        t1_sources = ['imigrasi', 'kemenkumham', 'bkpm', 'pajak', 'bps.go.id', 'hukumonline',
                      'ddtc', 'kemlu', 'jakarta post', 'tempo', 'kompas', 'jakartaglobe',
                      'indonesia expat', 'cnnindonesia', 'detik']
        base = 70 if any(s in source for s in t1_sources) else 45

        HIGH = ['kitas', 'visa', 'imigrasi', 'immigration', 'kbli', 'coretax', 'pajak', 'tax',
                'bpjs', 'permit', 'izin', 'oss', 'investment', 'investor', 'expat', 'wna',
                'deportasi', 'overstay', 'pt pma', 'perda', 'regulation', 'law', 'hukum',
                'bali business', 'foreign worker', 'tenaga asing',
                'digital nomad visa', 'kitas renewal', 'immigration office', 'overstay fine',
                'second home visa', 'golden visa', 'e-visa', 'telex visa', 'sponsor visa']
        MED  = ['indonesia', 'bisnis', 'business', 'economy', 'ekonomi', 'rupiah', 'bali',
                'digital nomad', 'property', 'properti', 'foreign', 'asing', 'pemerintah',
                'nomad', 'remote work', 'coworking', 'canggu', 'ubud', 'seminyak',
                'denpasar', 'sanur', 'nusa dua']
        NEG  = ['sport', 'olahraga', 'sepak bola', 'entertainment', 'celebrity', 'musik',
                'gossip', 'artis', 'film', 'resep', 'makanan']

        score = base
        score += sum(8 for kw in HIGH if kw in text)
        score += sum(3 for kw in MED  if kw in text)
        score -= sum(20 for kw in NEG if kw in text)

        return max(0, min(100, score))

    def generate_article_id(self, article: dict) -> str:
        content = f"{article.get('url', '')}{article.get('title', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    async def scrape_all(self) -> list[dict]:
        logger.info('='*60)
        logger.info('UNIFIED SCRAPER STARTED (ASYNC)')
        logger.info('='*60)

        sources = self.load_sources()
        all_articles = []

        # Batch sources to avoid overwhelming the network
        batch_size = 20
        for i in range(0, len(sources), batch_size):
            batch = sources[i:i+batch_size]
            tasks = [self.extract_articles_from_source(s) for s in batch]
            results = await asyncio.gather(*tasks)

            for source_articles in results:
                self.stats['sources_processed'] += 1
                self.stats['articles_found'] += len(source_articles)
                for article in source_articles:
                    article['id'] = self.generate_article_id(article)
                    score = self.score_article(article)
                    self.stats['articles_scored'] += 1

                    if score is not None:
                        article['quality_score'] = score
                        if score >= MIN_SCORE:
                            all_articles.append(article)
                            self.stats['articles_passed'] += 1

        return all_articles

    def save_results(self, articles: list[dict]):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f'{timestamp}_articles.json'
        output = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'articles': articles
        }
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info(f'\n💾 Saved: {output_file}')
        return output_file

    def print_summary(self):
        logger.info('\n' + '='*60)
        logger.info('SCRAPING COMPLETE')
        logger.info('='*60)
        logger.info(f"""
📊 STATS:
   Sources processed: {self.stats['sources_processed']}
   Articles found:    {self.stats['articles_found']}
   Articles scored:   {self.stats['articles_scored']}
   Passed threshold:  {self.stats['articles_passed']} (>={MIN_SCORE} score)
   Errors:            {self.stats['errors']}
""")

    def _extract_telegram(self, source: dict) -> list[dict]:
        try:
            from social_scrapers.telegram_scraper import fetch_telegram_channel_sync
            channel = source['url'].split('t.me/')[-1]
            messages = fetch_telegram_channel_sync(channel, limit=self.limit_per_source)
            res = []
            for msg in messages:
                if msg.get('text'):
                    published = msg['date']
                    if self._is_recent(published):
                        res.append({
                            'title': msg['text'][:100],
                            'url': msg['url'],
                            'summary': msg['text'][:500],
                            'text': msg['text'],
                            'published': published,
                            'source_name': source.get('name', ''),
                            'source_url': source.get('url', ''),
                            'category': source.get('category', 'social_media'),
                            'tier': source.get('tier', 'T2'),
                            'scraped_at': datetime.now().isoformat(),
                        })
            return res
        except Exception as e:
            logger.warning(f'  ⚠️ Telegram error: {e}')
            return []

    def _extract_reddit(self, source: dict) -> list[dict]:
        try:
            from social_scrapers.reddit_scraper import fetch_subreddit
            subreddit = source['url'].split('/r/')[-1].strip('/')
            posts = fetch_subreddit(subreddit, limit=self.limit_per_source)
            res = []
            for post in posts:
                published = post['created_utc']
                if self._is_recent(published):
                    res.append({
                        'title': post['title'],
                        'url': post['url'],
                        'summary': post['text'][:500] if post.get('text') else post['title'],
                        'text': post.get('text', ''),
                        'published': published,
                        'source_name': source.get('name', ''),
                        'source_url': source.get('url', ''),
                        'category': source.get('category', 'social_media'),
                        'tier': source.get('tier', 'T3'),
                        'scraped_at': datetime.now().isoformat(),
                    })
            return res
        except Exception as e:
            logger.warning(f'  ⚠️ Reddit error: {e}')
            return []

    def _extract_kaskus(self, source: dict) -> list[dict]:
        try:
            from social_scrapers.kaskus_scraper import fetch_kaskus_threads
            threads = fetch_kaskus_threads(source['url'], limit=self.limit_per_source)
            res = []
            for thread in threads:
                if thread.get('title'):
                    published = thread.get('date', '')
                    if self._is_recent(published):
                        res.append({
                            'title': thread['title'],
                            'url': thread['url'],
                            'summary': thread.get('text', '')[:500],
                            'text': thread.get('text', ''),
                            'published': published,
                            'source_name': source.get('name', ''),
                            'source_url': source.get('url', ''),
                            'category': source.get('category', 'social_media'),
                            'tier': source.get('tier', 'T3'),
                            'scraped_at': datetime.now().isoformat(),
                        })
            return res
        except Exception as e:
            logger.warning(f'  ⚠️ Kaskus error: {e}')
            return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Unified Article Scraper')
    parser.add_argument('--categories', default='immigration,tax,legal', help='Comma-separated categories')
    parser.add_argument('--limit', type=int, default=5, help='Limit articles per source')
    parser.add_argument('--min-score', type=int, default=40, help='Minimum quality score')
    args = parser.parse_args()

    global MIN_SCORE
    MIN_SCORE = args.min_score

    scraper = UnifiedScraper(categories=args.categories.split(','), limit_per_source=args.limit)

    async def run():
        articles = await scraper.scrape_all()
        output_file = scraper.save_results(articles)
        scraper.print_summary()
        await scraper.close()
        print(f'\n✅ Output: {output_file}')
        return 0 if articles else 1

    return asyncio.run(run())

if __name__ == '__main__':
    sys.exit(main())
