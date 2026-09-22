"""Guilt and innocence for the KG root census.

The fixture is a 9-node miniature of PROD carrying one of every shape the real
store holds: a rich `kbli:` node, a `kg_seed` node that wears the canonical id
with the wrong `entity_type` and no `kode`, the three duplicate shapes of ONE
code (47721), a phantom (99999) with no rich twin, and two free-text sweepings.

The census is judged on what it must SAY, not on how it says it: a shape is
attributed to the right writer, a phantom is a phantom only when no rich node
backs it, and the cure surface counts only nodes that have somewhere to go.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

FILIERA_DIR = Path(__file__).resolve().parents[1]
if str(FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(FILIERA_DIR))

from kg_root_census import (  # noqa: E402
    EXIT_CANNOT_VERIFY,
    EXIT_OK,
    FAMILY_BARE,
    FAMILY_COLON,
    FAMILY_KBLI_KBLI,
    FAMILY_OTHER,
    FAMILY_UNDERSCORE,
    classify_family,
    extract_token,
    main,
    plan_census,
)

FIXTURE = FILIERA_DIR / "tests/fixtures/kg_root_census_snapshot.json"


@pytest.fixture(scope="module")
def snapshot() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def census(snapshot: dict) -> dict:
    return plan_census(snapshot["nodes"], snapshot["edges"])


def _family(census: dict, name: str) -> dict:
    return next(f for f in census["families"] if f["family"] == name)


# -- classify_family: the double prefix must not collapse into the single one --


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("kbli:47721", FAMILY_COLON),
        ("kbli_47721", FAMILY_UNDERSCORE),
        ("kbli_kbli_47721", FAMILY_KBLI_KBLI),
        ("47721", FAMILY_BARE),
        ("kategori_r", FAMILY_OTHER),
    ],
)
def test_each_shape_is_attributed_to_its_own_writer(entity_id: str, expected: str) -> None:
    assert classify_family(entity_id) == expected


def test_double_prefix_is_not_read_as_single_prefix() -> None:
    """INNOCENCE for the ordering. `kbli_kbli_47721` matches BOTH prefix tests;
    testing `kbli_` first would merge 5,026 double-prefixed nodes into the
    single-prefix family and erase the second writer from the census."""
    assert classify_family("kbli_kbli_47721") != FAMILY_UNDERSCORE


def test_token_is_stripped_once_per_family_not_by_replace() -> None:
    """GUILT for `entity_id.replace("kbli:", "")` — the live reader's move. It
    is a no-op on the underscore families, which is how a garbage code reaches
    a client. Every shape of 47721 must yield the same five digits."""
    for entity_id in ("kbli:47721", "kbli_47721", "kbli_kbli_47721", "47721"):
        assert extract_token(entity_id) == "47721"
    assert "kbli_47721".replace("kbli:", "") == "kbli_47721"


def test_free_text_token_is_left_alone_after_one_strip() -> None:
    assert extract_token("kbli_pembuatan_karet_sintetis") == "pembuatan_karet_sintetis"
    assert extract_token("kategori_r") == "kategori_r"


# -- the census tables --


def test_families_are_counted_with_their_data_state(census: dict) -> None:
    colon = _family(census, FAMILY_COLON)
    assert (colon["nodes"], colon["with_kode"], colon["without_kode"]) == (3, 2, 1)
    assert _family(census, FAMILY_UNDERSCORE)["nodes"] == 2
    assert _family(census, FAMILY_KBLI_KBLI)["nodes"] == 2
    assert _family(census, FAMILY_BARE)["nodes"] == 1
    assert _family(census, FAMILY_OTHER)["nodes"] == 1
    assert census["total_nodes"] == 9


def test_a_canonical_id_can_still_be_empty(census: dict) -> None:
    """GUILT for "the id shape predicts the data perfectly". `kbli:55111` wears
    the right id and carries no `kode` — the census must be able to say so, or
    the six `kg_seed` nodes stay invisible behind a slogan."""
    assert _family(census, FAMILY_COLON)["without_kode"] == 1


def test_a_non_kbli_entity_type_is_still_counted(census: dict) -> None:
    """INNOCENCE for widening the `WHERE`. Filtering `entity_type='kbli'` — as
    every earlier census did — drops `kbli:55111` entirely."""
    types = dict(_family(census, FAMILY_COLON)["entity_types"])
    assert types.get("kbli_code") == 1


def test_edge_reachability_counts_nodes_not_edges(census: dict) -> None:
    assert _family(census, FAMILY_COLON)["edge_reachable"] == 2
    assert _family(census, FAMILY_UNDERSCORE)["edge_reachable"] == 2
    assert _family(census, FAMILY_OTHER)["edge_reachable"] == 0


def test_inbound_histogram_ignores_outbound_rows(census: dict) -> None:
    """GUILT: summing both directions into one histogram double-counts every
    edge whose two ends are both KBLI nodes."""
    assert dict(census["relationship_types"][FAMILY_UNDERSCORE]) == {"APPLIES_TO": 5}
    assert dict(census["relationship_types"][FAMILY_KBLI_KBLI]) == {"APPLIES_TO": 4, "PART_OF": 2}
    assert dict(census["relationship_types"][FAMILY_COLON]) == {"APPLIES_TO": 10}


# -- phantoms --


def test_phantom_is_five_digits_with_no_rich_twin(census: dict) -> None:
    """55111 is the `kg_seed` shape — the canonical id, no `kode`, no canonical
    code behind it; 99999 is the extractor shape. Both are phantoms, and the
    census must name both, because they need the SAME status and different
    writers put them there."""
    assert census["phantom_count"] == 2
    assert census["phantom_sample"] == ["55111", "99999"]


def test_a_code_with_a_rich_twin_is_never_a_phantom(census: dict) -> None:
    """INNOCENCE. 47721 exists in all four shapes; three of them are empty. A
    phantom test that looked at the node in hand rather than at the code would
    report three phantoms and license inventing data for a code we HAVE."""
    assert "47721" not in census["phantom_sample"]
    assert census["rich_tokens"] == 2
    assert census["five_digit_tokens"] == 4


def test_free_text_tokens_are_never_phantom_codes(census: dict) -> None:
    """A phantom is a well-formed code with no data. `kategori_r` has no data
    either, but calling it a phantom CODE would put it in a cure lot that
    assigns it a KBLI status."""
    assert "kategori_r" not in census["phantom_sample"]
    assert "pembuatan_karet_sintetis" not in census["phantom_sample"]
    assert census["distinct_tokens"] == 6


# -- the cure surface --


def test_repointable_counts_only_empties_with_somewhere_to_go(census: dict) -> None:
    """The three empty 47721 shapes are repointable; the 99999 phantom is not,
    because there is no rich node to repoint it to — inventing one is the thing
    the spec forbids."""
    assert census["repointable_nodes"] == 3
    assert census["repointable_edges_in"] == 8
    assert census["repointable_edges_out"] == 15


def test_double_prefix_proof_is_the_name_column(census: dict) -> None:
    """The id shape says WHICH writer; the name says WHY. Every double-prefixed
    node's name already starts with 'KBLI', which is the whole bug."""
    assert census["name_carries_kbli_prefix"][FAMILY_KBLI_KBLI] == 2


