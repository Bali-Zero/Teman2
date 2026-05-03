"""Template substitution with required-variable validation.

Uses :class:`string.Template` (``$name`` placeholders) — deterministic,
zero dependency. Validates required vars before rendering and auto-injects
``patch_css`` (empty by default).

Missing vars raise :class:`TemplateValidationError`; unknown vars are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from backend.services.layout.templates import (
    PlatformTemplate,
    TemplateSpec,
    get_template,
)


class TemplateValidationError(ValueError):
    """Raised when required variables are missing."""


@dataclass
class RenderOutput:
    html: str
    width: int
    height: int
    template: PlatformTemplate
    patch_css_applied: str


class TemplateRenderer:
    """Substitute variables into HTML templates + optional CSS patch."""

    def render(
        self,
        template: PlatformTemplate,
        variables: dict[str, str],
        *,
        patch_css: str = "",
    ) -> RenderOutput:
        spec: TemplateSpec = get_template(template)
        self._validate_required(spec, variables)

        # ensure patch_css is always defined so the template doesn't explode
        full_vars: dict[str, str] = {"patch_css": patch_css or ""}
        full_vars.update({k: _escape_html(v) for k, v in variables.items()})

        # Re-escape nothing for image_url / logo_url / patch_css since those are
        # trusted (URL) or CSS (controlled). Use raw substitution.
        for safe_key in ("image_url", "logo_url", "patch_css"):
            if safe_key in variables:
                full_vars[safe_key] = variables[safe_key]
        full_vars["patch_css"] = patch_css or ""

        try:
            rendered = Template(spec.html).safe_substitute(**full_vars)
        except Exception as exc:  # noqa: BLE001 — string.Template is defensive; still, we wrap
            raise TemplateValidationError(
                f"template substitution failed: {exc}",
            ) from exc

        return RenderOutput(
            html=rendered,
            width=spec.width,
            height=spec.height,
            template=template,
            patch_css_applied=patch_css or "",
        )

    def _validate_required(
        self, spec: TemplateSpec, variables: dict[str, str],
    ) -> None:
        missing = [v for v in spec.required_vars if v not in variables]
        if missing:
            raise TemplateValidationError(
                f"template {spec.name} missing required vars: {missing}",
            )


def _escape_html(value: str) -> str:
    """Minimal HTML escape for content inserted inside tags (not URLs)."""
    if value is None:
        return ""
    s = str(value)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )
