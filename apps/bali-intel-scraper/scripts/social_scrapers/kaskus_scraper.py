"""
Kaskus Forum Scraper
Scrapes threads from Kaskus.co.id forums using Playwright + BeautifulSoup.
Kaskus is JS-rendered, so headless Chromium is required for listing pages.
Thread content is extracted from og:description meta tags (server-rendered).
No authentication required for public forums.
"""

import time
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

POLITE_DELAY = 2  # seconds between requests


def _render_page(url: str, wait_ms: int = 5000) -> str:
    """Render a JS page with Playwright and return HTML."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(wait_ms)
            return page.content()
        finally:
            browser.close()


def fetch_kaskus_threads(
    url: str,
    limit: int = 10,
) -> List[Dict]:
    """Fetch thread listings from a Kaskus forum page."""
    threads = []

    # Step 1: Render listing page with Playwright (JS-rendered)
    try:
        html = _render_page(url)
    except Exception as e:
        raise ValueError(f'Failed to render Kaskus page: {e}') from e

    soup = BeautifulSoup(html, 'lxml')

    # Kaskus thread links contain /thread/ in the href
    seen_urls = set()
    candidates = []

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        text = a_tag.get_text(strip=True)

        if '/thread/' not in href:
            continue
        if len(text) < 15:
            continue

        full_url = urljoin('https://www.kaskus.co.id', href.split('?')[0])
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        candidates.append({
            'title': text,
            'url': full_url,
        })

        if len(candidates) >= limit:
            break

    # Step 2: Fetch each thread page for content via httpx
    # og:description is server-rendered, no Playwright needed
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    for candidate in candidates:
        try:
            time.sleep(POLITE_DELAY)
            resp = httpx.get(candidate['url'], headers=headers, timeout=15, follow_redirects=True)
            thread_soup = BeautifulSoup(resp.text, 'lxml')

            # og:description contains the first post content (server-rendered)
            post_content = ''
            og = thread_soup.find('meta', property='og:description')
            if og:
                post_content = og.get('content', '')

            if not post_content:
                meta = thread_soup.find('meta', attrs={'name': 'description'})
                if meta:
                    post_content = meta.get('content', '')

            threads.append({
                'title': candidate['title'],
                'url': candidate['url'],
                'text': post_content[:2000],
                'date': datetime.now().isoformat(),
            })

        except Exception:
            continue

    return threads
