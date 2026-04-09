"""Tests for entity resolver — the one component that doesn't need external services."""

from osint_nexus.resolver.entity_resolver import EntityResolver


def test_new_entity():
    r = EntityResolver()
    result = r.resolve({"nama": "Budi Santoso", "jabatan": "Kasi", "instansi": "Kanim NR"})
    assert result.match_method == "new"
    assert result.confidence == 1.0
    assert r.entity_count == 1


def test_nip_match():
    r = EntityResolver()
    r.resolve({"nama": "Budi Santoso", "nip": "199001012020011001"})
    result = r.resolve({"nama": "B. Santoso", "nip": "199001012020011001"})
    assert result.match_method == "nip"
    assert result.confidence == 1.0
    assert r.entity_count == 1  # Not duplicated


def test_jabatan_kantor_match():
    r = EntityResolver()
    r.resolve({"nama": "Siti Nurhaliza", "jabatan": "Kasi Intel", "instansi": "Kanim NR"})
    result = r.resolve({"nama": "Siti N.", "jabatan": "Kasi Intel", "instansi": "Kanim NR"})
    assert result.match_method == "jabatan_kantor"
    assert result.confidence == 0.9
    assert r.entity_count == 1


def test_fuzzy_name_match():
    r = EntityResolver()
    r.resolve({"nama": "Raja Ulul Azmi Syahwali"})
    result = r.resolve({"nama": "Raja Ulul Azmi S."})
    assert result.match_method == "fuzzy_name"
    assert result.confidence >= 0.85
    assert r.entity_count == 1


def test_no_false_positive():
    r = EntityResolver()
    r.resolve({"nama": "Budi Santoso"})
    result = r.resolve({"nama": "Ahmad Yusuf"})
    assert result.match_method == "new"
    assert r.entity_count == 2


def test_short_name_no_false_positive():
    """Regression: 'Agus' should NOT fuzzy-match 'Agus Andrianto'.

    token_set_ratio gives score=100 for subsets. Short single-word names
    must require stricter matching to avoid collapsing distinct persons.
    """
    r = EntityResolver()
    r.resolve({"nama": "Agus Andrianto"})
    result = r.resolve({"nama": "Agus"})
    assert result.match_method == "new", (
        f"'Agus' wrongly matched '{result.canonical_name}'"
    )
    assert r.entity_count == 2


def test_ministry_subset_no_false_positive():
    """Similar: 'Imigrasi' should not collapse into 'Imigrasi Ngurah Rai'."""
    r = EntityResolver()
    r.resolve({"nama": "Kantor Imigrasi Ngurah Rai"}, entity_type="organization")
    result = r.resolve({"nama": "Imigrasi"}, entity_type="organization")
    assert result.match_method == "new"
    assert r.entity_count == 2


def test_property_merge():
    r = EntityResolver()
    r.resolve({"nama": "Test Person", "nip": "123456789012345678"})
    r.resolve({"nama": "Test Person", "nip": "123456789012345678", "jabatan": "Kabid", "asal": "Jakarta"})
    entity = r.get_by_id("person:test_person")
    assert entity is not None
    assert entity.properties.get("jabatan") == "Kabid"
    assert entity.properties.get("asal") == "Jakarta"
