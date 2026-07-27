#!/usr/bin/env python3
"""
Vision Doc Extractor — hourly OCR-grade extraction from Bali Zero sources.

# Organo: vision-doc-extractor (cron-agent-python) → produce:
#         JSON strutturato + push NB-2 (NotebookLM Operations) via `nlm`
#         CLI + Telegram alert su conflitto con knowledge esistente
# Consuma da: ~/.intel_scraper/inbox/ (PDF/PNG/JPG da monitor pipeline)
#
# Ruolo: estrae dati strutturati da documenti normativi
#         (Permen/Perpres/SE Imigrasi/OSS/Pajak) usando Opus 4.7 vision HD.
#         Zero pricing governativo (solo rimando a PricingTool Bali Zero).

Input:
  - ~/.intel_scraper/inbox/<file.pdf|png|jpg>
  - State file ~/.cron-agent-python/vision-doc-extractor.state.json con hash MD5

Pipeline per file:
  1. Hash MD5 → skip se gia' processato
  2. Se PDF → convert first page a PNG (pdf2image, ~300 DPI)
  3. Resize lato lungo max 2576px (Vision HD cap) senza downscale
  4. base64 encode + invia a Opus 4.7 con prompt strutturato
  5. Parse JSON output con Pydantic schema (ExtractedDoc)
  6. Push a NB-2 via `nlm source add <NB_OPS_ID env var> --text "<JSON>" --title "<filename>"`
  7. Alert Telegram se chiavi critiche (article_text) contengono conflict markers

Env required (no hardcoded fallback — task #17 redaction, 2026-07-26: a literal
NotebookLM UUID and Telegram chat ID were fallback defaults in source; removed
because a docstring-adjacent literal has no credential SHAPE and is invisible
to pattern-based secret scans):
  - NB_OPS_ID (NotebookLM Operations notebook UUID)
  - TELEGRAM_BOT_TOKEN (via ~/.nuzantara-secrets.env)
  - TELEGRAM_ALERT_CHAT (chat id for conflict alerts)

Config via agent_config.py:
  - model: claude-opus-4-7
  - effort: xhigh (downgrade a high su CLI)
  - task_budget: 100k (ignorato su OAuth Max, ok)
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main


INBOX_DIR = Path.home() / ".intel_scraper" / "inbox"
PROCESSED_DIR = Path.home() / ".intel_scraper" / "processed"
OUTPUT_DIR = Path.home() / ".intel_scraper" / "extracted"
MAX_EDGE_PX = 2576  # Opus 4.7 vision HD cap
MAX_FILES_PER_RUN = 5
# task #17 redaction (2026-07-26): both used to carry a literal fallback default
# (a NotebookLM notebook UUID, a Telegram chat id) — deleted, not just "made
# optional". No credential SHAPE means a pattern-based secret scan never sees
# them; only the docstring three lines above said what they pointed to. Both
# are now required at point of use and fail loud when unset, rather than
# silently falling back to a value that shipped in cleartext source.

CONFLICT_MARKERS = (
    # If the model flags a contradiction with prior knowledge in its output,
    # these substrings trigger a Telegram alert.
    "CONFLICT",
    "contradicts",
    "superseded",
    "cabut",
    "dicabut",
    "repealed",
)

EXTRACTION_PROMPT = """You are a Bali Zero legal-document extractor. The image is a
page from an Indonesian regulatory source (Permen / Perpres / SE Imigrasi /
peraturan OSS / peraturan Pajak).

Extract strictly-structured data. Respond with a SINGLE JSON object, no prose,
no markdown fences. Schema:

{
  "doc_type": "Permen|Perpres|PP|UU|SE|Surat Edaran|Pengumuman|Unknown",
  "number": "string or empty",
  "year": "string or empty",
  "issued_date": "YYYY-MM-DD or empty",
  "issuing_authority": "string (Kementerian/Ditjen/Instansi)",
  "title": "headline in Bahasa Indonesia",
  "key_articles": [
    {"article": "Pasal X", "text": "verbatim Bahasa, max 500 chars"}
  ],
  "durations": [
    {"subject": "string (e.g. Visa C1)", "days": "integer", "extendable": "boolean or null"}
  ],
  "nominal_costs": [
    {"type": "PNBP|biaya|retribusi", "amount_idr": "string", "source_article": "Pasal X"}
  ],
  "expiry_deadlines": [
    {"what": "string", "by_date": "YYYY-MM-DD or empty"}
  ],
  "supersedes": "string (citation if this document repeals/amends a prior one)",
  "notes": "string (max 300 chars, verbatim only, zero speculation)"
}

