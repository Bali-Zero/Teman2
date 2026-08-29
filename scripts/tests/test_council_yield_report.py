"""Tests for scripts/council_yield_report.py (L03-PR-3, beyond-SOTA craft wave,
squad E — brief `/tmp/l3_pr3_brief_v2.md`, AMENDMENT 0-3).

Guilt AND innocence for every decision in the brief: family normalisation
(word-boundary, DECLARED PRECEDENCE), role bucketing (self/gate/review,
orthogonal to family), the unattributed bucket, the PLAUSIBLE third
disposition, the AMENDMENTS antidote with its false positive closed,
reproducibility, malformed-pack handling, and the fallback markdown path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import council_yield_report as cyr  # noqa: E402


# ---------------------------------------------------------------------------
# DECISION 1 — family normalisation: guilt (the four real multi-variant
# clusters from the brief collapse to one family each).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seat",
    [
        "kimi-k3",
        "kimi-code/k3",
        "kimi-code/k3 (cross-family refuter, round 1)",
    ],
)
def test_kimi_variants_collapse_to_one_family(seat: str) -> None:
    assert cyr.normalize_family(seat) == "kimi"


@pytest.mark.parametrize(
    "seat",
    [
        "gpt-5.6-sol xhigh",
        "codex-gpt-5.6-sol",
        "codex gpt-5.6-sol (round 1)",
        "codex-gpt-5.6-sol (cross-family refuter, PR",  # truncated, unbalanced paren
    ],
)
def test_gpt_codex_variants_collapse_to_one_family(seat: str) -> None:
    assert cyr.normalize_family(seat) == "codex-gpt-5.6"


@pytest.mark.parametrize(
    "seat",
    [
        "opus-5 orchestrator (team-lead)",
        "claude opus 5",
        "claude-opus-5",
    ],
)
def test_opus_variants_collapse_to_one_family(seat: str) -> None:
    assert cyr.normalize_family(seat) == "opus"


def test_agy_gemini_collapses_to_gemini_family() -> None:
    assert cyr.normalize_family("agy (Gemini 3.1 Pro, cross-family refuter)") == "gemini"


def test_codex_gpt_5_6_sol_is_exactly_one_seat_not_two() -> None:
    """Decision 1, verbatim: 'codex-gpt-5.6-sol is ONE seat, not codex+gpt.'
    Both aliases ('codex' and 'gpt-5.6') resolve to the identical family
    entry, so there is only ever one family in the output for this string,
    never two competing labels."""
    fam = cyr.normalize_family("codex-gpt-5.6-sol")
    assert fam == "codex-gpt-5.6"
    # Both tokens individually would also resolve to that SAME family entry —
    # proving they are aliases of one group, not two groups that happened to
    # agree on this string by coincidence.
    assert cyr.normalize_family("codex reviewer") == "codex-gpt-5.6"
    assert cyr.normalize_family("gpt-5.6 reviewer") == "codex-gpt-5.6"


# ---------------------------------------------------------------------------
# DECISION 1 — the over-match twin (innocence). AMENDMENT 1 note: the
# parser must not choke on the truncated/unbalanced-paren real string
# either (covered above); this block is the two explicit named traps.
# ---------------------------------------------------------------------------


def test_bare_gpt_mention_in_prose_does_not_bind() -> None:
    """There is deliberately no bare 'gpt' alias — only version-qualified
    'gpt-5.6'/'gpt5.6' — so a seat description that merely *mentions* GPT
    without that version number is correctly unattributed, not misfiled
    into the gpt-5.6 family."""
    seat = "session noting a stylistic resemblance to GPT-4's phrasing, no seat dispatched"
    assert cyr.normalize_family(seat) == cyr.UNATTRIBUTED


def test_session_inside_the_sessions_own_refuter_does_not_bind_self() -> None:
    """The brief's named over-match trap: 'session' must not bind inside
    'the session's own refuter'. Self-detection anchors on 'session' as the
    LEADING token (the seat announcing itself), not on 'session' appearing
    anywhere in the string — here it is the object of a possessive further
    into the sentence, describing an external refuter the session dispatched,
    which is a REVIEW role, not a self-check."""
    seat = "the session's own refuter"
    assert cyr.classify_role(seat) != cyr.ROLE_SELF
    assert cyr.classify_role(seat) == cyr.ROLE_REVIEW


def test_gate_word_alone_does_not_trigger_gate_role() -> None:
    """A seat literally named '... on-disk gate ...' must NOT land in the
    CI/harness `gate` bucket — that bucket is for deterministic tooling
    (harness/github actions/floor recompute/CI), never an LLM's own
    adjudication role that happens to use the word 'gate'."""
    seat = "opus-5 Gear-3 on-disk gate (fresh context, did not write the diff)"
    assert cyr.classify_role(seat) != cyr.ROLE_GATE
    assert cyr.classify_role(seat) == cyr.ROLE_REVIEW


# ---------------------------------------------------------------------------
# DECISION 1 — declared precedence order, pinned (not dict-iteration-order
# dependent). A synthetic string carrying two family tokens resolves to
# whichever family is EARLIER in FAMILY_PRECEDENCE, deterministically.
# ---------------------------------------------------------------------------


def test_precedence_order_is_deterministic_and_pinned() -> None:
    assert [name for name, _ in cyr.FAMILY_PRECEDENCE] == [
        "kimi",
        "codex-gpt-5.6",
        "gemini",
        "opus",
        "sonnet",
    ]
    # kimi precedes opus in the declared order -> wins when both are present.
    seat = "kimi refuter reviewing an opus-5 draft"
    assert cyr.normalize_family(seat) == "kimi"
    # gemini precedes opus -> wins.
    seat2 = "agy (gemini) cross-checking an opus-5 orchestrator's plan"
    assert cyr.normalize_family(seat2) == "gemini"


# ---------------------------------------------------------------------------
# DECISION 2 (AMENDMENT 2) — role bucketing, orthogonal to family: same
# family, different role, lands in different matrix cells.
# ---------------------------------------------------------------------------


def test_same_family_different_role_lands_in_different_buckets() -> None:
    review_seat = "sonnet-5 adversarial grader (fresh context)"
    self_seat = "sonnet-5 (self, bite-proof)"
    assert cyr.normalize_family(review_seat) == cyr.normalize_family(self_seat) == "sonnet"
    assert cyr.classify_role(review_seat) == cyr.ROLE_REVIEW
    assert cyr.classify_role(self_seat) == cyr.ROLE_SELF


def test_session_gate_on_its_own_diff_is_self_not_gate() -> None:
    """Real corpus seat: 'session (gate, on its own diff)'. Contains the
    bare word 'gate' but is self-review (a session grading its own diff,
    using the word loosely) — self is checked before gate, and 'gate' alone
    is not a gate-role trigger, so this correctly lands in self."""
    seat = "session (gate, on its own diff)"
    assert cyr.classify_role(seat) == cyr.ROLE_SELF


@pytest.mark.parametrize(
    "seat",
    [
        "Harness floor recompute (CI, deterministic)",
        "Harness floor recompute (GitHub CI, deterministic)",
        "organ-conformance gate (CI, deterministic)",
    ],
)
def test_gate_role_triggers(seat: str) -> None:
    assert cyr.classify_role(seat) == cyr.ROLE_GATE


# ---------------------------------------------------------------------------
# DECISION 3 — unattributed is a real bucket, never pooled into "other"
# with a fabricated per-seat yield.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seat",
    [
        "refuter-5187 (adversarial, fresh context)",
        "independent reviewer (fresh context)",
        "independent-gear3-grader",
        "finalize-defect-rootcause (subagent, REFUTED the conducting session)",
    ],
)
def test_named_unattributed_seats_report_as_unattributed(seat: str) -> None:
    assert cyr.normalize_family(seat) == cyr.UNATTRIBUTED


def test_unattributed_is_a_distinct_matrix_row_not_dropped(tmp_path: Path) -> None:
    _write_pack(
        tmp_path,
        "p1",
        dissent=[
            {"seat": "independent reviewer (fresh context)", "status": "CONFIRMED"},
        ],
    )
    report = cyr.run([], repo_root=tmp_path)
    rows = report["family_role_matrix"]
    matches = [r for r in rows if r["family"] == cyr.UNATTRIBUTED]
    assert matches, "unattributed finding must appear as its own row, not disappear"
    assert matches[0]["findings"] == 1


# ---------------------------------------------------------------------------
# DECISION 4 — PLAUSIBLE is a third disposition, absent from applied/rejected.
# ---------------------------------------------------------------------------


def test_plausible_is_its_own_bucket(tmp_path: Path) -> None:
    _write_pack(
        tmp_path,
        "p1",
        dissent=[
            {"seat": "kimi-k3", "status": "CONFIRMED"},
            {"seat": "kimi-k3", "status": "RETRACTED"},
            {"seat": "kimi-k3", "status": "PLAUSIBLE"},
        ],
    )
    report = cyr.run([], repo_root=tmp_path)
    row = next(r for r in report["family_role_matrix"] if r["family"] == "kimi")
    assert row["confirmed"] == 1
    assert row["retracted"] == 1
    assert row["plausible"] == 1
    # PLAUSIBLE must not have leaked into either applied(confirmed) or
    # rejected(retracted) — each is exactly 1, not 1.5 rounded or 2.
    assert row["confirmed"] != row["plausible"] + row["confirmed"]  # sanity: no double count
    assert report["totals"]["plausible"] == 1
    assert report["totals"]["confirmed"] == 1
    assert report["totals"]["retracted"] == 1


# ---------------------------------------------------------------------------
# LIVE-CORPUS ASSERTIONS — INVARIANTS, never frozen measurements.
#
# These three tests originally hard-coded the corpus as it stood on
# 2026-08-29: `packs_scanned == 54`, `findings == 267`, `len(seats) == 126`.
# Every one of those numbers is a MOVING measurement, not a property: the
# corpus grows by one pack on every merged PR in this repo, including the
# PR that ships this very file. Frozen that way, this test file becomes a
# repo-wide merge blocker — red on PRs that touched nothing, for a reason
# their author cannot act on. That is W129's shape (a test and the world it
# measures drifting apart) but decaying faster: on every merge rather than
# on a calendar, with four other squads shipping into the same corpus.
#
# What is worth pinning is what stays TRUE as the corpus grows: internal
# consistency, the spec's own >=5-pack acceptance floor, and the guarantee
# that nothing is silently dropped. A number that only this week's data
# satisfies proves the data, not the code.
# ---------------------------------------------------------------------------


def test_real_corpus_totals_are_internally_consistent() -> None:
    """The dispositions must ACCOUNT for every finding — no silent loss, no
    double count. True at 267 findings and true at 2670; a frozen `== 267`
    proved neither, it proved only that nobody had merged yet."""
    totals = cyr.run([])["totals"]
    assert totals["findings"] > 0
    assert (
        totals["confirmed"]
        + totals["retracted"]
        + totals["plausible"]
        + totals["unrecognized"]
        == totals["findings"]
    )
    assert all(
        totals[k] >= 0
        for k in ("findings", "confirmed", "retracted", "plausible", "unrecognized")
    )


def test_real_corpus_meets_the_specs_five_pack_acceptance_floor() -> None:
    """The lane spec's acceptance is "runs successfully on >=5 historical
    packs". THAT is the contract — over-satisfied today by an order of
    magnitude, and it stays satisfied as packs accumulate."""
    src = cyr.run([])["sources"]
    assert src["packs_scanned"] >= 5
    assert src["packs_with_dissent"] >= 5
    assert src["packs_with_dissent"] <= src["packs_scanned"]
    assert src["packs_with_council_yield_override"] <= src["packs_scanned"]


def test_real_corpus_never_silently_drops_a_pack() -> None:
    """Every scanned pack is either counted or NAMED as unparseable — the
    one guarantee a report owes its reader. Deliberately NOT asserted as
    `unparseable == []`: a malformed pack landed by another squad would then
    fail this PR's CI for a defect in someone else's file. What must never
    happen is a pack vanishing without a word, and that is what is pinned."""
    src = cyr.run([])["sources"]
    for entry in src["unparseable"]:
        assert entry["path"], entry
        assert entry["error"], entry


def test_real_corpus_every_raw_seat_normalises_without_raising() -> None:
    """The seat vocabulary grows with the corpus (126 distinct strings when
    measured, and one more the day anyone writes a new one), so its SIZE is
    not a property. What is: every string on disk resolves to a declared
    family or to `unattributed`, and none of them raises."""
    import glob

    import yaml

    seats: set[str] = set()
    for f in glob.glob(str(REPO / "evidence" / "**" / "pack.yml"), recursive=True):
        data = yaml.safe_load(open(f, encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for item in data.get("dissent") or []:
            if isinstance(item, dict) and isinstance(item.get("seat"), str):
                seats.add(item["seat"].strip())
    assert len(seats) >= 5
    for raw in seats:
        fam = cyr.normalize_family(raw)
        role = cyr.classify_role(raw)
        assert isinstance(fam, str) and fam
        assert role in (cyr.ROLE_REVIEW, cyr.ROLE_SELF, cyr.ROLE_GATE)


def test_override_counter_can_actually_count_not_only_report_zero(
    tmp_path: Path,
) -> None:
    """`packs_with_council_yield_override` was asserted only ever to be 0 —
    which a counter hard-wired to zero also satisfies. Mutation proved it:
    disabling the increment changed no test. Here it must COUNT."""
    _write_pack(tmp_path, "plain", dissent=[{"seat": "kimi-k3", "status": "CONFIRMED"}])
    _write_pack(
        tmp_path,
        "declared",
        council_yield={"seats": [{"seat": "agy", "status": "CONFIRMED"}]},
    )
    src = cyr.run([], repo_root=tmp_path)["sources"]
    assert src["packs_scanned"] == 2
    assert src["packs_with_council_yield_override"] == 1


# ---------------------------------------------------------------------------
# DECISION 5 — AMENDMENTS antidote, false positive closed. Exercised only
# via the `council_yield:` override (0 real instances, per AMENDMENT 3).
# ---------------------------------------------------------------------------


def test_zero_applied_with_findings_emits_amendments_candidate(tmp_path: Path) -> None:
    _write_pack(
        tmp_path,
        "p1",
        council_yield={
            "seats": [
                {"seat": "kimi-k3", "status": "RETRACTED"},
                {"seat": "codex-gpt-5.6-sol", "status": "RETRACTED"},
            ]
        },
    )
    report = cyr.run([], repo_root=tmp_path)
    cands = report["amendments_candidates"]
    assert len(cands) == 1
    assert cands[0]["findings"] == 2
    assert cands[0]["applied"] == 0


def test_zero_findings_does_not_emit_amendments_candidate(tmp_path: Path) -> None:
    """The false positive this decision closes: council_yield: {} — an
    empty/no-findings council has nothing to be silent about."""
    _write_pack(tmp_path, "p1", council_yield={"findings": 0, "applied": 0})
    report = cyr.run([], repo_root=tmp_path)
    assert report["amendments_candidates"] == []


def test_scalar_override_with_applied_does_not_emit_amendments_candidate(
    tmp_path: Path,
) -> None:
    _write_pack(tmp_path, "p1", council_yield={"findings": 3, "applied": 2, "rejected": 1})
    report = cyr.run([], repo_root=tmp_path)
    assert report["amendments_candidates"] == []
    row = next(r for r in report["family_role_matrix"] if r["family"] == cyr.UNATTRIBUTED)
    assert row["confirmed"] == 2
    assert row["retracted"] == 1


def test_council_yield_override_uses_derived_pack_totals_when_absent(
    tmp_path: Path,
) -> None:
    """A pack with NO council_yield: block derives its counts from dissent
    as normal — this is the 'absence means derive from dissent' contract."""
    _write_pack(
        tmp_path,
        "p1",
        dissent=[{"seat": "kimi-k3", "status": "CONFIRMED"}],
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["findings"] == 1
    assert report["sources"]["packs_with_council_yield_override"] == 0


def test_council_yield_override_replaces_not_adds_to_dissent(tmp_path: Path) -> None:
    """'OVERRIDES the derived counts for that pack' — a pack carrying BOTH
    dissent: and council_yield: reports only the override's counts, not the
    sum of both."""
    _write_pack(
        tmp_path,
        "p1",
        dissent=[
            {"seat": "kimi-k3", "status": "CONFIRMED"},
            {"seat": "kimi-k3", "status": "CONFIRMED"},
        ],
        council_yield={"seats": [{"seat": "kimi-k3", "status": "RETRACTED"}]},
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["findings"] == 1
    assert report["totals"]["retracted"] == 1
    assert report["totals"]["confirmed"] == 0


# ---------------------------------------------------------------------------
# DECISION 6 — reproducibility is the arming probe.
# ---------------------------------------------------------------------------


def test_reproducible_two_runs_identical_json_bytes() -> None:
    out1 = subprocess.run(
        [sys.executable, str(SCRIPTS / "council_yield_report.py"), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    out2 = subprocess.run(
        [sys.executable, str(SCRIPTS / "council_yield_report.py"), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out1.stdout == out2.stdout
    assert out1.returncode == 0
    assert out2.returncode == 0


def test_reproducible_two_runs_identical_human_bytes() -> None:
    out1 = subprocess.run(
        [sys.executable, str(SCRIPTS / "council_yield_report.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    out2 = subprocess.run(
        [sys.executable, str(SCRIPTS / "council_yield_report.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out1.stdout == out2.stdout


def test_json_output_is_valid_json_and_deterministically_sorted() -> None:
    out = subprocess.run(
        [sys.executable, str(SCRIPTS / "council_yield_report.py"), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(out.stdout)
    # Invariant, not a frozen count (see the LIVE-CORPUS block above).
    assert payload["totals"]["findings"] > 0
    # Serialised with sort_keys=True — re-dumping with the same settings
    # must reproduce byte-identical text (proves no insertion-order leak).
    assert json.dumps(payload, indent=2, sort_keys=True) == out.stdout.rstrip("\n")


# ---------------------------------------------------------------------------
# Malformed / unparseable packs — named, never raise, never silently skipped.
# ---------------------------------------------------------------------------


def test_malformed_yaml_pack_is_named_unparseable_and_does_not_raise(
    tmp_path: Path,
) -> None:
    pack_dir = tmp_path / "evidence" / "bad"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yml").write_text("dissent: [unterminated\n", encoding="utf-8")
    report = cyr.run([], repo_root=tmp_path)  # must not raise
    assert len(report["sources"]["unparseable"]) == 1
    assert "bad/pack.yml" in report["sources"]["unparseable"][0]["path"]


def test_non_mapping_top_level_yaml_is_named_unparseable(tmp_path: Path) -> None:
    pack_dir = tmp_path / "evidence" / "bad2"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    report = cyr.run([], repo_root=tmp_path)
    assert len(report["sources"]["unparseable"]) == 1


def test_dissent_not_a_list_is_named_unparseable(tmp_path: Path) -> None:
    pack_dir = tmp_path / "evidence" / "bad3"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yml").write_text("dissent: not-a-list\n", encoding="utf-8")
    report = cyr.run([], repo_root=tmp_path)
    assert len(report["sources"]["unparseable"]) == 1


def test_missing_dissent_key_is_a_valid_empty_pack_not_unparseable(
    tmp_path: Path,
) -> None:
    pack_dir = tmp_path / "evidence" / "clean"
    pack_dir.mkdir(parents=True)
    (pack_dir / "pack.yml").write_text("brief_ref: evidence/brief.yml\n", encoding="utf-8")
    report = cyr.run([], repo_root=tmp_path)
    assert report["sources"]["unparseable"] == []
    assert report["sources"]["packs_scanned"] == 1


def test_malformed_dissent_item_is_skipped_not_crashing(tmp_path: Path) -> None:
    _write_pack(
        tmp_path,
        "p1",
        dissent=["not-a-mapping", {"seat": "kimi-k3", "status": "CONFIRMED"}],
    )
    report = cyr.run([], repo_root=tmp_path)  # must not raise
    assert report["totals"]["findings"] == 1


# ---------------------------------------------------------------------------
# Runs over the real corpus without raising (CLI-level, both output modes).
# ---------------------------------------------------------------------------


def test_cli_runs_over_real_corpus_json_exit_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "council_yield_report.py"), "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["sources"]["packs_scanned"] >= 5


def test_cli_runs_over_real_corpus_human_exit_zero() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "council_yield_report.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "COUNCIL YIELD REPORT" in result.stdout
    assert "HONEST LIMIT" in result.stdout


def test_report_never_raises_even_with_yaml_module_absent(monkeypatch) -> None:
    monkeypatch.setattr(cyr, "yaml", None)
    result = cyr.load_pack(REPO / "evidence" / "pack.yml")
    assert result.ok is False
    assert "pyyaml" in (result.error or "")


# ---------------------------------------------------------------------------
# Fallback markdown path — explicit-file-only, honest about what it cannot
# parse. Uses synthetic docs (guilt: a real table shape; innocence: the
# prose-only shape the brief names for two of the three real 2026-08-28
# dossiers) rather than depending on those files' exact prose surviving
# future edits.
# ---------------------------------------------------------------------------

_TABLE_DOC = """# Some lane report

