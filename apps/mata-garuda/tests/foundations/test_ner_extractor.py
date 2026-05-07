import pytest
from unittest.mock import patch, MagicMock
from mata_garuda.foundations.ner_extractor import (
    NERExtractor,
    NamedEntity,
)


def test_extract_returns_named_entities():
    fake_pipeline_output = [
        {"entity_group": "PERSON", "word": "Bimo Wijayanto", "score": 0.99, "start": 0, "end": 14},
        {"entity_group": "ORG", "word": "DJP", "score": 0.95, "start": 18, "end": 21},
    ]

    # Wave 2 fix: pipeline import is now lazy inside _get_pipeline().
    # We mock _get_pipeline directly to avoid loading transformers/torch at all.
    with patch.object(NERExtractor, "_get_pipeline") as mock_pipeline_factory:
        mock_pipeline = MagicMock(return_value=fake_pipeline_output)
        mock_pipeline_factory.return_value = mock_pipeline

        extractor = NERExtractor()
        entities = extractor.extract("Bimo Wijayanto dari DJP")

    assert len(entities) == 2
    assert isinstance(entities[0], NamedEntity)
    assert entities[0].label == "PERSON"
    assert entities[0].text == "Bimo Wijayanto"
    assert entities[1].label == "ORG"


def test_extract_empty_text_returns_empty_list():
    # Wave 2 fix: pipeline import is now lazy inside _get_pipeline().
    # We mock _get_pipeline directly to avoid loading transformers/torch at all.
    with patch.object(NERExtractor, "_get_pipeline") as mock_pipeline_factory:
        mock_pipeline = MagicMock(return_value=[])
        mock_pipeline_factory.return_value = mock_pipeline

        extractor = NERExtractor()
        entities = extractor.extract("")

    assert entities == []


def test_filter_by_label_only_returns_matching():
    fake_pipeline_output = [
        {"entity_group": "PERSON", "word": "Bimo", "score": 0.99, "start": 0, "end": 4},
        {"entity_group": "ORG", "word": "DJP", "score": 0.95, "start": 8, "end": 11},
    ]
    # Wave 2 fix: pipeline import is now lazy inside _get_pipeline().
    # We mock _get_pipeline directly to avoid loading transformers/torch at all.
    with patch.object(NERExtractor, "_get_pipeline") as mock_pipeline_factory:
        mock_pipeline = MagicMock(return_value=fake_pipeline_output)
        mock_pipeline_factory.return_value = mock_pipeline

        extractor = NERExtractor()
        people = extractor.extract("Bimo dari DJP", labels=("PERSON",))

    assert len(people) == 1
    assert people[0].text == "Bimo"


def test_pipeline_initialised_only_once_under_concurrent_calls():
    """Wave 2 fix (DeepSeek W2 + Codex W2 2026-05-08): lazy load was racy.
    Two threads could both see _pipeline=None and both call pipeline(),
    downloading the model twice. Verify the lock+double-check pattern.

    To exercise the actual lock path (not just _get_pipeline), we spy on the
    real `_get_pipeline` and assert the underlying pipeline factory ran once."""
    import threading
    import sys
    import types

    # Inject a fake `transformers` module with a counting `pipeline` factory.
    call_count = 0
    factory_lock = threading.Lock()

    def fake_pipeline(*args, **kwargs):
        nonlocal call_count
        with factory_lock:
            call_count += 1
        # Simulate slow init so threads have time to race.
        import time

        time.sleep(0.05)
        return MagicMock(return_value=[])

    fake_module = types.ModuleType("transformers")
    fake_module.pipeline = fake_pipeline
    sys.modules["transformers"] = fake_module

    try:
        extractor = NERExtractor()
        threads = [
            threading.Thread(target=lambda: extractor.extract("Bimo"))
            for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        # Restore: don't pollute other tests / module state.
        del sys.modules["transformers"]

    assert call_count == 1, (
        f"pipeline() should be called exactly once across 8 concurrent threads, "
        f"got {call_count} (race condition still present)"
    )


def test_pipeline_shared_across_instances_same_model():
    """Wave 3 fix (DeepSeek W3, 2026-05-08): old code had _pipeline as
    instance attribute, so two NERExtractor() instances each downloaded the
    same 440MB model. Now cached class-level keyed by model_name."""
    import sys
    import types

    # Reset cache so this test is independent
    from mata_garuda.foundations.ner_extractor import NERExtractor as _NE

    _NE._pipeline_cache.clear()

    call_count = 0

    def fake_pipeline(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return MagicMock(return_value=[])

    fake_module = types.ModuleType("transformers")
    fake_module.pipeline = fake_pipeline
    sys.modules["transformers"] = fake_module

    try:
        ext1 = _NE()
        ext2 = _NE()  # same default model
        ext1.extract("hello")
        ext2.extract("world")
    finally:
        del sys.modules["transformers"]
        _NE._pipeline_cache.clear()

    assert call_count == 1, (
        f"pipeline() should be called once across 2 instances of the same model, "
        f"got {call_count}"
    )
