#!/usr/bin/env python3
"""
BALIZERO ARTICLE PREVIEW GENERATOR
===================================

Generates article previews that look EXACTLY like balizero.com

Features:
- Dark theme matching production site
- 21:9 cover image aspect ratio
- Category-specific accent colors
- Table of Contents
- Reading progress bar
- FAQ section with schema.org markup
- Mobile responsive

The preview URL is shared with:
1. Telegram approvers
2. News Room dashboard (/dashboard/intelligence)

Preview pages are served at:
https://bali-intel-scraper.fly.dev/preview/{article_id}

Author: BaliZero Team
"""

import re
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from loguru import logger


# Category colors matching balizero.com
CATEGORY_COLORS = {
    "immigration": {"primary": "#2251ff", "bg": "rgba(34, 81, 255, 0.1)", "name": "Immigration"},
    "business": {"primary": "#22c55e", "bg": "rgba(34, 197, 94, 0.1)", "name": "Business"},
    "tax": {"primary": "#f59e0b", "bg": "rgba(245, 158, 11, 0.1)", "name": "Tax & Legal"},
    "tax-legal": {"primary": "#f59e0b", "bg": "rgba(245, 158, 11, 0.1)", "name": "Tax & Legal"},
    "property": {"primary": "#e85c41", "bg": "rgba(232, 92, 65, 0.1)", "name": "Property"},
    "lifestyle": {"primary": "#7c3aed", "bg": "rgba(124, 58, 237, 0.1)", "name": "Lifestyle"},
    "tech": {"primary": "#ec4899", "bg": "rgba(236, 72, 153, 0.1)", "name": "Tech"},
    "regulation": {"primary": "#f59e0b", "bg": "rgba(245, 158, 11, 0.1)", "name": "Regulation"},
    "investment": {"primary": "#22c55e", "bg": "rgba(34, 197, 94, 0.1)", "name": "Investment"},
    "general": {"primary": "#2251ff", "bg": "rgba(34, 81, 255, 0.1)", "name": "News"},
}


@dataclass
class PreviewArticle:
    """Article data for preview generation"""
    article_id: str
    title: str
    subtitle: str
    content: str  # HTML or Markdown
    category: str
    source: str
    source_url: str
    cover_image: str
    published_at: str
    reading_time: int
    keywords: List[str]
    key_entities: List[str]
    faq_items: List[Dict]
    tldr_summary: str
    schema_json_ld: str
    relevance_score: int = 0
    author: str = "BaliZero Intelligence"
    reviewed_by: Optional[str] = None  # Human reviewer name for E-E-A-T


