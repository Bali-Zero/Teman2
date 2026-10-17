"""Offline replay of the /kbli* R19 wrapper token census against its contract.

The fixture is the census dumped (`--json`) by the live run on 5 pages x 6
states; these tests judge it with the committed contract, so they need no
browser and no dev server.
"""
from __future__ import annotations

import collections
import copy
import json
import re
import struct
import subprocess
import sys
import zlib
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
    assert len(census["captures"]) == 54 and census["failed"] == []
    assert any(line.startswith("colors-outside-direction-a: ") for line in out)
    assert out[-1].startswith("state-colors-off-contract: ")


def test_the_two_reds_of_7508_are_in_the_census(census):
    # Since W2''' the fixture is the walk at the wrapper's head: the alias resolves on the wrapper.
    assert census["reads"]["var --color-text-secondary"]["defined"] == "wrapper"
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
    assert out["pages"] == [p for p in census_mod.PAGES if p != census_mod.SECTOR_PAGE]
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
    """The fixture is the live walk at the W2''' head (it was origin/main 463ec63b76 with 51 off, 0 unseen):
    18 walks, every verdict line 0, and the rows the #8139 gate caught now paint their own hex."""
    assert len(census["walks"]) == 18 and census["walk_failed"] == []
    out = verdict(census)
    assert out[-1] == "state-colors-off-contract: 0"
    for line in ("state-rows-unseen: 0", "read-but-undefined: 0", "colors-outside-direction-a: 0"):
        assert line in out
    caught = {"hover:bg-surface-editorial-elevated": "#EAE3D8",
              "group-hover:text-[color:var(--accent-zantara)]": "#233D52",
              "group-hover:bg-[color-mix(in_srgb,var(--accent-zantara)_10%,transparent)]": "#EAE3D8",
              "selection:bg-accent-sand/30": "#EAE3D8", "selection:text-accent-sand": "#1D2C3B"}
    for token, hx in caught.items():
        assert census["state_obs"][token]["observed"] == [hx], token


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


REPO = Path(__file__).resolve().parents[3]
CTA_CURE = """/*
 * The copper primary-action hover carries elevated text (contract section 7.1).
 */
.hover\\:bg-\\[\\#D01033\\]\\/90:is(.kbli-r19, .kbli-r19 *):hover {
  color: var(--kbli-bg-elevated);
}
"""
SONNER_CURE = """/*
 * Sonner richColors must not restore type-specific dark control fills inside R19.
 * Icons and descriptions have no fill and keep inheriting the ink rule above.
 */
[data-sonner-toast]:is(.kbli-r19, .kbli-r19 *)
  :is([data-close-button], [data-button]) {
  background: var(--kbli-bg-surface) !important;
  border-color: var(--kbli-border) !important;
  color: var(--kbli-text-primary) !important;
}
"""


def _real_wrapper_css() -> str:
    return (REPO / "apps/mouth/src/styles/kbli-r19-wrapper.css").read_text()


def _real_sonner_css() -> str:
    candidates = (REPO / "node_modules/sonner/dist/styles.css",
                  REPO / "apps/mouth/node_modules/sonner/dist/styles.css")
    found = next((path for path in candidates if path.is_file()), None)
    assert found is not None, f"sonner styles.css not found at: {', '.join(map(str, candidates))}"
    return found.read_text()


def _without_cure(css: str, cure: str) -> str:
    assert css.count(cure) == 1
    return css.replace(cure, "")


def _static_paints(tmp_path, body: str, css: str, selectors: list[str], hover: str | None = None) -> dict:
    """Render a local page and return its real computed control paints."""
    from playwright.sync_api import sync_playwright
    page_path = tmp_path / "g.html"
    page_path.write_text(f"<!doctype html><style>{css}</style>{body}")
    m = census_mod._load_measure()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        page = browser.new_page()
        page.goto(page_path.as_uri())
        if hover:
            page.hover(hover)
        paints = page.evaluate(
            """selectors => Object.fromEntries(selectors.map(selector => {
              const element = document.querySelector(selector);
              const style = getComputedStyle(element);
              const glyph = element.matches("[data-close-button]") ? element.querySelector("svg") : null;
              return [selector, { color: style.color, glyph: getComputedStyle(glyph || element).color,
                                  background: style.backgroundColor, border: style.borderTopColor }];
            }))""", selectors)
        browser.close()
        return paints


def _hex(css_colour: str) -> str:
    rgb = census_mod._load_measure().rgb_of(css_colour)
    assert rgb is not None, css_colour
    return "#" + "".join(f"{round(channel):02X}" for channel in rgb)


def _paint_contrast(paint: dict) -> float:
    ground = _hex(paint["background"])
    foreground = census_mod.text_colour({"fg": _hex(paint["glyph"]), "a": ground, "fa": 1})
    return census_mod.contrast(foreground, ground)


CTA_CLASSES = (
    "mt-8 inline-flex items-center gap-2 rounded-xl bg-[var(--kbli-bg-surface)] backdrop-blur-md "
    "border border-[color:var(--border-strong)] px-7 py-3.5 text-sm font-bold text-white transition-all "
    "duration-300 hover:bg-[#D01033]/90 hover:border-accent-sand active:scale-[0.98]"
)


@needs_browser
def test_e2e_cta_hover_uses_elevated_text_on_copper_and_mutant_fails(tmp_path):
    body = f'<div class="kbli-r19"><a id="cta" class="{CTA_CLASSES}" href="#search">Explore</a></div>'
    # The utility declaration is the only compiled Tailwind CSS this static fixture needs.
    utility = ".text-white{color:var(--color-white)}"
    css = utility + _real_wrapper_css()
    clean = _static_paints(tmp_path, body, css, ["#cta"], hover="#cta")["#cta"]
    assert _hex(clean["background"]) == "#A44B36"
    assert _hex(clean["color"]) == "#FFFCF7"
    assert round(_paint_contrast(clean), 2) >= 5.64

    mutant = _static_paints(tmp_path, body, _without_cure(css, CTA_CURE), ["#cta"], hover="#cta")["#cta"]
    assert _hex(mutant["background"]) == "#A44B36"
    assert _paint_contrast(mutant) == pytest.approx(2.47, abs=0.01)


def _toast(toast_type: str) -> str:
    return f'''<li id="{toast_type}" data-sonner-toast data-rich-colors="true" data-styled="true"
      data-type="{toast_type}"><div data-icon><svg viewBox="0 0 16 16"><path d="M2 8h12"/></svg></div>
      <div data-content><div data-title>Title</div><div data-description>Description</div></div>
      <button data-button data-action>Action</button><button data-button data-cancel>Cancel</button>
      <button data-close-button><svg viewBox="0 0 16 16"><path d="M3 3l10 10M13 3L3 13"/></svg></button></li>'''


@needs_browser
def test_e2e_sonner_rich_controls_stay_on_contract_and_mutant_fails(tmp_path):
    body = ('<div class="kbli-r19"><ol data-sonner-toaster data-sonner-theme="dark">'
            + _toast("success") + _toast("error") + "</ol></div>")
    css = _real_sonner_css() + _real_wrapper_css()
    selectors = [f"#{kind} {part}" for kind in ("success", "error")
                 for part in ("[data-close-button]", "[data-icon]", "[data-description]",
                              "[data-action]", "[data-cancel]")]
    clean = _static_paints(tmp_path, body, css, selectors)
    contract_colours = set(census_mod.DIRECTION_A.values()) | set(census_mod.SEMANTIC.values())
    for kind in ("success", "error"):
        close = clean[f"#{kind} [data-close-button]"]
        assert _hex(close["background"]) in contract_colours
        assert _hex(close["border"]) == "#DAD8D1"
        assert _paint_contrast(close) >= 4.5
        for part in ("[data-icon]", "[data-description]"):
            paint = clean[f"#{kind} {part}"]
            assert _hex(paint["color"]) == "#1D2C3B"
            assert paint["background"] == "rgba(0, 0, 0, 0)"
        for part in ("[data-action]", "[data-cancel]"):
            paint = clean[f"#{kind} {part}"]
            assert _hex(paint["background"]) in contract_colours
            assert _paint_contrast(paint) >= 4.5

    mutant = _static_paints(tmp_path, body, _without_cure(css, SONNER_CURE),
                            ["#success [data-close-button]", "#error [data-close-button]"])
    assert _paint_contrast(mutant["#success [data-close-button]"]) == pytest.approx(1.23, abs=0.01)
    assert _paint_contrast(mutant["#error [data-close-button]"]) == pytest.approx(1.29, abs=0.01)


HANDOFF_CURE = """/*
 * The shared CTAHandoff bar is sticky to the viewport bottom: inside R19 it sat over the persona
 * cards, the stat pills and the last lines of every page. It stays in the flow, at the end of the page.
 */
[role="group"][aria-label="Next actions"]:is(.kbli-r19, .kbli-r19 *) {
  position: static !important;
}
"""
CANVAS_CURE = """/*
 * The page canvas behind the wrapper is the global dark body: an overscroll bounce or a short page showed it
 * as a dark band under the paper. The canvas takes Direction A's paper while an R19 wrapper is mounted.
 */
html:has(.kbli-r19),
body:has(.kbli-r19) {
  background-color: #f7f4ee;
}
"""
# CTAHandoff's own inline style, as packages/core/components/CTAHandoff.tsx renders it.
HANDOFF = ('<div role="group" aria-label="Next actions" style="display:flex;padding:8px 16px;position:sticky;'
           'z-index:40;bottom:0;background:#fff;border-top:1px solid #ddd"><a href="#" style="min-height:44px">'
           'Talk on WhatsApp</a></div>')


def _boxes(tmp_path, body: str, css: str, probes: list[str], scroll: int = 0) -> dict:
    from playwright.sync_api import sync_playwright
    page_path = tmp_path / "b.html"
    page_path.write_text(f"<!doctype html><style>body{{margin:0}}{css}</style>{body}")
    m = census_mod._load_measure()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=m.CHROME)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(page_path.as_uri())
        page.evaluate("y => window.scrollTo(0, y)", scroll)
        boxes = page.evaluate("""selectors => Object.fromEntries(selectors.map(selector => {
          const r = document.querySelector(selector).getBoundingClientRect();
          return [selector, { top: r.top, bottom: r.bottom }];
        }))""", probes)
        browser.close()
        return boxes


@needs_browser
def test_e2e_the_handoff_bar_never_overlaps_the_page_and_mutant_fails(tmp_path):
    body = (f'<div class="kbli-r19"><div id="page" style="height:3000px">content</div>{HANDOFF}</div>')
    css = _real_wrapper_css()
    for scroll in (0, 700):
        clean = _boxes(tmp_path, body, css, ["#page", "[aria-label='Next actions']"], scroll)
        assert clean["[aria-label='Next actions']"]["top"] >= clean["#page"]["bottom"]
    mutant = _boxes(tmp_path, body, _without_cure(css, HANDOFF_CURE), ["#page", "[aria-label='Next actions']"])
    assert mutant["[aria-label='Next actions']"]["top"] < mutant["#page"]["bottom"]


