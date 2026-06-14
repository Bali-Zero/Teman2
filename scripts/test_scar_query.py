#!/usr/bin/env python3
"""
test_scar_query.py — trap-table for the scar_query lexical pipeline.

Two duties:
 1. Behavioral unit tests on a synthetic corpus (deterministic, no real files).
 2. A live smoke that EVERY `scar query "<theme>"` promised by the bridge
    (cicatrix-superscar.md) actually returns ≥1 hit against the real corpus —
    so the bridge never points at a dead query (anti #2 Esiste≠Armato).

Run: python scripts/test_scar_query.py   (exit 0 = all green)
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("scar_query", HERE / "scar_query.py")
sq = importlib.util.module_from_spec(_spec)
sys.modules["scar_query"] = sq  # register so @dataclass can resolve the module
_spec.loader.exec_module(sq)  # type: ignore

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)


# --- 1. synthetic-corpus unit tests -----------------------------------------
SYNTH_SCARS = """# cicatrix-scars.md

### ⚠️ W99: villa import quota guard over-match (2026-01-01)

A scar about a guard whose bare-substring trigger matched inside quota.
The fix is word-boundary matching.

### 🚨 W98: secret in cleartext, world-readable .env (2026-01-02)

Postgres password leaked via cat over ssh into the transcript.
"""

SYNTH_ARCHIVE = """# cicatrix-scars-archive.md

### ✅ W50: HOME-fork drift, runtime runs a copy in ~/scripts (2026-01-03)

The deploy worktree diverged from the repo source of truth.
"""

SYNTH_BRIDGE = """# cicatrix-superscar.md

## #4 — Secret in the clear (world-readable credentials)

MALATTIA: secrets exposed on the filesystem.
**→ dettaglio:** `scar query "secret cleartext"`

## #1 — HOME-fork drift

body.
"""


def with_synth_corpus(fn):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "cicatrix-scars.md").write_text(SYNTH_SCARS, encoding="utf-8")
        (d / "cicatrix-scars-archive.md").write_text(SYNTH_ARCHIVE, encoding="utf-8")
        (d / "cicatrix-superscar.md").write_text(SYNTH_BRIDGE, encoding="utf-8")
        fn(d)


def t_parse_counts(d: Path) -> None:
    scars = sq.parse_corpus(d)
    check(len(scars) == 3, f"expected 3 synth scars, got {len(scars)}")
    titles = {s.title.split(":")[0].split(" ", 1)[-1] for s in scars}
    check(any("W99" in s.title for s in scars), "W99 not parsed")
    wmap = {w: s for s in scars for w in s.w_numbers}
    check("W50" in wmap and wmap["W50"].source == "cicatrix-scars-archive.md",
          "W50 not attributed to archive file")


def t_word_boundary_no_overmatch(d: Path) -> None:
    """anti #3: query 'ota' must NOT match 'quota' (the W99 scar)."""
    scars = sq.parse_corpus(d)
    hits = sq.search(scars, ["ota"], require_all=True)
    check(len(hits) == 0, f"'ota' over-matched 'quota' — guard-over-match regression ({len(hits)} hits)")
    # but the real word 'quota' DOES match
    hits2 = sq.search(scars, ["quota"], require_all=True)
    check(len(hits2) == 1, f"'quota' should hit W99 exactly once, got {len(hits2)}")


def t_and_vs_or(d: Path) -> None:
    scars = sq.parse_corpus(d)
    # AND: 'secret' + 'cleartext' both in W98 -> 1 hit
    h_and = sq.search(scars, ["secret", "cleartext"], require_all=True)
    check(len(h_and) == 1 and "W98" in h_and[0][1].title,
          f"AND[secret,cleartext] should hit only W98, got {[s.title[:12] for _, s in h_and]}")
    # OR: 'quota' OR 'cleartext' -> W99 + W98
    h_or = sq.search(scars, ["quota", "cleartext"], require_all=False)
    check(len(h_or) == 2, f"OR[quota,cleartext] should hit 2, got {len(h_or)}")
    # AND with a term present in neither together -> 0
    h_none = sq.search(scars, ["quota", "cleartext"], require_all=True)
    check(len(h_none) == 0, f"AND[quota,cleartext] never co-occur, expected 0, got {len(h_none)}")


