"""ARCH-3: Adaptive Query Decomposer.

Replaces static L1/L2 hardcoded queries with Ollama-driven decomposition.
Takes a research objective and cluster context, returns 2-5 targeted sub-queries.

Design:
- Primary: Ollama qwen3.5:9b (local, free, fast)
- Fallback: static templates from pipeline.py (backward compatible)
- Output: structured list of query strings with metadata

Usage:
    from apps.evaluator.nlm_deep_research.query_decomposer import QueryDecomposer

    decomposer = QueryDecomposer()
    queries = decomposer.decompose(
        objective="Monitor KITAS changes 2026",
        cluster="B",
        level="L1",
        domain="immigration",
    )
    # Returns: ["query1", "query2", ...]  (2-5 queries)

Cron: runs inside pipeline per invocation — no separate cron needed.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Ollama config ─────────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.5:9b"      # Primary — 6.6GB, fast, local
OLLAMA_TIMEOUT = 60               # seconds
MAX_QUERIES_PER_DECOMPOSITION = 4
MIN_QUERIES_PER_DECOMPOSITION = 2

# ── Research objectives per domain+cluster ────────────────────────────────────

# These are used as context for the LLM decomposer, not as the final queries.
# Maps (domain, cluster) → research objective text.
CLUSTER_OBJECTIVES = {
    # NB-2: Immigration & Visa Indonesia
    ("immigration", "A"): "Monitor latest changes to RPTKA, DKP-TKA work permit regulations for foreign workers in Indonesia 2025-2026",
    ("immigration", "B"): "Monitor KITAS to KITAP conversion, limited stay permit extensions, family reunification for foreigners in Indonesia 2025-2026",
    ("immigration", "C"): "Monitor Visit Visa changes: VOA, e-VOA, C1, C2, visa run rules, visit permit extensions in Indonesia 2025-2026",
    ("immigration", "D"): "Monitor Second Home visa, Golden Visa E28, retirement visa E33E/F, Digital Nomad E33G in Indonesia 2025-2026",
    ("immigration", "E"): "Monitor overstay penalties, deportation rules, Tim Pora enforcement in Bali 2025-2026",
    # NB-3: Company Setup
    ("company", "A"): "Monitor PT PMA registration process changes, OSS NIB requirements, BKPM rules Indonesia 2025-2026",
    ("company", "B"): "Monitor minimum capital requirements, shareholder rules, KBLI changes for PT PMA Indonesia 2025-2026",
    ("company", "C"): "Monitor PT PMDN setup requirements, local company rules, tax registration Indonesia 2025-2026",
    ("company", "D"): "Monitor representative office KPPA rules, branch office requirements Indonesia 2025-2026",
    ("company", "E"): "Monitor company compliance, annual report obligations, GMS requirements Indonesia 2025-2026",
    # NB-4: Tax
    ("tax", "A"): "Monitor CoreTax system changes, PPh 21 employer obligations, NPWP requirements Indonesia 2025-2026",
    ("tax", "B"): "Monitor PPN/VAT rate changes, e-faktur requirements, PKP registration Indonesia 2025-2026",
    ("tax", "C"): "Monitor transfer pricing, CbCR, BEPS compliance for multinationals Indonesia 2025-2026",
    ("tax", "D"): "Monitor personal income tax rates, tax treaty benefits for foreign nationals Indonesia 2025-2026",
    ("tax", "E"): "Monitor tax audit procedures, tax dispute resolution, DJP enforcement Indonesia 2025-2026",
    # NB-5: Property
    ("property", "A"): "Monitor foreign property ownership rules, HGB, Hak Pakai regulations Indonesia 2025-2026",
    ("property", "B"): "Monitor leasehold agreements, notarial requirements for property transactions Bali 2025-2026",
    ("property", "C"): "Monitor PPJB, AJB property sale procedures, taxes on property transfers Indonesia 2025-2026",
    ("property", "D"): "Monitor strata title, apartment ownership rules for foreigners Indonesia 2025-2026",
    ("property", "E"): "Monitor zoning regulations, Bali spatial planning, building permits IMBT Indonesia 2025-2026",
    # NB-6: Operations
    ("operations", "A"): "Monitor BPJS Ketenagakerjaan and Kesehatan obligations for employers Indonesia 2025-2026",
    ("operations", "B"): "Monitor minimum wage UMR/UMP changes, labor law Omnibus Law implementation Bali 2025-2026",
    ("operations", "C"): "Monitor halal certification requirements, BPOM food safety regulations Indonesia 2025-2026",
    ("operations", "D"): "Monitor OSS business license renewals, NIB compliance requirements Indonesia 2025-2026",
    ("operations", "E"): "Monitor UU PDP data protection compliance requirements Indonesia 2025-2026",
    # NB-7: Editorial (generic clusters)
    ("editorial", "A"): "Monitor AI content regulations, digital marketing rules Indonesia 2025-2026",
    ("editorial", "B"): "Monitor SEO algorithm changes, content strategy trends Indonesia 2025-2026",
    # NB-8: Lifestyle
    ("lifestyle", "A"): "Monitor expat banking regulations, remittance rules for foreigners in Bali 2025-2026",
    ("lifestyle", "B"): "Monitor health insurance requirements, BPJS access for foreigners Indonesia 2025-2026",
}

# ── Decomposer prompt ─────────────────────────────────────────────────────────

DECOMPOSE_SYSTEM_PROMPT = """You are a research query decomposer for an Indonesian regulatory monitoring system.
You receive a research OBJECTIVE and must output 2-4 specific, targeted queries to send to a NotebookLM notebook.
The notebook contains Indonesian regulatory documents, laws, and government circulars.

