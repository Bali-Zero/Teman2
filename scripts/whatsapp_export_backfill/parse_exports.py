from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

MESSAGE_RE = re.compile(
    r"^[\u200e\ufeff\s]*\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+"
    r"(?P<time>\d{1,2}[:.]\d{2}[:.]\d{2})\]\s+"
    r"(?P<sender>[^:]+):\s?(?P<body>.*)$"
)
ATTACHMENT_RE = re.compile(
    r"<(?P<label>attached|allegato|terlampir|adjunto|anexo|fichier joint|joint|angehängt|datei):\s*(?P<filename>[^>]+)>",
    re.IGNORECASE,
)


def canonical_phone(value: str | None) -> str:
    """Digits-only phone canonicalization for comparison."""
    digits = re.sub(r"\D+", "", value or "")
    if digits.startswith("0") and len(digits) > 1:
        return "62" + digits[1:]
    if digits.startswith("8"):
        return "62" + digits
    return digits


def classify_document(filename: str) -> str:
    """Filename-only classification (cheap, no OCR)."""
    normalized = unicodedata.normalize("NFC", filename).lower()
    path = Path(normalized)
    text = f"{path.stem} {path.suffix}".replace("_", " ").replace("-", " ")
    suffix = path.suffix

    if suffix == ".vcf" or "vcard" in text:
        return "contact"
    if "payment" in text or "statement" in text or "receipt" in text or "bank" in text:
        return "payment_statement"
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".mp4", ".mov", ".m4a", ".opus", ".mp3"}:
        return "media"
    if "invoice" in text or "faktur" in text:
        return "invoice"
    if "passport" in text or "paspor" in text:
        return "passport"
    if "pma" in text or "company setup" in text or "company incorporation" in text:
        return "pma_setup"
    if "c1" in text and ("tourism" in text or "wisata" in text or "itk" in text):
        return "itk_c1_tourism"
    if ("c8a" in text or "c8 a" in text) and ("sport" in text or "sports" in text or "itk" in text):
        return "itk_c8a_sport"
    if ("d12" in text or "d 12" in text) and ("pre" in text or "invest" in text or "itk" in text):
        return "itk_d12_pre_investment"
    if ("e23" in text or "e 23" in text) and ("employment" in text or "work" in text or "itas" in text or "kitas" in text):
        return "itas_e23_employment"
    if ("e31" in text or "e 31" in text) and ("family" in text or "itas" in text or "kitas" in text):
        return "itas_e31_family"
    if ("e33f" in text or "e33 f" in text) and ("retirement" in text or "retire" in text or "itas" in text or "kitas" in text):
        return "itas_e33f_retirement"
    if ("e33g" in text or "e33 g" in text) and ("remote" in text or "worker" in text or "itas" in text or "kitas" in text):
        return "itas_e33g_remote_worker"
    return "unknown"


def parse_export_root(export_root: str | Path, batch_id: str | None = None) -> list[dict[str, Any]]:
    root = Path(export_root)
    chat_path = root / "_chat.txt"
    if not chat_path.exists():
        raise FileNotFoundError(f"missing WhatsApp export chat file: {chat_path}")

    batch = batch_id or root.name
    raw_messages = _parse_chat_messages(chat_path)
    records: list[dict[str, Any]] = [
        {
            "record_type": "batch",
            "batch_id": batch,
            "export_root": str(root),
            "chat_path": "_chat.txt",
            "message_count": len(raw_messages),
        }
    ]

    seen_documents: set[str] = set()
    for index, message in enumerate(raw_messages, start=1):
        message_id = f"{batch}:{index:06d}"
        attachments = _extract_attachments(message["body"], root)
        records.append(
            {
                "record_type": "message",
                "batch_id": batch,
                "message_id": message_id,
                "message_index": index,
                "timestamp": message["timestamp"],
                "sender": message["sender"],
                "body": _strip_invisible(message["body"]).strip(),
                "attachments": attachments,
            }
        )
        for attachment in attachments:
            source_path = attachment["source_path"]
            if source_path in seen_documents:
                continue
            seen_documents.add(source_path)
            document = _document_record(batch, message_id, root / source_path, source_path)
            records.append(document)
            if document["category"] == "contact":
                records.extend(_contact_records(batch, message_id, root / source_path, source_path))
    return records


