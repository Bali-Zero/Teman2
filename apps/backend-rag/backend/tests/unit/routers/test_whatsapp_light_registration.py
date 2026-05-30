"""Regression tests for Meta WhatsApp webhook exposure on the API process."""

from __future__ import annotations

from fastapi import FastAPI


def test_whatsapp_webhook_is_mounted_on_light_api_process() -> None:
    from backend.app.setup.router_registration import include_light_routers

    app = FastAPI()
    include_light_routers(app)

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/webhook/whatsapp" in paths
    assert "/webhook/whatsapp/status" in paths


def test_whatsapp_chat_manifest_is_api_and_rag() -> None:
    from backend.app.setup.router_manifest import ROUTER_MANIFEST

    entries = [entry for entry in ROUTER_MANIFEST if entry.name == "whatsapp_chat"]
    assert entries
    assert entries[0].process_groups == frozenset({"api", "rag"})
