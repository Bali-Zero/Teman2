"""Guilt+innocence tests for scripts/detect_secrets_auto_triage.py's
CONTENT_KEYED_RULES (cicatrix-superscar.md #3 — guard over/under-match).

Registered in infra/guard-conformance/registry.json under the
`detect_secrets_content_keyed_rules` surface; executed by
.github/workflows/worker-plane-review-tests.yml — the workflow that already
owns scripts/check_worker_plane_review.py and
scripts/launch_worker_plane_review_panel.py, the two files this rule scopes
to.

Context (PR #3127): a fresh `detect-secrets scan` surfaced 18 unaudited
"Hex High Entropy String" findings in these two files — all executable
code-signing identity pins (sha256/cdhash of production CLI binaries used
to verify supply-chain integrity before spawning a reviewer process, plus a
PRODUCTION_ARTIFACT_SHA256 dict of the same class of content hash). These
are public integrity anchors, never credentials — removing them would
weaken the check they implement.

A plain PATH-based auto-triage rule (the shape most of this file's existing
AUTO_APPROVE_RULES use) would have blanket-approved ANY future finding
anywhere in these two files, including a real secret added later on an
unrelated line — exactly the #3 guard-over-match failure mode this repo's
cicatrix catalog warns about. CONTENT_KEYED_RULES instead requires the
actual source line at the finding's line_number to ALSO match a narrow
assignment-target pattern (`sha256|cdhash|codex_wrapper|codex_package`), so
the corpus below proves both halves: the 18 real findings get approved
(guilt) AND an unrelated secret on some other line in the SAME files does
not (innocence).

HARDENING (same-day cross-family review, 2026-07-26): the first version of
CONTENT_KEYED_RULES matched on the assignment TARGET name only, leaving the
VALUE unconstrained — a real credential assigned to `sha256=`/`cdhash=`
would have been approved on name alone, and Python's `;`-separated
statements meant a legitimate pin followed by a second, unrelated secret
assignment on the same line would ride along under the same line_number
match. The rule now also requires the value to be exactly the pin's hex
digest shape (64 lowercase hex chars for sha256/codex_wrapper/codex_package,
40 for cdhash), end-anchored to the line (optional trailing comma). Two
more innocence cases below prove both holes are closed; the existing guilt
cases (still passing) prove the fix didn't reintroduce the opposite
failure — a real digest getting rejected because the anchor now bites.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.detect_secrets_auto_triage import CONTENT_KEYED_RULES, classify, triage

CHECK_WORKER_PLANE_REVIEW = "scripts/check_worker_plane_review.py"
LAUNCH_WORKER_PLANE_REVIEW_PANEL = "scripts/launch_worker_plane_review_panel.py"

# Line numbers re-verified against the actual files on disk 2026-08-22 (the
# exact 18 findings `Detect Secrets` flagged on PR #3127).
CHECK_WORKER_PLANE_REVIEW_PIN_LINES = [185, 186, 196, 197]
LAUNCH_WORKER_PLANE_REVIEW_PANEL_PIN_LINES = [
    210,
    211,
    222,
    223,
    238,
    239,
    248,
    249,
    260,
    261,
    273,
    274,
    284,
    285,
]


def test_rule_registered_and_scoped_to_exactly_two_files() -> None:
    """Sanity: exactly one content-keyed rule for worker-plane, path-scoped
    to the two worker-plane review files — not a blanket match on
    scripts/*.py. (A second, unrelated content-keyed rule for KBLI
    gold-set data is added below — this test stays scoped to rule 0.)"""
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[0]
    assert path_pat.search(CHECK_WORKER_PLANE_REVIEW)
    assert path_pat.search(LAUNCH_WORKER_PLANE_REVIEW_PANEL)
    assert not path_pat.search("scripts/some_other_review_script.py")
    assert "credentials" in reason


# --- GUILT: the 18 real PR #3127 findings must be auto-approved -----------


def test_guilt_check_worker_plane_review_identity_pins_approved() -> None:
    for line in CHECK_WORKER_PLANE_REVIEW_PIN_LINES:
        auto, _reason = classify(CHECK_WORKER_PLANE_REVIEW, line)
        assert auto, f"{CHECK_WORKER_PLANE_REVIEW}:{line} should be auto-approved"


def test_guilt_launch_worker_plane_review_panel_identity_pins_approved() -> None:
    for line in LAUNCH_WORKER_PLANE_REVIEW_PANEL_PIN_LINES:
        auto, _reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, line)
        assert auto, f"{LAUNCH_WORKER_PLANE_REVIEW_PANEL}:{line} should be auto-approved"


def test_guilt_production_artifact_sha256_dict_members_approved() -> None:
    """PRODUCTION_ARTIFACT_SHA256's members (codex_wrapper, codex_package)
    don't say sha256=/cdhash= on their own line — they are the two findings
    a rule keyed ONLY on the literal names `sha256`/`cdhash` would have
    missed, which is why those two names are also in the content pattern."""
    for line in (284, 285):
        auto, _reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, line)
        assert auto, f"{LAUNCH_WORKER_PLANE_REVIEW_PANEL}:{line} should be auto-approved"


# --- INNOCENCE: unrelated lines/files must stay flagged --------------------


def test_innocence_unrelated_lines_in_same_files_not_approved() -> None:
    """Lines that are NOT sha256/cdhash/codex_wrapper/codex_package
    assignments must remain unaudited even inside the two approved files —
    this is what distinguishes a content-keyed rule from a blanket
    whole-file path rule (the over-match this rule exists to avoid)."""
    # kimi=Path(...) — unrelated identifier.
    auto, reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, 190)
    assert not auto
    assert reason == "no rule matched"
    # team_identifier="..." — also unrelated.
    auto, reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, 212)
    assert not auto
    assert reason == "no rule matched"


def test_innocence_synthetic_secret_on_unrelated_key_in_same_file() -> None:
    """A real secret assigned to a DIFFERENT identifier in one of these two
    files (e.g. a leaked API key added on a future PR) must still be
    caught — proves the rule is keyed on the assignment target, never on
    hex/secret shape alone."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[0]
    fake_secret_line = '        api_key="sk-FAKESECRETVALUE1234567890ABCDEF",\n'
    assert content_pat.search(fake_secret_line) is None


def test_innocence_other_file_with_sha256_assignment_not_approved() -> None:
    """The identical sha256= assignment shape in a file OUTSIDE the two
    scoped paths must not be auto-approved by this rule — proves the path
    scope, not just the content pattern, is load-bearing."""
    auto, reason = classify("scripts/some_other_script.py", 210)
    assert not auto
    assert reason == "no rule matched"


# --- HARDENING (2026-07-26 review): value-shape + end-anchor -------------


def test_innocence_pin_key_with_non_hex_value_not_approved() -> None:
    """A real credential assigned to a pin-named key (`sha256=`) must NOT
    be approved on the key name alone — the value has to actually be a
    64/40-char lowercase-hex digest. `ghp_...` is GitHub's real token
    prefix shape: alnum, not hex, wrong length."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[0]
    fake_token_line = (
        '        sha256="ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD",\n'
    )
    assert content_pat.search(fake_token_line) is None


def test_innocence_pin_followed_by_second_statement_not_approved() -> None:
    """Python allows `;`-separated statements on one line — a legitimate
    pin assignment followed by an unrelated secret assignment on the SAME
    line must not ride along under the pin's approval. The end-anchor
    (optional trailing comma, then end-of-line) breaks on anything after
    the pin's closing quote."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[0]
    compound_line = (
        '        sha256="d01b49210d72ecbe277a2665d104bacccddf2d22185be99446d2929e0edfc48d"'
        '; api_key="sk-realsecretvalue1234567890ABCDEF"\n'
    )
    assert content_pat.search(compound_line) is None


# --- KBLI gold-set sentence_sha256 rule (2026-07-26) ------------------------
#
# Context (PR #3181, apps/mouth/data/kbli-gold-all.json): the L3 prose-gap-
# disclosure cure (scripts/kbli_filiera/cure_l3_prose_gap_disclosure.py)
# writes a `sentence_sha256` idempotency marker on every record it touches —
# a 16-hex-char truncated digest of the appended disclosure sentence, so a
# re-run of the cure can tell its own prior work apart from an untouched
# record. `Detect Secrets` flagged 3 as "Hex High Entropy String" (findings
# verified live on PR #3181's head 2026-07-26: lines 15773/17523/29285, all
# `"sentence_sha256": "<16 lowercase hex>"`, no trailing comma — the field is
# the last key in its object in every observed instance).
#
# Unlike the other three KBLI rules in AUTO_APPROVE_RULES (data/kbli-filiera/,
# cure_specs/, and the canonical dataset + sync'd copies), kbli-gold-all.json
# has an OPEN writer set — kbli_audit_patcher.py, kbli_enrich_write.py, and
# kbli_enrich_pipeline.py all write it directly, plus cure specs patching it
# value-in-place — so a path-only rule here would be the first KBLI rule
# without the closed-writer-set argument that makes the others safe.
# Content-keyed instead: approval requires the line to be structurally
# exactly `"sentence_sha256": "<16 lowercase hex>"[,]`, end-anchored, mirroring
# the worker-plane rule's own discipline above.
#
# The real flagged lines are not reachable via `classify(path, line_number)`
# in THIS test's checkout: apps/mouth/data/kbli-gold-all.json exists on main,
# but the sentence_sha256 field itself is new content that only exists on the
# still-unmerged PR #3181 branch (0 occurrences on main as of 2026-07-26).
# The guilt cases below use the literal source lines copied verbatim from
# that PR's head instead of a live file read.

KBLI_GOLD_ALL = "apps/mouth/data/kbli-gold-all.json"

# Copied verbatim from PR #3181 head 61c2e532, lines 15773 / 17523 / 29285.
KBLI_GOLD_SENTENCE_SHA256_REAL_LINES = [
    '      "sentence_sha256": "398e623b02c49ba5"',
    '      "sentence_sha256": "bcbf0d7b6a2cd71d"',
    '      "sentence_sha256": "af4b83d5bbc0e35f"',
]


def _find_content_keyed_rule(
    reason_substring: str,
) -> tuple[re.Pattern[str], re.Pattern[str], str]:
    """Locate one CONTENT_KEYED_RULES entry by a substring unique to its
    reason string, rather than by list position.

    2026-08-23: three tests in this file indexed into CONTENT_KEYED_RULES
    positionally (CONTENT_KEYED_RULES[1]/[13]/[14]) instead of by identity.
    detect_secrets_auto_triage.py's own header comment above the list
    documents why the list had become append-only-by-convention: "inserting
    a rule mid-list shifts every later index and breaks the per-rule
    registration tests (measured the hard way 2026-08-21: 8 red from one
    mid-list insert)." That is the index-anchoring naming the symptom, not
    a reason the list itself needs positional stability — nothing in
    classify()'s matching loop depends on order for correctness (it returns
    on first content+path match; two rules covering the same file+line
    would only change WHICH reason string is reported, never whether the
    line is approved). Looking a rule up by what makes it unique — a
    substring of its own reason — removes the coupling instead of
    documenting around it: a rule can be inserted anywhere in the list
    without touching this file.

    Fails loudly on zero or more than one match rather than silently
    returning the wrong rule — a lookup that can return the wrong entry
    without raising is not an improvement on the index it replaces.
    """
    matches = [rule for rule in CONTENT_KEYED_RULES if reason_substring in rule[2]]
    assert len(matches) == 1, (
        f"expected exactly 1 CONTENT_KEYED_RULES entry with reason containing "
        f"{reason_substring!r}, found {len(matches)}: "
        f"{[rule[2] for rule in matches] if matches else [rule[2] for rule in CONTENT_KEYED_RULES]}"
    )
    return matches[0]


def test_kbli_gold_rule_registered_and_scoped_to_exactly_one_file() -> None:
    """Sanity: the KBLI gold-set rule is path-scoped to kbli-gold-all.json
    only — not the other KBLI files, which stay on the closed-writer-set
    path rules in AUTO_APPROVE_RULES."""
    # This count is a DELIBERATE speed bump, not bureaucracy (2026-08-21 audit:
    # a directory-wide AUTO_APPROVE_RULES entry had forgiven a real Google
    # OAuth triple for months, and 49/100 entries share that broad shape) —
    # it forces whoever adds a new auto-approval rule to also name it, date
    # it, and explain why it's not a credential, right here. Do NOT delete
    # this assert to "fix" a failure; see the structural property check
    # below for what a fix should actually add.
    #
    # 2026-08-21: this branch (#4498) independently added the p2b_score.json
    # rule, but #4422 landed it on main first via a different path — same
    # rule, registered once, not twice. The count below (15) and the comment
    # trail are derived from the live registry post-merge, not summed by
    # hand (team-lead's call: a rule appears once in the trail regardless of
    # how many PRs tried to add it).
    assert len(CONTENT_KEYED_RULES) == 17, (
        f"CONTENT_KEYED_RULES now has {len(CONTENT_KEYED_RULES)} entries, not 17. "
        "If you just ADDED a rule: bump this number AND append a `# +1: <what> "
        "(<date>, PR #NNNN)` line below, matching the existing trail's format — "
        "that comment IS the audit record this assert exists to force. "
        "If you REMOVED a rule: lower the number and drop its `# +1:` line. "
        "Do not change this number without touching the comment trail."
    )
    # +1: infra/llm-credentials/declared.json sha256_16 (2026-08-12)
    # +1: apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py public_key (2026-08-13)
    # +1: research/visa/2026-08-12-gold-replay-live-report.json payload_sha256 (2026-08-13)
    # +1: scripts/kbli_bench/results/p2b_score.json corpus_sha256 (2026-08-21, #4422 via main merge)
    # +2: scripts/lint_google_oauth_credentials.py KNOWN_COMPROMISED fingerprints + selftest fragment (2026-08-21)
    # +1: scripts/lint_telegram_tokens.py KNOWN_COMPROMISED sha256[:16] key (2026-08-14)
    # +1: traffic-source fail-closed proof identity/integrity anchors (2026-08-15)
    # +1: fold_pack_seq10.py seq-9 chain anchor exact-value pin (2026-08-19)
    # +1: fold_pack_seq11.py seq-10 chain anchor exact-value pin (2026-08-20)
    # +1: fold_pack_seq12.py seq-11 chain anchor exact-value pin (2026-08-20)
    # +1: fold_pack_seq13_rules.py seq-12 chain anchor exact-value pin (2026-08-23, #4660)
    # +1: fold_pack_seq13_source.py seq-12 chain anchor exact-value pin (2026-08-23, #4667)
    #
    # Note (2026-08-23): "appended last" is no longer a constraint. It was
    # true only because this test and the two Google-OAuth tests below
    # indexed into the list positionally; all three now look their rule up
    # by content instead (see _find_content_keyed_rule above), so a new
    # rule may be inserted anywhere in CONTENT_KEYED_RULES without breaking
    # a registration test. The count assert immediately above is unaffected
    # by this - it counts entries, not positions, and stays deliberate.
    path_pat, _content_pat, reason = _find_content_keyed_rule("KBLI gold-set")
    assert path_pat.search(KBLI_GOLD_ALL)
    assert not path_pat.search("apps/mouth/data/KBLI_2025_FINAL_CLEAN.json")
    assert not path_pat.search("data/kbli-filiera/some_manifest.json")
    assert "credential" in reason


def test_content_keyed_rules_are_well_formed_and_anchored() -> None:
    """Property check, ADDED ALONGSIDE the hand-maintained count above, not
    instead of it (2026-08-21, team-lead review: the count is a deliberate
    speed bump that forces a name+date declaration per rule; replacing it
    would make adding a bad rule painless again). This one catches a
    MALFORMED or unsafely-unanchored rule regardless of how many there are —
    something the count alone can never verify.

    `classify()` matches every rule with `.search()`, not `.match()` — a
    path or content pattern without a start anchor would match as a
    substring ANYWHERE in the path/line, which is exactly the #3
    guard-over-match failure mode (cicatrix-superscar.md) this file's own
    CONTENT_KEYED_RULES mechanism exists to avoid for the broader
    AUTO_APPROVE_RULES list."""
    for idx, entry in enumerate(CONTENT_KEYED_RULES):
        assert len(entry) == 3, f"CONTENT_KEYED_RULES[{idx}] is not a 3-tuple: {entry!r}"
        path_pat, content_pat, reason = entry
        assert isinstance(path_pat, re.Pattern), (
            f"CONTENT_KEYED_RULES[{idx}] path is not a compiled re.Pattern: {path_pat!r}"
        )
        assert isinstance(content_pat, re.Pattern), (
            f"CONTENT_KEYED_RULES[{idx}] content is not a compiled re.Pattern: {content_pat!r}"
        )
        assert isinstance(reason, str) and reason.strip(), (
            f"CONTENT_KEYED_RULES[{idx}] reason is empty or not a string"
        )
        # `(^|/)` anchors to the start of the path OR a path-component
        # boundary — both are legitimate; a pattern with neither would
        # match anywhere via .search().
        assert path_pat.pattern.startswith("^") or path_pat.pattern.startswith("(^|/)"), (
            f"CONTENT_KEYED_RULES[{idx}] path pattern is not start-anchored, "
            f"so .search() would match it as a substring anywhere: {path_pat.pattern!r}"
        )
        assert content_pat.pattern.startswith("^"), (
            f"CONTENT_KEYED_RULES[{idx}] content pattern is not start-anchored, "
            f"so .search() would match it as a substring anywhere in the line: "
            f"{content_pat.pattern!r}"
        )


def test_guilt_kbli_gold_real_pr3181_findings_approved() -> None:
    """The 3 real findings Detect Secrets flagged on PR #3181's head must be
    approved by this rule's content pattern."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    for line in KBLI_GOLD_SENTENCE_SHA256_REAL_LINES:
        assert content_pat.match(line), f"should be approved: {line!r}"


def test_guilt_kbli_gold_trailing_comma_variant_approved() -> None:
    """Every observed occurrence has sentence_sha256 as the LAST key in its
    object (no trailing comma), but the pattern allows an optional trailing
    comma too — a future cure that reorders fields must not silently stop
    matching."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    assert content_pat.match('  "sentence_sha256":"0123456789abcdef",')


def test_innocence_kbli_gold_wrong_key_name_not_approved() -> None:
    """A real secret assigned to a DIFFERENT key in the same file — even one
    with the exact 16-hex shape — must still be flagged. Proves the rule is
    keyed on the field NAME, not merely on hex shape."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    fake_line = '      "api_key": "398e623b02c49ba5"'
    assert content_pat.match(fake_line) is None


def test_innocence_kbli_gold_wrong_value_shape_not_approved() -> None:
    """A real credential assigned to `sentence_sha256` must not be approved
    on the key name alone — the value has to actually be 16 lowercase hex
    chars. `ghp_...` is GitHub's real token prefix shape."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    fake_line = '      "sentence_sha256": "ghp_realtoken1234567"'
    assert content_pat.match(fake_line) is None


def test_innocence_kbli_gold_wrong_length_not_approved() -> None:
    """15 or 17 hex chars must not match — the shape is exactly 16, not
    'roughly hex-shaped'."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    assert content_pat.match('      "sentence_sha256": "398e623b02c49ba"') is None  # 15
    assert content_pat.match('      "sentence_sha256": "398e623b02c49ba5a"') is None  # 17


def test_innocence_kbli_gold_uppercase_hex_not_approved() -> None:
    """Uppercase hex must not match — the cure only ever emits lowercase
    (verified against all 39 occurrences on PR #3181's head); an uppercase
    variant is a shape a real pasted credential could take that a lowercase-
    only cure output never would."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    assert content_pat.match('      "sentence_sha256": "398E623B02C49BA5"') is None


def test_innocence_kbli_gold_ride_along_statement_not_approved() -> None:
    """A legitimate sentence_sha256 line followed by an unrelated assignment
    must not approve the ride-along, mirroring the worker-plane rule's own
    end-anchor discipline."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    compound_line = (
        '      "sentence_sha256": "398e623b02c49ba5"; "api_key": "realsecret123456"'
    )
    assert content_pat.match(compound_line) is None


def test_innocence_kbli_gold_other_file_with_same_shape_not_approved() -> None:
    """The identical sentence_sha256 line shape approves on CONTENT alone
    (proving the content pattern itself is permissive enough to need the
    path scope), but a real end-to-end call through `classify()` against a
    file OUTSIDE kbli-gold-all.json must not be auto-approved — proves the
    path scope, not just the content pattern, is load-bearing. Uses the same
    "scripts/some_other_script.py" control path the worker-plane innocence
    test above already proves matches zero AUTO_APPROVE_RULES too (so a
    False here can only come from the content-keyed path scope, never from
    an unrelated rule picking it up incidentally — the first version of this
    test used `__file__`, which is itself a `test_*.py` file and got
    silently approved by the UNRELATED `test_*/_test` fixture rule instead
    of exercising this rule's path scope at all), monkeypatched to return
    the gold-set line's text so only the PATH differs from the guilt case."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[1]
    line = KBLI_GOLD_SENTENCE_SHA256_REAL_LINES[0]
    assert content_pat.match(line)  # content shape alone: matches

    import scripts.detect_secrets_auto_triage as triage_mod

    real_line_text = triage_mod._line_text
    try:
        triage_mod._line_text = lambda file_path, line_number: line  # noqa: ARG005
        auto, reason = triage_mod.classify("scripts/some_other_script.py", 1)
        assert not auto, "same content, wrong path must not be approved"
        assert reason == "no rule matched"
    finally:
        triage_mod._line_text = real_line_text


# --- article translation freshness stamp (2026-07-28) -----------------------
#
# Context (PR #3379): scripts/translate-articles.py used to skip on the mere
# EXISTENCE of the target file, so every translation froze at birth and an
# English correction never reached its locales — measured, 1275 of 2664
# translations were behind their source, and the hourly organ reported
# "0 translated, 1592 skipped/failed" every hour while exiting 0. It now skips
# on FRESHNESS: each translation records `source_sha256`, the digest of the
# English source BODY it was made from, in its own frontmatter. Deliberately
# not mtime — a checkout resets mtime, so the digest has to travel inside the
# file.
#
# `Detect Secrets` flagged all 1294 of them as "Hex High Entropy String" on
# that PR — correctly, by shape. The value is recomputable by anyone from the
# public English article: an integrity anchor, never a credential.
#
# Content-keyed rather than path-only because the writer set for article .mdx
# files is as open as it gets — the translator, the editorial pipeline, and
# humans editing prose by hand. A path rule would blanket-approve any future
# finding anywhere in 2500+ content files.

ARTICLE_IT = "apps/mouth/src/content/articles/business/art-of-strategic-patience.it.mdx"

# Copied verbatim from the stamped corpus on this branch.
ARTICLE_STAMP_REAL_LINES = [
    'source_sha256: "5f0aed5d76a50a055ab3f3d636b7a18fd7d98e791d12b8711086b19ee414786d"',
    'source_sha256: "73268c78bc925d2d18d31d60f4a6a1daaa1d69d02feb80a704cc1c19f5242595"',
]


def test_article_stamp_rule_registered_and_scoped_to_translations_only() -> None:
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[2]
    assert path_pat.search(ARTICLE_IT)
    for loc in ("id", "ru", "fr"):
        assert path_pat.search(f"apps/mouth/src/content/articles/business/x.{loc}.mdx")
    assert "credential" in reason


def test_innocence_english_source_is_out_of_scope() -> None:
    """The stamp only ever lands in a translation. An English source .mdx that
    grows a 64-hex line is NOT covered by this rule and stays unaudited."""
    path_pat, _content_pat, _reason = CONTENT_KEYED_RULES[2]
    assert not path_pat.search("apps/mouth/src/content/articles/business/x.mdx")


def test_innocence_other_content_paths_are_out_of_scope() -> None:
    path_pat, _content_pat, _reason = CONTENT_KEYED_RULES[2]
    assert not path_pat.search("apps/mouth/src/content/homepage-layout.json")
    assert not path_pat.search("apps/backend-rag/backend/config.it.mdx")


def test_guilt_real_stamp_lines_are_approved() -> None:
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[2]
    for line in ARTICLE_STAMP_REAL_LINES:
        assert content_pat.match(line), f"should be approved: {line!r}"


def test_innocence_a_credential_on_another_frontmatter_key_is_not_approved() -> None:
    """The whole point of content-keying: only THIS key, in THIS shape."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[2]
    for line in (
        'api_key: "5f0aed5d76a50a055ab3f3d636b7a18fd7d98e791d12b8711086b19ee414786d"',
        'token: "ghp_reallivetokenvaluethatmustneverbeapproved0001"',
        'source_sha256_backup: "5f0aed5d76a50a055ab3f3d636b7a18fd7d98e791d12b8711086b19ee414786d"',
    ):
        assert not content_pat.match(line), f"must NOT be approved: {line!r}"


def test_innocence_wrong_shape_is_not_approved() -> None:
    """Uppercase hex, wrong length, unquoted, or a second value riding along on
    the same line all fail — the pattern is end-anchored."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[2]
    for line in (
        'source_sha256: "5F0AED5D76A50A055AB3F3D636B7A18FD7D98E791D12B8711086B19EE414786D"',
        'source_sha256: "5f0aed5d"',
        "source_sha256: 5f0aed5d76a50a055ab3f3d636b7a18fd7d98e791d12b8711086b19ee414786d",
        'source_sha256: "5f0aed5d76a50a055ab3f3d636b7a18fd7d98e791d12b8711086b19ee414786d" api_key: "ghp_x"',
    ):
        assert not content_pat.match(line), f"must NOT be approved: {line!r}"


# --- tests?/**.sh gap (PRs #3591/#3596, 2026-08-04) ------------------------
#
# The generic "tests?/** tree" AUTO_APPROVE_RULES entry listed
# py/ts/tsx/js/jsx/json/yaml/yml but not sh, so a synthetic 40-char git oid
# fixture in scripts/tests/test_branch_graveyard_prmerged.sh read as a real
# "Hex High Entropy String" and blocked the Detect Secrets gate despite
# already living under a tests?/ dir. Guilt: a .sh file under scripts/tests/
# is now approved. Innocence: a .sh file NOT under a tests?/ dir is
# unaffected (still relies on some other rule or stays unaudited).


def test_guilt_shell_test_fixture_under_scripts_tests_is_approved() -> None:
    auto, reason = classify("scripts/tests/test_branch_graveyard_prmerged.sh", 54)
    assert auto, "scripts/tests/*.sh fixtures should be auto-approved"
    assert "tests/** tree" in reason


def test_innocence_shell_script_outside_tests_dir_not_approved_by_this_rule() -> None:
    auto, reason = classify("scripts/branch_graveyard_cleanup.sh", 10)
    assert not (auto and "tests/** tree" in reason), (
        "a .sh file outside a tests?/ dir must not be approved by the "
        f"tests-tree rule (got: auto={auto}, reason={reason!r})"
    )


# --- LLM credential registry sha256_16 rule (2026-08-12) --------------------
#
# Context: `infra/llm-credentials/declared.json` names WHICH Google API
# credentials are authorised to spend, so `scripts/llm_provider_reconcile.py`
# can ask Google (not our own ledger) whether an undeclared key is billing.
# The whole point of the file is that a PUBLIC repo can name a key without
# holding one, so it stores a one-way 16-hex truncation of the credential's
# UID — an identifier Google itself exposes as `credential_id` in Cloud
# Monitoring. Detect Secrets read that truncation as a "Hex High Entropy
# String" and blocked PR #4098 on `declared.json:22`.
#
# Content-keyed, same discipline as the rules above: approval needs the line
# to be exactly `"sha256_16": "<16 lowercase hex>"[,]`, end-anchored. The
# guilt case below reads the REAL line off disk through classify(), because
# unlike the KBLI rule this file exists in this checkout — so the test proves
# the rule fires on the actual finding CI rejected, not on a copy of it.

LLM_CREDENTIALS_DECLARED = "infra/llm-credentials/declared.json"


def test_llm_credentials_rule_registered_and_scoped_to_exactly_one_file() -> None:
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[4]
    assert path_pat.search(LLM_CREDENTIALS_DECLARED)
    assert not path_pat.search("infra/llm-credentials/declared.json.bak")
    assert not path_pat.search("infra/other/declared.json")
    assert "never key material" in reason


def test_guilt_the_real_line_ci_rejected_is_approved() -> None:
    """The exact finding that made `Detect Secrets` red on PR #4098.

    Read live off disk via classify(), so this fails if the file is renamed,
    the field is reshaped, or the rule is removed — not merely if someone
    edits a string literal in this test.
    """
    auto, reason = classify(LLM_CREDENTIALS_DECLARED, 22)
    assert auto, f"the real sha256_16 finding must be approved (got {reason!r})"
    assert "never key material" in reason


def test_innocence_the_label_line_in_the_same_file_is_not_approved() -> None:
    """Line 23 is the human-readable `label`. Nothing but the fingerprint line
    gets a pass, so a credential pasted anywhere else in this file still stops
    the gate."""
    auto, _reason = classify(LLM_CREDENTIALS_DECLARED, 23)
    assert not auto


def test_innocence_llm_credentials_wrong_key_name_not_approved() -> None:
    """Keyed on the field NAME, not on hex shape: the same 16-hex value under
    `api_key` must still be flagged."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[4]
    assert content_pat.match('      "api_key": "ddea903c496cd26c"') is None


def test_innocence_llm_credentials_real_credential_shape_not_approved() -> None:
    """A real credential assigned to `sha256_16` must not ride in on the key
    name. `AIza...` is Google's own API-key prefix — the exact shape this
    file exists to avoid ever holding."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[4]
    assert content_pat.match('      "sha256_16": "AIzaSyD-1234567890abcdefg"') is None


def test_innocence_llm_credentials_wrong_length_not_approved() -> None:
    """Exactly 16, not 'roughly hex-shaped'. A full 64-hex sha256 is also
    rejected: this field is defined as the truncation, and a full digest here
    would mean some other writer produced it."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[4]
    assert content_pat.match('      "sha256_16": "ddea903c496cd26"') is None  # 15
    assert content_pat.match('      "sha256_16": "ddea903c496cd26ca"') is None  # 17
    assert content_pat.match('      "sha256_16": "%s"' % ("a" * 64)) is None  # full digest


def test_innocence_llm_credentials_uppercase_hex_not_approved() -> None:
    """`credential_fingerprint()` emits lowercase (hashlib.hexdigest always
    does), so uppercase can only come from another writer — a shape a real
    pasted credential could take and this cure's output never would."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[4]
    assert content_pat.match('      "sha256_16": "DDEA903C496CD26C"') is None


def test_innocence_llm_credentials_ride_along_statement_not_approved() -> None:
    """End-anchored: a legitimate fingerprint followed by anything else on the
    same line must not launder the ride-along."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[4]
    compound = '      "sha256_16": "ddea903c496cd26c", "api_key": "AIzaSyD-1234567890abcd"'
    assert content_pat.match(compound) is None


def test_innocence_llm_credentials_same_shape_in_another_file_not_approved() -> None:
    """Path-scoped: the identical line in a different file gets no pass from
    this rule."""
    auto, reason = classify("infra/other/declared.json", 22)
    assert not (auto and "never key material" in reason)


# --- gold_replay_driver.py Ed25519 public_key rule (2026-08-13) ------------
#
# Context: CI's "Detect Secrets" gate flagged
# apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py:86 as an
# unaudited "Base64 High Entropy String" — the Ed25519 PUBLIC verification
# key of the production RulePack signing keypair (kid=prod-2026-07-1),
# already published verbatim in docs/runbooks/visa-engine-key-ceremony.md.
# It is a trust root read at replay time, never a secret; the private key
# never touches this repo.
#
# Content-keyed, same discipline as the rules above: approval needs the line
# to be exactly `"public_key": "<43-char base64url>"[,]`, end-anchored, so a
# real credential pasted onto any other line in this production-code file
# still stops the gate.

GOLD_REPLAY_DRIVER = "apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py"


def test_gold_replay_driver_rule_registered_and_scoped_to_exactly_one_file() -> None:
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[5]
    assert path_pat.search(GOLD_REPLAY_DRIVER)
    assert not path_pat.search(
        "apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py.bak"
    )
    assert not path_pat.search("apps/backend-rag/backend/scripts/visa_engine/other.py")
    assert "trust root" in reason


def test_guilt_gold_replay_driver_public_key_line_is_approved() -> None:
    """The exact finding shape that made `Detect Secrets` red: a 32-byte
    Ed25519 public key, unpadded base64url-encoded (43 chars)."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[5]
    for line in (
        '    "public_key": "ab3De9FghijKLM12no3PqrstUVwxyz45ABCdefGHI9X"',
        '        "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",',
    ):
        assert content_pat.match(line), f"must be approved: {line!r}"


def test_innocence_gold_replay_driver_wrong_key_name_not_approved() -> None:
    """Keyed on the field NAME, not on base64 shape: the same 43-char value
    under a different assignment target must still be flagged."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[5]
    assert (
        content_pat.match('    "private_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"')
        is None
    )


def test_innocence_gold_replay_driver_wrong_length_not_approved() -> None:
    """Exactly 43 chars (32-byte Ed25519 key, unpadded base64url) — a shorter
    or longer value cannot be this key and stays unaudited."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[5]
    assert content_pat.match('    "public_key": "AAAAAAAAAAAAAAAAAAAAAAAA"') is None  # too short
    assert (
        content_pat.match(
            '    "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"'
        )
        is None
    )  # too long


def test_innocence_gold_replay_driver_ride_along_statement_not_approved() -> None:
    """End-anchored: a legitimate public_key line followed by anything else
    must not launder the ride-along."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[5]
    compound = (
        '    "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", '
        '"api_key": "ghp_reallivetoken"'
    )
    assert content_pat.match(compound) is None


# --- gold replay driver live-run report payload_sha256 rule (2026-08-13) ---
#
# Context: the G-b gold replay driver's live-run report
# (research/visa/2026-08-12-gold-replay-live-report.json) repeats
# `payload_sha256` once per persona/pack observation — the content-derived
# sha256 of a PUBLIC signed RulePack payload, the same class of value as the
# AUTO_APPROVE_RULES `contracts/packs/rulepack-*.json` rule, just embedded in
# a research/ run report rather than the pack artifact itself. `Detect
# Secrets` flagged it as an unaudited "Hex High Entropy String".
#
# Content-keyed rather than a path-only research/*.json rule because this
# file's directory (research/visa/) can carry other ad-hoc JSON with
# different content in the future. Approval requires the line to be exactly
# `"payload_sha256": "<64 lowercase hex>"[,]`, end-anchored — same discipline
# as every other rule in this list.
#
# This rule shipped (PR #4131 / commit 07073a297) with no guilt/innocence
# tests of its own — exactly the gap that let a same-day merge-of-main
# collide it with `infra/llm-credentials/declared.json`'s rule at the same
# list index (both additions correct individually, colliding only in
# position; see the reordering above and cicatrix-superscar #9). The second
# collision, with main's gold_replay_driver.py rule landing at the same
# index via PR #4130, is resolved the same way: both rules kept, this one
# moved to CONTENT_KEYED_RULES[6].