class BaliZeroPreviewGenerator:
    """
    Generates article previews matching balizero.com design.

    Preview pages are stored locally and served via the scraper API.
    """

    def __init__(self, output_dir: str = "data/previews"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_category_style(self, category: str) -> Dict:
        """Get category-specific colors"""
        cat_key = category.lower().replace(" ", "-")
        return CATEGORY_COLORS.get(cat_key, CATEGORY_COLORS["general"])

    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown to HTML with proper styling"""
        if not text:
            return ""

        # Headers - add IDs for TOC linking
        text = re.sub(
            r"^### (.+)$",
            lambda m: f'<h3 id="{self._slugify(m.group(1))}">{m.group(1)}</h3>',
            text, flags=re.MULTILINE
        )
        text = re.sub(
            r"^## (.+)$",
            lambda m: f'<h2 id="{self._slugify(m.group(1))}">{m.group(1)}</h2>',
            text, flags=re.MULTILINE
        )
        text = re.sub(
            r"^# (.+)$",
            lambda m: f'<h1 id="{self._slugify(m.group(1))}">{m.group(1)}</h1>',
            text, flags=re.MULTILINE
        )

        # Bold and italic
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

        # Lists
        text = re.sub(r"^- (.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
        text = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\g<0></ul>", text)

        # Links
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)

        # Horizontal rules
        text = re.sub(r"^---+$", r"<hr>", text, flags=re.MULTILINE)

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

    def _slugify(self, text: str) -> str:
        """Create URL-friendly slug from text"""
        slug = text.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        return slug.strip("-")[:50]

    def _generate_tldr_html(self, tldr_summary: str) -> str:
        """Generate TL;DR HTML box (separate method to handle emoji in f-string)"""
        if not tldr_summary:
            return ""
        # Use HTML entity for lightning emoji to avoid f-string issues
        return f'''
        <div class="tldr-box">
            <div class="tldr-label">&#9889; TL;DR</div>
            <p class="tldr-text">{tldr_summary}</p>
        </div>
        '''

    def _generate_cover_image_html(self, cover_image: str, title: str) -> str:
        """Generate cover image HTML (separate method to avoid nested f-string)"""
        if not cover_image:
            return ""
        return f'''
        <div class="cover-image-container">
            <img src="{cover_image}" alt="{title}" class="cover-image">
        </div>
        '''

    def _extract_headings(self, content: str) -> List[Dict]:
        """Extract headings for Table of Contents"""
        headings = []

        # Match both markdown and HTML headings
        md_pattern = r"^(#{1,3})\s+(.+)$"
        html_pattern = r"<h([123])[^>]*>([^<]+)</h\1>"

        for match in re.finditer(md_pattern, content, re.MULTILINE):
            level = len(match.group(1))
            text = match.group(2).strip()
            headings.append({
                "level": level,
                "text": text,
                "id": self._slugify(text)
            })

        for match in re.finditer(html_pattern, content):
            level = int(match.group(1))
            text = match.group(2).strip()
            if not any(h["text"] == text for h in headings):
                headings.append({
                    "level": level,
                    "text": text,
                    "id": self._slugify(text)
                })

        return headings

    def generate_preview(self, article: PreviewArticle) -> str:
        """
        Generate full HTML preview page matching balizero.com design.

        Returns the HTML content.
        """
        cat_style = self._get_category_style(article.category)
        headings = self._extract_headings(article.content)
        article_html = self._markdown_to_html(article.content)

        # Format date
        try:
            dt = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
            formatted_date = dt.strftime("%B %d, %Y")
        except:
            formatted_date = article.published_at[:10] if article.published_at else "Today"

        # Generate TOC HTML
        toc_html = ""
        if headings:
            toc_items = []
            for h in headings:
                indent = "ml-4" if h["level"] > 2 else ""
                toc_items.append(
                    f'<a href="#{h["id"]}" class="toc-link {indent}">{h["text"]}</a>'
                )
            toc_html = "\n".join(toc_items)

        # Generate FAQ HTML
        faq_html = ""
        if article.faq_items:
            faq_items_html = ""
            for faq in article.faq_items:
                faq_items_html += f'''
                <div class="faq-item">
                    <h3 class="faq-question">{faq.get("question", "")}</h3>
                    <p class="faq-answer">{faq.get("answer", "")}</p>
                </div>
                '''
            faq_html = f'''
            <section class="faq-section">
                <h2>Frequently Asked Questions</h2>
                {faq_items_html}
            </section>
            '''

        # Keywords/tags HTML
        tags_html = "".join(
            f'<span class="tag">{kw}</span>'
            for kw in article.keywords[:8]
        )

        # Entities HTML
        entities_html = "".join(
            f'<span class="entity">{ent}</span>'
            for ent in article.key_entities[:6]
        )

        # Human review badge
        review_badge = ""
        if article.reviewed_by:
            review_badge = f'''
            <div class="review-badge">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                Reviewed by {article.reviewed_by}
            </div>
            '''

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article.title} | BaliZero Preview</title>
    <meta name="robots" content="noindex, nofollow">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">

    <!-- Schema.org JSON-LD -->
    <script type="application/ld+json">
    {article.schema_json_ld}
    </script>

    <style>
        :root {{
            --bg-primary: #0c1f3a;
            --bg-secondary: #0a1f3a;
            --bg-tertiary: #031219;
            --accent: {cat_style["primary"]};
            --accent-bg: {cat_style["bg"]};
            --text-primary: rgba(255, 255, 255, 1);
            --text-secondary: rgba(255, 255, 255, 0.8);
            --text-muted: rgba(255, 255, 255, 0.5);
            --border: rgba(255, 255, 255, 0.1);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-secondary);
            line-height: 1.7;
            min-height: 100vh;
        }}

        /* Reading Progress Bar */
        .progress-bar {{
            position: fixed;
            top: 0;
            left: 0;
            width: 0%;
            height: 3px;
            background: linear-gradient(90deg, #7c3aed, #ec4899);
            z-index: 1000;
            transition: width 0.1s ease;
        }}

        /* Preview Banner */
        .preview-banner {{
            background: linear-gradient(90deg, var(--accent), #ec4899);
            color: white;
            text-align: center;
            padding: 14px 20px;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 999;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }}
        .preview-banner svg {{
            width: 20px;
            height: 20px;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .preview-actions {{
            display: flex;
            gap: 10px;
            margin-left: 20px;
        }}
        .preview-btn {{
            padding: 6px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }}
        .preview-btn.approve {{
            background: white;
            color: #22c55e;
        }}
        .preview-btn.reject {{
            background: rgba(255,255,255,0.2);
            color: white;
        }}
        .preview-btn:hover {{
            transform: scale(1.05);
        }}

        /* Header */
        .site-header {{
            background: var(--bg-secondary);
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
        }}
        .header-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .logo {{
            font-family: 'Playfair Display', serif;
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
            text-decoration: none;
        }}
        .logo span {{ color: var(--accent); }}
        .nav-links {{
            display: flex;
            gap: 24px;
        }}
        .nav-link {{
            color: var(--text-muted);
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: color 0.2s;
        }}
        .nav-link:hover {{ color: var(--text-primary); }}

        /* Main Layout */
        .main-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 24px;
            display: grid;
            grid-template-columns: 220px 1fr 280px;
            gap: 40px;
        }}
        @media (max-width: 1024px) {{
            .main-container {{
                grid-template-columns: 1fr;
            }}
            .sidebar-left, .sidebar-right {{
                display: none;
            }}
        }}

        /* Sidebar Left - TOC */
        .sidebar-left {{
            position: sticky;
            top: 100px;
            height: fit-content;
        }}
        .toc-container {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid var(--border);
        }}
        .toc-title {{
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 16px;
        }}
        .toc-link {{
            display: block;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 14px;
            padding: 8px 0;
            border-left: 2px solid transparent;
            padding-left: 12px;
            margin-left: -12px;
            transition: all 0.2s;
        }}
        .toc-link:hover {{
            color: var(--text-primary);
            border-left-color: var(--accent);
        }}
        .toc-link.ml-4 {{
            margin-left: 4px;
            font-size: 13px;
        }}

        /* Article Content */
        .article-container {{
            max-width: 720px;
        }}

        /* Category Badge */
        .category-badge {{
            display: inline-block;
            background: var(--accent-bg);
            color: var(--accent);
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
            font-family: 'Playfair Display', serif;
            font-size: clamp(32px, 5vw, 48px);
            font-weight: 700;
            line-height: 1.15;
            margin-bottom: 16px;
            color: var(--text-primary);
        }}

        /* Subtitle */
        .article-subtitle {{
            font-size: 20px;
            color: var(--text-muted);
            margin-bottom: 24px;
            line-height: 1.5;
        }}

        /* Meta Info */
        .article-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            color: var(--text-muted);
            font-size: 14px;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}
        .meta-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .meta-item svg {{
            width: 16px;
            height: 16px;
            opacity: 0.6;
        }}

        /* Score Badge */
        .score-badge {{
            background: var(--accent-bg);
            color: var(--accent);
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 13px;
        }}

        /* Review Badge */
        .review-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(34, 197, 94, 0.1);
            color: #22c55e;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}

        /* Cover Image */
        .cover-image-container {{
            position: relative;
            width: 100%;
            aspect-ratio: 21/9;
            border-radius: 16px;
            overflow: hidden;
            margin-bottom: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        }}
        .cover-image {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        /* TL;DR Box */
        .tldr-box {{
            background: var(--accent-bg);
            border-left: 4px solid var(--accent);
            padding: 20px 24px;
            border-radius: 0 12px 12px 0;
            margin-bottom: 32px;
        }}
        .tldr-label {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--accent);
            margin-bottom: 8px;
        }}
        .tldr-text {{
            color: var(--text-secondary);
            font-size: 15px;
            line-height: 1.6;
        }}

        /* Article Content */
        .article-content {{
            font-size: 17px;
            color: var(--text-secondary);
        }}
        .article-content h1 {{
            font-family: 'Playfair Display', serif;
            font-size: 32px;
            color: var(--text-primary);
            margin: 48px 0 24px;
            scroll-margin-top: 100px;
        }}
        .article-content h2 {{
            font-family: 'Playfair Display', serif;
            font-size: 26px;
            color: var(--text-primary);
            margin: 40px 0 20px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
            scroll-margin-top: 100px;
        }}
        .article-content h3 {{
            font-size: 20px;
            color: var(--accent);
            margin: 32px 0 16px;
            scroll-margin-top: 100px;
        }}
        .article-content p {{
            margin-bottom: 20px;
        }}
        .article-content ul {{
            margin: 20px 0;
            padding-left: 24px;
        }}
        .article-content li {{
            margin-bottom: 12px;
            position: relative;
        }}
        .article-content li::marker {{
            color: var(--accent);
        }}
        .article-content strong {{
            color: var(--text-primary);
            font-weight: 600;
        }}
        .article-content a {{
            color: var(--accent);
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-color 0.2s;
        }}
        .article-content a:hover {{
            border-bottom-color: var(--accent);
        }}
        .article-content hr {{
            border: none;
            height: 1px;
            background: var(--border);
            margin: 40px 0;
        }}

        /* FAQ Section */
        .faq-section {{
            margin-top: 48px;
            padding-top: 32px;
            border-top: 2px solid var(--accent-bg);
        }}
        .faq-section > h2 {{
            font-family: 'Playfair Display', serif;
            font-size: 24px;
            color: var(--text-primary);
            margin-bottom: 24px;
        }}
        .faq-item {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 16px;
            border: 1px solid var(--border);
        }}
        .faq-question {{
            color: var(--text-primary);
            font-size: 17px;
            font-weight: 600;
            margin-bottom: 12px;
        }}
        .faq-answer {{
            color: var(--text-muted);
            font-size: 15px;
            line-height: 1.6;
        }}

        /* Source Box */
        .source-box {{
            background: var(--bg-secondary);
            border-left: 4px solid var(--accent);
            padding: 20px 24px;
            margin-top: 40px;
            border-radius: 0 12px 12px 0;
        }}
        .source-box p {{
            color: var(--text-muted);
            font-size: 14px;
            margin: 0;
        }}
        .source-box a {{
            color: var(--accent);
            text-decoration: none;
        }}
        .source-box a:hover {{
            text-decoration: underline;
        }}

        /* Tags & Entities */
        .tags-section {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
        }}
        .tag {{
            background: var(--bg-secondary);
            color: var(--text-muted);
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 13px;
            border: 1px solid var(--border);
            transition: all 0.2s;
        }}
        .tag:hover {{
            border-color: var(--accent);
            color: var(--text-secondary);
        }}

        .entities-section {{
            margin-top: 16px;
        }}
        .entities-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 10px;
        }}
        .entity {{
            display: inline-block;
            background: var(--accent-bg);
            color: var(--accent);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            margin-right: 8px;
            margin-bottom: 8px;
        }}

        /* Sidebar Right */
        .sidebar-right {{
            position: sticky;
            top: 100px;
            height: fit-content;
        }}
        .sidebar-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            border: 1px solid var(--border);
            margin-bottom: 20px;
        }}
        .sidebar-title {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 16px;
        }}

        /* Newsletter Form */
        .newsletter-input {{
            width: 100%;
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--bg-tertiary);
            color: var(--text-primary);
            font-size: 14px;
            margin-bottom: 12px;
        }}
        .newsletter-input::placeholder {{
            color: var(--text-muted);
        }}
        .newsletter-btn {{
            width: 100%;
            padding: 12px 16px;
            border-radius: 8px;
            border: none;
            background: var(--accent);
            color: white;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .newsletter-btn:hover {{
            opacity: 0.9;
        }}

        /* Share Buttons */
        .share-buttons {{
            display: flex;
            gap: 10px;
        }}
        .share-btn {{
            flex: 1;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: transparent;
            color: var(--text-muted);
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }}
        .share-btn:hover {{
            border-color: var(--accent);
            color: var(--accent);
        }}

        /* Footer */
        .site-footer {{
            background: var(--bg-tertiary);
            padding: 48px 24px;
            text-align: center;
            border-top: 1px solid var(--border);
            margin-top: 60px;
        }}
        .footer-text {{
            color: var(--text-muted);
            font-size: 14px;
        }}
        .footer-text a {{
            color: var(--accent);
            text-decoration: none;
        }}

        /* Mobile Floating TOC */
        @media (max-width: 1024px) {{
            .mobile-toc-btn {{
                display: flex;
                position: fixed;
                bottom: 24px;
                right: 24px;
                width: 56px;
                height: 56px;
                border-radius: 50%;
                background: var(--accent);
                color: white;
                align-items: center;
                justify-content: center;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                cursor: pointer;
                z-index: 100;
            }}
        }}
        @media (min-width: 1025px) {{
            .mobile-toc-btn {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <!-- Reading Progress Bar -->
    <div class="progress-bar" id="progressBar"></div>

    <!-- Preview Banner -->
    <div class="preview-banner">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
        </svg>
        <span>PREVIEW MODE — Article pending approval</span>
        <div class="preview-actions">
            <button class="preview-btn approve" onclick="approveArticle()">✓ Approve</button>
            <button class="preview-btn reject" onclick="rejectArticle()">✕ Reject</button>
        </div>
    </div>

    <!-- Header -->
    <header class="site-header">
        <div class="header-content">
            <a href="https://balizero.com" class="logo">Bali<span>Zero</span></a>
            <nav class="nav-links">
                <a href="https://balizero.com/news" class="nav-link">News</a>
                <a href="https://balizero.com/services" class="nav-link">Services</a>
                <a href="https://balizero.com/contact" class="nav-link">Contact</a>
            </nav>
        </div>
    </header>

    <!-- Main Content -->
    <main class="main-container">
        <!-- Sidebar Left - Table of Contents -->
        <aside class="sidebar-left">
            <div class="toc-container">
                <div class="toc-title">On this page</div>
                {toc_html if toc_html else '<p style="color: var(--text-muted); font-size: 13px;">No sections</p>'}
            </div>
        </aside>

        <!-- Article -->
        <article class="article-container">
            <!-- Category -->
            <span class="category-badge">{cat_style["name"]}</span>

            <!-- Title -->
            <h1 class="article-title">{article.title}</h1>

            <!-- Subtitle -->
            {f'<p class="article-subtitle">{article.subtitle}</p>' if article.subtitle else ''}

            <!-- Meta -->
            <div class="article-meta">
                <span class="meta-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                        <line x1="16" y1="2" x2="16" y2="6"/>
                        <line x1="8" y1="2" x2="8" y2="6"/>
                        <line x1="3" y1="10" x2="21" y2="10"/>
                    </svg>
                    {formatted_date}
                </span>
                <span class="meta-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    {article.reading_time} min read
                </span>
                <span class="meta-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                    </svg>
                    {article.source}
                </span>
                <span class="score-badge">Score: {article.relevance_score}/100</span>
                {review_badge}
            </div>

            <!-- Cover Image -->
            {self._generate_cover_image_html(article.cover_image, article.title)}

            <!-- TL;DR -->
            {self._generate_tldr_html(article.tldr_summary)}

            <!-- Content -->
            <div class="article-content">
                {article_html}
            </div>

            <!-- FAQ -->
            {faq_html}

            <!-- Source -->
            <div class="source-box">
                <p>&#128240; Source: <a href="{article.source_url}" target="_blank" rel="noopener">{article.source}</a></p>
            </div>

            <!-- Tags -->
            <div class="tags-section">
                {tags_html}
            </div>

            <!-- Entities -->
            <div class="entities-section">
                <div class="entities-label">Key Entities</div>
                {entities_html}
            </div>
        </article>

        <!-- Sidebar Right -->
        <aside class="sidebar-right">
            <!-- Article Info -->
            <div class="sidebar-card">
                <div class="sidebar-title">Article Info</div>
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
                    <strong>ID:</strong> {article.article_id}
                </p>
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 8px;">
                    <strong>Author:</strong> {article.author}
                </p>
                <p style="font-size: 13px; color: var(--text-muted);">
                    <strong>Category:</strong> {article.category.title()}
                </p>
            </div>

            <!-- Share -->
            <div class="sidebar-card">
                <div class="sidebar-title">Share Article</div>
                <div class="share-buttons">
                    <button class="share-btn" onclick="shareTwitter()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                        </svg>
                        X
                    </button>
                    <button class="share-btn" onclick="shareLinkedIn()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                        </svg>
                        LinkedIn
                    </button>
                </div>
            </div>

            <!-- Newsletter -->
            <div class="sidebar-card">
                <div class="sidebar-title">Stay Updated</div>
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
                    Get the latest Indonesia business & expat news.
                </p>
                <input type="email" class="newsletter-input" placeholder="Enter your email">
                <button class="newsletter-btn">Subscribe</button>
            </div>
        </aside>
    </main>

    <!-- Mobile TOC Button -->
    <button class="mobile-toc-btn" onclick="toggleMobileToc()">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
    </button>

    <!-- Footer -->
    <footer class="site-footer">
        <p class="footer-text">
            © 2026 <a href="https://balizero.com">BaliZero</a>. Indonesia's trusted guide for expats and investors.
        </p>
    </footer>

    <script>
        // Reading progress bar
        window.addEventListener('scroll', () => {{
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrolled = (window.scrollY / docHeight) * 100;
            document.getElementById('progressBar').style.width = scrolled + '%';
        }});

        // Article actions
        const articleId = '{article.article_id}';

        function approveArticle() {{
            if (confirm('Approve this article for publication?')) {{
                // Call approval API
                fetch(`/api/approval/${{articleId}}/approve`, {{ method: 'POST' }})
                    .then(r => r.json())
                    .then(data => {{
                        alert('Article approved! It will be published shortly.');
                        window.close();
                    }})
                    .catch(e => alert('Error: ' + e.message));
            }}
        }}

        function rejectArticle() {{
            const reason = prompt('Reason for rejection (optional):');
            if (reason !== null) {{
                fetch(`/api/approval/${{articleId}}/reject`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ reason }})
                }})
                .then(r => r.json())
                .then(data => {{
                    alert('Article rejected.');
                    window.close();
                }})
                .catch(e => alert('Error: ' + e.message));
            }}
        }}

        // Share functions
        function shareTwitter() {{
            const url = encodeURIComponent(window.location.href);
            const text = encodeURIComponent('{article.title}');
            window.open(`https://twitter.com/intent/tweet?text=${{text}}&url=${{url}}`, '_blank');
        }}

        function shareLinkedIn() {{
            const url = encodeURIComponent(window.location.href);
            window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${{url}}`, '_blank');
        }}

        // Mobile TOC
        function toggleMobileToc() {{
            alert('Table of Contents:\\n\\n' +
                Array.from(document.querySelectorAll('.toc-link'))
                    .map(a => '• ' + a.textContent)
                    .join('\\n')
            );
        }}
    </script>
</body>
</html>'''

        return html

    def save_preview(self, article: PreviewArticle) -> str:
        """
        Generate and save preview HTML file.

        Returns the file path.
        """
        html = self.generate_preview(article)

        # Save to file
        filename = f"{article.article_id}.html"
        filepath = self.output_dir / filename
        filepath.write_text(html, encoding="utf-8")

        logger.success(f"Preview saved: {filepath}")
        return str(filepath)

    def get_preview_url(self, article_id: str, base_url: str = "https://bali-intel-scraper.fly.dev") -> str:
        """Get the public URL for a preview"""
        return f"{base_url}/preview/{article_id}"


def generate_article_id(title: str, source_url: str) -> str:
    """Generate unique article ID"""
    content = f"{title}:{source_url}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


# Convenience function for pipeline integration
def create_preview_from_pipeline(
    title: str,
    content: str,
    category: str,
    source: str,
    source_url: str,
    cover_image: str,
    seo_metadata: Dict,
    relevance_score: int = 0,
    published_at: str = None,
    reviewed_by: str = None,
) -> tuple[str, str]:
    """
    Create preview from pipeline data.

    Returns (article_id, preview_path)
    """
    article_id = generate_article_id(title, source_url)

    article = PreviewArticle(
        article_id=article_id,
        title=title,
        subtitle=seo_metadata.get("meta_description", ""),
        content=content,
        category=category,
        source=source,
        source_url=source_url,
        cover_image=cover_image,
        published_at=published_at or datetime.now(timezone.utc).isoformat(),
        reading_time=seo_metadata.get("reading_time_minutes", 5),
        keywords=seo_metadata.get("keywords", []),
        key_entities=seo_metadata.get("key_entities", []),
        faq_items=seo_metadata.get("faq_items", []),
        tldr_summary=seo_metadata.get("tldr_summary", ""),
        schema_json_ld=seo_metadata.get("schema_json_ld", "{}"),
        relevance_score=relevance_score,
        reviewed_by=reviewed_by,
    )

    generator = BaliZeroPreviewGenerator()
    preview_path = generator.save_preview(article)

    return article_id, preview_path


# CLI test
if __name__ == "__main__":
    # Test preview generation
    test_article = PreviewArticle(
        article_id="test123abc",
        title="Indonesia Extends Digital Nomad Visa to 5 Years",
        subtitle="A groundbreaking policy change that positions Bali as the top destination for remote workers in Southeast Asia.",
        content="""## Executive Summary

The Indonesian government has officially announced an extension of the Digital Nomad Visa (E33G) validity period from 1 year to 5 years, making Indonesia one of the most attractive destinations for remote workers in Southeast Asia.

## Key Changes

- **Validity**: Extended from 1 year to 5 years
- **Income requirement**: $2,000 USD/month minimum
- **Work authorization**: Remote work for foreign companies permitted
- **Tax status**: Not subject to Indonesian income tax if staying less than 183 days/year

## Impact for Digital Nomads

This policy change positions Bali and other Indonesian destinations as top choices for the growing digital nomad community. The extended visa reduces administrative burden and provides long-term stability for remote workers.

### Who Benefits Most

1. Remote workers with stable income
2. Freelancers and consultants
3. Startup founders running location-independent businesses
4. Digital content creators

## How to Apply

Applications can be submitted through Indonesian embassies worldwide or converted from a tourist visa within Indonesia. Processing time is approximately 4-6 weeks.

### Required Documents

- Valid passport (18+ months validity)
- Proof of income ($2,000/month minimum)
- Health insurance covering Indonesia
- Clean criminal record
- Application form and photos

---

*For personalized guidance on your visa application, contact BaliZero's immigration experts.*
""",
        category="immigration",
        source="Jakarta Post",
        source_url="https://www.thejakartapost.com/news/digital-nomad-visa",
        cover_image="https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1200&h=514&fit=crop",
        published_at="2026-01-11T10:00:00Z",
        reading_time=5,
        keywords=["digital nomad visa", "E33G", "Indonesia visa", "remote work", "Bali", "expat"],
        key_entities=["Indonesia", "Bali", "Ministry of Law", "Digital Nomad Visa", "E33G", "Immigration"],
        faq_items=[
            {"question": "How long is the digital nomad visa valid?", "answer": "The E33G Digital Nomad Visa is now valid for up to 5 years, extended from the previous 1-year validity."},
            {"question": "What is the income requirement?", "answer": "You need to prove a minimum monthly income of $2,000 USD from foreign sources."},
            {"question": "Can I work for Indonesian companies?", "answer": "No, the E33G visa only allows remote work for foreign employers. Working for Indonesian companies requires a different visa type."},
        ],
        tldr_summary="Indonesia has extended the Digital Nomad Visa (E33G) from 1 year to 5 years, requiring $2,000/month income and allowing remote work for foreign companies without Indonesian income tax for stays under 183 days.",
        schema_json_ld='{"@context":"https://schema.org","@type":"NewsArticle","headline":"Indonesia Extends Digital Nomad Visa to 5 Years"}',
        relevance_score=92,
        reviewed_by="Marco Rossi",
    )

    generator = BaliZeroPreviewGenerator()
    path = generator.save_preview(test_article)

    logger.success(f"Preview generated: {path}")
    logger.info(f"Open in browser: file://{path}")
