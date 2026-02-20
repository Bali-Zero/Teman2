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
        
        articles = []
        
        try:
            # Try RSS/Atom feed first (fast & reliable)
            feed = feedparser.parse(url, timeout=5)
            if feed.entries:
                self.log(f'  ✓ Found {len(feed.entries)} feed entries')
                for entry in feed.entries[:self.limit_per_source]:
                    article = self._extract_from_feed_entry(entry, source)
                    if article:
                        articles.append(article)
            
            # If no feed, try article extraction (slower, less reliable)
            if not articles:
                self.log(f'  No feed, trying article extraction...')
                article = self._extract_from_webpage(url, source)
                if article:
                    articles.append(article)
                else:
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
    
    def score_article(self, article: Dict) -> Optional[int]:
        """Score article quality using Ollama (local, free)"""
        try:
            prompt = f"""Score this article's value for Bali business/visa/immigration consulting (0-100):

Title: {article.get('title', '')}
Summary: {article.get('summary', '')[:300]}
Source: {article.get('source_name', '')}

Respond with ONLY a number 0-100."""

            result = subprocess.run(
                ['ollama', 'run', 'deepseek-r1:1.5b', prompt],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                score_text = result.stdout.strip()
                # Extract first number found
                import re
                match = re.search(r'\d+', score_text)
                if match:
                    score = int(match.group())
                    return max(0, min(100, score))  # Clamp 0-100
        
        except subprocess.TimeoutExpired:
            self.log('  Ollama timeout', 'WARN')
        except Exception as e:
            self.log(f'  Scoring error: {e}', 'WARN')
        
        return None
    
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
            time.sleep(2)
        
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
