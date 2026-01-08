#!/usr/bin/env python3
"""
Telegram Article Approval System
=================================

Sends article previews to Telegram for manual approval before publishing.

Features:
- HTML preview generation
- Telegram notification with inline buttons
- Approval/rejection tracking
- Webhook for Telegram callbacks

Setup:
1. Create a Telegram bot via @BotFather
2. Get your chat ID from @userinfobot
3. Set environment variables:
   - TELEGRAM_BOT_TOKEN=your_bot_token
   - TELEGRAM_CHAT_ID=your_chat_id

Author: BaliZero Team
"""

import os
import json
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import aiohttp
from loguru import logger

# Telegram API base URL
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


@dataclass
class PendingArticle:
    """Article pending approval"""

    article_id: str
    title: str
    category: str
    source: str
    source_url: str
    preview_html: str
    preview_url: str
    seo_metadata: dict
    enriched_content: str
    image_url: str
    created_at: str
    relevance_score: int = 0
    published_at: Optional[str] = None
    status: str = "pending"  # pending, approved, rejected
    approved_at: Optional[str] = None
    telegram_message_id: Optional[int] = None


class TelegramApproval:
    """
    Telegram-based article approval system.

    Sends article previews to Telegram and waits for approval
    before publishing to the API.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_ids: Optional[list[str]] = None,
        preview_base_url: str = "https://nuzantara-rag.fly.dev/preview",
    ):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")

        # Support multiple chat IDs for team notifications
        if chat_ids:
            self.chat_ids = chat_ids
        else:
            # Get from environment - comma-separated for multiple
            env_chat_ids = os.environ.get(
                "TELEGRAM_APPROVAL_CHAT_ID"
            ) or os.environ.get("TELEGRAM_CHAT_ID", "")
            self.chat_ids = [
                cid.strip() for cid in env_chat_ids.split(",") if cid.strip()
            ]

        self.preview_base_url = preview_base_url

        # Storage for pending articles
        self.pending_dir = Path("data/pending_articles")
        self.pending_dir.mkdir(parents=True, exist_ok=True)

        # HTML preview directory
        self.preview_dir = Path("data/previews")
        self.preview_dir.mkdir(parents=True, exist_ok=True)

        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set - notifications disabled")
        if not self.chat_ids:
            logger.warning("TELEGRAM_APPROVAL_CHAT_ID not set - notifications disabled")
        else:
            logger.info(
                f"Telegram notifications configured for {len(self.chat_ids)} recipient(s)"
            )

    def _generate_article_id(self, title: str, source_url: str) -> str:
        """Generate unique article ID"""
        content = f"{title}:{source_url}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def generate_html_preview(self, article: dict, seo_metadata: dict) -> str:
        """
        Generate HTML preview as a formatted article (like it would appear on the website).

        Returns the HTML string for preview.
        """
        import re

        title = seo_metadata.get("title", article.get("title", "Untitled")).replace(
            " | BaliZero", ""
        )
        description = seo_metadata.get("meta_description", "")
        content = article.get("enriched_content", article.get("content", ""))
        keywords = seo_metadata.get("keywords", [])
        faq_items = seo_metadata.get("faq_items", [])
        image_url = article.get("image_url", "")
        category = article.get("category", "general")
        source = article.get("source", "Unknown")
        source_url = article.get("source_url", "")
        reading_time = seo_metadata.get("reading_time_minutes", 5)
        published_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

        # Convert markdown-style content to HTML
        def markdown_to_html(text):
            # Headers
            text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
            text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
            text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)
            # Bold
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            # Italic
            text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
            # Lists
            text = re.sub(r"^- (.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
            text = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\g<0></ul>", text)
            # Paragraphs
            paragraphs = text.split("\n\n")
            formatted = []
            for p in paragraphs:
                p = p.strip()
                if p and not p.startswith("<"):
                    formatted.append(f"<p>{p}</p>")
                elif p:
                    formatted.append(p)
            return "\n".join(formatted)

        article_html = markdown_to_html(content)

        # Generate FAQ HTML
        faq_html = ""
        if faq_items:
            faq_html = (
                '<section class="faq-section"><h2>Frequently Asked Questions</h2>'
            )
            for faq in faq_items:
                faq_html += f"""
                <div class="faq-item">
                    <h3>{faq["question"]}</h3>
                    <p>{faq["answer"]}</p>
                </div>
                """
            faq_html += "</section>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | BaliZero</title>
    <meta name="description" content="{description}">
    <meta name="keywords" content="{", ".join(keywords)}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.7;
            min-height: 100vh;
        }}

        /* Approval Banner */
        .approval-banner {{
            background: linear-gradient(90deg, #f39c12 0%, #e74c3c 100%);
            color: white;
            text-align: center;
            padding: 12px 20px;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        /* Header */
        .site-header {{
            background: white;
            backdrop-filter: blur(10px);
            padding: 15px 0;
            border-bottom: 1px solid #e0e0e0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        .header-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .logo {{
            font-size: 24px;
            font-weight: 700;
            color: #e67e22;
            text-decoration: none;
        }}
        .logo span {{ color: #2c3e50; }}

        /* Article Container */
        .article-container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px 80px;
            background: white;
            min-height: calc(100vh - 200px);
        }}

        /* Category Badge */
        .category-badge {{
            display: inline-block;
            background: #fff3e0;
            color: #e67e22;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 20px;
        }}

        /* Article Title */
        .article-title {{
            font-size: clamp(28px, 5vw, 42px);
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 20px;
            color: #1a1a2e;
        }}

        /* Meta Info */
        .article-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
            padding-bottom: 30px;
            border-bottom: 1px solid #eee;
        }}
        .meta-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .meta-item svg {{
            width: 16px;
            height: 16px;
            opacity: 0.6;
        }}

        /* Cover Image */
        .cover-image {{
            width: 100%;
            height: auto;
            border-radius: 16px;
            margin-bottom: 40px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        }}

        /* Article Content */
        .article-content {{
            font-size: 17px;
            color: #444;
        }}
        .article-content h1 {{
            font-size: 32px;
            color: #1a1a2e;
            margin: 40px 0 20px;
        }}
        .article-content h2 {{
            font-size: 26px;
            color: #1a1a2e;
            margin: 35px 0 18px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
        .article-content h3 {{
            font-size: 20px;
            color: #e67e22;
            margin: 25px 0 12px;
        }}
        .article-content p {{
            margin-bottom: 20px;
        }}
        .article-content ul {{
            margin: 20px 0;
            padding-left: 25px;
        }}
        .article-content li {{
            margin-bottom: 10px;
        }}
        .article-content strong {{
            color: #1a1a2e;
        }}
        .article-content a {{
            color: #e67e22;
            text-decoration: none;
        }}
        .article-content a:hover {{
            text-decoration: underline;
        }}

        /* FAQ Section */
        .faq-section {{
            margin-top: 50px;
            padding-top: 40px;
            border-top: 2px solid #fff3e0;
        }}
        .faq-section h2 {{
            color: #e67e22;
            margin-bottom: 30px;
        }}
        .faq-item {{
            background: #fafafa;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 15px;
            border: 1px solid #eee;
        }}
        .faq-item h3 {{
            color: #1a1a2e;
            font-size: 18px;
            margin-bottom: 12px;
        }}
        .faq-item p {{
            color: #666;
            font-size: 15px;
        }}

        /* Source Attribution */
        .source-box {{
            background: #fafafa;
            border-left: 4px solid #e67e22;
            padding: 20px 25px;
            margin-top: 40px;
            border-radius: 0 12px 12px 0;
        }}
        .source-box p {{
            color: #666;
            font-size: 14px;
            margin: 0;
        }}
        .source-box a {{
            color: #e67e22;
        }}

        /* Tags */
        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 40px;
            padding-top: 30px;
            border-top: 1px solid #eee;
        }}
        .tag {{
            background: #f5f5f5;
            color: #666;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            border: 1px solid #e0e0e0;
        }}

        /* Footer */
        .site-footer {{
            background: #1a1a2e;
            padding: 40px 20px;
            text-align: center;
            color: #888;
            font-size: 14px;
        }}

        @media (max-width: 600px) {{
            .article-container {{ padding: 20px 15px 60px; }}
            .article-title {{ font-size: 24px; }}
            .article-content {{ font-size: 16px; }}
        }}
    </style>
</head>
<body>
    <!-- Approval Banner -->
    <div class="approval-banner">
        ⚠️ PREVIEW - Pending Approval - This article is not yet published
    </div>

    <!-- Header -->
    <header class="site-header">
        <div class="header-content">
            <a href="https://balizero.com" class="logo">Bali<span>Zero</span></a>
            <span style="color: #888; font-size: 14px;">News & Insights</span>
        </div>
    </header>

    <!-- Article -->
    <article class="article-container">
        <!-- Category -->
        <span class="category-badge">{category}</span>

        <!-- Title -->
        <h1 class="article-title">{title}</h1>

        <!-- Meta -->
        <div class="article-meta">
            <span class="meta-item">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {published_date}
            </span>
            <span class="meta-item">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {reading_time} min read
            </span>
            <span class="meta-item">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9.5a2 2 0 00-2-2h-2" />
                </svg>
                {source}
            </span>
        </div>

        <!-- Cover Image -->
        {f'<img src="{image_url}" alt="{title}" class="cover-image">' if image_url else ""}

        <!-- Content -->
        <div class="article-content">
            {article_html}
        </div>

        <!-- FAQ -->
        {faq_html}

        <!-- Source -->
        <div class="source-box">
            <p>📰 Source: <a href="{source_url}" target="_blank" rel="noopener">{source}</a></p>
        </div>

        <!-- Tags -->
        <div class="tags">
            {"".join(f'<span class="tag">{kw}</span>' for kw in keywords[:8])}
        </div>
    </article>

    <!-- Footer -->
    <footer class="site-footer">
        <p>© 2026 BaliZero. Indonesia's trusted guide for expats and investors.</p>
    </footer>
</body>
</html>"""

        return html

    async def upload_preview_to_backend(
        self,
        article_id: str,
        html_content: str,
        backend_url: str = "https://nuzantara-rag.fly.dev",
    ) -> Optional[str]:
        """
        Upload HTML preview to backend server.

        Called BEFORE sending Telegram message, so the preview link
        is ready when team clicks it.

        Returns preview URL if successful, None otherwise.
        """
        try:
            import aiohttp

            upload_url = f"{backend_url}/preview/upload"
            payload = {
                "article_id": article_id,
                "html_content": html_content,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    upload_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 201:
                        result = await resp.json()
                        preview_url = result.get("preview_url")
                        logger.success(f"Preview uploaded to backend: {preview_url}")
                        return preview_url
                    else:
                        error = await resp.text()
                        logger.error(f"Failed to upload preview to backend: {error}")
                        return None
        except Exception as e:
            logger.error(f"Error uploading preview to backend: {e}")
            return None

    def escape_markdown(self, text: str) -> str:
        """
        Escape special Markdown characters for Telegram.

        Telegram MarkdownV2 requires escaping: _*[]()~`>#+-=|{}.!
        We use simpler Markdown mode which requires escaping: _*[]()
        """
        if not text:
            return ""

        # Escape special characters that break Telegram Markdown parsing
        escape_chars = ["_", "*", "[", "]", "(", ")"]
        for char in escape_chars:
            text = text.replace(char, f"\\{char}")

        return text

    async def send_telegram_notification(
        self, article: PendingArticle
    ) -> Optional[int]:
        """
        Send article notification to Telegram with approve/reject buttons.

        Sends to all configured chat IDs (team notification).
        Returns the first message ID if successful.
        """
        if not self.bot_token or not self.chat_ids:
            logger.warning("Telegram not configured, skipping notification")
            return None

        # Format published date
        pub_date = "Unknown"
        if article.published_at:
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
                pub_date = dt.strftime("%Y-%m-%d")
            except:
                pub_date = (
                    article.published_at[:10] if article.published_at else "Unknown"
                )

        # Full enriched content (Telegram limit: 4096 chars, leave room for formatting)
        max_content_length = 3500
        if len(article.enriched_content) > max_content_length:
            content_preview = (
                article.enriched_content[:max_content_length]
                + "\n\n[...continua su Intelligence/News Room]"
            )
        else:
            content_preview = article.enriched_content

        # Escape content for Telegram Markdown
        escaped_content = self.escape_markdown(content_preview)
        escaped_title = self.escape_markdown(article.title)
        escaped_keywords = self.escape_markdown(
            ", ".join(article.seo_metadata.get("keywords", [])[:5])
        )
        escaped_entities = self.escape_markdown(
            ", ".join(article.seo_metadata.get("key_entities", [])[:5])
        )

        # Format message (English)
        message = f"""📰 *New Article Ready for Review*

*{escaped_title}*

📊 *Score:* `{article.relevance_score}/100` | 📅 *Published:* {pub_date}
📂 *Category:* `{article.category.upper()}`
📰 *Source:* [{article.source}]({article.source_url})

✨ *Claude Enriched Preview:*
{escaped_content}

🔑 *Keywords:* {escaped_keywords}
🏷️ *Entities:* {escaped_entities}

_Article ID: `{article.article_id}`_"""

        # Inline keyboard for approve/reject/changes
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Approve",
                        "callback_data": f"approve:{article.article_id}",
                    },
                    {
                        "text": "❌ Reject",
                        "callback_data": f"reject:{article.article_id}",
                    },
                ],
                [
                    {
                        "text": "✏️ Request Changes",
                        "callback_data": f"changes:{article.article_id}",
                    }
                ],
                [{"text": "🔗 View Source", "url": article.source_url}],
            ]
        }

        first_message_id = None

        try:
            async with aiohttp.ClientSession() as session:
                # Send to all configured chat IDs
                for chat_id in self.chat_ids:
                    # Check if we have a cover image to send
                    if article.image_url and Path(article.image_url).exists():
                        # Send as photo with caption
                        url = TELEGRAM_API.format(
                            token=self.bot_token, method="sendPhoto"
                        )

                        # Prepare multipart form data
                        data = aiohttp.FormData()
                        data.add_field("chat_id", str(chat_id))
                        data.add_field("caption", message)
                        data.add_field("parse_mode", "Markdown")
                        data.add_field("reply_markup", json.dumps(keyboard))

                        # Add image file
                        with open(article.image_url, "rb") as img_file:
                            data.add_field(
                                "photo",
                                img_file,
                                filename=Path(article.image_url).name,
                                content_type="image/png",
                            )

                            async with session.post(url, data=data) as resp:
                                if resp.status == 200:
                                    result = await resp.json()
                                    message_id = result.get("result", {}).get(
                                        "message_id"
                                    )
                                    logger.success(
                                        f"Telegram notification sent to {chat_id}: message_id={message_id} (with image)"
                                    )
                                    if first_message_id is None:
                                        first_message_id = message_id
                                else:
                                    error = await resp.text()
                                    logger.error(
                                        f"Telegram API error for {chat_id}: {error}"
                                    )
                    else:
                        # Send as text message (no image)
                        url = TELEGRAM_API.format(
                            token=self.bot_token, method="sendMessage"
                        )
                        payload = {
                            "chat_id": chat_id,
                            "text": message,
                            "parse_mode": "Markdown",
                            "disable_web_page_preview": False,
                            "reply_markup": json.dumps(keyboard),
                        }

                        async with session.post(url, json=payload) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                message_id = result.get("result", {}).get("message_id")
                                logger.success(
                                    f"Telegram notification sent to {chat_id}: message_id={message_id}"
                                )
                                if first_message_id is None:
                                    first_message_id = message_id
                            else:
                                error = await resp.text()
                                logger.error(
                                    f"Telegram API error for {chat_id}: {error}"
                                )

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

        return first_message_id

    async def submit_for_approval(
        self, article: dict, seo_metadata: dict, enriched_content: str
    ) -> PendingArticle:
        """
        Submit an article for approval.

        1. Generate HTML preview
        2. Save pending article
        3. Send Telegram notification

        Returns the PendingArticle object.
        """
        title = article.get("title", "Untitled")
        source_url = article.get("source_url", "")

        # Generate article ID
        article_id = self._generate_article_id(title, source_url)

        # Generate HTML preview
        html_preview = self.generate_html_preview(article, seo_metadata)

        # Save HTML file locally
        preview_filename = f"{article_id}.html"
        preview_path = self.preview_dir / preview_filename
        preview_path.write_text(html_preview, encoding="utf-8")

        # Upload HTML preview to backend (so link is ready for Telegram)
        uploaded_preview_url = await self.upload_preview_to_backend(
            article_id, html_preview
        )
        preview_url = (
            uploaded_preview_url or f"{self.preview_base_url}/{preview_filename}"
        )

        # Create pending article
        pending = PendingArticle(
            article_id=article_id,
            title=title,
            category=article.get("category", "general"),
            source=article.get("source", "Unknown"),
            source_url=source_url,
            preview_html=str(preview_path),
            preview_url=preview_url,
            seo_metadata=seo_metadata,
            enriched_content=enriched_content,
            image_url=article.get("image_url", ""),
            created_at=datetime.now(timezone.utc).isoformat(),
            relevance_score=article.get("relevance_score", 0),
            published_at=article.get("published_at"),
        )

        # Save pending article JSON
        pending_path = self.pending_dir / f"{article_id}.json"
        pending_path.write_text(
            json.dumps(asdict(pending), indent=2, ensure_ascii=False)
        )

        logger.info(f"Article submitted for approval: {article_id}")
        logger.info(f"HTML preview: {preview_path}")

        # Send Telegram notification
        message_id = await self.send_telegram_notification(pending)
        if message_id:
            pending.telegram_message_id = message_id
            # Update JSON with message ID
            pending_path.write_text(
                json.dumps(asdict(pending), indent=2, ensure_ascii=False)
            )

        return pending

    def get_pending_article(self, article_id: str) -> Optional[PendingArticle]:
        """Get a pending article by ID"""
        pending_path = self.pending_dir / f"{article_id}.json"
        if pending_path.exists():
            data = json.loads(pending_path.read_text())
            return PendingArticle(**data)
        return None

    def approve_article(self, article_id: str) -> bool:
        """Mark an article as approved"""
        pending = self.get_pending_article(article_id)
        if pending:
            pending.status = "approved"
            pending.approved_at = datetime.now(timezone.utc).isoformat()
            pending_path = self.pending_dir / f"{article_id}.json"
            pending_path.write_text(
                json.dumps(asdict(pending), indent=2, ensure_ascii=False)
            )
            logger.success(f"Article approved: {article_id}")
            return True
        return False

    def reject_article(self, article_id: str) -> bool:
        """Mark an article as rejected"""
        pending = self.get_pending_article(article_id)
        if pending:
            pending.status = "rejected"
            pending_path = self.pending_dir / f"{article_id}.json"
            pending_path.write_text(
                json.dumps(asdict(pending), indent=2, ensure_ascii=False)
            )
            logger.info(f"Article rejected: {article_id}")
            return True
        return False

    def list_pending(self) -> list[PendingArticle]:
        """List all pending articles"""
        pending_articles = []
        for path in self.pending_dir.glob("*.json"):
            data = json.loads(path.read_text())
            article = PendingArticle(**data)
            if article.status == "pending":
                pending_articles.append(article)
        return pending_articles

    def list_approved(self) -> list[PendingArticle]:
        """List all approved articles ready for publishing"""
        approved_articles = []
        for path in self.pending_dir.glob("*.json"):
            data = json.loads(path.read_text())
            article = PendingArticle(**data)
            if article.status == "approved":
                approved_articles.append(article)
        return approved_articles