## Adversarial review

Two-seat pass.

| # | Seat | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | codex | CRITICAL | something broke | APPLIED (fixed) |
| 2 | kimi | MAJOR | something else | REJECTED as stated |
| 3 | both | MINOR | shared catch | APPLIED |

## Next section
more text
"""

_PROSE_ONLY_DOC = """# Another lane report

## Adversarial review

Joint panel, 2026-08-28: four seats, 57 raw findings, deduped to 27 joint
register rows — 23 applied, 3 partial, 1 with an embedded reject. No table
here, only prose.

## §Meta
more text
"""


def test_fallback_markdown_table_parses_guilt(tmp_path: Path) -> None:
    doc = tmp_path / "lane-report.md"
    doc.write_text(_TABLE_DOC, encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    report = cyr.run([str(doc)], repo_root=tmp_path)
    assert report["sources"]["fallback_docs_scanned"] == 1
    assert report["sources"]["unparseable"] == []
    assert report["totals"]["findings"] == 3
    assert report["totals"]["confirmed"] == 2  # two APPLIED
    assert report["totals"]["retracted"] == 1  # one REJECTED


def test_fallback_prose_only_doc_is_unparseable_not_fabricated(tmp_path: Path) -> None:
    """Real shape of two of the three 2026-08-28 dossiers the brief names:
    a narrative tally with no per-row Seat/Disposition table. This tool
    does not guess structured counts out of prose numbers — it names the
    doc as unparseable, honestly, per the CLI contract."""
    doc = tmp_path / "prose-report.md"
    doc.write_text(_PROSE_ONLY_DOC, encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    report = cyr.run([str(doc)], repo_root=tmp_path)
    assert report["sources"]["fallback_docs_scanned"] == 1
    assert len(report["sources"]["unparseable"]) == 1
    assert "prose-report.md" in report["sources"]["unparseable"][0]["path"]


def test_fallback_paths_are_additive_not_replacing_default_corpus(
    tmp_path: Path,
) -> None:
    _write_pack(tmp_path, "p1", dissent=[{"seat": "kimi-k3", "status": "CONFIRMED"}])
    doc = tmp_path / "lane-report.md"
    doc.write_text(_TABLE_DOC, encoding="utf-8")
    report = cyr.run([str(doc)], repo_root=tmp_path)
    # 1 from the default-discovered pack + 3 from the fallback doc = 4.
    assert report["totals"]["findings"] == 4
    assert report["sources"]["packs_scanned"] == 1
    assert report["sources"]["fallback_docs_scanned"] == 1


def test_the_three_real_named_dossiers_are_either_parsed_or_named_honestly() -> None:
    """Smoke-checks the actual three 2026-08-28 files the brief points at
    (note: they live under research/design/, not research/operations/ as
    the brief's prose says — the brief's own path was stale). Whichever
    shape each is in today, this tool must not raise and must not fabricate
    a count for a prose-only doc."""
    docs = [
        REPO / "research/design/2026-08-28-sponsor-i18n-design.md",
        REPO / "research/design/2026-08-28-delegate-flow-design.md",
        REPO / "research/design/2026-08-28-case-code-design.md",
    ]
    present = [d for d in docs if d.exists()]
    if not present:
        pytest.skip("2026-08-28 dossiers not present in this checkout")
    report = cyr.run([str(d) for d in present])  # must not raise
    assert report["sources"]["fallback_docs_scanned"] == len(present)


# ---------------------------------------------------------------------------
# resolve_extra_paths — directory recursion, .md routing, single-pack files.
# ---------------------------------------------------------------------------


def test_resolve_extra_paths_recurses_directories_for_pack_yml(tmp_path: Path) -> None:
    d = tmp_path / "somewhere"
    (d / "nested").mkdir(parents=True)
    (d / "nested" / "pack.yml").write_text("brief_ref: x\n", encoding="utf-8")
    packs, mds = cyr.resolve_extra_paths(["somewhere"], tmp_path)
    assert len(packs) == 1
    assert mds == []


def test_resolve_extra_paths_routes_md_to_fallback(tmp_path: Path) -> None:
    doc = tmp_path / "report.md"
    doc.write_text("# x\n", encoding="utf-8")
    packs, mds = cyr.resolve_extra_paths([str(doc)], tmp_path)
    assert packs == []
    assert len(mds) == 1


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _write_pack(
    tmp_path: Path,
    name: str,
    dissent: list | None = None,
    council_yield: dict | None = None,
) -> Path:
    import yaml

    pack_dir = tmp_path / "evidence" / name
    pack_dir.mkdir(parents=True, exist_ok=True)
    data: dict = {"brief_ref": "evidence/brief.yml"}
    if dissent is not None:
        data["dissent"] = dissent
    if council_yield is not None:
        data["council_yield"] = council_yield
    pack_path = pack_dir / "pack.yml"
    pack_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return pack_path


# ---------------------------------------------------------------------------
# ORCHESTRATOR GATE ADDITION — the AMENDMENTS antidote must not be inert.
#
# The function shipped from the implementer scoped itself to `used_override`
# only. Measured on the live corpus at that moment: `council_yield:` appeared
# in 0 of 54 packs, so the antidote could fire on a synthetic fixture and
# NEVER on real data — while FOUR real packs carried findings>0 with zero
# CONFIRMED, which is exactly the shape it exists to detect. That is
# superscar #2 (Esiste != Armato), and building the misfire-log antidote so
# that it is itself silent while the corpus misfires reproduces the defect
# inside its own cure.
#
# These are the proofs that the derived path is armed AND that the two
# sources stay distinguishable. Without them the behaviour is unpinned in
# BOTH directions: the extension broke no test, which is precisely why it
# needed tests of its own.
# ---------------------------------------------------------------------------


def test_derived_path_emits_amendments_candidate_without_any_block(
    tmp_path: Path,
) -> None:
    """GUILT, derived: a pack with NO `council_yield:` block whose `dissent:`
    raised findings and confirmed none is a candidate. Before the extension
    this returned [] — the antidote was reachable only through a schema
    nothing on disk had adopted."""
    _write_pack(
        tmp_path,
        "p1",
        dissent=[
            {"seat": "kimi-k3", "status": "RETRACTED"},
            {"seat": "codex-gpt-5.6-sol", "status": "PLAUSIBLE"},
        ],
    )
    cands = cyr.run([], repo_root=tmp_path)["amendments_candidates"]
    assert len(cands) == 1, cands
    assert cands[0]["source"] == "derived"
    assert cands[0]["findings"] == 2
    assert cands[0]["applied"] == 0


def test_derived_path_innocent_when_something_was_applied(tmp_path: Path) -> None:
    """INNOCENCE, derived: one CONFIRMED finding is enough — a council that
    changed the design is not silent, and convicting it would be a false
    positive on the only advisory line this report emits."""
    _write_pack(
        tmp_path,
        "p1",
        dissent=[
            {"seat": "kimi-k3", "status": "CONFIRMED"},
            {"seat": "kimi-k3", "status": "RETRACTED"},
        ],
    )
    assert cyr.run([], repo_root=tmp_path)["amendments_candidates"] == []


def test_derived_path_innocent_when_there_were_no_findings(tmp_path: Path) -> None:
    """INNOCENCE, derived: the false positive DECISION 5 closes, now proven
    on the derived path too — a council that raised nothing has nothing to be
    silent about. Convicting it would be the misfire-log defect in reverse."""
    _write_pack(tmp_path, "p1", dissent=[])
    assert cyr.run([], repo_root=tmp_path)["amendments_candidates"] == []


def test_declared_and_derived_candidates_are_labelled_apart(tmp_path: Path) -> None:
    """The `source` field is load-bearing, not decoration. A declared count is
    the author's own accounting; a derived count is this script reading
    `dissent:`. Pooling them under one label would be the same "one name, two
    meanings" drift this PR had to cure once already, in the pack key itself."""
    _write_pack(
        tmp_path,
        "declared_pack",
        council_yield={"seats": [{"seat": "kimi-k3", "status": "RETRACTED"}]},
    )
    _write_pack(
        tmp_path,
        "derived_pack",
        dissent=[{"seat": "kimi-k3", "status": "RETRACTED"}],
    )
    cands = cyr.run([], repo_root=tmp_path)["amendments_candidates"]
    by_source = {c["source"]: c["pack"] for c in cands}
    assert set(by_source) == {"declared", "derived"}, cands
    assert "declared_pack" in by_source["declared"]
    assert "derived_pack" in by_source["derived"]


