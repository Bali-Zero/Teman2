"""
Preview Router - Serve HTML previews for Telegram approval articles
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preview", tags=["Preview"])

# Preview storage path (shared with scraper via volume or sync)
PREVIEW_DIR = Path("/app/data/previews")  # On Fly.io
LOCAL_PREVIEW_DIR = Path("data/previews")  # Local development


class PreviewUpload(BaseModel):
    """Payload for uploading HTML preview from scraper"""

    article_id: str
    html_content: str


@router.post("/upload")
async def upload_preview(payload: PreviewUpload):
    """
    Upload HTML preview from scraper (running locally on Mac).

    Called by scraper BEFORE sending Telegram message, so the preview
    link is ready when team clicks it.

    Example:
        POST /preview/upload
        {
            "article_id": "19d416944a15",
            "html_content": "<html>...</html>"
        }
    """
    try:
        # Use Fly.io path in production, local path in dev
        preview_dir = PREVIEW_DIR if PREVIEW_DIR.parent.exists() else LOCAL_PREVIEW_DIR
        preview_dir.mkdir(parents=True, exist_ok=True)

        preview_path = preview_dir / f"{payload.article_id}.html"

        # Add noindex meta tag if not present
        html_content = payload.html_content
        if "<head>" in html_content and 'name="robots"' not in html_content:
            html_content = html_content.replace(
                "<head>", '<head>\n<meta name="robots" content="noindex, nofollow">'
            )

        # Save HTML file
        preview_path.write_text(html_content, encoding="utf-8")

        preview_url = f"https://nuzantara-rag.fly.dev/preview/{payload.article_id}.html"

        logger.info(f"Preview uploaded: {payload.article_id} → {preview_path}")

        return JSONResponse(
            status_code=201,
            content={
                "status": "uploaded",
                "article_id": payload.article_id,
                "preview_url": preview_url,
                "file_size": len(html_content),
            },
        )
    except Exception as e:
        logger.error(f"Failed to upload preview {payload.article_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save preview: {str(e)}")


@router.get("/{article_id}.html", response_class=HTMLResponse)
async def get_preview(article_id: str):
    """
    Serve HTML preview for article.
    Used by Telegram messages to show full article with images.

    Example: https://nuzantara-rag.fly.dev/preview/19d416944a15.html
    """
    # Try Fly.io path first, then local
    preview_paths = [
        PREVIEW_DIR / f"{article_id}.html",
        LOCAL_PREVIEW_DIR / f"{article_id}.html",
    ]

    for preview_path in preview_paths:
        if preview_path.exists():
            try:
                html_content = preview_path.read_text(encoding="utf-8")

                # Add noindex meta tag to prevent search engine indexing
                if "<head>" in html_content and 'name="robots"' not in html_content:
                    html_content = html_content.replace(
                        "<head>", '<head>\n<meta name="robots" content="noindex, nofollow">'
                    )

                logger.info(f"Serving preview: {article_id}")
                return HTMLResponse(content=html_content, status_code=200)
            except Exception as e:
                logger.error(f"Error reading preview {article_id}: {e}")
                raise HTTPException(status_code=500, detail="Error reading preview")

    logger.warning(f"Preview not found: {article_id}")
    raise HTTPException(status_code=404, detail=f"Preview not found. Article ID: {article_id}")


@router.get("/", response_class=HTMLResponse)
async def preview_index():
    """List all available previews (dev only)"""
    html = "<h1>Preview Articles</h1><ul>"

    preview_dir = LOCAL_PREVIEW_DIR if LOCAL_PREVIEW_DIR.exists() else PREVIEW_DIR
    if preview_dir.exists():
        for preview_file in sorted(preview_dir.glob("*.html"), reverse=True):
            article_id = preview_file.stem
            html += f'<li><a href="/preview/{article_id}.html">{article_id}</a></li>'

    html += "</ul>"
    return HTMLResponse(content=html)
