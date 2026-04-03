"""ARCH-3: Post-Query Gap Detector.

After a QueryDecomposer run, compares expected evidence types against
the claims actually extracted from NLM responses. Generates follow-up
queries for gaps.

Design:
- Takes NLM response text + original query objective
- Extracts claim types present (legal_ref, date, procedure, fee, authority)
- Compares against expected types for the domain
- Returns gap follow-up queries via Ollama qwen3.5:9b (same as decomposer)
- Graceful fallback to empty list if Ollama unavailable

Usage:
    from apps.evaluator.nlm_deep_research.gap_detector import GapDetector

    detector = GapDetector()
    follow_ups = detector.detect(
        objective="Monitor KITAS changes 2026",
        domain="immigration",
        nlm_response="...",
    )
    # Returns: list[str] — follow-up queries for gaps, or [] if no gaps
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Ollama config ─────────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_TIMEOUT = 45

# ── Expected evidence types per domain ───────────────────────────────────────

# Maps domain → evidence types we expect to find in a complete answer.
# If any type is absent from the NLM response, it's a gap.
EXPECTED_EVIDENCE = {
    "immigration": ["legal_ref", "validity_period", "procedure", "fee", "issuing_authority"],
    "company":     ["legal_ref", "procedure", "capital_req", "timeframe", "authority"],
    "tax":         ["legal_ref", "rate", "deadline", "reporting_procedure", "authority"],
    "property":    ["legal_ref", "ownership_type", "procedure", "restriction", "authority"],
    "operations":  ["legal_ref", "procedure", "compliance_deadline", "penalty", "authority"],
    "editorial":   ["trend", "platform", "metric", "strategy", "tool"],
    "lifestyle":   ["service", "cost", "location", "requirement", "recommendation"],
}

# Keywords that signal each evidence type is present in a text
EVIDENCE_SIGNALS = {
    "legal_ref":         ["pasal", "pp ", "pmk", "perpres", "undang", "peraturan", "uу", "regulation", "article"],
    "validity_period":   ["tahun", "bulan", "hari", "year", "month", "valid", "berlaku", "masa"],
    "procedure":         ["langkah", "prosedur", "step", "proses", "cara", "submit", "apply", "pengajuan"],
    "fee":               ["biaya", "rp ", "idr", "juta", "ribu", "fee", "cost", "tarif", "bayar"],
    "issuing_authority": ["imigrasi", "kemenaker", "bkpm", "oss", "kantor", "dirjen", "ministry"],
    "capital_req":       ["modal", "capital", "minimum", "investasi", "million", "miliar"],
    "timeframe":         ["hari kerja", "working day", "minggu", "week", "bulan", "month", "proses"],
    "authority":         ["kantor", "dinas", "kementerian", "bkpm", "oss", "notaris", "ministry"],
    "rate":              ["%", "persen", "percent", "tarif pajak", "tax rate", "pph", "ppn"],
    "deadline":          ["tenggat", "deadline", "batas waktu", "jatuh tempo", "due date"],
    "reporting_procedure": ["lapor", "spt", "efiling", "coretax", "report", "filing"],
    "penalty":           ["denda", "sanksi", "penalty", "fine", "hukuman"],
    "compliance_deadline": ["tenggat", "deadline", "batas", "wajib", "harus", "mandatory"],
    "ownership_type":    ["hak milik", "hgb", "hak pakai", "freehold", "leasehold", "strata"],
    "restriction":       ["asing", "wna", "wni", "foreign", "prohibited", "larangan", "tidak boleh"],
    "trend":             ["trend", "meningkat", "menurun", "growth", "adoption", "populer"],
    "platform":          ["instagram", "tiktok", "youtube", "linkedin", "platform", "channel"],
    "metric":            ["engagement", "reach", "impressi", "conversion", "ctr", "views"],
    "strategy":          ["strategi", "strategy", "pendekatan", "approach", "tactic"],
    "tool":              ["tool", "software", "platform", "aplikasi", "app"],
    "service":           ["layanan", "service", "fasilitas", "klinik", "gym", "coworking"],
    "cost":              ["harga", "price", "cost", "biaya", "rp", "idr"],
    "location":          ["bali", "denpasar", "seminyak", "canggu", "ubud", "area", "lokasi"],
    "requirement":       ["syarat", "requirement", "butuh", "perlu", "dokumen", "visa"],
    "recommendation":    ["rekomendasi", "recommend", "terbaik", "best", "populer", "pilih"],
}


@dataclass
class GapResult:
    """Result of gap detection on an NLM response."""
    domain: str
    objective: str
    present_types: list[str]
    missing_types: list[str]
    coverage_score: float          # 0.0–1.0
    follow_up_queries: list[str]
    used_ollama: bool = False


class GapDetector:
    """Detects knowledge gaps in NLM responses and generates follow-up queries."""

    def detect(
        self,
        objective: str,
        domain: str,
        nlm_response: str,
    ) -> GapResult:
        """Detect gaps and return follow-up queries.

        Args:
            objective: The research objective (e.g. "Monitor KITAS changes 2026").
            domain: Domain key (immigration, company, tax, property, operations,
                    editorial, lifestyle).
            nlm_response: Raw text response from NLM query.

        Returns:
            GapResult with missing_types and follow_up_queries.
        """
        expected = EXPECTED_EVIDENCE.get(domain, [])
        if not expected:
            logger.debug("No expected evidence defined for domain '%s'", domain)
            return GapResult(
                domain=domain,
                objective=objective,
                present_types=[],
                missing_types=[],
                coverage_score=1.0,
                follow_up_queries=[],
            )

        response_lower = nlm_response.lower()
        present = [
            ev_type for ev_type in expected
            if any(sig in response_lower for sig in EVIDENCE_SIGNALS.get(ev_type, []))
        ]
        missing = [ev for ev in expected if ev not in present]
        coverage = len(present) / len(expected) if expected else 1.0

        follow_ups: list[str] = []
        used_ollama = False

        if missing:
            follow_ups, used_ollama = self._generate_follow_ups(
                objective=objective,
                domain=domain,
                missing_types=missing,
            )

        logger.info(
            "Gap detection [%s]: coverage=%.0f%% present=%s missing=%s follow_ups=%d",
            domain, coverage * 100, present, missing, len(follow_ups),
        )

        return GapResult(
            domain=domain,
            objective=objective,
            present_types=present,
            missing_types=missing,
            coverage_score=coverage,
            follow_up_queries=follow_ups,
            used_ollama=used_ollama,
        )

    def _generate_follow_ups(
        self,
        objective: str,
        domain: str,
        missing_types: list[str],
    ) -> tuple[list[str], bool]:
        """Generate follow-up queries for missing evidence types via Ollama.

        Falls back to simple template queries if Ollama is unavailable.
        """
        # Try Ollama first
        try:
            result = self._ollama_follow_ups(objective, domain, missing_types)
            if result:
                return result, True
        except Exception as e:
            logger.debug("Ollama gap follow-up failed: %s — using fallback", e)

        # Fallback: simple templates per missing type
        return self._template_follow_ups(objective, domain, missing_types), False

    def _ollama_follow_ups(
        self,
        objective: str,
        domain: str,
        missing_types: list[str],
    ) -> list[str]:
        """Ask Ollama qwen3.5:9b to generate follow-up queries for gaps."""
        missing_str = ", ".join(missing_types)
        prompt = (
            f"Research objective: {objective}\n"
            f"Domain: {domain} (Indonesia 2025-2026)\n"
            f"Missing evidence types: {missing_str}\n\n"
            f"Write {min(len(missing_types), 3)} specific follow-up questions "
            f"(in English, max 15 words each) that would fill these gaps. "
            f"Return ONLY a JSON array of strings, no explanation."
        )

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"think": False, "temperature": 0.3},
        }

        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read())

        content = data.get("message", {}).get("content", "").strip()

        # Parse JSON array from response
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            queries = json.loads(content[start:end])
            if isinstance(queries, list):
                return [str(q).strip() for q in queries if q][:3]

        return []

    def _template_follow_ups(
        self,
        objective: str,
        domain: str,
        missing_types: list[str],
    ) -> list[str]:
        """Simple template fallback — one query per missing type."""
        templates: dict[str, str] = {
            "legal_ref":           f"What are the legal regulations governing {objective}?",
            "validity_period":     f"What is the validity period for {objective}?",
            "procedure":           f"What is the step-by-step procedure for {objective}?",
            "fee":                 f"What are the official fees and costs for {objective}?",
            "issuing_authority":   f"Which government authority issues or oversees {objective}?",
            "capital_req":         f"What are the minimum capital requirements for {objective}?",
            "timeframe":           f"What is the processing timeframe for {objective}?",
            "authority":           f"Which authority regulates {objective} in Indonesia?",
            "rate":                f"What is the current tax rate applicable to {objective}?",
            "deadline":            f"What are the reporting deadlines for {objective}?",
            "reporting_procedure": f"How to file or report {objective} to Indonesian authorities?",
            "penalty":             f"What are the penalties for non-compliance with {objective}?",
            "compliance_deadline": f"What compliance deadlines apply to {objective}?",
            "ownership_type":      f"What ownership types are available for {objective}?",
            "restriction":         f"What restrictions apply to foreigners regarding {objective}?",
        }
        return [
            templates[t] for t in missing_types[:3] if t in templates
        ]