def test_declared_scalar_block_is_read_not_silently_derived(tmp_path: Path) -> None:
    """A pack whose `council_yield:` gives SCALAR counts (no `seats:`) must be
    judged by those scalars.

    This case is the only one that discriminates, and finding that out cost a
    surviving mutant. The first version of this test used a block declaring
    `applied: 1` and asserted "no candidate" — which passes for the WRONG
    reason: parsing returns early on `council_yield:`, so a scalar override
    leaves `findings` EMPTY, and a code path that ignored the block entirely
    would read (0 findings, 0 applied) and also emit no candidate. The verdict
    was right; the road to it proved nothing about the road it named (the
    vacuous-premise trap: a guilt test that reaches its verdict by another
    route is not evidence about the route).

    Inverted here: the scalars say findings>0 with applied==0, so reading the
    block MUST convict while ignoring it would see 0 findings and acquit. A
    mutant that stops honouring `used_override` now fails."""
    _write_pack(
        tmp_path,
        "p1",
        dissent=[{"seat": "kimi-k3", "status": "CONFIRMED"}],
        council_yield={"findings": 2, "applied": 0, "rejected": 2},
    )
    cands = cyr.run([], repo_root=tmp_path)["amendments_candidates"]
    assert len(cands) == 1, cands
    assert cands[0]["source"] == "declared"
    assert cands[0]["findings"] == 2