GOLD_REPLAY_LIVE_REPORT = "research/visa/2026-08-12-gold-replay-live-report.json"
GOLD_REPLAY_POST_NOTICE_REPORT = (
    "research/visa/2026-08-15-gold-replay-live-post-notice-report.json"
)


def test_gold_replay_live_report_rule_registered_and_scoped_to_reviewed_files() -> (
    None
):
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[6]
    assert path_pat.search(GOLD_REPLAY_LIVE_REPORT)
    assert path_pat.search(GOLD_REPLAY_POST_NOTICE_REPORT)
    assert not path_pat.search(
        "research/visa/2026-08-12-gold-replay-live-report.json.bak"
    )
    assert not path_pat.search(
        "research/visa/2026-08-15-gold-replay-live-post-notice-report.json.bak"
    )
    assert not path_pat.search("research/visa/2026-08-13-some-other-report.json")
    assert not path_pat.search("research/visa/2026-08-16-gold-replay-live-report.json")
    assert "never a credential" in reason


def test_guilt_gold_replay_live_report_real_line_is_approved() -> None:
    """The exact finding shape CI flagged, read live off disk via classify()
    at the file's first payload_sha256 occurrence (line 8) — so this fails if
    the file is renamed, the field is reshaped, or the rule is removed, not
    merely if someone edits a string literal in this test."""
    auto, reason = classify(GOLD_REPLAY_LIVE_REPORT, 8)
    assert auto, f"the real payload_sha256 finding must be approved (got {reason!r})"
    assert "never a credential" in reason


