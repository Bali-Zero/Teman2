"""hop6 of intel_lake_e2e_probe.py — NotebookLM sandbox fixture prune.

Pure selection (guilt + innocence), the orchestration around it driven by a
fake runner (no network, no real `nlm`), and a parity pin between the probe's
live notebook id and the pusher's remap target for the probe's legacy id.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PROBE_PATH = _REPO_ROOT / "scripts" / "probes" / "intel_lake_e2e_probe.py"
_PUSHER_PATH = _REPO_ROOT / "scripts" / "intel-lake-nb-pusher-a2" / "intel-lake-nb-pusher-standalone.py"

NONCE = "0123456789ab"
LIVE_NB = "7e6ae978-136c-4c96-bed5-9fab6f39176f"


def _sid(n: int) -> str:
    return f"{n:08x}-0000-4000-8000-{n:012x}"


@pytest.fixture(scope="module")
def probe():
    spec = importlib.util.spec_from_file_location("intel_lake_e2e_probe_hop6", _PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["intel_lake_e2e_probe_hop6"] = module
    spec.loader.exec_module(module)
    return module


def _src(n: int, title=None, url=None) -> dict:
    return {"id": _sid(n), "status": 2, "title": title, "type": "generated_text", "url": url}


def _fixture_title(n: int) -> dict:
    return _src(n, title=f"[PROBE-SANDBOX] e2e fixture {n:012x}")


class FakeNlm:
    """Records argv of every call; `sources` is what `source list` returns."""

    def __init__(self, sources, list_rc=0, list_stdout=None, delete_rc=0, raises=None):
        self.sources = sources
        self.list_rc = list_rc
        self.list_stdout = list_stdout
        self.delete_rc = delete_rc
        self.raises = raises
        self.calls: list[list[str]] = []
        self.timeouts: list[object] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.timeouts.append(kwargs.get("timeout"))
        verb = argv[2]
        if self.raises and verb == "list":
            raise self.raises
        if verb == "list":
            out = self.list_stdout if self.list_stdout is not None else json.dumps(self.sources)
            return SimpleNamespace(returncode=self.list_rc, stdout=out, stderr="")
        return SimpleNamespace(returncode=self.delete_rc, stdout="", stderr="")

    @property
    def deletes(self):
        return [c for c in self.calls if c[2] == "delete"]

    @property
    def deleted_ids(self):
        return [i for c in self.deletes for i in c[3:] if re.fullmatch(r"[0-9a-f-]{36}", i)]


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.delenv("INTEL_LAKE_PROBE_NLM_PRUNE", raising=False)
    monkeypatch.delenv("INTEL_LAKE_PROBE_NLM_RESIDUE_MAX", raising=False)
    monkeypatch.delenv("INTEL_LAKE_PROBE_NLM_UNKNOWN_MAX", raising=False)
    monkeypatch.setenv("INTEL_LAKE_PROBE_HOP6_STATE", str(tmp_path / "hop6-state.json"))


@pytest.fixture
def nlm_present(probe, monkeypatch):
    monkeypatch.setattr(probe, "_resolve_nlm", lambda: "/fake/nlm")


class TestSelectionInnocence:
    @pytest.mark.parametrize(
        "title",
        [
            f"prefix [PROBE-SANDBOX] e2e fixture {NONCE}",
            f"[PROBE-SANDBOX] e2e fixture {NONCE} suffix",
            f"[PROBE-SANDBOX] e2e fixture {NONCE}\n",
            f"[PROBE-SANDBOX] e2e fixture {NONCE[:-1]}",
            f"[PROBE-SANDBOX] e2e fixture {NONCE}0",
            f"[PROBE-SANDBOX] e2e fixture {NONCE.upper()}",
            "[PROBE-SANDBOX] e2e fixture zzzzzzzzzzzz",
            "nlm_push_zzzzzzzz.txt",
            "nlm_push_0123abcd.txt.bak",
            "my_nlm_push_0123abcd.txt",
            "nlm_push_0123abc.txt",
            "Permenaker 2026 amendment on foreign worker permits",
            "",
        ],
    )
    def test_title_not_selected(self, probe, title):
        assert probe.select_fixture_ids([_src(1, title=title)]) == []

    @pytest.mark.parametrize(
        "url",
        [
            f"https://probe-sandbox.example.test.evil.com/probe-{NONCE}",
            f"https://evil.probe-sandbox.example.test/probe-{NONCE}",
            f"https://evil.com/?u=https://probe-sandbox.example.test/probe-{NONCE}",
            f"https://evil.com/#https://probe-sandbox.example.test/probe-{NONCE}",
            f"https://probe-sandbox.example.test/probe-{NONCE}?x=1",
            f"https://probe-sandbox.example.test/probe-{NONCE}#frag",
            f"https://probe-sandbox.example.test/probe-{NONCE}/extra",
            f"https://probe-sandbox.example.test/other-{NONCE}",
            f"https://probe-sandbox.example.test/probe-{NONCE[:-1]}",
            f"https://probe-sandbox.example.test:8443/probe-{NONCE}",
            f"https://user@probe-sandbox.example.test/probe-{NONCE}",
            f"http://probe-sandbox.example.test/probe-{NONCE}",
            "https://www.example.com/article",
        ],
    )
    def test_url_not_selected(self, probe, url):
        assert probe.select_fixture_ids([_src(1, url=url)]) == []

    def test_missing_fields_and_junk_entries_not_selected(self, probe):
        junk = [
            _src(1),
            {"id": _sid(2)},
            {"id": _sid(3), "title": None, "url": None},
            {"id": _sid(4), "title": 7, "url": 7},
            "not-a-dict",
            None,
            ["x"],
        ]
        assert probe.select_fixture_ids(junk) == []

    def test_fixture_shape_without_a_valid_id_not_selected(self, probe):
        bad = [
            {"id": None, "title": f"[PROBE-SANDBOX] e2e fixture {NONCE}"},
            {"id": "--confirm", "title": f"[PROBE-SANDBOX] e2e fixture {NONCE}"},
            {"title": f"[PROBE-SANDBOX] e2e fixture {NONCE}"},
        ]
        assert probe.select_fixture_ids(bad) == []


class TestSelectionGuilt:
    def test_each_shape_is_selected(self, probe):
        sources = [
            _src(1, title=f"[PROBE-SANDBOX] e2e fixture {NONCE}"),
            _src(2, url=f"https://probe-sandbox.example.test/probe-{NONCE}"),
            _src(3, title="nlm_push_0123abcd.txt"),
            _src(4, title="Some real article"),
        ]
        assert probe.select_fixture_ids(sources) == [_sid(1), _sid(2), _sid(3)]

    def test_title_is_the_real_generator_output(self, probe):
        fx = probe.ProbeFixture.generate()
        got = probe.select_fixture_ids([_src(1, title=fx.title), _src(2, url=fx.canonical_url)])
        assert got == [_sid(1), _sid(2)]


class TestHop6:
    def test_each_shape_reaches_the_delete_call(self, probe, nlm_present):
        fake = FakeNlm(
            [
                _src(1, title=f"[PROBE-SANDBOX] e2e fixture {NONCE}"),
                _src(2, url=f"https://probe-sandbox.example.test/probe-{NONCE}"),
                _src(3, title="nlm_push_0123abcd.txt"),
                _src(4, title="Keep me"),
            ]
        )
        probe.hop6_prune_nlm_fixtures(runner=fake)
        assert fake.deleted_ids == [_sid(1), _sid(2), _sid(3)]

    def test_list_targets_the_live_notebook_constant(self, probe, nlm_present):
        fake = FakeNlm([])
        probe.hop6_prune_nlm_fixtures(runner=fake)
        assert fake.calls[0][:4] == ["/fake/nlm", "source", "list", probe.NB_SANDBOX_LIVE_UUID]
        assert probe.NB_SANDBOX_LIVE_UUID == LIVE_NB
        assert "--json" in fake.calls[0]

    def test_profile_flag_on_both_verbs(self, probe, nlm_present):
        fake = FakeNlm([_fixture_title(1)])
        probe.hop6_prune_nlm_fixtures(runner=fake)
        assert [c[-2:] for c in fake.calls] == [["--profile", "default"]] * 2
        assert "--confirm" in fake.deletes[0]

    def test_every_call_has_a_timeout(self, probe, nlm_present):
        fake = FakeNlm([_fixture_title(1)])
        probe.hop6_prune_nlm_fixtures(runner=fake)
        assert fake.timeouts and all(isinstance(t, (int, float)) and t > 0 for t in fake.timeouts)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"list_rc": 1},
            {"list_stdout": "not json"},
            {"list_stdout": '{"sources": []}'},
            {"list_stdout": "null"},
            {"raises": subprocess.TimeoutExpired(cmd="nlm", timeout=1)},
            {"raises": OSError("boom")},
        ],
    )
    def test_list_failure_deletes_nothing_and_passes(self, probe, nlm_present, caplog, kwargs):
        fake = FakeNlm([_fixture_title(1)], **kwargs)
        with caplog.at_level("WARNING", logger="intel-lake.probe"):
            probe.hop6_prune_nlm_fixtures(runner=fake)
        assert fake.deletes == []
        assert "hop6 WARN" in caplog.text

    def test_binary_absent_skips(self, probe, monkeypatch, caplog):
        monkeypatch.setattr(probe, "_resolve_nlm", lambda: None)
        fake = FakeNlm([_fixture_title(1)])
        with caplog.at_level("WARNING", logger="intel-lake.probe"):
            probe.hop6_prune_nlm_fixtures(runner=fake)
        assert fake.calls == []
        assert "hop6 SKIP" in caplog.text

    def test_resolve_prefers_path_then_home_fallback(self, probe, monkeypatch, tmp_path):
        monkeypatch.setattr(probe.shutil, "which", lambda name: "/on/path/nlm")
        assert probe._resolve_nlm() == "/on/path/nlm"
        monkeypatch.setattr(probe.shutil, "which", lambda name: None)
        monkeypatch.setattr(probe.Path, "home", classmethod(lambda cls: tmp_path))
        assert probe._resolve_nlm() is None
        (tmp_path / ".local" / "bin").mkdir(parents=True)
        (tmp_path / ".local" / "bin" / "nlm").write_text("")
        assert probe._resolve_nlm() == str(tmp_path / ".local" / "bin" / "nlm")

    def test_kill_switch(self, probe, nlm_present, monkeypatch, caplog):
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_PRUNE", "0")
        fake = FakeNlm([_fixture_title(1)])
        with caplog.at_level("INFO", logger="intel-lake.probe"):
            probe.hop6_prune_nlm_fixtures(runner=fake)
        assert fake.calls == []
        assert "hop6 SKIP" in caplog.text

    def test_batches_are_at_most_20(self, probe, nlm_present):
        fake = FakeNlm([_fixture_title(i) for i in range(1, 46)])
        probe.hop6_prune_nlm_fixtures(runner=fake)
        sizes = [len([a for a in c[3:] if re.fullmatch(r"[0-9a-f-]{36}", a)]) for c in fake.deletes]
        assert sizes == [20, 20, 5]

    def test_per_run_cap_is_60(self, probe, nlm_present, monkeypatch):
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_RESIDUE_MAX", "1000")
        fake = FakeNlm([_fixture_title(i) for i in range(1, 91)])
        probe.hop6_prune_nlm_fixtures(runner=fake)
        assert len(fake.deleted_ids) == 60
        assert len(set(fake.deleted_ids)) == 60

    def test_ids_come_only_from_this_listing(self, probe, nlm_present):
        fake = FakeNlm([_fixture_title(1), _src(2, title="Keep me")])
        probe.hop6_prune_nlm_fixtures(runner=fake)
        assert fake.deleted_ids == [_sid(1)]

    def test_summary_line_counts_and_hides_other_titles(self, probe, nlm_present, caplog):
        fake = FakeNlm([_fixture_title(1), _fixture_title(2), _src(3, title="Secret client memo")])
        with caplog.at_level("INFO", logger="intel-lake.probe"):
            probe.hop6_prune_nlm_fixtures(runner=fake)
        assert "hop6 PASS — pruned=2 residue=0 kept_other=1" in caplog.text
        assert "Secret client memo" not in caplog.text

    def test_failed_delete_below_threshold_warns_and_passes(self, probe, nlm_present, caplog):
        fake = FakeNlm([_fixture_title(1), _fixture_title(2)], delete_rc=1)
        with caplog.at_level("INFO", logger="intel-lake.probe"):
            probe.hop6_prune_nlm_fixtures(runner=fake)
        assert "hop6 WARN" in caplog.text
        assert "pruned=0 residue=2" in caplog.text

    def test_residue_at_threshold_raises(self, probe, nlm_present, monkeypatch):
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_RESIDUE_MAX", "3")
        fake = FakeNlm([_fixture_title(i) for i in range(1, 4)], delete_rc=1)
        with pytest.raises(AssertionError, match="hop6"):
            probe.hop6_prune_nlm_fixtures(runner=fake)

    def test_residue_just_below_threshold_does_not_raise(self, probe, nlm_present, monkeypatch, caplog):
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_RESIDUE_MAX", "4")
        fake = FakeNlm([_fixture_title(i) for i in range(1, 4)], delete_rc=1)
        with caplog.at_level("INFO", logger="intel-lake.probe"):
            probe.hop6_prune_nlm_fixtures(runner=fake)
        assert "residue=3" in caplog.text

    def test_default_threshold_is_100(self, probe, nlm_present):
        fake = FakeNlm([_fixture_title(i) for i in range(1, 101)], delete_rc=1)
        with pytest.raises(AssertionError):
            probe.hop6_prune_nlm_fixtures(runner=fake)
        fake = FakeNlm([_fixture_title(i) for i in range(1, 100)], delete_rc=1)
        probe.hop6_prune_nlm_fixtures(runner=fake)
        assert len(fake.deletes) == 3


def test_live_notebook_constant_matches_pusher_remap(probe):
    """NB_SANDBOX_LIVE_UUID must stay the pusher's remap target for the probe's legacy id."""
    text = _PUSHER_PATH.read_text()
    block = re.search(r"_NB_UUID_REMAP\s*=\s*\{(.*?)\n\}", text, re.S)
    assert block, "_NB_UUID_REMAP not found in the pusher"
    remap = dict(re.findall(r'"([0-9a-f-]{36})"\s*:\s*"([0-9a-f-]{36})"', block.group(1)))
    assert remap.get(probe.NB_SANDBOX_UUID) == probe.NB_SANDBOX_LIVE_UUID


def test_nlm_push_title_matches_any_run_by_design(probe):
    """The sandbox notebook is probe-only, so any nlm_push_<8hex>.txt in it is a fixture, this run's or not."""
    assert probe.select_fixture_ids([_src(1, title="nlm_push_deadbeef.txt")]) == [_sid(1)]


