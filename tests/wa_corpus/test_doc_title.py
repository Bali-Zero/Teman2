from scripts.wa_corpus.renderer import doc_title


def test_title_uses_crm_name_when_client():
    t = doc_title("+33600000000", "Alexandre")
    assert t == "WA · Alexandre · +33600000000"
    # phone is always present (stable key for search/rename)
    assert "+33600000000" in t


def test_title_uses_phone_when_no_crm_name():
    t = doc_title("+628120000008", None)
    assert t == "WA · +628120000008"


def test_title_phone_present_in_both_cases():
    # OBLIGATORY: phone is the stable key, never dropped
    assert "+33600000000" in doc_title("+33600000000", "Alexandre")
    assert "+33600000000" in doc_title("+33600000000", None)


def test_title_sanitizes_unsafe_name_chars():
    t = doc_title("+62123", "Gledys / Cristian: Aires")
    assert "/" not in t and ":" not in t
    assert "+62123" in t


def test_empty_crm_name_falls_back_to_phone():
    assert doc_title("+62123", "") == "WA · +62123"
    assert doc_title("+62123", "   ") == "WA · +62123"
