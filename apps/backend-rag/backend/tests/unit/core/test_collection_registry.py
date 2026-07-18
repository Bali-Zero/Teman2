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


# ── P7 (SPEC v2 D3): curated_qa collection registration ─────────────────────


def test_curated_qa_is_a_known_collection() -> None:
    assert is_known_collection("curated_qa") is True


def test_curated_qa_resolves_to_itself_physical_name() -> None:
    # No hybrid/versioned successor yet — logical name == physical name.
    assert resolve_collection_name("curated_qa") == "curated_qa"


def test_curated_qa_is_in_canonical_logical_collections() -> None:
    from backend.core.collection_registry import get_canonical_collection_names

    assert "curated_qa" in get_canonical_collection_names()


def test_curated_qa_canonicalizes_to_itself() -> None:
    from backend.core.collection_registry import canonicalize_collection_name

    assert canonicalize_collection_name("curated_qa") == "curated_qa"
