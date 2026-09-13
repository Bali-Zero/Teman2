"""The training-data ingest gate: the local files cannot write the price split back.

RULED Zero 2026-09-11 (bot mission rc2, root cause 2 of cycle 359): the
government-fee detector that PR #5615 put in `curated_qa_harvest.py` also
guards every script that writes local `training-data/` markdown into
`training_conversations_hybrid`. The guilt strings are REAL text from that
collection (synthetic consultant dialogues, no client data); the itemised
PT PMA quote is the one the bot corner calls a worked example of the split.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import os
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

from backend.services.misc.curated_qa_government_fee_detector import (
    REVIEW_FLAG_FIELD,
    text_is_refused,
)

ITEMISED_PT_PMA_ID = (
    "- Jasa Pendirian (Akta, SK, NPWP, NIB): **IDR 20.000.000**\n"
    "- Biaya PNBP (Negara): **IDR 5.000.000**\n"
    "- Virtual Office (1 Tahun, Zona Komersial Badung): **IDR 4.500.000**\n"
    "Total Investasi Setup: **IDR 29.500.000**."
)
ITEMISED_PT_PMA_EN = (
    "- Setup Service (Deed, SK, NPWP, NIB): **IDR 20,000,000**\n"
    "- Government Fee (PNBP): **IDR 5,000,000**\n"
    "- Virtual Office (1 Year, Badung Commercial Zone): **IDR 4,500,000**\n"
    "Total Setup Investment: **IDR 29,500,000**."
)
ITEMISED_D1_JV = (
    "Kangge D1 5 Tahun niki, biaya PNBP menyang negara emang rodok dhuwur Mas, "
    "niku **IDR 15.000.000**. Jasa agency kito **IDR 3.500.000**. "
    "Dadi total **IDR 18.500.000**."
)
NAMES_THE_FEE_WITHOUT_A_FIGURE = (
    "The government fee (PNBP) is set by immigration and can change over time, "
    "so rather than quote a figure that may age, ask our team for the current one."
)
OUR_ALL_INCLUSIVE_PRICE = "Bali Zero quotes the PT PMA setup at IDR 29.500.000, all inclusive."

SPLIT = "\n<<chunk>>\n"
FILE = "training-data/business/pt_pma_quote.md"


@pytest.mark.parametrize(
    "text", [ITEMISED_PT_PMA_ID, ITEMISED_PT_PMA_EN, ITEMISED_D1_JV], ids=["id", "en", "jv"]
)
def test_an_itemised_quote_is_refused_with_a_named_reason(text: str) -> None:
    reason = text_is_refused(text)
    assert reason is not None
    assert "pnbp" in reason, "the reason names the government-fee token it saw"
    assert "all-inclusive" in reason, "the reason names the ruling it enforces"


@pytest.mark.parametrize(
    "text",
    [NAMES_THE_FEE_WITHOUT_A_FIGURE, OUR_ALL_INCLUSIVE_PRICE],
    ids=["fee-without-figure", "our-single-price"],
)
def test_a_text_with_no_government_figure_passes(text: str) -> None:
    assert text_is_refused(text) is None


def test_the_reason_offers_no_marker_that_markdown_cannot_carry() -> None:
    reason = text_is_refused(ITEMISED_PT_PMA_ID)
    assert reason is not None
    assert REVIEW_FLAG_FIELD not in reason


def _script(name: str) -> types.ModuleType:
    """Import a script without leaking its import-time side effects.

    Each one puts `apps/backend-rag/backend` at the FRONT of sys.path and loads
    `.env`; neither may outlive the import in a shared pytest process.
    """
    saved = list(sys.path)
    try:
        with mock.patch.dict(os.environ):
            return importlib.import_module(f"scripts.{name}")
    finally:
        sys.path[:] = saved


def _fake_core(
    monkeypatch: pytest.MonkeyPatch, embedded: list[str], *, awaitable: bool = False
) -> None:
    """Stand-ins for the `core.*` modules the scripts import lazily."""

    class TextChunker:
        def __init__(self, **_: object) -> None:
            pass

        def chunk_text(self, text: str) -> list[str]:
            return text.split(SPLIT)

    class Embedder:
        def generate_query_embedding(self, text: str) -> object:
            embedded.append(text)
            if not awaitable:
                return [0.0]

            async def _vector() -> list[float]:
                return [0.0]

            return _vector()

    class BM25Vectorizer:
        def generate_sparse_vector(self, text: str) -> dict:
            return {"indices": [1], "values": [1.0]}

    core = types.ModuleType("core")
    core.__path__ = []
    fakes = {
        "core": core,
        "core.chunker": {"TextChunker": TextChunker},
        "core.embeddings": {"create_embeddings_generator": lambda **_: Embedder()},
        "core.bm25_vectorizer": {"BM25Vectorizer": BM25Vectorizer},
    }
    for name, attrs in fakes.items():
        module = attrs if isinstance(attrs, types.ModuleType) else types.ModuleType(name)
        if not isinstance(attrs, types.ModuleType):
            module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)


def _corpus(root: Path, *chunks: str) -> None:
    path = root / FILE
    path.parent.mkdir(parents=True)
    path.write_text(SPLIT.join(chunks), encoding="utf-8")


def _record(sink: list[str]) -> object:
    return lambda _pid, _dense, _idx, _val, payload: sink.append(payload["text"]) or True


def test_reingest_never_embeds_or_upserts_a_refused_chunk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The consumer. Mutation-verified: `reason = None` in place of the gate call turns this red."""
    mod = _script("reingest_training_data")
    embedded: list[str] = []
    upserted_ids: list[int] = []
    _fake_core(monkeypatch, embedded)
    _corpus(tmp_path, ITEMISED_PT_PMA_ID, OUR_ALL_INCLUSIVE_PRICE)
    monkeypatch.setattr(mod, "backend_rag_root", tmp_path)
    monkeypatch.setattr(mod, "FILES_TO_REINGEST", [FILE])
    monkeypatch.setattr(mod, "upsert_point", lambda pid, *_: upserted_ids.append(pid) or True)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    mod.reingest_files()

    assert embedded == [OUR_ALL_INCLUSIVE_PRICE]
    point_id = int(hashlib.md5(f"{FILE}_1".encode()).hexdigest()[:16], 16)
    assert upserted_ids == [point_id], "ids stay keyed on the chunk index after a refusal"


