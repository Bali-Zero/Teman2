"""
Standardized Logging Configuration for Nuzantara Backend

Provides configurable logging with:
- Structured JSON logging for production
- Colored console logging for development
- Component-specific loggers
- Performance tracking
- Error aggregation
"""

import logging
import sys
import time
from datetime import datetime
from typing import Optional

import structlog
from pythonjsonlogger import jsonlogger
from structlog.stdlib import LoggerFactory

# Environment-based configuration
ENVIRONMENT = getattr(__import__('os').environ, 'ENVIRONMENT', 'development')
LOG_LEVEL = getattr(__import__('os').environ, 'LOG_LEVEL', 'INFO').upper()
LOG_FORMAT = getattr(__import__('os').environ, 'LOG_FORMAT', 'console')


class PerformanceLogger:
    """Context manager for performance tracking"""

    def __init__(self, operation: str, logger: logging.Logger, level: str = "info"):
        self.operation = operation
        self.logger = logger
        self.level = level
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        getattr(self.logger, self.level)(f"🚀 Starting {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            getattr(self.logger, self.level)(
                f"❌ {self.operation} failed in {duration:.2f}s",
                extra={"error": str(exc_val), "duration": duration}
            )
        else:
            getattr(self.logger, self.level)(
                f"✅ {self.operation} completed in {duration:.2f}s",
                extra={"duration": duration}
            )


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for development"""

    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '\033[32m',  # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',  # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'  # Reset
    }

    def format(self, record):
        if ENVIRONMENT == 'development':
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"

        # Add component info if available
        if hasattr(record, 'component'):
            record.name = f"{record.name}[{record.component}]"

        return super().format(record)


class StructuredJSONFormatter(jsonlogger.JsonFormatter):
    """JSON formatter for production with structured fields"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['environment'] = ENVIRONMENT
        log_record['service'] = 'nuzantara-backend'

        # Add component if available
        if hasattr(record, 'component'):
            log_record['component'] = record.component

        # Add request_id if available (for tracing)
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id

        # Add user_id if available
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id


def setup_logging():
    """Setup standardized logging configuration"""

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))

    # Clear existing handlers
    root_logger.handlers.clear()

    if ENVIRONMENT == 'production' or LOG_FORMAT == 'json':
        # Production: JSON logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJSONFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        ))
    else:
        # Development: Colored console logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    root_logger.addHandler(handler)

    # Configure specific loggers
    configure_component_loggers()

    # Suppress noisy third-party loggers
    suppress_noise()


def configure_component_loggers():
    """Configure component-specific loggers"""

    components = {
        'database': logging.INFO,
        'api': logging.INFO,
        'auth': logging.WARNING,
        'external': logging.WARNING,
        'performance': logging.INFO,
        'security': logging.INFO,
    }

    for component, level in components.items():
        logger = logging.getLogger(f"nuzantara.{component}")
        logger.setLevel(level)


def suppress_noise():
    """Suppress noisy third-party loggers"""

    noisy_loggers = [
        'urllib3.connectionpool',
        'requests.packages.urllib3',
        'httpx',
        'asyncpg',
        'sqlalchemy.engine',
        'langchain',
        'openai',
        'anthropic',
        'google',
        'qdrant',
    ]

    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)


def get_logger(name: str, component: Optional[str] = None) -> logging.Logger:
    """Get a configured logger with optional component tagging"""

    logger = logging.getLogger(name)

    if component:
        # Add component as logger adapter
        logger = logging.LoggerAdapter(logger, {'component': component})

    return logger


def get_performance_logger(name: str, operation: str) -> PerformanceLogger:
    """Get a performance tracking context manager"""

    logger = get_logger(name, 'performance')
    return PerformanceLogger(operation, logger)


# Structured logging with structlog
def configure_structlog():
    """Configure structlog for advanced structured logging"""

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
            structlog.processors.JSONRenderer() if ENVIRONMENT == 'production'
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# Initialize logging on import
setup_logging()
configure_structlog()

# Export commonly used loggers
database_logger = get_logger('nuzantara.database', 'database')
api_logger = get_logger('nuzantara.api', 'api')
auth_logger = get_logger('nuzantara.auth', 'auth')
security_logger = get_logger('nuzantara.security', 'security')
performance_logger = get_logger('nuzantara.performance', 'performance')