def test_guilt_gold_replay_post_notice_real_line_is_approved() -> None:
    """The exact line 8 finding from Detect Secrets job 94874089047 is the
    public RulePack payload digest and must be approved by the same narrow
    content-keyed rule."""
    auto, reason = classify(GOLD_REPLAY_POST_NOTICE_REPORT, 8)
    assert auto, f"the post-notice payload_sha256 must be approved (got {reason!r})"
    assert "never a credential" in reason


def test_innocence_gold_replay_live_report_wrong_key_name_not_approved() -> None:
    """Line 9 is `rule_pack_id` — a UUID, not a sha256, and not this rule's
    key name either way. Nothing but the payload_sha256 line gets a pass."""
    auto, _reason = classify(GOLD_REPLAY_LIVE_REPORT, 9)
    assert not auto


def test_innocence_gold_replay_live_report_wrong_key_name_same_hex_shape_not_approved() -> (
    None
):
    """Keyed on the field NAME, not on hex shape: the same 64-hex value under
    a different assignment target must still be flagged."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[6]
    fake_line = (
        '    "rulepack_signature": '
        '"3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f82"'
    )
    assert content_pat.match(fake_line) is None


def test_innocence_gold_replay_live_report_wrong_length_not_approved() -> None:
    """63 or 65 hex chars must not match — the shape is exactly 64, a real
    sha256, not 'roughly hex-shaped'."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[6]
    assert (
        content_pat.match(
            '    "payload_sha256": '
            '"3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f8"'
        )
        is None
    )  # 63
    assert (
        content_pat.match(
            '    "payload_sha256": '
            '"3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f82a"'
        )
        is None
    )  # 65


