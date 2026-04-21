"""HTML+CSS platform templates for War Room 2.0 Layout Renderer.

Templates use ``$variable`` placeholders (string.Template) for substitution.
They import Bali Zero brand (colors, fonts) from brand.json constants below.
Google Fonts used as CDN fallback — local fonts on Pro are preferred but
templates must work in any environment.

Reference: docs/war-room-2.0-design.md §5.1. Brand values below were
originally sourced from the WR1 config/brand.json (removed 2026-04-22);
WR2 keeps them inline since the Layout Renderer is a pure-Python stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.services.war_room.models import Platform

# ── Brand constants (inlined from WR1's brand.json) ──────────────────

BRAND_BG = "#373d42"
BRAND_TEXT_PRIMARY = "#FFFFFF"
BRAND_TEXT_ACCENT = "#F4A01C"

# Google Fonts CDN fallbacks — used only if local fonts unavailable.
GOOGLE_FONTS_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=League+Spartan:wght@800&"
    "family=Montserrat:wght@400;700;900&display=swap');"
)


class PlatformTemplate(str, Enum):
    IG_CAROUSEL_COVER = "ig_carousel_cover"
    IG_CAROUSEL_SLIDE = "ig_carousel_slide"
    X_THREAD_IMAGE = "x_thread_image"
    LINKEDIN_POST = "linkedin_post"
    NEWSLETTER = "newsletter"


@dataclass(frozen=True)
class TemplateSpec:
    platform_template: PlatformTemplate
    width: int
    height: int
    required_vars: tuple[str, ...]
    html: str

    @property
    def name(self) -> str:
        return self.platform_template.value


_BASE_CSS_VARS = f"""
  --bz-bg: {BRAND_BG};
  --bz-text: {BRAND_TEXT_PRIMARY};
  --bz-accent: {BRAND_TEXT_ACCENT};
"""


def _common_head(width: int, height: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}, height={height}">
<style>
{GOOGLE_FONTS_IMPORT}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: {width}px;
  height: {height}px;
  font-family: 'Montserrat', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  background: var(--bz-bg);
  color: var(--bz-text);
  overflow: hidden;
}}
:root {{
{_BASE_CSS_VARS}
}}
"""


# ── IG Carousel (1080x1350, 4:5) — cover slide ────────────────────────

IG_COVER_HTML = _common_head(1080, 1350) + """
.container {
  position: relative;
  width: 1080px;
  height: 1350px;
  background-image: linear-gradient(rgba(0,0,0,0.35), rgba(0,0,0,0.55)),
                    url('$image_url');
  background-size: cover;
  background-position: center;
  padding: 90px 80px 120px 80px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.kicker {
  font-family: 'Montserrat', 'Helvetica Neue', Helvetica, sans-serif;
  font-weight: 700;
  font-size: 24px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--bz-accent);
  margin-bottom: 20px;
}
.headline {
  font-family: 'League Spartan', Impact, sans-serif;
  font-weight: 800;
  font-size: 84px;
  line-height: 0.95;
  color: var(--bz-text);
  max-width: 920px;
  letter-spacing: -1px;
}
.logo {
  position: absolute;
  bottom: 48px;
  left: 50%;
  transform: translateX(-50%);
  width: 200px;
  opacity: 0.95;
}
.patch-slot { /* injected CSS patch goes here */ }
$patch_css
</style>
</head>
<body>
<div class="container">
  <div class="kicker">$kicker</div>
  <h1 class="headline">$headline</h1>
  <img class="logo" src="$logo_url" alt="Bali Zero logo" />
</div>
</body>
</html>
"""


# ── IG Carousel body slide (1080x1350, 4:5) ────────────────────────────

IG_SLIDE_HTML = _common_head(1080, 1350) + """
.container {
  position: relative;
  width: 1080px;
  height: 1350px;
  display: grid;
  grid-template-rows: 720px 1fr;
}
.photo {
  width: 100%;
  height: 720px;
  background-image: url('$image_url');
  background-size: cover;
  background-position: center;
}
.text-block {
  padding: 70px 80px 80px 80px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  background: var(--bz-bg);
}
.slide-num {
  font-family: 'Montserrat', sans-serif;
  font-weight: 700;
  font-size: 20px;
  letter-spacing: 2px;
  color: var(--bz-accent);
  text-transform: uppercase;
}
.headline {
  font-family: 'Montserrat', 'Helvetica Neue', Helvetica, sans-serif;
  font-weight: 900;
  font-size: 52px;
  line-height: 1.05;
  color: var(--bz-text);
}
.body {
  font-family: 'Montserrat', 'Helvetica Neue', Helvetica, sans-serif;
  font-weight: 400;
  font-size: 26px;
  line-height: 1.35;
  color: var(--bz-text);
  opacity: 0.9;
}
$patch_css
</style>
</head>
<body>
<div class="container">
  <div class="photo"></div>
  <div class="text-block">
    <div class="slide-num">$slide_num</div>
    <h2 class="headline">$headline</h2>
    <p class="body">$body</p>
  </div>
</div>
</body>
</html>
"""


# ── X Thread hero image (1600x900) ────────────────────────────────────

