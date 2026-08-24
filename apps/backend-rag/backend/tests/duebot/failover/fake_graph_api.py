"""In-memory fake of the ONE Meta Graph API surface B5 touches: per-WABA
``subscribed_apps`` (POST override + GET readback). Built on
``httpx.MockTransport`` — no socket ever opens (``network_guard.py``
would refuse it anyway if one tried).

Stores the "currently configured" callback per ``waba_id``, plus a call
log a test can assert against (``post_calls`` / ``get_calls``) — this is
what proves "zero callback-override calls" in the drill's both-nodes-up
and neither-node-up cases (research §5.4 item 10 / KILL-SWITCHES.md's
own verify recipe for ``TEAM_BOT_FAILOVER_AUTO_ENABLED``).

``force_status`` / ``force_readback_mismatch`` let a test script exactly
the failure Meta could return WITHOUT the client having to guess at real
Graph API error bodies it has never observed (see waba_override.py's own
disclosure about the unverified live shape).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


@dataclass
class FakeGraphAPI:
    callbacks: dict[str, str] = field(default_factory=dict)
    post_calls: list[dict[str, str]] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)
    force_status: int | None = None
    """When set, EVERY call (POST and GET) returns this status instead of
    the normal 200 — used to script AUTH_DEAD (401)/RATE_LIMITED (429)/
    SERVER_ERROR (5xx) without a real Meta account.
    """
    force_readback_mismatch: bool = False
    """When True, the GET readback reports a DIFFERENT uri than what was
    actually stored — proves override_callback's own verification step
    fires even when the POST itself looked fine.
    """

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.force_status is not None:
            return httpx.Response(self.force_status, json={"error": "forced"})

        # path shape: /{graph_version}/{waba_id}/subscribed_apps
        parts = request.url.path.strip("/").split("/")
        waba_id = parts[1] if len(parts) >= 3 else "unknown"

        if request.method == "POST":
            form = dict(
                pair.split("=", 1) for pair in request.content.decode().split("&") if "=" in pair
            )
            import urllib.parse

            callback_uri = urllib.parse.unquote_plus(form.get("override_callback_uri", ""))
            self.callbacks[waba_id] = callback_uri
            self.post_calls.append({"waba_id": waba_id, "callback_uri": callback_uri})
            return httpx.Response(200, json={"success": True})

        if request.method == "GET":
            self.get_calls.append(waba_id)
            stored = self.callbacks.get(waba_id, "")
            reported = stored + "#mismatch" if self.force_readback_mismatch else stored
            return httpx.Response(200, json={"override_callback_uri": reported})

        return httpx.Response(405, json={"error": "method not allowed"})

    def client(self, *, base_url: str = "https://graph.facebook.com") -> httpx.AsyncClient:
        transport = httpx.MockTransport(self.handler)
        return httpx.AsyncClient(base_url=base_url, transport=transport)


__all__ = ["FakeGraphAPI"]