def test_innocence_gold_replay_live_report_uppercase_hex_not_approved() -> None:
    """Uppercase hex must not match — the driver only ever emits lowercase
    (hashlib.hexdigest always does); an uppercase variant is a shape a real
    pasted credential could take that this rule's own output never would."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[6]
    fake_line = (
        '    "payload_sha256": '
        '"3D068AEF2DCA40F1EFB74BDD3F8859E767C000282AB8299AC7F277B0B9719F82"'
    )
    assert content_pat.match(fake_line) is None


def test_innocence_gold_replay_live_report_ride_along_statement_not_approved() -> None:
    """End-anchored: a legitimate payload_sha256 line followed by anything
    else on the same line must not launder the ride-along."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[6]
    compound = (
        '    "payload_sha256": '
        '"3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f82", '
        '"api_key": "sk-realsecretvalue1234567890ABCDEF"'
    )
    assert content_pat.match(compound) is None


def test_innocence_gold_replay_driver_same_shape_in_another_file_not_approved() -> None:
    """Path-scoped: the identical line in a different file gets no pass from
    this rule."""
    auto, reason = classify(
        "apps/backend-rag/backend/scripts/visa_engine/other.py", 86
    )
    assert not (auto and "trust root" in reason)


def test_innocence_gold_replay_live_report_same_shape_in_another_file_not_approved() -> (
    None
):
    """Path-scoped: the identical line shape in a different file gets no
    pass from this rule."""
    auto, reason = classify("research/visa/some_other_report.json", 8)
    assert not (auto and "never a credential" in reason)


