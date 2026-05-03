"""ARCH-4: Cross-Notebook Intelligence Correlator.

Detects multi-domain queries and fan-outs to multiple NotebookLM notebooks
in parallel. Extracts atomic claims from each response, builds a correlation
matrix (AGREE / CONTRADICT / COMPLEMENT), and synthesizes a unified answer
via Ollama qwen3.5:9b local model.

Design:
- Domain detection: keyword overlap (same as resolve_notebook in registry)
- Fan-out: concurrent subprocess NLM CLI calls
- Claim extraction: sentence-level with domain tagging
- Correlation: keyword/semantic overlap scoring
- Synthesis: Ollama qwen3.5:9b (local, no API key)
- Integration: called by orchestrator when 2+ domains match

Usage (standalone):
    from apps.evaluator.nlm_deep_research.cross_notebook_correlator import CrossNotebookCorrelator

    correlator = CrossNotebookCorrelator()
    result = correlator.query(
        "Aprire PT PMA: che visa serve, che tasse pago, posso comprare proprietà?"
    )
    # result.domains_matched = ["immigration", "company", "tax", "property"]
    # result.synthesis = "unified answer..."
    # result.contradictions = [{"claim_a": ..., "claim_b": ..., "severity": "HIGH"}]

Usage (in orchestrator — async):
    result = await correlator.query_async(query)

Cron: no dedicated cron — called on-demand from orchestrator.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

NLM_QUERY_TIMEOUT = 90       # seconds per notebook query
MAX_NOTEBOOKS_PER_QUERY = 4  # max fan-out (memory pressure)
MIN_DOMAINS_FOR_CROSS = 2    # minimum domains to trigger cross-query

# Ollama (synthesis)
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_TIMEOUT = 60

# Domain keyword registry (mirrors nlm_notebook_registry.py)
DOMAIN_REGISTRY: dict[str, dict[str, Any]] = {
    "immigration": {
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",
        "label": "Immigration & Visa",
        "keywords": {"visa", "kitas", "kitap", "tka", "immigration", "imigrasi",
                     "work permit", "stay permit", "foreigner", "expat"},
    },
    "company": {
        "notebook_id": "933509f9-1561-403d-bd44-4a7a67a36df2",
        "label": "Company & Licensing",
        "keywords": {"company", "kbli", "pma", "oss", "licensing", "nib",
                     "investment", "business", "pt ", "perseroan"},
    },
    "tax": {
        "notebook_id": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",
        "label": "Tax & Compliance",
        "keywords": {"tax", "compliance", "lkpm", "npwp", "pph", "ppn",
                     "coretax", "bpjs", "fiscal", "pajak"},
    },
    "property": {
        "notebook_id": "d9438180-5e63-4e2a-a473-6061101f6a8d",
        "label": "Property & Zoning",
        "keywords": {"property", "zoning", "land", "hgb", "hak pakai",
                     "building", "villa", "real estate", "leasehold"},
    },
    "operations": {
        "notebook_id": "85207af3-352f-4554-8d2a-18f42cc541ba",
        "label": "Operations",
        "keywords": {"sop", "team", "pricing", "crm", "workflow",
                     "competitor", "bpjs", "umr", "salary"},
    },
    "editorial": {
        "notebook_id": "f51ab8a0-50d0-49f1-a64f-ebc131fed7b8",
        "label": "Editorial & Market",
        "keywords": {"seo", "content", "market", "intel", "trends",
                     "news", "article", "editorial"},
    },
    "lifestyle": {
        "notebook_id": "4fd8cd0f-93f1-4e43-9c9e-86c0d581852c",
        "label": "Expat Life",
        "keywords": {"lifestyle", "expat", "healthcare", "cost of living",
                     "culture", "digital nomad", "education", "school"},
    },
}


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class NotebookResponse:
    domain: str
    notebook_id: str
    label: str
    response: str | None
    error: str | None = None
    latency_ms: int = 0


@dataclass
class CorrelationEntry:
    claim_a: str
    domain_a: str
    claim_b: str
    domain_b: str
    relationship: str  # "AGREE" | "CONTRADICT" | "COMPLEMENT"
    confidence: float  # 0.0 - 1.0


@dataclass
class CrossNotebookResult:
    query: str
    domains_matched: list[str]
    notebook_responses: list[NotebookResponse]
    correlations: list[CorrelationEntry]
    contradictions: list[CorrelationEntry]  # subset where relationship == CONTRADICT
    synthesis: str
    synthesis_source: str   # "ollama" | "concatenation_fallback"
    total_latency_ms: int
    errors: list[str] = field(default_factory=list)

    @property
    def has_contradictions(self) -> bool:
        return len(self.contradictions) > 0

    @property
    def successful_domains(self) -> list[str]:
        return [r.domain for r in self.notebook_responses if r.response and not r.error]


# ── Domain detection ──────────────────────────────────────────────────────────

def detect_domains(query: str, threshold: int = 1) -> list[str]:
    """Return list of domain keys that match the query.

    Args:
        query: User query text
        threshold: Minimum keyword matches to include domain (default 1)

    Returns:
        List of domain keys ordered by match score (descending).
    """
    query_lower = query.lower()
    scored: list[tuple[int, str]] = []

    for domain, data in DOMAIN_REGISTRY.items():
        score = sum(1 for kw in data["keywords"] if kw in query_lower)
        if score >= threshold:
            scored.append((score, domain))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [domain for _, domain in scored[:MAX_NOTEBOOKS_PER_QUERY]]


def is_multi_domain(query: str) -> bool:
    """Return True if query spans 2+ domains (triggers cross-notebook mode)."""
    return len(detect_domains(query)) >= MIN_DOMAINS_FOR_CROSS


# ── NLM query ─────────────────────────────────────────────────────────────────

def _query_notebook_sync(notebook_id: str, query: str) -> tuple[str | None, str | None]:
    """Query a single notebook via nlm CLI. Returns (response, error)."""
    try:
        result = subprocess.run(
            ["nlm", "query", "notebook", notebook_id, query],
            capture_output=True,
            text=True,
            timeout=NLM_QUERY_TIMEOUT,
        )
        if result.returncode != 0:
            return None, result.stderr.strip()[:200]
        return result.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return None, f"timeout after {NLM_QUERY_TIMEOUT}s"
    except FileNotFoundError:
        return None, "nlm CLI not found"
    except OSError as exc:
        logger.warning("Subprocess OS error querying notebook: %s", exc)
        return None, str(exc)
    except Exception as exc:
        logger.exception("Unexpected error querying notebook %s", notebook_id)
        return None, str(exc)


async def _query_notebook_async(
    domain: str,
    notebook_id: str,
    label: str,
    query: str,
) -> NotebookResponse:
    """Async wrapper for NLM query using executor pool."""
    t0 = time.monotonic()
    loop = asyncio.get_event_loop()
    response, error = await loop.run_in_executor(
        None,
        _query_notebook_sync,
        notebook_id,
        query,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    return NotebookResponse(
        domain=domain,
        notebook_id=notebook_id,
        label=label,
        response=response,
        error=error,
        latency_ms=latency_ms,
    )


# ── Claim extraction ──────────────────────────────────────────────────────────

def _extract_claims(text: str, max_claims: int = 8) -> list[str]:
    """Extract atomic claims from response text.

    Simple sentence-level extraction. Each sentence > 30 chars is a claim.
    """
    if not text:
        return []
    # Split on sentence boundaries
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    claims = []
    for s in sentences:
        s = s.strip().lstrip("- *•→")
        if len(s) > 30:
            claims.append(s[:300])
        if len(claims) >= max_claims:
            break
    return claims


# ── Correlation engine ────────────────────────────────────────────────────────

def _compute_claim_overlap(claim_a: str, claim_b: str) -> float:
    """Compute word overlap score between two claims (Jaccard-like).

    Returns 0.0 - 1.0.
    """
    if not claim_a or not claim_b:
        return 0.0
    words_a = set(claim_a.lower().split())
    words_b = set(claim_b.lower().split())
    # Remove stop words
    stop = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
            "to", "of", "for", "and", "or", "but", "that", "this", "with",
            "dari", "di", "ke", "dan", "atau", "yang", "untuk", "dengan"}
    words_a -= stop
    words_b -= stop
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


_CONTRADICT_KEYWORDS = frozenset({
    "however", "but", "contrary", "different", "unlike", "instead",
    "not", "no ", "cannot", "berbeda", "tidak", "bukan", "sebaliknya",
    "namun", "tetapi", "melainkan",
})

_AGREE_KEYWORDS = frozenset({
    "also", "similarly", "likewise", "same", "confirm", "consistent",
    "sama", "juga", "sesuai", "konfirmasi", "selaras",
})


def _classify_relationship(claim_a: str, claim_b: str, overlap: float) -> tuple[str, float]:
    """Classify relationship between two claims.

    Returns (relationship, confidence).
    relationship: "AGREE" | "CONTRADICT" | "COMPLEMENT"
    """
    if overlap < 0.05:
        # Little overlap → COMPLEMENT (different topics)
        return "COMPLEMENT", 0.7

    combined = (claim_a + " " + claim_b).lower()

    # Check for explicit contradiction signals
    contradict_score = sum(1 for kw in _CONTRADICT_KEYWORDS if kw in combined)
    agree_score = sum(1 for kw in _AGREE_KEYWORDS if kw in combined)

    if contradict_score > agree_score and overlap > 0.15:
        return "CONTRADICT", min(0.5 + contradict_score * 0.1, 0.9)
    elif agree_score > 0 or overlap > 0.25:
        return "AGREE", min(0.5 + overlap, 0.9)
    else:
        return "COMPLEMENT", 0.6


def build_correlation_matrix(
    responses: list[NotebookResponse],
    max_correlations: int = 20,
) -> list[CorrelationEntry]:
    """Build correlation matrix across all notebook responses.

    Compares all claim pairs across different domains.
    Returns at most max_correlations entries sorted by confidence (desc).
    """
    correlations: list[CorrelationEntry] = []

    # Extract claims per domain
    domain_claims: dict[str, list[str]] = {}
    for resp in responses:
        if resp.response:
            domain_claims[resp.domain] = _extract_claims(resp.response)

    domains = list(domain_claims.keys())
    # Compare pairs of domains
    for i in range(len(domains)):
        for j in range(i + 1, len(domains)):
            domain_a = domains[i]
            domain_b = domains[j]
            claims_a = domain_claims[domain_a]
            claims_b = domain_claims[domain_b]

            for ca in claims_a[:4]:  # limit per-domain pairs
                for cb in claims_b[:4]:
                    overlap = _compute_claim_overlap(ca, cb)
                    relationship, confidence = _classify_relationship(ca, cb, overlap)
                    # Only include non-trivial correlations
                    if relationship in ("CONTRADICT", "AGREE") or overlap > 0.1:
                        correlations.append(CorrelationEntry(
                            claim_a=ca,
                            domain_a=domain_a,
                            claim_b=cb,
                            domain_b=domain_b,
                            relationship=relationship,
                            confidence=confidence,
                        ))

    # Sort by confidence desc, prioritize contradictions
    correlations.sort(key=lambda c: (
        0 if c.relationship == "CONTRADICT" else 1,
        -c.confidence,
    ))
    return correlations[:max_correlations]


# ── Synthesis via Ollama ──────────────────────────────────────────────────────

_SYNTHESIS_SYSTEM = """You are a multi-domain research synthesizer for Indonesian business law.
You receive answers from multiple specialized NotebookLM notebooks on different domains
(immigration, company law, tax, property, operations).