def test_dry_run_reports_refusals_and_never_embeds_or_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _script("reingest_training_data")
    _fake_core(monkeypatch, [])
    monkeypatch.delitem(sys.modules, "core.embeddings")

    def _no_sink(*_: object) -> bool:
        raise AssertionError("a dry run must not write")

    monkeypatch.setattr(mod, "upsert_point", _no_sink)
    monkeypatch.setattr(mod, "backend_rag_root", tmp_path)
    _corpus(tmp_path, ITEMISED_PT_PMA_ID, NAMES_THE_FEE_WITHOUT_A_FIGURE, OUR_ALL_INCLUSIVE_PRICE)

    assert mod.dry_run([FILE]) == (3, 1)


def test_file_arguments_are_accepted_only_with_dry_run() -> None:
    mod = _script("reingest_training_data")
    with pytest.raises(SystemExit) as exc:
        mod.main([FILE])
    assert exc.value.code == 2


def test_ingest_single_file_never_embeds_a_refused_chunk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _script("ingest_single_file")
    embedded: list[str] = []
    upserted: list[str] = []
    _corpus(tmp_path, ITEMISED_PT_PMA_EN, OUR_ALL_INCLUSIVE_PRICE)
    monkeypatch.setattr(mod, "backend_rag_root", tmp_path)
    monkeypatch.setattr(mod, "chunk_text", lambda text: text.split(SPLIT))
    monkeypatch.setattr(mod, "get_openai_embedding", lambda t: embedded.append(t) or [0.0])
    monkeypatch.setattr(mod, "generate_bm25_sparse", lambda _t: {"indices": [], "values": []})
    monkeypatch.setattr(mod, "upsert_point", _record(upserted))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    mod.ingest_file(FILE)

    assert embedded == upserted == [OUR_ALL_INCLUSIVE_PRICE]


def test_ingest_license_procedures_never_embeds_a_refused_chunk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _script("ingest_license_procedures")
    embedded: list[str] = []
    upserted: list[str] = []
    _fake_core(monkeypatch, embedded, awaitable=True)
    _corpus(tmp_path, ITEMISED_D1_JV, OUR_ALL_INCLUSIVE_PRICE)

    async def _no_search(*_: object) -> dict:
        return {}

    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(mod, "backend_rag_root", tmp_path)
    monkeypatch.setattr(mod, "FILES_TO_INGEST", [FILE])
    monkeypatch.setattr(mod, "upsert_point", _record(upserted))
    monkeypatch.setattr(mod, "search_test", _no_search)
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

    asyncio.run(mod.ingest_files())

    assert embedded == upserted == [OUR_ALL_INCLUSIVE_PRICE]
