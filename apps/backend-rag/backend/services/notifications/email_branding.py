"""Shared email branding helpers (logo, header HTML).

The logo is hosted on https://kita.balizero.com/static/email/ — a public
URL is required because Gmail webview does NOT render data: URIs in <img
src>, while a regular https URL works in every mail client (Gmail, Apple
Mail, iOS, Outlook). The asset itself lives in `apps/mouth/public/static/email/`
and ships with every Mouth/Vercel deploy.
"""


LOGO_URL = "https://kita.balizero.com/static/email/balizero-logo-email.png"


def logo_header_html(width_px: int = 96) -> str:
    """Return a centered <img> block to drop at the top of every client email."""
    return (
        f'<div style="text-align:center;margin:0 0 24px;">'
        f'<img src="{LOGO_URL}" alt="Bali Zero" '
        f'width="{width_px}" height="{width_px}" '
        f'style="width:{width_px}px;height:{width_px}px;display:inline-block;">'
        f"</div>"
    )
