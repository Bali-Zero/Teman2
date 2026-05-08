from __future__ import annotations

from backend.services.notifications.email_branding import (
    LOGO_URL,
    logo_header_html,
    team_email_html,
)


def test_logo_header_html_uses_configured_logo_and_dimensions() -> None:
    html = logo_header_html(width_px=48)

    assert f'src="{LOGO_URL}"' in html
    assert 'alt="Bali Zero"' in html
    assert 'width="48"' in html
    assert 'height="48"' in html
    assert "width:48px;height:48px" in html


def test_team_email_html_renders_meta_rows_cta_body_and_signature() -> None:
    html = team_email_html(
        title="Renewal Ready",
        intro="A client renewal needs review.",
        meta_rows=[("Client", "Made Example"), ("Visa", "E33G")],
        body_html="<p>Passport is valid.</p>",
        cta_label="Open CRM",
        cta_url="https://crm.example.test/client/123",
        signature="Zantara Ops",
    )

    assert "Renewal Ready" in html
    assert "A client renewal needs review." in html
    assert "Client" in html
    assert "Made Example" in html
    assert "Visa" in html
    assert "E33G" in html
    assert "<p>Passport is valid.</p>" in html
    assert 'href="https://crm.example.test/client/123"' in html
    assert ">Open CRM</a>" in html
    assert "Zantara Ops" in html
    assert LOGO_URL in html


def test_team_email_html_omits_cta_when_url_is_missing() -> None:
    html = team_email_html(
        title="No CTA",
        intro="Nothing to click.",
        cta_label="Open CRM",
        cta_url=None,
    )

    assert "Open CRM" not in html
    assert "<table" in html