class TestOutcomeAndSummary:
    def test_verified_when_listed_and_nothing_left(self, probe, nlm_present):
        assert probe.hop6_prune_nlm_fixtures(runner=FakeNlm([_fixture_title(1)])) == ("verified", "")
        assert probe.hop6_prune_nlm_fixtures(runner=FakeNlm([])) == ("verified", "")

    def test_listing_failure_is_unverified(self, probe, nlm_present):
        assert probe.hop6_prune_nlm_fixtures(runner=FakeNlm([], list_rc=1)) == ("unverified", "list-rc=1")
        got = probe.hop6_prune_nlm_fixtures(runner=FakeNlm([], list_stdout="nope"))
        assert got[0] == "unverified"

    def test_binary_absent_is_unverified(self, probe, monkeypatch):
        monkeypatch.setattr(probe, "_resolve_nlm", lambda: None)
        assert probe.hop6_prune_nlm_fixtures(runner=FakeNlm([])) == ("unverified", "nlm-binary-absent")

    def test_failed_delete_is_unverified_with_residue(self, probe, nlm_present):
        fake = FakeNlm([_fixture_title(1), _fixture_title(2)], delete_rc=1)
        assert probe.hop6_prune_nlm_fixtures(runner=fake) == ("unverified", "residue=2")

    def test_kill_switch_is_skipped(self, probe, nlm_present, monkeypatch):
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_PRUNE", "0")
        assert probe.hop6_prune_nlm_fixtures(runner=FakeNlm([])) == ("skipped", "kill-switch")

    def test_summary_claims_six_hops_only_when_verified(self, probe):
        assert probe.final_summary(("verified", "")) == "PROBE PASS — all 6 hops verified, 0 contamination"
        unverified = probe.final_summary(("unverified", "list-rc=1"))
        assert unverified == "PROBE PASS — 5 pipeline hops verified, hop6 UNVERIFIED (list-rc=1)"
        assert "6 hops" not in unverified
        skipped = probe.final_summary(("skipped", "kill-switch"))
        assert skipped == "PROBE PASS — 5 pipeline hops verified, hop6 SKIPPED (kill-switch)"
        assert "6 hops" not in skipped


