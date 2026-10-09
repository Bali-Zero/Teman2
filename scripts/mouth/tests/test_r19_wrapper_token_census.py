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
    """The fixture is the live walk on origin/main 4443d209f1: 10 walks, 51 state classes off contract, 0 unseen.
    W2'' regenerates it and the pin moves to 0."""
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


def opened(name: str, ground: dict, pairs: list[dict]) -> dict:
    return {"name": name, "walk": "desktop/light", "roots": 1, "scrims": 0, "pairs": len(pairs), "unmeasurable": 0,
            "min": min(p["ratio"] for p in pairs), "below": [p for p in pairs if p["ratio"] < 4.5],
            "grounds": [json.dumps(ground, sort_keys=True)]}


def pair(ratio: float, fg: str, bg: str, text: str = "Restaurant") -> dict:
    return {"ratio": ratio, "fg": fg, "bg": bg, "text": text, "cls": "font-semibold truncate text-white"}


def lines_of(out: list[str], prefix: str) -> str:
    return next(ln for ln in out if ln.startswith(prefix))


def test_guilt_ink_titles_on_the_unnamed_dark_dropdown_count():
    """The #8161 BLOCK: the dropdown ground stays #1C1C1F at 0.95 and the titles turned ink."""
    dark = {"token": "bg-[#1c1c1f]/95", "hex": "#1C1C1F", "a": 0.95, "image": False, "scrim": False}
    census = {"opened": [opened("search-dropdown", dark, [pair(1.05, "#1D2C3B", "#272729"),
                                                          pair(2.40, "#58626B", "#272729", "description")])],
              "opened_failed": []}
    out = census_mod.opened_verdict(census, SURFACES)
    assert lines_of(out, "opened-text-below-4.5:") == "opened-text-below-4.5: 2"
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 1"
    assert any(ln.startswith("  bg-[#1c1c1f]/95  expected elevated #FFFCF7 (opaque), painted #1C1C1F alpha 0.95")
               for ln in out)
    assert out[-1] == "opened-text-below-4.5: 2"


def test_innocence_an_elevated_surface_with_ink_text_counts_zero():
    card = {"token": "bg-[#1c1c1f]/95", "hex": "#FFFCF7", "a": 1, "image": False, "scrim": False}
    census = {"opened": [opened("search-dropdown", card, [pair(13.91, "#1D2C3B", "#FFFCF7")])], "opened_failed": []}
    out = census_mod.opened_verdict(census, SURFACES)
    assert out[0] == "opened-surfaces: 1 ok, 0 failed"
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 0"
    assert out[-1] == "opened-text-below-4.5: 0"


def test_a_scrim_keeps_its_alpha_and_a_gradient_stop_must_paint_nothing():
    scrim = {"token": "bg-black/70", "hex": "#1D2C3B", "a": 0.7, "image": False, "scrim": True}
    stop = {"token": "from-[#0F1115]", "hex": "transparent", "a": 0, "image": True, "scrim": False}
    census = {"opened": [opened("sector-drawer", scrim, [pair(13.91, "#1D2C3B", "#FFFCF7")]),
                         opened("explorer-answer-inspector", stop, [pair(13.91, "#1D2C3B", "#FFFCF7")])],
              "opened_failed": []}
    off = census_mod.judge_grounds(census, SURFACES)
    assert len(off) == 1 and off[0].startswith("  from-[#0F1115]  expected not painted on this surface")


@pytest.mark.parametrize("census", [{"opened": [], "opened_failed": ["sector-drawer mobile/system-dark: timeout"]},
                                    {"opened": [], "opened_failed": []}, {}],
                         ids=["a surface failed to open", "nothing opened", "no opened walk"])
def test_an_incomplete_opened_walk_never_prints_zero(census):
    out = census_mod.opened_verdict(census, SURFACES)
    assert "INCOMPLETE" in out[-1] and "INCOMPLETE" in lines_of(out, "opened-grounds-off-contract:")


OPENER = ('<button id="open" onclick="document.getElementById(\'s\').hidden=false">open</button>'
          '<div id="s" class="{cls}" style="{style}" hidden><p class="text-white" style="color:#1D2C3B">Restaurant</p>'
          '<p class="text-zinc-400" style="color:#58626B">description</p></div>')


def open_page(tmp_path, monkeypatch, cls: str, style: str) -> dict:
    """Runs the real walk_opened() on one local page whose surface opens on a click."""
    from playwright.sync_api import sync_playwright
    (tmp_path / "o.html").write_text("<!doctype html><body style='background:#F7F4EE'>"
                                     + OPENER.format(cls=cls, style=style))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(census_mod, "SCENARIOS", [
        ("local-surface", "/o.html", "walk", None, False, lambda page: page.click("#open"), ["#s"])])
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


@needs_browser
def test_e2e_guilt_ink_on_the_dark_dropdown_ground_counts(tmp_path, monkeypatch):
    census = open_page(tmp_path, monkeypatch, "bg-[#1c1c1f]/95", "background-color: rgb(28 28 31 / 0.95)")
    out = census_mod.opened_verdict(census, SURFACES)
    assert out[0] == "opened-surfaces: 2 ok, 0 failed"
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 1"
    assert out[-1] == "opened-text-below-4.5: 4"
    assert any(" 1.05  #1D2C3B on #272729  'Restaurant'" in ln for ln in out)


@needs_browser
def test_e2e_innocence_an_elevated_surface_with_ink_text_counts_zero(tmp_path, monkeypatch):
    census = open_page(tmp_path, monkeypatch, "bg-[#1c1c1f]/95", "background-color: #FFFCF7")
    out = census_mod.opened_verdict(census, SURFACES)
    assert out[0] == "opened-surfaces: 2 ok, 0 failed"
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 0"
    assert out[-1] == "opened-text-below-4.5: 0"


def test_the_origin_main_opened_walk_is_the_guilt(census):
    """Main today: every surface opens; the dropdown titles are white and readable, the red code chip is not."""
    out = census_mod.opened_verdict(census, SURFACES)
    assert out[0] == "opened-surfaces: 19 ok, 0 failed"
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 21"
    assert out[-1] == "opened-text-below-4.5: 386"
    drop = next(o for o in census["opened"] if o["name"] == "search-dropdown" and o["walk"] == "desktop/light")
    assert [(p["ratio"], p["fg"], p["text"]) for p in drop["below"]] == [(3.31, "#DC2626", "56101"),
                                                                        (3.31, "#DC2626", "55130")]
    assert all(p["text"] not in ("Restaurant", "Villa") for p in drop["below"])


def test_guilt_8161s_head_reads_ink_titles_on_the_dark_dropdown():
    """The opened search rows dumped live at #8161's head (51b2407f27): the BLOCK, counted."""
    rows = [json.loads(ln) for ln in (FIXTURE.parent / "r19_opened_8161_search.jsonl").read_text().splitlines()]
    out = census_mod.opened_verdict({"opened": rows, "opened_failed": []}, SURFACES)
    drop = next(o for o in rows if o["name"] == "search-dropdown" and o["walk"] == "desktop/light")
    titles = [(p["ratio"], p["fg"], p["bg"]) for p in drop["below"] if p["text"] in ("Restaurant", "Villa")]
    assert titles == [(1.05, "#1D2C3B", "#272729")] * 2
    assert any(ln.startswith("  bg-[#1c1c1f]/95  expected elevated #FFFCF7 (opaque), painted #1C1C1F alpha 0.95")
               for ln in out)
    assert out[-1] == "opened-text-below-4.5: 88"
