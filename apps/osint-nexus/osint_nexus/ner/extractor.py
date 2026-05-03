"""NER extraction using local Ollama LLM."""

from __future__ import annotations

import json
from typing import Any

import httpx

from osint_nexus.config import MODEL_NER, OLLAMA_BASE_URL
from osint_nexus.utils.logging import get_logger

logger = get_logger("ner")

NER_SYSTEM_PROMPT = """Kamu adalah NER extractor untuk dokumen pemerintah Indonesia.
Dari teks yang diberikan, ekstrak entitas berikut dalam format JSON:

{
  "persons": [{"nama": "", "jabatan": "", "instansi": "", "nip": ""}],
  "organizations": [{"nama": "", "tipe": "", "lokasi": ""}],
  "locations": [{"nama": "", "tipe": ""}],
  "events": [{"nama": "", "tanggal": "", "lokasi": ""}],
  "money": [{"jumlah": "", "konteks": ""}],
  "documents": [{"nomor": "", "tipe": "", "tanggal": ""}],
  "relations": [{"subject": "", "predicate": "", "object": "", "context": ""}]
}

Predicate yang valid dan ARAH yang benar:
- JABATAN_DI: subject=PERSON, object=KANTOR
- BERTEMU: subject=PERSON, object=PERSON
- MENANG_TENDER: subject=VENDOR (perusahaan pemenang), object=NAMA_PAKET
  Contoh: "PT Boga memenangkan tender X" → subject="PT Boga", object="X"
  JANGAN tulis "Kanim memenangkan" — Kanim adalah pemberi tender, bukan pemenang.
- HADIR_DI: subject=PERSON, object=EVENT
- KELUARGA: subject=PERSON, object=PERSON (context: istri/suami/anak/saudara)
- MEMILIKI: subject=PERSON, object=ASSET/COMPANY
- DILAPORKAN: subject=PERSON, object=DOKUMEN
- ANGKATAN: subject=PERSON, object=TAHUN_ANGKATAN

Jika field tidak ditemukan, kosongkan string. HANYA output JSON valid, tanpa penjelasan."""

NER_USER_TEMPLATE = """Ekstrak entitas dari teks berikut:

---
{text}
---

Output JSON:"""


class NERExtractor:
    """Extracts named entities from text using local Ollama LLM."""

    def __init__(self, model: str = MODEL_NER, base_url: str = OLLAMA_BASE_URL) -> None:
        self.model = model
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._client

    async def extract(self, text: str, source: str = "") -> dict[str, Any]:
        """Extract entities from text.

        Args:
            text: Raw text to process
            source: Source identifier for logging

        Returns:
            Parsed entity dict with persons, organizations, etc.
        """
        if not text or len(text.strip()) < 20:
            return self._empty_result()

        # Truncate very long texts
        if len(text) > 8000:
            text = text[:8000] + "\n[...TRUNCATED]"

        client = await self._get_client()
        try:
            resp = await client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": NER_SYSTEM_PROMPT},
                        {"role": "user", "content": NER_USER_TEMPLATE.format(text=text)},
                    ],
                    "stream": False,
                    "think": False,  # CRITICAL: qwen3.5 thinks for 60s+ otherwise
                    "format": "json",  # Force valid JSON output
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 2048,
                    },
                },
            )
            resp.raise_for_status()
            raw_output = resp.json()["message"]["content"]

            return self._parse_response(raw_output, source)

        except httpx.TimeoutException:
            logger.warning("NER timeout for source=%s (text len=%d)", source, len(text))
            return self._empty_result()
        except Exception as e:
            logger.error("NER extraction failed: %s", e)
            return self._empty_result()

    def _parse_response(self, raw: str, source: str) -> dict[str, Any]:
        """Parse LLM JSON output, handling common malformations."""
        # Strip markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        # Find JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end <= start:
            logger.warning("No JSON found in NER output for source=%s", source)
            return self._empty_result()

        try:
            result = json.loads(cleaned[start:end])
            # Validate expected keys
            for key in ["persons", "organizations", "relations"]:
                if key not in result:
                    result[key] = []
            logger.info(
                "NER extracted: %d persons, %d orgs, %d relations (source=%s)",
                len(result.get("persons", [])),
                len(result.get("organizations", [])),
                len(result.get("relations", [])),
                source,
            )
            return result
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error in NER output: %s", e)
            return self._empty_result()

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "persons": [],
            "organizations": [],
            "locations": [],
            "events": [],
            "money": [],
            "documents": [],
            "relations": [],
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
