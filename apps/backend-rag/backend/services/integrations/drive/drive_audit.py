import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

# Import delle metriche Prometheus di Nuzantara (con fallback per ambienti di test)
try:
    from backend.app.metrics import (
        drive_errors_total,
        drive_file_size_bytes,
        drive_operation_duration_seconds,
        drive_operations_total,
    )

    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False

# 1. Inizializzazione del logger isolata
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# 2. Classe dedicata al logging strutturato e alla compliance
class DriveAuditLogger:
    """
    Structured audit logging for Google Drive operations.
    Garantisce la compliance tracciando chi ha fatto cosa, quando e con quale risultato.
    """

    def log_operation(
        self, user_email: str, operation: str, status: str, details: dict = None,
    ) -> None:
        """Registra un'operazione su Drive con formato strutturato JSON-ready."""
        log_data = {
            "action": "drive_audit",
            "user_email": user_email,
            "operation": operation,
            "status": status,
            **(details or {}),
        }

        if status == "success":
            logger.info(f"Drive Operation Success: {log_data}")
        else:
            logger.error(f"Drive Operation Failed: {log_data}")

    def log_error(
        self, user_email: str, operation: str, error_type: str, error_msg: str, details: dict = None,
    ) -> None:
        """Registra un errore specifico di Drive per l'audit trail."""
        self.log_operation(
            user_email=user_email,
            operation=operation,
            status="failed",
            details={"error_type": error_type, "error_message": error_msg, **(details or {})},
        )

    def _classify_error(self, error_msg: str) -> str:
        """Classify an error message into a known error type category."""
        msg_lower = error_msg.lower()
        if "storagequotaexceeded" in msg_lower or "quota" in msg_lower:
            return "quota_exceeded"
        if "permission denied" in msg_lower or "forbidden" in msg_lower:
            return "permission_denied"
        if "not found" in msg_lower:
            return "not_found"
        if "rate limit" in msg_lower:
            return "rate_limited"
        if "invalid token" in msg_lower or "auth" in msg_lower or "unauthorized" in msg_lower:
            return "auth_error"
        if "timeout" in msg_lower:
            return "timeout"
        if "network error" in msg_lower or "connection" in msg_lower:
            return "network_error"
        return "unknown"


# Istanza globale di default per retrocompatibilità o uso standalone
audit_logger = DriveAuditLogger()


# 3. Decoratore per l'automazione dell'audit e delle metriche
def drive_operation(operation_name: str) -> Callable:
    """
    Decorator for Drive operations that handles metrics and audit logging.
    Misura la latenza, traccia i file upload/download e cattura le eccezioni.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self_or_service: Any, user_email: str, *args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            status = "success"
            error_type = "none"

            # Identifica il logger di audit (iniettato tramite Facade o usa il globale)
            audit_instance = getattr(self_or_service, "audit", audit_logger)

            try:
                # Esecuzione dell'operazione asincrona
                result = await func(self_or_service, user_email, *args, **kwargs)

                # Tracciamento opzionale della dimensione del file (per metriche Prometheus)
                if METRICS_ENABLED and isinstance(result, dict) and "size" in result:
                    try:
                        size_bytes = int(result["size"])
                        drive_file_size_bytes.labels(operation=operation_name).observe(size_bytes)
                    except (ValueError, TypeError):
                        pass

                return result

            except Exception as e:
                status = "failed"
                # Classificazione base dell'errore (auth_failed, not_found, network_error, ecc.)
                error_name = type(e).__name__.lower()
                error_type = (
                    "network_error"
                    if "connection" in error_name or "timeout" in error_name
                    else "operation_failed"
                )

                if METRICS_ENABLED:
                    drive_errors_total.labels(error_type=error_type, operation=operation_name).inc()

                # Logga l'errore strutturato prima di propagarlo
                audit_instance.log_error(
                    user_email=user_email,
                    operation=operation_name,
                    error_type=error_type,
                    error_msg=str(e),
                )
                raise

            finally:
                duration = time.time() - start_time

                # Aggiornamento delle metriche Prometheus
                if METRICS_ENABLED:
                    drive_operations_total.labels(
                        operation=operation_name, user_email=user_email, status=status,
                    ).inc()
                    drive_operation_duration_seconds.labels(operation=operation_name).observe(
                        duration,
                    )

                # Log di audit per operazioni completate con successo
                if status == "success":
                    audit_instance.log_operation(
                        user_email=user_email,
                        operation=operation_name,
                        status=status,
                        details={"duration_seconds": round(duration, 3)},
                    )

        return wrapper

    return decorator