def t_title_weighs_more(d: Path) -> None:
    scars = sq.parse_corpus(d)
    # 'HOME-fork' appears in W50's title; 'drift' in title+body. Title hit must score high.
    hits = sq.search(scars, ["home-fork"], require_all=True)
    check(len(hits) == 1 and hits[0][0] >= 5, f"title hit should score >=5, got {hits}")


def t_case_insensitive(d: Path) -> None:
    scars = sq.parse_corpus(d)
    check(len(sq.search(scars, ["SECRET"], require_all=True)) == 1, "case-insensitive search broken")


def t_main_default_is_or(d: Path) -> None:
    """CLI-level: a multi-term query with no flag must be OR (theme search),
    so the bridge's multi-word `scar query "<theme>"` promises resolve."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    # 'quota' (W99) and 'cleartext' (W98) never co-occur → AND=0, OR=2.
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = sq.main(["--rules-dir", str(d), "--titles", "quota", "cleartext"])
    check(rc == 0, f"default multi-term should find hits (OR), got rc={rc}")
    check("W99" in buf.getvalue() and "W98" in buf.getvalue(),
          "default OR should surface both W99 and W98")
    # --all flips to AND → no co-occurrence → rc 1
    buf2, err2 = io.StringIO(), io.StringIO()
    with redirect_stdout(buf2), redirect_stderr(err2):
        rc2 = sq.main(["--rules-dir", str(d), "--all", "--titles", "quota", "cleartext"])
    check(rc2 == 1, f"--all (AND) on non-co-occurring terms should return rc=1, got {rc2}")


def t_quoted_phrase_tokenizes(d: Path) -> None:
    """The bridge cites `scar query "<theme>"` with quotes → the whole theme
    arrives as ONE argv element. main() must split it into terms, not search a
    literal multi-word phrase (which would always be 0 hits)."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        # single quoted arg with spaces, exactly as a shell passes "secret cleartext"
        rc = sq.main(["--rules-dir", str(d), "--titles", "secret cleartext"])
    check(rc == 0, f"quoted multi-word phrase should tokenize+hit, got rc={rc} / {err.getvalue().strip()}")
    check("W98" in buf.getvalue(), "tokenized 'secret cleartext' should surface W98")


def t_family_render(d: Path) -> None:
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = sq.render_family(d, "4")
    out = buf.getvalue()
    check(rc == 0 and "Secret in the clear" in out, "family #4 render failed")
    check("scar query" in out, "family render lost the bridge body")


# --- 2. live bridge-promise smoke -------------------------------------------
def t_bridge_promises_resolve() -> None:
    """Every `scar query "<theme>"` in the real bridge must return >=1 hit."""
    rules = None
    for cand in sq._candidate_rules_dirs():
        if (cand / "cicatrix-superscar.md").is_file():
            rules = cand
            break
    if rules is None:
        FAILURES.append("LIVE: cicatrix-superscar.md not found — cannot smoke bridge promises")
        return
    bridge = (rules / "cicatrix-superscar.md").read_text(encoding="utf-8")
    # real promises only — exclude the literal `<tema>` placeholder in the
    # maintenance note (a `<...>` token is documentation, not a live query).
    themes = [t for t in re.findall(r'scar query "([^"]+)"', bridge) if "<" not in t]
    check(len(themes) >= 10, f"expected >=10 bridge promises, found {len(themes)}")
    scars = sq.parse_corpus(rules)
    check(len(scars) >= 40, f"live corpus parsed only {len(scars)} scars (expected many)")
    import io
    from contextlib import redirect_stdout, redirect_stderr
    for theme in themes:
        # Drive it through main() the SAME way a shell does: the quoted theme is
        # ONE argv element. This catches the tokenize bug end-to-end, not just
        # the pre-split search() path.
        buf, err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            rc = sq.main(["--rules-dir", str(rules), "--titles", theme])
        check(rc == 0, f'LIVE: bridge promise `scar query "{theme}"` returns ZERO hits (rc={rc})')


def main() -> int:
    for fn in (
        t_parse_counts,
        t_word_boundary_no_overmatch,
        t_and_vs_or,
        t_title_weighs_more,
        t_case_insensitive,
        t_main_default_is_or,
        t_quoted_phrase_tokenizes,
        t_family_render,
    ):
        with_synth_corpus(fn)
    t_bridge_promises_resolve()

    if FAILURES:
        print(f"❌ {len(FAILURES)} failure(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("✅ scar_query: all trap-table + live-bridge-promise checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