def test_innocence_gold_replay_post_notice_same_shape_in_similar_file_not_approved() -> (
    None
):
    """A future or renamed report receives no implicit approval."""
    auto, reason = classify(
        "research/visa/2026-08-16-gold-replay-live-post-notice-report.json", 8
    )
    assert not (auto and "never a credential" in reason)


# --- Telegram token gate KNOWN_COMPROMISED rule (2026-08-14) ----------------
#
# Context: `scripts/lint_telegram_tokens.py` refuses a Telegram bot token
# anywhere in the tree. It holds a dict mapping the 16-hex truncated sha256 of
# tokens known to be BURNED to a human-readable note, so that a
# re-introduction is NAMED ("this is the @Balizerobot token") instead of
# merely flagged. detect-secrets reads that key as a "Hex High Entropy
# String" and made the gate red on the PR that introduced it.
#
# The hash is one-way; the token itself is deliberately absent from the file.
# This is a PRODUCTION script under scripts/, so the rule is content-keyed and
# not path-keyed: a path rule would blanket-approve any future finding in it.
# Guilt reads the real line off disk through classify(), so this test fails if
# the dict is renamed, reshaped, or the rule removed — not merely if someone
# edits a string literal here.

LINT_TELEGRAM_TOKENS = "scripts/lint_telegram_tokens.py"


