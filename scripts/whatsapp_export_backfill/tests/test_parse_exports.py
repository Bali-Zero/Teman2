import json
from pathlib import Path

from scripts.whatsapp_export_backfill.parse_exports import (
    canonical_phone,
    classify_document,
    parse_export_root,
    write_jsonl,
)


def test_parse_export_supports_multiline_attachments_vcf_and_nfc(tmp_path: Path) -> None:
    export_root = tmp_path / "WhatsApp Chat - Sample"
    export_root.mkdir()
    (export_root / "_chat.txt").write_text(
        "\n".join(
            [
                "[01/02/26, 09.10.11] Lisa Marek: Hello",
                "second line",
                "[01/02/26, 09:11:12] Sindy Kirks: invoice.pdf • 1 page <attached: invoice.pdf>",
                "[01/02/26, 09.12.13] Trevor: carta.pdf <allegato: precomposed-é-passport.pdf>",
                "[01/02/26, 09.13.14] Gemma: <attached: contact.vcf>",
            ]
        ),
        encoding="utf-8",
    )
    (export_root / "invoice.pdf").write_bytes(b"%PDF-1.4 invoice")
    (export_root / "precomposed-é-passport.pdf").write_bytes(b"%PDF-1.4 passport")
    (export_root / "contact.vcf").write_text(
        "\n".join(
            [
                "BEGIN:VCARD",
                "VERSION:3.0",
                "FN:Lisa Marek",
                "TEL;waid=628123456789:+62 812-3456-789",
                "END:VCARD",
            ]
        ),
        encoding="utf-8",
    )

    records = parse_export_root(export_root, batch_id="batch-1")
    messages = [record for record in records if record["record_type"] == "message"]
    documents = [record for record in records if record["record_type"] == "document"]
    contacts = [record for record in records if record["record_type"] == "contact"]

    assert len(messages) == 4
    assert messages[0]["body"] == "Hello\nsecond line"
    assert messages[1]["attachments"][0]["marker_language"] == "en"
    assert messages[2]["attachments"][0]["marker_language"] == "it"
    assert messages[2]["attachments"][0]["filename_nfc"] == "precomposed-é-passport.pdf"
    assert {document["category"] for document in documents} == {"invoice", "passport", "contact"}
    assert contacts == [
        {
            "record_type": "contact",
            "batch_id": "batch-1",
            "message_id": messages[3]["message_id"],
            "display_name": "Lisa Marek",
            "phones": ["628123456789"],
            "waids": ["628123456789"],
            "source_path": "contact.vcf",
        }
    ]


def test_write_jsonl_emits_batch_message_contact_and_document_records(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    export_root.mkdir()
    (export_root / "_chat.txt").write_text(
        "[02/03/26, 10:00:00] Makar: <attached: person.vcf>",
        encoding="utf-8",
    )
    (export_root / "person.vcf").write_text(
        "BEGIN:VCARD\nFN:Makar\nTEL:+62 812 0000 1111\nEND:VCARD\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "out.jsonl"
    records = parse_export_root(export_root, batch_id="batch-jsonl")
    write_jsonl(records, output_path)

    lines = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert [line["record_type"] for line in lines] == ["batch", "message", "document", "contact"]


def test_yopo_export_counts_when_fixture_exists() -> None:
    yopo_root = Path(
        "/Users/nuzantara/Desktop/WhatsApp Chat - YOPO company/WhatsApp Chat - YOPO company"
    )
    if not yopo_root.exists():
        return

    records = parse_export_root(yopo_root, batch_id="yopo-test")
    messages = [record for record in records if record["record_type"] == "message"]
    documents = [record for record in records if record["record_type"] == "document"]

    assert len(messages) == 12
    assert len(documents) == 5


def test_phone_canonicalization_and_document_classification() -> None:
    assert canonical_phone("+62 812-3456") == "628123456"
    assert canonical_phone("0812 3456") == "628123456"
    assert canonical_phone("812.3456") == "628123456"
    assert classify_document("KITAS E33G remote worker.pdf") == "itas_e33g_remote_worker"
    assert classify_document("statement payment bank.png") == "payment_statement"
    assert classify_document("family E31 KITAS.pdf") == "itas_e31_family"