class TestConsecutiveUnknownCounter:
    def _count(self, probe) -> int:
        return probe._read_unknown_count()

    def _fail(self, probe):
        return probe.hop6_prune_nlm_fixtures(runner=FakeNlm([], list_rc=1))

    def test_increments_on_each_unreadable_listing(self, probe, nlm_present):
        for expected in (1, 2, 3):
            self._fail(probe)
            assert self._count(probe) == expected

    def test_resets_on_a_verified_run(self, probe, nlm_present):
        self._fail(probe)
        self._fail(probe)
        probe.hop6_prune_nlm_fixtures(runner=FakeNlm([_fixture_title(1)]))
        assert self._count(probe) == 0

    def test_resets_when_listed_even_if_delete_failed(self, probe, nlm_present):
        self._fail(probe)
        probe.hop6_prune_nlm_fixtures(runner=FakeNlm([_fixture_title(1)], delete_rc=1))
        assert self._count(probe) == 0

    def test_raises_at_the_default_of_8_not_before(self, probe, nlm_present):
        for _ in range(7):
            self._fail(probe)
        with pytest.raises(AssertionError, match="hop6"):
            self._fail(probe)

    def test_env_tunes_the_limit(self, probe, nlm_present, monkeypatch):
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_UNKNOWN_MAX", "2")
        self._fail(probe)
        with pytest.raises(AssertionError):
            self._fail(probe)

    def test_missing_binary_counts_as_unknown(self, probe, monkeypatch):
        monkeypatch.setattr(probe, "_resolve_nlm", lambda: None)
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_UNKNOWN_MAX", "2")
        probe.hop6_prune_nlm_fixtures(runner=FakeNlm([]))
        with pytest.raises(AssertionError):
            probe.hop6_prune_nlm_fixtures(runner=FakeNlm([]))

    def test_kill_switch_leaves_the_counter_alone(self, probe, nlm_present, monkeypatch):
        self._fail(probe)
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_PRUNE", "0")
        probe.hop6_prune_nlm_fixtures(runner=FakeNlm([]))
        assert self._count(probe) == 1

    @pytest.mark.parametrize("content", ["not json", "[]", '{"consecutive_unknown": "x"}', '{"consecutive_unknown": -3}', '{"consecutive_unknown": true}', ""])
    def test_corrupt_state_file_restarts_the_count(self, probe, nlm_present, content):
        probe._unknown_state_path().write_text(content)
        self._fail(probe)
        assert self._count(probe) == 1

    def test_missing_state_file_counts_from_zero(self, probe, nlm_present):
        assert not probe._unknown_state_path().exists()
        self._fail(probe)
        assert self._count(probe) == 1

    def test_unwritable_state_never_breaks_the_probe(self, probe, nlm_present, monkeypatch, tmp_path, caplog):
        blocker = tmp_path / "blocker"
        blocker.write_text("a file, so a child path cannot be created")
        monkeypatch.setenv("INTEL_LAKE_PROBE_HOP6_STATE", str(blocker / "state.json"))
        with caplog.at_level("WARNING", logger="intel-lake.probe"):
            assert self._fail(probe) == ("unverified", "list-rc=1")
        assert "state file not written" in caplog.text


