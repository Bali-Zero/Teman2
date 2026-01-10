import importlib.util
import sys
import types
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch, service_result=None, service_error=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    class _ImageService:
        def __init__(self, api_key=None):
            self.api_key = api_key

        async def generate_image(self, _prompt):
            if service_error:
                raise service_error
            return service_result or {
                "success": True,
                "url": "https://image.example/prompt/test",
                "prompt": "test",
                "service": "pollinations_fallback",
            }

    monkeypatch.setitem(
        sys.modules,
        "services.misc.image_generation_service",
        types.SimpleNamespace(ImageGenerationService=_ImageService, redis_url='redis://localhost:6379'),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.media"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "media.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module):
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def test_generate_image_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post("/media/generate-image", json={"prompt": "hello"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["service"] == "pollinations_fallback"


def test_generate_image_service_not_configured(monkeypatch):
    module = _load_module(
        monkeypatch,
        service_result={"success": False, "error": "Image generation service not configured"},
    )
    client = _make_client(module)

    response = client.post("/media/generate-image", json={"prompt": "hello"})

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"] == "Image generation service not configured"


def test_generate_image_invalid_prompt(monkeypatch):
    module = _load_module(
        monkeypatch,
        service_result={"success": False, "error": "Invalid prompt", "details": "bad"},
    )
    client = _make_client(module)

    response = client.post("/media/generate-image", json={"prompt": "  "})

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "Invalid prompt"


def test_generate_image_unknown_error(monkeypatch):
    module = _load_module(
        monkeypatch,
        service_result={"success": False, "error": "boom", "details": "fail"},
    )
    client = _make_client(module)

    response = client.post("/media/generate-image", json={"prompt": "hello"})

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "boom"


def test_generate_image_exception(monkeypatch):
    module = _load_module(monkeypatch, service_error=RuntimeError("crash"))
    client = _make_client(module)

    response = client.post("/media/generate-image", json={"prompt": "hello"})

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "Internal server error"


def test_upload_file_success(monkeypatch, tmp_path):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    monkeypatch.chdir(tmp_path)
    payload = {"file": ("test.txt", BytesIO(b"hello"), "text/plain")}

    response = client.post("/media/upload", files=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["filename"] == "test.txt"
    assert data["url"].startswith("/static/uploads/")
    assert (tmp_path / "static" / "uploads").exists()


def test_upload_file_error(monkeypatch, tmp_path):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    monkeypatch.chdir(tmp_path)

    def _fail_copy(_src, _dst):
        raise RuntimeError("write failed")

    monkeypatch.setattr(module.shutil, "copyfileobj", _fail_copy)

    payload = {"file": ("test.txt", BytesIO(b"hello"), "text/plain")}

    response = client.post("/media/upload", files=payload)

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["error"] == "Upload failed"
