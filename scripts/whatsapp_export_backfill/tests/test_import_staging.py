from __future__ import annotations

import json
from pathlib import Path

from scripts.whatsapp_export_backfill.import_staging import summarize_jsonl


def test_summarize_jsonl_counts_records(tmp_path: Path) -> None:
    p = tmp_path / "data.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "batch"}),
                json.dumps({"record_type": "message"}),
                json.dumps({"record_type": "message"}),
                json.dumps({"record_type": "document"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert summarize_jsonl(p) == {"batch": 1, "document": 1, "message": 2}

