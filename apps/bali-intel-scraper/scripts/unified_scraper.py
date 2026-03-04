#!/usr/bin/env python3
"""
Unified Article Scraper
Scrapes articles from 609 sources in unified_sources.json
Uses: newspaper3k + BeautifulSoup + Ollama scoring

Output: data/scraped/YYYYMMDD_HHMMSS_articles.json
"""

import json
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import subprocess
from urllib.parse import urlparse

# Third-party imports (need to install)
try:
    from newspaper import Article
    import feedparser
    import requests
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install newspaper3k feedparser beautifulsoup4 lxml requests")
    sys.exit(1)

# Paths

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
    'reddit.com': None,  # handled via URL pattern below
    'cnbcindonesia.com': 'https://www.cnbcindonesia.com/rss',
    'ddtc.co.id': 'https://ddtc.co.id/rss',
}

def _resolve_rss(url: str) -> str:
    """Return best RSS URL for a given source URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    # YouTube RSS feeds are already valid RSS URLs
    if 'youtube.com/feeds/videos.xml' in url:
        return url
    # Reddit subreddit RSS
    if 'reddit.com/r/' in url:
        path = parsed.path.rstrip('/')
        return f'https://www.reddit.com{path}/.rss'
    for key, rss in _KNOWN_RSS.items():
        if key in domain and rss:
            return rss
    return url  # fallback: try original URL as-is with feedparser

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCES_FILE = PROJECT_ROOT / 'config' / 'unified_sources.json'
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'scraped'
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Config
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
TIMEOUT = 30
MIN_SCORE = 40  # Ollama quality threshold


class UnifiedScraper:
    def __init__(self, categories: List[str] = None, limit_per_source: int = 5):
        self.categories = categories or ['immigration', 'tax', 'legal']
        self.limit_per_source = limit_per_source
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.stats = {
            'sources_processed': 0,
            'articles_found': 0,
            'articles_scored': 0,
            'articles_passed': 0,
            'errors': 0
        }
    
    def log(self, message: str, level: str = 'INFO'):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f'[{timestamp}] [{level}] {message}')
        sys.stdout.flush()
    
    def load_sources(self) -> List[Dict]:
        """Load sources from unified_sources.json"""
        with open(SOURCES_FILE, 'r') as f:
            data = json.load(f)
        
        # Extract sources from categories
        sources = []
        categories_data = data.get('categories', {})
        
        for category_name in self.categories:
            if category_name in categories_data:
                category_sources = categories_data[category_name].get('sources', [])
                for source in category_sources:
                    source['category'] = category_name
                    sources.append(source)
        
        self.log(f'Loaded {len(sources)} sources from {len(self.categories)} categories')
        return sources
    
    def extract_articles_from_source(self, source: Dict) -> List[Dict]:
        """Extract articles from a single source"""
        url = source.get('url')
        if not url:
            return []
        
        self.log(f'Scraping: {source.get("name", url)[:50]}...')

        # Social media type dispatch
        source_type = source.get('type', 'web')
        if source_type == 'telegram':
            return self._extract_telegram(source)
        elif source_type == 'reddit':
            return self._extract_reddit(source)
        elif source_type == 'kaskus':
            return self._extract_kaskus(source)
        elif source_type == 'youtube_rss':
            pass  # YouTube RSS works with existing feedparser pipeline

        articles = []
        
        try:
            # 1) Risolvi RSS noto o fai discovery
            rss_url = _resolve_rss(url)
            feed = feedparser.parse(rss_url)

            # 2) Se RSS risolto fallisce, prova discovery dalla homepage
            if not feed.entries and rss_url != url:
                feed = feedparser.parse(url)

            if not feed.entries:
                # Discovery: cerca <link type="application/rss+xml"> nel HTML
                try:
                    resp = self.session.get(url, timeout=8)
                    from bs4 import BeautifulSoup as _BS
                    soup = _BS(resp.text, 'lxml')
                    rss_link = soup.find('link', type='application/rss+xml')
                    if rss_link and rss_link.get('href'):
                        discovered = rss_link['href']
                        if discovered.startswith('/'):
                            from urllib.parse import urlparse as _up
                            p = _up(url)
                            discovered = f"{p.scheme}://{p.netloc}{discovered}"
                        feed = feedparser.parse(discovered)
                        if feed.entries:
                            self.log(f'  ✓ RSS discovered: {discovered}')
                except Exception:
                    pass

            if feed.entries:
                self.log(f'  ✓ {len(feed.entries)} feed entries')
                for entry in feed.entries[:self.limit_per_source]:
                    article = self._extract_from_feed_entry(entry, source)
                    if article:
                        articles.append(article)

            # 3) Nessun RSS → scraping listing (tag/search/category page)
            if not articles:
                articles = self._extract_from_listing(url, source)

            if not articles:
                self.log(f'  ⚠️  No content extracted', 'WARN')
        
        except Exception as e:
            self.log(f'  ❌ Error: {str(e)[:100]}', 'ERROR')
            self.stats['errors'] += 1
        
        return articles
    
    def _extract_from_feed_entry(self, entry, source: Dict) -> Optional[Dict]:
        """Extract article from RSS feed entry"""
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
            self.log(f'  Feed entry error: {e}', 'WARN')
            return None
    
    def _extract_from_webpage(self, url: str, source: Dict) -> Optional[Dict]:
        """Extract article from webpage using newspaper3k"""
        try:
            article = Article(url)
            article.config.request_timeout = 10  # Aggressive timeout
            article.download()
            article.parse()
            
            if not article.title or len(article.text) < 200:
                return None
            
            return {
                'title': article.title,
                'url': url,
                'summary': article.summary if hasattr(article, 'summary') else '',
                'text': article.text[:2000],  # Limit for scoring
                'published': article.publish_date.isoformat() if article.publish_date else '',
                'source_name': source.get('name', ''),
                'source_url': source.get('url', ''),
                'category': source.get('category', ''),
                'tier': source.get('tier', 'T3'),
                'scraped_at': datetime.now().isoformat()
            }
        except Exception as e:
            self.log(f'  Webpage extraction error: {e}', 'WARN')
            return None
    

    def _extract_from_listing(self, url, source):
        """FIX3: scrape tag/search/category listing, extract and fetch article links."""
        articles = []
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            from bs4 import BeautifulSoup as _BS
            from urllib.parse import urljoin, urlparse as _up
            soup = _BS(resp.text, 'lxml')
            base = _up(url).scheme + '://' + _up(url).netloc
            seen, candidates = set(), []
            for a in soup.find_all('a', href=True):
                href = urljoin(base, a['href'])
                text = a.get_text(strip=True)
                if (len(text) > 30 and href not in seen
                        and href.startswith('http')
                        and _up(href).netloc == _up(url).netloc
                        and href != url
                        and '#' not in href
                        and 'mailto:' not in href):
                    seen.add(href)
                    candidates.append((href, text))
                if len(candidates) >= self.limit_per_source * 3:
                    break
            from newspaper import Article as _Art
            import datetime as _dt
            for href, anchor_text in candidates[:self.limit_per_source]:
                try:
                    art = _Art(href)
                    art.config.request_timeout = 8
                    art.download()
                    art.parse()
                    title = art.title or anchor_text
                    if title and len(art.text) >= 150:
                        articles.append({
                            'title': title, 'url': href,
                            'summary': getattr(art, 'meta_description', '') or art.text[:250],
                            'text': art.text[:2000],
                            'published': art.publish_date.isoformat() if art.publish_date else '',
                            'source_name': source.get('name',''), 'source_url': source.get('url',''),
                            'category': source.get('category',''), 'tier': source.get('tier','T3'),
                            'scraped_at': _dt.datetime.now().isoformat(),
                        })
                except Exception:
                    pass
            if articles:
                self.log('  + Listing: ' + str(len(articles)) + ' articles')
        except Exception as e:
            self.log('  Listing error: ' + str(e), 'WARN')
        return articles

    def score_article(self, article: Dict) -> Optional[int]:
        """FIX: keyword scoring istantaneo. AI scoring avviene in step 2.5 della pipeline."""
        title   = (article.get('title', '') or '').lower()
        summary = (article.get('summary', '') or article.get('text', '') or '').lower()
        source  = (article.get('source_name', '') or '').lower()
        text    = title + ' ' + summary

        # Sorgenti T1 autopass
        t1_sources = ['imigrasi', 'kemenkumham', 'bkpm', 'pajak', 'bps.go.id', 'hukumonline',
                      'ddtc', 'kemlu', 'jakarta post', 'tempo', 'kompas', 'jakartaglobe',
                      'indonesia expat', 'cnnindonesia', 'detik']
        base = 70 if any(s in source for s in t1_sources) else 45

        HIGH = ['kitas', 'visa', 'imigrasi', 'immigration', 'kbli', 'coretax', 'pajak', 'tax',
                'bpjs', 'permit', 'izin', 'oss', 'investment', 'investor', 'expat', 'wna',
                'deportasi', 'overstay', 'pt pma', 'perda', 'regulation', 'law', 'hukum',
                'bali business', 'foreign worker', 'tenaga asing']
        MED  = ['indonesia', 'bisnis', 'business', 'economy', 'ekonomi', 'rupiah', 'bali',
                'digital nomad', 'property', 'properti', 'foreign', 'asing', 'pemerintah']
        NEG  = ['sport', 'olahraga', 'sepak bola', 'entertainment', 'celebrity', 'musik',
                'gossip', 'artis', 'film', 'resep', 'makanan']

        score = base
        score += sum(8 for kw in HIGH if kw in text)
        score += sum(3 for kw in MED  if kw in text)
        score -= sum(20 for kw in NEG if kw in text)

        return max(0, min(100, score))

    def generate_article_id(self, article: Dict) -> str:
        """Generate unique ID for article"""
        content = f"{article.get('url', '')}{article.get('title', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def scrape_all(self) -> List[Dict]:
        """Scrape articles from all sources"""
        self.log('='*60)
        self.log('UNIFIED SCRAPER STARTED')
        self.log('='*60)
        
        sources = self.load_sources()
        all_articles = []
        
        for i, source in enumerate(sources, 1):
            self.log(f'\n[{i}/{len(sources)}] {source.get("name", "Unknown")[:40]}')
            
            articles = self.extract_articles_from_source(source)
            self.stats['sources_processed'] += 1
            self.stats['articles_found'] += len(articles)
            
            # Score each article
            for article in articles:
                article['id'] = self.generate_article_id(article)
                
                score = self.score_article(article)
                self.stats['articles_scored'] += 1
                
                if score is not None:
                    article['quality_score'] = score
                    if score >= MIN_SCORE:
                        all_articles.append(article)
                        self.stats['articles_passed'] += 1
                        self.log(f'  ✅ Score: {score} - {article["title"][:50]}...')
                    else:
                        self.log(f'  ❌ Score: {score} (below threshold)')
                else:
                    self.log(f'  ⚠️  Could not score')
            
            # Rate limiting
            time.sleep(0.5)  # FIX3: reduced from 2s
        
        return all_articles
    
    def save_results(self, articles: List[Dict]):
        """Save scraped articles to JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f'{timestamp}_articles.json'
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'articles': articles
        }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        self.log(f'\n💾 Saved: {output_file}')
        return output_file
    
    def print_summary(self):
        """Print scraping summary"""
        self.log('\n' + '='*60)
        self.log('SCRAPING COMPLETE')
        self.log('='*60)
        self.log(f"""
📊 STATS:
   Sources processed: {self.stats['sources_processed']}
   Articles found:    {self.stats['articles_found']}
   Articles scored:   {self.stats['articles_scored']}
   Passed threshold:  {self.stats['articles_passed']} (>={MIN_SCORE} score)
   Errors:            {self.stats['errors']}
""")


    def _extract_telegram(self, source: Dict) -> List[Dict]:
        """Stub: implemented in Task 5"""
        return []

    def _extract_reddit(self, source: Dict) -> List[Dict]:
        """Stub: implemented in Task 6"""
        return []

    def _extract_kaskus(self, source: Dict) -> List[Dict]:
        """Stub: implemented in Task 7"""
        return []


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified Article Scraper')
    parser.add_argument('--categories', default='immigration,tax,legal',
                       help='Comma-separated categories')
    parser.add_argument('--limit', type=int, default=5,
                       help='Limit articles per source')
    parser.add_argument('--min-score', type=int, default=40,
                       help='Minimum quality score')
    
    args = parser.parse_args()
    
    # Update global config
    global MIN_SCORE
    MIN_SCORE = args.min_score
    
    # Run scraper
    scraper = UnifiedScraper(
        categories=args.categories.split(','),
        limit_per_source=args.limit
    )
    
    articles = scraper.scrape_all()
    output_file = scraper.save_results(articles)
    scraper.print_summary()
    
    print(f'\n✅ Output: {output_file}')
    return 0 if articles else 1


if __name__ == '__main__':
    sys.exit(main())
