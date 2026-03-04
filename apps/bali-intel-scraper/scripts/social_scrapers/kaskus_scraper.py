"""
Kaskus Forum Scraper
Scrapes threads from Kaskus.co.id forums using httpx + BeautifulSoup.
No authentication required for public forums.
"""

import time
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
POLITE_DELAY = 2  # seconds between requests


def fetch_kaskus_threads(
    url: str,
    limit: int = 10,
) -> List[Dict]:
    """Fetch thread listings from a Kaskus forum page."""
    headers = {'User-Agent': USER_AGENT}
    threads = []

    try:
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise ValueError(f'Failed to fetch Kaskus page: {e}')

    soup = BeautifulSoup(resp.text, 'lxml')

    # Kaskus thread links are typically in <a> tags with thread URLs
    seen_urls = set()
    candidates = []

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        text = a_tag.get_text(strip=True)

        # Kaskus thread URLs contain /thread/
        if '/thread/' not in href:
            continue
        if len(text) < 15:
            continue

        full_url = urljoin('https://www.kaskus.co.id', href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        candidates.append({
            'title': text,
            'url': full_url,
        })

        if len(candidates) >= limit * 2:
            break

    # Fetch each thread page for content (first post only)
    for candidate in candidates[:limit]:
        try:
            time.sleep(POLITE_DELAY)
            thread_resp = httpx.get(
                candidate['url'], headers=headers, timeout=15, follow_redirects=True
            )
            thread_resp.raise_for_status()

            thread_soup = BeautifulSoup(thread_resp.text, 'lxml')

            # Extract first post content
            post_content = ''
            # Try common Kaskus post selectors
            for selector in ['div.post-content', 'div.entry', 'article', 'div.post_body']:
                content_div = thread_soup.select_one(selector)
                if content_div:
                    post_content = content_div.get_text(strip=True)[:2000]
                    break

            if not post_content:
                # Fallback: get meta description
                meta = thread_soup.find('meta', attrs={'name': 'description'})
                if meta:
                    post_content = meta.get('content', '')

            threads.append({
                'title': candidate['title'],
                'url': candidate['url'],
                'text': post_content,
                'date': datetime.now().isoformat(),
            })

        except Exception:
            # Skip individual thread errors
            continue

    return threads
