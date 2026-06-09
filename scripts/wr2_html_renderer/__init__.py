"""WR2 HTML→PNG carousel renderer package (replaces the Canva path)."""
from .renderer import (
    RenderResult,
    render_html_files,
    CANVAS_W,
    CANVAS_H,
)

__all__ = ["RenderResult", "render_html_files", "CANVAS_W", "CANVAS_H"]
