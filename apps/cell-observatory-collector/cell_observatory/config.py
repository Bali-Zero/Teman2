from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    minimax_api_key: str
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
        try:
            # Track A activation 2026-05-02: MiniMax classifier routes through
            # OpenRouter (free tier minimax-m2.5:free). Cascade priority:
            #   1. OPENROUTER_API_KEY (canonical OpenRouter env name)
            #   2. MINIMAXM2_API_KEY (legacy alias)
            #   3. MINIMAX_API_KEY (direct minimax.io fallback for paid mode)
            minimax_api_key = (
                os.environ.get("OPENROUTER_API_KEY")
                or os.environ.get("MINIMAXM2_API_KEY")
                or os.environ["MINIMAX_API_KEY"]
            )
        except KeyError as e:
            raise RuntimeError(
                "OPENROUTER_API_KEY or MINIMAXM2_API_KEY or MINIMAX_API_KEY required"
            ) from e

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
            eventbus_database_url=eventbus_database_url,
            db_path=db_path,
            api_port=int(os.environ.get("OBSERVATORY_API_PORT", "17891")),
            api_key=os.environ.get("OBSERVATORY_API_KEY", ""),
            cost_alert_threshold_usd=float(os.environ.get("OBSERVATORY_COST_ALERT_THRESHOLD_USD", "1.0")),
            retention_days=int(os.environ.get("OBSERVATORY_RETENTION_DAYS", "90")),
            classifier_max_inflight=int(os.environ.get("OBSERVATORY_CLASSIFIER_MAX_INFLIGHT", "50")),
            classifier_queue_maxsize=int(os.environ.get("OBSERVATORY_CLASSIFIER_QUEUE_MAXSIZE", "10000")),
        )
