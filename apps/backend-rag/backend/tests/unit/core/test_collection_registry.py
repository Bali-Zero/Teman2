from backend.core.collection_registry import (
    is_known_collection,
    resolve_collection_name,
)


def test_resolve_collection_name_maps_live_kbli_collection() -> None:
    assert resolve_collection_name("kbli_2025_final") == "kbli_2025_final_hybrid"


def test_resolve_collection_name_maps_live_legal_collection() -> None:
    assert resolve_collection_name("legal_unified") == "legal_unified_hybrid_hybrid"
    assert resolve_collection_name("legal_architect") == "legal_unified_hybrid_hybrid"


def test_resolve_collection_name_preserves_unknown_values() -> None:
    assert resolve_collection_name("custom_collection") == "custom_collection"


def test_is_known_collection_only_for_registry_entries() -> None:
    assert is_known_collection("tax_genius") is True
    assert is_known_collection("custom_collection") is False
