"""Fixtures for connectivity tests.

These tests require local infrastructure (docker-compose up).
They are skipped automatically if the service is not reachable.
"""

import socket

import pytest

from nuzantara_graph.config import Settings


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Quick TCP check to see if a service is listening."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (OSError, ConnectionRefusedError):
        return False


# These are available to all test files in this directory via conftest auto-discovery
QDRANT_AVAILABLE = _is_port_open("localhost", 6333)
POSTGRES_AVAILABLE = _is_port_open("localhost", 5432)
REDIS_AVAILABLE = _is_port_open("localhost", 6379)


@pytest.fixture(scope="module")
def local_settings():
    """Settings pointing to local docker-compose services."""
    return Settings(
        qdrant_url="http://localhost:6333",
        qdrant_api_key="",
        database_url="postgresql://postgres:postgres@localhost:5432/nuzantara_v6",
        redis_url="redis://localhost:6379/0",
        openai_api_key="",
        google_api_key="",
    )
