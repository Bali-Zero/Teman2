from scripts.whatsapp_export_backfill.match_exports import score_contact_match


def test_exact_one_active_non_team_client_scores_one() -> None:
    result = score_contact_match(
        {"display_name": "Lisa Marek", "phones": ["628111"]},
        candidate_clients=[
            {"id": "c1", "name": "Lisa Marek", "phone": "+62 8111", "status": "active"}
        ],
        whatsapp_contacts=[],
    )

    assert result["score"] == 1.0
    assert result["decision"] == "match"
    assert result["client_id"] == "c1"


def test_exact_phone_with_whatsapp_contact_and_client_scores_095() -> None:
    result = score_contact_match(
        {"display_name": "Sindy Kirks", "phones": ["628222"]},
        candidate_clients=[{"id": "c2", "name": "Sindy K", "phone": "08222", "status": "active"}],
        whatsapp_contacts=[{"name": "Sindy Kirks", "phone": "+62 8222"}],
    )

    assert result["score"] == 0.95
    assert result["decision"] == "match"
    assert result["client_id"] == "c2"


def test_deleted_duplicate_or_alias_mismatch_is_strong_review() -> None:
    result = score_contact_match(
        {"display_name": "Trevor", "phones": ["628333"]},
        candidate_clients=[
            {"id": "old", "name": "Trevor", "phone": "+62 8333", "status": "deleted"},
            {"id": "new", "name": "Trevor Alias", "phone": "+62 8333", "status": "active"},
        ],
        whatsapp_contacts=[],
    )

    assert result["score"] == 0.80
    assert result["decision"] == "review"
    assert result["client_id"] == "new"


def test_gemma_multiple_active_family_clients_is_review_only() -> None:
    result = score_contact_match(
        {"display_name": "Gemma", "phones": ["628444"]},
        candidate_clients=[
            {"id": "g1", "name": "Gemma Family", "phone": "+62 8444", "status": "active"},
            {"id": "g2", "name": "Gemma Spouse", "phone": "+62 8444", "status": "active"},
        ],
        whatsapp_contacts=[{"name": "Gemma", "phone": "+62 8444"}],
    )

    assert result["score"] == 0.80
    assert result["decision"] == "review"
    assert result["client_id"] is None


def test_makar_no_vcard_exact_phone_is_review_only() -> None:
    result = score_contact_match(
        {"display_name": "Makar", "phones": []},
        candidate_clients=[{"id": "m1", "name": "Makar", "phone": "+62 8555", "status": "active"}],
        whatsapp_contacts=[],
    )

    assert result["score"] == 0.65
    assert result["decision"] == "review"
    assert result["client_id"] == "m1"


def test_no_match_scores_below_review_threshold() -> None:
    result = score_contact_match(
        {"display_name": "Unknown", "phones": ["628999"]},
        candidate_clients=[
            {"id": "x1", "name": "Someone Else", "phone": "+62 8111", "status": "active"}
        ],
        whatsapp_contacts=[],
    )

    assert result["score"] < 0.65
    assert result["decision"] == "no_match"