@needs_browser
def test_e2e_the_canvas_behind_an_r19_wrapper_is_paper_and_mutant_fails(tmp_path):
    from playwright.sync_api import sync_playwright
    m = census_mod._load_measure()

    def canvas(css: str) -> tuple[str, str]:
        page_path = tmp_path / "c.html"
        page_path.write_text('<!doctype html><style>body{background:rgb(29,39,59)}' + css
                             + '</style><div class="kbli-r19">x</div>')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            page = browser.new_page()
            page.goto(page_path.as_uri())
            read = page.evaluate("""() => [getComputedStyle(document.documentElement).backgroundColor,
                                          getComputedStyle(document.body).backgroundColor]""")
            browser.close()
            return tuple(_hex(c) for c in read)
    css = _real_wrapper_css()
    assert canvas(css) == ("#F7F4EE", "#F7F4EE")
    assert canvas(_without_cure(css, CANVAS_CURE))[1] == "#1D273B"


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
def test_e2e_the_state_walk_hovers_an_entrance_held_with_forwards_at_its_end_state(tmp_path, monkeypatch):
    """W0d-3b-2: the state walk finishes motion as the resolvers do. Removed, the entrance would sit under the bar,
    covered, and its hover would never be observed."""
    body, css = bracket_page("#233D52")
    bar = '<div style="position:relative;z-index:2;height:64px;background:#1D2C3B"></div>'
    census = walk_page(tmp_path, monkeypatch, bar + body.replace('class="group"', 'class="group in"'),
                       css + ".in{display:block;transform:translateY(-64px);animation:drop .3s forwards}"
                             "@keyframes drop{to{transform:none}}")
    assert census["state_obs"][BRACKET]["observed"] == ["#233D52"]


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


class ThemePage:
    """A page whose data-theme reads `seq` in turn: what hydration left, then what holds after it is forced."""
    def __init__(self, *seq):
        self.seq, self.set = list(seq), []

    def evaluate(self, js, arg=None):
        if arg is not None:
            self.set.append(arg)
            return None
        return self.seq.pop(0)

    def wait_for_timeout(self, ms):
        pass


@pytest.mark.parametrize("seq,forced,raises,sets", [(("light",), "light", False, []), (("dark", "light"), "light", False,
                                                    ["light"]), (("dark", "dark"), "light", True, ["light"]),
                                                    ((), None, False, [])],
                         ids=["held", "hydrated over, forced again", "the page keeps its own", "system theme"])
def test_a_forced_theme_holds_after_hydration_or_the_walk_fails_naming_it(seq, forced, raises, sets):
    page = ThemePage(*seq)
    if raises:
        with pytest.raises(RuntimeError, match=r"^theme: the page hydrated data-theme='dark' over 'light'$"):
            census_mod.force_theme(page, forced)
    else:
        census_mod.force_theme(page, forced)
    assert page.set == sets


def test_an_over_image_only_walk_fails_yet_its_grounds_are_listed():
    out = verdict_of({"opened": [walk("x", [run("#16161A", fg="#F5F6F7", image="gradient")])]})
    assert out[0] == "opened-surfaces: 0 ok, 1 failed"
    assert out[1 + len(census_mod.NOT_JUDGEABLE)].startswith("  x desktop/light: failed:over-image-only (1 runs)")
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


CONTRACT = census_mod.CONTRACT.read_text()
NAMES = {sc[0] for sc in census_mod.SCENARIOS}


def test_innocence_every_overlay_on_the_tree_has_a_section_8_7_row_and_no_row_is_stale():
    """W0d-3: on this tree U is 0, and every row still names a hit."""
    hits, rows = census_mod.overlay_hits(), census_mod.parse_overlays(CONTRACT, NAMES)
    assert census_mod.unclaimed_verdict(hits, rows) == ["surfaces-unclaimed: 0"]
    assert sorted(rows) == sorted(hits)


def test_guilt_g30_a_new_portal_in_the_fence_with_no_row_is_unclaimed(tmp_path):
    """G30: a createPortal( in a fence file, and a class-string overlay in a file it imports, with no section 8.7
    row: U counts both, keyed file::pattern::ordinal. Comments, closing tags and URL strings are not hits."""
    fence = tmp_path / "apps/mouth/src/components/kbli"
    fence.mkdir(parents=True)
    (tmp_path / "apps/mouth/src/lib").mkdir(parents=True)
    (fence / "Pop.tsx").write_text(
        'import { Sheet } from "@/lib/sheet";\n// createPortal( in a comment is not a hit\n'
        'const u = "https://example.invalid/x";\nexport const Pop = () => createPortal(<Sheet />, document.body);\n')
    (tmp_path / "apps/mouth/src/lib/sheet.tsx").write_text(
        'export const Sheet = () => <div className="fixed inset-0 z-50 bg-black/70" />;\n')
    (fence / "Pop.test.tsx").write_text('createPortal(<div role="dialog" />, document.body);\n')
    hits = census_mod.overlay_hits(tmp_path)
    assert hits == {"apps/mouth/src/components/kbli/Pop.tsx::createPortal(::0": 4,
                    "apps/mouth/src/lib/sheet.tsx::overlay::0": 1}
    rows = census_mod.parse_overlays(CONTRACT, NAMES)
    assert census_mod.unclaimed_verdict(hits, rows) == [
        "  apps/mouth/src/components/kbli/Pop.tsx::createPortal(::0 (line 4) has no section 8.7 row",
        "  apps/mouth/src/lib/sheet.tsx::overlay::0 (line 1) has no section 8.7 row", "surfaces-unclaimed: 2"]


@pytest.mark.parametrize("source,key", [
    ('<div className="fixed inset-0\n z-50 bg-black/70" />', "overlay::0"),
    ("<div className='fixed inset-0\n z-50 bg-black/70' />", "overlay::0"),
    ('<div role = "dialog" />', "role::0"),
    ('<div role={ "dialog" } />', "role::0"),
    ("<p>Don't miss this</p>\n// <div role=\"dialog\" />\n<p>It's fine</p>\n<div role=\"listbox\" />", "role::0"),
], ids=["multiline-double-quote", "multiline-single-quote", "spaced-role", "expression-role", "prose-apostrophes-keep-comments"])
def test_guilt_b1_valid_jsx_overlay_forms_do_not_bypass_surfaces_unclaimed(tmp_path, source, key):
    """B1 (#8617 gate): multiline className strings, spaced/expression role attributes, and prose apostrophes must
    produce the exact unclaimed overlay hit without swallowing comments."""
    f = tmp_path / "apps/mouth/src/components/kbli/Overlay.tsx"
    f.parent.mkdir(parents=True)
    f.write_text("export const Overlay = () => (<>" + source + "</>);\n")
    hits = census_mod.overlay_hits(tmp_path)
    assert list(hits) == [f"apps/mouth/src/components/kbli/Overlay.tsx::{key}"]
    assert census_mod.unclaimed_verdict(hits, {})[-1] == "surfaces-unclaimed: 1"


def test_guilt_g31_the_floating_results_row_is_false_the_day_they_fill():
    """G31 + B2 (#8617 gate): section 8.7 declares the explorer's floating results unreachable because every
    setSearchResults call empties them. The static fact holds on this tree and fails on any call or reference
    that is not proved to pass []."""
    page = (census_mod.ROOT / "apps/mouth/src/app/kbli-explorer/page.tsx").read_text()
    assert census_mod.floating_results_unreachable(page)
    for call in (
        "setSearchResults(r)",
        "setSearchResults(results.filter(Boolean))",
        "setSearchResults(await loadResults())",
        "Promise.resolve([]).then(setSearchResults)",
    ):
        assert not census_mod.floating_results_unreachable(page.replace("setSearchResults([])", call, 1)), call


@pytest.mark.parametrize("row,error", [
    ("| `x.tsx::toast::0` | no-such-walk | why |", "neither a census scenario"),
    ("| `x.tsx::toast::0` | unreachable |  |", "needs its reason"),
    ("| `apps/mouth/src/components/kbli/KBLISearch.tsx::role::0` | search-dropdown | again |", "expected a new key"),
], ids=["an unknown claim", "a declared row without a reason", "a duplicate key"])
def test_the_overlay_table_refuses_a_row_it_cannot_trust(row, error):
    text = CONTRACT.replace("<!-- overlays:end -->", row + "\n\n<!-- overlays:end -->")
    with pytest.raises(census_mod.ContractError, match=error):
        census_mod.parse_overlays(text, NAMES)
    bad_sep = re.sub(r"(<!-- overlays:begin -->\s*\|[^\n]+\n)\|[^\n]+", r"\1| bad | sep | line |", CONTRACT, count=1)
    with pytest.raises(census_mod.ContractError, match="header must be"):
        census_mod.parse_overlays(bad_sep, NAMES)


def test_a_token_with_two_roles_needs_its_per_surface_row_declared():
    """W0d-3 (ii-2): bg-black/60 is section 5's wash on the /kbli card (app/kbli/page.tsx:187) and a scrim behind
    the explorer sidebar (app/kbli-explorer/page.tsx:1124). Its section 8.1 row is accepted only as a declared
    per-surface row, and both rows cross-reference each other."""
    contract = census_mod.load_contract(CONTRACT)
    states = census_mod.parse_states(CONTRACT, contract)
    surfaces = census_mod.parse_surfaces(CONTRACT, contract, states)
    assert surfaces["bg-black/60"]["ground"] == "scrim"
    assert "app/kbli-explorer/page.tsx:1124" in surfaces["bg-black/60"]["surface"]
    assert "on the /kbli card it is §5's wash" in surfaces["bg-black/60"]["reason"]
    assert "(`app/kbli/page.tsx:187`); the explorer sidebar backdrop is a scrim (§8.1)" in contract[("class", "bg-black/60")]["reason"]
    undeclared = CONTRACT.replace("Per-surface row (W0d-3)", "Second row (W0d-3)", 1)
    with pytest.raises(census_mod.ContractError, match="already has a section 5 or 7 row"):
        census_mod.parse_surfaces(undeclared, contract, states)


def test_the_section_8_5_shared_component_counts_and_cells_match_the_contract():
    """ii-4: section 8.5's NavShell and Footer cells and every count in section 8.5 match the pins and mutants."""
    assert "/visa/*` but `/visa/voa` (default); `/tax-calendar`, `/property/eligibility`, BlogNav, `/visa/voa` (paper once hydrated)" in CONTRACT
    assert "the marketing home mounts `components/r19/home/Footer`, another component" in CONTRACT
    assert sum(len(rs) for rs in census_mod.SHARED_PAIRS.values()) == 10 and "ten (pair,\n  route) pins" in CONTRACT
    assert len(PIN) == 24 and "24 walks in all" in CONTRACT
    assert {k: drift_of(MUTANTS[k]["shared"])[1] for k in ("I9", "A", "B", "I10")} == {
        "I9": "0", "A": "84", "B": "108", "I10": "0"}
    assert "D 84, all on `/v2`, `/v2/news` and `/visa/second-home`" in CONTRACT
    assert "D 108, on all six MobileNav pins" in CONTRACT



