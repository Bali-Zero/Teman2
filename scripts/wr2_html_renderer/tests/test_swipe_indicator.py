"""Article 14.1 swipe-indicator injection (systemic composer gap, closed 2026-07-14).

The constitution (14.1, APPROVED 2026-05-12) requires a `.swipe-indicator` on
slides 2..N-1; the CSS has lived in layouts/_base.css since then, but no layout
skeleton ships the element and the composer never injected it — the critic
soft-flagged the absence on every single carousel run.
"""

from wr2_html_renderer.composer import _inject_swipe_indicator

HTML = "<html><head></head><body><div>content</div></body></html>"


class TestSwipeIndicator:
    def test_inner_slides_get_the_dot(self):
        for idx in (2, 5, 8):
            out = _inject_swipe_indicator(HTML, idx, 9)
            assert out.count('class="swipe-indicator"') == 1, idx

    def test_cover_excluded(self):
        assert "swipe-indicator" not in _inject_swipe_indicator(HTML, 1, 9)

    def test_closer_excluded(self):
        assert "swipe-indicator" not in _inject_swipe_indicator(HTML, 9, 9)

    def test_two_slide_carousel_has_none(self):
        assert "swipe-indicator" not in _inject_swipe_indicator(HTML, 1, 2)
        assert "swipe-indicator" not in _inject_swipe_indicator(HTML, 2, 2)

    def test_idempotent_on_skeleton_owned_indicator(self):
        """Innocence: a skeleton that already carries its own indicator is left alone."""
        own = HTML.replace("<div>content</div>", '<div class="swipe-indicator"></div>')
        out = _inject_swipe_indicator(own, 3, 9)
        assert out.count("swipe-indicator") == 1

    def test_injected_before_body_close(self):
        out = _inject_swipe_indicator(HTML, 4, 9)
        assert out.index("swipe-indicator") < out.index("</body>")