def test_every_candidate_source_is_one_of_the_two_literals(tmp_path: Path) -> None:
    """A stable invariant rather than a corpus-coupled count: pinning "4
    candidates on the live corpus" would go red the day someone else's pack
    lands, failing a PR that touched nothing (the W129 shape). What is worth
    pinning is that the label can only ever be one of the two documented
    values."""
    _write_pack(tmp_path, "a", dissent=[{"seat": "kimi-k3", "status": "RETRACTED"}])
    _write_pack(
        tmp_path,
        "b",
        council_yield={"seats": [{"seat": "agy", "status": "RETRACTED"}]},
    )
    cands = cyr.run([], repo_root=tmp_path)["amendments_candidates"]
    assert cands
    assert all(c["source"] in ("declared", "derived") for c in cands), cands


# ---------------------------------------------------------------------------
# BLIND REFUTATION CURES (Kimi K3, non-Anthropic, generator != grader).
# The payload was the module's code ONLY — no tests, no PR framing, no author
# intent — so the refuter could not read the answer off our own words. Every
# finding below was CONFIRMED by running its input on disk before being
# accepted (a refuter's finding is a lead, not a fact, W65).
#
# All 60 tests passed both BEFORE and AFTER these cures, which is precisely
# why the cures needed tests of their own: behaviour nothing pins is
# behaviour nothing protects.
# ---------------------------------------------------------------------------


