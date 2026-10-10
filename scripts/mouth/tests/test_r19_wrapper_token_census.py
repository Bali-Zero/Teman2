"""Offline replay of the /kbli* R19 wrapper token census against its contract.

The fixture is the census dumped (`--json`) by the live run on 5 pages x 6
states; these tests judge it with the committed contract, so they need no
browser and no dev server.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
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
    assert any(line.startswith("state-colors-off-contract: ") for line in out)
    assert out[-1].startswith("opened-text-below-4.5: ")


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
    """The fixture is the live walk on origin/main 463ec63b76 (apps/mouth unchanged through f75a4fee92), dumped by
    W0d-2: 10 walks, 51 state classes off contract, 0 unseen. W2''' regenerates it and the pin moves to 0."""
    assert len(census["walks"]) == 10 and census["walk_failed"] == []
    out = verdict(census)
    assert out[-1] == "state-colors-off-contract: 51"
    assert "state-rows-unseen: 0" in out
    assert any(ln.strip().startswith("hover:bg-surface-editorial-elevated  expected #EAE3D8") for ln in out)
    assert any(ln.strip().startswith("group-hover:text-[color:var(--accent-zantara)]  expected #233D52") for ln in out)


# ---- the real walk, end to end, on a page we write --------------------------------------------

import functools  # noqa: E402
import http.server  # noqa: E402
import threading  # noqa: E402


def unseen(out: list[str]) -> tuple[str, list[str]]:
    at = next(i for i, ln in enumerate(out) if ln.startswith("state-rows-unseen:"))
    named = []
    for ln in out[at + 1 :]:
        if not ln.startswith("  "):
            break
        named.append(ln.strip())
    return out[at], named


def test_innocence_a_painted_row_that_was_observed_is_not_unseen():
    assert unseen(state_verdict(clean_obs())) == ("state-rows-unseen: 0", [])


def test_guilt_a_painted_row_in_the_dom_but_never_observed_is_named():
    walk = clean_obs()
    walk["state_obs"]["group-hover:text-[color:var(--accent-zantara)]"]["observed"] = []
    line, named = unseen(state_verdict(walk))
    assert line == "state-rows-unseen: 1"
    assert named[0].startswith("group-hover:text-[color:var(--accent-zantara)]  (group-hover color)")


def test_a_row_that_paints_nothing_is_never_unseen():
    walk = clean_obs()
    assert walk["state_obs"]["hover:shadow-xl"]["observed"] == []
    assert unseen(state_verdict(walk))[0] == "state-rows-unseen: 0"


def _chrome_ready() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return Path(census_mod._load_measure().CHROME).exists()
    except Exception:
        return False


needs_browser = pytest.mark.skipif(not _chrome_ready(), reason="no Playwright / headless Chrome on this machine")


def _css_class(token: str) -> str:
    return "." + re.sub(r"([^\w-])", r"\\\1", token)


def walk_page(tmp_path, monkeypatch, body: str, css: str) -> dict:
    """Runs the real walk_states() on one local page whose wrapper is [data-presentation=r19]."""
    from playwright.sync_api import sync_playwright
    (tmp_path / "g.html").write_text(
        f'<!doctype html><style>*{{border:0 solid transparent}}{css}</style>'
        f'<div data-presentation="r19">{body}</div>')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(census_mod, "PAGES", ["/g.html"])
    census = {"walks": [], "walk_failed": [], "state_obs": {}}
    m = census_mod._load_measure()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            census_mod.walk_states(browser, m, f"http://127.0.0.1:{server.server_port}", census)
            browser.close()
    finally:
        server.shutdown()
    assert census["walk_failed"] == [] and len(census["walks"]) == 2
    return census


BRACKET = "group-hover:text-[color:var(--accent-zantara)]"


def bracket_page(colour: str) -> tuple[str, str]:
    body = f'<a class="group" href="#x"><span class="{BRACKET}">label</span></a>'
    return body, f".group:hover {_css_class(BRACKET)}{{color:{colour}}}"


@needs_browser
def test_e2e_guilt_a_bracket_typed_class_painting_the_wrong_hue_counts_one(tmp_path, monkeypatch):
    census = walk_page(tmp_path, monkeypatch, *bracket_page("#A44B36"))  # the row says structure #233D52
    lines, count = census_mod.judge_states(census, STATES)
    assert count == 1 and lines[0].startswith(f"  {BRACKET}  expected #233D52, painted #A44B36")


@needs_browser
def test_e2e_innocence_a_bracket_typed_class_painting_its_row_counts_zero(tmp_path, monkeypatch):
    census = walk_page(tmp_path, monkeypatch, *bracket_page("#233D52"))
    assert census["state_obs"][BRACKET]["observed"] == ["#233D52"]
    assert census_mod.judge_states(census, STATES)[1] == 0


@needs_browser
def test_e2e_copper_at_30_percent_reads_the_copper_hex(tmp_path, monkeypatch):
    token = "hover:border-accent-warm/40"
    body = f'<a class="{token}" href="#x" style="border-width:2px">label</a>'
    css = f"{_css_class(token)}:hover{{border-color:rgba(164,75,54,0.3)}}"
    census = walk_page(tmp_path, monkeypatch, body, css)
    assert census["state_obs"][token]["observed"] == ["#A44B36"]
    assert census_mod.judge_states(census, STATES)[1] == 0


@needs_browser
def test_e2e_a_color_mix_paint_keeps_its_hue(tmp_path, monkeypatch):
    token = "group-hover:bg-[color-mix(in_srgb,var(--accent-zantara)_10%,transparent)]"
    body = f'<a class="group" href="#x"><span class="{token}">label</span></a>'
    css = f".group:hover {_css_class(token)}{{background:color-mix(in srgb,#EAE3D8 10%,transparent)}}"
    census = walk_page(tmp_path, monkeypatch, body, css)
    assert census["state_obs"][token]["observed"] == ["#EAE3D8"]


# ---- the form Tailwind 4 emits for a /NN modifier ---------------------------------------------

HUES = ["#A44B36", "#D4B483", "#D4845A", "#D01033", "#EAE3D8"]
ALPHAS = [10, 30, 40, 60]


@needs_browser
def test_e2e_tailwind_slash_30_copper_reads_the_copper_hex_and_a_wrong_hue_counts_one(tmp_path, monkeypatch):
    token = "hover:border-accent-warm/40"  # copper row; Tailwind compiles /NN to color-mix(in oklab, ...)
    body = f'<a class="{token}" href="#x" style="border-width:2px">label</a>'
    painted = lambda hue: f"{_css_class(token)}:hover{{border-color:color-mix(in oklab, {hue} 30%, transparent)}}"
    census = walk_page(tmp_path, monkeypatch, body, painted("#A44B36"))
    assert census["state_obs"][token]["observed"] == ["#A44B36"]
    assert census_mod.judge_states(census, STATES)[1] == 0
    wrong = walk_page(tmp_path, monkeypatch, body, painted("#D4845A"))
    lines, count = census_mod.judge_states(wrong, STATES)
    assert count == 1 and lines[0].startswith(f"  {token}  expected #A44B36, painted #D4845A")


@needs_browser
def test_hex_drops_the_alpha_of_every_computed_syntax_exactly():
    """20 oklab inputs (5 hues x 4 alphas) plus the other syntaxes Chrome computes, each read to its exact hex."""
    from playwright.sync_api import sync_playwright
    m = census_mod._load_measure()
    inputs = [(h, f"color-mix(in oklab, {h} {a}%, transparent)") for h in HUES for a in ALPHAS]
    inputs += [("#A44B36", "color-mix(in srgb, #A44B36 30%, transparent)"), ("#A44B36", "rgba(164, 75, 54, 0.3)"),
               ("#A44B36", "rgb(164 75 54 / 30%)"), ("#A44B36", "color-mix(in oklch, #A44B36 30%, transparent)"),
               ("#A44B36", "color-mix(in lab, #A44B36 30%, transparent)"), ("#A44B36", "#A44B36")]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        page = browser.new_page()
        page.set_content('<div data-presentation="r19"><p id="p">x</p></div>')
        assert page.evaluate(census_mod.STATE_JS, census_mod.STATE_TOKEN)["root"]
        got = page.evaluate("""(cs) => cs.map((c) => {
            const p = document.getElementById('p'); p.style.color = c;
            return window.__r19s.hex(getComputedStyle(p).color); })""", [c for _, c in inputs])
        zero = page.evaluate("""() => { const p = document.getElementById('p'); p.style.color = 'transparent';
            return window.__r19s.hex(getComputedStyle(p).color); }""")
        browser.close()
    assert [(want, g) for (want, _), g in zip(inputs, got)] == [(want, want) for want, _ in inputs]
    assert zero == "transparent"


# --- Section 8: the surfaces a click opens (W0c) -------------------------------------------

SURFACES = census_mod.parse_surfaces(CONTRACT, census_mod.load_contract(CONTRACT), STATES)


def edit_surface(text: str, token: str, column: str, value: str) -> str:
    """Rewrites one cell of one surfaces row; the table may be padded."""
    out = []
    for line in text.splitlines():
        if line.startswith(f"| `{token}` ") and line.count("|") == len(census_mod.UHEADER) + 1:
            cells = [c.strip() for c in line.strip("|").split("|")]
            cells[census_mod.UHEADER.index(column)] = value
            line = "| " + " | ".join(cells) + " |"
        out.append(line)
    return "\n".join(out)


def test_the_surfaces_table_names_the_four_slabs_the_gate_named_opaque():
    for token in ("bg-[#1c1c1f]/95", "bg-[#141416]/95", "bg-[#0A0C10]", "bg-[#151921]"):
        row = SURFACES[token]
        assert row["ground"] == "opaque" and row["hex"] in (census_mod.DIRECTION_A["elevated"],
                                                            census_mod.DIRECTION_A["wash"]), token
        assert row["ratio"] >= 4.5 and "ink" in row["text"], token


def test_every_text_bearing_surface_clears_4_5_and_no_scrim_carries_text():
    for token, row in SURFACES.items():
        if row["ground"] == "scrim":
            assert row["hex"] == census_mod.DIRECTION_A["ink"] and row["text"] == [], token
        for role in row["text"]:
            hx = {**census_mod.DIRECTION_A, **census_mod.SEMANTIC}[role]
            assert census_mod.contrast(hx, row["hex"]) >= 4.5, (token, role)


@pytest.mark.parametrize("mutation", [
    ("contrast: not the recomputed ratio", lambda t: edit_surface(t, "bg-[#1c1c1f]/95", "contrast", "6.10")),
    ("slab painted ink", lambda t: edit_surface(edit_surface(t, "bg-[#1c1c1f]/95", "value", "ink #1D2C3B"),
                                                "bg-[#1c1c1f]/95", "contrast", "1.00")),
    ("text below 4.5 on wash", lambda t: edit_surface(edit_surface(t, "bg-[#151921]", "text", "line-strong"),
                                                      "bg-[#151921]", "contrast", "1.80")),
    ("scrim carrying text", lambda t: edit_surface(edit_surface(t, "bg-black/70", "text", "ink"),
                                                   "bg-black/70", "contrast", "1.00")),
    ("unknown ground", lambda t: edit_surface(t, "bg-[#151921]", "ground", "glass")),
    ("a state variant", lambda t: t.replace("| `bg-[#151921]` ", "| `hover:bg-[#151921]` ", 1)),
    ("a token section 5 already names", lambda t: t.replace("| `bg-[#151921]` ", "| `bg-white/5` ", 1)),
    ("block: markers gone", lambda t: t.replace(census_mod.UEND, "", 1)),
], ids=lambda m: m[0] if isinstance(m, tuple) else "")
def test_a_mutated_surfaces_table_is_refused_not_read_as_empty(mutation):
    mutated = mutation[1](CONTRACT)
    assert mutated != CONTRACT
    with pytest.raises(census_mod.ContractError):
        contract = census_mod.load_contract(mutated)
        census_mod.parse_surfaces(mutated, contract, census_mod.parse_states(mutated, contract))


def test_a_class_named_in_both_section_5_and_8_2_is_refused():
    dup = CONTRACT.replace(census_mod.CEND, "| class | `text-white` | ink #1D2C3B | duplicate |\n" + census_mod.CEND, 1)
    with pytest.raises(census_mod.ContractError, match="repeats section 5"):
        census_mod.load_contract(dup)


ROWS = census_mod.load_contract(CONTRACT)
PIN = json.loads(census_mod.SHARED_PIN.read_text())
ELEVATED, INK = census_mod.DIRECTION_A["elevated"], census_mod.DIRECTION_A["ink"]


PAPER, WASH, COPPER = (census_mod.DIRECTION_A[r] for r in ("paper", "wash", "copper"))


def run(a: str, text: str = "Restaurant", fg: str = INK, painter: str = "div.absolute.z-50", **kw) -> dict:
    """One measured text run as the resolvers return it: A's ground `a`, B's `b` (the same unless given)."""
    return {"text": text, "path": "div>p", "fg": fg, "fa": 1.0, "clip": False, "state": "ok", "a": a, "spread": 0,
            "b": a, "image": None, "approx": False, "painter": painter, "action": "off", "occludedBy": None, **kw}


def walk(name: str, runs: list[dict], grounds: list[dict] | None = None, outside: list[str] | None = None,
         scrims: list[dict] | None = None, **kw) -> dict:
    row = {"name": name, "walk": "desktop/light", "roots": 1, "runs": runs, "outside": outside or [],
           "scrims": len(scrims or []), "grounds": grounds or [], "scrimPaint": scrims or [], "positions": 1,
           "incomplete": False, **kw}
    row["state"], row["reason"] = census_mod.walk_state(row)
    return row


def slab(token: str, hexv: str, a: float = 1) -> dict:
    return {"token": token, "hex": hexv, "a": a, "image": False, "scrim": False}


def verdict_of(census: dict, pin: dict | None = None, touched: list[str] | None = None) -> list[str]:
    return census_mod.opened_verdict(census, SURFACES, ROWS, pin, touched)


def lines_of(out: list[str], prefix: str) -> str:
    return next(ln for ln in out if ln.startswith(prefix))


def test_guilt_ink_titles_on_the_dark_dropdown_count_by_class_row_and_by_pixels():
    """The #8161 BLOCK: the dropdown ground stays #1C1C1F at 0.95 and the titles turned ink."""
    census = {"opened": [walk("search-dropdown", [run("#272729"), run("#272729", "description", "#58626B")],
                              [slab("bg-[#1c1c1f]/95", "#1C1C1F", 0.95)])]}
    out = verdict_of(census)
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 2"
    assert any(ln.startswith("  bg-[#1c1c1f]/95  expected elevated #FFFCF7 (opaque), painted #1C1C1F alpha 0.95")
               for ln in out)
    assert any(ln.startswith("  ground #272729 under 'Restaurant' at div.absolute.z-50") for ln in out)
    assert out[-1] == "opened-text-below-4.5: 2"


@pytest.mark.parametrize("ground,off", [("#F9F6F0", False), ("#FAF4EE", True), ("#A64C35", False),
                                        ("#EAE3DB", True)],
                         ids=["paper +2 on two channels", "paper +3", "copper drift #A64C35 on an action",
                              "wash +3 on blue"])
def test_a_ground_within_two_levels_of_a_role_is_that_role(ground, off):
    r = run(ground, action="ok")
    assert (census_mod.run_verdict(r) is not None) is off


@pytest.mark.parametrize("action,why", [("ok", None), ("off", "copper off an action"),
                                        ("box", "copper off an action (outside the action box)")])
def test_copper_is_a_ground_only_inside_its_own_action_box(action, why):
    assert census_mod.run_verdict(run(COPPER, fg=ELEVATED, action=action)) == why


def test_ink_is_a_ground_only_at_rest_and_only_under_elevated_or_paper_text():
    assert census_mod.run_verdict(run(INK, fg=ELEVATED), page_level=True) is None
    assert census_mod.run_verdict(run(INK, fg=PAPER), page_level=True) is None
    assert census_mod.run_verdict(run(INK, fg="#58626B"), page_level=True) == "off"
    assert census_mod.run_verdict(run(INK, fg=ELEVATED)) == "off"


@pytest.mark.parametrize("kw,why", [({"image": "gradient"}, "gradient"), ({"spread": 7}, "non-uniform"),
                                    ({"image": "canvas"}, "canvas"), ({"clip": True}, "text clipped to a background")])
def test_over_image_is_off_contract_and_named(kw, why):
    off, _ = census_mod.judge_runs([run(ELEVATED, **kw)], "x desktop/light")
    assert list(off.values()) == [f"  ground {ELEVATED} over-image ({why}) under 'Restaurant' at div.absolute.z-50, "
                                  "on x desktop/light"]


def test_a_six_level_spread_is_still_one_ground():
    assert census_mod.run_verdict(run(ELEVATED, spread=6)) is None


def test_the_resolvers_disagree_beyond_two_levels_unless_b_is_approximate_or_an_image():
    runs = [run(ELEVATED, b="#FFFCFA"), run(ELEVATED, "b", b="#FFFCF9", painter="div.b"),
            run(ELEVATED, "c", b="#000000", approx=True), run(ELEVATED, "d", b="#000000", image="img")]
    _, disagree = census_mod.judge_runs(runs, "x desktop/light")
    assert list(disagree.values()) == ["  disagree #FFFCF7 (pixels) vs #FFFCFA (DOM) under 'Restaurant' "
                                       "at div.absolute.z-50, on x desktop/light"]
    out = verdict_of({"opened": [walk("x", runs)]})
    assert lines_of(out, "ground-resolver-disagree:") == "ground-resolver-disagree: 1"


@pytest.mark.parametrize("hexv,a,off", [(INK, 0.45, False), (INK, 1, True), ("#000000", 0.45, True),
                                        (WASH, 1, True)],
                         ids=["ink 0.45", "opaque ink", "black 0.45", "opaque wash (G24)"])
def test_a_scrim_is_translucent_ink(hexv, a, off):
    row = walk("x", [run(ELEVATED)], scrims=[{"path": "body>div.fixed", "hex": hexv, "a": a}])
    lines = census_mod.judge_grounds({"opened": [row]}, SURFACES, ROWS)
    assert lines == ([f"  scrim {hexv} alpha {a} at body>div.fixed (a scrim is ink, translucent), on x desktop/light"]
                     if off else [])


def test_a_gradient_stop_class_must_paint_nothing():
    row = walk("x", [run(ELEVATED)], [{"token": "from-[#0F1115]", "hex": "transparent", "a": 0, "image": True,
                                       "scrim": False}])
    off = census_mod.judge_grounds({"opened": [row]}, SURFACES, ROWS)
    assert len(off) == 1 and off[0].startswith("  from-[#0F1115]  expected not painted on this surface")


@pytest.mark.parametrize("row,state", [
    ({"error": "opener: Timeout 300ms exceeded"}, "failed:never-opened (opener: Timeout 300ms exceeded)"),
    ({"roots": 0, "runs": []}, "failed:never-opened (0 roots)"),
    ({"runs": []}, "failed:never-opened (0 text runs)"),
    ({"runs": [run(ELEVATED, state="occluded"), run(ELEVATED, state="occluded")]},
     "failed:never-opened (0 measurable, 2 occluded)"),
    ({"runs": [run(ELEVATED, image="gradient"), run(ELEVATED, spread=9)]}, "failed:over-image-only (2 runs)"),
    ({"runs": [run(ELEVATED, image="gradient"), run(ELEVATED)]}, "ok"),
], ids=["opener", "no root", "no text", "all occluded", "all over an image", "one measured"])
def test_one_verdict_state_per_walk_and_its_reason(row, state):
    w = walk("x", **{"runs": [run(ELEVATED)], **row})
    assert (f"{w['state']} ({w['reason']})" if w["reason"] else w["state"]) == state


def test_an_over_image_only_walk_fails_yet_its_grounds_are_listed():
    out = verdict_of({"opened": [walk("x", [run("#16161A", fg="#F5F6F7", image="gradient")])]})
    assert out[0] == "opened-surfaces: 0 ok, 1 failed"
    assert out[1].startswith("  x desktop/light: failed:over-image-only (1 runs)")
    assert lines_of(out, "opened-grounds-off-contract:").startswith("opened-grounds-off-contract: 1 (INCOMPLETE")
    for prefix in ("opened-outside-wrapper:", "ground-resolver-disagree:", "opened-text-below-4.5:"):
        assert "INCOMPLETE" in lines_of(out, prefix), prefix


def test_a_walk_over_the_scroll_cap_is_incomplete():
    out = verdict_of({"opened": [walk("x", [run(ELEVATED)], incomplete=True)]})
    assert out[0] == "opened-surfaces: 1 ok, 0 failed"
    assert "INCOMPLETE" in out[-1] and "over the scroll cap" in out[-1]


def test_innocence_an_elevated_surface_with_ink_text_counts_zero():
    census = {"opened": [walk("search-dropdown", [run(ELEVATED)], [slab("bg-[#1c1c1f]/95", ELEVATED)])]}
    out = verdict_of(census)
    assert out[0] == "opened-surfaces: 1 ok, 0 failed"
    for prefix in ("opened-outside-wrapper:", "opened-grounds-off-contract:", "ground-resolver-disagree:",
                   "opened-text-below-4.5:"):
        assert lines_of(out, prefix) == f"{prefix} 0", prefix


def test_guilt_a_portal_outside_the_wrapper_is_counted():
    out = verdict_of({"opened": [walk("kbli-mobile-nav", [run(ELEVATED)], outside=["html>body>div.md:hidden.fixed"])]})
    assert lines_of(out, "opened-outside-wrapper:") == "opened-outside-wrapper: 1"
    assert "  html>body>div.md:hidden.fixed  renders outside the wrapper (kbli-mobile-nav desktop/light)" in out


def test_page_grounds_count_each_painter_and_hex_and_never_print_zero_unread():
    cap = {"page": "/kbli", "state": "desktop/light"}
    off, _ = census_mod.judge_runs([run("#16161A", fg="#F5F6F7"), run(INK, fg=ELEVATED)], "/kbli desktop/light",
                                   page_level=True)
    assert census_mod.page_verdict({"captures": [{**cap, "page_off": off}], "failed": []})[-1] == \
        "page-grounds-off-contract: 1"
    assert "INCOMPLETE" in census_mod.page_verdict({"captures": [{**cap, "page_off": {}, "page_incomplete": True}],
                                                    "failed": []})[-1]
    assert "INCOMPLETE" in census_mod.page_verdict({"captures": [cap], "failed": []})[-1]


def test_a_shared_fingerprint_holds_runs_the_root_ground_and_the_branch():
    row = {"runs": [run("#0E192F", "Menu", fg="#CFD1D5"), run(ELEVATED, "Logo", image="img"),
                    run(ELEVATED, "x", state="occluded")], "rootGround": "#0E192F"}
    assert census_mod.fingerprint(row, "non-R19") == ["#1D2C3B at alpha 1.0 over an image 'Logo'",
                                                      "#CFD1D5 on #0E192F 'Menu'", "branch non-R19", "root #0E192F"]


def shared(fingerprints: dict, failed: list[str] | None = None) -> dict:
    return {"opened": [walk("x", [run(ELEVATED)])], "shared_failed": failed or [],
            "shared": [{"name": k.rsplit(" ", 1)[0], "walk": k.rsplit(" ", 1)[1], "fingerprint": v}
                       for k, v in fingerprints.items()]}


def drift_of(fingerprints: dict) -> tuple[list[str], str]:
    return census_mod.shared_drift(shared(fingerprints), PIN)


MUTANTS = json.loads((FIXTURE.parent / "r19_shared_mutants.json").read_text())
MOBILE_NAV_FILE = "apps/mouth/src/app/v2/_components/MobileNav.tsx"


def test_innocence_i9_every_shared_component_as_pinned_has_no_drift():
    """I9: origin/main unmodified, walked live on a second dev server (the scratch tree, before any mutation)."""
    assert lines_of(verdict_of(shared(PIN), PIN), "shared-component-drift:") == "shared-component-drift: 0"
    assert drift_of(MUTANTS["I9"]["shared"]) == ([], "0")


def test_guilt_g27_an_ungated_paper_repaint_of_the_non_r19_drawer_drifts_on_v2_and_visa():
    """Mutation A: `background: isR19 ? "var(--nav-bg)" : "#F7F4EE"` in MobileNav.tsx, the #8183 gap."""
    lines, count = drift_of(MUTANTS["A"]["shared"])
    assert int(count) >= 1
    for route in ("/v2", "/visa/second-home", "/v2/news"):
        where = f"MobileNav non-R19 {route} mobile/light"
        assert any(ln.startswith("  - ") and "'Menu'" in ln and ln.endswith(f"({where})") for ln in lines), route
        assert any(ln.startswith("  + ") and " on #F7F4EE 'Menu'" in ln and ln.endswith(f"({where})")
                   for ln in lines), route
    assert not [ln for ln in lines if "MobileNav R19 " in ln or "NavShell" in ln or "Footer" in ln]


def test_guilt_g28_a_deeper_item_tint_on_every_branch_drifts_on_v2_and_tax_calendar():
    """Mutation B: the item ground `color-mix(… 6% …)` becomes 40% on both branches."""
    lines, count = drift_of(MUTANTS["B"]["shared"])
    assert int(count) >= 1
    for where in ("MobileNav non-R19 /v2 mobile/light", "MobileNav R19 /tax-calendar mobile/light"):
        assert any(ln.startswith("  + ") and "'Home'" in ln and ln.endswith(f"({where})") for ln in lines), where


def test_innocence_i10_a_paper_repaint_gated_on_the_prop_moves_only_kbli():
    """W2''''s intended change on a scratch tree: D stays 0 and /kbli's drawer, judged by K, is repainted."""
    assert drift_of(MUTANTS["I10"]["shared"]) == ([], "0")
    painted = {g["hex"] for g in MUTANTS["I10"]["kbli_painted"]}
    assert census_mod.DIRECTION_A["paper"] in painted
    assert census_mod.DIRECTION_A["paper"] not in {g["hex"] for g in MUTANTS["I9"]["kbli_painted"]}


def test_guilt_g29_mobile_nav_edited_with_the_v2_pin_removed_is_unpinned():
    partial = {k: v for k, v in PIN.items() if " /v2 " not in k}
    lines, count = census_mod.shared_unpinned([MOBILE_NAV_FILE], partial)
    assert count == "1"
    assert lines == [f"  {MOBILE_NAV_FILE}  MobileNav non-R19: no pin for MobileNav non-R19 /v2 mobile/light, "
                     "MobileNav non-R19 /v2 mobile/system-dark"]
    out = verdict_of(shared(PIN), partial, [MOBILE_NAV_FILE])
    assert lines_of(out, "shared-touched-unpinned:") == "shared-touched-unpinned: 1"


def test_a_pin_taken_on_the_wrong_branch_does_not_cover_its_pair():
    where = "MobileNav non-R19 /visa/second-home mobile/system-dark"
    wrong = {**PIN, where: [x.replace("branch non-R19", "branch R19") for x in PIN[where]]}
    lines, count = census_mod.shared_unpinned([MOBILE_NAV_FILE], wrong)
    assert count == "1" and lines[0].endswith(f"no pin for {where}")


def test_a_branch_that_flips_at_run_time_is_drift():
    where = "MobileNav non-R19 /v2 mobile/light"
    flipped = {**PIN, where: [x.replace("branch non-R19", "branch R19") for x in PIN[where]]}
    lines, count = drift_of(flipped)
    assert count == "2" and lines == [f"  - branch non-R19  ({where})", f"  + branch R19  ({where})"]


@pytest.mark.parametrize("touched", ["packages/core/components/BZLogo.tsx", "apps/mouth/src/components/ui/button.tsx",
                                     "apps/mouth/src/components/providers/LazyToaster.tsx",
                                     "apps/mouth/src/components/r19/presentation.ts"])
def test_guilt_a_shared_file_with_no_pin_is_unpinned_by_construction(touched):
    lines, count = census_mod.shared_unpinned([touched, "scripts/mouth/r19_wrapper_token_census.py"], PIN)
    assert count == "1" and lines == [f"  {touched}  has no pinned pair: an edit to it is unpinned by construction"]


def test_innocence_a_diff_that_touches_no_shared_file_or_a_pinned_one_counts_zero():
    for touched in ([], ["docs/specs/2026-10-08-kbli-r19-wrapper-token-contract.md"], list(census_mod.SHARED_MATRIX)[:4]):
        assert census_mod.shared_unpinned(touched, PIN) == ([], "0"), touched


@pytest.mark.parametrize("touched", [None, "cannot diff against origin/main: unknown revision"])
def test_no_diff_never_prints_zero(touched):
    assert "INCOMPLETE" in census_mod.shared_unpinned(touched, PIN)[1]


def test_a_shared_walk_missing_failed_or_unpinned_never_prints_zero():
    partial = {k: v for k, v in PIN.items() if "/tax-calendar" not in k}
    assert "INCOMPLETE" in drift_of(partial)[1]
    assert "INCOMPLETE" in census_mod.shared_drift(shared(PIN, ["Footer editorial /v2 mobile/light: HTTP 500"]), PIN)[1]
    assert lines_of(verdict_of(shared(PIN), None), "shared-component-drift:") == "shared-component-drift: UNPINNED"
    extra = {**PIN, "MobileNav R19 /blog mobile/light": ["branch R19"]}
    assert drift_of(extra) == (["  ? MobileNav R19 /blog mobile/light  walked, not in the pin"], "1")


def test_the_pin_covers_every_pair_of_the_matrix_on_the_branch_it_claims():
    want = sorted(k for pair, routes in census_mod.SHARED_PAIRS.items() for r in routes
                  for k in census_mod.pin_keys(pair, r))
    assert sorted(PIN) == want and len(want) == 24
    for key, prints in PIN.items():
        pair = " ".join(key.split()[:2])
        branch = census_mod.BRANCH_OF.get(pair)
        assert [x for x in prints if x.startswith("branch ")] == ([f"branch {branch}"] if branch else []), key
        assert len(prints) > 1, key
    assert {r for r in census_mod.MOBILE_NAV["MobileNav non-R19"]} >= {"/v2", "/visa/second-home"}


@pytest.mark.parametrize("moved,drift", [("#1D2C3B on #F0EBE3 'News'", False), ("#1F2C3B on #EEE9E1 'News'", False),
                                         ("#1D2C3B on #F1EBE3 'News'", True), ("#1D2C3B on #EEE9E1 'Blog'", True),
                                         ("root #F9F6F0", False), ("root #FAF6F0", True)],
                         ids=["ground +2", "text +2", "ground +3", "another label", "root +2", "root +3"])
def test_a_pinned_entry_holds_within_two_levels_per_channel(moved, drift):
    """The pixels move a level when the page behind or the page texture shifts: within 2 it is the same entry."""
    where = "Footer R19 blog /news mobile/light"
    pinned = "root #F7F4EE" if moved.startswith("root") else "#1D2C3B on #EEE9E1 'News'"
    pin = {where: ["branch x", pinned]}
    walked = {"shared": [{"name": "Footer R19 blog /news", "walk": "mobile/light", "fingerprint": ["branch x", moved]}],
              "shared_failed": []}
    lines, count = census_mod.shared_drift(walked, pin)
    assert count == ("2" if drift else "0"), lines


def test_touched_files_reads_committed_and_uncommitted_changes_since_the_merge_base(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    for f in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / f).write_text("0\n")
    git("add", ".")
    git("commit", "-qm", "base")
    git("checkout", "-qb", "lot")
    (tmp_path / "a.txt").write_text("1\n")
    git("commit", "-qam", "lot")
    (tmp_path / "b.txt").write_text("1\n")
    assert census_mod.touched_files("main", tmp_path) == ["a.txt", "b.txt"]
    assert census_mod.touched_files("no-such-ref", tmp_path).startswith("cannot diff against no-such-ref")


def test_guilt_a_scratch_edit_to_the_r19_presentation_styles_is_unpinned(tmp_path):
    """Gate note 3: R19Presentation.module.css paints every R19 surface, so a lot that edits it is N >= 1."""
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    css = tmp_path / "apps/mouth/src/components/r19/R19Presentation.module.css"
    css.parent.mkdir(parents=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    css.write_text(".drawer { background: var(--r19-paper); }\n")
    git("add", ".")
    git("commit", "-qm", "base")
    git("checkout", "-qb", "lot")
    css.write_text(".drawer { background: #F7F4EE; }\n")
    touched = census_mod.touched_files("main", tmp_path)
    lines, count = census_mod.shared_unpinned(touched, PIN)
    assert int(count) >= 1
    assert lines == ["  apps/mouth/src/components/r19/R19Presentation.module.css  has no pinned pair: an edit to it "
                     "is unpinned by construction"]
    out = verdict_of(shared(PIN), PIN, touched)
    assert lines_of(out, "shared-touched-unpinned:") == "shared-touched-unpinned: 1"


@pytest.mark.parametrize("census", [{"opened": [walk("sector-drawer", [], error="load: timeout")]},
                                    {"opened": []}, {}],
                         ids=["a surface failed to open", "nothing opened", "no opened walk"])
def test_an_incomplete_opened_walk_never_prints_zero(census):
    out = verdict_of(census)
    for prefix in ("opened-outside-wrapper:", "opened-grounds-off-contract:", "ground-resolver-disagree:",
                   "shared-touched-unpinned:", "shared-component-drift:", "opened-text-below-4.5:"):
        assert "INCOMPLETE" in lines_of(out, prefix), prefix


def test_the_mobile_nav_drawer_and_the_portal_ruling_are_in_the_contract():
    for family in ("background", "color", "border"):
        assert ("rule", f"MobileNav paper drawer {{ {family} }}") in ROWS
    assert ROWS[("rule", "MobileNav paper CTA { background }")]["hex"] == census_mod.DIRECTION_A["copper"]
    assert ROWS[("rule", "MobileNav paper CTA { color }")]["hex"] == ELEVATED
    portals = CONTRACT.split("**Portals.**")[1].split("\n\n")[0]
    for surface in ("sector drawer", "comparison modal", "mobile nav"):
        assert surface in portals, surface


PAGE = ("<!doctype html><html><head><style>{css}</style></head><body style='margin:0;background:#F7F4EE'>"
        "<div data-presentation='r19' style='padding:24px'>{body}</div>{tail}</body></html>")
LIGHT = "#F5F6F7"
REVEAL = "document.getElementById('s').hidden = false"
GRADIENT = "background:linear-gradient(#0F1115, #2A2A30);padding:24px"
CHECKER = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='8' height='8'>"
           "<rect width='4' height='4' fill='%23111'/><rect x='4' y='4' width='4' height='4' fill='%23111'/></svg>")


def p(color: str, text: str = "Restaurant", style: str = "") -> str:
    return f'<p style="color:{color};margin:0;{style}">{text}</p>'


def surface(style: str, inner: str | None = None, cls: str = "") -> str:
    return f'<div id="s" class="{cls}" style="{style}" hidden>{inner if inner is not None else p(LIGHT)}</div>'


def appended(html: str, reveal: str = REVEAL) -> str:
    return f"{reveal}; document.body.insertAdjacentHTML('beforeend', `{html}`)"


SCRIM = '<div style="position:fixed;inset:0;background:{};z-index:5"></div>'
LIFTED = "position:relative;z-index:10;background:#FFFCF7;padding:16px"
TOOLTIP = ('<span role="button" style="position:relative;color:#1D2C3B">KBLI<span style="position:absolute;left:0;'
           'top:28px;background:#A44B36;color:#FFFCF7;padding:4px;white-space:nowrap">Business code</span></span>')
BEFORE_CSS = ("{sel}{{position:relative;z-index:0;padding:8px}}"
              "{sel}::before{{content:'';position:absolute;inset:0;background:#111;z-index:-1}}")
CANVAS = ('<canvas id="cv" width="400" height="80" style="position:absolute;inset:0;width:100%;height:100%">'
          "</canvas>")
# id: body, css, opener (JS, or None to click a selector that is not there), selectors,
#     expected (P, K at least, M exactly or at least as ">=n", walk state, an excerpt every walk prints)
CASES = [
    ("G1", surface("background-color:rgb(28 28 31 / 0.95);padding:16px", cls="bg-[#1c1c1f]/95"), "", REVEAL, ["#s"],
     (0, 1, 0, "ok", "  bg-[#1c1c1f]/95  expected elevated #FFFCF7 (opaque)")),
    ("G2", surface("background-color:rgb(28 28 30 / 0.95);padding:16px", cls="bg-[#1c1c1e]/95"), "", REVEAL,
     ["#s"], (0, 1, 0, "ok", "  bg-[#1c1c1e]/95  has no section 5 or 8.1 row")),
    ("G3", surface("background:#18181B;padding:16px", cls="bg-zinc-900"), "", REVEAL, ["#s"],
     (0, 2, 0, "ok", "  ground #18181B under 'Restaurant'")),
    ("G4", surface("background-color:rgb(28 28 31 / 0.95);padding:16px", p(INK), cls="bg-[#1c1c1e]/95"), "",
     REVEAL, ["#s"], (0, 1, ">=1", "ok", "  ground #2")),
    ("G5", surface("background:#1E293B;padding:16px", cls="bg-slate-800"), "", REVEAL, ["#s"],
     (0, 2, 0, "ok", "  ground #1E293B under 'Restaurant'")),
    ("G6", surface("background:#222;padding:16px"), "", REVEAL, ["#s"], (0, 1, 0, "ok", "  ground #222222 under")),
    ("G7", surface("", cls="x"), ".x{background:#111;padding:16px}", REVEAL, ["#s"],
     (0, 1, 0, "ok", "  ground #111111 under 'Restaurant' at html>body>div>div.x")),
    ("G8", surface(GRADIENT, p(LIGHT) + f'<div style="background:#FFFCF7;padding:8px">{p(INK, "Villa")}</div>'),
     "", REVEAL, ["#s"], (0, 1, 0, "ok", "over-image (gradient) under 'Restaurant'")),
    ("G9", surface(GRADIENT), "", REVEAL, ["#s"], ("INC", 1, "INC", "failed:over-image-only (1 runs)",
                                                  "over-image (gradient) under 'Restaurant'")),
    ("G10", f'<div style="background:#1A1A1A;padding:8px"><div>{surface("")}</div></div>', "", REVEAL, ["#s"],
     (0, 1, 0, "ok", "  ground #1A1A1A under 'Restaurant'")),
    ("G11", surface("background:#1A1A1A", f"<div><div>{p(LIGHT)}</div></div>"), "", REVEAL, ["#s"],
     (0, 1, 0, "ok", "  ground #1A1A1A under 'Restaurant'")),
    ("G12", "", "", appended('<div role="dialog" style="position:fixed;top:0;left:0;width:300px;background:#0F1B31;'
                             f'padding:16px">{p(LIGHT, "Menu")}</div>', ""), ['[role="dialog"]'],
     (2, 1, 0, "ok", "  ground #0F1B31 under 'Menu'")),
    ("G13", surface("background:#FFFCF7;padding:16px", p(ELEVATED, "Notice", "background:#A44B36;padding:4px")), "",
     REVEAL, ["#s"], (0, 1, 0, "ok", "(copper off an action)")),
    ("G14", surface("background:#FFFCF7;padding:16px", f'<div class="y">{p(INK)}</div>'), BEFORE_CSS.format(sel=".y"),
     REVEAL, ["#s"], (0, 1, ">=1", "ok", "div.y::before")),
    ("G15", surface("background:#FFFCF7;padding:16px", f'<div class="before:bg-[#111]">{p(INK)}</div>'),
     BEFORE_CSS.format(sel=r".before\:bg-\[\#111\]"), REVEAL, ["#s"], (0, 1, ">=1", "ok", "::before")),
    ("G16", surface("position:relative;background:#FFFCF7;padding:16px",
                    '<div style="position:absolute;inset:0;background:#111"></div>' + p(INK, style="position:relative")),
     "", REVEAL, ["#s"], (0, 1, ">=1", "ok", "  ground #111111 under 'Restaurant'")),
    ("G17", surface("position:relative;background:#FFFCF7;padding:16px",
                    '<div style="position:absolute;inset:0;background:#111;pointer-events:none"></div>'
                    + p(INK, style="position:relative")),
     "", REVEAL, ["#s"], (0, 1, ">=1", "ok", "  ground #111111 under 'Restaurant'")),
    ("G18", surface("background:#FFFCF7;padding:16px", '<div style="position:relative;padding:16px">' + CANVAS
                    + p(INK, style="position:relative") + f"</div>{p(INK, 'Villa')}"),
     "", REVEAL + "; const g = document.getElementById('cv').getContext('2d'); g.fillStyle = '#111';"
     " g.fillRect(0, 0, 400, 80)", ["#s"], (0, 1, ">=1", "ok", "over-image (canvas) under 'Restaurant'")),
    ("G19", surface("background:#F7F4EE;padding:16px",
                    f'<div style="opacity:.5"><div style="background:#111;padding:8px">{p(ELEVATED)}</div></div>'),
     "", REVEAL, ["#s"], (0, 1, None, "ok", "  ground #8")),
    ("G20", surface("background:#F7F4EE;padding:16px", p(INK, style="background:rgb(0 0 0 / 0.2)")), "", REVEAL,
     ["#s"], (0, 1, 0, "ok", "  ground #C")),
    ("G21", surface("background:#FFFCF7;padding:16px 16px 56px", TOOLTIP), "", REVEAL, ["#s"],
     (0, 1, 0, "ok", "(copper off an action (outside the action box))")),
    ("G22", surface("background:#FFFCF7;padding:16px", p(INK)), "",
     appended('<div style="position:fixed;inset:0;background:#FFFCF7;z-index:50"></div>'), ["#s"],
     ("INC", None, "INC", "failed:never-opened (0 measurable, 1 occluded)", None)),
    ("G23", surface("background:#FFFCF7;padding:16px", p(INK)), "", None, ["#s"],
     ("INC", None, "INC", "failed:never-opened (opener:", None)),
    ("G24", surface(LIFTED, p(INK)), "", appended(SCRIM.format("#EAE3D8")), ["#s"],
     (0, 1, 0, "ok", "  scrim #EAE3D8 alpha 1 at ")),
    ("I1", surface("background:#FFFCF7;padding:16px", p(INK)), "", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    ("I2", surface("background:#F7F4EE;padding:16px", p(INK)), "", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    ("I3", surface("background:#FFFCF7;padding:16px",
                   f'<div style="background:#EAE3D8;padding:8px">{p("#58626B")}</div>'), "", REVEAL, ["#s"],
     (0, 0, 0, "ok", None)),
    ("I4", surface("background:#FFFCF7;padding:16px", '<button style="background:#A44B36;color:#FFFCF7;border:0;'
                   'padding:8px 16px;font:16px sans-serif">Get Started</button>'), "", REVEAL, ["#s"],
     (0, 0, 0, "ok", None)),
    ("I5", surface("background:#FFFCF7;padding:16px", '<a href="#x" style="display:inline-block;background:#A44B36;'
                   'padding:8px 16px;text-decoration:none"><span style="color:#FFFCF7">Get Started</span></a>'),
     "", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    ("I6", surface(LIFTED, p(INK)), "", appended(SCRIM.format("rgba(29,44,59,0.45)")), ["#s"],
     (0, 0, 0, "ok", None)),
    ("I7", surface("position:relative;background:#F7F4EE;padding:16px",
                   '<div style="position:absolute;inset:0;background-image:linear-gradient(45deg,#000 25%,'
                   'transparent 25%);opacity:.05;pointer-events:none"></div><div style="position:relative;'
                   f'background:#FFFCF7;padding:8px">{p(INK)}</div>'), "", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    # Beyond the spec's table: glyphs that fill their box, a full block and a colour pictograph, are made
    # transparent before A reads the pixels; a bullet pseudo-element is not a ground; an opaque ink scrim is off.
    ("glyphs", surface("background:#FFFCF7;padding:16px", p(INK, "\u2588\u2588\u2588", "font-size:40px;line-height:1")
                       + p(INK, "\U0001F7E5\U0001F7E5", "font-size:40px;line-height:1")), "", REVEAL, ["#s"],
     (0, 0, 0, "ok", None)),
    ("G24-ink", surface(LIFTED, p(INK)), "", appended(SCRIM.format("#1D2C3B")), ["#s"],
     (0, 1, 0, "ok", "  scrim #1D2C3B alpha 1 at ")),
    # A 1.5% texture over the whole page, as `body::after` paints it, is faint: no ground and no occluder.
    ("faint", surface("background:#FFFCF7;padding:16px", p(INK)), "",
     appended('<div style="position:fixed;inset:0;background-image:linear-gradient(45deg,#A0A0A0,#E0E0E0);opacity:.015;'
              'pointer-events:none;z-index:99"></div>'), ["#s"], (0, 0, 0, "ok", None)),
    # The page's colour-dodge glow, a fixed pseudo-element over the viewport, blends: no ground, B approximate.
    ("glow", surface("padding:16px", p(INK)),
     "body::before{content:'';position:fixed;inset:0;background:radial-gradient(60% 40% at 50% 0%,"
     "rgba(164,75,54,.01),transparent);mix-blend-mode:color-dodge;pointer-events:none;z-index:0}", REVEAL, ["#s"],
     (0, 0, 0, "ok", None)),
    ("bullet", surface("background:#FFFCF7;padding:16px", f'<ul style="margin:0"><li class="b">{p(INK)}</li></ul>'),
     ".b{list-style:none;position:relative;padding-left:16px}.b::before{content:'';position:absolute;left:0;"
     "top:8px;width:6px;height:6px;background:#A44B36}", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    # The same texture seen through a translucent surface on a page taller than the viewport: a fixed
    # pseudo-element covers the viewport, not its host, so B sees it and is approximate, not in disagreement.
    ("texture-under", surface("position:relative;z-index:1;background:rgba(255,252,247,0.5);padding:16px", p(INK)),
     "body{min-height:3000px}body::after{content:'';position:fixed;inset:0;background-image:linear-gradient(#000,"
     "#000);opacity:.023;pointer-events:none;z-index:0}", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
]


def serve(tmp_path, html: str):
    (tmp_path / "o.html").write_text(html)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def open_case(tmp_path, monkeypatch, body: str, css: str, opener: str | None, selectors: list[str]) -> dict:
    """Runs the real walk_opened() (desktop/light and mobile/system-dark) on one local page."""
    from playwright.sync_api import sync_playwright
    server = serve(tmp_path, PAGE.format(css=css, body=body, tail=""))

    def open_it(page):
        if opener is None:
            page.click("#not-on-this-page", timeout=300)
        page.evaluate(f"() => {{ {opener} }}")
    monkeypatch.setattr(census_mod, "SCENARIOS", [("case", "/o.html", "walk", None, False, open_it, selectors)])
    monkeypatch.setattr(census_mod, "SHARED", [])
    monkeypatch.setattr(census_mod, "SETTLE", {"load": 50, "ready": 100, "open": 150, "scroll": 50})
    census: dict = {}
    m = census_mod._load_measure()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            census_mod.walk_opened(browser, m, f"http://127.0.0.1:{server.server_port}", census)
            browser.close()
    finally:
        server.shutdown()
    return census


def count(out: list[str], prefix: str) -> str:
    return lines_of(out, prefix).split(": ", 1)[1]


@needs_browser
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_e2e_guilt_and_innocence_through_the_real_walk(tmp_path, monkeypatch, case):
    """SPEC-W0d section 3, G1-G24 and I1-I7: each row through walk_opened() on a local page."""
    _, body, css, opener, selectors, (p_, k, m_, state, excerpt) = case
    out = verdict_of(open_case(tmp_path, monkeypatch, body, css, opener, selectors))
    walks = [ln for ln in out if ln.startswith("  case ")]
    assert len(walks) == 2 and all(f": {state}" in ln for ln in walks), walks
    if p_ == "INC":
        for prefix in ("opened-outside-wrapper:", "opened-grounds-off-contract:", "ground-resolver-disagree:",
                       "opened-text-below-4.5:"):
            assert "INCOMPLETE" in lines_of(out, prefix), prefix
    else:
        assert count(out, "opened-outside-wrapper:") == str(p_)
    k_seen = int(count(out, "opened-grounds-off-contract:").split()[0])
    assert k is None or (k_seen >= k if k else k_seen == 0), out
    m_seen = int(count(out, "opened-text-below-4.5:").split()[0])
    if m_ not in (None, "INC"):
        assert m_seen >= 1 if m_ == ">=1" else m_seen == m_, out
    if excerpt:
        assert any(excerpt in ln for ln in out), out
    if state == "ok":  # B sees every painter of these pages, so it agrees with A
        assert count(out, "ground-resolver-disagree:") == "0", out


PAGE_CASES = [
    ("G25", '<section style="background:linear-gradient(135deg, rgba(20,20,25,0.95), rgba(30,30,35,0.95));'
            f'padding:24px">{p(LIGHT, "Talk to our team")}</section>', 1, "over-image (gradient) under 'Talk to our team'"),
    ("G26", f'<section style="background-image:url(&quot;{CHECKER}&quot;);padding:24px">{p(INK, "Licences")}</section>',
     1, "over-image (image) under 'Licences'"),
    ("I8", f'<div style="background:#1D2C3B;padding:8px">{p(ELEVATED, "Indonesia")}</div>{p(INK, "Body")}', 0, None),
]


@needs_browser
@pytest.mark.parametrize("case", PAGE_CASES, ids=[c[0] for c in PAGE_CASES])
def test_e2e_page_grounds_at_rest(tmp_path, case):
    """SPEC-W0d section 3, G25, G26 and I8: the page-level judge on a local wrapper at rest."""
    from playwright.sync_api import sync_playwright
    _, body, g, excerpt = case
    server = serve(tmp_path, PAGE.format(css="", body=body, tail=""))
    m = census_mod._load_measure()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
            page.goto(f"http://127.0.0.1:{server.server_port}/o.html", wait_until="load")
            res = census_mod.page_grounds(page, "local desktop/light")
            browser.close()
    finally:
        server.shutdown()
    out = census_mod.page_verdict({"captures": [{"page": "/o.html", "state": "desktop/light", **res}], "failed": []})
    assert out[-1] == f"page-grounds-off-contract: {g}", out
    if excerpt:
        assert any(excerpt in ln for ln in out), out


@needs_browser
def test_e2e_i11_two_walks_print_the_same_verdict(tmp_path, monkeypatch):
    """A rotation of 2.5 s inside the walk holds its first state, and two walks print the same text."""
    rotate = ("<script>setInterval(() => { const q = document.createElement('p');"
              " q.textContent = 'rotated'; q.style.color = '#444444';"
              " document.getElementById('s').append(q); }, 2500);</script>")
    body = surface("background:#FFFCF7;padding:16px", p(INK)) + rotate
    first = verdict_of(open_case(tmp_path, monkeypatch, body, "", REVEAL, ["#s"]))
    second = verdict_of(open_case(tmp_path, monkeypatch, body, "", REVEAL, ["#s"]))
    assert first == second and first[-1] == "opened-text-below-4.5: 0"


def test_the_origin_main_opened_walk_is_the_guilt(census):
    """Main today, by pixels: every surface opens; the dropdown titles are white and readable, the red code chips
    are not; the resolvers disagree on two runs (the page texture over the footer, a pictograph chip)."""
    out = verdict_of(census, PIN, [])
    assert out[0] == "opened-surfaces: 25 ok, 0 failed"
    assert lines_of(out, "opened-outside-wrapper:") == "opened-outside-wrapper: 10"
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 143"
    assert lines_of(out, "ground-resolver-disagree:") == "ground-resolver-disagree: 2"
    assert lines_of(out, "shared-touched-unpinned:") == "shared-touched-unpinned: 0"
    assert lines_of(out, "shared-component-drift:") == "shared-component-drift: 0"
    assert out[-1] == "opened-text-below-4.5: 685"
    drop = next(o for o in census["opened"] if o["name"] == "search-dropdown" and o["walk"] == "desktop/light")
    below = [(round(census_mod.contrast(census_mod.text_colour(r), r["a"]), 2), r["fg"], r["text"])
             for r in drop["runs"] if r["state"] == "ok" and r["fg"]
             and census_mod.contrast(census_mod.text_colour(r), r["a"]) < 4.5]
    assert below == [(3.3, "#DC2626", "56101"), (3.26, "#DC2626", "55130")]


def test_the_origin_main_page_grounds_name_the_consultation_card_over_its_gradient(census):
    """G25 on main: KBLIConsultationCTA's inline gradient puts its text over an image, on every state of 55203."""
    assert census_mod.page_verdict(census)[-1] == "page-grounds-off-contract: 449"
    card = {c["state"] for c in census["captures"] if c["page"] == "/kbli/55203"
            for ln in c["page_off"].values()
            if "over-image (gradient)" in ln and "section.rp-dark-island.mt-12>div.rounded-2xl" in ln}
    assert card == set(census["states"])