Rules:
- Each query must be self-contained and specific
- Queries should cover different angles of the objective
- Use Indonesian (Bahasa Indonesia) for operational queries (level L1)
- Use English for comparative/analytical queries (level L2)
- Each query ends with: "Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi." (for L1)
- For L2: "Answer based ONLY on source documents. Cite source file names."
- Output ONLY a JSON array of strings: ["query1", "query2", ...]
- No explanation, no markdown, JUST the JSON array"""

DECOMPOSE_USER_TEMPLATE = """Decompose this research objective into {n} targeted queries.

OBJECTIVE: {objective}
LEVEL: {level} ({level_desc})
CLUSTER: {cluster} — {cluster_name}
DOMAIN: {domain}

Output {n} queries as a JSON array."""


@dataclass
class DecompositionResult:
    queries: list[str]
    source: str  # "ollama" | "static_fallback" | "error_fallback"
    model: str
    latency_ms: int
    objective: str
    cluster: str
    level: str


# ── Static fallback templates ─────────────────────────────────────────────────
# Mirrored from pipeline.py — used when Ollama is unavailable

_STATIC_L1: dict[str, str] = {
    "A": "Berikan update terbaru tentang peraturan RPTKA, DKP-TKA, dan izin kerja TKA di Indonesia tahun 2025-2026. Apakah ada perubahan prosedur, tarif, atau persyaratan baru? Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
    "B": "Berikan update terbaru tentang konversi KITAS ke KITAP, perpanjangan izin tinggal terbatas, dan penyatuan keluarga WNA di Indonesia tahun 2025-2026. Apakah ada perubahan persyaratan? Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
    "C": "Berikan update terbaru tentang Visa Kunjungan (VOA, e-VOA, C1, C2), perpanjangan izin tinggal kunjungan, dan aturan visa run di Indonesia tahun 2025-2026. Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
    "D": "Berikan update terbaru tentang visa Second Home, Golden Visa E28, visa pensiun E33E/E33F, dan visa Digital Nomad E33G di Indonesia tahun 2025-2026. Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
    "E": "Berikan update terbaru tentang sanksi overstay, deportasi, Tim Pora, dan penegakan hukum keimigrasian di Bali tahun 2025-2026. Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
}

_STATIC_L2: dict[str, str] = {
    "A": "Bandingkan prosedur RPTKA dan DKP-TKA sebelum dan sesudah PP 34/2021. Apa yang berubah untuk perusahaan PT PMA yang ingin mempekerjakan TKA di Bali? Jawab hanya berdasarkan dokumen sumber. Cantumkan nama file referensi.",
    "B": "Bandingkan persyaratan konversi KITAS ke KITAP untuk kategori pekerja (E23), investor (E28), dan keluarga (E31). Apa perbedaan utama dalam durasi, dokumen, dan biaya? Jawab hanya berdasarkan dokumen sumber.",
    "C": "Bandingkan hak dan pembatasan pemegang VOA, C1, dan C2 di Indonesia. Aktivitas apa yang legal dan ilegal untuk masing-masing? Jawab hanya berdasarkan dokumen sumber.",
    "D": "Bandingkan syarat investasi antara Golden Visa E28B 5 tahun dan 10 tahun, serta Second Home E33B. Berapa minimum investasi dan deposit untuk masing-masing? Jawab hanya berdasarkan dokumen sumber.",
    "E": "Jelaskan perbedaan antara pencegahan (cekal), penangkalan, dan deportasi dalam hukum keimigrasian Indonesia. Kapan masing-masing diterapkan? Jawab hanya berdasarkan dokumen sumber.",
}

_LEVEL_DESCRIPTIONS = {
    "L1": "Monitoring — What changed?",
    "L2": "Comparative — How did it change?",
    "L3": "Deep analysis",
    "L4": "Synthesis",
}

_CLUSTER_NAMES = {
    "A": "Work Permits",
    "B": "Stay Permits",
    "C": "Visit Visas",
    "D": "Special Visas",
    "E": "Compliance",
}


# ── Ollama client ─────────────────────────────────────────────────────────────

def _call_ollama(
    system: str,
    user: str,
    model: str = OLLAMA_MODEL,
    timeout: int = OLLAMA_TIMEOUT,
) -> str | None:
    """Call Ollama chat endpoint. Returns response text or None on failure."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "think": False,         # Disable chain-of-thought for qwen3.5
            "temperature": 0.1,     # Low temp for consistent structured output
        },
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return result.get("message", {}).get("content", "")
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None