Your task:
1. Extract key facts from each domain response
2. Identify where domains AGREE, COMPLEMENT, or CONTRADICT each other
3. Build a unified, coherent answer that integrates all domains
4. Flag any contradictions explicitly

Rules:
- Answer based ONLY on the provided domain responses
- If domains contradict, state the contradiction and both views
- Use bullet points per domain when combining information
- End with a "Key Takeaway" that synthesizes the most important cross-domain insight
- Keep total response under 800 words"""


def _call_ollama_synthesis(
    query: str,
    domain_responses: list[tuple[str, str, str]],  # [(domain, label, response)]
    contradictions: list[CorrelationEntry],
    timeout: int = OLLAMA_TIMEOUT,
) -> str | None:
    """Call Ollama for cross-domain synthesis."""
    sections = []
    for domain, label, response in domain_responses:
        sections.append(f"=== {label.upper()} ({domain}) ===\n{response[:600]}")

    contradiction_text = ""
    if contradictions:
        contradiction_text = "\n\nIDENTIFIED CONTRADICTIONS:\n" + "\n".join(
            f"- [{c.domain_a.upper()}] says: \"{c.claim_a[:150]}\"\n"
            f"  vs [{c.domain_b.upper()}] says: \"{c.claim_b[:150]}\""
            for c in contradictions[:3]
        )

    user_msg = (
        f"USER QUERY: {query}\n\n"
        f"DOMAIN RESPONSES:\n\n" + "\n\n".join(sections) +
        contradiction_text +
        "\n\nPlease synthesize all domain information into a unified answer."
    )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYNTHESIS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {"think": False, "temperature": 0.15},
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
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        logger.warning("Ollama synthesis network error: %s", exc)
        return None
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Ollama synthesis serialization error: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Unexpected error in Ollama synthesis")
        return None


def _concatenation_fallback(
    query: str,
    responses: list[NotebookResponse],
    contradictions: list[CorrelationEntry],
) -> str:
    """Simple fallback synthesis when Ollama is unavailable."""
    lines = [f"Cross-domain response for: {query}\n"]
    for resp in responses:
        if resp.response:
            lines.append(f"**{resp.label}:**")
            lines.append(resp.response[:400])
            lines.append("")

    if contradictions:
        lines.append("⚠️ **Potential Contradictions:**")
        for c in contradictions[:3]:
            lines.append(
                f"- [{c.domain_a}] vs [{c.domain_b}]: "
                f"\"{c.claim_a[:100]}\" / \"{c.claim_b[:100]}\""
            )
    return "\n".join(lines)


# ── Main correlator class ─────────────────────────────────────────────────────

class CrossNotebookCorrelator:
    """Cross-notebook intelligence correlator.

    Detects multi-domain queries, fans out to multiple NLM notebooks,
    builds correlation matrix, and synthesizes unified answers.
    """

    def __init__(
        self,
        domain_registry: dict[str, dict[str, Any]] | None = None,
        use_ollama: bool = True,
    ) -> None:
        self._registry = domain_registry or DOMAIN_REGISTRY
        self._use_ollama = use_ollama

    def detect_domains(self, query: str) -> list[str]:
        """Return ordered list of matching domain keys for the query."""
        return detect_domains(query)

    def is_multi_domain(self, query: str) -> bool:
        """Return True if query spans 2+ domains."""
        return is_multi_domain(query)

    def query(self, query: str) -> CrossNotebookResult:
        """Synchronous cross-notebook query.

        Runs NLM queries sequentially (for use in non-async contexts).
        Use query_async() for parallel execution in async contexts.
        """
        t0 = time.monotonic()
        domains = detect_domains(query)

        if len(domains) < MIN_DOMAINS_FOR_CROSS:
            return CrossNotebookResult(
                query=query,
                domains_matched=domains,
                notebook_responses=[],
                correlations=[],
                contradictions=[],
                synthesis=f"Query matches only {len(domains)} domain(s) — use single-notebook query.",
                synthesis_source="n/a",
                total_latency_ms=0,
                errors=["Insufficient domain matches for cross-notebook query"],
            )

        logger.info(
            "CrossNotebookCorrelator: fan-out to %d domains: %s",
            len(domains),
            ", ".join(domains),
        )

        # Sequential queries (sync version)
        responses: list[NotebookResponse] = []
        errors: list[str] = []

        for domain in domains:
            data = self._registry[domain]
            resp_text, err = _query_notebook_sync(data["notebook_id"], query)
            resp = NotebookResponse(
                domain=domain,
                notebook_id=data["notebook_id"],
                label=data["label"],
                response=resp_text,
                error=err,
            )
            responses.append(resp)
            if err:
                errors.append(f"{domain}: {err}")

        return self._build_result(query, domains, responses, errors, t0)

    async def query_async(self, query: str) -> CrossNotebookResult:
        """Async cross-notebook query with parallel fan-out.

        Preferred for use in async orchestrator contexts.
        """
        t0 = time.monotonic()
        domains = detect_domains(query)

        if len(domains) < MIN_DOMAINS_FOR_CROSS:
            return CrossNotebookResult(
                query=query,
                domains_matched=domains,
                notebook_responses=[],
                correlations=[],
                contradictions=[],
                synthesis=f"Query matches only {len(domains)} domain(s) — single-notebook mode.",
                synthesis_source="n/a",
                total_latency_ms=0,
                errors=["Insufficient domain matches"],
            )

        logger.info(
            "CrossNotebookCorrelator async: fan-out to %d domains: %s",
            len(domains),
            ", ".join(domains),
        )

        # Parallel async queries
        tasks = []
        for domain in domains:
            data = self._registry[domain]
            tasks.append(_query_notebook_async(
                domain=domain,
                notebook_id=data["notebook_id"],
                label=data["label"],
                query=query,
            ))

        responses: list[NotebookResponse] = await asyncio.gather(*tasks, return_exceptions=False)
        errors = [f"{r.domain}: {r.error}" for r in responses if r.error]

        return self._build_result(query, domains, list(responses), errors, t0)

    def _build_result(
        self,
        query: str,
        domains: list[str],
        responses: list[NotebookResponse],
        errors: list[str],
        t0: float,
    ) -> CrossNotebookResult:
        """Build CrossNotebookResult from collected responses."""
        # Correlation matrix
        successful = [r for r in responses if r.response]
        correlations = build_correlation_matrix(successful)
        contradictions = [c for c in correlations if c.relationship == "CONTRADICT"]

        # Synthesis
        domain_triples = [
            (r.domain, r.label, r.response)
            for r in successful
            if r.response
        ]

        synthesis = None
        synthesis_source = "concatenation_fallback"

        if self._use_ollama and domain_triples:
            synthesis = _call_ollama_synthesis(query, domain_triples, contradictions)
            if synthesis:
                synthesis_source = "ollama"

        if not synthesis:
            synthesis = _concatenation_fallback(query, successful, contradictions)

        total_ms = int((time.monotonic() - t0) * 1000)

        return CrossNotebookResult(
            query=query,
            domains_matched=domains,
            notebook_responses=responses,
            correlations=correlations,
            contradictions=contradictions,
            synthesis=synthesis,
            synthesis_source=synthesis_source,
            total_latency_ms=total_ms,
            errors=errors,
        )


# ── Module-level singleton ────────────────────────────────────────────────────

_default_correlator: CrossNotebookCorrelator | None = None


def get_correlator() -> CrossNotebookCorrelator:
    """Get the module-level CrossNotebookCorrelator singleton."""
    global _default_correlator
    if _default_correlator is None:
        _default_correlator = CrossNotebookCorrelator()
    return _default_correlator