X_THREAD_HTML = _common_head(1600, 900) + """
.container {
  position: relative;
  width: 1600px;
  height: 900px;
  background-image: linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.6)),
                    url('$image_url');
  background-size: cover;
  background-position: center;
  padding: 80px 120px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.kicker {
  font-family: 'Montserrat', sans-serif;
  font-weight: 700;
  font-size: 22px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--bz-accent);
  margin-bottom: 24px;
}
.headline {
  font-family: 'League Spartan', Impact, sans-serif;
  font-weight: 800;
  font-size: 90px;
  line-height: 0.98;
  color: var(--bz-text);
  max-width: 1300px;
  letter-spacing: -1px;
}
.source {
  position: absolute;
  bottom: 50px;
  right: 100px;
  font-family: 'Montserrat', sans-serif;
  font-weight: 700;
  font-size: 20px;
  color: var(--bz-text);
  opacity: 0.8;
}
$patch_css
</style>
</head>
<body>
<div class="container">
  <div class="kicker">$kicker</div>
  <h1 class="headline">$headline</h1>
  <div class="source">balizero.com</div>
</div>
</body>
</html>
"""


# ── LinkedIn post image (1200x628) ────────────────────────────────────

LINKEDIN_HTML = _common_head(1200, 628) + """
.container {
  position: relative;
  width: 1200px;
  height: 628px;
  background-image: linear-gradient(rgba(0,0,0,0.3), rgba(0,0,0,0.55)),
                    url('$image_url');
  background-size: cover;
  background-position: center;
  padding: 60px 80px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.kicker {
  font-family: 'Montserrat', sans-serif;
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--bz-accent);
  margin-bottom: 16px;
}
.headline {
  font-family: 'League Spartan', Impact, sans-serif;
  font-weight: 800;
  font-size: 58px;
  line-height: 1.02;
  color: var(--bz-text);
  max-width: 1000px;
}
.subhead {
  font-family: 'Montserrat', sans-serif;
  font-weight: 400;
  font-size: 22px;
  line-height: 1.3;
  color: var(--bz-text);
  opacity: 0.92;
  margin-top: 18px;
  max-width: 950px;
}
$patch_css
</style>
</head>
<body>
<div class="container">
  <div class="kicker">$kicker</div>
  <h1 class="headline">$headline</h1>
  <p class="subhead">$subhead</p>
</div>
</body>
</html>
"""


# ── Newsletter (600x800, email-safe tables + inline-ready classes) ──────

NEWSLETTER_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<style>
body { margin: 0; padding: 0; background: #f5f2eb; font-family: Helvetica, Arial, sans-serif; }
.wrap { width: 600px; margin: 0 auto; background: #ffffff; }
.cover-cell { padding: 0; }
.cover { width: 600px; height: 400px; display: block; }
.content { padding: 32px 36px; color: #1a1a1a; }
.kicker { font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;
          color: #F4A01C; margin-bottom: 12px; }
.headline { font-size: 28px; font-weight: 800; line-height: 1.15; color: #1a1a1a;
            margin: 0 0 16px 0; }
.body { font-size: 15px; line-height: 1.55; color: #333333; margin: 0; }
.footer { padding: 20px 36px; font-size: 11px; color: #888888;
          border-top: 1px solid #eeeeee; }
$patch_css
</style>
</head>
<body>
<table class="wrap" role="presentation" cellspacing="0" cellpadding="0">
  <tr><td class="cover-cell">
    <img class="cover" src="$image_url" alt="cover" />
  </td></tr>
  <tr><td class="content">
    <div class="kicker">$kicker</div>
    <h1 class="headline">$headline</h1>
    <p class="body">$body</p>
  </td></tr>
  <tr><td class="footer">Bali Zero — balizero.com</td></tr>
</table>
</body>
</html>
"""


_TEMPLATES: dict[PlatformTemplate, TemplateSpec] = {
    PlatformTemplate.IG_CAROUSEL_COVER: TemplateSpec(
        platform_template=PlatformTemplate.IG_CAROUSEL_COVER,
        width=1080,
        height=1350,
        required_vars=("kicker", "headline", "image_url", "logo_url"),
        html=IG_COVER_HTML,
    ),
    PlatformTemplate.IG_CAROUSEL_SLIDE: TemplateSpec(
        platform_template=PlatformTemplate.IG_CAROUSEL_SLIDE,
        width=1080,
        height=1350,
        required_vars=("slide_num", "headline", "body", "image_url"),
        html=IG_SLIDE_HTML,
    ),
    PlatformTemplate.X_THREAD_IMAGE: TemplateSpec(
        platform_template=PlatformTemplate.X_THREAD_IMAGE,
        width=1600,
        height=900,
        required_vars=("kicker", "headline", "image_url"),
        html=X_THREAD_HTML,
    ),
    PlatformTemplate.LINKEDIN_POST: TemplateSpec(
        platform_template=PlatformTemplate.LINKEDIN_POST,
        width=1200,
        height=628,
        required_vars=("kicker", "headline", "subhead", "image_url"),
        html=LINKEDIN_HTML,
    ),
    PlatformTemplate.NEWSLETTER: TemplateSpec(
        platform_template=PlatformTemplate.NEWSLETTER,
        width=600,
        height=800,
        required_vars=("kicker", "headline", "body", "image_url"),
        html=NEWSLETTER_HTML,
    ),
}


def get_template(t: PlatformTemplate) -> TemplateSpec:
    return _TEMPLATES[t]


def list_templates() -> list[TemplateSpec]:
    return list(_TEMPLATES.values())


# ── Platform → primary template (for consumer convenience) ──────────

PLATFORM_DEFAULT_TEMPLATE: dict[Platform, PlatformTemplate] = {
    Platform.INSTAGRAM: PlatformTemplate.IG_CAROUSEL_SLIDE,  # cover handled separately
    Platform.X: PlatformTemplate.X_THREAD_IMAGE,
    Platform.LINKEDIN: PlatformTemplate.LINKEDIN_POST,
    Platform.NEWSLETTER: PlatformTemplate.NEWSLETTER,
    # blog uses MDX, no rendered image needed except cover reuse
    Platform.BLOG: PlatformTemplate.LINKEDIN_POST,
}
