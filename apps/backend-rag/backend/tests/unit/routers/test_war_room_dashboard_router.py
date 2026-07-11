from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers.war_room_dashboard import router


def test_war_room_metrics_requires_admin_user() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "viewer@example.com",
        "role": "team",
    }
    app.dependency_overrides[get_database_pool] = lambda: object()

    try:
        response = TestClient(app).get("/api/war-room/metrics/timeline")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required"}
