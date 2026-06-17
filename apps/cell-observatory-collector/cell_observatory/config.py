from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    minimax_api_key: str | None
    classifier_backend: str  # "ollama" | "minimax"
    eventbus_database_url: str
    db_path: Path
    api_port: int
    api_key: str
    cost_alert_threshold_usd: float
    retention_days: int
    classifier_max_inflight: int
    classifier_queue_maxsize: int

    @classmethod
    def from_env(cls) -> "Config":
        # Backend selector (default ollama — local, zero-cost, sanctioned).
        # Only the "minimax" backend needs a paid LLM key; "ollama" needs none.
        classifier_backend = os.environ.get("OBSERVATORY_CLASSIFIER", "ollama").lower()

        if classifier_backend not in ("ollama", "minimax"):
            raise RuntimeError(
                f"OBSERVATORY_CLASSIFIER={classifier_backend!r} is not a recognised "
                "backend; valid values: 'ollama' (default), 'minimax'"
            )

        minimax_api_key: str | None = (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("MINIMAXM2_API_KEY")
            or os.environ.get("MINIMAX_API_KEY")
        )
        if classifier_backend == "minimax" and not minimax_api_key:
            raise RuntimeError(
                "OBSERVATORY_CLASSIFIER=minimax requires OPENROUTER_API_KEY "
                "or MINIMAXM2_API_KEY or MINIMAX_API_KEY"
            )

        try:
            eventbus_database_url = os.environ["EVENTBUS_DATABASE_URL"]
        except KeyError as e:
            raise RuntimeError("EVENTBUS_DATABASE_URL required") from e

        db_path = Path(os.environ.get(
            "OBSERVATORY_DB_PATH",
            str(Path.home() / ".cell-observatory" / "observatory.db"),
        ))

        return cls(
            minimax_api_key=minimax_api_key,
            classifier_backend=classifier_backend,
            eventbus_database_url=eventbus_database_url,
            db_path=db_path,
            api_port=int(os.environ.get("OBSERVATORY_API_PORT", "17891")),
            api_key=os.environ.get("OBSERVATORY_API_KEY", ""),
            cost_alert_threshold_usd=float(os.environ.get("OBSERVATORY_COST_ALERT_THRESHOLD_USD", "1.0")),
            retention_days=int(os.environ.get("OBSERVATORY_RETENTION_DAYS", "90")),
            classifier_max_inflight=int(os.environ.get("OBSERVATORY_CLASSIFIER_MAX_INFLIGHT", "50")),
            classifier_queue_maxsize=int(os.environ.get("OBSERVATORY_CLASSIFIER_QUEUE_MAXSIZE", "10000")),
        )