def _telegram_rule():
    """Locate the rule by what it MATCHES, not by a positional index that
    silently shifts when someone inserts a rule above it."""
    for path_pat, content_pat, reason in CONTENT_KEYED_RULES:
        if path_pat.search(LINT_TELEGRAM_TOKENS):
            return path_pat, content_pat, reason
    raise AssertionError("no CONTENT_KEYED rule covers the Telegram token gate")


def test_telegram_token_rule_registered_and_scoped_to_exactly_one_file() -> None:
    path_pat, _content_pat, reason = _telegram_rule()
    assert path_pat.search(LINT_TELEGRAM_TOKENS)
    assert not path_pat.search("scripts/lint_telegram_tokens.py.bak")
    assert not path_pat.search("scripts/tests/test_lint_telegram_tokens.py")
    assert "never key material" in reason


def test_guilt_the_known_compromised_fingerprint_line_is_approved() -> None:
    """The exact finding that made `Detect Secrets` red on PR #4163.

    Found by scanning the live file for the dict entry rather than pinning a
    line number: a hardcoded number would rot the moment anything above it
    moves, and would then pass by testing the wrong line.
    """
    _path_pat, content_pat, _reason = _telegram_rule()
    lines = open(LINT_TELEGRAM_TOKENS, encoding="utf-8").read().splitlines()
    hits = [i + 1 for i, ln in enumerate(lines) if content_pat.search(ln)]
    assert len(hits) == 1, f"expected exactly one KNOWN_COMPROMISED entry, got {hits}"
    auto, reason = classify(LINT_TELEGRAM_TOKENS, hits[0])
    assert auto, f"the burned-token fingerprint must be approved (got {reason!r})"
    assert "never key material" in reason


def test_innocence_a_live_token_as_dict_key_is_not_approved() -> None:
    """A Telegram token is `<digits>:AA<33>`, which cannot pass as a 16-hex
    key. Assembled from fragments so this test file is not itself a finding."""
    _path_pat, content_pat, _reason = _telegram_rule()
    body = "AA" + "Hn4Kd9Wq" + "2Zx7Lm1P" + "v6Rt3Yb8" + "Sc5Ug0Jf"
    assert content_pat.match(f'    "8295471667:{body}": "@Balizerobot",') is None


def test_innocence_hex_key_with_a_non_handle_value_is_not_approved() -> None:
    """The value must begin with the `@` of a bot handle. A 16-hex key mapped
    to an opaque string is some other writer's data and stays unaudited."""
    _path_pat, content_pat, _reason = _telegram_rule()
    assert content_pat.match('    "a54b897b432002bb": "' + "z" * 40 + '",') is None


def test_innocence_a_credential_elsewhere_in_the_same_file_is_not_approved() -> None:
    """Content-keyed, not path-keyed: this is a production script, so a secret
    added later on an unrelated line must still stop the gate."""
    _path_pat, content_pat, _reason = _telegram_rule()
    assert content_pat.match('    api_key = "ghp_' + "y" * 36 + '"') is None


# --- traffic-source fail-closed live-proof identity anchors (2026-08-15) ---

TRAFFIC_SOURCE_LIVE_PROOF = (
    "research/visa/2026-08-15-traffic-source-fail-closed-live-proof.json"
)
TRAFFIC_SOURCE_CI_FINDING_LINES = [27, 33, 46, 67, 76, 85]


def _traffic_source_live_proof_rule():
    """Find by covered entity, never a positional list index."""
    matches = [
        rule
        for rule in CONTENT_KEYED_RULES
        if rule[0].search(TRAFFIC_SOURCE_LIVE_PROOF)
    ]
    assert len(matches) == 1
    return matches[0]


def test_traffic_source_live_proof_rule_is_exact_path_scoped() -> None:
    path_pat, _content_pat, reason = _traffic_source_live_proof_rule()
    assert path_pat.search(TRAFFIC_SOURCE_LIVE_PROOF)
    assert not path_pat.search(f"{TRAFFIC_SOURCE_LIVE_PROOF}.bak")
    assert not path_pat.search(
        "research/visa/2026-08-16-traffic-source-fail-closed-live-proof.json"
    )
    assert "never bearer material" in reason


def test_guilt_traffic_source_ci_findings_are_auto_approved() -> None:
    """The exact six unaudited findings emitted by CI run 31859642168."""
    for line_number in TRAFFIC_SOURCE_CI_FINDING_LINES:
        auto, reason = classify(TRAFFIC_SOURCE_LIVE_PROOF, line_number)
        assert auto, f"line {line_number} should be approved (got {reason!r})"


def test_guilt_traffic_source_ci_residue_is_fully_triaged() -> None:
    baseline = {
        "results": {
            TRAFFIC_SOURCE_LIVE_PROOF: [
                {"line_number": line_number, "type": "Hex High Entropy String"}
                for line_number in TRAFFIC_SOURCE_CI_FINDING_LINES
            ]
        }
    }
    updated, stats, residue = triage(baseline, apply=True)
    assert stats == {
        "auto_approved": 6,
        "hard_blocked": 0,
        "no_rule": 0,
        "total": 6,
    }
    assert residue == []
    assert all(
        hit["is_secret"] is False
        for hit in updated["results"][TRAFFIC_SOURCE_LIVE_PROOF]
    )


def test_guilt_every_declared_identity_anchor_shape_is_covered() -> None:
    """Also cover duplicate values that detect-secrets de-duplicates today."""
    _path_pat, content_pat, _reason = _traffic_source_live_proof_rule()
    lines = Path(TRAFFIC_SOURCE_LIVE_PROOF).read_text(encoding="utf-8").splitlines()
    matching_lines = [line for line in lines if content_pat.search(line)]
    matching_keys = {
        line.strip().split("\":", 1)[0].lstrip('"') for line in matching_lines
    }
    assert matching_keys == {
        "api_machine",
        "document_sha256",
        "expected_merge_sha",
        "head_sha",
        "idempotency_key_sha256",
        "instance",
        "payload_sha256",
        "traffic_source_parameter_sha256",
    }


def test_innocence_traffic_source_wrong_key_same_hash_shape_is_not_approved() -> None:
    _path_pat, content_pat, _reason = _traffic_source_live_proof_rule()
    assert content_pat.match('  "api_key_sha256": "' + "a" * 64 + '",') is None


def test_innocence_traffic_source_wrong_widths_are_not_approved() -> None:
    _path_pat, content_pat, _reason = _traffic_source_live_proof_rule()
    assert content_pat.match('  "head_sha": "' + "a" * 64 + '",') is None
    assert content_pat.match('  "api_machine": "' + "a" * 16 + '",') is None


def test_innocence_traffic_source_ride_along_is_not_approved() -> None:
    _path_pat, content_pat, _reason = _traffic_source_live_proof_rule()
    compound = (
        '  "payload_sha256": "'
        + "a" * 64
        + '", "api_key": "ghp_'
        + "y" * 36
        + '"'
    )
    assert content_pat.match(compound) is None


# --- fold_pack_seq10.py seq-9 chain anchor rule (2026-08-19) ----------------
#
# Context (PR #4350): CI's Detect Secrets gate flagged
# apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq10.py:99 as an
# unaudited "Hex High Entropy String" — _EXPECTED_SEQ9_PAYLOAD_SHA256, the
# content-derived sha256 of the PUBLIC signed seq-9 RulePack payload (same
# value class as the contracts/packs/rulepack-*.json rule in
# AUTO_APPROVE_RULES: hashes of public legal documents, never credentials).
# The fold script pins it so the seq-10 chain link is triple-derived at run
# time (declared == anchor == recomputed from the seq-9 source bytes) and any
# mismatch aborts the fold.
#
# Content-keyed and pinned to the EXACT anchor value, not a hex shape: this
# is production code with an open surface for future edits — a real
# credential pasted anywhere else in the file (or even another 64-hex value
# on this line) stays flagged. The approved line is the bare
# continuation-string line of the parenthesized assignment, end-anchored.

FOLD_PACK_SEQ10 = "apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq10.py"
FOLD_PACK_SEQ10_ANCHOR = (
    "47feff8246c608c7c6085ffdac776fdc020bb56688d5f35a0a3e685eb40f271e"
)


def test_fold_seq10_rule_registered_and_scoped_to_exactly_one_file() -> None:
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[9]
    assert path_pat.search(FOLD_PACK_SEQ10)
    assert not path_pat.search(
        "apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py"
    )
    assert not path_pat.search(
        "apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq11.py"
    )
    assert not path_pat.search("scripts/fold_pack_seq10.py")
    assert "credential" in reason


