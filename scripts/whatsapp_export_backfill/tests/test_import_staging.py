import json
from pathlib import Path
from unittest.mock import MagicMock

from scripts.whatsapp_export_backfill.import_staging import (
    _compute_source_hash,
    _excerpt,
    _msg_index,
    import_jsonl,
    summarize_jsonl,
)


def test_compute_source_hash_stable() -> None:
    batch = {
        "export_root": "/Users/x/Desktop/WhatsApp Chat - YOPO",
        "chat_path": "_chat.txt",
        "batch_id": "WhatsApp Chat - YOPO",
    }
    h1 = _compute_source_hash(batch)
    h2 = _compute_source_hash(batch)
    assert h1 == h2
    assert len(h1) == 64

    batch2 = {**batch, "batch_id": "WhatsApp Chat - OTHER"}
    assert _compute_source_hash(batch2) != h1


def test_msg_index_parses_zero_padded_suffix() -> None:
    assert _msg_index("WhatsApp Chat - YOPO company:000001") == 1
    assert _msg_index("WhatsApp Chat - YOPO company:000012") == 12
    assert _msg_index("malformed") is None
    assert _msg_index(None) is None


def test_excerpt_truncates_and_appends_ellipsis() -> None:
    short = "Hello"
    assert _excerpt(short) == "Hello"

    long = "x" * 500
    out = _excerpt(long, limit=240)
    assert out is not None
    assert len(out) == 241  # 240 + ellipsis
    assert out.endswith("…")

    assert _excerpt(None) is None
    assert _excerpt("") is None


def test_summarize_jsonl_counts(tmp_path: Path) -> None:
    path = tmp_path / "sample.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "batch"}),
                json.dumps({"record_type": "document"}),
                json.dumps({"record_type": "document"}),
                json.dumps({"record_type": "message"}),
                "",
            ]
        )
    )
    counts = summarize_jsonl(path)
    assert counts == {"batch": 1, "document": 2, "message": 1}


def test_import_jsonl_inserts_with_mock_conn(tmp_path: Path) -> None:
    path = tmp_path / "sample.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "record_type": "batch",
                        "batch_id": "WhatsApp Chat - YOPO",
                        "export_root": "/tmp/x",
                        "chat_path": "_chat.txt",
                        "message_count": 1,
                    }
                ),
                json.dumps(
                    {
                        "record_type": "document",
                        "batch_id": "WhatsApp Chat - YOPO",
                        "filename": "a.pdf",
                        "filename_nfc": "a.pdf",
                        "source_path": "a.pdf",
                        "category": "unknown",
                        "size_bytes": 100,
                        "sha256": "deadbeef",
                        "mime_type": "application/pdf",
                        "message_id": "WhatsApp Chat - YOPO:000001",
                    }
                ),
                json.dumps(
                    {
                        "record_type": "message",
                        "batch_id": "WhatsApp Chat - YOPO",
                        "message_id": "WhatsApp Chat - YOPO:000001",
                        "timestamp": "2026-05-15T10:00:00",
                        "sender": "Makar",
                        "body": "Hello",
                        "attachments": ["a.pdf"],
                    }
                ),
            ]
        )
    )

    cur = MagicMock()
    # First INSERT batch returns id=42; subsequent inserts return rowcount=1
    cur.fetchone.return_value = (42,)
    cur.rowcount = 1

    conn = MagicMock()
    # Make context managers return the mocks
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur

    counts = import_jsonl(path, conn)
    assert counts == {"batch": 1, "document": 1, "message": 1}

    # Verify exactly 3 INSERTs executed (batch, doc, msg) — batch upsert path uses RETURNING
    insert_calls = [
        c for c in cur.execute.call_args_list if "INSERT" in c.args[0].upper()
    ]
    assert len(insert_calls) == 3
