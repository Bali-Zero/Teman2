"""
Reddit Scraper
Uses PRAW (Python Reddit API Wrapper) to fetch posts from subreddits.
Requires: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars.
"""

import os
from datetime import datetime, timezone
from typing import List, Dict


def fetch_subreddit(
    subreddit_name: str,
    limit: int = 10,
    sort: str = 'new',
    min_score: int = 5,
    min_text_length: int = 50,
) -> List[Dict]:
    """Fetch posts from a subreddit using PRAW (read-only mode)."""
    import praw

    client_id = os.environ.get('REDDIT_CLIENT_ID', '')
    client_secret = os.environ.get('REDDIT_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        raise ValueError('REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars required')

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