def test_guilt_fold_seq10_real_finding_approved() -> None:
    """The exact real line 99 in the fold script must be approved — read live
    off disk, so this fails if the file and rule ever drift, not merely if
    someone edits a string literal in this test."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[9]
    lines = Path(FOLD_PACK_SEQ10).read_text(encoding="utf-8").splitlines()
    real_line = lines[98]  # line 99, 1-indexed
    assert real_line == f'    "{FOLD_PACK_SEQ10_ANCHOR}"'
    assert content_pat.match(real_line), f"should be approved: {real_line!r}"


def test_innocence_fold_seq10_other_hex_value_not_approved() -> None:
    """A DIFFERENT 64-hex bare string line must not be approved — proves the
    rule is pinned to the exact anchor value, not merely to the shape."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[9]
    other_hex_line = '    "' + "a" * 64 + '"'
    assert content_pat.match(other_hex_line) is None


def test_innocence_fold_seq10_uppercase_not_approved() -> None:
    """The same value uppercased must not be approved — the anchor is
    lowercase hex, matching hashlib.hexdigest's own output."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[9]
    uppercase_line = f'    "{FOLD_PACK_SEQ10_ANCHOR.upper()}"'
    assert content_pat.match(uppercase_line) is None


def test_innocence_fold_seq10_ride_along_statement_not_approved() -> None:
    """The value followed by a second statement or token on the same line
    must not launder the ride-along — end-anchored, same discipline as every
    other rule in this list."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[9]
    for compound in (
        f'    "{FOLD_PACK_SEQ10_ANCHOR}"; import os',
        f'    "{FOLD_PACK_SEQ10_ANCHOR}" "second_token"',
    ):
        assert content_pat.match(compound) is None, f"must NOT be approved: {compound!r}"


def test_innocence_fold_seq10_keyed_assignment_not_approved() -> None:
    """A JSON-style keyed line carrying the same value must not be approved —
    the rule approves only the bare continuation-string shape of the
    parenthesized assignment, never a `"key": "value"` shape."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[9]
    keyed_line = f'    "payload_sha256": "{FOLD_PACK_SEQ10_ANCHOR}",'
    assert content_pat.match(keyed_line) is None


# ---------------------------------------------------------------------------
# Rule 11: fold_pack_seq11.py — the seq-10 chain anchor, pinned to the exact
# public payload sha256 of the signed seq-10 RulePack. Same value class and
# same discipline as rule 10 above (the seq-9 anchor in fold_pack_seq10.py):
# the fold script pins the PRIOR pack's payload hash so the chain link is
# triple-derived at run time (declared == anchor == recomputed) and any
# mismatch aborts the fold.
#
# Content-keyed and pinned to the EXACT anchor value, not a hex shape: this
# is production code with an open surface for future edits — a real
# credential pasted anywhere else in the file (or even another 64-hex value
# on this line) stays flagged. The approved line is the bare
# continuation-string line of the parenthesized assignment, end-anchored.

FOLD_PACK_SEQ11 = "apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq11.py"
FOLD_PACK_SEQ11_ANCHOR = (
    "188442baee0af899e464a696b883d2158e6e362c29d75b61eec5769ba24b9aac"
)


def test_fold_seq11_rule_registered_and_scoped_to_exactly_one_file() -> None:
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[10]
    assert path_pat.search(FOLD_PACK_SEQ11)
    assert not path_pat.search(FOLD_PACK_SEQ10)
    assert not path_pat.search(
        "apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py"
    )
    assert not path_pat.search("scripts/fold_pack_seq11.py")
    assert "credential" in reason


def test_guilt_fold_seq11_real_finding_approved() -> None:
    """The exact real line 93 in the fold script must be approved — read live
    off disk, so this fails if the file and rule ever drift, not merely if
    someone edits a string literal in this test."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[10]
    lines = Path(FOLD_PACK_SEQ11).read_text(encoding="utf-8").splitlines()
    real_line = lines[92]  # line 93, 1-indexed
    assert real_line == f'    "{FOLD_PACK_SEQ11_ANCHOR}"'
    assert content_pat.match(real_line), f"should be approved: {real_line!r}"


def test_innocence_fold_seq11_other_hex_value_not_approved() -> None:
    """A DIFFERENT 64-hex bare string line must not be approved — proves the
    rule is pinned to the exact anchor value, not merely to the shape.
    The seq-9 anchor (rule 10's value) doubles as the nearest-neighbour
    innocent: a REAL sibling anchor must still not launder through THIS rule."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[10]
    other_hex_line = '    "' + "a" * 64 + '"'
    assert content_pat.match(other_hex_line) is None
    sibling_anchor_line = f'    "{FOLD_PACK_SEQ10_ANCHOR}"'
    assert content_pat.match(sibling_anchor_line) is None


def test_innocence_fold_seq11_uppercase_not_approved() -> None:
    """The same value uppercased must not be approved — the anchor is
    lowercase hex, matching hashlib.hexdigest's own output."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[10]
    uppercase_line = f'    "{FOLD_PACK_SEQ11_ANCHOR.upper()}"'
    assert content_pat.match(uppercase_line) is None


def test_innocence_fold_seq11_ride_along_statement_not_approved() -> None:
    """The value followed by a second statement or token on the same line
    must not launder the ride-along — end-anchored, same discipline as every
    other rule in this list."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[10]
    for compound in (
        f'    "{FOLD_PACK_SEQ11_ANCHOR}"; import os',
        f'    "{FOLD_PACK_SEQ11_ANCHOR}" "second_token"',
    ):
        assert content_pat.match(compound) is None, f"must NOT be approved: {compound!r}"


def test_innocence_fold_seq11_keyed_assignment_not_approved() -> None:
    """A JSON-style keyed line carrying the same value must not be approved —
    the rule approves only the bare continuation-string shape of the
    parenthesized assignment, never a `"key": "value"` shape."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[10]
    keyed_line = f'    "payload_sha256": "{FOLD_PACK_SEQ11_ANCHOR}",'
    assert content_pat.match(keyed_line) is None


# ---------------------------------------------------------------------------
# fold_pack_seq12.py — seq-11 chain anchor exact-value pin (CONTENT_KEYED_RULES[11])
# ---------------------------------------------------------------------------
# Same class and discipline as the seq-10/seq-11 fold rules directly above:
# the pinned value is the sha256 of the PUBLIC signed seq-11 RulePack payload,
# and the rule approves ONLY the bare continuation-string line of the
# parenthesized assignment, end-anchored, in exactly one file.

FOLD_PACK_SEQ12 = "apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq12.py"
FOLD_PACK_SEQ12_ANCHOR = (
    "836acc511bcadd41c28284e7f00bd8be27c6109ebcc5536f7053c3f61eaa2865"
)


def test_fold_seq12_rule_registered_and_scoped_to_exactly_one_file() -> None:
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[11]
    assert path_pat.search(FOLD_PACK_SEQ12)
    assert not path_pat.search(FOLD_PACK_SEQ11)
    assert not path_pat.search(FOLD_PACK_SEQ10)
    assert not path_pat.search(
        "apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py"
    )
    assert not path_pat.search("scripts/fold_pack_seq12.py")
    assert "credential" in reason