class TestRunWiring:
    """run() must log what hop6 really did, with the DB hops stubbed out."""

    def _run(self, probe, monkeypatch, caplog, nlm_runner):
        async def noop(*a, **k):
            return None

        class Conn:
            async def close(self):
                return None

        async def connect(dsn):
            return Conn()

        async def hop1(*a, **k):
            return "item-1"

        async def hop3(*a, **k):
            return "nb-intel"

        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/x")
        monkeypatch.setenv("INTEL_LAKE_PRODUCER_TOKEN", "t")
        monkeypatch.setattr(probe.asyncpg, "connect", connect)
        monkeypatch.setattr(probe, "hop1_post_observation", hop1)
        monkeypatch.setattr(probe, "hop3_check_routing", hop3)
        for name in ("hop2_check_outbox", "hop2_5_set_sandbox_flag", "hop4_check_nb_push", "hop5_cleanup_verify"):
            monkeypatch.setattr(probe, name, noop)
        real = probe.hop6_prune_nlm_fixtures
        monkeypatch.setattr(probe, "hop6_prune_nlm_fixtures", lambda: real(runner=nlm_runner))
        monkeypatch.setattr(probe, "_resolve_nlm", lambda: "/fake/nlm")
        import asyncio

        with caplog.at_level("INFO", logger="intel-lake.probe"):
            rc = asyncio.run(probe.run(1))
        return rc, caplog.text

    def test_failed_listing_does_not_claim_six_hops(self, probe, monkeypatch, caplog):
        rc, text = self._run(probe, monkeypatch, caplog, FakeNlm([], list_rc=1))
        assert rc == 0
        assert "PROBE PASS — 5 pipeline hops verified, hop6 UNVERIFIED (list-rc=1)" in text
        assert "all 6 hops verified" not in text

    def test_clean_prune_claims_six_hops(self, probe, monkeypatch, caplog):
        rc, text = self._run(probe, monkeypatch, caplog, FakeNlm([_fixture_title(1)]))
        assert rc == 0
        assert "PROBE PASS — all 6 hops verified, 0 contamination" in text

    def test_unknown_limit_fails_the_probe(self, probe, monkeypatch, caplog):
        monkeypatch.setenv("INTEL_LAKE_PROBE_NLM_UNKNOWN_MAX", "1")
        rc, text = self._run(probe, monkeypatch, caplog, FakeNlm([], list_rc=1))
        assert rc == 1
        assert "PROBE FAILED" in text
