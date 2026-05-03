"""Content Tools - 6 tools for article composition and newsletter management."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    @require_role("visa_specialist")
    async def compose_article(
        topic: str,
        style: str = "informative",
        target_length: str = "medium",
        data: Optional[dict] = None,
    ) -> dict:
        """
        Compose an AI-generated article on a topic.

        Args:
            topic: Article topic or headline
            style: Writing style (informative, alert, guide, analysis, news)
            target_length: Length (short=500w, medium=1000w, long=2000w)
            data: Optional structured data to include in the article

        Returns:
            Generated article with title, body, meta description, tags, SEO score.
        """
        payload: dict = {
            "topic": topic,
            "style": style,
            "target_length": target_length,
        }
        if data:
            payload["data"] = data
        return await _call(
            "/api/article-composer/compose", method="POST", json=payload
        )

    @mcp.tool()
    @require_role("visa_specialist")
    async def publish_article(article_id: str) -> dict:
        """
        Publish a composed article to the blog.

        Args:
            article_id: UUID of the article from compose_article

        Returns:
            Published article with public URL and publication timestamp.
        """
        return await _call(
            f"/api/article-composer/publish/{article_id}", method="POST"
        )

    @mcp.tool()
    async def list_articles(
        limit: int = 20, offset: int = 0, category: Optional[str] = None
    ) -> dict:
        """
        List published articles and news.

        Args:
            limit: Max results
            offset: Pagination offset
            category: Filter by category

        Returns:
            List of articles with title, date, category, views, URL.
        """
        params: dict = {"limit": limit, "offset": offset}
        if category:
            params["category"] = category
        return await _call("/api/news", params=params)

    @mcp.tool()
    async def get_article(article_id: str) -> dict:
        """
        Get full article content.

        Args:
            article_id: UUID of the article

        Returns:
            Complete article: title, body, author, date, tags, SEO metadata.
        """
        return await _call(f"/api/news/{article_id}")

    @mcp.tool()
    async def subscribe_newsletter(email: str, name: Optional[str] = None) -> dict:
        """
        Subscribe an email to the Bali Zero newsletter.

        Args:
            email: Subscriber email address
            name: Subscriber name (optional)

        Returns:
            Subscription record with confirmation status.
        """
        payload: dict = {"email": email}
        if name:
            payload["name"] = name
        return await _call(
            "/api/newsletter/subscribe", method="POST", json=payload
        )

    @mcp.tool()
    async def list_subscribers(limit: int = 50, offset: int = 0) -> dict:
        """
        List newsletter subscribers.

        Args:
            limit: Max results
            offset: Pagination offset

        Returns:
            List of subscribers with email, name, subscribed_at, status.
        """
        return await _call(
            "/api/newsletter/subscribers",
            params={"limit": limit, "offset": offset},
        )
