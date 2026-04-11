"""
Hierarchical chunker for Indonesian politics KB.

Splits JSONL records into parent (full document) and child (claim-level) chunks.
Each child carries a pointer to its parent for aggregation during retrieval.

Design trade-off: Since the KB is structured JSONL (not free text), claim
extraction traverses JSON fields and generates natural-language sentences
rather than using NLP parsing. This avoids a spaCy dependency (~30MB) and
works reliably on the structured data we have.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from hashlib import md5
from pathlib import Path
from typing import Any

from backend.kb.politics.hierarchical.extractor import ClaimExtractor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Chunk:
    """A single chunk (parent or child) with metadata."""

    id: str
    text: str
    chunk_type: str  # "parent" or "child"
    parent_id: str | None  # None for parents, parent chunk id for children
    record_id: str  # Original JSONL record id
    record_type: str  # person, party, election, jurisdiction
    source_path: str  # Source file path
    offset: int  # Line number (0-indexed) in source file
    language: str  # "id" or "en"
    metadata: dict[str, Any] = field(default_factory=dict)


def _deterministic_id(record_id: str, chunk_type: str, index: int = 0) -> str:
    """Generate a deterministic chunk ID from content identifiers.

    Uses record_id + chunk_type + index (NOT source_path or line offset)
    so that IDs remain stable if files are reorganized or records reordered.
    """
    raw = f"{record_id}|{chunk_type}|{index}"
    return md5(raw.encode("utf-8")).hexdigest()


def _detect_language(text: str) -> str:
    """Detect language per document. Heuristic: Indonesian keywords vs English.

    Simple but effective for our structured data where we know the corpus
    is overwhelmingly Indonesian with some English field names.
    """
    id_markers = [
        "presiden", "gubernur", "partai", "pemilu", "jabatan",
        "wakil", "menteri", "yurisdiksi", "lahir", "anggota",
        "keanggotaan", "berdiri", "pimpinan", "republik", "indonesia",
        "tokoh", "calon", "suara", "daerah", "kontes",
    ]
    lower = text.lower()
    id_count = sum(1 for m in id_markers if m in lower)
    return "id" if id_count >= 2 else "en"


class HierarchicalChunker:
    """Split JSONL politics records into parent and child chunks.

    Parent chunk: Full human-readable text of the record (~200-800 tokens).
    Child chunks: Individual claim-level sentences (~20-80 tokens each),
                  each carrying a pointer back to the parent.
    """

    def __init__(self) -> None:
        self._extractor = ClaimExtractor()

    def chunk_record(
        self,
        record: dict[str, Any],
        source_path: str,
        line_offset: int,
    ) -> list[Chunk]:
        """Chunk a single JSONL record into parent + children.

        Args:
            record: Parsed JSON record from JSONL file.
            source_path: Path to the source file (for attribution).
            line_offset: Line number (0-indexed) in the source file.

        Returns:
            List of Chunk objects: first is the parent, rest are children.
        """
        record_id = record.get("id", f"unknown:{line_offset}")
        record_type = record.get("type", "unknown")

        # Build parent text (full record representation)
        parent_text = self._build_parent_text(record)
        if not parent_text.strip():
            logger.warning(f"Empty parent text for record {record_id} at {source_path}:{line_offset}")
            return []

        language = _detect_language(parent_text)

        parent_id = _deterministic_id(record_id, "parent")
        parent = Chunk(
            id=parent_id,
            text=parent_text,
            chunk_type="parent",
            parent_id=None,
            record_id=record_id,
            record_type=record_type,
            source_path=source_path,
            offset=line_offset,
            language=language,
            metadata=self._extract_metadata(record),
        )

        # Extract child claims
        claims = self._extractor.extract_claims(record)
        children: list[Chunk] = []
        for i, claim_text in enumerate(claims):
            child_id = _deterministic_id(record_id, "child", i)
            children.append(Chunk(
                id=child_id,
                text=claim_text,
                chunk_type="child",
                parent_id=parent_id,
                record_id=record_id,
                record_type=record_type,
                source_path=source_path,
                offset=line_offset,
                language=language,
                metadata=self._extract_metadata(record),
            ))

        return [parent, *children]

    def chunk_file(self, path: Path) -> list[Chunk]:
        """Chunk all records in a JSONL file.

        Handles corrupt/empty lines gracefully.
        """
        chunks: list[Chunk] = []
        source = str(path)

        try:
            with path.open("r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Corrupt JSON at {source}:{line_idx}: {e}")
                        continue

                    record_chunks = self.chunk_record(record, source, line_idx)
                    chunks.extend(record_chunks)
        except OSError as e:
            logger.error(f"Cannot read {source}: {e}")

        return chunks

    def chunk_directory(self, root: Path) -> list[Chunk]:
        """Chunk all JSONL files under a politics KB directory.

        Traverses: persons/, parties/, elections/, jurisdictions/ subdirs.
        """
        all_chunks: list[Chunk] = []
        root = Path(root)

        for subdir in ["persons", "parties", "elections", "jurisdictions"]:
            dirpath = root / subdir
            if not dirpath.is_dir():
                continue
            for jsonl_file in sorted(dirpath.glob("*.jsonl")):
                if jsonl_file.name.startswith("seed_template"):
                    continue  # Skip template files
                file_chunks = self.chunk_file(jsonl_file)
                all_chunks.extend(file_chunks)
                logger.info(f"Chunked {jsonl_file.name}: {len(file_chunks)} chunks")

        parents = sum(1 for c in all_chunks if c.chunk_type == "parent")
        children = sum(1 for c in all_chunks if c.chunk_type == "child")
        logger.info(f"Total: {len(all_chunks)} chunks ({parents} parents, {children} children)")
        return all_chunks

    def _build_parent_text(self, record: dict[str, Any]) -> str:
        """Build full human-readable text for a record (parent chunk).

        Reuses the pattern from PoliticsIngestionService._build_text()
        but adds richer context for hierarchical retrieval.
        """
        t = record.get("type")

        if t == "person":
            return self._build_person_text(record)
        if t == "party":
            return self._build_party_text(record)
        if t == "election":
            return self._build_election_text(record)
        if t == "jurisdiction":
            return self._build_jurisdiction_text(record)

        return json.dumps(record, ensure_ascii=False)

    def _build_person_text(self, r: dict[str, Any]) -> str:
        name = r.get("name", "")
        aliases = r.get("aliases", [])
        alias_str = f" (alias: {', '.join(aliases)})" if aliases else ""
        dob = r.get("dob", "")
        pob = r.get("pob", "")

        lines = [f"Tokoh politik: {name}{alias_str}"]
        if dob or pob:
            lines.append(f"Lahir: {dob} di {pob}" if pob else f"Lahir: {dob}")

        parties = r.get("party_memberships", [])
        if parties:
            lines.append("Keanggotaan partai:")
            for p in parties:
                pid = p.get("party_id", "?")
                pfrom = p.get("from", "?")
                pto = p.get("to", "sekarang")
                lines.append(f"  - {pid} ({pfrom} - {pto or 'sekarang'})")

        offices = r.get("offices", [])
        if offices:
            lines.append("Jabatan:")
            for o in offices:
                oname = o.get("office", "?")
                jid = o.get("jurisdiction_id", "")
                ofrom = o.get("from", "?")
                oto = o.get("to", "sekarang")
                elected = " (terpilih)" if o.get("elected") else ""
                lines.append(f"  - {oname} di {jid} ({ofrom} - {oto or 'sekarang'}){elected}")

        cases = r.get("cases", [])
        if cases:
            lines.append("Kasus hukum:")
            for c in cases:
                lines.append(f"  - {c}")

        return "\n".join(lines)

    def _build_party_text(self, r: dict[str, Any]) -> str:
        name = r.get("name", "")
        abbrev = r.get("abbrev", "")
        founded = r.get("founded", "?")
        ideology = r.get("ideology", [])
        dissolved = r.get("dissolved")

        lines = [f"Partai politik: {name} ({abbrev})"]
        lines.append(f"Didirikan: {founded or '?'}")
        if dissolved:
            lines.append(f"Dibubarkan: {dissolved}")
        if ideology:
            lines.append(f"Ideologi: {', '.join(ideology)}")

        leaders = r.get("leaders", [])
        if leaders:
            lines.append("Pimpinan:")
            for ld in leaders:
                pid = ld.get("person_id", "?")
                lfrom = ld.get("from", "?")
                lto = ld.get("to", "sekarang")
                lines.append(f"  - {pid} ({lfrom} - {lto or 'sekarang'})")

        return "\n".join(lines)

    def _build_election_text(self, r: dict[str, Any]) -> str:
        eid = r.get("id", "?")
        date = r.get("date", "?")
        level = r.get("level", "?")
        scope = r.get("scope", "?")
        jid = r.get("jurisdiction_id", "?")
        turnout = r.get("turnout_pct")

        lines = [f"Pemilihan umum: {eid}"]
        lines.append(f"Tanggal: {date} | Level: {level} | Lingkup: {scope} | Yurisdiksi: {jid}")
        if turnout:
            lines.append(f"Tingkat partisipasi: {turnout}%")

        for c in r.get("contests", []):
            office = c.get("office", "?")
            district = c.get("district", "")
            district_str = f" daerah {district}" if district else ""
            lines.append(f"Kontes: {office}{district_str}")
            for res in c.get("results", []):
                cand = res.get("candidate_id", "?")
                party = res.get("party_id", "?")
                votes = res.get("votes")
                pct = res.get("pct", 0.0)
                vote_str = f", {votes:,} suara" if votes else ""
                lines.append(f"  - {cand} (partai: {party or 'independen'}){vote_str}, {pct}%")

        return "\n".join(lines)

    def _build_jurisdiction_text(self, r: dict[str, Any]) -> str:
        name = r.get("name", "?")
        jid = r.get("id", "?")
        kind = r.get("kind", "?")
        parent = r.get("parent_id", "")
        valid_from = r.get("valid_from", "?")
        valid_to = r.get("valid_to")
        codes = r.get("codes", {})

        lines = [f"Yurisdiksi: {name} ({jid})"]
        lines.append(f"Jenis: {kind}")
        if parent:
            lines.append(f"Induk: {parent}")
        lines.append(f"Berlaku: {valid_from} - {valid_to or 'sekarang'}")
        if codes:
            code_str = ", ".join(f"{k}={v}" for k, v in codes.items())
            lines.append(f"Kode: {code_str}")

        return "\n".join(lines)

    def _extract_metadata(self, record: dict[str, Any]) -> dict[str, Any]:
        """Extract flat metadata from record for Qdrant payload.

        IMPORTANT: Qdrant payloads must be flat (no nested dicts).
        """
        meta: dict[str, Any] = {
            "domain": "politics-id",
            "record_type": record.get("type", "unknown"),
            "record_id": record.get("id", ""),
        }
        if record.get("qid"):
            meta["qid"] = record["qid"]
        if record.get("name"):
            meta["name"] = record["name"]
        if record.get("abbrev"):
            meta["abbrev"] = record["abbrev"]
        if record.get("date"):
            meta["date"] = record["date"]
        source_count = len(record.get("sources", []) or [])
        meta["source_count"] = source_count
        return meta
