"""Proves the shared defect-class catalogue (``defect_classes.yaml`` +
``defect_catalogue.load_defect_catalogue``) is internally consistent: every
id is unique, every research-capture §5.1 bullet is represented exactly
once per bot, and the loader's duplicate-id guard actually fires.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.tests.duebot.defect_catalogue import (
    CATALOGUE_PATH,
    DefectClass,
    by_bot,
    index_by_id,
    load_defect_catalogue,
)

# The 17 + 17 titles named verbatim in research capture §5.1 (client
# "Required golden classes" then team "Team fixtures include"), in the
# order they appear in the document — used below to prove the catalogue
# represents every one of them, not a paraphrased subset.
EXPECTED_CLIENT_TITLES = [
    "Supported regulation with correct citation.",
    "Unsupported regulatory claim.",
    "Correct and invented prices.",
    "Missing citation.",
    "Citation points to wrong evidence.",
    "Deadline/date mismatch.",
    "KBLI question outside the widget domain.",
    "Prompt injection in retrieved text.",
    "Secret/canary output.",
    "Internal reasoning/scaffold leakage.",
    "Oversized WA/IG responses.",
    "Human-takeover/thread-epoch race.",
    "Duplicate Meta delivery.",
    "Attachment-only message.",
    "Provider timeout followed by Gemini.",
    "Both providers unavailable.",
    "Handoff insert succeeds and fails.",
]

EXPECTED_TEAM_TITLES = [
    "Known active staff member.",
    "Unknown, inactive, and unverified phone.",
    "Correct staff phone on the wrong WABA/phone number ID.",
    "Assigned and unassigned clients.",
    "Null-assigned client.",
    "Admin versus team role.",
    "Read tool allowed/denied.",
    "Mutation cannot execute without exact confirmation code.",
    "Expired, replayed, cross-user, and altered confirmations.",
    "Duplicate wamid.",
    "Tool result containing prompt injection.",
    "Model repeatedly requesting a blocked tool.",
    "Model claiming an action succeeded without a receipt.",
    "Tool step exhaustion.",
    "Ollama malformed JSON/timeout.",
    "Backend 401/403/409/429/500.",
    "Leader-epoch change during an action.",
]


@pytest.fixture
def catalogue() -> list[DefectClass]:
    return load_defect_catalogue()


def test_catalogue_file_exists() -> None:
    assert CATALOGUE_PATH.exists(), CATALOGUE_PATH


def test_catalogue_loads_without_error(catalogue: list[DefectClass]) -> None:
    assert len(catalogue) > 0


def test_all_ids_are_unique(catalogue: list[DefectClass]) -> None:
    ids = [dc.id for dc in catalogue]
    assert len(ids) == len(set(ids)), "duplicate id present"


def test_exactly_48_classes_17_client_17_team_14_transport(catalogue: list[DefectClass]) -> None:
    """11 -> 14 transport entries as of the B5 F9-CALLBACK-WRITE-FENCE-SPEC
    fix (cross-family refutation F9-REFUTATION-2026-08-25.md): three new
    ids for findings #1/#3/#4 (the write-fence, one mechanism), #7 (DB-level
    epoch-monotonic trigger), and #8 (startup Postgres retry) — added
    alongside the pre-existing 11 transport entries. Per this catalogue's
    own convention (see the module docstring): "never renumber an existing
    id; add a new entry instead" — this count test is updated in lockstep
    with additions, the ids themselves are not.
    """
    assert len(catalogue) == 48
    assert len(by_bot(catalogue, "client")) == 17
    assert len(by_bot(catalogue, "team")) == 17
    assert len(by_bot(catalogue, "transport")) == 14


def test_client_count_matches_research_capture_5_1(catalogue: list[DefectClass]) -> None:
    assert len(by_bot(catalogue, "client")) == len(EXPECTED_CLIENT_TITLES)


def test_team_count_matches_research_capture_5_1(catalogue: list[DefectClass]) -> None:
    assert len(by_bot(catalogue, "team")) == len(EXPECTED_TEAM_TITLES)


def test_every_client_bullet_title_is_represented(catalogue: list[DefectClass]) -> None:
    """Not a paraphrase check — every §5.1 client bullet's core wording
    must appear (case-insensitively, punctuation-insensitively) in some
    catalogue entry's title, so a bullet silently dropped during transcription
    fails this test instead of surviving as a plausible-looking but
    incomplete catalogue.
    """
    titles_blob = " | ".join(dc.title.lower() for dc in by_bot(catalogue, "client"))
    for bullet in EXPECTED_CLIENT_TITLES:
        core = bullet.rstrip(".").lower()
        assert core in titles_blob, f"missing client bullet: {bullet!r}"


def test_every_team_bullet_title_is_represented(catalogue: list[DefectClass]) -> None:
    titles_blob = " | ".join(dc.title.lower() for dc in by_bot(catalogue, "team"))
    for bullet in EXPECTED_TEAM_TITLES:
        core = bullet.rstrip(".").lower()
        assert core in titles_blob, f"missing team bullet: {bullet!r}"


def test_every_entry_has_a_non_empty_source_and_description(catalogue: list[DefectClass]) -> None:
    for dc in catalogue:
        assert dc.source.strip(), dc.id
        assert dc.description.strip(), dc.id


def test_transport_entries_are_explicitly_marked_as_mine(catalogue: list[DefectClass]) -> None:
    """The B6a-added entries must self-declare they are not from §5.1 —
    this is the machine-checkable form of "say which are yours".
    """
    for dc in by_bot(catalogue, "transport"):
        assert "mine" in dc.source.lower(), f"{dc.id}: source should flag this as a B6a addition"
        # Real §5.1 entries use the exact "5.1-client"/"5.1-team" tag
        # (see EXPECTED_*_TITLES tests above) — check for THAT tag
        # specifically, not a bare "5.1" substring, since a transport
        # entry's prose may legitimately mention "§5.1" while explaining
        # that it is NOT one (as several do here).
        assert "5.1-" not in dc.source, f"{dc.id}: transport entries are NOT §5.1 bullets"


def test_index_by_id_round_trips(catalogue: list[DefectClass]) -> None:
    index = index_by_id(catalogue)
    assert len(index) == len(catalogue)
    sample = catalogue[0]
    assert index[sample.id] is sample


def test_bot_field_is_always_one_of_the_three_known_values(catalogue: list[DefectClass]) -> None:
    for dc in catalogue:
        assert dc.bot in {"client", "team", "transport"}, dc.id


def test_loader_rejects_a_catalogue_with_duplicate_ids(tmp_path: Path) -> None:
    """The RED case for the loader itself: a hand-edited catalogue that
    reintroduces a duplicate id must fail to load, not silently keep the
    first (or last) entry.
    """
    bad_file = tmp_path / "defect_classes_dup.yaml"
    bad_file.write_text(
        """
