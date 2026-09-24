from __future__ import annotations

import logging
import os
import sys
from importlib import import_module, reload

import pytest


class _ReferenceCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_colored_formatter_colours_output_without_mutating_shared_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    root_logger = logging.getLogger()
    original_root_handlers = root_logger.handlers[:]
    original_root_level = root_logger.level
    child_logger = logging.getLogger("backend.tests.colored_formatter.shared_record")
    original_child_handlers = child_logger.handlers[:]
    original_child_level = child_logger.level
    original_child_propagate = child_logger.propagate
    original_child_disabled = child_logger.disabled

    logging_config = import_module("backend.app.core.logging_config")
    original_environment = logging_config.ENVIRONMENT

    try:
        # Coloring is a development-mode feature; pin it directly rather than
        # relying on whatever ENVIRONMENT the test runner happens to export
        # (pytest.ini sets "test", not "development").
        logging_config.ENVIRONMENT = "development"

        root_logger.handlers.clear()
        root_logger.setLevel(getattr(logging, logging_config.LOG_LEVEL))
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging_config.ColoredFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            ),
        )
        root_logger.addHandler(console_handler)

        reference_handler = _ReferenceCaptureHandler()
        child_logger.handlers.clear()
        child_logger.addHandler(reference_handler)
        child_logger.setLevel(logging.ERROR)
        child_logger.propagate = True
        child_logger.disabled = False

        child_logger.error("shared-record probe")
        rendered_output = capsys.readouterr().out
        stored_records = reference_handler.records[:]
    finally:
        logging_config.ENVIRONMENT = original_environment
        root_logger.handlers[:] = original_root_handlers
        root_logger.setLevel(original_root_level)
        child_logger.handlers[:] = original_child_handlers
        child_logger.setLevel(original_child_level)
        child_logger.propagate = original_child_propagate
        child_logger.disabled = original_child_disabled

    assert "\x1b[31mERROR\x1b[0m" in rendered_output
    assert len(stored_records) == 1
    assert stored_records[0].levelname == "ERROR"
    assert "\x1b" not in stored_records[0].levelname


def test_environment_constant_tracks_a_real_env_var() -> None:
    """ENVIRONMENT must be read via a mapping `.get()`, not `getattr()` on the
    `os.environ` object — `os._Environ` never carries the name as an
    attribute, so a `getattr` read silently always returns the default."""
    logging_config = import_module("backend.app.core.logging_config")
    original_value = os.environ.get("ENVIRONMENT")

    try:
        os.environ["ENVIRONMENT"] = "production"
        reload(logging_config)
        assert logging_config.ENVIRONMENT == "production"
    finally:
        if original_value is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = original_value
        reload(logging_config)
