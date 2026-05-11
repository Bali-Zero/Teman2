"""Shared email branding helpers (logo, header HTML).

The logo is hosted on https://kita.balizero.com/static/email/ — a public
URL is required because Gmail webview does NOT render data: URIs in <img
src>, while a regular https URL works in every mail client (Gmail, Apple
Mail, iOS, Outlook). The asset itself lives in `apps/mouth/public/static/email/`
and ships with every Mouth/Vercel deploy.
"""


LOGO_URL = "https://kita.balizero.com/static/email/balizero-logo-email.png"

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
) -> str:
    """Render a clean, on-brand HTML email for internal team notifications.

    Visual style mirrors the Bali Zero standard-doc palette (dark navy
    header bar + gold accent + neutral greys), the same one used by the
    invoice PDF and the Tax Report cover.
    """
    rows_html = ""
    if meta_rows:
        cells = "".join(
            f'<tr>'
            f'<td style="padding:6px 12px 6px 0;font-size:12px;color:{COLOR_MUTED};'
            f'font-family:Helvetica,Arial,sans-serif;white-space:nowrap;width:140px;">'
            f'{label}</td>'
            f'<td style="padding:6px 0;font-size:13px;color:{COLOR_TEXT};'
            f'font-family:Helvetica,Arial,sans-serif;font-weight:600;">'
            f'{value}</td>'
            f'</tr>'
            for label, value in meta_rows
        )
        rows_html = (
            f'<table cellspacing="0" cellpadding="0" border="0" width="100%" '
            f'style="background:{COLOR_LIGHT};border:1px solid {COLOR_BORDER};'
            f'border-radius:6px;margin:0 0 20px;">'
            f'<tr><td style="padding:10px 16px;">'
            f'<table cellspacing="0" cellpadding="0" border="0">{cells}</table>'
            f'</td></tr></table>'
        )

    cta_html = ""
    if cta_label and cta_url:
        cta_html = (
            f'<div style="margin:8px 0 24px;">'
            f'<a href="{cta_url}" '
            f'style="display:inline-block;background:{COLOR_GOLD};color:{COLOR_NAVY};'
            f'font-family:Helvetica,Arial,sans-serif;font-size:13px;font-weight:700;'
            f'padding:10px 20px;border-radius:6px;text-decoration:none;">'
            f'{cta_label}</a>'
            f'</div>'
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
          <strong style="color:{COLOR_TEXT};">{signature}</strong><br>
          Billing: asya@balizero.com · +62 881 0384 67246<br>
          General: WhatsApp +62 821 3107 363 · balizero.com
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