def test_the_census_walks_51_opened_surfaces_on_9_pages():
    """SPEC-W0d section 1.a: 9 pages (the sector route resolved at run time), 25 + 26 opened walks."""
    walks = {"all": 6, "walk": 2, "mobile": 1, "mobile-all": 3}
    assert len(census_mod.PAGES) == 9 and census_mod.SECTOR_PAGE in census_mod.PAGES
    assert sum(walks[sc[2]] for sc in census_mod.SCENARIOS) == 51
    opened = [u for u in census_mod.scenarios(*census_mod.measure_literals()) if u[1] == "opened"]
    assert len(opened) == 51 - len(census_mod.NOT_JUDGEABLE) == 51


def test_the_declared_not_judgeable_walks_are_exactly_the_pending_mobile_variant(monkeypatch):
    """W0d-3b-2a: on origin/main the exemption was a named row; W2''' empties NOT_JUDGEABLE and returns the walk."""
    assert census_mod.NOT_JUDGEABLE == {}
    names = {n for _, _, n, _ in census_mod.scenarios(*census_mod.measure_literals())}
    assert "zantara-pending desktop/light" in names and "zantara-pending mobile/system-dark" in names
    assert "declared-not-judgeable:" not in census_mod.opened_verdict({"opened": []}, {}, {}, None, [])
    monkeypatch.setattr(census_mod, "NOT_JUDGEABLE", {("zantara-pending", "mobile/system-dark"): "over-image"})
    names_exempt = {n for _, _, n, _ in census_mod.scenarios(*census_mod.measure_literals())}
    assert "zantara-pending mobile/system-dark" not in names_exempt
    assert "declared-not-judgeable: zantara-pending mobile/system-dark" in census_mod.opened_verdict(
        {"opened": []}, {}, {}, None, [])


def test_guilt_an_all_over_image_walk_is_still_failed():
    run = {"state": "ok", "clip": False, "image": "gradient", "spread": 0}
    assert census_mod.walk_state({"roots": 1, "runs": [run, run]})[0] == "failed:over-image-only"


def test_the_sector_route_is_the_first_card_the_server_links(tmp_path):
    (tmp_path / "kbli").mkdir()
    (tmp_path / "kbli/sectors").write_text('<a href="/kbli">KBLI</a><a href="/kbli/sectors/A">A</a>'
                                           '<a href="/kbli/sectors/B">B</a>')
    server = serve(tmp_path, "")
    try:
        assert census_mod.sector_route(f"http://127.0.0.1:{server.server_port}") == "/kbli/sectors/A"
    finally:
        server.shutdown()


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
AT_BOTTOM = "position:absolute;left:7px;top:calc(100vh - 34px);padding:8px;"
TALL = "body{min-height:300vh}"
GLOW = ("; document.body.insertAdjacentHTML('beforeend', `<div style=\"position:fixed;left:0;bottom:0;width:64px;"
        "height:64px;filter:blur(6px) saturate(1.2);z-index:30\"><svg width='64' height='64'><circle cx='32' cy='32' "
        "r='8' fill='#25D366'/></svg></div>`)")
EDGE = ("; document.body.insertAdjacentHTML('beforeend', `<div style=\"position:fixed;left:0;bottom:0;width:44px;"
        "height:64px;filter:blur(6px);z-index:30\"><div style=\"width:44px;height:64px;background:#25D366\">"
        "</div></div>`)")
DEV = ("; document.body.insertAdjacentHTML('beforeend', `<nextjs-portal style=\"display:block;position:fixed;left:0;"
       "bottom:0;width:140px;height:60px;background:#111111;z-index:40\"></nextjs-portal>`)")
SHADOW = ("; document.body.insertAdjacentHTML('beforeend', `<div style=\"position:fixed;left:0;bottom:0;width:10px;"
          "height:10px;box-shadow:0 0 40px 30px rgba(0,0,0,.8);z-index:30\"></div>`)")
FLIP = ("<script>addEventListener('scroll', () => document.documentElement.setAttribute('data-theme', 'dark'),"
        " { once: true })</script>")
RELOAD = ("<script>addEventListener('scroll', () => { if (!sessionStorage.r) { sessionStorage.r = 1;"
          " location.reload(); } })</script>")
QUERY = ("; document.body.insertAdjacentHTML('beforeend', `<div class=\"tsqd-parent-container\"><div style=\""
         "position:fixed;left:0;bottom:0;width:140px;height:60px;background:#111111;z-index:40\"></div></div>`)")
# A ground that script motion cycles unless the reader asks for reduced motion: the census asks, so it reads the
# final frame (W0d-3b-2).
SCRIPTED = ("<script>if (!matchMedia('(prefers-reduced-motion: reduce)').matches) { const s = document.getElementById('s');"
            " let t = 0; (function f() { t += 1; s.style.background = t % 2 ? '#111111' : '#222222';"
            " requestAnimationFrame(f); })(); }</script>")
REHYDRATE = ("<script>setTimeout(() => { const h = document.documentElement;"
             " if (h.getAttribute('data-theme') === 'light') h.setAttribute('data-theme', 'dark'); }, 300)</script>")
LIFTED = "position:relative;z-index:10;background:#FFFCF7;padding:16px"
TOOLTIP = ('<span role="button" style="position:relative;color:#1D2C3B">KBLI<span style="position:absolute;left:0;'
           'top:28px;background:#A44B36;color:#FFFCF7;padding:4px;white-space:nowrap">Business code</span></span>')
BEFORE_CSS = ("{sel}{{position:relative;z-index:0;padding:8px}}"
              "{sel}::before{{content:'';position:absolute;inset:0;background:#111;z-index:-1}}")
CANVAS = ('<canvas id="cv" width="400" height="80" style="position:absolute;inset:0;width:100%;height:100%">'
          "</canvas>")
# id: body, css, opener (JS, or None to click a selector that is not there), selectors,
#     expected (P, K at least, M exactly or at least as ">=n", walk state, an excerpt every walk prints)
MENU_TOP = ('<div id="d" style="position:fixed;left:0;top:0;width:100%;height:64px;background:#FFFCF7;z-index:40">'
            + p(INK, "Menu") + "</div>")
STRIP = "position:absolute;left:7px;top:calc(100vh - 36px);padding:8px;background:#FFFCF7;z-index:10;"
STRIP_SCRIM = ('<div style="position:absolute;left:0;top:0;width:100%;height:calc(100vh - 40px);'
               'background:rgba(29,44,59,.45)"><div style="position:fixed;left:0;right:0;bottom:40px;height:4px;'
               'background:#25D366;z-index:30;{}"></div></div>' + MENU_TOP)


def faded_a1(wrapper_style: str) -> str:
    """A1: a flat absolute scrim in a wrapper, its child bar above the surface; the wrapper style is the variable."""
    return ('<div style="' + wrapper_style + '">'
            '<div style="position:absolute;left:0;top:0;width:100%;height:100vh;background:rgba(29,44,59,.45)">'
            '<div style="position:absolute;left:0;top:70px;width:100%;height:60px;z-index:20;background:#1D2C3B"></div></div>'
            + surface("position:relative;z-index:10;background:#FFFCF7;padding:16px",
                      p(INK) + p(INK, "Villa", "margin-top:40px")) + '</div>')


