"""
Data export API.

Export articles and analytics in various formats.
"""

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.db.connection import db
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="export")

router = APIRouter(prefix="/export", tags=["export"])


class Exporter:
    """Export data in various formats."""

    async def export_articles(
        self,
        format: str = "json",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        category: str | None = None,
        source_id: str | None = None,
    ) -> StreamingResponse:
        """Export articles to specified format."""
        # Build query
        conditions = ["is_deleted = false OR is_deleted IS NULL"]
        params = []

        if start_date:
            conditions.append(f"created_at >= ${len(params) + 1}")
            params.append(start_date)

        if end_date:
            conditions.append(f"created_at <= ${len(params) + 1}")
            params.append(end_date)

        if category:
            conditions.append(f"category = ${len(params) + 1}")
            params.append(category)

        if source_id:
            conditions.append(f"source_id = ${len(params) + 1}")
            params.append(source_id)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT * FROM articles
            WHERE {where_clause}
            ORDER BY created_at DESC
        """

        articles = await db.fetch(query, *params)

        logger.info(
            f"Exporting {len(articles)} articles as {format}",
            action=LogAction.EXPORT,
            metadata={"format": format, "count": len(articles)},
        )

        if format == "json":
            return self._export_json(articles)
        elif format == "csv":
            return self._export_csv(articles)
        elif format == "rss":
            return self._export_rss(articles)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    def _export_json(self, articles: list) -> StreamingResponse:
        """Export as JSON."""
        data = [dict(row) for row in articles]
        content = json.dumps(data, default=str, indent=2)

        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=articles_{datetime.now():%Y%m%d}.json"
            },
        )

    def _export_csv(self, articles: list) -> StreamingResponse:
        """Export as CSV."""
        if not articles:
            return StreamingResponse(
                io.StringIO(""),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=articles_{datetime.now():%Y%m%d}.csv"
                },
            )

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=articles[0].keys())
        writer.writeheader()

        for article in articles:
            writer.writerow(dict(article))

        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=articles_{datetime.now():%Y%m%d}.csv"
            },
        )

    def _export_rss(self, articles: list) -> StreamingResponse:
        """Export as RSS feed."""
        rss_items = []

        for article in articles:
            rss_items.append(f"""
    <item>
        <title>{self._escape_xml(article.get("title", ""))}</title>
        <link>{article.get("url", "")}</link>
        <pubDate>{article.get("published_at", "")}</pubDate>
        <description>{self._escape_xml(article.get("summary", "") or "")}</description>
    </item>""")

        rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Bali Intel Export</title>
    <link>https://bali-intel.example.com</link>
    <description>Exported articles from Bali Intel Scraper</description>
    <lastBuildDate>{datetime.now().isoformat()}</lastBuildDate>
    {"".join(rss_items)}
</channel>
</rss>"""

        return StreamingResponse(
            io.StringIO(rss_content),
            media_type="application/rss+xml",
            headers={
                "Content-Disposition": f"attachment; filename=articles_{datetime.now():%Y%m%d}.rss"
            },
        )

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )


exporter = Exporter()


@router.get("/articles")
async def export_articles(
    format: str = Query("json", regex="^(json|csv|rss)$"),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    category: str | None = None,
    source_id: str | None = None,
):
    """Export articles in specified format."""
    return await exporter.export_articles(
        format=format,
        start_date=start_date,
        end_date=end_date,
        category=category,
        source_id=source_id,
    )


@router.get("/stats")
async def export_stats(format: str = Query("json", regex="^(json|csv)$")):
    """Export statistics."""
    # Get basic stats
    stats = await db.fetchrow("""
        SELECT 
            COUNT(*) as total_articles,
            COUNT(DISTINCT source_id) as total_sources,
            MAX(created_at) as latest_article
        FROM articles
        WHERE is_deleted = false OR is_deleted IS NULL
    """)

    if format == "json":
        return dict(stats)
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=stats.keys())
        writer.writeheader()
        writer.writerow(dict(stats))
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=stats_{datetime.now():%Y%m%d}.csv"
            },
        )


__all__ = ["router", "exporter"]