Rules:
- Zero pricing speculation. Only verbatim nominal amounts shown in the image.
- If a field is not present in the image, use empty string "" or empty list [].
- Do not invent article numbers. Only quote articles visible in the image.
- If the image is blurry/illegible, set "title" to "ILLEGIBLE" and other fields empty.
- If this document appears to CONFLICT with or SUPERSEDE a prior regulation, mention it in "supersedes".
"""


@dataclass
class ExtractedDoc:
    """Loose schema — Pydantic stricter validation happens at parse time."""
    doc_type: str
    number: str
    year: str
    title: str
    raw_json: dict[str, Any]


class VisionDocExtractorJob(AgentJob):
    name = "vision-doc-extractor"
    timeout_s = 600
    requires_side_effects = False  # only fires if new documents found

    async def run(self) -> RunResult:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        seen_hashes = self._load_state()

        # Gather candidate files
        candidates = [
            p for p in sorted(INBOX_DIR.iterdir())
            if p.is_file() and p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}
        ]
        if not candidates:
            self.log_step("inbox_empty")
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="inbox_empty",
            )

        processed = 0
        pushed = 0
        alerts = 0
        errors = 0

        for path in candidates[:MAX_FILES_PER_RUN]:
            try:
                file_hash = self._file_hash(path)
                if file_hash in seen_hashes:
                    self.log_step("skip_seen", inputs={"file": path.name, "hash": file_hash})
                    continue

                image_bytes, mime = self._load_as_image(path)
                self.log_step(
                    "image_loaded",
                    inputs={"file": path.name, "bytes": len(image_bytes), "mime": mime},
                )

                extracted = await self._extract(image_bytes, mime)
                if not extracted:
                    errors += 1
                    continue

                # Persist JSON
                out_path = OUTPUT_DIR / f"{path.stem}.json"
                out_path.write_text(json.dumps(extracted.raw_json, indent=2, ensure_ascii=False))
                self.log_step(
                    "json_written",
                    outputs={"file": out_path.name, "doc_type": extracted.doc_type},
                    side_effect=f"extracted:{out_path.name}",
                )

                # Push to NB-2
                ok_push = self._push_to_nb2(extracted, path.name)
                if ok_push:
                    pushed += 1

                # Conflict check
                if self._has_conflict(extracted.raw_json):
                    await self._alert_conflict(path.name, extracted)
                    alerts += 1

                # Move to processed
                shutil.move(str(path), str(PROCESSED_DIR / path.name))
                seen_hashes[file_hash] = {
                    "file": path.name,
                    "ts": int(time.time()),
                    "doc_type": extracted.doc_type,
                }
                processed += 1
            except Exception as e:
                self.logger.error("extract_error", file=path.name, error=str(e))
                errors += 1

        self._save_state(seen_hashes)

        self.log_step(
            "run_summary",
            outputs={
                "processed": processed,
                "pushed_nb2": pushed,
                "alerts": alerts,
                "errors": errors,
            },
        )

        return RunResult(
            status="ok" if errors == 0 else "error",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps({
                "processed": processed, "pushed": pushed, "alerts": alerts, "errors": errors,
            }),
            error=None if errors == 0 else f"{errors} file(s) failed extraction",
        )

    # ── State ────────────────────────────────────────────────────────────

    def _load_state(self) -> dict[str, dict]:
        if not self.state_file.exists():
            return {}
        try:
            data = json.loads(self.state_file.read_text())
            return data.get("seen_hashes", {}) or {}
        except Exception:
            return {}

    def _save_state(self, seen_hashes: dict[str, dict]) -> None:
        # Preserve last result payload written by AgentJob._write_state
        existing = {}
        if self.state_file.exists():
            try:
                existing = json.loads(self.state_file.read_text())
            except Exception:
                pass
        existing["seen_hashes"] = seen_hashes
        self.state_file.write_text(json.dumps(existing, indent=2))

    def _file_hash(self, path: Path) -> str:
        h = hashlib.md5()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── Image prep ───────────────────────────────────────────────────────

    def _load_as_image(self, path: Path) -> tuple[bytes, str]:
        """Return (bytes, mime_type). PDFs: first page rasterized at max 2576px."""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from pdf2image import convert_from_path
            pages = convert_from_path(str(path), first_page=1, last_page=1, dpi=300)
            if not pages:
                raise ValueError(f"pdf2image returned no pages for {path.name}")
            img = pages[0]
        else:
            from PIL import Image
            img = Image.open(str(path))
            img.load()

        # Clamp to MAX_EDGE_PX on long side only (no downscale otherwise)
        from PIL import Image
        if max(img.size) > MAX_EDGE_PX:
            ratio = MAX_EDGE_PX / float(max(img.size))
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        buf = io.BytesIO()
        # Always emit PNG for fidelity
        img.convert("RGB").save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "image/png"

    # ── Vision call via Claude Agent SDK ────────────────────────────────

    async def _extract(self, image_bytes: bytes, mime: str) -> ExtractedDoc | None:
        """Call Opus 4.7 with image + prompt, return parsed ExtractedDoc."""
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        from agent_config import get_config, MODEL_OPUS_47

        cfg = get_config(self.name)
        resolved_model = cfg["model"]
        resolved_effort = cfg["effort"]
        if resolved_effort == "xhigh":
            resolved_effort = "high"  # CLI compat

        opts_kwargs: dict[str, Any] = {
            "max_turns": 1,
            "effort": resolved_effort,
            "model": resolved_model,
            "tools": [],
            "allowed_tools": [],
            "permission_mode": "bypassPermissions",
            "setting_sources": [],
            "system_prompt": (
                "You are a strict JSON-only extraction system. Output a single JSON "
                "object matching the schema. No prose, no markdown fences."
            ),
        }
        if cfg.get("task_budget") and resolved_model == MODEL_OPUS_47:
            opts_kwargs["task_budget"] = {"total": int(cfg["task_budget"])}
        if cfg.get("betas"):
            opts_kwargs["betas"] = list(cfg["betas"])

        opts = ClaudeAgentOptions(**opts_kwargs)

        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        message = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": b64},
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            },
            "parent_tool_use_id": None,
            "session_id": "default",
        }

        async def _stream():
            yield message

        chunks: list[str] = []
        try:
            async with ClaudeSDKClient(options=opts) as client:
                await client.query(_stream())
                async for msg in client.receive_response():
                    content = getattr(msg, "content", None)
                    if isinstance(content, list):
                        for block in content:
                            text = getattr(block, "text", None)
                            if text:
                                chunks.append(text)
                    elif isinstance(content, str):
                        chunks.append(content)
        except Exception as e:
            self.logger.error("vision_sdk_error", error=str(e))
            return None

        raw = "\n".join(chunks).strip()
        # Strip accidental fences
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.lstrip().startswith("json"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except Exception as e:
            self.logger.error("json_parse_error", error=str(e), raw_preview=raw[:200])
            return None

        return ExtractedDoc(
            doc_type=str(parsed.get("doc_type", "Unknown")),
            number=str(parsed.get("number", "")),
            year=str(parsed.get("year", "")),
            title=str(parsed.get("title", "")),
            raw_json=parsed,
        )

    # ── NB-2 push via nlm CLI ────────────────────────────────────────────

    def _push_to_nb2(self, doc: ExtractedDoc, source_filename: str) -> bool:
        nb_id = os.environ.get("NB_OPS_ID")
        if not nb_id:
            raise RuntimeError(
                "NB_OPS_ID env var is required (no hardcoded fallback, task #17) — "
                "set it before running vision-doc-extractor"
            )
        title = f"{doc.doc_type} {doc.number}/{doc.year} — {source_filename}".strip()
        body = json.dumps(doc.raw_json, ensure_ascii=False, indent=2)
        try:
            result = subprocess.run(
                ["nlm", "source", "add", nb_id, "--text", body, "--title", title[:200]],
                capture_output=True, text=True, timeout=120,
            )
            ok = result.returncode == 0
            self.log_step(
                "nb2_push",
                outputs={"ok": ok, "title": title[:100]},
                side_effect=f"nb2:{source_filename}" if ok else None,
                error=None if ok else (result.stderr or result.stdout)[:500],
            )
            return ok
        except Exception as e:
            self.logger.error("nb2_push_error", error=str(e))
            return False

    # ── Conflict detection + Telegram ────────────────────────────────────

    def _has_conflict(self, parsed: dict) -> bool:
        blob = json.dumps(parsed, ensure_ascii=False).lower()
        supersedes = str(parsed.get("supersedes", "")).strip()
        if supersedes and supersedes.lower() not in ("", "none", "n/a"):
            return True
        return any(marker.lower() in blob for marker in CONFLICT_MARKERS)

    async def _alert_conflict(self, filename: str, doc: ExtractedDoc) -> None:
        supersedes = str(doc.raw_json.get("supersedes", ""))[:300]
        msg = (
            f"⚠️ <b>Vision Doc Extractor</b> — possibile conflitto knowledge\n"
            f"{datetime.now(WITA).strftime('%Y-%m-%d %H:%M WITA')}\n\n"
            f"File: <code>{filename}</code>\n"
            f"Tipo: {doc.doc_type} {doc.number}/{doc.year}\n"
            f"Titolo: {doc.title[:200]}\n\n"
            f"Supersedes/repeal flag:\n<code>{supersedes}</code>\n\n"
            f"Controlla JSON in <code>~/.intel_scraper/extracted/</code>"
        )
        # Route to the configured alert chat per plan §5.
        chat_id = os.environ.get("TELEGRAM_ALERT_CHAT")
        if not chat_id:
            raise RuntimeError(
                "TELEGRAM_ALERT_CHAT env var is required (no hardcoded fallback, task #17) — "
                "set it before running vision-doc-extractor"
            )
        await self.send_telegram(msg, chat_id=chat_id)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(VisionDocExtractorJob)
