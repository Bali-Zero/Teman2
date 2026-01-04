import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _MetricSample:
    def __init__(self, name, labels, value):
        self.name = name
        self.labels = labels
        self.value = value


class _Metric:
    def __init__(self, name, samples):
        self.name = name
        self.samples = samples


def _load_module(monkeypatch, aggregator_results=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"
    aggregator_results = aggregator_results or {}

    class _Aggregator:
        def __init__(self, _state):
            self.state = _state

        async def get_overview_stats(self):
            return aggregator_results.get("overview", {"conversations_today": 1})

        async def get_rag_stats(self):
            return aggregator_results.get("rag", {"avg_latency_ms": 1.0})

        async def get_crm_stats(self):
            return aggregator_results.get("crm", {"clients_total": 1})

        async def get_team_stats(self):
            return aggregator_results.get("team", {"hours_today": 1.0})

        async def get_system_stats(self):
            return aggregator_results.get("system", {"cpu_percent": 1.0})

        async def get_qdrant_stats(self):
            return aggregator_results.get("qdrant", {"total_documents": 1})

        async def get_feedback_stats(self):
            return aggregator_results.get("feedback", {"avg_rating": 4.0})

        async def get_alert_stats(self):
            return aggregator_results.get("alerts", {"auth_failures_today": 0})

    async def get_current_user():
        return {"email": "zero@balizero.com"}

    monkeypatch.setitem(
        sys.modules,
        "app.dependencies",
        types.SimpleNamespace(get_current_user=get_current_user),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.analytics.analytics_aggregator",
        types.SimpleNamespace(AnalyticsAggregator=_Aggregator),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.analytics"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "analytics.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module, user_email):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: {"email": user_email}
    return TestClient(app)


def test_overview_forbidden(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, "user@example.com")

    response = client.get("/api/analytics/overview")

    assert response.status_code == 403
    assert "restricted" in response.json()["detail"]


def test_overview_success(monkeypatch):
    module = _load_module(monkeypatch, aggregator_results={"overview": {"conversations_today": 9}})
    client = _make_client(module, "zero@balizero.com")

    response = client.get("/api/analytics/overview")

    assert response.status_code == 200
    assert response.json()["conversations_today"] == 9


def test_all_analytics_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, "zero@balizero.com")

    response = client.get("/api/analytics/all")

    assert response.status_code == 200
    payload = response.json()
    assert "overview" in payload
    assert "alerts" in payload
    assert "generated_at" in payload


def test_llm_usage_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, "zero@balizero.com")

    metrics = [
        _Metric(
            "zantara_llm_prompt_tokens_total",
            [
                _MetricSample(
                    "zantara_llm_prompt_tokens_total",
                    {"model": "gpt", "endpoint": "/api/chat"},
                    10,
                )
            ],
        ),
        _Metric(
            "zantara_llm_completion_tokens_total",
            [
                _MetricSample(
                    "zantara_llm_completion_tokens_total",
                    {"model": "gpt", "endpoint": "/api/chat"},
                    5,
                )
            ],
        ),
        _Metric(
            "zantara_llm_cost_usd_total",
            [_MetricSample("zantara_llm_cost_usd_total", {"model": "gpt"}, 0.1234567)],
        ),
    ]
    monkeypatch.setitem(
        sys.modules,
        "prometheus_client",
        types.SimpleNamespace(REGISTRY=types.SimpleNamespace(collect=lambda: metrics)),
    )

    response = client.get("/api/analytics/llm-usage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_prompt_tokens"] == 10
    assert payload["total_completion_tokens"] == 5
    assert payload["total_tokens"] == 15
    assert payload["total_cost_usd"] == 0.123457
    assert payload["usage_by_model"][0]["model"] == "gpt"


def test_llm_usage_registry_error(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, "zero@balizero.com")

    def _raise():
        raise RuntimeError("registry down")

    monkeypatch.setitem(
        sys.modules,
        "prometheus_client",
        types.SimpleNamespace(REGISTRY=types.SimpleNamespace(collect=_raise)),
    )

    response = client.get("/api/analytics/llm-usage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_tokens"] == 0
