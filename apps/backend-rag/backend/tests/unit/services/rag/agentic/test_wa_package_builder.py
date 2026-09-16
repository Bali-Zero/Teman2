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

from backend.core import score_provenance
from backend.services.rag.agentic import wa_package_builder as wpb_module
from backend.services.rag.agentic._abstain_policy import build_abstain_policy
from backend.services.rag.agentic._support_signal import SupportVerdict
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

    async def test_chunks_drop_retriever_extras_to_exactly_four_keys(self) -> None:
        """The fake retriever hands back `id` + `metadata.source_path` on every
        hit (mirroring a real `format_search_results()` result) — every
        chunk in the built package must carry ONLY collection/text/score
        plus B1.1's declared `score_kind` (the fake hit declares none, so
        it reads back UNKNOWN; `score_raw` is therefore absent, not just
        empty — the hit has no `score_raw` to carry through either).
        """
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        assert package.chunks, "expected at least one chunk from the fake retriever"
        for chunk in package.chunks:
            assert set(chunk.keys()) == {"collection", "text", "score", "score_kind"}
            assert chunk["score_kind"] == score_provenance.UNKNOWN

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
# 3ter. IDENTITY authority (B2.5-1b, second authority, same order as greeting)
# ============================================================================


class TestIdentityAuthority:
    """`wa_identity.match_identity_question` is the second authority, checked
    right after `match_greeting` and by the same reasoning: a question about
    the assistant itself has no retrieval answer, so it is never an
    unbuildable package — it is a scripted turn, short-circuited by
    `wa_codex_leg` before this function is ever called on that query. This
    class is the second line of defense for any other caller."""

    async def test_identity_query_raises_unbuildable(self) -> None:
        with pytest.raises(PackageUnbuildable) as exc_info:
            await build_context_package(
                query="ciao tu sei Zantara?",
                history=[],
                thread_epoch=0,
                retriever=FakeRetriever(),
            )
        assert exc_info.value.reason == "identity_domain"

    async def test_a_case_question_with_an_identity_phrase_still_builds(self) -> None:
        """The domain-veto half: "cosa puoi fare per la mia PT PMA?" contains
        the identity phrase "cosa puoi fare" but is a real case question —
        it must build exactly like any other visa query, never raise."""
        package = await build_context_package(
            query="cosa puoi fare per la mia PT PMA?",
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        assert isinstance(package, ContextPackage)


# ============================================================================
# 3bis. GREETING authority (B2.5 PR-3, ruling d, measured defect D4)
# ============================================================================


class TestGreetingAuthority:
    """`wa_greeting.match_greeting` is the ONE authority for "is this a
    scripted greeting" — not `QueryPlanner`'s cheap keyword classifier. A
    plan the planner calls GREETING but the precise matcher rejects is not
    unbuildable any more: it builds with GENERAL's collections.
    """

    async def test_true_greeting_still_raises_greeting_domain(self) -> None:
        with pytest.raises(PackageUnbuildable) as exc_info:
            await build_context_package(
                query="Halo",
                history=[],
                thread_epoch=0,
                retriever=FakeRetriever(),
            )
        assert exc_info.value.reason == "greeting_domain"

    async def test_ordinal_prefixed_greeting_still_raises_greeting_domain(self) -> None:
        """The measured defect (D4): "11.  Halo" must be treated exactly
        like "Halo" by the SAME authority the WA leg already defers to."""
        with pytest.raises(PackageUnbuildable) as exc_info:
            await build_context_package(
                query="11.  Halo",
                history=[],
                thread_epoch=0,
                retriever=FakeRetriever(),
            )
        assert exc_info.value.reason == "greeting_domain"

    async def test_planner_greeting_disagreement_builds_with_general_collections(
        self,
    ) -> None:
        """The disagreeing shape: the planner's greeting-keyword pattern
        fires on "halo" inside this sentence and, with no other domain
        keyword scoring, GREETING wins — but the message is 8 tokens, well
        past `wa_greeting`'s 5-token/48-char greeting cap, so
        `match_greeting` refuses it. VERIFIED here with the real planner and
        the real matcher, not assumed."""
        query = "Halo, apa kabar semuanya di kantor hari ini?"
        from backend.services.integrations.wa_greeting import match_greeting
        from backend.services.rag.agentic.query_plan import QueryDomain
        from backend.services.rag.agentic.query_planner import (
            _DOMAIN_COLLECTIONS,
            QueryPlanner,
        )

        plan = QueryPlanner().plan(query)
        assert plan.domain == QueryDomain.GREETING, "fixture no longer disagrees — replace it"
        assert match_greeting(query) is None, "fixture no longer disagrees — replace it"

        retriever = FakeRetriever()
        package = await build_context_package(
            query=query,
            history=[],
            thread_epoch=0,
            retriever=retriever,
        )
        assert isinstance(package, ContextPackage)
        assert package.evidence_inputs["domain"] == "general"
        # No hits were configured on the fake, so `package.chunks` is empty —
        # the collections actually QUERIED (recorded on every call
        # regardless of hit count) are the proof GENERAL's map was used,
        # not the planner's original (empty) GREETING map.
        assert set(retriever.calls) == set(_DOMAIN_COLLECTIONS[QueryDomain.GENERAL])

    async def test_cross_authority_invariant_over_a_synthetic_corpus(self) -> None:
        """For every text below: `builder raises greeting_domain` IFF
        `match_greeting(text) is not None`. ~20 synthetic strings spanning
        true greetings, the disagreeing shape, ordinal-prefixed variants,
        real content, and the innocence set from `test_wa_greeting.py`."""
        from backend.services.integrations.wa_greeting import match_greeting

        corpus = [
            "Halo",
            "Hi",
            "Ciao!",
            "11.  Halo",
            "1) Hi",
            "3. Selamat pagi",
            "Halo, apa kabar semuanya di kantor hari ini?",
            "thank you",
            "hii",
            "makasih",
            "What documents do I need for a KITAS work permit?",
            "Berapa biaya pendirian PT PMA?",
            "11. Halo, berapa harga PT PMA?",
            "2026 halo",
            "Pasal 6. Halo",
            "1. KITAS",
            "bali zero",
            "Halo admin?",
            "xyzabc123",
            "good morning zantara",
        ]
        assert len(corpus) >= 20

        for text in corpus:
            expects_greeting_domain = match_greeting(text) is not None
            try:
                await build_context_package(
                    query=text,
                    history=[],
                    thread_epoch=0,
                    retriever=FakeRetriever(),
                )
                raised_greeting_domain = False
            except PackageUnbuildable as exc:
                raised_greeting_domain = exc.reason == "greeting_domain"

            assert raised_greeting_domain == expects_greeting_domain, (
                f"{text!r}: builder raised greeting_domain={raised_greeting_domain} "
                f"but match_greeting is not None={expects_greeting_domain}"
            )


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
        # These are recognized by `wa_greeting.match_greeting` — the ONE
        # greeting authority as of B2.5 PR-3 (ruling d) — so the builder
        # still refuses them.
        for query in ("hi", "hey", "ciao!", "hi there"):
            with pytest.raises(PackageUnbuildable):
                await build_context_package(
                    query=query,
                    history=[],
                    thread_epoch=0,
                    retriever=FakeRetriever(),
                )

    async def test_planner_only_greetings_now_build_with_general(self) -> None:
        """B2.5 PR-3 (ruling d): the planner's cheap keyword heuristic still
        scores the colloquial elongations ("hii", "heyy", "ciaooo", ...) and
        the thanks-phrases ("thank you", "makasih", "terimakasih") as
        GREETING — `wa_greeting.match_greeting` does not recognize any of
        them (it has no elongation logic and is not a thanks-detector). Under
        the OLD single-source-of-truth (planner domain alone), each of these
        was declared unbuildable — the same failure shape D4 measured for
        "11.  Halo", just for a different prefix. GREETING is no longer an
        authority on its own: these now build with GENERAL's collections
        instead of falling off the retry ladder.
        """
        for query in (
            "thank you",
            "hii",
            "heyy",
            "hellooo",
            "ciaooo",
            "halooo",
            "makasih",
            "terimakasih",
        ):
            package = await build_context_package(
                query=query,
                history=[],
                thread_epoch=0,
                retriever=FakeRetriever(),
            )
            assert isinstance(package, ContextPackage), f"{query!r} was declared unbuildable"
            assert package.evidence_inputs["domain"] == "general"


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


def _scorer_sources_and_context(package: ContextPackage) -> tuple[list[dict[str, Any]], list[str]]:
    """The EXACT sources/context shape `build_context_package` feeds
    `calculate_evidence_score` (mirrored here, not imported, so a test can
    independently recompute the expected score for a built package)."""
    sources = [
        {
            "score": chunk["score"],
            "score_kind": score_provenance.kind_of(chunk),
            "score_raw": score_provenance.raw_of(chunk),
        }
        for chunk in package.chunks
    ]
    context = [chunk["text"] for chunk in package.chunks]
    return sources, context


class TestSupportSignalWiring:
    """B2.4 PR-2 (design `B2-4-design.md` §1.1 step 1, §2 item 3): the
    builder no longer judges at all — the daemon judges the CLAIMED job
    with a real Codex seat, before generating. `evaluate_support()` itself
    stays intact (the B2.1 harness calls it directly) but this module
    never calls it any more."""

    async def test_builder_never_calls_the_judge(self) -> None:
        """Guilt: patch the judge to EXPLODE if called at all — a full
        dlp=True build (the only shape that used to consult it) must
        complete without tripping it."""

        def _explode(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError(
                "wa_package_builder called the judge — B2.4 PR-2 moved it to the daemon"
            )

        with patch(
            "backend.services.rag.agentic._support_signal.evaluate_support",
            side_effect=_explode,
        ):
            package = await build_context_package(
                query=VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
                dlp=True,
            )

        assert package.evidence_inputs["support_verdict"] is None
        assert package.evidence_inputs["support_votes"] == []
        assert package.evidence_inputs["support_judge"] == "deferred:broker"
        assert package.evidence_inputs["support_fallback_used"] is False

    async def test_dlp_false_also_never_calls_the_judge_and_reports_deferred(self) -> None:
        def _explode(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("wa_package_builder called the judge on a dlp=False build")

        with patch(
            "backend.services.rag.agentic._support_signal.evaluate_support",
            side_effect=_explode,
        ):
            package = await build_context_package(
                query=VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=_visa_retriever(),
            )

        assert package.evidence_inputs["support_verdict"] is None
        assert package.evidence_inputs["support_votes"] == []
        assert package.evidence_inputs["support_judge"] == "deferred:broker"
        assert package.evidence_inputs["support_fallback_used"] is False

    async def test_evidence_score_stays_the_support_none_value(self) -> None:
        """`evidence_score`/`abstain` keep the `support=None` "not
        consulted, no change" value — byte-identical to what a SUPPORTED
        verdict would produce (reasoning_utils.calculate_evidence_score
        L790), the only branch the daemon-side release ever reads."""
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
            dlp=True,
        )
        sources, context = _scorer_sources_and_context(package)
        expected = calculate_evidence_score(
            sources=sources, context_gathered=context, query=VISA_QUERY, support=None
        )
        assert package.evidence_inputs["evidence_score"] == expected

    async def test_evidence_inputs_carry_the_unsupported_pair_matching_the_pure_scorer(
        self,
    ) -> None:
        """The additive `evidence_score_unsupported`/`abstain_unsupported`
        pair is the SAME sources/context/query scored as though the judge
        had already ruled NOT_SUPPORTED — the carrier `wa_codex_leg`
        reaches for on every abstain disposition."""
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
            dlp=True,
        )
        sources, context = _scorer_sources_and_context(package)
        expected_unsupported = calculate_evidence_score(
            sources=sources,
            context_gathered=context,
            query=VISA_QUERY,
            support=SupportVerdict.NOT_SUPPORTED,
        )
        assert package.evidence_inputs["evidence_score_unsupported"] == expected_unsupported
        expected_abstain_unsupported = build_abstain_policy(VISA_QUERY).label_abstains(
            expected_unsupported
        )
        assert package.evidence_inputs["abstain_unsupported"] == expected_abstain_unsupported
        # Additive: none of the pre-existing keys disappear.
        assert set(package.evidence_inputs) >= {
            "evidence_score",
            "context_length",
            "domain",
            "label_threshold",
            "abstain",
            "dlp",
        }


class TestContextLengthMeaningUnchanged:
    """`context_length` KEEPS its meaning exactly (B2.1 §3): len of sealed
    chunks including curated, excluding the pricing block — pinned across
    package shapes now that support-signal wiring runs alongside it."""

    async def test_empty_package_context_length_zero(self) -> None:
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=FakeRetriever({}),
        )
        assert package.evidence_inputs["context_length"] == 0
        assert package.chunks == []

    async def test_curated_only_package_context_length_counts_curated(self) -> None:
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=FakeRetriever({}),
            curated_qa_block="[CURATED · vetted 2026-08-01]\nKITAS basics.",
        )
        assert package.evidence_inputs["context_length"] == 1
        assert len(package.chunks) == 1

    async def test_vector_only_package_context_length_counts_retrieved(self) -> None:
        package = await build_context_package(
            query=VISA_QUERY,
            history=[],
            thread_epoch=0,
            retriever=_visa_retriever(),
        )
        assert package.evidence_inputs["context_length"] == len(package.chunks)
        assert package.evidence_inputs["context_length"] == 2

    async def test_pricing_only_package_excludes_pricing_block_from_context_length(
        self,
    ) -> None:
        fake_pricing = FakePricingService(_real_pricing_result(PRICING_VISA_QUERY))
        with patch.object(wpb_module, "get_pricing_service", return_value=fake_pricing):
            package = await build_context_package(
                query=PRICING_VISA_QUERY,
                history=[],
                thread_epoch=0,
                retriever=FakeRetriever({}),
            )
        assert package.pricing_block is not None
        assert package.evidence_inputs["context_length"] == 0
        assert package.chunks == []


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