def test_override_with_only_est_tokens_does_not_erase_the_pack(tmp_path: Path) -> None:
    """F1, the sharpest finding: ANY non-empty mapping used to take the
    override path, so `council_yield: {est_tokens: 5000}` — an author adding
    only the informational field — silently DELETED that pack's entire
    `dissent:` list. And because the derived counts then read 0 findings, it
    ALSO silenced the AMENDMENTS antidote on exactly the pack that needed it:
    a council that raised something and applied none of it went unreported
    because its findings had been erased on the way in.

    An override that overrides with nothing is not an override."""
    _write_pack(
        tmp_path,
        "p1",
        council_yield={"est_tokens": 5000},
        dissent=[{"seat": "kimi-k3", "status": "RETRACTED"}],
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["findings"] == 1
    assert report["totals"]["retracted"] == 1
    cands = report["amendments_candidates"]
    assert len(cands) == 1, cands
    assert cands[0]["source"] == "derived"
    assert any("no usable seats" in w["warning"] for w in report["sources"]["warnings"])


def test_override_with_mistyped_seats_does_not_zero_the_pack(tmp_path: Path) -> None:
    """F2: `seats:` as a string (one indentation slip) failed
    `isinstance(list)`, fell into the scalar branch and fabricated totals of
    all zeros — a seat list with a typo read as "the council raised nothing"."""
    _write_pack(
        tmp_path,
        "p1",
        council_yield={"seats": "kimi-k3: CONFIRMED"},
        dissent=[{"seat": "agy", "status": "CONFIRMED"}],
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["findings"] == 1
    assert any("not a non-empty list" in w["warning"] for w in report["sources"]["warnings"])


def test_a_real_override_still_overrides(tmp_path: Path) -> None:
    """INNOCENCE for F1/F2 — the over-correction twin (W94: curing an
    over-match births the under-match). A block carrying genuine counts must
    STILL win over `dissent:`, or the cure has quietly deleted the feature."""
    _write_pack(
        tmp_path,
        "p1",
        council_yield={"findings": 5, "applied": 3, "rejected": 2},
        dissent=[{"seat": "kimi-k3", "status": "CONFIRMED"}],
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["findings"] == 5
    assert report["totals"]["confirmed"] == 3
    assert report["sources"]["packs_with_council_yield_override"] == 1


def test_override_with_seats_still_overrides(tmp_path: Path) -> None:
    """INNOCENCE for F1/F2, the other real override shape."""
    _write_pack(
        tmp_path,
        "p1",
        council_yield={"seats": [{"seat": "agy", "status": "CONFIRMED"}]},
        dissent=[{"seat": "kimi-k3", "status": "RETRACTED"}],
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["confirmed"] == 1
    assert report["totals"]["retracted"] == 0


def test_non_mapping_council_yield_is_reported_not_silently_ignored(
    tmp_path: Path,
) -> None:
    """F12: a mistyped `dissent:` raised a hard error while a mistyped
    `council_yield:` vanished without a word. Two sibling keys, asymmetric
    validation — one screams, the other disappears."""
    _write_pack(
        tmp_path,
        "p1",
        council_yield="applied 3 of 5",
        dissent=[{"seat": "kimi-k3", "status": "CONFIRMED"}],
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["findings"] == 1
    assert any("not a mapping" in w["warning"] for w in report["sources"]["warnings"])


def test_bool_and_negative_counts_are_refused_and_named(tmp_path: Path) -> None:
    """F11/F15: `isinstance(True, int)` is True in Python, so YAML
    `applied: yes` counted as 1 applied and `rejected: -3` flowed straight
    into the report as a negative total. Same cure rule 14 made days ago for
    `appetite:` in evidence_pack_lint.py — validate the NUMBER, not the type."""
    _write_pack(
        tmp_path,
        "p1",
        council_yield={"findings": 4, "applied": True, "rejected": -3, "plausible": 1},
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["retracted"] >= 0
    assert report["totals"]["confirmed"] != 1 or report["totals"]["findings"] == 4
    warns = " ".join(w["warning"] for w in report["sources"]["warnings"])
    assert "applied=True" in warns
    assert "rejected=-3" in warns


def test_zero_is_a_usable_count_not_a_rejected_one(tmp_path: Path) -> None:
    """INNOCENCE for F11 — the over-correction twin. `0` is a real, declared
    measurement ("we applied none"), and the bound is `>= 0`, never `> 0`.
    A later 'tidy' that excludes zero would delete the AMENDMENTS antidote's
    entire reason for existing."""
    _write_pack(tmp_path, "p1", council_yield={"findings": 3, "applied": 0, "rejected": 3})
    report = cyr.run([], repo_root=tmp_path)
    assert report["sources"]["packs_with_council_yield_override"] == 1
    assert not any("applied=0" in w["warning"] for w in report["sources"]["warnings"])
    assert len(report["amendments_candidates"]) == 1


def test_malformed_dissent_items_are_named_not_silently_dropped(
    tmp_path: Path,
) -> None:
    """F3: `_seat_findings_from_items` counted malformed items and its
    docstring promised they were "never silently vanished from the pack's
    diagnostics" — while BOTH call sites bound the count to `_malformed` and
    threw it away. A docstring describing behaviour the code does not have is
    worse than silence: it tells the next reader not to look."""
    _write_pack(
        tmp_path,
        "p1",
        dissent=[
            {"seat": "kimi-k3", "status": "CONFIRMED"},
            {"seat": ""},
            "just a string",
        ],
    )
    report = cyr.run([], repo_root=tmp_path)
    assert report["totals"]["findings"] == 1
    assert any("2 malformed" in w["warning"] for w in report["sources"]["warnings"])


def test_role_is_about_the_seat_not_the_work_it_reviewed(tmp_path: Path) -> None:
    """F13, the over-match: "kimi-k3 on opus's own diff" is a KIMI seat
    reviewing an OPUS diff — the cross-family case this whole report exists to
    measure — and it was filed as `self`, deleting it from council yield."""
    assert cyr.classify_role("kimi-k3 on opus's own diff") == cyr.ROLE_REVIEW
    assert cyr.classify_role("sonnet reviewing codex, this session was clean") == cyr.ROLE_REVIEW


def test_genuine_self_signals_still_classify_as_self() -> None:
    """INNOCENCE for F13 — the under-match twin. Curing an over-match births
    it (W94), so the real self-refutation shapes measured in the live corpus
    must still be caught."""
    for raw in (
        "session (declared limit, unresolved)",
        "session self-refutation (recorded because nothing external caught it)",
        "sonnet-5 (self, bite-proof)",
        "the build lane, against its own correction",
    ):
        assert cyr.classify_role(raw) == cyr.ROLE_SELF, raw
    assert cyr.classify_role("Harness floor recompute (CI, deterministic)") == cyr.ROLE_GATE
    assert cyr.classify_role("kimi-k3 (cross-family refuter, blind)") == cyr.ROLE_REVIEW


def test_markdown_section_ends_at_any_heading_level(tmp_path: Path) -> None:
    """F4: the terminator matched h2 ONLY, so an `# Appendix` chapter below
    the review section did not end it and every table further down the
    document was ingested — producing phantom findings named `foo`, `---`
    and `a`. A report that manufactures findings out of unrelated tables is
    worse than one that reports none."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "## Adversarial review\n\n"
        "| Seat | Disposition |\n| --- | --- |\n| kimi-k3 | applied |\n\n"
        "# Appendix\n\n"
        "| foo | bar |\n| --- | --- |\n| a | b |\n",
        encoding="utf-8",
    )
    report = cyr.run([str(doc)], repo_root=tmp_path)
    seats = {f["family"] for f in report["family_role_matrix"]}
    assert report["totals"]["findings"] == 1, report["totals"]
    assert cyr.UNATTRIBUTED not in seats or report["totals"]["unrecognized"] == 0


def test_markdown_second_table_header_and_separators_are_not_findings(
    tmp_path: Path,
) -> None:
    """F5: only the FIRST data row was separator-checked, so a second table in
    the same section contributed its header row and its `---` separator as
    findings literally named `Seat` and `---`."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "## Adversarial review\n\n"
        "| Seat | Disposition |\n| --- | --- |\n| kimi-k3 | applied |\n\n"
        "| Seat | Disposition |\n| --- | --- |\n| sonnet | rejected |\n",
        encoding="utf-8",
    )
    report = cyr.run([str(doc)], repo_root=tmp_path)
    assert report["totals"]["findings"] == 2, report["totals"]
    assert report["totals"]["unrecognized"] == 0


def test_markdown_table_inside_a_code_fence_is_an_illustration_not_data(
    tmp_path: Path,
) -> None:
    """F6: a dossier that SHOWS the reader what the table looks like was
    convicted by its own example."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "## Adversarial review\n\nExample of the format:\n\n"
        "```\n| Seat | Disposition |\n| --- | --- |\n| kimi-k3 | applied |\n```\n\n"
        "No findings were raised.\n",
        encoding="utf-8",
    )
    report = cyr.run([str(doc)], repo_root=tmp_path)
    assert report["totals"]["findings"] == 0, report["totals"]


def test_markdown_and_yaml_agree_on_the_disposition_vocabulary(
    tmp_path: Path,
) -> None:
    """F10: a hand-written table saying `Confirmed` — the exact word the
    `dissent:` schema uses — fell through to `unrecognized`, because the
    markdown mapper only knew applied/rejected/partial. The two formats
    describe the same three outcomes and must not disagree on their names."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "## Adversarial review\n\n"
        "| Seat | Disposition |\n| --- | --- |\n"
        "| kimi-k3 | Confirmed |\n| agy | Retracted |\n| sonnet | applied |\n",
        encoding="utf-8",
    )
    report = cyr.run([str(doc)], repo_root=tmp_path)
    assert report["totals"]["unrecognized"] == 0, report["totals"]
    assert report["totals"]["confirmed"] == 2
    assert report["totals"]["retracted"] == 1


def test_fallback_doc_candidate_is_not_mislabelled_as_derived(
    tmp_path: Path,
) -> None:
    """F14 (my own defect, not the implementer's): `derived` is DEFINED as
    "the counts come from its dissent: list" — and a fallback markdown doc has
    no dissent list at all. Labelling it `derived` makes the `source` field
    say something untrue about where the number came from, which is the exact
    failure the field exists to prevent."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "## Adversarial review\n\n"
        "| Seat | Disposition |\n| --- | --- |\n| kimi-k3 | rejected |\n",
        encoding="utf-8",
    )
    cands = cyr.run([str(doc)], repo_root=tmp_path)["amendments_candidates"]
    assert len(cands) == 1, cands
    assert cands[0]["source"] == "fallback_md"


def test_this_session_is_temporal_when_the_seat_names_a_family() -> None:
    """"this session" says WHEN, not WHO. The live corpus proves it is used
    both ways, so treating it as a strong self-signal deleted four genuine
    cross-family kimi findings from council yield — inflating the honesty of
    the very number this report exists to keep honest, by removing the
    external review from it."""
    raw = "kimi-code/k3 (cross-family adversarial review, this session)"
    assert cyr.normalize_family(raw) == "kimi"
    assert cyr.classify_role(raw) == cyr.ROLE_REVIEW


def test_this_session_still_decides_when_nothing_else_identifies_the_seat() -> None:
    """The under-match twin, and it is not hypothetical: the first cut of the
    F13 cure dropped `this session` outright and reclassified BOTH of these
    real corpus strings as `review` — counting the session's own re-runs as
    council yield. Caught by diffing the live matrix, not by reading."""
    for raw in (
        "this session, independent gate re-run beyond what the receipts above required",
        "this session, independent re-verification of the merge (fresh context)",
    ):
        assert cyr.normalize_family(raw) == cyr.UNATTRIBUTED, raw
        assert cyr.classify_role(raw) == cyr.ROLE_SELF, raw


def test_markdown_empty_seat_cell_is_not_a_finding(tmp_path: Path) -> None:
    """The markdown path accepted a blank seat cell and reported a finding
    literally named "''", while the YAML path already refuses a blank seat —
    the same asymmetric-validation shape as F12, one format screaming and the
    other inventing. Found by a surviving mutant: the cure had been written
    without a proof, which is a cure nothing protects."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "## Adversarial review\n\n"
        "| Seat | Disposition |\n| --- | --- |\n"
        "| kimi-k3 | applied |\n|  | rejected |\n",
        encoding="utf-8",
    )
    report = cyr.run([str(doc)], repo_root=tmp_path)
    assert report["totals"]["findings"] == 1, report["totals"]
    assert report["totals"]["retracted"] == 0
