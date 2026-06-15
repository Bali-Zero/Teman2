"""Shared email branding helpers (logo, header HTML).

The logo is hosted on https://kita.balizero.com/static/email/ — a public
URL is required because Gmail webview does NOT render data: URIs in <img
src>, while a regular https URL works in every mail client (Gmail, Apple
Mail, iOS, Outlook). The asset itself lives in `apps/mouth/public/static/email/`
and ships with every Mouth/Vercel deploy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

LOGO_URL = "https://kita.balizero.com/static/email/balizero-logo-email.png"

# Public base for team member portraits. Same host as LOGO_URL — proven to
# render in Gmail/Apple Mail/Outlook (data: URIs do not). The photos ship with
# every Mouth/Vercel deploy from apps/mouth/public/static/team/, and the SSOT
# email->slug->photo mapping lives in apps/mouth/src/data/team-roster.ts
# (team_members.avatar mirrors the same paths, migration 229).
TEAM_PHOTO_BASE = "https://kita.balizero.com"

# Bali Zero standard-doc palette (matches Tax Report cover + invoice PDF)
COLOR_NAVY = "#1F2937"
COLOR_GOLD = "#F4B400"
COLOR_LIGHT = "#F7F8FA"
COLOR_BORDER = "#E5E7EB"
COLOR_TEXT = "#1F2937"
COLOR_MUTED = "#6B7280"


def logo_header_html(width_px: int = 96) -> str:
    """Return a centered <img> block to drop at the top of every client email."""
    return (
        f'<div style="text-align:center;margin:0 0 24px;">'
        f'<img src="{LOGO_URL}" alt="Bali Zero" '
        f'width="{width_px}" height="{width_px}" '
        f'style="width:{width_px}px;height:{width_px}px;display:inline-block;">'
        f"</div>"
    )


def team_email_html(
    *,
    title: str,
    intro: str,
    meta_rows: list[tuple[str, str]] | None = None,
    body_html: str = "",
    cta_label: str | None = None,
    cta_url: str | None = None,
    signature: str = "Zantara CRM",
    consultant_photo_url: str | None = None,
    consultant_name: str | None = None,
) -> str:
    """Render a clean, on-brand HTML email for internal team notifications.

    Visual style mirrors the Bali Zero standard-doc palette (dark navy
    header bar + gold accent + neutral greys), the same one used by the
    invoice PDF and the Tax Report cover.

    When ``consultant_photo_url`` is provided, the signature footer shows the
    assigned consultant's portrait next to their name. The URL must be absolute
    (mail clients do not render relative paths); pass a path that begins with
    ``/static/team/`` and it is resolved against ``TEAM_PHOTO_BASE``. Pass
    ``None`` (the default) for the legacy text-only signature.
    """
    photo_url: str | None = consultant_photo_url
    if photo_url and photo_url.startswith("/"):
        photo_url = f"{TEAM_PHOTO_BASE}{photo_url}"

    # Avatar cell: portrait when we have a usable photo, else a neutral
    # initial-less placeholder dot so the layout stays balanced.
    if photo_url:
        avatar_html = (
            f'<td width="44" valign="top" style="padding:0 12px 0 0;">'
            f'<img src="{photo_url}" '
            f'alt="{consultant_name or signature}" width="40" height="40" '
            f'style="display:block;width:40px;height:40px;border-radius:50%;'
            f'object-fit:cover;border:1px solid {COLOR_BORDER};">'
            f"</td>"
        )
    else:
        avatar_html = ""
    rows_html = ""
    if meta_rows:
        cells = "".join(
            f"<tr>"
            f'<td style="padding:6px 12px 6px 0;font-size:12px;color:{COLOR_MUTED};'
            f'font-family:Helvetica,Arial,sans-serif;white-space:nowrap;width:140px;">'
            f"{label}</td>"
            f'<td style="padding:6px 0;font-size:13px;color:{COLOR_TEXT};'
            f'font-family:Helvetica,Arial,sans-serif;font-weight:600;">'
            f"{value}</td>"
            f"</tr>"
            for label, value in meta_rows
        )
        rows_html = (
            f'<table cellspacing="0" cellpadding="0" border="0" width="100%" '
            f'style="background:{COLOR_LIGHT};border:1px solid {COLOR_BORDER};'
            f'border-radius:6px;margin:0 0 20px;">'
            f'<tr><td style="padding:10px 16px;">'
            f'<table cellspacing="0" cellpadding="0" border="0">{cells}</table>'
            f"</td></tr></table>"
        )

    cta_html = ""
    if cta_label and cta_url:
        cta_html = (
            f'<div style="margin:8px 0 24px;">'
            f'<a href="{cta_url}" '
            f'style="display:inline-block;background:{COLOR_GOLD};color:{COLOR_NAVY};'
            f"font-family:Helvetica,Arial,sans-serif;font-size:13px;font-weight:700;"
            f'padding:10px 20px;border-radius:6px;text-decoration:none;">'
            f"{cta_label}</a>"
            f"</div>"
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Helvetica,Arial,sans-serif;">
  <table cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f4f6f9;">
    <tr><td align="center" style="padding:24px 12px;">
      <table cellspacing="0" cellpadding="0" border="0" width="600"
             style="max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden;
             box-shadow:0 1px 3px rgba(0,0,0,0.06);">
        <tr><td style="background:{COLOR_NAVY};padding:18px 28px;">
          <table cellspacing="0" cellpadding="0" border="0" width="100%">
            <tr>
              <td style="font-family:Helvetica,Arial,sans-serif;color:#ffffff;
                         font-size:11px;letter-spacing:3px;text-transform:uppercase;
                         font-weight:700;">Bali Zero · Operations</td>
              <td align="right">
                <img src="{LOGO_URL}" alt="Bali Zero" width="36" height="36"
                     style="display:inline-block;vertical-align:middle;">
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="height:3px;background:{COLOR_GOLD};line-height:3px;font-size:0;">&nbsp;</td></tr>
        <tr><td style="padding:28px 28px 8px;">
          <h1 style="margin:0 0 14px;font-family:Helvetica,Arial,sans-serif;
                     font-size:20px;color:{COLOR_TEXT};font-weight:700;line-height:1.3;">
            {title}
          </h1>
          <p style="margin:0 0 18px;font-family:Helvetica,Arial,sans-serif;
                    font-size:14px;color:{COLOR_TEXT};line-height:1.55;">
            {intro}
          </p>
          {rows_html}
          <div style="font-family:Helvetica,Arial,sans-serif;font-size:14px;
                      color:{COLOR_TEXT};line-height:1.55;">
            {body_html}
          </div>
          {cta_html}
        </td></tr>
        <tr><td style="padding:18px 28px 24px;border-top:1px solid {COLOR_BORDER};
                       font-family:Helvetica,Arial,sans-serif;font-size:12px;
                       color:{COLOR_MUTED};">
          <table cellspacing="0" cellpadding="0" border="0"><tr>
            {avatar_html}
            <td valign="top" style="font-family:Helvetica,Arial,sans-serif;
                       font-size:12px;color:{COLOR_MUTED};line-height:1.5;">
              <strong style="color:{COLOR_TEXT};">{signature}</strong><br>
              Billing: asya@balizero.com · +62 881 0384 67246<br>
              General: WhatsApp +62 822 6459 9868 · balizero.com
            </td>
          </tr></table>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


async def resolve_consultant_avatar(
    db_pool: asyncpg.Pool,
    email: str | None,
) -> tuple[str | None, str | None]:
    """Return ``(photo_url, full_name)`` for a team member by email.

    Reads the canonical ``team_members.avatar`` column (aligned to the
    team-roster SSOT by migration 229). The avatar is stored as a site-relative
    path like ``/static/team/<slug>.jpg``; callers pass it straight to
    ``team_email_html(consultant_photo_url=...)`` which resolves it against
    ``TEAM_PHOTO_BASE``. Best-effort: any failure (no email, no row, no avatar,
    DB error) returns ``(None, None)`` so the signature gracefully degrades to
    the legacy text-only footer — a portrait is never load-bearing.
    """
    if not email:
        return None, None
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT avatar, full_name FROM team_members "
                "WHERE lower(email) = lower($1) LIMIT 1",
                email,
            )
    except Exception as exc:  # signature avatar is non-critical — degrade silently
        logger.warning("resolve_consultant_avatar failed for %s: %s", email, exc)
        return None, None
    if not row:
        return None, None
    return row["avatar"], row["full_name"]
