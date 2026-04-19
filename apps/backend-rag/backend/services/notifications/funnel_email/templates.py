"""Inline HTML templates for funnel-app drip emails.

Rationale for not using Jinja files
-----------------------------------
We have 6 templates total (5 Clock checkpoints + 1 Match pre-arrival).
External Jinja files would add a loader, a path config, and a file
dependency at import time. Keeping them here as f-strings:

- Makes the prompt-to-render path transparent.
- Lets tests assert on the exact output without filesystem I/O.
- Survives import-order issues (we had the migration-runner scar 2026-04-19
  for similar pattern-based bugs).

If we grow past ~12 templates, extract to Jinja files then.
"""

from __future__ import annotations

from dataclasses import dataclass

# Sender alignment with CLAUDE.md §14: always zantara@balizero.com, always
# the "Zantara" display name.
SENDER_EMAIL = "zantara@balizero.com"
SENDER_NAME = "Zantara"


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    preheader: str  # shown in inbox preview


# ----------------------------------------------------------------------
# Visa Clock checkpoints (D-60 / D-30 / D-14 / D-7 / D-1)
# ----------------------------------------------------------------------

_CLOCK_SUBJECTS: dict[str, str] = {
    "visa_clock_d60": "Your {visa_type} expires in 60 days — time to start",
    "visa_clock_d30": "{visa_type} renewal: 30 days left to gather docs",
    "visa_clock_d14": "{visa_type}: 14 days — kantor imigrasi window opens",
    "visa_clock_d7":  "{visa_type}: 1 week to pickup or renewal",
    "visa_clock_d1":  "{visa_type} expires tomorrow",
}

_CLOCK_BODIES: dict[str, str] = {
    "visa_clock_d60": (
        "Your {visa_type} expires on {expiry_date}. Today is D-60 — the right "
        "time to decide: extend, switch, or let it lapse. "
        "If you want us to handle the paperwork, reply to this email or message us "
        "on WhatsApp: {whatsapp_url}."
    ),
    "visa_clock_d30": (
        "30 days before your {visa_type} expiry ({expiry_date}). "
        "Documents we usually need by now: passport valid 6+ months, proof of address, "
        "and — if you're extending — confirmation of sponsor/employer. "
        "Send us what you have; we'll flag gaps: {whatsapp_url}."
    ),
    "visa_clock_d14": (
        "Two weeks out from {expiry_date}. This is when we book your kantor imigrasi "
        "appointment (biometrics + passport hand-in). You'll be unable to travel "
        "abroad during the ~5-day processing window. Start WhatsApp: {whatsapp_url}."
    ),
    "visa_clock_d7": (
        "One week from expiry. If we haven't filed yet, we can still process "
        "urgent. If you've filed already, pickup window opens now. "
        "WhatsApp for status: {whatsapp_url}."
    ),
    "visa_clock_d1": (
        "Your {visa_type} expires tomorrow, {expiry_date}. If you still hold the "
        "passport (no KITAS/extension in hand), message us NOW: {whatsapp_url}. "
        "Overstaying costs IDR 1M per day and can trigger deportation."
    ),
}


def render_clock(
    *,
    trigger_type: str,
    visa_type: str,
    expiry_date: str,  # already formatted, e.g. "15 Nov 2025"
    whatsapp_url: str,
    unsubscribe_url: str,
) -> RenderedEmail:
    if trigger_type not in _CLOCK_SUBJECTS:
        raise ValueError(f"unknown clock trigger: {trigger_type}")

    subject = _CLOCK_SUBJECTS[trigger_type].format(visa_type=visa_type)
    body = _CLOCK_BODIES[trigger_type].format(
        visa_type=visa_type,
        expiry_date=expiry_date,
        whatsapp_url=whatsapp_url,
    )

    html = _wrap_html(
        title=subject,
        body=body,
        primary_cta=("Continue on WhatsApp", whatsapp_url),
        unsubscribe_url=unsubscribe_url,
    )
    preheader = f"{visa_type} expires {expiry_date} — next step enclosed."
    return RenderedEmail(subject=subject, html=html, preheader=preheader)


# ----------------------------------------------------------------------
# Visa Match pre-arrival (D-7 before expected_arrival_date)
# ----------------------------------------------------------------------


def render_match_prearrival(
    *,
    recommended_visa: str,
    arrival_date: str,
    whatsapp_url: str,
    pre_arrival_steps: list[str],
    unsubscribe_url: str,
) -> RenderedEmail:
    steps_html = "".join(f"<li>{step}</li>" for step in pre_arrival_steps)
    subject = f"Arriving in Bali next week? {recommended_visa} checklist inside"
    body = (
        f"You're arriving in Bali on {arrival_date}. Before you board, "
        f"make sure you have the {recommended_visa} essentials: "
    )
    html = _wrap_html(
        title=subject,
        body=body + f"<ol class=\"bz-steps\">{steps_html}</ol>"
                    "<p>If you want us to file on arrival, book a 15-minute call: </p>",
        primary_cta=("Continue on WhatsApp", whatsapp_url),
        unsubscribe_url=unsubscribe_url,
    )
    preheader = f"{recommended_visa} checklist — {len(pre_arrival_steps)} items to confirm."
    return RenderedEmail(subject=subject, html=html, preheader=preheader)


# ----------------------------------------------------------------------
# HTML wrapper — shared chrome (logo, footer, unsubscribe)
# ----------------------------------------------------------------------


def _wrap_html(
    *,
    title: str,
    body: str,
    primary_cta: tuple[str, str],  # (label, url)
    unsubscribe_url: str,
) -> str:
    cta_label, cta_url = primary_cta
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #f5f5f4; color: #0c0c0e; margin: 0; padding: 32px 16px; }}
  .wrap {{ max-width: 560px; margin: 0 auto; background: #fff;
           border-radius: 12px; padding: 32px; }}
  h1 {{ font-size: 20px; line-height: 1.3; margin: 0 0 16px; }}
  p, li {{ font-size: 15px; line-height: 1.55; }}
  .bz-steps {{ padding-left: 18px; margin: 16px 0 24px; }}
  .bz-steps li {{ margin-bottom: 6px; }}
  .cta {{ display: inline-block; margin-top: 16px;
          background: #25D366; color: #fff; text-decoration: none;
          padding: 12px 22px; border-radius: 8px; font-weight: 600; }}
  .footer {{ font-size: 12px; color: #666; margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px; }}
  a {{ color: #0c0c0e; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>{title}</h1>
    <p>{body}</p>
    <p><a class="cta" href="{cta_url}">{cta_label}</a></p>
    <div class="footer">
      Bali Zero · Jl. Hanoman, Ubud ·
      <a href="{unsubscribe_url}">unsubscribe</a>
    </div>
  </div>
</body>
</html>"""