async def handle_telegram_callback(
    update: dict, approval_system: TelegramApproval
) -> str:
    """
    Handle Telegram callback query (button press).

    This would be called from a webhook or polling bot.
    """
    callback_query = update.get("callback_query", {})
    data = callback_query.get("data", "")
    chat_id = callback_query.get("from", {}).get("id")

    if ":" not in data:
        return "Invalid callback data"

    action, article_id = data.split(":", 1)

    if action == "approve":
        if approval_system.approve_article(article_id):
            return f"✅ Article {article_id} approved and queued for publishing!"
        return f"❌ Article {article_id} not found"

    elif action == "reject":
        if approval_system.reject_article(article_id):
            return f"🗑️ Article {article_id} rejected and discarded"
        return f"❌ Article {article_id} not found"

    elif action == "changes":
        # Mark as pending changes and prompt for feedback
        pending = approval_system.get_pending_article(article_id)
        if pending:
            pending.status = "changes_requested"
            pending_path = approval_system.pending_dir / f"{article_id}.json"
            pending_path.write_text(
                json.dumps(asdict(pending), indent=2, ensure_ascii=False)
            )
            return f"✏️ Please reply to this message with your requested changes for article {article_id}"
        return f"❌ Article {article_id} not found"

    return "Unknown action"


