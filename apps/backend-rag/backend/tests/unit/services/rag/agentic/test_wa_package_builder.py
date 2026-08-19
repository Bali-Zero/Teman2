"""BOT-V4 S2 (D1/D4): the deterministic WA codex-route package builder.

S2 acceptance criterion (spec §2.2,
research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md): "the
codex-route package builder invokes zero LLMs" — a test, not a claim. This
file proves it two ways: (1) runtime tripwires on every known LLM entry
point the codebase exposes, monkeypatched to raise if ever called while a
full package (including the pricing-intent path) is built; (2) a static
AST scan of the module's own source proving it carries no `backend.llm`
import at all — so the runtime tripwire isn't the only thing standing
between this path and an LLM call.

Also covers: the allowlist schema (exactly 7 payload keys, exactly 3 keys
per chunk even when the fake retriever hands back extra metadata), the
GREETING/no-collections `PackageUnbuildable` gate, the pricing-intent gate
(independent of QueryPlanner's domain — "quanto costa il KITAS?" classifies
as VISA by entity, but still fires the price gate), hash determinism, the
evidence-inputs freeze against the `_abstain_policy` SSOT (never a literal),
and the declared chunk cap with its log line (no silent caps — scar family
#2, W97).
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from backend.services.rag.agentic import wa_package_builder as wpb_module
from backend.services.rag.agentic._abstain_policy import build_abstain_policy
from backend.services.rag.agentic.wa_package_builder import (
    ContextPackage,
    PackageUnbuildable,
    build_context_package,
)


class FakeRetriever:
    """Stand-in for `SearchService` — canned `hybrid_search` results per collection.

    Deliberately ignores the `limit` kwarg (the fake owns exactly how many
    hits come back per collection, so a test can hand back more than the
    module's own cap to prove the cap fires) and records nothing beyond
    what a test needs — `search_collection` is intentionally NOT
    implemented, since D1 uses `hybrid_search` only (see the dispatch-choice
    docstring in `wa_package_builder.py`).
    """

    def __init__(self, hits_by_collection: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._hits_by_collection = hits_by_collection or {}
        self.calls: list[str] = []

    async def hybrid_search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
    ) -> dict[str, Any]:
        self.calls.append(collection_override)
        hits = self._hits_by_collection.get(collection_override, [])
        return {"query": query, "results": list(hits), "collection": collection_override}


def _hit(text: str, score: float, **extra_metadata: Any) -> dict[str, Any]:
    """A raw hybrid_search hit shaped like `format_search_results()`'s output —
    carrying extra fields (id/metadata/source paths) a real retriever would
    include, so the allowlist test proves they get dropped, not just that
    the happy path has few enough fields to look clean by accident.
    """
    return {
        "id": "doc-xyz",
        "text": text,
        "score": score,
        "metadata": {"source_path": "/internal/repo/path.md", **extra_metadata},
    }


VISA_QUERY = "What documents do I need for a KITAS work permit?"
GREETING_QUERY = "ciao!"
PRICING_VISA_QUERY = "quanto costa il KITAS?"
KBLI_QUERY = "KBLI business classification codes lookup"


def _visa_retriever() -> FakeRetriever:
    return FakeRetriever(
        {
            "visa_oracle": [_hit("KITAS requires a sponsor letter and passport copy.", 0.82)],
            "legal_unified_hybrid": [_hit("Immigration law UU 6/2011 governs stay permits.", 0.55)],
        },
    )


class FakePricingService:
    def __init__(self, result: dict[str, Any]) -> None:
        self._result = result
        self.queries: list[str] = []

    def search_service(self, query: str) -> dict[str, Any]:
        self.queries.append(query)
        return self._result


# ============================================================================
# 1. Zero-LLM acceptance criterion
# ============================================================================


class TestZeroLLMAcceptanceCriterion:
    async def test_codex_package_builder_invokes_zero_llms(self, monkeypatch) -> None:
        """S2's named acceptance criterion. Every known LLM entry point is
        monkeypatched to explode; a FULL package build (pricing-intent query,
        multi-collection retrieval, curated_qa block present) must complete
        without tripping any of them.
        """

        def _explode(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("LLM invoked in codex package path")

        monkeypatch.setattr("backend.llm.genai_client.get_genai_client", _explode)
        monkeypatch.setattr("backend.llm.claude_oauth_client.complete_async", _explode)
        monkeypatch.setattr("backend.llm.claude_oauth_client.complete", _explode)
        monkeypatch.setattr("backend.llm.ollama_client.ollama_generate", _explode)
        monkeypatch.setattr("backend.llm.ollama_client.ollama_chat", _explode)

        fake_pricing = FakePricingService({"key": "kitas_permits", "price": "Rp 5.000.000"})
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=PRICING_VISA_QUERY,
                history=[{"role": "user", "content": "hi"}],
                thread_epoch=1,
                retriever=_visa_retriever(),
                curated_qa_block="[CURATED · vetted 2026-08-01]\nKITAS costs vary by category.",
            )

        assert isinstance(package, ContextPackage)
        assert set(package.to_payload().keys()) == {
            "history",
            "chunks",
            "pricing_block",
            "persona_digest",
            "evidence_inputs",
            "thread_epoch",
            "package_hash",
        }
        assert package.pricing_block == {"key": "kitas_permits", "price": "Rp 5.000.000"}

    def test_module_source_has_no_backend_llm_import(self) -> None:
        """Static proof, independent of the runtime tripwires above: the
        module's own SOURCE carries no `backend.llm` import statement — an
        AST walk, not a substring search, because the module's docstrings
        and comments legitimately mention "backend.llm" in prose.
        """
        source = Path(wpb_module.__file__).read_text()
        tree = ast.parse(source)
        offending: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offending.extend(
                    alias.name for alias in node.names if alias.name.startswith("backend.llm")
                )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("backend.llm"):
                    offending.append(module)
        assert offending == [], f"wa_package_builder.py imports backend.llm: {offending}"


# ============================================================================
# 2. Allowlist schema
# ============================================================================


class TestAllowlistSchema:
    async def test_to_payload_has_exactly_the_seven_keys(self) -> None:
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        assert set(package.to_payload().keys()) == {
            "history",
            "chunks",
            "pricing_block",
            "persona_digest",
            "evidence_inputs",
            "thread_epoch",
            "package_hash",
        }

    async def test_chunks_drop_retriever_extras_to_exactly_three_keys(self) -> None:
        """The fake retriever hands back `id` + `metadata.source_path` on every
        hit (mirroring a real `format_search_results()` result) — every
        chunk in the built package must carry ONLY collection/text/score.
        """
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        assert package.chunks, "expected at least one chunk from the fake retriever"
        for chunk in package.chunks:
            assert set(chunk.keys()) == {"collection", "text", "score"}


# ============================================================================
# 3. GREETING / no-collections gate
# ============================================================================


class TestUnbuildableGate:
    async def test_greeting_query_raises_unbuildable(self) -> None:
        with pytest.raises(PackageUnbuildable) as exc_info:
            await build_context_package(
                query=GREETING_QUERY,
                history=[],
                thread_epoch=0,
                retriever=FakeRetriever(),
            )
        assert exc_info.value.reason == "greeting_domain"

    async def test_real_visa_query_builds(self) -> None:
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        assert isinstance(package, ContextPackage)
        assert package.package_hash


# ============================================================================
# 4. Pricing-intent gate (independent of QueryPlanner's domain)
# ============================================================================


class TestPricingGate:
    async def test_pricing_intent_query_populates_pricing_block(self) -> None:
        fake_pricing = FakePricingService({"key": "kitas_permits", "price": "Rp 5.000.000"})
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=PRICING_VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
        assert package.pricing_block == {"key": "kitas_permits", "price": "Rp 5.000.000"}
        assert fake_pricing.queries == [PRICING_VISA_QUERY]

    async def test_non_pricing_query_leaves_pricing_block_none(self) -> None:
        fake_pricing = FakePricingService({"key": "should-not-be-used"})
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
        assert package.pricing_block is None
        assert fake_pricing.queries == []


# ============================================================================
# 5. Hash determinism
# ============================================================================


class TestHashDeterminism:
    async def test_identical_inputs_produce_identical_hash(self) -> None:
        package_a = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": "hi"}],
            thread_epoch=3,
            retriever=_visa_retriever(),
        )
        package_b = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": "hi"}],
            thread_epoch=3,
            retriever=_visa_retriever(),
        )
        assert package_a.package_hash == package_b.package_hash

    async def test_mutated_chunk_text_changes_the_hash(self) -> None:
        baseline = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": "hi"}],
            thread_epoch=3,
            retriever=_visa_retriever(),
        )
        mutated_retriever = FakeRetriever(
            {
                "visa_oracle": [_hit("KITAS requires a DIFFERENT document set entirely.", 0.82)],
                "legal_unified_hybrid": [
                    _hit("Immigration law UU 6/2011 governs stay permits.", 0.55),
                ],
            },
        )
        mutated = await build_context_package(
            query=VISA_QUERY,
            history=[{"role": "user", "content": "hi"}],
            thread_epoch=3,
            retriever=mutated_retriever,
        )
        assert baseline.package_hash != mutated.package_hash


# ============================================================================
# 6. Evidence freeze against the abstain-policy SSOT
# ============================================================================


class TestEvidenceFreeze:
    async def test_label_threshold_matches_abstain_policy_ssot(self) -> None:
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        expected = build_abstain_policy(VISA_QUERY).label_threshold
        assert package.evidence_inputs["label_threshold"] == expected
        assert package.evidence_inputs["domain"] == "visa"
        assert package.evidence_inputs["context_length"] == len(package.chunks)


# ============================================================================
# 7. Declared chunk cap
# ============================================================================


class TestChunkCap:
    async def test_ten_chunks_in_eight_kept_and_drop_is_logged(self, caplog) -> None:
        ten_hits = [_hit(f"KBLI code entry number {i}.", 0.9 - i * 0.01) for i in range(10)]
        retriever = FakeRetriever({"kbli_2025_final": ten_hits})

        with caplog.at_level(
            logging.INFO, logger="backend.services.rag.agentic.wa_package_builder"
        ):
            package = await build_context_package(
                query=KBLI_QUERY,
                history=[],
                thread_epoch=0,
                retriever=retriever,
            )

        assert len(package.chunks) == 8
        assert "dropping" in caplog.text and "chunk" in caplog.text
