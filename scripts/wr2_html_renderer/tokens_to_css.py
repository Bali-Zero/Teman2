"""tokens.json → CSS :root custom-properties generator.

Closes the gap flagged in the GROUND phase (2026-06-07): `layouts/_base.css`
carries the comment "Auto-injected by the renderer from tokens.json" but no
such injector ever existed — the file was hand-maintained and could silently
drift from `tokens.json`. This module makes that comment true.

The brand source of truth is `~/.claude/skills/bali-zero-brand/tokens.json`
(closed namespace, owner Antonello). This generator reads it and emits the
exact `:root { --token: value; }` block the layouts reference via `var(--*)`.

Design notes:
- Pure stdlib (json only) — no third-party deps, runs anywhere.
- Deterministic: same tokens.json → byte-identical CSS (stable key order).
- The token-name mapping mirrors the names already used across the 9 layout
  `.md` skeletons and `_base.css` (verified 2026-06-07), so generated CSS is
  a drop-in for the hand-maintained `:root` block.
- Values that live ONLY in `_base.css` and not in tokens.json (the SOTA-pattern
  component tokens added 2026-05-12, and `--font-size-statement-bomb-shrunk`)
  are emitted from an explicit SUPPLEMENT table here, with provenance comments,
  rather than silently dropped. If/when they migrate into tokens.json, delete
  them from the supplement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_TOKENS_PATH = Path.home() / ".claude" / "skills" / "bali-zero-brand" / "tokens.json"

# Token values present in _base.css but NOT (yet) in tokens.json.
# Provenance: SOTA pattern adoptions 2026-05-12 (_external-bench-2026-05.md) +
# the statement-bomb auto-shrink target. Emitted so generated CSS stays a
# superset-compatible drop-in for the hand-maintained _base.css :root block.
# When any of these lands in tokens.json, remove it here to avoid duplication.
_SUPPLEMENT: dict[str, str] = {
    # statement-bomb auto-shrink target (in _base.css, not tokens.json)
    "--font-size-statement-bomb-shrunk": "56px",
    # SOTA pattern #10 — swipe indicator
    "--swipe-indicator-size": "12px",
    "--swipe-indicator-offset": "32px",
    # SOTA pattern #3 — regulation badge
    "--regulation-badge-size": "16px",
    "--regulation-badge-padding": "6px 12px",
    "--regulation-badge-offset": "32px",
    "--regulation-badge-radius": "4px",
    # SOTA pattern #25 — QR closing
    "--qr-closing-size": "120px",
    "--qr-closing-offset": "60px",
    "--qr-closing-border-width": "2px",
}


def _get(tokens: dict[str, Any], *path: str) -> Any:
    """Walk a dotted path into the tokens dict, returning the `value` leaf.

    tokens.json leaves are `{"value": X, "type": ..., "role": ...}`; this
    returns X. Raises KeyError with the full path if any segment is missing
    (fail-loud — a missing token means the brand file changed shape and the
    renderer must NOT silently emit a half-empty :root).
    """
    node: Any = tokens
    for seg in path:
        if not isinstance(node, dict) or seg not in node:
            raise KeyError(f"tokens.json missing path: {'.'.join(path)} (at segment '{seg}')")
        node = node[seg]
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def build_root_vars(tokens: dict[str, Any]) -> dict[str, str]:
    """Map tokens.json into the canonical {css-var-name: value} dict.

    Names match those already referenced by the layout skeletons + _base.css
    (verified against both on 2026-06-07).
    """
    v: dict[str, str] = {}

    # Colors — tokens.color.*
    v["--color-bg-antracite"] = _get(tokens, "color", "bg", "antracite")
    v["--color-bg-black"] = _get(tokens, "color", "bg", "black")
    v["--color-text-white"] = _get(tokens, "color", "text", "white")
    v["--color-text-muted"] = _get(tokens, "color", "text", "muted")
    v["--color-accent-yellow"] = _get(tokens, "color", "accent", "yellow")
    v["--color-status-red"] = _get(tokens, "color", "status", "red")
    v["--color-overlay-darken-60"] = _get(tokens, "color", "overlay", "darken-60")
    v["--color-overlay-darken-40"] = _get(tokens, "color", "overlay", "darken-40")

    # Typography — tokens.font.*
    v["--font-family-primary"] = _get(tokens, "font", "family", "primary")
    v["--font-family-mono"] = _get(tokens, "font", "family", "mono")
    v["--font-weight-bold"] = str(_get(tokens, "font", "weight", "bold"))
    v["--font-weight-extrabold"] = str(_get(tokens, "font", "weight", "extrabold"))
    v["--font-size-headline-cover"] = _get(tokens, "font", "size", "headline-cover")
    v["--font-size-headline-slide"] = _get(tokens, "font", "size", "headline-slide")
    v["--font-size-subheadline"] = _get(tokens, "font", "size", "subheadline")
    v["--font-size-body-lg"] = _get(tokens, "font", "size", "body-lg")
    v["--font-size-body-md"] = _get(tokens, "font", "size", "body-md")
    v["--font-size-source"] = _get(tokens, "font", "size", "source")
    v["--font-size-statement-bomb"] = _get(tokens, "font", "size", "statement-bomb")
    v["--letter-spacing-title"] = _get(tokens, "font", "letter-spacing", "title")
    v["--letter-spacing-body"] = _get(tokens, "font", "letter-spacing", "body")
    v["--line-height-tight"] = str(_get(tokens, "font", "line-height", "tight"))
    v["--line-height-snug"] = str(_get(tokens, "font", "line-height", "snug"))
    v["--line-height-normal"] = str(_get(tokens, "font", "line-height", "normal"))

    # Spacing — tokens.spacing.*
    v["--spacing-edge-margin"] = _get(tokens, "spacing", "edge-margin")
    v["--spacing-logo-bottom"] = _get(tokens, "spacing", "logo-bottom")
    v["--spacing-section-gap"] = _get(tokens, "spacing", "section-gap")
    v["--spacing-list-gap"] = _get(tokens, "spacing", "list-gap")

    # Canvas — tokens.size.canvas.*  (numbers in tokens.json → px here)
    v["--canvas-width"] = f"{_get(tokens, 'size', 'canvas', 'width')}px"
    v["--canvas-height"] = f"{_get(tokens, 'size', 'canvas', 'height')}px"

    # Logo — tokens.size.logo.*
    v["--logo-diameter"] = _get(tokens, "size", "logo", "diameter")

    # Supplement (in _base.css, not yet in tokens.json) — see module docstring
    for name, val in _SUPPLEMENT.items():
        v[name] = val

    return v


def render_root_block(tokens: dict[str, Any]) -> str:
    """Produce the `:root { ... }` CSS string from tokens (no surrounding file)."""
    vars_ = build_root_vars(tokens)
    lines = [":root {"]
    for name, value in vars_.items():
        lines.append(f"  {name}: {value};")
    lines.append("}")
    return "\n".join(lines)


def load_tokens(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_TOKENS_PATH
    if not p.is_file():
        raise FileNotFoundError(f"tokens.json not found at {p}")
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Generate CSS :root vars from bali-zero-brand tokens.json")
    ap.add_argument("--tokens", type=Path, default=None, help="path to tokens.json (default: brand skill)")
    ap.add_argument("--out", type=Path, default=None, help="write the :root block to this file (default: stdout)")
    args = ap.parse_args()

    block = render_root_block(load_tokens(args.tokens))
    if args.out:
        args.out.write_text(block + "\n", encoding="utf-8")
        print(f"wrote {len(block)} chars to {args.out}")
    else:
        print(block)