def _parse_query_array(text: str) -> list[str] | None:
    """Extract JSON array of strings from LLM output.

    Handles cases where the model wraps the array in markdown code fences.
    """
    if not text:
        return None
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()
    # Find the first [ ... ] block
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        if not isinstance(parsed, list):
            return None
        strings = [s for s in parsed if isinstance(s, str) and len(s.strip()) > 20]
        return strings if strings else None
    except (json.JSONDecodeError, ValueError):
        return None


# ── Main decomposer ───────────────────────────────────────────────────────────

class QueryDecomposer:
    """Adaptive query decomposer using Ollama local LLM.

    Falls back to static templates if Ollama is unavailable.
    """

    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        timeout: int = OLLAMA_TIMEOUT,
        n_queries: int = MAX_QUERIES_PER_DECOMPOSITION,
        use_cache: bool = True,
    ) -> None:
        self._model = model
        self._timeout = timeout
        self._n_queries = n_queries
        # In-memory cache: (domain, cluster, level) → queries
        self._cache: dict[tuple[str, str, str], list[str]] = {} if use_cache else {}
        self._use_cache = use_cache

    def decompose(
        self,
        cluster: str,
        level: str,
        domain: str = "immigration",
        objective: str | None = None,
    ) -> DecompositionResult:
        """Decompose research objective into targeted NLM queries.

        Args:
            cluster: Cluster letter (A-E)
            level: Query level (L1, L2, L3, L4)
            domain: Domain key (immigration, company, tax, etc.)
            objective: Optional explicit objective. If None, looked up from CLUSTER_OBJECTIVES.

        Returns:
            DecompositionResult with .queries list (guaranteed non-empty).
        """
        cache_key = (domain, cluster, level)
        if self._use_cache and cache_key in self._cache:
            logger.debug("QueryDecomposer: cache hit for %s/%s/%s", domain, cluster, level)
            return DecompositionResult(
                queries=self._cache[cache_key],
                source="cache",
                model=self._model,
                latency_ms=0,
                objective=objective or "",
                cluster=cluster,
                level=level,
            )

        # Resolve objective
        if not objective:
            objective = CLUSTER_OBJECTIVES.get(
                (domain, cluster),
                f"Monitor {domain} regulatory changes for cluster {cluster} Indonesia 2025-2026",
            )

        level_desc = _LEVEL_DESCRIPTIONS.get(level, level)
        cluster_name = _CLUSTER_NAMES.get(cluster, cluster)

        # Build prompt
        user_msg = DECOMPOSE_USER_TEMPLATE.format(
            n=self._n_queries,
            objective=objective,
            level=level,
            level_desc=level_desc,
            cluster=cluster,
            cluster_name=cluster_name,
            domain=domain,
        )

        t0 = time.monotonic()
        response = _call_ollama(DECOMPOSE_SYSTEM_PROMPT, user_msg, self._model, self._timeout)
        latency_ms = int((time.monotonic() - t0) * 1000)

        if response:
            queries = _parse_query_array(response)
            if queries and MIN_QUERIES_PER_DECOMPOSITION <= len(queries) <= 6:
                # Cap to max
                queries = queries[:MAX_QUERIES_PER_DECOMPOSITION]
                if self._use_cache:
                    self._cache[cache_key] = queries
                logger.info(
                    "QueryDecomposer: Ollama decomposed %s/%s/%s into %d queries (%dms)",
                    domain, cluster, level, len(queries), latency_ms,
                )
                return DecompositionResult(
                    queries=queries,
                    source="ollama",
                    model=self._model,
                    latency_ms=latency_ms,
                    objective=objective,
                    cluster=cluster,
                    level=level,
                )
            else:
                logger.warning(
                    "QueryDecomposer: Ollama response not parseable as query array, "
                    "using static fallback. Response: %s",
                    (response or "")[:200],
                )

        # Static fallback
        fallback_query = self._static_fallback(level, cluster)
        logger.info(
            "QueryDecomposer: using static fallback for %s/%s/%s",
            domain, cluster, level,
        )
        return DecompositionResult(
            queries=[fallback_query],
            source="static_fallback",
            model="static",
            latency_ms=latency_ms,
            objective=objective,
            cluster=cluster,
            level=level,
        )

    def decompose_first(self, cluster: str, level: str, domain: str = "immigration") -> str:
        """Convenience: return only the first (primary) query string.

        Drop-in replacement for pipeline._build_query().
        """
        result = self.decompose(cluster=cluster, level=level, domain=domain)
        return result.queries[0]

    def _static_fallback(self, level: str, cluster: str) -> str:
        """Return static fallback query (mirrors pipeline.py templates)."""
        if level == "L1":
            return _STATIC_L1.get(cluster, _STATIC_L1["A"])
        if level == "L2":
            return _STATIC_L2.get(cluster, _STATIC_L2["A"])
        return (
            f"Analisis mendalam tentang Cluster {cluster} — dampak perubahan regulasi "
            f"keimigrasian 2024-2026 terhadap operasi di Bali. Jawab hanya berdasarkan dokumen sumber."
        )

    def clear_cache(self) -> None:
        self._cache.clear()


# ── Module-level singleton ────────────────────────────────────────────────────

_default_decomposer: QueryDecomposer | None = None


def get_decomposer() -> QueryDecomposer:
    """Get the module-level QueryDecomposer singleton."""
    global _default_decomposer
    if _default_decomposer is None:
        _default_decomposer = QueryDecomposer()
    return _default_decomposer


def decompose_query(
    cluster: str,
    level: str,
    domain: str = "immigration",
    objective: str | None = None,
) -> DecompositionResult:
    """Module-level convenience function using singleton decomposer."""
    return get_decomposer().decompose(cluster=cluster, level=level, domain=domain, objective=objective)
