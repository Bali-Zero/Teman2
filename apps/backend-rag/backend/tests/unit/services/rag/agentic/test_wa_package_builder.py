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

S2 cross-family (Codex) review round — each finding carries its own
guilt+innocence pair here:
  - finding 1: the builder must pass `fallback_to_plain=False` to
    `hybrid_search` (SearchService's default error fallback runs Gemini
    query expansion — the wiring assertion is the guard the FakeRetriever
    can actually witness);
  - finding 2: `pricing_block` is reduced to a per-field allowlist —
    contact_info (WhatsApp number, wa.me link), disclaimers and internal
    annotations are dropped by construction (the fake speaks the REAL wire
    shape measured on `PricingService.search_service`, W114);
  - findings 3+8: history is rebuilt to exactly {"role","content"} with
    capped lengths — extra keys (phone, crm_id) never reach the payload;
  - finding 4: the current query is appended as the final user turn, so it
    is in the payload AND in the hash;
  - finding 5: `to_payload()` returns a deep copy — mutating one payload
    cannot corrupt the package or a later payload;
  - finding 6: chunk order is a deterministic total order (-score,
    collection, text), independent of collection-arrival order.

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
from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score
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
    docstring in `wa_package_builder.py`). `fallback_to_plain` defaults to
    True to mirror the REAL signature, so only an explicit False from the
    builder can make the flag assertion pass.
    """

    def __init__(self, hits_by_collection: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._hits_by_collection = hits_by_collection or {}
        self.calls: list[str] = []
        self.fallback_flags: list[bool] = []

    async def hybrid_search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
        fallback_to_plain: bool = True,
    ) -> dict[str, Any]:
        self.calls.append(collection_override)
        self.fallback_flags.append(fallback_to_plain)
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


def _real_pricing_result(query: str) -> dict[str, Any]:
    """The REAL wire shape of `PricingService.search_service()` — 2026 data:
    per-category values are DICTS keyed by the public service name
    (`filtered_results[category_name] = items` on the scorer's dict path),
    NOT lists. The first draft of this fake modeled a list and thereby
    masked a sanitizer that dropped every real 2026 match (Codex S2
    re-verdict, blocker) — a fake speaking the code's imagination instead
    of the wire's is two copies of one hypothesis confirming each other
    (W114). The real-service contract test below is the standing cure: this
    fake's shape is pinned against the live JSON, not against memory.
    """
    return {
        "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026",
        "search_query": query,
        "results": {
            "kitas_permits": {
                "Working KITAS (E23)": {
                    "name": "Working KITAS (E23)",
                    "price": "Rp 5.000.000",
                    "duration": "12 months",
                    "validity": "1 year",
                    "notes": "sponsor required",
                    "_sub_block": "monthly_tax_basic",
                    "icon_id": "kitas",
                    "description_en": "internal-facing description",
                }
            }
        },
        "contact_info": {
            "whatsapp": "+62 821 3454 721",
            "wa_link": "https://wa.me/6282134547211",
            "email": "zero@balizero.com",
        },
        "disclaimer": {"it": "prezzi soggetti a variazione"},
    }


_SANITIZED_PRICING = {
    "search_query": PRICING_VISA_QUERY,
    "results": {
        "kitas_permits": {
            "Working KITAS (E23)": {
                "name": "Working KITAS (E23)",
                "price": "Rp 5.000.000",
                "duration": "12 months",
                "validity": "1 year",
                "notes": "sponsor required",
            }
        }
    },
}


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
        # The retriever-fallback LLM (S2 review, finding 1): GeminiService is
        # what SearchService's plain-search fallback would construct.
        monkeypatch.setattr(
            "backend.services.llm_clients.gemini_service.GeminiService",
            _explode,
        )

        fake_pricing = FakePricingService(_real_pricing_result(PRICING_VISA_QUERY))
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
        assert package.pricing_block == _SANITIZED_PRICING

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

    async def test_builder_disables_the_hybrid_search_llm_fallback(self) -> None:
        """finding 1 (BLOCKER): SearchService.hybrid_search's default error
        fallback is `self.search()`, which runs Gemini query expansion. The
        builder must pass fallback_to_plain=False on EVERY collection call —
        the wiring this fake can actually witness.
        """
        retriever = _visa_retriever()
        await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=retriever,
        )
        assert retriever.calls, "expected at least one hybrid_search call"
        assert retriever.fallback_flags == [False] * len(retriever.calls)


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

    async def test_history_extra_keys_are_dropped(self) -> None:
        """findings 3+8 (GUILT): a caller-supplied entry smuggling phone /
        crm_id keys must reach the payload as {"role","content"} ONLY."""
        package = await build_context_package(
            query=VISA_QUERY,
            history=[
                {
                    "role": "user",
                    "content": "earlier question",
                    "phone": "+62 812 0000 0000",
                    "crm_id": "client-42",
                }
            ],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        for turn in package.history:
            assert set(turn.keys()) == {"role", "content"}
        assert "+62 812 0000 0000" not in str(package.to_payload())

    async def test_history_content_is_capped_and_logged(self, caplog) -> None:
        """findings 3+8: an annotation caps nothing — the builder truncates
        oversized content defensively and DECLARES the truncation (W97)."""
        with caplog.at_level(
            logging.INFO, logger="backend.services.rag.agentic.wa_package_builder"
        ):
            package = await build_context_package(
                query=VISA_QUERY,
                history=[{"role": "user", "content": "x" * 10_000}],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
        assert len(package.history[0]["content"]) == wpb_module._MAX_HISTORY_CONTENT_CHARS
        assert "truncat" in caplog.text and "history" in caplog.text

    async def test_current_query_is_the_final_user_turn(self) -> None:
        """finding 4 (BLOCKER): the generator must receive the question it is
        answering — the payload history ends with the current query."""
        package = await build_context_package(
            query=VISA_QUERY,
            history=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        assert package.history[-1] == {"role": "user", "content": VISA_QUERY}

    async def test_to_payload_returns_an_independent_copy(self) -> None:
        """finding 5 (INNOCENCE of the frozen claim): mutating one payload
        must not corrupt the package or a later payload."""
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        first = package.to_payload()
        first["chunks"].clear()
        first["history"].append({"role": "user", "content": "injected"})
        second = package.to_payload()
        assert second["chunks"], "second payload lost its chunks to the first's mutation"
        assert second["history"][-1] == {"role": "user", "content": VISA_QUERY}


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
    async def test_pricing_intent_query_populates_sanitized_pricing_block(self) -> None:
        fake_pricing = FakePricingService(_real_pricing_result(PRICING_VISA_QUERY))
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=PRICING_VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
        assert package.pricing_block == _SANITIZED_PRICING
        assert fake_pricing.queries == [PRICING_VISA_QUERY]

    async def test_pricing_block_never_carries_contact_or_internal_fields(self) -> None:
        """finding 2 (BLOCKER, GUILT): the WhatsApp number, wa.me link,
        disclaimer and _sub_block annotation from the REAL wire shape must
        be dropped by construction — 'no contact info' is part of the
        allowlist, not a hope about upstream."""
        fake_pricing = FakePricingService(_real_pricing_result(PRICING_VISA_QUERY))
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=PRICING_VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
        rendered = str(package.to_payload())
        assert "+62 821 3454 721" not in rendered
        assert "wa.me" not in rendered
        assert "_sub_block" not in rendered
        assert "disclaimer" not in rendered
        assert "contact_info" not in rendered

    async def test_priceless_pricing_result_becomes_none(self) -> None:
        """finding 2 (INNOCENCE): the no-match wire shape (message +
        suggestion + contact_info, no `results`) sanitizes to None, not to
        a contact-info-only block."""
        no_match = {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026",
            "search_query": PRICING_VISA_QUERY,
            "message": "No service found",
            "suggestion": "Contact support",
            "contact_info": {"whatsapp": "+62 821 3454 721"},
        }
        fake_pricing = FakePricingService(no_match)
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=PRICING_VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
        assert package.pricing_block is None

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

    async def test_legacy_list_category_shape_still_sanitizes(self) -> None:
        """The scorer's legacy-fixture path emits `[entry, ...]` per category
        — both wire shapes must survive the allowlist (symmetry: a fix that
        covers only the shape that bit is half a fix)."""
        legacy = _real_pricing_result(PRICING_VISA_QUERY)
        legacy["results"] = {
            "kitas_permits": [
                {
                    "name": "Working KITAS (E23)",
                    "price": "Rp 5.000.000",
                    "icon_id": "kitas",
                }
            ]
        }
        fake_pricing = FakePricingService(legacy)
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=PRICING_VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
        assert package.pricing_block == {
            "search_query": PRICING_VISA_QUERY,
            "results": {
                "kitas_permits": [{"name": "Working KITAS (E23)", "price": "Rp 5.000.000"}]
            },
        }

    async def test_real_pricing_service_contract_survives_the_sanitizer(self) -> None:
        """W114 antidote at the TRUE boundary: run the REAL PricingService
        (its wire is the official 2026 JSON on disk — no network) through the
        sanitizer. This is the test the fake could never carry: if the wire
        shape drifts, THIS goes red while the fake stays green. It is exactly
        the test that would have caught the first sanitizer dropping every
        real 2026 match.
        """
        from backend.services.pricing.pricing_service import get_pricing_service

        raw = get_pricing_service().search_service("quanto costa il KITAS?")
        assert isinstance(raw.get("results"), dict) and raw["results"], (
            "real pricing lookup for KITAS returned no results — "
            "the contract test needs a matching query"
        )
        sanitized = wpb_module._sanitize_pricing_block(raw)
        assert sanitized is not None, "sanitizer dropped a REAL 2026 pricing match"
        assert set(sanitized.keys()) == {"search_query", "results"}
        rendered = str(sanitized)
        assert "contact_info" not in rendered
        assert "wa.me" not in rendered
        assert "_sub_block" not in rendered
        for category_value in sanitized["results"].values():
            entries = (
                category_value.values() if isinstance(category_value, dict) else category_value
            )
            for entry in entries:
                assert set(entry.keys()) <= set(wpb_module._PRICING_ENTRY_FIELDS)


# ============================================================================
# 4bis. Greeting word-boundary (Codex S2 re-verdict, major — scar family #3)
# ============================================================================


class TestGreetingWordBoundary:
    """`_GREETING_KEYWORDS` are short ordinary-language tokens; bare substring
    scoring turned "Which visa options are available?" into GREETING via the
    "hi" inside "which" — and GREETING is the one verdict that zeroes the
    collection list, so this PR's route would have sent real visa questions
    to the Gemini leg as `unbuildable`. Guilt AND innocence, per the family
    #3 antidote: no guard ships without both.
    """

    async def test_real_questions_containing_hi_substrings_build_packages(self) -> None:
        # "history" doubles as the innocence case for the elongation
        # tolerance: \b + "hi" + i* must not fire inside it.
        for query in (
            "Which visa options are available?",
            "What is this visa?",
            "What is the history of visa regulations?",
        ):
            package = await build_context_package(
                query=query,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )
            assert isinstance(package, ContextPackage), f"{query!r} was declared unbuildable"

    def test_elongation_does_not_fire_mid_sentence(self) -> None:
        """Codex round 4: 'What is an HII region?' lowercases to a
        mid-sentence 'hii' — the elongated form is a colloquial OPENER, so
        it only counts at the start of the message; mid-sentence it is
        jargon, never a greeting."""
        from backend.services.rag.agentic.query_planner import QueryDomain, QueryPlanner

        plan = QueryPlanner().plan("What is an HII region?")
        assert plan.domain is not QueryDomain.GREETING

    async def test_actual_greetings_still_gate(self) -> None:
        # Includes the colloquial elongations WhatsApp greetings actually
        # arrive in (Codex round 3: a strict trailing \b regressed these)
        # and the Indonesian colloquial thanks the old substring matcher
        # never covered either.
        for query in (
            "hi",
            "hey",
            "ciao!",
            "thank you",
            "hi there",
            "hii",
            "heyy",
            "hellooo",
            "ciaooo",
            "halooo",
            "makasih",
            "terimakasih",
        ):
            with pytest.raises(PackageUnbuildable):
                await build_context_package(
                    query=query,
                    history=[],
                    thread_epoch=0,
                    retriever=FakeRetriever(),
                )


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

    async def test_different_query_same_history_changes_the_hash(self) -> None:
        """finding 4 (GUILT): two different questions over identical history
        and identical retrieval must never share a package_hash."""
        hits = {
            "visa_oracle": [_hit("KITAS requires a sponsor letter and passport copy.", 0.82)],
            "legal_unified_hybrid": [_hit("Immigration law UU 6/2011 governs stay permits.", 0.55)],
        }
        package_a = await build_context_package(
            query="What documents do I need for a KITAS work permit?",
            history=[{"role": "user", "content": "hi"}],
            thread_epoch=3,
            retriever=FakeRetriever(hits),
        )
        package_b = await build_context_package(
            query="How long does a KITAS work permit renewal take?",
            history=[{"role": "user", "content": "hi"}],
            thread_epoch=3,
            retriever=FakeRetriever(hits),
        )
        assert package_a.package_hash != package_b.package_hash

    async def test_chunk_order_is_independent_of_collection_arrival_order(self) -> None:
        """finding 6 (MAJOR): QueryPlanner merges cross-domain collections
        through a set (per-process iteration order). The package must not
        depend on it — proven with score-TIED hits, where only the
        deterministic (collection, text) tiebreak keeps the order stable."""
        hits = {
            "visa_oracle": [_hit("Visa fact.", 0.60)],
            "legal_unified_hybrid": [_hit("Legal fact.", 0.60)],
        }
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=FakeRetriever(hits),
        )
        assert [c["collection"] for c in package.chunks] == sorted(
            c["collection"] for c in package.chunks
        )


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
# 6bis. The price book counts as evidence
# ============================================================================


COMPANY_PRICE_QUERY = "Harga PT PMA berapa all in?"
UNRELATED_PRICE_QUERY = "Harga sewa motor matic di Canggu berapa per bulan?"


def _pt_pma_pricing_result(query: str) -> dict[str, Any]:
    """A catalogue hit for the PT PMA setup service, in the real 2026 wire
    shape. Mirrors the live entry the bot was holding on 2026-09-01 when it
    refused to quote it."""
    return {
        "official_notice": "PREZZI UFFICIALI BALI ZERO 2026",
        "search_query": query,
        "results": {
            "company_services": {
                "New Company - PT PMA": {
                    "name": "New Company - PT PMA",
                    "price": "Rp 20.000.000",
                    "notes": "All-inclusive price.",
                    "_sub_block": "internal",
                }
            }
        },
        "contact_info": {"whatsapp": "+62 821 3454 721"},
    }


def _company_retriever() -> FakeRetriever:
    """What QueryDomain.COMPANY actually routes to — regulatory corpora that
    say nothing about what Bali Zero charges. This is the retrieval reality
    that made the live query abstain."""
    return FakeRetriever(
        {
            "legal_unified_hybrid": [
                _hit("UU 40/2007 governs limited liability companies and their organs.", 0.31),
            ],
            "kbli_2025_final": [
                _hit("KBLI 70209 covers other management consultancy activities.", 0.28),
            ],
        },
    )


class TestPricingCountsAsEvidence:
    """Guilt and innocence for the fix to the live 2026-09-01 false abstain.

    GUILT: the bot held Rp 20.000.000 in `pricing_block` and still answered
    "saya tidak punya sumber yang pasti". INNOCENCE: the same mechanism must
    not license an answer when the catalogue hit does not actually match the
    question — otherwise the cure is just a louder bug.
    """

    async def test_catalogue_hit_is_counted_as_evidence(self) -> None:
        """What THIS change delivers: the price book stops being invisible to
        the evidence calculation.

        It deliberately does NOT assert that the abstain clears. Measured on
        the live query (2026-09-01, Indonesian, English catalogue): counting
        the price moves the score 0.04 -> 0.08 against a 0.15 threshold, so
        the refusal survives for a SECOND, INDEPENDENT and INHERITED reason —
        `calculate_evidence_score` derives relevance from lexical overlap, so
        an Indonesian question scores ~0.08 against English context and ~0.80
        against the same content in Indonesian (a factor of ten decided by
        language alone), and its `len(w) > 3` keyword filter discards the very
        tokens that identify the subject ("PT", "PMA", "NIB", "OSS").

        Asserting `abstain is False` here would make this test a claim about a
        defect this diff does not touch, and it would go green only when
        someone fixed something else. The cross-language scorer is specified
        separately in `research/operations/2026-09-01-wa-evidence-relevance-cross-language-spec.md`.
        """
        fake_pricing = FakePricingService(_pt_pma_pricing_result(COMPANY_PRICE_QUERY))
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=COMPANY_PRICE_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_company_retriever(),
            )
            chunks_only = calculate_evidence_score(
                sources=[{"score": c["score"]} for c in package.chunks],
                context_gathered=[c["text"] for c in package.chunks],
                query=COMPANY_PRICE_QUERY,
            )

        assert package.pricing_block is not None, "precondition: the price was retrieved"
        # The regression itself: evidence must count what was retrieved, not
        # only the slice that came from the vector store.
        assert package.evidence_inputs["context_length"] > len(package.chunks)
        assert package.evidence_inputs["evidence_score"] > chunks_only, (
            "the price book must raise the evidence score; scoring chunks alone "
            "is what let the builder refuse a price it was holding"
        )

    async def test_pricing_evidence_does_not_rescue_an_unrelated_query(self) -> None:
        """Innocence. Same populated `pricing_block`, a question it does not
        answer. `calculate_evidence_score` gates source quality behind semantic
        relevance, so a non-matching catalogue entry must leave the abstain
        standing — a populated block is never on its own a licence to answer.
        """
        fake_pricing = FakePricingService(_pt_pma_pricing_result(UNRELATED_PRICE_QUERY))
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=UNRELATED_PRICE_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_company_retriever(),
            )

        assert package.pricing_block is not None, "precondition: a block was still built"
        assert package.evidence_inputs["abstain"] is True, (
            "a catalogue entry about company setup must not license an answer "
            "about motorbike rental"
        )

    def test_helper_renders_the_service_name_not_only_the_entry(self) -> None:
        """The 2026 wire keys each entry by its public service name, and that
        name carries the words a client types ("PT PMA"). Rendering the entry
        body alone loses it, and the keyword overlap that drives relevance
        never fires — the failure mode that made this fix look inert."""
        texts = wpb_module._pricing_evidence_texts(
            {
                "search_query": COMPANY_PRICE_QUERY,
                "results": {
                    "company_services": {
                        "New Company - PT PMA": {"name": "New Company - PT PMA", "price": "Rp 20.000.000"}
                    }
                },
            },
        )
        assert texts and "PT PMA" in texts[0]

    def test_absent_pricing_block_contributes_nothing(self) -> None:
        assert wpb_module._pricing_evidence_texts(None) == []
        assert wpb_module._pricing_evidence_texts({"results": {}}) == []


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


def test_wire_text_is_exactly_the_bytes_package_hash_covers() -> None:
    """Codex S2 re-verdict r5, finding 1 (GUILT): the hash domain and the
    wire bytes must be the SAME function's output. Before wire_text()
    existed, the only serialization on offer was to_payload() — 7 fields
    INCLUDING package_hash — so a broker recomputing sha256 over the
    received bytes rejected every healthy package by construction."""
    import hashlib
    import json

    fields: dict[str, Any] = {
        "history": [{"role": "user", "content": "hi"}],
        "chunks": [{"text": "chunk", "source": "s"}],
        "pricing_block": {"category": {"svc": {"price": "1"}}},
        "persona_digest": "digest",
        "evidence_inputs": {"domain": "visa"},
        "thread_epoch": 3,
    }
    pkg = ContextPackage(package_hash=wpb_module._package_hash(**fields), **fields)

    wire = pkg.wire_text()
    assert hashlib.sha256(wire.encode("utf-8")).hexdigest() == pkg.package_hash
    # The wire is the 6-field envelope — the hash travels BESIDE it, never
    # inside it (a hash cannot cover bytes that contain themselves).
    assert "package_hash" not in json.loads(wire)
    # And it is NOT the to_payload() serialization, which does carry it.
    assert "package_hash" in pkg.to_payload()


def test_post_build_mutation_cannot_divorce_wire_from_hash() -> None:
    """Codex re-verdict r6, finding 2 (GUILT): frozen=True freezes the
    field bindings, not the nested lists/dicts — with a lazily-serialized
    wire, `pkg.history[-1]["content"] = ...` between build and offer made
    sha256(wire_text()) != package_hash and the broker rejected a healthy
    package. The wire is now SEALED at construction: mutating the nested
    state afterwards changes nothing on the wire."""
    import hashlib

    fields: dict[str, Any] = {
        "history": [{"role": "user", "content": "original"}],
        "chunks": [],
        "pricing_block": None,
        "persona_digest": "d",
        "evidence_inputs": {},
        "thread_epoch": 1,
    }
    pkg = ContextPackage(package_hash=wpb_module._package_hash(**fields), **fields)
    wire_before = pkg.wire_text()

    pkg.history[-1]["content"] = "tampered after build"

    assert pkg.wire_text() == wire_before
    assert hashlib.sha256(pkg.wire_text().encode("utf-8")).hexdigest() == pkg.package_hash
    assert "tampered" not in pkg.wire_text()


def test_context_package_refuses_a_hash_that_does_not_cover_its_bytes() -> None:
    """The seal is verified at construction: a package_hash that does not
    cover the wire bytes is a builder bug, refused loudly instead of
    travelling to the broker and failing there as a mystery rejection."""
    with pytest.raises(ValueError, match="does not cover"):
        ContextPackage(
            history=[],
            chunks=[],
            pricing_block=None,
            persona_digest="d",
            evidence_inputs={},
            thread_epoch=1,
            package_hash="not-the-right-hash",
        )
