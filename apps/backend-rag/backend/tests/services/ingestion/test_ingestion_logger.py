from __future__ import annotations

from typing import Any

from backend.services.ingestion.ingestion_logger import (
    IngestionLogger,
    IngestionStage,
    LogLevel,
)


class FakeStructuredLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def debug(self, message: str, **kwargs: Any) -> None:
        self.calls.append(("debug", message, kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        self.calls.append(("info", message, kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self.calls.append(("warning", message, kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self.calls.append(("error", message, kwargs))

    def critical(self, message: str, **kwargs: Any) -> None:
        self.calls.append(("critical", message, kwargs))


class FakeStdLogger:
    def __init__(self) -> None:
        self.errors: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.errors.append((message, args, kwargs))


def make_logger() -> tuple[IngestionLogger, FakeStructuredLogger, FakeStdLogger]:
    logger = IngestionLogger("test_ingestion")
    structured = FakeStructuredLogger()
    std_logger = FakeStdLogger()
    logger.logger = structured  # type: ignore[assignment]
    logger.std_logger = std_logger  # type: ignore[assignment]
    return logger, structured, std_logger


def test_create_event_extracts_file_metadata(tmp_path) -> None:
    file_path = tmp_path / "document.pdf"
    file_path.write_bytes(b"abc")
    logger, _, _ = make_logger()

    event = logger._create_event(
        level=LogLevel.INFO,
        stage=IngestionStage.PARSING,
        message="Parsing",
        file_path=str(file_path),
        document_id="doc-1",
    )

    assert event.file_type == ".pdf"
    assert event.file_size_bytes == 3
    assert event.document_id == "doc-1"
    assert event.stage == "parsing"


def test_log_event_drops_none_values_and_routes_by_level() -> None:
    logger, structured, _ = make_logger()
    event = logger._create_event(
        level=LogLevel.WARNING,
        stage=IngestionStage.MONITORING,
        message="Slow",
        document_id="doc-1",
        additional_context={"metric": "latency"},
    )

    logger._log_event(event, "Slow operation")

    level, message, payload = structured.calls[0]
    assert level == "warning"
    assert message == "Slow operation"
    assert payload["document_id"] == "doc-1"
    assert payload["additional_context"] == {"metric": "latency"}
    assert "file_path" not in payload


def test_start_ingestion_generates_document_id_and_logs_context(tmp_path) -> None:
    file_path = tmp_path / "document.pdf"
    file_path.write_bytes(b"abc")
    logger, structured, _ = make_logger()

    document_id = logger.start_ingestion(
        file_path=str(file_path),
        source="drive",
        trace_id="trace-1",
        user_id="user-1",
    )

    assert document_id.startswith("doc_")
    payload = structured.calls[0][2]
    assert payload["stage"] == "initialization"
    assert payload["source"] == "drive"
    assert payload["trace_id"] == "trace-1"
    assert payload["user_id"] == "user-1"


def test_parsing_error_logs_structured_and_standard_errors() -> None:
    logger, structured, std_logger = make_logger()

    logger.parsing_error(
        document_id="doc-1",
        file_path="/tmp/bad.pdf",
        error=ValueError("bad pdf"),
        trace_id="trace-1",
    )

    payload = structured.calls[0][2]
    assert structured.calls[0][0] == "error"
    assert payload["stage"] == "parsing"
    assert payload["error_type"] == "ValueError"
    assert payload["parsing_error"] == "bad pdf"
    assert std_logger.errors[0][1] == ("doc-1", "bad pdf")


def test_completion_and_failure_events_include_success_flags() -> None:
    logger, structured, _ = make_logger()

    logger.ingestion_completed(
        document_id="doc-1",
        file_path="/tmp/doc.pdf",
        chunks_created=4,
        collection_name="legal_unified",
        tier="A",
        total_duration_ms=25.0,
    )
    logger.ingestion_failed(
        document_id="doc-2",
        file_path="/tmp/bad.pdf",
        error=RuntimeError("boom"),
        stage=IngestionStage.CHUNKING,
        duration_ms=5.0,
    )

    completed = structured.calls[0][2]
    failed = structured.calls[1][2]
    assert completed["success"] is True
    assert completed["chunks_created"] == 4
    assert completed["collection_name"] == "legal_unified"
    assert failed["success"] is False
    assert failed["stage"] == "chunking"


def test_scraper_data_normalized_accepts_public_keyword_arguments() -> None:
    logger, structured, _ = make_logger()

    logger.scraper_data_normalized(
        document_id="doc-1",
        source_url="https://example.com/article",
        normalized_fields={"title": "Article", "content": "Text"},
        duration_ms=12.5,
        trace_id="trace-1",
    )

    payload = structured.calls[0][2]
    assert payload["stage"] == "cleaning"
    assert payload["duration_ms"] == 12.5
    assert payload["additional_context"] == {"source_url": "https://example.com/article"}


def test_monitoring_and_optimization_helpers_record_expected_context() -> None:
    logger, structured, _ = make_logger()

    logger.performance_alert("doc-1", "alert-1", "warning", "duration", 12.0, 10.0)
    logger.optimization_recommendation("doc-1", "batching", "high", "Batch writes", "2x")
    logger.resource_utilization("doc-1", 80.0, 512.0, 5.0, 2.0)
    logger.batch_processing_summary("batch-1", 10, 8, 2, 1000.0, 0.5)
    logger.error_recovery_attempt("doc-1", "TimeoutError", "retry", success=False)
    logger.cache_performance("doc-1", "redis", 0.75, 100, 3.0)
    logger.database_performance("doc-1", "insert", 20.0, 40, "simple")

    contexts = [call[2]["additional_context"] for call in structured.calls]
    assert contexts[0]["alert_id"] == "alert-1"
    assert contexts[1]["recommendation_type"] == "optimization"
    assert contexts[2]["metric_type"] == "resource_utilization"
    assert contexts[3]["success_rate"] == 80.0
    assert contexts[4]["recovery_success"] is False
    assert contexts[5]["cache_hits"] == 75
    assert contexts[6]["throughput_rows_per_second"] == 2000.0
