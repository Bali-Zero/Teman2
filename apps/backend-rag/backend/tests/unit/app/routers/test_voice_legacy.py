from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.voice import router


def test_elevenlabs_kbli_audit_webhook_is_retired() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/voice/elevenlabs/kbli-audit",
        json={"query": "Audit KBLI 62010"},
    )

    assert response.status_code == 410
    assert response.json() == {
        "detail": "ElevenLabs KBLI audit webhook retired; use local voice concierge."
    }
