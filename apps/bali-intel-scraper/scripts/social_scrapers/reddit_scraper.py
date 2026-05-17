"""
Reddit Scraper
Primary: uses Reddit JSON API (no auth, rate-limited).
Fallback: uses PRAW if REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET are set (higher limits).

Reddit is blocked by some ISPs (e.g. Indonesia). Set NORDVPN_SOCKS_USER and
NORDVPN_SOCKS_PASS to route through NordVPN SOCKS5 proxy automatically.
"""

import os
from datetime import datetime, timezone

import httpx


def _build_proxy_url() -> str:
    """Build SOCKS5 proxy URL from NordVPN env vars, or return empty string."""
    user = os.environ.get('NORDVPN_SOCKS_USER', '')
    passwd = os.environ.get('NORDVPN_SOCKS_PASS', '')
    if user and passwd:
        return f'socks5://{user}:{passwd}@nl.socks.nordhold.net:1080'
    return ''


def fetch_subreddit(
    subreddit_name: str,
    limit: int = 10,
    sort: str = 'new',
    min_score: int = 5,
    min_text_length: int = 50,
) -> list[dict]:
    """Fetch posts from a subreddit.

    Uses PRAW if credentials are set, otherwise falls back to JSON API.
    """
    client_id = os.environ.get('REDDIT_CLIENT_ID', '')
    client_secret = os.environ.get('REDDIT_CLIENT_SECRET', '')

    if client_id and client_secret:
        return _fetch_via_praw(subreddit_name, limit, sort, min_score, min_text_length,
                               client_id, client_secret)

    return _fetch_via_json(subreddit_name, limit, sort, min_score, min_text_length)


def _fetch_via_json(
    subreddit_name: str,
    limit: int,
    sort: str,
    min_score: int,
    min_text_length: int,
) -> list[dict]:
    """Fetch via Reddit JSON API — no auth, works without API keys."""
    url = f'https://www.reddit.com/r/{subreddit_name}/{sort}.json'
    params = {'limit': str(limit * 3), 'raw_json': '1'}
    headers = {
        'User-Agent': 'BaliZeroIntelScraper/1.0 (by /u/balizero)',
        'Accept': 'application/json',
    }

    proxy = _build_proxy_url()
    with httpx.Client(proxy=proxy, timeout=15, follow_redirects=True) if proxy else httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(url, params=params, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    children = data.get('data', {}).get('children', [])

    posts = []
    for child in children:
        post = child.get('data', {})

        score = post.get('score', 0)
        if score < min_score:
            continue

        text = post.get('selftext', '')
        if len(text) < min_text_length and not post.get('url'):
            continue

        created = post.get('created_utc', 0)

        posts.append({
            'title': post.get('title', ''),
            'text': text[:2000],
            'url': f'https://www.reddit.com{post.get("permalink", "")}',
            'score': score,
            'num_comments': post.get('num_comments', 0),
            'created_utc': datetime.fromtimestamp(created, tz=timezone.utc).isoformat() if created else '',
            'author': post.get('author', '[deleted]'),
            'subreddit': subreddit_name,
        })

        if len(posts) >= limit:
            break

    return posts


def _fetch_via_praw(
    subreddit_name: str,
    limit: int,
    sort: str,
    min_score: int,
    min_text_length: int,
    client_id: str,
    client_secret: str,
) -> list[dict]:
    """Fetch via PRAW (authenticated, higher rate limits)."""
    import praw

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent='BaliZeroIntelScraper/1.0',
    )

    subreddit = reddit.subreddit(subreddit_name)

    if sort == 'hot':
        submissions = subreddit.hot(limit=limit * 3)
    elif sort == 'top':
        submissions = subreddit.top(limit=limit * 3, time_filter='day')
    else:
        submissions = subreddit.new(limit=limit * 3)

    posts = []
    for post in submissions:
        if post.score < min_score:
            continue

        text = post.selftext or ''
        if len(text) < min_text_length and not post.url:
            continue

        posts.append({
            'title': post.title,
            'text': text[:2000],
            'url': f'https://www.reddit.com{post.permalink}',
            'score': post.score,
            'num_comments': post.num_comments,
            'created_utc': datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat(),
            'author': str(post.author) if post.author else '[deleted]',
            'subreddit': subreddit_name,
        })

        if len(posts) >= limit:
            break

    return posts