def scrim_over_static(scrim_style: str, child: bool = True) -> tuple:
    """A scrim over a static surface: it covers the run itself, so what it holds is behind it too (SPEC-3b2bi)."""
    bar = ('<div style="position:absolute;left:0;top:70px;width:100%;height:60px;background:#1D2C3B"></div>'
           if child else "")
    return (surface("background:#FFFCF7;padding:16px", p(INK) + p(INK, "Villa", "margin-top:40px")), "",
            appended('<div style="position:absolute;left:0;top:0;width:100%;height:100vh;background:rgba(29,44,59,.45);'
                     + scrim_style + f'">{bar}</div><div id="d" style="position:fixed;left:0;bottom:0;width:100%;'
                     f'height:64px;background:#FFFCF7;z-index:40">{p(INK, "Menu")}</div>'), ["#s", "#d"],
            (2, 0, 0, "ok", None))


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
    # A 1.5% texture laid over the page, not fixed, is faint: no ground and no occluder.
    ("faint", surface("background:#FFFCF7;padding:16px", p(INK)), "",
     appended('<div style="position:absolute;inset:0;background-image:linear-gradient(45deg,#A0A0A0,#E0E0E0);'
              'opacity:.015;pointer-events:none;z-index:99"></div>'), ["#s"], (0, 0, 0, "ok", None)),
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
    # The #8202 gate: a floating button's blurred glow at the viewport's bottom-left, fixed, over a run there. Every
    # point is under the glow's filtered box but off its circle: the run is read again in the middle (G and I).
    ("G-badge", surface(f"{AT_BOTTOM}background:#222222", p(LIGHT, "Villa")), TALL, REVEAL + GLOW, ["#s"],
     (0, 1, 0, "ok", "  ground #222222 under 'Villa'")),
    ("I-badge", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK, "Villa")), TALL, REVEAL + GLOW, ["#s"],
     (0, 0, 0, "ok", None)),
    # A glow whose box ends inside the run: the points past its edge are left, and its blur reaches them.
    ("I-badge-edge", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK)), TALL, REVEAL + EDGE, ["#s"],
     (0, 0, 0, "ok", None)),
    # The dev server's indicator is never painted: on a page that cannot scroll, the run under it is read.
    ("I-dev-indicator", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK, "Villa")), "", REVEAL + DEV, ["#s"],
     (0, 0, 0, "ok", None)),
    # An opener whose first click lands before hydration, so the surface is not there or the opener throws: the page
    # is loaded and opened once more. The count lives in sessionStorage, which a reload keeps.
    ("I-opener-twice", surface("background:#FFFCF7;padding:16px", p(INK)), "",
     "sessionStorage.n = +(sessionStorage.n || 0) + 1; if (+sessionStorage.n > 1) { " + REVEAL + " }", ["#s"],
     (0, 0, 0, "ok", None)),
    ("I-opener-throws", surface("background:#FFFCF7;padding:16px", p(INK)), "",
     "sessionStorage.n = +(sessionStorage.n || 0) + 1; if (+sessionStorage.n === 1) throw new Error('early'); "
     + REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    # A page that hydrates its own theme over the forced light one is forced again before it is read.
    ("I-theme-hydrated", surface("background:#FFFCF7;padding:16px", p(INK)) + REHYDRATE,
     "[data-theme=dark] #s{background:#111111!important}", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    # W0d-3, the #8202 gate's notes. An occluded run whose occluder is a sibling inside its own surface is text
    # its reader cannot see: its own K line, the gate's case d'.
    ("G-occluded", surface("position:relative;background:#FFFCF7;padding:16px", p(INK) + p(INK, "Villa")
                           + '<div style="position:absolute;left:0;top:0;width:100%;height:40px;'
                           'background:rgba(0,0,0,.6)"></div>'), "", REVEAL, ["#s"],
     (0, 1, 0, "ok", "  occluded 'Restaurant' at ")),
    # A run under another surface the walk opened is the surface order working (P counts the portal outside).
    ("I-surface-over-surface", surface("background:#FFFCF7;padding:16px", p(INK) + p(INK, "Villa")),
     "", appended('<div id="d" style="position:absolute;left:0;top:0;width:100%;height:64px;background:#FFFCF7;'
                  f'z-index:20">{p(INK, "Menu")}</div>'), ["#s", "#d"], (2, 0, 0, "ok", None)),
    # A scrim painted by a gradient, or by a backdrop blur alone, is judged: a scrim is translucent ink.
    ("G-gradient-scrim", surface(LIFTED, p(INK)), "",
     appended(SCRIM.format("linear-gradient(rgba(29,44,59,.4),rgba(29,44,59,.5))")), ["#s"],
     (0, 1, 0, "ok", "  scrim no colour over an image at ")),
    ("G-blur-scrim", surface(LIFTED, p(INK)), "",
     appended('<div style="position:fixed;inset:0;backdrop-filter:blur(4px);z-index:5"></div>'), ["#s"],
     (0, 1, 0, "ok", "  scrim no colour at ")),
    ("I-blur-ink-scrim", surface(LIFTED, p(INK)), "",
     appended('<div style="position:fixed;inset:0;background:rgba(29,44,59,.45);backdrop-filter:blur(4px);'
              'z-index:5"></div>'), ["#s"], (0, 0, 0, "ok", None)),
    # Translucent ink over an image is still an image under the surface: off contract.
    ("G-ink-image-scrim", surface(LIFTED, p(INK)), "",
     appended(SCRIM.format("linear-gradient(rgba(29,44,59,.2),rgba(29,44,59,.3)) rgba(29,44,59,.45)")), ["#s"],
     (0, 1, 0, "ok", "  scrim #1D2C3B alpha 0.45 over an image at ")),
    # A run of one surface under the walk's scrim, behind the surface it serves, is the surface order working.
    ("I-under-the-walks-scrim", surface("background:#FFFCF7;padding:16px", p(INK)), "",
     appended(SCRIM.format("rgba(29,44,59,.45)") + '<div id="d" style="position:fixed;left:0;bottom:0;width:100%;'
              f'height:64px;background:#FFFCF7;z-index:20">{p(INK, "Menu")}</div>'), ["#s", "#d"],
     (2, 0, 0, "ok", None)),
    # W0d-3b-2b (the #8249 gate's binding 3): a child of a FLAT scrim (absolute, no z-index, so no stacking context)
    # can sit above the surface and hide a run; it is counted, where a child of a fixed scrim cannot rise.
    ("G-flat-scrim-child", surface("position:relative;z-index:10;background:#FFFCF7;padding:16px",
                                   p(INK) + p(INK, "Villa", "margin-top:40px")), "",
     appended('<div style="position:absolute;left:0;top:0;width:100%;height:100vh;background:rgba(29,44,59,.45)">'
              '<div style="position:absolute;left:0;top:70px;width:100%;height:60px;z-index:20;background:#1D2C3B">'
              '</div></div>'), ["#s"], (0, 1, None, "ok", "  occluded 'Villa' at ")),
    # W0d-3b-2b-i' (the #8560 gate's A1): the flat scrim sits inside a FIXED wrapper. The scrim's own ancestors do
    # not make it a stacking context, so its child still rises above the surface and is counted.
    ("G-flat-scrim-in-fixed-wrapper", '<div style="position:fixed;inset:0;z-index:5">'
     '<div style="position:absolute;left:0;top:0;width:100%;height:100vh;background:rgba(29,44,59,.45)">'
     '<div style="position:absolute;left:0;top:70px;width:100%;height:60px;z-index:20;background:#1D2C3B"></div></div>'
     + surface("position:relative;z-index:10;background:#FFFCF7;padding:16px",
               p(INK) + p(INK, "Villa", "margin-top:40px")) + '</div>', "", REVEAL, ["#s"],
     (0, 1, None, "ok", "  occluded 'Villa' at ")),
    # Its innocence twins: a scrim that is itself fixed, or that blurs its backdrop, holds its child.
    # SPEC-3b2bi: a wrapper that fades, or is positioned, does not make the scrim stack: the child still rises.
    ("G-flat-scrim-faded-wrapper", faded_a1("position:fixed;inset:0;z-index:5;opacity:.99"), "", REVEAL, ["#s"],
     (0, 1, None, "ok", "  occluded 'Villa' at ")),
    ("G-flat-scrim-faded-abs-wrapper", faded_a1("position:absolute;inset:0;z-index:5;opacity:.99"), "", REVEAL, ["#s"],
     (0, 1, None, "ok", "  occluded 'Villa' at ")),
    # Its innocence: the scrim covers the run itself, by whatever it is that puts it above the surface.
    # SPEC-3b2bi r1, the reach path. within() decides THAT an overlay reaches; whether a scrim exempts is read at p, where
    # the run is. R-A: the bar's glow changes the run's pixels while the flat scrim lies UNDER the run at p: counted.
    ("G-reach-glow-scrim-under-run", surface("position:absolute;left:7px;top:calc(100vh - 44px);padding:8px;"
                                             "background:#FFFCF7;z-index:10", p(INK, "Villa")), "",
     appended('<div style="position:absolute;left:0;top:0;width:100%;height:100vh;background:rgba(29,44,59,.45)">'
              '<div style="position:fixed;left:0;right:0;bottom:0;height:4px;background:#25D366;filter:blur(12px);'
              'z-index:30"></div></div>' + MENU_TOP), ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    # R-D / R-C: the scrim ends 40px above the bottom and the run sits below it, so the scrim is absent at p; its
    # child bar's shadow (R-D) or blur (R-C) still lands on the run: counted.
    ("G-reach-shadow-scrim-absent", surface(STRIP, p(INK, "Villa")), "",
     appended(STRIP_SCRIM.format('box-shadow:0 24px 8px 8px rgba(0,0,0,.85)')), ["#s", "#d"],
     (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("G-reach-blur-scrim-absent", surface(STRIP, p(INK, "Villa")), "",
     appended(STRIP_SCRIM.format('filter:blur(16px)')), ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    # R-E / R-E2: the scrim covers the run at p and holds the reaching bar: behind the scrim, exempt.
    ("I-reach-scrim-covers-run-fixed", surface(AT_BOTTOM + "background:#FFFCF7", p(INK, "Villa")), "",
     appended('<div style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:30;background:rgba(29,44,59,.45)">'
              '<div style="position:fixed;left:0;right:0;bottom:0;height:4px;background:#25D366;filter:blur(8px)"></div>'
              '</div>' + MENU_TOP), ["#s", "#d"], (2, 0, 0, "ok", None)),
    ("I-reach-scrim-covers-run-flat", surface(AT_BOTTOM + "background:#FFFCF7", p(INK, "Villa")), "",
     appended('<div style="position:absolute;left:0;top:0;width:100%;height:100vh;background:rgba(29,44,59,.45)">'
              '<div style="position:fixed;left:0;right:0;bottom:0;height:4px;background:#25D366;filter:blur(8px)"></div>'
              '</div>' + MENU_TOP), ["#s", "#d"], (2, 0, 0, "ok", None)),
    # R-B, DECLARED: a bar confined under the run's surface, in a fixed z5 scrim. within() says it reaches (its own,
    # older nearest-point rule) and the scrim is under the run at p, so it is counted: an accepted over-count that errs
    # in the fail-closed direction (SPEC-3b2bi section 2). The paint is unchanged (delta 0), see the receipts.
    ("D-reach-bar-confined-under-surface", surface("position:absolute;left:7px;top:calc(100vh - 44px);padding:8px;"
                                                   "background:#FFFCF7;z-index:10", p(INK, "Villa")), "",
     appended('<div style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:5;background:rgba(29,44,59,.45)">'
              '<div style="position:fixed;left:0;right:0;bottom:0;height:4px;background:#25D366;filter:blur(12px)"></div>'
              '</div>' + MENU_TOP), ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("I-scrim-own-opacity", *scrim_over_static("opacity:.99")),
    ("I-scrim-zindex", *scrim_over_static("z-index:30")),
    ("I-scrim-isolate", *scrim_over_static("isolation:isolate")),
    ("I-scrim-translate", *scrim_over_static("translate:1px 0")),
    ("I-flat-scrim-itself", *scrim_over_static("", child=False)),
    ("I-fixed-scrim-child", surface("background:#FFFCF7;padding:16px", p(INK) + p(INK, "Villa", "margin-top:40px")), "",
     appended('<div style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:30;background:rgba(29,44,59,.45)">'
              '<div style="position:absolute;left:0;top:70px;width:100%;height:60px;background:#1D2C3B"></div></div>'
              '<div id="d" style="position:fixed;left:0;bottom:0;width:100%;height:64px;background:#FFFCF7;'
              f'z-index:40">{p(INK, "Menu")}</div>'), ["#s", "#d"], (2, 0, 0, "ok", None)),
    ("I-blur-scrim-child", surface("background:#FFFCF7;padding:16px", p(INK) + p(INK, "Villa", "margin-top:40px")), "",
     appended('<div style="position:absolute;left:0;top:0;width:100%;height:100vh;z-index:30;'
              'background:rgba(29,44,59,.45);backdrop-filter:blur(4px)"><div style="position:absolute;left:0;'
              'top:70px;width:100%;height:60px;background:#1D2C3B"></div></div>'
              '<div id="d" style="position:fixed;left:0;bottom:0;width:100%;height:64px;background:#FFFCF7;'
              f'z-index:40">{p(INK, "Menu")}</div>'), ["#s", "#d"], (2, 0, 0, "ok", None)),
    # W0d-3b-2: a surface that fades in and holds its end state is read at its end state, not at opacity 0.
    ("I-surface-entrance-held", surface("background:#FFFCF7;padding:16px", p(INK)),
     "#s{opacity:0;animation:fade .3s forwards}@keyframes fade{to{opacity:1}}", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    # W0d-3b-2: script motion that honours reduced motion is read at its final frame.
    ("I-reduced-motion-final-frame", surface("background:#FFFCF7;padding:16px", p(INK)) + SCRIPTED, "", REVEAL,
     ["#s"], (0, 0, 0, "ok", None)),
    # The #8228 gate's notes. 1: a run that stays under a fixed glow on a page that cannot scroll is counted.
    ("G-badge-unscrollable", surface(f"{AT_BOTTOM}background:#222222", p(LIGHT, "Villa")) + p(INK), "",
     REVEAL + GLOW, ["#s", "#s ~ p"], (0, 1, 0, "ok", "  occluded 'Villa' at ")),
    # 3: a fixed faint texture over the whole page is read through, not an occluder of every run.
    ("I-fixed-texture", surface("background:#FFFCF7;padding:16px", p(INK)), "",
     appended('<div style="position:fixed;inset:0;background-image:linear-gradient(45deg,#A0A0A0,#E0E0E0);'
              'opacity:.015;pointer-events:none;z-index:99"></div>'), ["#s"], (0, 0, 0, "ok", None)),
    # 4: a shadow paints past its element's box: a run within its reach is read in the middle instead.
    ("I-shadow-reach", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK, "Villa")), TALL, REVEAL + SHADOW, ["#s"],
     (0, 0, 0, "ok", None)),
    # A shadow reaches only from an overlay painted above the run: a shadowed bar behind the surface reaches nothing.
    ("I-glow-behind-the-surface", surface("position:absolute;left:0;top:calc(100vh - 60px);width:200px;height:60px;"
                                          "box-sizing:border-box;padding:8px;z-index:40;background:#FFFCF7",
                                          p(INK, "Villa")), "",
     appended('<div style="position:fixed;left:0;bottom:0;width:10px;height:10px;'
              'box-shadow:0 0 40px 30px rgba(0,0,0,.8);z-index:1"></div>'), ["#s"], (0, 0, 0, "ok", None)),
    # A shadow cast down from a bottom bar reaches nothing above the bar (the /v2 mobile CTA bar over the footer).
    ("I-shadow-cast-down", surface("position:absolute;left:7px;top:calc(100vh - 85px);padding:8px;"
                                   "background:#FFFCF7", p(INK, "Villa")), "",
     appended('<div style="position:fixed;left:0;right:0;bottom:0;height:56px;background:#121619;'
              'box-shadow:0 10px 15px -3px rgba(0,0,0,.1),0 4px 6px -4px rgba(0,0,0,.1);z-index:40"></div>'),
     ["#s"], (0, 0, 0, "ok", None)),
    # A blur paints three radii past its box: a run there, on a page that cannot scroll, is counted.
    ("G-blur-reach", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK, "Villa")) + p(INK), "",
     appended('<div style="position:fixed;left:0;right:0;bottom:0;height:4px;background:#25D366;'
              'filter:blur(8px);z-index:30"></div>'), ["#s", "#s ~ p"], (0, 1, 0, "ok", "  occluded 'Villa' at ")),
    # W0d-3b-2b (the #8488 gate's B2): a drop-shadow() in `filter` reaches nothing (contract 8.4), where the same
    # element with a blur() is counted just above; the shadow is cast down, past the bar, so nothing paints above it.
    ("I-drop-shadow-no-reach", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK, "Villa")) + p(INK), "",
     appended('<div style="position:fixed;left:0;right:0;bottom:0;height:4px;background:#25D366;'
              'filter:drop-shadow(0 12px 2px rgba(0,0,0,.5));z-index:30"></div>'), ["#s", "#s ~ p"], (0, 0, 0, "ok", None)),
    # The #8560 gate's N1 and M10 (ii-6): a fixed element whose only paint is a drop-shadow() cast toward the run
    # reaches nothing, even when every sample point of the run sits within one blur radius (<= 6px) of the bar.
    ("I-drop-shadow-only-no-reach",
     surface("position:absolute;left:7px;top:calc(100vh - 10px);padding:0;background:#FFFCF7",
             p(INK, "Villa", "font-size:6px;line-height:1")) + p(INK), "",
     appended('<div style="position:fixed;left:0;right:0;bottom:0;height:4px;'
              'filter:drop-shadow(0 0 8px rgba(0,0,0,.5));z-index:30"></div>'), ["#s", "#s ~ p"], (0, 0, 0, "ok", None)),
    # A transparent shadow paints nothing, so it reaches nothing.
    ("I-transparent-shadow", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK, "Villa")), "",
     appended('<div style="position:fixed;left:0;bottom:0;width:10px;height:10px;'
              'box-shadow:0 0 40px 30px rgba(0,0,0,0);z-index:30"></div>'), ["#s"], (0, 0, 0, "ok", None)),
    # 5: a page that turns its theme during the scroll walk fails the walk, naming it.
    ("G-theme-flip", surface("background:#FFFCF7;padding:16px", p(INK) + '<div style="height:150vh"></div>'
                             + p(INK, "Villa")) + FLIP, "", REVEAL, ["#s"],
     ("INC", None, "INC", "failed:never-opened (theme: the page turned data-theme='dark' during the walk)", None)),
    # 2: a page that reloads under the walk is walked once more.
    ("I-reload-mid-walk", surface("background:#FFFCF7;padding:16px", p(INK) + '<div style="height:150vh"></div>'
                                  + p(INK, "Villa")) + RELOAD, "", REVEAL, ["#s"], (0, 0, 0, "ok", None)),
    # The dev server's query devtools button sits in the same corner as its indicator: never painted.
    ("I-query-devtools", surface(f"{AT_BOTTOM}background:#FFFCF7", p(INK, "Villa")), "", REVEAL + QUERY, ["#s"],
     (0, 0, 0, "ok", None)),
    # W0d-3b-2b-ii (ii-11, mixed-point cause reduction): S covers only the run's centre and top corners (height 100vh-15px),
    # while S's child shadow (MIX-reach) or child ink bar (MIX-main), or the same bar outside S, covers the bottom corners
    # where S is absent. The non-exempt bottom points decide: counted.
    ("G-mix-reach", surface(STRIP, p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:calc(100vh - 15px);z-index:30;'
              'background:rgba(29,44,59,.45)"><div id="bar" style="position:fixed;left:0;right:0;top:calc(100vh - 60px);'
              'height:4px;background:#1D2C3B;box-shadow:0 40px 6px 10px rgba(0,0,0,.85)"></div></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("G-mix-reach-outside", surface(STRIP, p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:calc(100vh - 15px);z-index:30;'
              'background:rgba(29,44,59,.45)"></div><div id="bar" style="position:fixed;left:0;right:0;'
              'top:calc(100vh - 60px);height:4px;background:#1D2C3B;box-shadow:0 40px 6px 10px rgba(0,0,0,.85);'
              'z-index:31"></div>' + MENU_TOP), ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("G-mix-main", surface(STRIP, p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:calc(100vh - 15px);z-index:30;'
              'background:rgba(29,44,59,.45)"><div id="bar" style="position:absolute;left:0;width:100%;'
              'top:calc(100vh - 32px);height:32px;background:#1D2C3B"></div></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("G-mix-main-outside", surface(STRIP, p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:calc(100vh - 15px);z-index:30;'
              'background:rgba(29,44,59,.45)"></div><div id="bar" style="position:fixed;left:0;width:100%;'
              'top:calc(100vh - 32px);height:32px;background:#1D2C3B;z-index:31"></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    # S as its own reacher: when S ends above the run, its shadow over the run is counted; when S covers the run, exempt.
    ("G-self-shadow-scrim-absent", surface("position:absolute;left:7px;top:calc(100vh - 34px);padding:8px;"
                                           "background:#FFFCF7;z-index:10;", p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:calc(100vh - 40px);z-index:30;'
              'background:rgba(29,44,59,.45);box-shadow:0 24px 8px 8px rgba(0,0,0,.85)"></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("I-self-shadow-scrim-covers", surface("position:absolute;left:7px;top:calc(100vh - 34px);padding:8px;"
                                           "background:#FFFCF7;z-index:10;", p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:30;'
              'background:rgba(29,44,59,.45);box-shadow:0 24px 8px 8px rgba(0,0,0,.85)"></div>' + MENU_TOP),
     ["#s", "#d"], (2, 0, 0, "ok", None)),
    # Two scrims: S1 flat (under the z10 surface) holds a reaching glow bar; S2 fixed z20 covers the run. S1 is under the run, so counted.
    ("G-two-scrims-wrong-one-covers", surface("position:absolute;left:7px;top:calc(100vh - 44px);padding:8px;"
                                              "background:#FFFCF7;z-index:10", p(INK, "Villa")), "",
     appended('<div id="S" style="position:absolute;left:0;top:0;width:100%;height:100vh;background:rgba(29,44,59,.45)">'
              '<div id="bar" style="position:fixed;left:0;right:0;bottom:0;height:4px;background:#25D366;filter:blur(12px);'
              'z-index:30"></div></div><div id="S2" style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:20;'
              'background:rgba(29,44,59,.35)"></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    # W0d-3b-2b-ii (ii-12, simultaneous occluder precedence): at p, S (fixed z30) covers the run and holds an exempt
    # reaching glow, while a non-scrim opaque toast (fixed z40, main stack) or a non-scrim reacher also covers the run.
    # The non-exempt occluder takes precedence over the exempt one.
    ("G-near-first-reacher-and-toast", surface(AT_BOTTOM + "background:#FFFCF7", p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:30;'
              'background:rgba(29,44,59,.45)"><div id="bar" style="position:fixed;left:0;right:0;bottom:0;height:4px;'
              'background:#25D366;filter:blur(8px)"></div></div><div id="toast" style="position:fixed;left:0;bottom:0;'
              'width:240px;height:60px;z-index:40;background:#1D2C3B"></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("G-near-first-toast-only", surface(AT_BOTTOM + "background:#FFFCF7", p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:30;'
              'background:rgba(29,44,59,.45)"></div><div id="toast" style="position:fixed;left:0;bottom:0;'
              'width:240px;height:60px;z-index:40;background:#1D2C3B"></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
    ("G-two-reachers-exempt-first", surface(AT_BOTTOM + "background:#FFFCF7", p(INK, "Villa")), "",
     appended('<div id="S" style="position:fixed;left:0;top:0;width:100%;height:100vh;z-index:30;'
              'background:rgba(29,44,59,.45)"><div id="bar1" style="position:fixed;left:0;right:0;bottom:0;height:4px;'
              'background:#25D366;filter:blur(8px)"></div></div><div id="bar2" style="position:fixed;left:0;right:0;'
              'bottom:0;height:4px;background:#25D366;filter:blur(8px);z-index:40"></div>' + MENU_TOP),
     ["#s", "#d"], (2, 1, None, "ok", "  occluded 'Villa' at ")),
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
    # The content of a closed <details> is laid out under the section after it: it is not rendered, not occluded.
    ("I-closed-details", f'<details><summary style="color:{INK}">More</summary>{p(INK, "Hidden")}</details>'
                         f'<div style="background:#FFFCF7;padding:24px">{p(INK, "Body")}</div>', 0, None),
    # Its guilt twin (the #8249 gate's binding 1): an open <details> is rendered, and covered it is counted.
    ("G-open-details-covered", f'<details open><summary style="color:{INK}">More</summary>{p(INK, "Shown")}</details>'
                               '<div style="position:relative;z-index:2;margin-top:-96px;height:96px;'
                               'background:#1D2C3B"></div>', 2, "occluded 'Shown' at "),
    # W0d-3b-2: an entrance that starts collapsed and holds its end state with `forwards` is read at its end state,
    # not collapsed under the bar above it (the explorer's 2025-transition card under its composer, W0d-3b-1).
    ("I-entrance-held", '<style>.in{transform:translateY(-64px);animation:drop .3s forwards}'
                        '@keyframes drop{to{transform:none}}</style>'
                        '<div style="position:relative;z-index:2;height:64px;background:#1D2C3B"></div>'
                        f'<div class="in" style="background:#FFFCF7;padding:8px">{p(INK, "Notice")}</div>', 0, None),
    # The guilt side: an entrance without `forwards` ends where it started, collapsed under the bar, which is what
    # a reader sees, and it is still counted.
    ("G-entrance-not-held", '<style>.in{transform:translateY(-64px);animation:drop .3s}'
                            '@keyframes drop{to{transform:none}}</style>'
                            '<div style="position:relative;z-index:2;height:64px;background:#1D2C3B"></div>'
                            f'<div class="in" style="background:#FFFCF7;padding:8px">{p(INK, "Notice")}</div>', 1,
     "occluded 'Notice' at "),
    # W0d-3, the #8228 gate's note 1 at rest: text under a fixed glow on a page that cannot scroll is counted.
    ("G-occluded-at-rest", f'<div style="{AT_BOTTOM}background:#FFFCF7">{p(INK, "Villa")}</div>', 1,
     "occluded 'Villa' at ", '<div style="position:fixed;left:0;bottom:0;width:64px;height:64px;filter:blur(6px);'
     'z-index:30"><svg width="64" height="64"><circle cx="32" cy="32" r="8" fill="#25D366"/></svg></div>'),
]


@needs_browser
@pytest.mark.parametrize("case", PAGE_CASES, ids=[c[0] for c in PAGE_CASES])
def test_e2e_page_grounds_at_rest(tmp_path, case):
    """SPEC-W0d section 3, G25, G26 and I8: the page-level judge on a local wrapper at rest."""
    from playwright.sync_api import sync_playwright
    _, body, g, excerpt, *tail = case  # the tail is painted outside the wrapper
    server = serve(tmp_path, PAGE.format(css="", body=body, tail="".join(tail)))
    m = census_mod._load_measure()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            page = census_mod.new_context(browser, 1440, 900, "light").new_page()
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
def test_e2e_the_capture_pass_asks_for_reduced_motion(tmp_path, monkeypatch):
    """ii-5 (N3 / G6): capture_pages() itself runs under reduced motion, so a page whose script cycles its ground
    unless prefers-reduced-motion is reduce is read at its paper frame, and a mutant that drops reduced motion or
    calls page.emulate_media(reduced_motion='no-preference') inside capture_pages() fails behaviorally."""
    from playwright.sync_api import sync_playwright
    monkeypatch.setattr(census_mod, "SETTLE", {"load": 50, "ready": 100, "open": 150, "scroll": 50})
    body = f'<div id="s" style="background:#FFFCF7;padding:16px">{p(INK)}</div>' + SCRIPTED
    server = serve(tmp_path, PAGE.format(css="", body=body, tail=""))
    m = census_mod._load_measure()
    census = {"captures": [], "failed": [], "reads": {}, "colors": {}}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            census_mod.capture_pages(browser, m, f"http://127.0.0.1:{server.server_port}", census,
                                     [("rest", "capture", "/o.html desktop/light", ("/o.html", "desktop", "light"))])
            browser.close()
    finally:
        server.shutdown()
    assert census_mod.page_verdict(census) == ["page-grounds-off-contract: 0"]


@needs_browser
def test_e2e_a_static_page_reads_the_same_with_and_without_reduced_motion(tmp_path):
    """W0d-3b-2, innocence: asking for reduced motion changes nothing on a page that does not move."""
    from playwright.sync_api import sync_playwright
    body = f'<div style="background:#1D2C3B;padding:8px">{p(ELEVATED, "Indonesia")}</div>{p(INK, "Body")}'
    server = serve(tmp_path, PAGE.format(css="", body=body, tail=""))
    m = census_mod._load_measure()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            reads = []
            for ctx in (census_mod.new_context(browser, 1440, 900, "light"),
                        browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")):
                page = ctx.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/o.html", wait_until="load")
                reads.append(census_mod.page_grounds(page, "local desktop/light"))
            browser.close()
    finally:
        server.shutdown()
    assert reads[0] == reads[1] and reads[0]["page_runs"] == 2


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
    """W2''' head, by pixels: every surface opens inside the wrapper, every ground is on contract, and every run
    clears 4.5:1 (including zantara-pending mobile/system-dark, returned from NOT_JUDGEABLE)."""
    out = verdict_of(census, PIN, [])
    assert out[0] == "opened-surfaces: 51 ok, 0 failed"
    assert lines_of(out, "opened-outside-wrapper:") == "opened-outside-wrapper: 0"
    assert lines_of(out, "opened-grounds-off-contract:") == "opened-grounds-off-contract: 0"
    assert lines_of(out, "ground-resolver-disagree:") == "ground-resolver-disagree: 0"
    assert lines_of(out, "shared-touched-unpinned:") == "shared-touched-unpinned: 0"
    assert lines_of(out, "shared-component-drift:") == "shared-component-drift: 0"
    assert out[-1] == "opened-text-below-4.5: 0"
    pending = next(o for o in census["opened"] if o["name"] == "zantara-pending" and o["walk"] == "mobile/system-dark")
    assert pending["state"] == "ok"
    drop = next(o for o in census["opened"] if o["name"] == "search-dropdown" and o["walk"] == "desktop/light")
    below = [(round(census_mod.contrast(census_mod.text_colour(r), r["a"]), 2), r["fg"], r["text"])
             for r in drop["runs"] if r["state"] == "ok" and r["fg"]
             and census_mod.contrast(census_mod.text_colour(r), r["a"]) < 4.5]
    assert below == []


def test_the_origin_main_page_grounds_name_the_consultation_card_over_its_gradient(census):
    """G25: on W2''' KBLIConsultationCTA sits on solid elevated ground (page-grounds-off-contract: 0); a capture
    carrying the pre-W2 inline gradient is named over-image (gradient)."""
    assert census_mod.page_verdict(census)[-1] == "page-grounds-off-contract: 0"
    guilty = copy.deepcopy(census)
    guilty["captures"][0]["page_off"] = {
        "g25": "  ground #1E1B1A over-image (gradient) under 'Need custom KBLI guidance?' at "
               "section.rp-dark-island.mt-12>div.rounded-2xl, on /kbli/55203 desktop/light"}
    verdict_lines = census_mod.page_verdict(guilty)
    assert verdict_lines[-1] == "page-grounds-off-contract: 1"
    assert "over-image (gradient)" in verdict_lines[0] and "section.rp-dark-island.mt-12>div.rounded-2xl" in verdict_lines[0]


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


# Section 8.3, Zero's Q11 (SPEC-W0d section 4): the five proofs of the re-cut explorer logo.
def png_bytes(rows: list[list[tuple]]) -> bytes:
    """An 8-bit PNG, RGB or RGBA by the pixel tuples' length, every row unfiltered."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    head = struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, 6 if len(rows[0][0]) == 4 else 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in rows)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def roundel(x: int, y: int) -> str:
    """A 64x64 logo: a red 3 inside a black disc inside a white ring, on a black field."""
    r = ((x - 32) ** 2 + (y - 32) ** 2) ** 0.5
    return "three" if 28 <= x < 36 and 26 <= y < 38 else "disc" if r < 20 else "ring" if r < 26 else "field"


RGB = {"three": (164, 32, 32), "disc": (1, 0, 0), "ring": (250, 250, 250), "field": (1, 1, 0)}
LOGO_RGB = png_bytes([[RGB[roundel(x, y)] for x in range(64)] for y in range(64)])
SRC = f'<img src="{census_mod.LOGO_ALPHA_SRC}" alt="Zantara Logo" />'
ON_PAPER = {"src": census_mod.LOGO_ALPHA_SRC, "corners": ["#F7F4EE"] * 4}


def logo_cut(alpha=lambda part, x, y: 0 if part == "field" else 255, rgb=lambda part, x, y: RGB[part]) -> bytes:
    return png_bytes([[(*rgb(roundel(x, y), x, y), alpha(roundel(x, y), x, y)) for x in range(64)] for y in range(64)])


def test_innocence_the_logo_cut_on_its_black_field_passes_the_five_proofs():
    assert census_mod.logo_proof(LOGO_RGB, logo_cut(), SRC, ON_PAPER) == []


@pytest.mark.parametrize("new, page_text, record, failed", [
    (LOGO_RGB, SRC, ON_PAPER, "IHDR: 64x64 colour type 2, not 64x64 RGBA (6)"),
    (logo_cut(alpha=lambda part, x, y: 255 if (x, y) == (63, 0) else 0 if part == "field" else 255), SRC, ON_PAPER,
     "corners: alpha [0, 255, 0, 0], not 0"),
    (logo_cut(alpha=lambda part, x, y: 0 if (x, y) in ((0, 0), (63, 0), (0, 63), (63, 63)) else 255), SRC, ON_PAPER,
     "corners: "),
    (logo_cut(alpha=lambda part, x, y: 0 if part in ("field", "disc") else 255), SRC, ON_PAPER, "roundel: "),
    (logo_cut(rgb=lambda part, x, y: (255, 255, 255) if part == "three" else RGB[part]), SRC, ON_PAPER, "roundel: 96 "),
    (logo_cut(), '<img src="/images/logo-zantara.png" />', ON_PAPER, "img: the explorer does not point at"),
    (logo_cut(), SRC, {"src": "/images/logo-zantara.png", "corners": ["#010100"] * 4}, "render: "),
    (logo_cut(), SRC, {**ON_PAPER, "corners": ["#F7F4EE"] * 3 + ["#080A0E"]}, "render: "),
    (logo_cut(), SRC, None, "render: "),
], ids=["the RGB original", "a corner left opaque", "corners cut only field left opaque", "the disc cut too",
        "the 3 recoloured", "the img not repointed", "the old logo rendered", "a corner off paper", "no render read"])
def test_guilt_each_logo_proof_names_its_failure(new, page_text, record, failed):
    bad = census_mod.logo_proof(LOGO_RGB, new, page_text, record)
    assert len(bad) == 1 and bad[0].startswith(failed), bad


def test_the_explorer_logo_today_is_rgb_and_its_mask_keeps_the_disc():
    w, h, ctype, rows = census_mod.png_rows(census_mod.LOGO.read_bytes())
    field = census_mod.black_field(w, h, rows)
    assert (w, h, ctype) == (1024, 1024, 2)
    assert field[0] and not field[512 * w + 512]  # the corner is field, the black disc at the centre is not
    assert census_mod.logo_proof(census_mod.LOGO.read_bytes(), census_mod.LOGO.read_bytes(),
                                 census_mod.LOGO_PAGE.read_text(), None)[0].startswith("IHDR: 1024x1024 colour type 2")


@pytest.mark.skipif(not census_mod.LOGO_ALPHA.exists(), reason="W2''' ships the transparent logo (section 8.3)")
def test_the_transparent_logo_keeps_the_roundel_and_sits_on_paper():
    record = census_mod.load(FIXTURE).get("logo")
    assert census_mod.logo_proof(census_mod.LOGO.read_bytes(), census_mod.LOGO_ALPHA.read_bytes(),
                                 census_mod.LOGO_PAGE.read_text(), record) == []


@needs_browser
@pytest.mark.parametrize("png, corners", [(logo_cut(), "#F7F4EE"), (LOGO_RGB, "#010100")], ids=["cut", "original"])
def test_e2e_the_logo_corners_are_read_from_the_render(tmp_path, png, corners):
    from playwright.sync_api import sync_playwright
    (tmp_path / "logo-zantara-transparent.png").write_bytes(png)
    server = serve(tmp_path, '<body style="margin:0;background:#F7F4EE"><div style="width:40px;height:40px;'
                             'margin:32px"><img src="logo-zantara-transparent.png" style="width:100%;height:100%">'
                             '</div></body>')
    m = census_mod._load_measure()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=m.CHROME)
            page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
            page.goto(f"http://127.0.0.1:{server.server_port}/o.html", wait_until="load")
            record = census_mod.logo_corners(page)
            browser.close()
    finally:
        server.shutdown()
    assert record == {"src": "logo-zantara-transparent.png", "corners": [corners] * 4}



# Section 9 (W0d-3a): the census in parts. The fixture is one full run; cut by part, it is what the four
# `wrapper-census-part` jobs dump for the aggregate.
UNITS = census_mod.scenarios(*census_mod.measure_literals())
WORKFLOW = (census_mod.ROOT / ".github/workflows/r19-wrapper-census-tests.yml").read_text()
EXIT_BLOCK = re.search(r"### 8\.8 .*?```\n(.*?)```", CONTRACT, re.S).group(1)
EXIT_LINES = [ln for ln in EXIT_BLOCK.splitlines() if ln.strip()]


def cut(census: dict) -> dict[str, dict]:
    """The full census as each part dumps it: an entry goes with the part that runs its scenario, the reads,
    colours and state classes with `rest`, and a part that walks no surface dumps no opened walk."""
    part_of = collections.defaultdict(lambda: "kbli", {f"{k} {n}": part for part, k, n, _ in UNITS})  # off-list: kbli
    out = {}
    for p in census_mod.PARTS:
        sub = {**{k: census[k] for k in ("schema", "pages", "states")}, "parts": [p],
               **{k: census[k] if p == "rest" else {} for k in ("reads", "colors", "state_obs")}}
        for k, see in census_mod.SCENARIO_OF.items():
            if k in census and (p != "rest" or k not in ("opened", "shared", "shared_failed")):
                sub[k] = [x for x in census[k] if part_of[see(x)] == p]
        out[p] = sub
    return out


def parts_file(tmp_path, census: dict, order=("shared", "explorer", "rest", "kbli")) -> Path:
    parts = cut(census)
    for p in order:
        census_mod.dump(parts[p], tmp_path / f"census-{p}.jsonl")
    path = tmp_path / "census.jsonl"
    path.write_text("".join((tmp_path / f"census-{p}.jsonl").read_text() for p in order))
    return path


def replay(capsys, path: Path) -> str:
    assert census_mod.main(["--replay", str(path), "--diff-base", "HEAD"]) == 0
    return capsys.readouterr().out


def test_the_parts_cut_from_one_list_cover_it_once():
    keys = [f"{kind} {name}" for _, kind, name, _ in UNITS]
    by_part = {p: {f"{k} {n}" for q, k, n, _ in UNITS if q == p} for p in census_mod.PARTS}
    assert len(keys) == len(set(keys)) == 54 + 18 + 51 + 24
    assert {q for q, *_ in UNITS} == set(census_mod.PARTS) and all(by_part.values())
    assert set().union(*by_part.values()) == set(keys)
    assert all(not (by_part[a] & by_part[b]) for a in by_part for b in by_part if a < b)
    assert {p: len(v) for p, v in by_part.items()} == {"rest": 72, "kbli": 34, "explorer": 17, "shared": 24}


def test_each_part_waits_for_every_route_it_loads():
    """On M5 the `shared` part's first walk met a server not yet listening (net::ERR_CONNECTION_REFUSED at /v2):
    a part waits for the routes its scenarios load, not for the ones of PAGES it happens to hold."""
    shared = {sc[1] for sc in census_mod.SHARED}
    assert all(census_mod.routes_of([u for u in UNITS if u[0] == p]) for p in census_mod.PARTS)
    assert set(census_mod.routes_of([u for u in UNITS if u[0] == "shared"])) == shared
    assert census_mod.routes_of(UNITS)[:len(census_mod.PAGES)] == census_mod.PAGES and set(census_mod.routes_of(UNITS)) == {
        *census_mod.PAGES, *shared}


def test_the_workflow_runs_every_part_and_judges_them_after_any_failure():
    parts = json.dumps(list(census_mod.PARTS), separators=(",", ":"))
    assert f"part: ${{{{ fromJSON(inputs.parts || '{parts}') }}}}" in WORKFLOW
    assert f"default: '{parts}'" in WORKFLOW
    job = WORKFLOW[WORKFLOW.index("\n  wrapper-census-states:\n"):]
    assert "    needs: wrapper-census-part\n" in job and "    if: ${{ !cancelled() }}\n" in job
    assert "--replay \"$RUNNER_TEMP/census.jsonl\"" in job
    # A re-run part replaces its own dump under the same name (the #8237 gate, note 3).
    upload = WORKFLOW[WORKFLOW.index("actions/upload-artifact@"):WORKFLOW.index("retention-days:")]
    assert "name: census-part-${{ matrix.part }}\n" in upload and "overwrite: true\n" in upload


def test_the_parts_judged_together_print_the_full_runs_verdict_byte_for_byte(tmp_path, capsys):
    """The W0d-3a proof, offline: one full run's dump (the fixture), cut into the four parts' dumps and
    concatenated in another order, replays to the very text of the full dump. The same dump from before the parts
    replays to that text without its first line."""
    whole = replay(capsys, FIXTURE)
    legacy = census_mod.load(FIXTURE)
    assert legacy.pop("parts") == ["full"] and legacy.pop("seconds")
    census_mod.dump(legacy, tmp_path / "legacy.jsonl")
    assert whole == "scenarios-off-manifest: 0\n" + replay(capsys, tmp_path / "legacy.jsonl")
    assert all(want in whole.splitlines() for want in EXIT_LINES)
    for order in (census_mod.PARTS, ("shared", "explorer", "rest", "kbli")):
        assert replay(capsys, parts_file(tmp_path, census_mod.load(FIXTURE), order)) == whole


def test_a_live_census_and_its_dump_print_the_same_colour_lines(tmp_path):
    """A live run keeps its colours in the order it met them, its dump sorts them by hex: colours tied on their
    count print by hex either way, so the single job's live verdict is the aggregate's text."""
    census = census_mod.load(FIXTURE)
    census["colors"]["#010203"] = {"hex": "#010203", "prop": "color", "count": 7, "selector": "a", "page": "/kbli", "state": "desktop/light"}
    census["colors"]["#040506"] = {"hex": "#040506", "prop": "color", "count": 7, "selector": "b", "page": "/kbli", "state": "desktop/light"}
    counts = [c["count"] for c in census["colors"].values()]
    assert len(counts) > len(set(counts))
    census["colors"] = dict(reversed(census["colors"].items()))
    census_mod.dump(census, tmp_path / "c.jsonl")
    assert verdict(census) == verdict(census_mod.load(tmp_path / "c.jsonl"))


DROPS = {"capture": ("captures", lambda c: (c["page"], c["state"]) == ("/kbli-explorer", "mobile/forced-dark"),
                     "capture /kbli-explorer mobile/forced-dark", "read-but-undefined: 0 (INCOMPLETE: 1 captures "
                     "failed, not a verdict)"),
         "walk": ("walks", lambda w: w == "/kbli/56101 mobile/system-dark", "walk /kbli/56101 mobile/system-dark",
                  "state-colors-off-contract: INCOMPLETE (1 walks failed, 17 ok, not a verdict)"),
         "opened": ("opened", lambda o: (o["name"], o["walk"]) == ("explorer-compare", "desktop/light"),
                    "opened explorer-compare desktop/light", "opened-surfaces: 50 ok, 1 failed"),
         "shared": ("shared", lambda s: (s["name"], s["walk"]) == ("Footer R19 blog /news", "mobile/light"),
                    "shared Footer R19 blog /news mobile/light",
                    "shared-component-drift: INCOMPLETE (1 shared walks failed, not a verdict)")}


@pytest.mark.parametrize("kind", DROPS)
def test_guilt_a_scenario_no_part_ran_is_missing_and_its_counts_never_read_zero(tmp_path, capsys, kind):
    where, hit, key, line = DROPS[kind]
    census = census_mod.load(FIXTURE)
    census[where] = [x for x in census[where] if not hit(x)]
    out = replay(capsys, parts_file(tmp_path, census)).splitlines()
    assert out[:2] == ["scenarios-off-manifest: 1 (INCOMPLETE: 1 scenarios not received, not a verdict)",
                       f"  missing: {key}"]
    assert line in out


# The counts each part feeds: without the part, every one of them reads INCOMPLETE (the #8237 gate, note 1).
FED = {"rest": ["reads:", "defined-above-wrapper:", "read-but-undefined:", "colors-outside-direction-a:",
                "state-rows-unseen:", "state-colors-off-contract:", "page-grounds-off-contract:",
                "ground-resolver-disagree:"],
       "kbli": ["opened-outside-wrapper:", "opened-grounds-off-contract:", "ground-resolver-disagree:",
                "opened-text-below-4.5:"],
       "shared": ["shared-component-drift:"]}
FED["explorer"] = FED["kbli"]


@pytest.mark.parametrize("part", census_mod.PARTS)
def test_guilt_a_missing_part_is_every_one_of_its_scenarios_missing(tmp_path, capsys, part):
    """And every count the part feeds reads INCOMPLETE: none prints a bare number."""
    order = [p for p in census_mod.PARTS if p != part]
    out = replay(capsys, parts_file(tmp_path, census_mod.load(FIXTURE), order)).splitlines()
    n = sum(q == part for q, *_ in UNITS)
    assert out[0] == f"scenarios-off-manifest: {n} (INCOMPLETE: {n} scenarios not received, not a verdict)"
    assert sum(ln.startswith("  missing: ") for ln in out) == n
    assert not set(EXIT_LINES) <= set(out)
    assert [f for f in FED[part] if "INCOMPLETE" not in lines_of(out, f)] == []


def test_guilt_no_dump_at_all_is_the_whole_list_missing(tmp_path, capsys):
    (tmp_path / "census.jsonl").write_text("")
    out = replay(capsys, tmp_path / "census.jsonl").splitlines()
    assert out[0] == "scenarios-off-manifest: 147 (INCOMPLETE: 147 scenarios not received, not a verdict)"
    assert "captures: 0 ok, 54 failed" in out and "opened-surfaces: 0 ok, 51 failed" in out


def test_guilt_a_part_twice_and_a_scenario_off_the_list_are_named(tmp_path, capsys):
    path = parts_file(tmp_path, census_mod.load(FIXTURE))
    path.write_text(path.read_text() + (tmp_path / "census-explorer.jsonl").read_text())
    out = replay(capsys, path).splitlines()
    assert out[0] == "scenarios-off-manifest: 17" and "  twice: opened explorer-compare desktop/light" in out
    census = census_mod.load(FIXTURE)
    census["opened"][0]["name"] = "ghost-surface"
    out = replay(capsys, parts_file(tmp_path, census)).splitlines()
    assert out[:3] == ["scenarios-off-manifest: 2 (INCOMPLETE: 1 scenarios not received, not a verdict)",
                       "  missing: opened search-dropdown mobile/light",
                       "  unexpected: opened ghost-surface mobile/light"]


def test_a_token_two_parts_read_folds_as_one_run_folds_it(tmp_path):
    """Parts fold in the order of PARTS, whatever the order of the file: the first part's example stands unless a
    later part reads the token from worse (RANK), and the counts add up."""
    head = {"schema": 1, "pages": ["/kbli"], "states": ["desktop/light"], "captures": [], "failed": [],
            "walks": [], "walk_failed": []}
    def read(token, defined, selector, count):
        return {"read": f"var {token}", "kind": "var", "token": token, "defined": defined, "selector": selector,
                "count": count, "page": "/kbli", "state": "desktop/light"}
    docs = [({**head, "parts": ["rest"]}, [read("--tie", "above", "a", 2), read("--worse", "wrapper", "a", 1)]),
            ({**head, "parts": ["kbli"]}, [read("--tie", "above", "b", 3), read("--worse", "nowhere", "b", 1)])]
    (tmp_path / "c.jsonl").write_text("".join(json.dumps(h) + "\n" + "".join(json.dumps(r) + "\n" for r in rows)
                                              for h, rows in reversed(docs)))
    census = census_mod.load(tmp_path / "c.jsonl")
    assert census["parts"] == ["rest", "kbli"]
    assert {t: tuple(census["reads"][f"var {t}"][k] for k in ("count", "defined", "selector"))
            for t in ("--tie", "--worse")} == {"--tie": (5, "above", "a"), "--worse": (2, "nowhere", "b")}


def test_innocence_a_failed_scenario_is_received_not_missing(tmp_path, capsys):
    census = census_mod.load(FIXTURE)
    gone = census["captures"].pop(7)
    census["failed"].append(f"{gone['page']} {gone['state']}: opener: Timeout 30000ms: waiting for x: y")
    out = replay(capsys, parts_file(tmp_path, census)).splitlines()
    assert out[:2] == ["scenarios-off-manifest: 0", "captures: 53 ok, 1 failed"]


def test_the_sector_opener_moves_the_pointer_off_the_card_it_clicked():
    """The #8202 gate: the drawer is read with the pointer away, so the clicked card's hover is not its state."""
    from unittest import mock
    page = mock.MagicMock()
    census_mod._open_sector(page)
    names = [c[0] for c in page.method_calls]
    assert names[-1] == "mouse.move" and page.mouse.move.call_args == mock.call(0, 0), names
    assert names.index("wait_for_selector") < names.index("mouse.move")


def exit_step() -> str:
    """The aggregate's assert step, as CI runs it."""
    body = re.search(r"\n      - name: Every scenario received[^\n]*\n(?:        env:\n(?:          .*\n)+)?"
                     r"        run: \|\n((?:          .*\n|\n)+)", WORKFLOW).group(1)
    return "\n".join(ln[10:] for ln in body.splitlines())


def run_exit_step(tmp_path, log: str, result: str = "success") -> subprocess.CompletedProcess:
    (tmp_path / "census.txt").write_text(log)
    return subprocess.run(["bash", "-c", exit_step()], capture_output=True, text=True,
                          env={"RUNNER_TEMP": str(tmp_path), "PARTS_RESULT": result, "PATH": "/usr/bin:/bin"})


def test_innocence_the_exit_step_passes_the_parts_judged_together(tmp_path, capsys):
    r = run_exit_step(tmp_path, replay(capsys, parts_file(tmp_path, census_mod.load(FIXTURE))))
    assert r.returncode == 0, r.stdout
    assert [ln for ln in r.stdout.splitlines() if ln.startswith("ok: ")] == [f"ok: {w}" for w in EXIT_LINES]


def test_innocence_the_exit_step_passes_the_exit_block(tmp_path):
    assert EXIT_LINES == [ln for ln in EXIT_BLOCK.splitlines() if ln in EXIT_LINES]
    r = run_exit_step(tmp_path, "  a walk line\n" + EXIT_BLOCK)
    assert r.returncode == 0, r.stdout
    assert [ln for ln in r.stdout.splitlines() if ln.startswith("ok: ")] == [f"ok: {w}" for w in EXIT_LINES]


@pytest.mark.parametrize("want", EXIT_LINES)
def test_guilt_the_exit_step_fails_a_log_carrying_1(tmp_path, want):
    bad = re.sub(r"\b0(?= failed$)|(?<=: )0$", "1", want)
    r = run_exit_step(tmp_path, EXIT_BLOCK.replace(want + "\n", bad + "\n"))
    assert r.returncode == 1 and f"::error::the census did not print '{want}'" in r.stdout, r.stdout


def test_guilt_the_exit_step_fails_an_incomplete_log(tmp_path):
    log = (EXIT_BLOCK.replace("opened-surfaces: 51 ok, 0 failed", "opened-surfaces: 50 ok, 1 failed")
           .replace("captures: 54 ok, 0 failed", "captures: 53 ok, 1 failed")
           .replace("shared-component-drift: 0", "shared-component-drift: 0 (INCOMPLETE: 1 walk failed, not a verdict)"))
    r = run_exit_step(tmp_path, log)
    assert r.returncode == 1 and r.stdout.count("::error::") == 3, r.stdout


def test_guilt_the_exit_step_fails_a_missing_scenario_and_a_red_part(tmp_path, capsys):
    census = census_mod.load(FIXTURE)
    census["shared"] = census["shared"][1:]
    r = run_exit_step(tmp_path, replay(capsys, parts_file(tmp_path, census)))
    assert r.returncode == 1 and r.stdout.count("::error::") == 2, r.stdout
    assert "  missing: shared MobileNav non-R19 /v2 mobile/light" in r.stdout
    r = run_exit_step(tmp_path, replay(capsys, parts_file(tmp_path, census_mod.load(FIXTURE))), "failure")
    assert r.returncode == 1 and "::error::wrapper-census-part concluded 'failure'" in r.stdout, r.stdout


def test_every_census_context_asks_for_reduced_motion_from_one_place():
    """The #8488 gate's B1: a context opened anywhere else in the module could drop reduced motion for one pass
    (the capture pass or the state walk) with no browser row noticing."""
    src = census_mod.__file__
    text = open(src).read()
    assert text.count("browser.new_context(") == 1 and text.count("= new_context(browser,") == 3
    body = text.split("def new_context(", 1)[1].split("\n\n\n", 1)[0]
    assert 'reduced_motion="reduce"' in body


def test_the_drop_shadow_statement_is_in_the_contract_and_the_code_reads_only_blur():
    """The #8488 gate's B2: 8.4 says a `drop-shadow()` in `filter` reaches nothing, and reachOf reads blur() only."""
    flat = " ".join(CONTRACT.split())
    assert "A `drop-shadow()` in `filter` reaches nothing" in flat
    reach = census_mod.RESOLVE_JS.split("const reachOf", 1)[1].split("return side;", 1)[0]
    assert "blur\\(" in reach and "drop-shadow" not in reach


def test_the_bring_fallback_keeps_the_occluder_and_why_it_is_exempt():
    """The #8249 gate's binding 4 and ii-11/ii-12: decode(), bring() and pointB() prefer a non-exempt occluder."""
    decode = census_mod.RESOLVE_JS.split("async decode(", 1)[1].split("bring() {", 1)[0]
    fallback = census_mod.RESOLVE_JS.split("bring() {", 1)[1].split("return true;", 1)[0]
    pointb = census_mod.RESOLVE_JS.split("const pointB =", 1)[1].split("const ls =", 1)[0]
    assert "const occ = bs.find((b) => b.occluded && !b.exempt) || bs.find((b) => b.occluded);" in decode
    assert "(r.trial.bs.find((b) => b.occluded && !b.exempt) || r.trial.bs.find((b) => b.occluded))" in fallback
    assert "if (occ) { r.occludedBy = occ.occluded; r.exempt = occ.exempt; }" in fallback
    assert "if (hits.length) return hits.find((h) => !h.exempt) || hits[0];" in pointb


def test_guilt_a_capture_not_read_through_leaves_ground_resolver_disagree_incomplete(census):
    """The #8249 gate's binding 2: it also counts the disagreements read at rest, as G does."""
    short = copy.deepcopy(census)
    short["captures"][0]["page_incomplete"] = True
    out = verdict_of(short, PIN, [])
    assert "INCOMPLETE" in lines_of(out, "ground-resolver-disagree:")
    assert "INCOMPLETE" not in lines_of(verdict_of(census, PIN, []), "ground-resolver-disagree:")


def test_the_full_dispatch_has_headroom_and_the_exit_step_lists_the_declared_line():
    """The #8488 gate's B4 and B5: `full` ran 39m06s against a 40-minute timeout; a declared walk is printed."""
    assert "timeout-minutes: ${{ matrix.part == 'full' && 75 || 40 }}" in WORKFLOW
    assert "|declared-|opened-|" in WORKFLOW


MENU = '<div id="d" hidden style="position:absolute;left:0;top:0;width:100%;height:64px;background:#FFFCF7;z-index:20">' \
       + p(INK, "Menu") + "</div>"


@needs_browser
@pytest.mark.parametrize("body, selectors, clause, absent", [
    (surface("background:#FFFCF7;padding:16px", p(INK) + p(INK, "Villa")) + MENU, ["#s", "#d"],
     "of them under another opened surface", "behind the walk's own scrim"),
    (surface("background:#FFFCF7;padding:16px", p(INK) + p(INK, "Villa")) + SCRIM.format("rgba(29,44,59,.45)"), ["#s"],
     "of them behind the walk's own scrim", "under another opened surface"),
], ids=["a surface over a surface", "the walk's own scrim"])
def test_e2e_the_walk_line_names_the_cause_of_an_exempt_occlusion(tmp_path, monkeypatch, body, selectors, clause, absent):
    """The #8560 gate's (b): an occluded run is counted under the cause that exempts it, never under the other."""
    opener = "document.getElementById('s').hidden = false; const d = document.getElementById('d'); if (d) d.hidden = false"
    out = verdict_of(open_case(tmp_path, monkeypatch, body, "", opener, selectors))
    walks = [ln for ln in out if ln.startswith("  case ")]
    assert walks and all(clause in ln and absent not in ln for ln in walks), walks
