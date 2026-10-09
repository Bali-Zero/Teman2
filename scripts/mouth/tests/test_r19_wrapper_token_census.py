"""Offline replay of the /kbli* R19 wrapper token census against its contract.

The fixture is the census dumped (`--json`) by the live run on 5 pages x 6
states; these tests judge it with the committed contract, so they need no
browser and no dev server.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import r19_wrapper_token_census as census_mod  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "r19_wrapper_census.jsonl"
CONTRACT = census_mod.CONTRACT.read_text()


def verdict(census: dict, text: str = CONTRACT) -> list[str]:
    contract = census_mod.parse_contract(text)
    return census_mod.verdict(census, contract, census_mod.parse_states(text, contract))


def undefined(out: list[str]) -> tuple[str, list[str]]:
    at = next(i for i, line in enumerate(out) if line.startswith("read-but-undefined:"))
    named = []
    for line in out[at + 1 :]:
        if not line.startswith("  "):
            break
        named.append(line.strip())
    return out[at], named


def without_row(token: str) -> str:
    lines = [ln for ln in CONTRACT.splitlines() if f"| `{token}` " not in ln]
    assert len(lines) == len(CONTRACT.splitlines()) - 1, token
    return "\n".join(lines)


@pytest.fixture
def census() -> dict:
    return census_mod.load(FIXTURE)


def test_innocence_the_committed_contract_defines_every_live_read(census):
    out = verdict(census)
    assert undefined(out) == ("read-but-undefined: 0", [])
    assert len(census["captures"]) == 30 and census["failed"] == []
    assert any(line.startswith("colors-outside-direction-a: ") for line in out)
    assert out[-1].startswith("state-colors-off-contract: ")


def test_the_two_reds_of_7508_are_in_the_census(census):
    assert census["reads"]["var --color-text-secondary"]["defined"] == "above"
    assert "class brand-tagline" in census["reads"]


def test_guilt_one_extra_read_token_is_named(census):
    guilty = copy.deepcopy(census)
    guilty["reads"]["var --kbli-guilt-probe"] = {
        "kind": "var", "token": "--kbli-guilt-probe", "defined": "above", "count": 1,
        "selector": "div.guilt", "page": "/kbli", "state": "mobile/light"}
    line, named = undefined(verdict(guilty))
    assert line == "read-but-undefined: 1"
    assert named == ["var --kbli-guilt-probe  e.g. div.guilt on /kbli mobile/light"]


def test_guilt_one_removed_row_is_named(census):
    line, named = undefined(verdict(census, without_row("--color-text-secondary")))
    assert line == "read-but-undefined: 1"
    assert named[0].startswith("var --color-text-secondary  e.g. ")


def test_an_incomplete_census_never_prints_zero(census):
    partial = copy.deepcopy(census)
    partial["failed"] = ["/kbli/55203 mobile/light: HTTP 500"]
    line, _ = undefined(verdict(partial))
    assert line != "read-but-undefined: 0" and "INCOMPLETE" in line


def in_table(text: str, pattern: str, repl: str) -> str:
    """Applies one substitution inside the contract block only."""
    head, rest = text.split(census_mod.BEGIN)
    return head + census_mod.BEGIN + re.sub(pattern, repl, rest, count=1)


@pytest.mark.parametrize("mutation", [
    ("header: wrong column", lambda t: in_table(t, r"\| value(\s*)\|", r"| colour\1|")),
    ("row: a fifth cell", lambda t: in_table(t, r"\| (copper #A44B36\s*)\|", r"| \1| x |")),
    ("value: off-palette hex", lambda t: in_table(t, "muted #58626B", "muted #435464")),
    ("value: dark-theme verdict hue", lambda t: in_table(t, "semantic #2E5E4E", "semantic #5EC490")),
    ("block: markers gone", lambda t: t.replace("<!-- contract:begin -->", "", 1)),
], ids=lambda m: m[0] if isinstance(m, tuple) else "")
def test_a_mutated_contract_is_refused_not_read_as_empty(mutation):
    mutated = mutation[1](CONTRACT)
    assert mutated != CONTRACT
    with pytest.raises(census_mod.ContractError):
        census_mod.parse_contract(mutated)


def test_cli_replay_prints_the_verdict_last(capsys):
    census_mod.main(["--replay", str(FIXTURE)])
    out = capsys.readouterr().out.splitlines()
    assert "read-but-undefined: 0" in out
    assert any(line.startswith("colors-outside-direction-a: ") for line in out)
    assert out[-1].startswith("state-colors-off-contract: ")


def test_export_hands_the_armed_test_the_same_probe_and_states(capsys, census):
    assert census_mod.main(["--export"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["probe"] == census_mod.PROBE_JS
    assert out["pages"] == census_mod.PAGES
    assert [s["name"] for s in out["states"]] == census["states"]
    assert out["direction_a"] == census_mod.DIRECTION_A
    assert all(v >= 4.5 for v in out["semantic_on_paper"].values())


# ---- section 7: the state contract -------------------------------------------------------

STATES = census_mod.parse_states(CONTRACT, census_mod.parse_contract(CONTRACT))


def clean_obs() -> dict:
    """A walk in which every painted state row is observed painting its own hex."""
    obs = {t: {"token": t, "state": r["state"], "prop": r["prop"], "observed": [r["hex"]] if r["hex"] else [],
               "selector": "div.x", "count": 1, "page": "/kbli", "walk": "desktop/light"}
           for t, r in STATES.items()}
    return {"walks": ["/kbli desktop/light"], "walk_failed": [], "state_obs": obs}


def state_verdict(extra: dict) -> list[str]:
    base = census_mod.load(FIXTURE)
    return verdict({**base, **extra})


def state_line(out: list[str]) -> tuple[str, list[str]]:
    at = next(i for i, ln in enumerate(out) if ln.startswith("state-colors-off-contract:"))
    named = [ln.strip() for ln in reversed(out[:at]) if ln.startswith("  ") and "expected" in ln or "undeclared" in ln]
    return out[at], named


def test_innocence_a_walk_that_paints_every_row_is_zero():
    line, named = state_line(state_verdict(clean_obs()))
    assert line == "state-colors-off-contract: 0" and named == []


def test_guilt_a_state_painted_off_its_row_is_named():
    walk = clean_obs()
    token = "hover:bg-surface-editorial-elevated"  # the gate's catch: resolves to elevated, the row says wash
    walk["state_obs"][token]["observed"] = [census_mod.DIRECTION_A["elevated"]]
    line, named = state_line(state_verdict(walk))
    assert line == "state-colors-off-contract: 1"
    assert named[0].startswith(f"{token}  expected #EAE3D8, painted #FFFCF7")


def test_guilt_a_colour_outside_the_palette_is_named():
    walk = clean_obs()
    walk["state_obs"]["hover:text-accent-sand"]["observed"] = ["#D4B483"]
    assert state_line(state_verdict(walk))[0] == "state-colors-off-contract: 1"


def test_guilt_an_undeclared_state_class_is_named():
    walk = clean_obs()
    walk["state_obs"]["hover:bg-fuchsia-500"] = {"token": "hover:bg-fuchsia-500", "state": "hover", "prop": "background",
                                                 "observed": ["#EAE3D8"], "selector": "a.new", "count": 1,
                                                 "page": "/kbli", "walk": "desktop/light"}
    line, named = state_line(state_verdict(walk))
    assert line == "state-colors-off-contract: 1" and "undeclared" in named[0]


def test_a_ring_row_is_met_by_any_shadow_colour_and_missed_by_none_of_them():
    walk = clean_obs()
    ring = "focus:ring-2"
    walk["state_obs"][ring]["observed"] = ["#000000", census_mod.DIRECTION_A["copper"]]
    assert state_line(state_verdict(walk))[0] == "state-colors-off-contract: 0"
    walk["state_obs"][ring]["observed"] = ["#000000"]
    assert state_line(state_verdict(walk))[0] == "state-colors-off-contract: 1"


def test_a_token_never_reached_is_unseen_not_off():
    walk = clean_obs()
    for ob in walk["state_obs"].values():
        ob["observed"] = []
    assert state_line(state_verdict(walk))[0] == "state-colors-off-contract: 0"


@pytest.mark.parametrize("extra", [{"walks": [], "walk_failed": []},
                                   {"walks": ["a"], "walk_failed": ["/kbli desktop/light: HTTP 500"]}],
                         ids=["no walk ran", "a walk failed"])
def test_an_incomplete_walk_never_prints_zero(extra):
    line, _ = state_line(state_verdict({**clean_obs(), **extra}))
    assert line.startswith("state-colors-off-contract: INCOMPLETE")


def edit_row(text: str, token: str, column: str | None, value: str | None) -> str:
    """Rewrites one cell of one state row (column None drops the last cell); the table may be padded."""
    out = []
    for line in text.splitlines():
        if re.match(rf"\| `{re.escape(token)}`\s+\|", line):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if column is None:
                cells.pop()
            else:
                cells[census_mod.SHEADER.index(column)] = value
            line = "| " + " | ".join(cells) + " |"
        out.append(line)
    return "\n".join(out)


def in_states(text: str, pattern: str, repl: str) -> str:
    head, rest = text.split(census_mod.SBEGIN)
    return head + census_mod.SBEGIN + re.sub(pattern, repl, rest, count=1)


@pytest.mark.parametrize("mutation", [
    ("contrast: not the recomputed ratio", lambda t: edit_row(t, "focus:ring-2", "contrast", "5.27")),
    ("value: off-palette hex", lambda t: edit_row(t, "focus:ring-2", "value", "copper #D4845A")),
    ("focus border below 3:1", lambda t: edit_row(t, "focus:border-white/[0.15]", "value", "line-strong #A8ACA9")),
    ("text below 4.5:1", lambda t: edit_row(edit_row(t, "hover:text-white", "value", "copper #A44B36"),
                                            "hover:text-white", "against", "ink #1D2C3B")),
    ("state: unknown variant", lambda t: edit_row(t, "hover:text-white", "state", "hovr")),
    ("row: a missing cell", lambda t: edit_row(t, "hover:text-white", None, None)),
    ("block: markers gone", lambda t: t.replace(census_mod.SEND, "", 1)),
    ("block: header wrong", lambda t: in_states(t, r"\| against\s+\|", "| surface |")),
], ids=lambda m: m[0] if isinstance(m, tuple) else "")
def test_a_mutated_state_table_is_refused_not_read_as_empty(mutation):
    mutated = mutation[1](CONTRACT)
    assert mutated != CONTRACT
    with pytest.raises(census_mod.ContractError):
        census_mod.parse_states(mutated, census_mod.parse_contract(CONTRACT))


def test_a_duplicate_state_row_is_refused():
    row = next(ln for ln in CONTRACT.splitlines() if re.match(r"\| `hover:text-white`\s+\| hover", ln))
    with pytest.raises(census_mod.ContractError):
        census_mod.parse_states(CONTRACT.replace(row, row + "\n" + row, 1))


def test_a_state_row_that_contradicts_section_5_is_refused():
    main = next(ln for ln in CONTRACT.splitlines() if ln.startswith("| class     | `hover:text-white`"))
    forged = CONTRACT.replace(main, re.sub(r"ink #1D2C3B", "copper #A44B36", main, count=1), 1)
    assert forged != CONTRACT
    with pytest.raises(census_mod.ContractError, match="contradicts section 5"):
        census_mod.parse_states(forged, census_mod.parse_contract(forged))


def test_a_state_class_is_defined_by_its_state_row_alone(census):
    read = {"kind": "class", "token": "hover:bg-white/[0.04]", "defined": None, "count": 1,
            "selector": "a.x", "page": "/kbli", "state": "mobile/light"}
    assert ("class", read["token"]) not in census_mod.parse_contract(CONTRACT)
    assert read["token"] in STATES
    census["reads"]["class " + read["token"]] = read
    assert undefined(verdict(census))[0] == "read-but-undefined: 0"


def test_the_state_token_grammar_covers_the_table_and_spares_non_colours():
    grammar = re.compile(census_mod.STATE_TOKEN)
    assert [t for t in STATES if not grammar.match(t)] == []
    for innocent in ("hover:underline", "hover:text-sm", "hover:scale-105", "focus:outline-none",
                     "hover:text-center", "hover:border-solid", "text-white", "bg-white/5", "scrollbar-thin"):
        assert not grammar.match(innocent), innocent


def test_every_painted_state_row_clears_its_floor():
    for token, row in STATES.items():
        if row["hex"] is None:
            continue
        floor = 4.5 if row["prop"] in ("color", "background") else 3.0 if row["prop"] == "ring" or (
            row["prop"] == "border" and row["state"].startswith(("focus", "group-focus"))) else 0.0
        assert census_mod.contrast(row["hex"], row["against"].split()[1]) >= floor, token


def test_the_flag_title_clears_the_ink_hero_band():
    row = census_mod.parse_contract(CONTRACT)[("class", "kbli-flag-title")]
    assert census_mod.contrast(row["hex"], census_mod.DIRECTION_A["ink"]) >= 4.5


def test_the_rest_copper_borders_were_ruled_to_line():
    contract = census_mod.parse_contract(CONTRACT)
    for token in ("border-[rgba(212,132,90,0.2)]", "border-accent-sand/20", "border-accent-sand/30", "border-accent-warm/30"):
        assert contract[("class", token)]["hex"] == census_mod.DIRECTION_A["line"], token


def test_the_origin_main_walk_is_the_pre_w2_number(census):
    """The fixture is the live walk on origin/main a906625f63: 10 walks, 46 state classes off contract.
    W2'' regenerates it and the pin moves to 0."""
    assert len(census["walks"]) == 10 and census["walk_failed"] == []
    out = verdict(census)
    assert out[-1] == "state-colors-off-contract: 46"
    assert any(ln.strip().startswith("hover:bg-surface-editorial-elevated  expected #EAE3D8") for ln in out)