def test_guilt_fold_seq12_real_finding_approved() -> None:
    """The exact real line 89 in the fold script must be approved — read live
    off disk, so this fails if the file and rule ever drift, not merely if
    someone edits a string literal in this test."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[11]
    lines = Path(FOLD_PACK_SEQ12).read_text(encoding="utf-8").splitlines()
    real_line = lines[88]  # line 89, 1-indexed
    assert real_line == f'    "{FOLD_PACK_SEQ12_ANCHOR}"'
    assert content_pat.match(real_line), f"should be approved: {real_line!r}"


def test_innocence_fold_seq12_other_hex_value_not_approved() -> None:
    """A DIFFERENT 64-hex bare string line must not be approved — proves the
    rule is pinned to the exact anchor value, not merely to the shape.
    The seq-10 anchor (rule 11's value) doubles as the nearest-neighbour
    innocent: a REAL sibling anchor must still not launder through THIS rule."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[11]
    other_hex_line = '    "' + "a" * 64 + '"'
    assert content_pat.match(other_hex_line) is None
    sibling_anchor_line = f'    "{FOLD_PACK_SEQ11_ANCHOR}"'
    assert content_pat.match(sibling_anchor_line) is None


def test_innocence_fold_seq12_uppercase_not_approved() -> None:
    """The same value uppercased must not be approved — the anchor is
    lowercase hex, matching hashlib.hexdigest's own output."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[11]
    uppercase_line = f'    "{FOLD_PACK_SEQ12_ANCHOR.upper()}"'
    assert content_pat.match(uppercase_line) is None


def test_innocence_fold_seq12_ride_along_statement_not_approved() -> None:
    """The value followed by a second statement or token on the same line
    must not launder the ride-along — end-anchored, same discipline as every
    other rule in this list."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[11]
    for compound in (
        f'    "{FOLD_PACK_SEQ12_ANCHOR}"; import os',
        f'    "{FOLD_PACK_SEQ12_ANCHOR}" "second_token"',
    ):
        assert content_pat.match(compound) is None, f"must NOT be approved: {compound!r}"


def test_innocence_fold_seq12_keyed_assignment_not_approved() -> None:
    """A JSON-style keyed line carrying the same value must not be approved —
    the rule approves only the bare continuation-string shape of the
    parenthesized assignment, never a `"key": "value"` shape."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[11]
    keyed_line = f'    "payload_sha256": "{FOLD_PACK_SEQ12_ANCHOR}",'
    assert content_pat.match(keyed_line) is None


# ---------------------------------------------------------------------------
# fold_pack_seq13_source.py — seq-12 chain anchor exact-value pin (2026-08-23, #4667)
# ---------------------------------------------------------------------------
# The seq-13 JOIN fold. Same value as fold_pack_seq13_rules.py's own rule
# above (both chain off seq-12), in a DIFFERENT file — pins the anchor to
# the exact value, in exactly this one path. Looked up by content (a
# substring unique to its reason once file-qualified), not by list
# position, per the 2026-08-23 policy note above: a new rule may be
# inserted anywhere in CONTENT_KEYED_RULES without breaking a registration
# test — this entry is itself an example, inserted between the seq12 and
# p2b_score.json rules without touching any positional test in this file.

FOLD_PACK_SEQ13_SOURCE = (
    "apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq13_source.py"
)
FOLD_PACK_SEQ13_SOURCE_ANCHOR = (
    "ff43d55e79e833a91820c4b68dd9ffdd086e7969b3b3a44dbd80747aa451406d"
)


def test_fold_seq13_source_rule_registered_and_scoped_to_exactly_one_file() -> None:
    path_pat, _content_pat, reason = _find_content_keyed_rule(
        "fold_pack_seq13_source.py: seq-12 chain anchor"
    )
    assert path_pat.search(FOLD_PACK_SEQ13_SOURCE)
    assert not path_pat.search(FOLD_PACK_SEQ12)
    assert not path_pat.search(
        "apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq13_rules.py"
    )
    assert not path_pat.search(
        "scripts/detect_secrets_auto_triage.py"
    )
    assert "credential" in reason


def test_guilt_fold_seq13_source_real_finding_approved() -> None:
    """The exact real line 218 in the fold script must be approved — read
    live off disk, so this fails if the file and rule ever drift, not
    merely if someone edits a string literal in this test."""
    _path_pat, content_pat, _reason = _find_content_keyed_rule(
        "fold_pack_seq13_source.py: seq-12 chain anchor"
    )
    lines = Path(FOLD_PACK_SEQ13_SOURCE).read_text(encoding="utf-8").splitlines()
    real_line = lines[217]  # line 218, 1-indexed
    assert real_line == f'    "{FOLD_PACK_SEQ13_SOURCE_ANCHOR}"'
    assert content_pat.match(real_line), f"should be approved: {real_line!r}"


def test_innocence_fold_seq13_source_other_hex_value_not_approved() -> None:
    """A DIFFERENT 64-hex bare string line must not be approved — proves the
    rule is pinned to the exact anchor value, not merely to the shape."""
    _path_pat, content_pat, _reason = _find_content_keyed_rule(
        "fold_pack_seq13_source.py: seq-12 chain anchor"
    )
    other_hex_line = '    "' + "a" * 64 + '"'
    assert content_pat.match(other_hex_line) is None


def test_innocence_fold_seq13_source_uppercase_not_approved() -> None:
    """The same value uppercased must not be approved — the anchor is
    lowercase hex, matching hashlib.hexdigest's own output."""
    _path_pat, content_pat, _reason = _find_content_keyed_rule(
        "fold_pack_seq13_source.py: seq-12 chain anchor"
    )
    uppercase_line = f'    "{FOLD_PACK_SEQ13_SOURCE_ANCHOR.upper()}"'
    assert content_pat.match(uppercase_line) is None


def test_innocence_fold_seq13_source_ride_along_statement_not_approved() -> None:
    """The value followed by a second statement or token on the same line
    must not launder the ride-along — end-anchored, same discipline as every
    other rule in this list."""
    _path_pat, content_pat, _reason = _find_content_keyed_rule(
        "fold_pack_seq13_source.py: seq-12 chain anchor"
    )
    for compound in (
        f'    "{FOLD_PACK_SEQ13_SOURCE_ANCHOR}"; import os',
        f'    "{FOLD_PACK_SEQ13_SOURCE_ANCHOR}" "second_token"',
    ):
        assert content_pat.match(compound) is None, f"must NOT be approved: {compound!r}"


def test_innocence_fold_seq13_source_keyed_assignment_not_approved() -> None:
    """A JSON-style keyed line carrying the same value must not be approved —
    the rule approves only the bare continuation-string shape of the
    parenthesized assignment, never a `"key": "value"` shape."""
    _path_pat, content_pat, _reason = _find_content_keyed_rule(
        "fold_pack_seq13_source.py: seq-12 chain anchor"
    )
    keyed_line = f'    "payload_sha256": "{FOLD_PACK_SEQ13_SOURCE_ANCHOR}",'
    assert content_pat.match(keyed_line) is None


def test_fold_seq13_source_rule_does_not_launder_via_seq13_rules_path() -> None:
    """The two seq-13 chain-anchor rules share the identical anchor VALUE
    (both fold scripts chain off seq-12) but must stay path-scoped: this
    rule's path pattern must reject fold_pack_seq13_rules.py even though
    the content pattern alone would match a line copy-pasted from it."""
    path_pat, content_pat, _reason = _find_content_keyed_rule(
        "fold_pack_seq13_source.py: seq-12 chain anchor"
    )
    real_line = f'    "{FOLD_PACK_SEQ13_SOURCE_ANCHOR}"'
    assert content_pat.match(real_line)  # content alone matches...
    assert not path_pat.search(  # ...but path must not, for the sibling file
        "apps/backend-rag/backend/scripts/visa_engine/fold_pack_seq13_rules.py"
    )


GOOGLE_OAUTH_LINT = "scripts/lint_google_oauth_credentials.py"


def test_google_oauth_known_compromised_rule_registered() -> None:
    """Looks its rule up by content (a substring unique to its reason), not
    by list position (2026-08-23 - previously CONTENT_KEYED_RULES[13], the
    exact positional coupling s13-rules' mid-list insert broke elsewhere in
    this file the same day). Approves only the 16-hex dict-key lines
    carrying the exact 2026-08-21 publication marker, only in the OAuth
    guard's own file."""
    path_pat, content_pat, reason = _find_content_keyed_rule(
        "Google OAuth gate: KNOWN_COMPROMISED"
    )
    assert path_pat.search(GOOGLE_OAUTH_LINT)
    assert not path_pat.search("scripts/lint_telegram_tokens.py")
    assert "never key material" in reason
    good = '    "83f24d5051c7f127": "GOCSPX client secret published in 9 scripts until 2026-08-21",'
    assert content_pat.match(good)
    # Same hex-key shape without the publication marker stays flagged.
    other = '    "83f24d5051c7f127": "some unrelated note",'
    assert content_pat.match(other) is None


def test_google_oauth_selftest_fragment_rule_registered() -> None:
    """Same content-based lookup as the test above, not by list position."""
    path_pat, content_pat, _reason = _find_content_keyed_rule(
        "OAuth guard selftest fixture fragment"
    )
    assert path_pat.search(GOOGLE_OAUTH_LINT)
    frag = '    ref_body = "0c" + "defghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-abcd"'
    assert content_pat.match(frag)
    # A bare 64-char assignment without the ref_body assembly shape stays flagged.
    bare = '    token = "defghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-abcd"'
    assert content_pat.match(bare) is None