def test_guilt_8161s_head_reads_ink_titles_on_the_dark_dropdown():
    """The search walks dumped live at #8161's head (51b2407f27) by the W0d-2 census: the BLOCK, by pixels."""
    rows = [json.loads(ln) for ln in (FIXTURE.parent / "r19_opened_8161_search.jsonl").read_text().splitlines()]
    out = verdict_of({"opened": rows})
    assert out[0] == "opened-surfaces: 10 ok, 0 failed"
    drop = next(o for o in rows if o["name"] == "search-dropdown" and o["walk"] == "desktop/light")
    titles = [(round(census_mod.contrast(census_mod.text_colour(r), r["a"]), 2), r["fg"], r["a"])
              for r in drop["runs"] if r["text"] in ("Restaurant", "Villa")]
    assert titles == [(1.04, "#1D2C3B", "#282729"), (1.03, "#1D2C3B", "#28282A")]
    assert any(ln.startswith("  bg-[#1c1c1f]/95  expected elevated #FFFCF7 (opaque), painted #1C1C1F alpha 0.95")
               for ln in out)
    assert any(ln.startswith("  ground #282729 under 'Restaurant' at ") for ln in out)
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 21"
    assert lines_of(out, "ground-resolver-disagree:") == "ground-resolver-disagree: 0"
    assert out[-1] == "opened-text-below-4.5: 108"
