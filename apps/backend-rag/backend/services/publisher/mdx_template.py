"""MDX template + frontmatter builder for BlogPublisher.

Produces a canonical MDX file:

    ---
    title: "..."
    slug: "..."
    date: "YYYY-MM-DDTHH:MM:SSZ"
    tone_register: "analitico"
    cover_image: "https://..."
    hashtags: ["bali", "kbli"]
    draft_id: "..."
    ---

    # Title

    <main caption>

    ![cover](...)

    ## Sezione 2 (slide 2 headline)

    <slide 2 final_text>

    ...

Escape rules: we escape ``<``, ``>``, ``{``, ``}`` inside slide text so MDX
doesn't try to interpret them as JSX. YAML frontmatter strings are
double-quoted with internal ``"`` escaped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from backend.services.publisher.base import DraftPayload
from backend.services.war_room.models import RegisterTone

# Sprint 19: reading-time heuristic — 220 words/minute (Medium-ish baseline).
WORDS_PER_MINUTE = 220


@dataclass
class MdxExtras:
    """Optional metadata appended to the frontmatter.

    All fields are optional. When a dossier-backed article is published,
    we attach ``dossier_id`` + ``source_theses`` so the frontend can link
    readers back to the underlying reasoning.
    """

    dossier_id: str | None = None
    source_theses: list[str] = field(default_factory=list)
    composite_score: float | None = None
    category: str | None = None
    reading_time_min: int | None = None


def calculate_reading_time_min(text: str) -> int:
    """Word-count ÷ 220 wpm, rounded up, minimum 1."""
    if not text:
        return 1
    words = len(re.findall(r"\S+", text))
    minutes = max(1, round(words / WORDS_PER_MINUTE + 0.49))
    return minutes


def build_slug(topic: str, draft_id: UUID | str) -> str:
    """Deterministic URL-safe slug from topic + last 8 chars of draft_id.

    The draft_id suffix prevents collisions across days/topics.
    """
    normalized = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    if not normalized:
        normalized = "war-room"
    normalized = normalized[:60].rstrip("-")
    suffix = str(draft_id).replace("-", "")[-8:]
    return f"{normalized}-{suffix}"


def render_frontmatter(
    *,
    title: str,
    slug: str,
    published_at: datetime,
    tone_register: RegisterTone | None,
    cover_image_url: str,
    hashtags: list[str],
    draft_id: UUID | str,
    extras: MdxExtras | None = None,
) -> str:
    lines: list[str] = ["---"]
    lines.append(f'title: "{_yaml_escape(title)}"')
    lines.append(f'slug: "{_yaml_escape(slug)}"')
    lines.append(f'date: "{published_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}"')
    if tone_register is not None:
        lines.append(f'tone_register: "{tone_register.value}"')
    if cover_image_url:
        lines.append(f'cover_image: "{_yaml_escape(cover_image_url)}"')
    if hashtags:
        quoted = ", ".join(f'"{_yaml_escape(h)}"' for h in hashtags)
        lines.append(f"hashtags: [{quoted}]")
    lines.append(f'draft_id: "{draft_id}"')

    if extras is not None:
        if extras.dossier_id:
            lines.append(f'dossier_id: "{_yaml_escape(extras.dossier_id)}"')
        if extras.source_theses:
            quoted = ", ".join(
                f'"{_yaml_escape(t)}"' for t in extras.source_theses[:10]
            )
            lines.append(f"source_theses: [{quoted}]")
        if extras.composite_score is not None:
            clamped = max(0.0, min(1.0, float(extras.composite_score)))
            lines.append(f"composite_score: {clamped:.3f}")
        if extras.category:
            lines.append(f'category: "{_yaml_escape(extras.category)}"')
        if extras.reading_time_min is not None:
            lines.append(f"reading_time_min: {int(extras.reading_time_min)}")

    lines.append("---")
    return "\n".join(lines)


def render_body(draft: DraftPayload) -> str:
    parts: list[str] = []
    # Title = topic
    parts.append(f"# {_mdx_escape(draft.topic)}")
    parts.append("")
    # Main caption as lede
    if draft.main_caption:
        parts.append(_mdx_escape(draft.main_caption))
        parts.append("")
    # Cover image
    if draft.cover_image_url:
        parts.append(f"![{_mdx_escape(draft.topic)}]({draft.cover_image_url})")
        parts.append("")
    # Slides → sub-sections
    for slide in draft.slides:
        section_title = slide.caption or f"Slide {slide.slide_number}"
        parts.append(f"## {_mdx_escape(section_title)}")
        parts.append("")
        if slide.image_url:
            parts.append(f"![slide {slide.slide_number}]({slide.image_url})")
            parts.append("")
        if slide.final_text:
            parts.append(_mdx_escape(slide.final_text))
            parts.append("")
    # Footer: hashtags line (plain, no JSX)
    if draft.hashtags:
        parts.append("")
        parts.append(
            " ".join(f"#{_mdx_escape(h.lstrip('#'))}" for h in draft.hashtags)
        )
    return "\n".join(parts).rstrip() + "\n"


def render_full_mdx(
    draft: DraftPayload,
    *,
    slug: str,
    published_at: datetime,
    extras: MdxExtras | None = None,
    auto_reading_time: bool = False,
) -> str:
    body = render_body(draft)

    # If requested, compute reading_time from the body length.
    effective_extras = extras
    if auto_reading_time:
        if effective_extras is None:
            effective_extras = MdxExtras()
        if effective_extras.reading_time_min is None:
            effective_extras = MdxExtras(
                dossier_id=effective_extras.dossier_id,
                source_theses=list(effective_extras.source_theses),
                composite_score=effective_extras.composite_score,
                category=effective_extras.category,
                reading_time_min=calculate_reading_time_min(body),
            )

    fm = render_frontmatter(
        title=draft.topic,
        slug=slug,
        published_at=published_at,
        tone_register=draft.tone_register,
        cover_image_url=draft.cover_image_url,
        hashtags=draft.hashtags,
        draft_id=draft.draft_id,
        extras=effective_extras,
    )
    return f"{fm}\n\n{body}"


def filename_for(published_at: datetime, slug: str) -> str:
    date_part = published_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    return f"{date_part}-{slug}.mdx"


# ── escape helpers ──────────────────────────────────────────────────


def _mdx_escape(text: str) -> str:
    """Escape MDX-interpretable characters so slide text never breaks the doc.

    MDX treats ``<``/``>`` as JSX. We convert them to ``&lt;``/``&gt;``.
    Braces (``{``/``}``) are interpreted as expression slots — escape to HTML entities.
    """
    if text is None:
        return ""
    return (
        str(text)
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("{", "&#123;")
        .replace("}", "&#125;")
    )


def _yaml_escape(value: str) -> str:
    if value is None:
        return ""
    # double-quoted YAML string: escape backslash and quote
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