def test_fanout_is_reported_per_well_formed_code(census: dict) -> None:
    """47721 resolves to 4 nodes; 55130, 55111 and 99999 to 1 each. The
    notebook fallback's `LIMIT 5` is safe only while this maximum stays under
    5 — on PROD it reached 4 on 94 codes."""
    assert dict(census["fanout"]) == {1: 3, 4: 1}


# -- exit codes --


def test_empty_snapshot_is_cannot_verify_never_ok(tmp_path: Path) -> None:
    """W84. 'I traversed nothing' must never render as 'there is nothing there'."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
    assert main(["--snapshot", str(empty)]) == EXIT_CANNOT_VERIFY


def test_unreadable_snapshot_is_cannot_verify(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert main(["--snapshot", str(missing)]) == EXIT_CANNOT_VERIFY


def test_fixture_replay_exits_ok() -> None:
    assert main(["--snapshot", str(FIXTURE)]) == EXIT_OK


def test_emit_sql_never_touches_the_database() -> None:
    assert main(["--emit-sql"]) == EXIT_OK


def test_the_script_holds_no_write_statement() -> None:
    """The census is read-only by construction, and this pins it: a future
    edit that adds an UPDATE to the 'read-only' census is the exact shape of
    the accident this lane exists to prevent."""
    source = (FILIERA_DIR / "kg_root_census.py").read_text(encoding="utf-8").upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP ", "TRUNCATE"):
        assert verb not in source.replace("UPDATED_AT", "")


def test_cli_runs_the_fixture_end_to_end() -> None:
    proc = subprocess.run(
        [sys.executable, str(FILIERA_DIR / "kg_root_census.py"), "--snapshot", str(FIXTURE)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == EXIT_OK, proc.stderr
    assert "KG ROOT CENSUS" in proc.stdout
    assert "PHANTOM" in proc.stdout
