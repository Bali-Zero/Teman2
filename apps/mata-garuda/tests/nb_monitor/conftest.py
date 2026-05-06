"""Shared fixtures for nb_monitor tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def make_jsonl(tmp_path):
    """Return a factory that creates a JSONL session file with given UUID counts."""

    def _make(file_name: str, uuid_counts: dict[str, int]) -> Path:
        f = tmp_path / file_name
        lines = []
        for uuid, n in uuid_counts.items():
            for _ in range(n):
                lines.append(
                    json.dumps(
                        {
                            "type": "assistant",
                            "message": {
                                "content": [
                                    {
                                        "type": "tool_use",
                                        "name": "mcp__notebooklm-mcp__notebook_query",
                                        "input": {"notebook_id": uuid},
                                    }
                                ]
                            },
                        }
                    )
                )
        f.write_text("\n".join(lines) + "\n")
        return f

    return _make


@pytest.fixture
def fake_bootstrap(tmp_path):
    bp = tmp_path / "bootstrap.json"
    bp.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-07",
                "source": "test",
                "notebooks": [
                    {
                        "uuid": "uuid-A",
                        "name": "NB-A",
                        "family": "INTEL",
                        "lifecycle_stage": "TAC",
                        "active_routing": True,
                        "first_audited": "2026-04-01",
                        "round2_classification": "Test",
                    },
                    {
                        "uuid": "uuid-B",
                        "name": "NB-B",
                        "family": "INTEL",
                        "lifecycle_stage": "TAC",
                        "active_routing": True,
                        "first_audited": "2026-04-01",
                        "round2_classification": "Test",
                    },
                    {
                        "uuid": "uuid-C",
                        "name": "NB-C",
                        "family": "RESEARCH",
                        "lifecycle_stage": "DM",
                        "active_routing": False,
                        "first_audited": "2026-05-01",
                        "round2_classification": "Test",
                    },
                ],
            }
        )
    )
    return bp