def write_jsonl(records: Iterable[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def parse_vcf(text: str) -> dict[str, Any]:
    display_name = ""
    phones: list[str] = []
    waids: list[str] = []
    for line in _unfold_vcf(text):
        upper = line.upper()
        if upper.startswith("FN:"):
            display_name = line.split(":", 1)[1].strip()
            continue
        if upper.startswith("TEL"):
            meta, _, value = line.partition(":")
            phone = canonical_phone(value)
            if phone and phone not in phones:
                phones.append(phone)
            waid_match = re.search(r"waid=([^;:]+)", meta, re.IGNORECASE)
            if waid_match:
                waid = canonical_phone(waid_match.group(1))
                if waid and waid not in waids:
                    waids.append(waid)
    return {"display_name": display_name, "phones": phones, "waids": waids}


def _parse_chat_messages(chat_path: Path) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in chat_path.read_text(encoding="utf-8-sig").splitlines():
        match = MESSAGE_RE.match(line)
        if match:
            if current is not None and not _is_system_message(current):
                messages.append(current)
            current = {
                "timestamp": _parse_timestamp(match.group("date"), match.group("time")),
                "sender": _strip_invisible(match.group("sender")).strip(),
                "body": match.group("body"),
            }
            continue
        if current is not None:
            current["body"] = current["body"] + "\n" + line
    if current is not None and not _is_system_message(current):
        messages.append(current)
    return messages


def _parse_timestamp(date_value: str, time_value: str) -> str:
    normalized_time = time_value.replace(".", ":")
    year_format = "%y" if len(date_value.rsplit("/", 1)[-1]) == 2 else "%Y"
    return datetime.strptime(f"{date_value} {normalized_time}", f"%d/%m/{year_format} %H:%M:%S").isoformat()


def _extract_attachments(body: str, root: Path) -> list[dict[str, str]]:
    attachments: list[dict[str, str]] = []
    for match in ATTACHMENT_RE.finditer(body):
        filename = _strip_invisible(match.group("filename")).strip()
        label = match.group("label").lower()
        marker_lang = {
            "attached": "en",
            "allegato": "it",
            "terlampir": "id",
            "adjunto": "es",
            "anexo": "pt",
            "fichier joint": "fr",
            "joint": "fr",
            "angehängt": "de",
            "datei": "de",
        }.get(label, "en")
        attachments.append(
            {
                "filename": filename,
                "filename_nfc": unicodedata.normalize("NFC", filename),
                "source_path": _resolve_attachment_path(root, filename),
                "marker_language": marker_lang,
            }
        )
    return attachments


def _resolve_attachment_path(root: Path, filename: str) -> str:
    normalized = unicodedata.normalize("NFC", filename)
    for path in root.rglob("*"):
        if path.is_file() and unicodedata.normalize("NFC", path.name) == normalized:
            return path.relative_to(root).as_posix()
    return filename


def _document_record(batch_id: str, message_id: str, path: Path, source_path: str) -> dict[str, Any]:
    size = path.stat().st_size if path.exists() else None
    return {
        "record_type": "document",
        "batch_id": batch_id,
        "message_id": message_id,
        "source_path": source_path,
        "filename": Path(source_path).name,
        "filename_nfc": unicodedata.normalize("NFC", Path(source_path).name),
        "category": classify_document(Path(source_path).name),
        "mime_type": mimetypes.guess_type(Path(source_path).name)[0],
        "size_bytes": size,
        "sha256": _sha256(path) if path.exists() else None,
    }


def _contact_records(batch_id: str, message_id: str, path: Path, source_path: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    contact = parse_vcf(path.read_text(encoding="utf-8", errors="replace"))
    if not contact["display_name"] and not contact["phones"] and not contact["waids"]:
        return []
    return [
        {
            "record_type": "contact",
            "batch_id": batch_id,
            "message_id": message_id,
            "display_name": contact["display_name"],
            "phones": contact["phones"],
            "waids": contact["waids"],
            "source_path": source_path,
        }
    ]


def _unfold_vcf(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strip_invisible(value: str) -> str:
    return value.replace("\u200e", "").replace("\ufeff", "")


def _is_system_message(message: dict[str, str]) -> bool:
    body = _strip_invisible(message["body"]).lower()
    fragments = (
        "messages and calls are end-to-end encrypted",
        "created group",
        "added you",
        "disappearing messages were turned on",
        "turned off disappearing messages",
    )
    return any(fragment in body for fragment in fragments)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse a WhatsApp export folder into JSONL records.")
    parser.add_argument("export_root", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--batch-id")
    args = parser.parse_args(argv)

    records = parse_export_root(args.export_root, batch_id=args.batch_id)
    write_jsonl(records, args.output)
    counts: dict[str, int] = {}
    for record in records:
        counts[record["record_type"]] = counts.get(record["record_type"], 0) + 1
    sys.stdout.write(json.dumps(counts, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