# ============================================================================
# 8. GENERAL fallback never reroutes a real question (RULING I110 C1)
# ============================================================================


class TestGeneralFallbackNeverReroutesRealQuestions:
    """Binding condition added post-review (ruling I110 C1): the GENERAL
    override for a planner/matcher disagreement (`TestGreetingAuthority`
    above) must never fire for a real, on-topic question — only for the
    narrow class the planner's cheap keyword heuristic mis-scores as
    GREETING. Proven over the B1.5 evidence-sufficiency corpus (23
    synthetic, real business/nonsense queries — loaded from disk, never
    copied) plus 8 synthetic probe texts, EVERY one of the 31 texts used
    both as-is and prefixed with one leading list ordinal ("11.  "),
    62 texts total, no network (the planner and `match_greeting` are
    both pure).
    """

    _PROBES: tuple[str, ...] = (
        "Halo",
        "11.  Halo",
        "I want to talk to a human, please",
        "Saya mau bicara dengan orang, bukan bot",
        "Berapa biaya pendirian PT PMA?",
        "What documents do I need for an E33G visa?",
        "How long does PT PMA registration take?",
        "Can I pay in two instalments?",
    )

    @staticmethod
    def _b15_texts() -> list[str]:
        import json

        fixture = (
            Path(__file__).resolve().parents[4]
            / "benchmarks"
            / "evidence_sufficiency"
            / "query_vectors_b1_5.json"
        )
        data = json.loads(fixture.read_text())
        return [item["query"] for item in data["query_list"]]

    async def _effective_domain(self, query: str) -> str:
        try:
            package = await build_context_package(
                query=query, history=[], thread_epoch=0, retriever=FakeRetriever()
            )
        except PackageUnbuildable as exc:
            return f"unbuildable:{exc.reason}"
        return str(package.evidence_inputs["domain"])

    async def test_effective_domain_diverges_from_planner_only_on_greeting(self) -> None:
        from backend.services.integrations.wa_greeting import match_greeting
        from backend.services.integrations.wa_human_handoff import match_human_request
        from backend.services.rag.agentic.query_planner import QueryPlanner

        planner = QueryPlanner()
        b15_texts = self._b15_texts()
        assert len(b15_texts) == 23, "the B1.5 fixture's query_list count changed — re-check scope"

        # Ruling I110 C1: EVERY text — the 23 B1.5 texts AND the 8 probes —
        # is exercised both as-is and with one leading list ordinal, so an
        # ordinal-prefixed real question from the B1.5 corpus is covered
        # too, not just the hand-picked probes.
        texts: list[str] = []
        for text in [*b15_texts, *self._PROBES]:
            texts.append(text)
            texts.append("11.  " + text)
        assert len(texts) == 62, "expected 23+8 texts, each as-is and ordinal-prefixed"

        divergences = 0
        for text in texts:
            planner_domain = planner.plan(text).domain.value
            effective = await self._effective_domain(text)
            mg = match_greeting(text)
            mhr = match_human_request(text)

            if effective == planner_domain:
                continue
            divergences += 1
            # B2.5-2: a human-handoff request short-circuits `build_context_
            # package` unconditionally (same authority family as greeting,
            # but never GREETING-gated) — legitimate whatever the planner's
            # raw domain was, unlike the GREETING-correction case below.
            if effective == "unbuildable:human_handoff_domain":
                assert mhr is not None, (
                    f"{text!r}: raised human_handoff_domain but match_human_request is None"
                )
                continue
            # Any OTHER divergence — either the override to GENERAL, or a
            # raised greeting_domain that the planner's raw domain doesn't
            # spell — is only legitimate when the planner itself called
            # GREETING.
            assert planner_domain == "greeting", (
                f"{text!r}: effective domain {effective!r} diverged from a "
                f"NON-greeting planner domain {planner_domain!r} — the "
                "GENERAL fallback rerouted a real question"
            )
            if effective == "unbuildable:greeting_domain":
                assert mg is not None, (
                    f"{text!r}: raised greeting_domain but match_greeting is None"
                )
            else:
                assert effective == "general" and mg is None and mhr is None, (
                    f"{text!r}: expected the GENERAL override with no scripted "
                    f"greeting match, got effective={effective!r} match_greeting={mg!r}"
                )

        assert divergences > 0, "fixture never exercises the disagreement path — dead test"


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
