"""
Structured Logging Utilities for Data Ingestion & Processing
Provides comprehensive logging with Document ID, Source, and Parsing Errors
"""

import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import structlog


class LogLevel(Enum):
    """Log levels for ingestion operations"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IngestionStage(Enum):
    """Ingestion pipeline stages"""

    INITIALIZATION = "initialization"
    PARSING = "parsing"
    CLEANING = "cleaning"
    METADATA_EXTRACTION = "metadata_extraction"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    VECTOR_STORAGE = "vector_storage"
    COMPLETION = "completion"
    ERROR_RECOVERY = "error_recovery"
    MONITORING = "monitoring"
    OPTIMIZATION = "optimization"
    CACHE_ACCESS = "cache_access"
    DATABASE_ACCESS = "database_access"


@dataclass
class IngestionLogEvent:
    """Structured log event for ingestion operations"""

    timestamp: str
    level: str
    stage: str
    document_id: str | None = None
    source: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    file_size_bytes: int | None = None
    parsing_error: str | None = None
    error_type: str | None = None
    error_details: str | None = None
    duration_ms: float | None = None
    chunks_created: int | None = None
    metadata_extracted: dict[str, Any] | None = None
    collection_name: str | None = None
    tier: str | None = None
    success: bool | None = None
    trace_id: str | None = None
    user_id: str | None = None
    additional_context: dict[str, Any] | None = None


class IngestionLogger:
    """
    Structured logger for data ingestion operations.

    Provides comprehensive logging with:
    - Document ID tracking
    - Source identification
    - Detailed error reporting
    - Performance metrics
    - Structured JSON output for analysis
    """

    def __init__(self, service_name: str = "ingestion"):
        """
        Initialize the ingestion logger.

        Args:
            service_name: Name of the service generating logs
        """
        self.service_name = service_name

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self.logger = structlog.get_logger(service_name)

        # Also keep a standard logger for compatibility
        self.std_logger = logging.getLogger(f"zantara.{service_name}")

    def _create_event(
        self,
        level: LogLevel,
        stage: IngestionStage,
        message: str,
        document_id: str | None = None,
        source: str | None = None,
        file_path: str | None = None,
        parsing_error: str | None = None,
        error_type: str | None = None,
        error_details: str | None = None,
        duration_ms: float | None = None,
        chunks_created: int | None = None,
        metadata_extracted: dict[str, Any] | None = None,
        collection_name: str | None = None,
        tier: str | None = None,
        success: bool | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> IngestionLogEvent:
        """Create a structured log event"""

        # Extract file info if path provided
        file_type = None
        file_size_bytes = None
        if file_path:
            try:
                path_obj = Path(file_path)
                file_type = path_obj.suffix.lower()
                if path_obj.exists():
                    file_size_bytes = path_obj.stat().st_size
            except Exception:
                pass  # Ignore file system errors in logging

        return IngestionLogEvent(
            timestamp=datetime.now().isoformat(),
            level=level.value,
            stage=stage.value,
            document_id=document_id,
            source=source,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            parsing_error=parsing_error,
            error_type=error_type,
            error_details=error_details,
            duration_ms=duration_ms,
            chunks_created=chunks_created,
            metadata_extracted=metadata_extracted,
            collection_name=collection_name,
            tier=tier,
            success=success,
            trace_id=trace_id,
            user_id=user_id,
            additional_context=additional_context,
        )

    def _log_event(self, event: IngestionLogEvent, _message: str):
        """Log a structured event"""
        log_data = asdict(event)

        # Remove None values to keep logs clean
        log_data = {k: v for k, v in log_data.items() if v is not None}

        # Log with appropriate level
        if event.level == LogLevel.DEBUG.value:
            self.logger.debug(_message, **log_data)
        elif event.level == LogLevel.INFO.value:
            self.logger.info(_message, **log_data)
        elif event.level == LogLevel.WARNING.value:
            self.logger.warning(_message, **log_data)
        elif event.level == LogLevel.ERROR.value:
            self.logger.error(_message, **log_data)
        elif event.level == LogLevel.CRITICAL.value:
            self.logger.critical(_message, **log_data)

    def start_ingestion(
        self,
        file_path: str,
        document_id: str | None = None,
        source: str = "file_upload",
        trace_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """
        Log the start of an ingestion operation.

        Args:
            file_path: Path to the file being ingested
            document_id: Unique document identifier
            source: Source of the ingestion (file_upload, scraper, api)
            trace_id: Trace ID for correlation
            user_id: User ID who initiated the ingestion

        Returns:
            Generated document ID if not provided
        """
        if not document_id:
            # Generate document ID from file path
            document_id = f"doc_{int(time.time())}_{Path(file_path).stem}"

        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.INITIALIZATION,
            message=f"Starting ingestion: {file_path}",
            document_id=document_id,
            source=source,
            file_path=file_path,
            trace_id=trace_id,
            user_id=user_id,
        )

        self._log_event(event, f"Ingestion started for {document_id}")
        return document_id

    def parsing_success(
        self,
        document_id: str,
        file_path: str,
        text_length: int,
        duration_ms: float,
        source: str = "file_upload",
        trace_id: str | None = None,
    ):
        """Log successful parsing"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.PARSING,
            message=f"Successfully parsed document: {text_length} chars",
            document_id=document_id,
            source=source,
            file_path=file_path,
            duration_ms=duration_ms,
            additional_context={"text_length": text_length},
            trace_id=trace_id,
        )

        self._log_event(event, f"Parsing successful for {document_id}")

    def parsing_error(
        self,
        document_id: str,
        file_path: str,
        error: Exception,
        source: str = "file_upload",
        trace_id: str | None = None,
    ):
        """Log parsing error with detailed information"""
        error_type = type(error).__name__
        error_details = str(error)

        event = self._create_event(
            level=LogLevel.ERROR,
            stage=IngestionStage.PARSING,
            message=f"Parsing failed: {error_details}",
            document_id=document_id,
            source=source,
            file_path=file_path,
            parsing_error=error_details,
            error_type=error_type,
            error_details=error_details,
            trace_id=trace_id,
        )

        self._log_event(event, f"Parsing error for {document_id}")

        # Also log to standard logger for backward compatibility
        self.std_logger.error(
            f"Parsing error for {document_id}: {error_details}",
            extra={
                "document_id": document_id,
                "file_path": file_path,
                "error_type": error_type,
            },
            exc_info=True,
        )

    def metadata_extracted(
        self,
        document_id: str,
        metadata: dict[str, Any],
        source: str = "unknown",
        trace_id: str | None = None,
    ):
        """Log successful metadata extraction"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.METADATA_EXTRACTION,
            message=f"Metadata extracted: {len(metadata)} fields",
            document_id=document_id,
            source=source,
            metadata_extracted=metadata,
            trace_id=trace_id,
        )

        self._log_event(event, f"Metadata extracted for {document_id}")

    def chunking_completed(
        self,
        document_id: str,
        chunks_count: int,
        duration_ms: float,
        source: str = "file_upload",
        trace_id: str | None = None,
    ):
        """Log chunking completion"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.CHUNKING,
            message=f"Document chunked into {chunks_count} pieces",
            document_id=document_id,
            source=source,
            chunks_created=chunks_count,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )

        self._log_event(event, f"Chunking completed for {document_id}")

    def ingestion_completed(
        self,
        document_id: str,
        file_path: str,
        chunks_created: int,
        collection_name: str,
        tier: str,
        total_duration_ms: float,
        source: str = "file_upload",
        trace_id: str | None = None,
        user_id: str | None = None,
    ):
        """Log successful ingestion completion"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.COMPLETION,
            message=f"Ingestion completed successfully: {chunks_created} chunks",
            document_id=document_id,
            source=source,
            file_path=file_path,
            chunks_created=chunks_created,
            collection_name=collection_name,
            tier=tier,
            duration_ms=total_duration_ms,
            success=True,
            trace_id=trace_id,
            user_id=user_id,
        )

        self._log_event(event, f"Ingestion completed for {document_id}")

    def ingestion_failed(
        self,
        document_id: str,
        file_path: str,
        error: Exception,
        stage: IngestionStage,
        duration_ms: float | None = None,
        source: str = "file_upload",
        trace_id: str | None = None,
        user_id: str | None = None,
    ):
        """Log ingestion failure"""
        error_type = type(error).__name__
        error_details = str(error)

        event = self._create_event(
            level=LogLevel.ERROR,
            stage=stage,
            message=f"Ingestion failed: {error_details}",
            document_id=document_id,
            source=source,
            file_path=file_path,
            parsing_error=error_details,
            error_type=error_type,
            error_details=error_details,
            duration_ms=duration_ms,
            success=False,
            trace_id=trace_id,
            user_id=user_id,
        )

        self._log_event(event, f"Ingestion failed for {document_id}")

        # Also log to standard logger
        self.std_logger.error(
            f"Ingestion failed for {document_id}: {error_details}",
            extra={
                "document_id": document_id,
                "file_path": file_path,
                "stage": stage.value,
                "error_type": error_type,
            },
            exc_info=True,
        )

    def scraper_data_normalized(
        self,
        document_id: str,
        _source_url: str,
        _duration_ms: float,
        normalized_fields: dict[str, Any],
        trace_id: str | None = None,
    ):
        """Log scraper data normalization"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.CLEANING,
            _message=f"Scraper data normalized: {len(normalized_fields)} fields",
            document_id=document_id,
            source="scraper",
            trace_id=trace_id,
        )

        self._log_event(event, f"Scraper data normalized for {document_id}")

    def stage_progress(
        self,
        document_id: str,
        stage: IngestionStage,
        message: str,
        source: str = "file_upload",
        trace_id: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ):
        """Log progress through ingestion stages"""
        event = self._create_event(
            level=LogLevel.DEBUG,
            stage=stage,
            message=message,
            document_id=document_id,
            source=source,
            trace_id=trace_id,
            additional_context=additional_context,
        )

        self._log_event(event, message)

    def performance_alert(
        self,
        document_id: str,
        alert_id: str,
        severity: str,
        metric_name: str,
        current_value: float,
        threshold: float,
        trace_id: str | None = None,
    ):
        """Log performance alert"""
        event = self._create_event(
            level=LogLevel.WARNING,
            stage=IngestionStage.MONITORING,
            message=f"Performance alert: {metric_name} = {current_value:.2f} (threshold: {threshold:.2f})",
            document_id=document_id,
            source="performance_monitor",
            trace_id=trace_id,
            additional_context={
                "alert_id": alert_id,
                "severity": severity,
                "metric_name": metric_name,
                "current_value": current_value,
                "threshold": threshold,
                "alert_type": "performance",
            },
        )

        self._log_event(event, f"Performance alert for {document_id}: {metric_name}")

    def optimization_recommendation(
        self,
        document_id: str,
        category: str,
        priority: str,
        description: str,
        expected_improvement: str,
        trace_id: str | None = None,
    ):
        """Log optimization recommendation"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.OPTIMIZATION,
            message=f"Optimization recommendation: {description}",
            document_id=document_id,
            source="performance_optimizer",
            trace_id=trace_id,
            additional_context={
                "category": category,
                "priority": priority,
                "description": description,
                "expected_improvement": expected_improvement,
                "recommendation_type": "optimization",
            },
        )

        self._log_event(event, f"Optimization recommendation for {document_id}")

    def resource_utilization(
        self,
        document_id: str,
        cpu_percent: float,
        memory_mb: float,
        disk_io_mb: float,
        network_io_mb: float,
        trace_id: str | None = None,
    ):
        """Log resource utilization metrics"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.MONITORING,
            message=f"Resource utilization: CPU {cpu_percent}%, Memory {memory_mb}MB",
            document_id=document_id,
            source="system_monitor",
            trace_id=trace_id,
            additional_context={
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "disk_io_mb": disk_io_mb,
                "network_io_mb": network_io_mb,
                "metric_type": "resource_utilization",
            },
        )

        self._log_event(event, f"Resource utilization for {document_id}")

    def batch_processing_summary(
        self,
        document_id: str,
        total_documents: int,
        successful: int,
        failed: int,
        total_duration_ms: float,
        avg_document_size_mb: float,
        trace_id: str | None = None,
    ):
        """Log batch processing summary"""
        success_rate = (successful / total_documents * 100) if total_documents > 0 else 0

        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.COMPLETION,
            message=f"Batch processing: {successful}/{total_documents} successful ({success_rate:.1f}%)",
            document_id=document_id,
            source="batch_processor",
            trace_id=trace_id,
            additional_context={
                "total_documents": total_documents,
                "successful": successful,
                "failed": failed,
                "success_rate": success_rate,
                "total_duration_ms": total_duration_ms,
                "avg_document_size_mb": avg_document_size_mb,
                "throughput_docs_per_second": (total_documents / (total_duration_ms / 1000))
                if total_duration_ms > 0
                else 0,
                "processing_type": "batch",
            },
        )

        self._log_event(event, f"Batch processing summary for {document_id}")

    def error_recovery_attempt(
        self,
        document_id: str,
        error_type: str,
        recovery_action: str,
        success: bool,
        trace_id: str | None = None,
    ):
        """Log error recovery attempt"""
        event = self._create_event(
            level=LogLevel.INFO if success else LogLevel.WARNING,
            stage=IngestionStage.ERROR_RECOVERY,
            message=f"Error recovery {'successful' if success else 'failed'}: {recovery_action}",
            document_id=document_id,
            source="error_recovery",
            trace_id=trace_id,
            additional_context={
                "error_type": error_type,
                "recovery_action": recovery_action,
                "recovery_success": success,
                "log_type": "error_recovery",
            },
        )

        self._log_event(event, f"Error recovery for {document_id}: {recovery_action}")

    def cache_performance(
        self,
        document_id: str,
        cache_type: str,
        hit_rate: float,
        total_requests: int,
        avg_response_time_ms: float,
        trace_id: str | None = None,
    ):
        """Log cache performance metrics"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.CACHE_ACCESS,
            message=f"Cache performance: {cache_type} hit rate {hit_rate:.2%}",
            document_id=document_id,
            source="cache_monitor",
            trace_id=trace_id,
            additional_context={
                "cache_type": cache_type,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
                "avg_response_time_ms": avg_response_time_ms,
                "cache_hits": int(total_requests * hit_rate),
                "cache_misses": int(total_requests * (1 - hit_rate)),
                "metric_type": "cache_performance",
            },
        )

        self._log_event(event, f"Cache performance for {document_id}: {cache_type}")

    def database_performance(
        self,
        document_id: str,
        operation: str,
        duration_ms: float,
        rows_affected: int,
        query_complexity: str,
        trace_id: str | None = None,
    ):
        """Log database performance metrics"""
        event = self._create_event(
            level=LogLevel.INFO,
            stage=IngestionStage.DATABASE_ACCESS,
            message=f"DB operation: {operation} completed in {duration_ms:.2f}ms",
            document_id=document_id,
            source="database_monitor",
            trace_id=trace_id,
            additional_context={
                "operation": operation,
                "duration_ms": duration_ms,
                "rows_affected": rows_affected,
                "query_complexity": query_complexity,
                "throughput_rows_per_second": (rows_affected / (duration_ms / 1000))
                if duration_ms > 0
                else 0,
                "metric_type": "database_performance",
            },
        )

        self._log_event(event, f"Database performance for {document_id}: {operation}")


# Global logger instance
ingestion_logger = IngestionLogger()