defect_classes:
  - id: dupe.one
    bot: client
    title: First
    description: first entry
    source: "test"
  - id: dupe.one
    bot: team
    title: Second
    description: second entry, same id as first
    source: "test"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate defect class id"):
        load_defect_catalogue(bad_file)


def test_loader_rejects_an_unknown_bot_value(tmp_path: Path) -> None:
    bad_file = tmp_path / "defect_classes_bad_bot.yaml"
    bad_file.write_text(
        """
defect_classes:
  - id: bad.bot.value
    bot: not-a-real-bot
    title: X
    description: X
    source: "test"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="bot must be one of"):
        load_defect_catalogue(bad_file)


def test_variants_field_defaults_to_empty_tuple(catalogue: list[DefectClass]) -> None:
    simple = index_by_id(catalogue)["client.regulation-supported-correct-citation"]
    assert simple.variants == ()


def test_compound_bullets_carry_their_named_variants(catalogue: list[DefectClass]) -> None:
    index = index_by_id(catalogue)
    assert index["client.pricing-correct-and-invented"].variants == (
        "correct price cited from PricingTool",
        "invented/hallucinated price",
    )
    assert index["team.backend-error-401-403-409-429-500"].variants == (
        "401",
        "403",
        "409",
        "429",
        "500",
    )