# CLI for testing
if __name__ == "__main__":

    async def test_approval():
        approval = TelegramApproval(
            preview_base_url="file:///Users/antonellosiano/Desktop/nuzantara/apps/bali-intel-scraper/scripts/data/previews"
        )

        # Test article with real Unsplash image
        test_article = {
            "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
            "content": "The Indonesian government announced a groundbreaking policy...",
            "enriched_content": """# Indonesia Extends Digital Nomad Visa to 5 Years

## Executive Summary

The Indonesian government has officially announced an extension of the Digital Nomad Visa (E33G) validity period from 1 year to 5 years, making Indonesia one of the most attractive destinations for remote workers in Southeast Asia.

## Key Changes

- **Validity**: Extended from 1 year to 5 years
- **Income requirement**: $2,000 USD/month minimum
- **Work authorization**: Remote work for foreign companies permitted
- **Tax status**: Not subject to Indonesian income tax if staying less than 183 days/year

## Impact for Digital Nomads

This policy change positions Bali and other Indonesian destinations as top choices for the growing digital nomad community. The extended visa reduces administrative burden and provides long-term stability for remote workers.

## How to Apply

Applications can be submitted through Indonesian embassies worldwide or converted from a tourist visa within Indonesia. Processing time is approximately 4-6 weeks.

---
*Source: Ministry of Law and Human Rights*
""",
            "category": "immigration",
            "source": "Jakarta Post",
            "source_url": "https://example.com/nomad-visa",
            "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1200&h=630&fit=crop",
        }

        test_seo = {
            "title": "Indonesia Extends Digital Nomad Visa to 5 Years | BaliZero",
            "meta_description": "Indonesia extends Digital Nomad Visa E33G from 1 to 5 years. Learn about requirements, costs, and how to apply for this groundbreaking visa.",
            "keywords": [
                "digital nomad visa",
                "E33G",
                "Indonesia visa",
                "remote work",
                "Bali",
                "BaliZero",
            ],
            "key_entities": [
                "Indonesia",
                "Bali",
                "Ministry of Law",
                "Digital Nomad Visa",
                "E33G",
            ],
            "faq_items": [
                {
                    "question": "How long is the digital nomad visa valid?",
                    "answer": "The E33G Digital Nomad Visa is now valid for up to 5 years.",
                },
                {
                    "question": "What is the income requirement?",
                    "answer": "You need to prove a minimum monthly income of $2,000 USD.",
                },
            ],
            "canonical_url": "https://balizero.com/news/immigration/digital-nomad-visa-extended",
            "reading_time_minutes": 4,
            "tldr_summary": "Indonesia has extended the Digital Nomad Visa (E33G) from 1 year to 5 years, requiring $2,000/month income and allowing remote work for foreign companies.",
            "schema_json_ld": '{"@context": "https://schema.org", "@type": "NewsArticle", "headline": "Indonesia Extends Digital Nomad Visa"}',
        }

        # Submit for approval
        pending = await approval.submit_for_approval(
            article=test_article,
            seo_metadata=test_seo,
            enriched_content=test_article["enriched_content"],
        )

        print("\n✅ Article submitted for approval!")
        print(f"   ID: {pending.article_id}")
        print(f"   HTML Preview: {pending.preview_html}")
        print(f"   Preview URL: {pending.preview_url}")

        if pending.telegram_message_id:
            print(f"   Telegram Message ID: {pending.telegram_message_id}")
        else:
            print("   ⚠️ Telegram notification not sent (check bot token)")

        # List pending
        print(f"\n📋 Pending articles: {len(approval.list_pending())}")

    asyncio.run(test_approval())
