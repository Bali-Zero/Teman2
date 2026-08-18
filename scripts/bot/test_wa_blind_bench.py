"""Unit tests for scripts/bot/wa_blind_bench.py.

Orchestrator corpus gate: an unavailable subscription client must be an
explicit SKIP/NOT RUN and must never count as a green promotion gate. These
tests prove that path is a true no-op (zero subprocess calls), and that an
available faked subscription client plus fixtures produces the expected
blind-transcript/key-file split. No test launches the real Codex CLI.

Run:
    cd ~/nuzantara && python3 -m pytest scripts/bot/test_wa_blind_bench.py -v
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent.parent))
sys.path.insert(0, str(SCRIPTS_DIR.parent.parent / "apps" / "backend-rag"))

from scripts.bot.wa_blind_bench import (  # noqa: E402
    _DEFAULT_SEED,
    _STATUS_PREFIX,
    FixtureFormatError,
    _blind_labels,
    _load_fixtures,
    _mkdir_private,
    _open_private,
    _render_fixture_prompt,
    _safe_fixture_ref,
    run_bench,
)
from scripts.bot.wa_blind_bench import (  # noqa: E402
    CodexSubscriptionBenchClient as _RealCodexSubscriptionBenchClient,
)


@pytest.fixture(autouse=True)
def _available_subscription_client_by_default(monkeypatch):
    """Keep every offline test independent of the workstation's real login."""

    class _Result:
        text = "synthetic answer"
        latency_ms = 1.0
        attempts = 1
        refusal = None

    class _Client:
        available = True

        async def generate(self, *, input_text, model=None, **kwargs):
            return _Result()

        async def close(self):
            pass

    import scripts.bot.wa_blind_bench as client_module

    monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _Client)


class TestK5PrivateOutputDirectory:
    """K5 (Kimi K3 diagnostic, 2026-08-15): `wa_blind_bench.py`'s own
    `output_dir.mkdir()` had the same missing-`mode=` gap as the corpus
    builder's — same fix (`_mkdir_private`), tested independently here
    since it's this file's own function, not an import from the corpus
    builder."""

    def test_freshly_created_directory_is_mode_0700(self, tmp_path: Path):
        target = tmp_path / "bench-runs.local"
        old_umask = os.umask(0o022)
        try:
            _mkdir_private(target)
        finally:
            os.umask(old_umask)
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o700, f"expected 0o700, got {oct(mode)}"

    def test_already_existing_looser_directory_is_tightened(self, tmp_path: Path):
        target = tmp_path / "preexisting"
        target.mkdir(mode=0o750)
        os.chmod(target, 0o750)  # force group access without ever granting world access
        assert stat.S_IMODE(target.stat().st_mode) == 0o750

        _mkdir_private(target)

        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o700, f"expected tightened to 0o700, got {oct(mode)}"


class TestR9_8MkdirPrivateRefusesSymlinkLeaf:
    """R9-8 (MICRO, Kimi K3 round-9 review): the directory-component twin
    of R8-13's leaf-file symlink hole. `Path.mkdir(exist_ok=True)`
    silently accepts a pre-planted symlink whose target is a directory,
    and `os.chmod` follows it to the target by default — `_mkdir_private`
    must refuse rather than chmod through the symlink."""

    def test_guilt_symlink_leaf_is_refused(self, tmp_path: Path):
        real_target = tmp_path / "real-dir"
        real_target.mkdir(mode=0o750)
        os.chmod(real_target, 0o750)

        symlink_path = tmp_path / "bench-runs.local"
        symlink_path.symlink_to(real_target)

        with pytest.raises(OSError):
            _mkdir_private(symlink_path)

        assert stat.S_IMODE(real_target.stat().st_mode) == 0o750, (
            "a symlink target's permissions must never be tightened by a call that refuses it"
        )

    def test_innocence_plain_directory_still_gets_0700(self, tmp_path: Path):
        target = tmp_path / "plain-dir"
        _mkdir_private(target)
        assert not target.is_symlink()
        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o700, f"expected 0o700, got {oct(mode)}"


class TestOpenPrivateFchmod:
    """MEDIUM binding correction, 2026-08-15 (Kimi K3, live-gate round 5,
    two passes) — same class of bug as `build_deid_corpus.py`'s
    `_write_jsonl_private` (see that function's docstring for the full
    two-pass history: `os.open(..., mode=0o600)` only applies `mode` on
    CREATION, and the first fix's `O_TRUNC`-up-front open destroyed
    pre-existing content before a failed `os.fchmod` could even be
    checked). `_open_private` had ZERO test coverage of any kind before
    this round."""

    def test_preexisting_loose_file_is_tightened_to_0600(self, tmp_path: Path):
        target = tmp_path / "preexisting.jsonl"
        target.write_text('{"turn": "old"}\n', encoding="utf-8")
        os.chmod(target, 0o640)
        assert stat.S_IMODE(target.stat().st_mode) == 0o640

        with _open_private(target) as f:
            f.write('{"turn": "new"}\n')

        mode = stat.S_IMODE(target.stat().st_mode)
        assert mode == 0o600, f"expected tightened to 0o600, got {oct(mode)}"

    def test_fchmod_failure_leaves_original_content_untouched_and_fd_closed(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        target = tmp_path / "existing.jsonl"
        original_content = '{"turn": "keep me byte-identical"}\n'
        target.write_text(original_content, encoding="utf-8")
        os.chmod(target, 0o640)

        closed_fds: list[int] = []
        real_close = os.close

        def _spy_close(fd: int) -> None:
            closed_fds.append(fd)
            real_close(fd)

        def _raise_fchmod(fd: int, mode: int) -> None:
            raise OSError("simulated fchmod failure")

        monkeypatch.setattr(os, "fchmod", _raise_fchmod)
        monkeypatch.setattr(os, "close", _spy_close)

        with pytest.raises(OSError):
            _open_private(target)

        assert len(closed_fds) == 1, "the fd opened before the failed fchmod must be closed exactly once"
        assert target.read_text(encoding="utf-8") == original_content, (
            "pre-existing content must survive a failed fchmod completely untouched"
        )

    def test_r11_1_ftruncate_failure_closes_fd_exactly_once_and_propagates(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        """R11-1 (Kimi K3 round-11 review): R10-4's fix moved `os.ftruncate`/
        `os.lseek` inside the `os.fchmod` guard, but the ADR claimed "no new
        branch to pin" while the fd-closed-on-truncate-failure BEHAVIOR is
        genuinely new — the existing `os.fchmod`-failure test above never
        reaches the `os.ftruncate` call at all (it raises first). This test
        exercises the branch R10-4 actually added: `os.ftruncate` raising.

        R12-5 binding correction, 2026-08-15 (Kimi K3 round-12 review):
        this test asserted fd-closed-exactly-once but, unlike its sibling
        `os.fchmod`-failure test above, never asserted that the
        pre-existing content actually survived the failure untouched —
        the exact guarantee this function's docstring claims for this
        branch. Added below, mirroring the sibling assertion."""
        target = tmp_path / "existing-ftruncate.jsonl"
        original_content = '{"turn": "keep me byte-identical"}\n'
        target.write_text(original_content, encoding="utf-8")
        os.chmod(target, 0o640)

        closed_fds: list[int] = []
        real_close = os.close

        def _spy_close(fd: int) -> None:
            closed_fds.append(fd)
            real_close(fd)

        def _raise_ftruncate(fd: int, length: int) -> None:
            raise OSError("simulated ftruncate failure")

        monkeypatch.setattr(os, "ftruncate", _raise_ftruncate)
        monkeypatch.setattr(os, "close", _spy_close)

        with pytest.raises(OSError):
            _open_private(target)

        assert len(closed_fds) == 1, "the fd must be closed exactly once when os.ftruncate fails"
        assert target.read_text(encoding="utf-8") == original_content, (
            "pre-existing content must survive a failed ftruncate completely untouched"
        )

    # R12-4 (Kimi K3 round-12 review): the sibling test that pinned
    # `os.fdopen` failing INSIDE the fchmod/ftruncate/lseek guard
    # (`test_r11_2_fdopen_failure_closes_fd_exactly_once_and_propagates`)
    # is DELETED here — it pinned exactly the R11-2 behavior round-12
    # reverts (see `_open_private`'s docstring for the CPython
    # double-close/fd-recycling hazard that made the wrap unsafe).
    # `os.fdopen` is deliberately unguarded again; there is no
    # close-on-exception branch left to pin for it.

    def test_happy_path_replaces_longer_preexisting_content_with_no_residual_tail(self, tmp_path: Path):
        target = tmp_path / "shrinking.jsonl"
        long_original = "\n".join(f'{{"turn": "padding {i}"}}' for i in range(20))
        target.write_text(long_original + "\n", encoding="utf-8")
        assert len(target.read_text(encoding="utf-8")) > 100

        with _open_private(target) as f:
            f.write('{"turn": "short"}\n')

        final_content = target.read_text(encoding="utf-8")
        assert final_content == '{"turn": "short"}\n'
        assert "padding" not in final_content, "no residual tail from the longer pre-existing content"


class TestSkipUnavailable:
    @pytest.mark.asyncio
    async def test_skip_when_codex_subscription_unavailable_zero_calls(self, tmp_path, monkeypatch, capsys):
        class _UnavailableClient:
            available = False

            async def generate(self, *, input_text, model=None, **kwargs):
                raise AssertionError("generate must not run while unavailable")

            async def close(self):
                raise AssertionError("close must not run before availability gate")

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _UnavailableClient)

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        output_dir = tmp_path / "out"

        stats = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=output_dir,
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
        )

        assert stats == {"fixtures": 0, "skipped": 1}
        assert not output_dir.exists() or not list(output_dir.glob("*.local.jsonl")), (
            "no output files should be written on a SKIP"
        )

        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}SKIPPED_UNAVAILABLE" in captured.out

    @pytest.mark.asyncio
    async def test_skip_when_no_fixtures_even_when_subscription_client_available(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        class _AvailableClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                raise AssertionError("no fixture means no generate call")

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _AvailableClient)
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()  # exists but empty — no fixtures_*.local.jsonl
        output_dir = tmp_path / "out"

        stats = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=output_dir,
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
        )

        assert stats == {"fixtures": 0, "skipped": 1}
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}SKIPPED_NO_FIXTURES" in captured.out


class TestBlindLabels:
    def test_labels_cover_all_variants_bijectively(self):
        variants = ["gpt-5.6-terra", "gpt-5.6-luna"]
        label_map = _blind_labels(variants, seed=1)
        assert set(label_map.values()) == set(variants)
        assert set(label_map.keys()) == {"A", "B"}

    def test_same_seed_is_reproducible(self):
        variants = ["gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.6-sol"]
        first_call = _blind_labels(variants, seed=7)
        second_call = _blind_labels(variants, seed=7)
        assert first_call == second_call


class TestStableHash:
    """Binding correction, 2026-08-15: the per-fixture shuffle seed used to
    derive from Python's builtin `hash(str)`, which is salted per-process
    by `PYTHONHASHSEED` (randomized by default) — the "same fixture ->
    same shuffle on a re-run" claim in the module docstring was false for
    a re-run in a FRESH process. `_stable_int_hash` uses SHA-256 instead.
    """

    def test_stable_hash_matches_known_sha256_digest(self):
        """Pin against a LITERAL, hardcoded SHA-256 digest — not against
        `int(hashlib.sha256(...).hexdigest(), 16)` computed inline, which
        is the exact same expression `_stable_int_hash` itself evaluates
        and therefore not an independent oracle at all (R6-8 binding
        correction, Kimi K3 round-6 review: the previous version of this
        test *claimed* to be "not a self-comparison" in its own docstring
        while its `expected` was in fact the identical computation written
        twice — a self-comparison in every way that matters, the docstring
        notwithstanding). The hex string below was computed ONCE
        (`hashlib.sha256(b"fixture-000001").hexdigest()`) and pasted as a
        literal, so this test now actually pins `_stable_int_hash` against
        an external, independently-verifiable value — a genuine change to
        the SHA-256 implementation (or to how `_stable_int_hash` encodes
        its input) would be caught here even if the change also broke
        `hashlib.sha256` itself in some hypothetical matching way, which
        the inline-computed version could never detect."""
        from scripts.bot.wa_blind_bench import _stable_int_hash

        known_digest_hex = "732535bfbf82b429d6d8075342c5f0bdf5bea92ba257e0f6eea77708a789d7ec"
        expected = int(known_digest_hex, 16)
        assert _stable_int_hash("fixture-000001") == expected

    def test_stable_hash_differs_for_different_inputs(self):
        from scripts.bot.wa_blind_bench import _stable_int_hash

        first_id_hash = _stable_int_hash("fixture-000001")
        second_id_hash = _stable_int_hash("fixture-000002")
        assert first_id_hash != second_id_hash

    def test_stable_hash_matches_across_a_fresh_subprocess(self):
        """The real bug this guards against: `hash()` on `str` differs
        across separate `python3` invocations (each gets its own random
        `PYTHONHASHSEED` unless pinned). Running two INDEPENDENT
        subprocesses and asserting they agree is the only way to actually
        catch a regression back to `hash()` — an in-process test alone
        cannot distinguish "stable" from "coincidentally the same process
        hasn't reseeded".
        """
        import subprocess
        import sys as _sys

        script = (
            "import sys; sys.path.insert(0, '.'); "
            "from scripts.bot.wa_blind_bench import _stable_int_hash; "
            "print(_stable_int_hash('fixture-000042'))"
        )
        repo_root = SCRIPTS_DIR.parent.parent

        results = []
        for _ in range(2):
            proc = subprocess.run(
                [_sys.executable, "-c", script],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            results.append(proc.stdout.strip())

        assert results[0] == results[1], (
            f"_stable_int_hash produced different values across two fresh subprocesses: {results!r} — "
            f"this is exactly the class of bug a bare hash(str) has (PYTHONHASHSEED salting)."
        )
        assert results[0] != "", "subprocess produced no output"


class TestR6_2NonceBasedBlinding:
    """R6-2 (Kimi K3 round-6 review): the per-fixture shuffle seed used to
    derive from PUBLIC inputs only — `--seed` (default 42, printed in
    `--help`) and `fixture_id` (printed in plain text inside the blind
    transcript itself) — so anyone holding the transcript plus this
    file's source could recompute the shuffle WITHOUT the key file. Fixed
    by folding a per-run SECRET nonce (written only to the key file) into
    the seed derivation via `_fixture_seed`."""

    def test_guilt_old_style_public_only_derivation_no_longer_matches(self):
        """The pre-fix formula (`seed_base + _stable_int_hash(fixture_id)
        % 10_000`, no nonce at all) must not reproduce the actual
        per-fixture seed once a nonce is in play."""
        from scripts.bot.wa_blind_bench import _fixture_seed, _stable_int_hash

        fixture_id = "fixture-000001"
        seed_base = 42
        old_style_seed = seed_base + _stable_int_hash(fixture_id) % 10_000
        actual_seed = _fixture_seed(nonce="a-real-run-nonce", fixture_id=fixture_id, seed_base=seed_base)
        assert old_style_seed != actual_seed

    def test_innocence_same_nonce_reproduces_the_same_seed(self):
        """Reproducibility IS preserved, conditionally: the SAME nonce +
        fixture id + seed_base always yields the SAME per-fixture seed."""
        from scripts.bot.wa_blind_bench import _fixture_seed

        first = _fixture_seed(nonce="shared-nonce", fixture_id="fixture-000007", seed_base=42)
        second = _fixture_seed(nonce="shared-nonce", fixture_id="fixture-000007", seed_base=42)
        assert first == second

    def test_different_nonce_yields_a_different_seed(self):
        """Guilt companion: changing ONLY the nonce (same fixture id, same
        seed_base) must change the derived seed — proves the nonce is
        actually load-bearing in the derivation, not a decorative field."""
        from scripts.bot.wa_blind_bench import _fixture_seed

        a = _fixture_seed(nonce="nonce-one", fixture_id="fixture-000007", seed_base=42)
        b = _fixture_seed(nonce="nonce-two", fixture_id="fixture-000007", seed_base=42)
        assert a != b

    @pytest.mark.asyncio
    async def test_two_runs_with_the_same_nonce_produce_the_same_label_shuffle(self, tmp_path, monkeypatch):
        """End-to-end innocence: a legitimate re-run that supplies the
        prior run's nonce (as `--nonce` would) reproduces the exact same
        blind-label shuffle — the reproducibility guarantee the module
        docstring makes, now correctly scoped to "given the nonce"."""

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeResult:
            def __init__(self, model: str):
                self.refusal = False
                self.text = f"answer from {model}"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        shared_nonce = "reused-nonce-for-reproducibility-test"

        stats_a = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "run_a",
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
            nonce=shared_nonce,
        )
        stats_b = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "run_b",
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
            nonce=shared_nonce,
        )
        assert stats_a["fixtures"] == 1
        assert stats_b["fixtures"] == 1

        key_a = (tmp_path / "run_a" / "label_key.local.jsonl").read_text(encoding="utf-8").splitlines()
        key_b = (tmp_path / "run_b" / "label_key.local.jsonl").read_text(encoding="utf-8").splitlines()
        assert json.loads(key_a[0])["nonce"] == shared_nonce
        assert json.loads(key_b[0])["nonce"] == shared_nonce
        assert json.loads(key_a[1])["label_map"] == json.loads(key_b[1])["label_map"], (
            "same nonce + same seed + same fixture id must reproduce the same shuffle"
        )

    @pytest.mark.asyncio
    async def test_omitted_nonce_generates_a_fresh_secret_per_run(self, tmp_path, monkeypatch):
        """Innocence for the default path: when no `--nonce` is supplied,
        `run_bench` must generate its own fresh nonce (never a fixed
        constant, never empty)."""

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeResult:
            def __init__(self, model: str):
                self.refusal = False
                self.text = "answer"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "run_1",
            candidates=["gpt-5.6-terra"],
            seed=42,
        )
        await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "run_2",
            candidates=["gpt-5.6-terra"],
            seed=42,
        )

        nonce_1 = json.loads(
            (tmp_path / "run_1" / "label_key.local.jsonl").read_text(encoding="utf-8").splitlines()[0],
        )["nonce"]
        nonce_2 = json.loads(
            (tmp_path / "run_2" / "label_key.local.jsonl").read_text(encoding="utf-8").splitlines()[0],
        )["nonce"]
        assert nonce_1, "a nonce must always be generated"
        assert nonce_2, "a nonce must always be generated"
        assert nonce_1 != nonce_2, "two independent runs must not share a nonce"


class TestR6_2RefinementReuseNonceFromFile:
    """R6-2 refinement (orchestrator/Codex order, 2026-08-15, binding):
    the nonce is a SECRET, and a secret in argv is visible in plaintext to
    any other process on the machine (ps/proc) for this process's whole
    lifetime — the same class of exposure `build_deid_corpus.py`'s R6-4
    fix already treats as unacceptable for non-secret WhatsApp text, and a
    stricter standard applies to an actual secret. `--nonce` is REMOVED
    from the CLI; `--reuse-nonce-from <path>` reads the nonce off disk
    from a prior run's own key file instead — a path in argv identifies a
    file, not a secret value."""

    @staticmethod
    def _fixtures_dir(tmp_path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )
        return fixtures_dir

    @staticmethod
    def _patch_fake_client(monkeypatch):
        class _FakeResult:
            def __init__(self, model):
                self.refusal = False
                self.text = f"answer from {model}"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

    def test_guilt_nonce_flag_no_longer_exists_on_the_cli(self, tmp_path, monkeypatch):
        import scripts.bot.wa_blind_bench as module

        fixtures_dir = self._fixtures_dir(tmp_path)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(tmp_path / "out"),
                "--nonce",
                "a-secret-that-must-never-be-a-cli-flag",
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            module.main()
        assert exc_info.value.code == 2, "argparse must reject the removed --nonce flag as unrecognized"

    def test_innocence_reuse_nonce_from_reproduces_the_same_shuffle_via_the_cli(self, tmp_path, monkeypatch):
        """Deliberately NOT `@pytest.mark.asyncio` / `async def`: `module.main()`
        below calls `asyncio.run(...)` internally, which raises
        `RuntimeError: asyncio.run() cannot be called from a running event
        loop` if this test itself already has one (pytest-asyncio's) — so
        run_a is built via a fresh top-level `asyncio.run(...)` too, matching
        how a real operator would invoke this in two separate CLI runs."""
        import asyncio as _asyncio

        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        stats_a = _asyncio.run(
            run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=tmp_path / "run_a",
                candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
                seed=42,
            ),
        )
        assert stats_a["fixtures"] == 1
        key_a_path = tmp_path / "run_a" / "label_key.local.jsonl"
        key_a_lines = key_a_path.read_text(encoding="utf-8").splitlines()
        nonce_a = json.loads(key_a_lines[0])["nonce"]

        import scripts.bot.wa_blind_bench as module

        cli_argv = [
            "wa_blind_bench.py",
            "--fixtures-dir",
            str(fixtures_dir),
            "--output-dir",
            str(tmp_path / "run_b"),
            "--candidates",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
            "--reuse-nonce-from",
            str(key_a_path),
        ]
        monkeypatch.setattr(sys, "argv", cli_argv)
        rc = module.main()
        assert rc == 0

        # The secret nonce value itself must never appear anywhere in
        # argv — only the PATH to the key file it lives in does.
        assert nonce_a not in cli_argv

        key_b_lines = (tmp_path / "run_b" / "label_key.local.jsonl").read_text(encoding="utf-8").splitlines()
        assert json.loads(key_b_lines[0])["nonce"] == nonce_a, "the reused run must carry the SAME nonce"
        assert json.loads(key_b_lines[1])["label_map"] == json.loads(key_a_lines[1])["label_map"], (
            "same nonce + same seed + same fixture id must reproduce the same shuffle via --reuse-nonce-from"
        )

    def test_guilt_malformed_reuse_nonce_from_file_fails_loud_not_a_silent_fresh_nonce(self, tmp_path, monkeypatch):
        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        bad_key_file = tmp_path / "not_a_key_file.jsonl"
        bad_key_file.write_text("not even json\n", encoding="utf-8")

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(bad_key_file),
            ],
        )
        rc = module.main()
        assert rc == 1, "a malformed --reuse-nonce-from file must fail loud, never silently fall back"
        assert not output_dir.exists(), "nothing should have been run when the requested nonce could not be read"

    def test_guilt_missing_reuse_nonce_from_file_fails_loud(self, tmp_path, monkeypatch):
        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(tmp_path / "does_not_exist.jsonl"),
            ],
        )
        rc = module.main()
        assert rc == 1
        assert not output_dir.exists()


class TestR7_2NonDictNonceLineDoesNotCrash:
    """R7-2 (Kimi K3 round-7 review): a `--reuse-nonce-from` file whose
    first line is syntactically valid JSON but NOT a JSON object —
    `[1,2]`, `42`, `"str"`, `null` — used to reach `["nonce"]` directly
    and raise a raw `TypeError` (list/int/str/NoneType is not
    subscriptable by a string key). `TypeError` was NOT in the previous
    except tuple, so it propagated as an unhandled traceback instead of
    this function's promised clean `return 1`."""

    @staticmethod
    def _fixtures_dir(tmp_path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )
        return fixtures_dir

    @pytest.mark.parametrize("bad_first_line", ["[1, 2]", "42", '"just a string"', "null"])
    def test_guilt_non_dict_first_line_fails_loud_not_a_raw_typeerror(self, tmp_path, monkeypatch, bad_first_line):
        fixtures_dir = self._fixtures_dir(tmp_path)

        bad_key_file = tmp_path / "not_a_key_file.jsonl"
        bad_key_file.write_text(bad_first_line + "\n", encoding="utf-8")

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(bad_key_file),
            ],
        )
        # Must not raise TypeError — must return 1 cleanly, same as every
        # other malformed --reuse-nonce-from shape.
        rc = module.main()
        assert rc == 1, f"non-dict first line {bad_first_line!r} must fail loud (rc=1), never raise"
        assert not output_dir.exists(), "nothing should have been run when the nonce line was malformed"


class TestR7_3FixtureShapeValidation:
    """R7-3 (Kimi K3 round-7 review): `_load_fixtures` used to append
    `json.loads(line)` with zero shape validation. `fixture["id"]` (seed
    of the label_map) and `fixture["language"]` (blind-transcript row) are
    read OUTSIDE any per-candidate try/except in the caller — a fixture
    that was valid JSON but not a dict, or missing those keys, crashed
    `run_bench` PARTWAY THROUGH a run, AFTER `_open_private` had already
    created (and possibly partially written) the blind transcript and key
    files, with no status line recorded. Validated here now, BEFORE
    `run_bench` ever opens any output file."""

    def test_guilt_non_dict_fixture_line_fails_before_any_output_file_created(self, tmp_path):
        from scripts.bot.wa_blind_bench import FixtureFormatError, _load_fixtures

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text("[1, 2]\n", encoding="utf-8")

        with pytest.raises(FixtureFormatError):
            _load_fixtures(fixtures_dir)

    def test_guilt_missing_required_key_fails(self, tmp_path):
        from scripts.bot.wa_blind_bench import FixtureFormatError, _load_fixtures

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "text": "missing language key"}) + "\n",
            encoding="utf-8",
        )

        with pytest.raises(FixtureFormatError):
            _load_fixtures(fixtures_dir)

    def test_guilt_empty_string_value_fails(self, tmp_path):
        from scripts.bot.wa_blind_bench import FixtureFormatError, _load_fixtures

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "", "language": "en", "text": "empty id"}) + "\n",
            encoding="utf-8",
        )

        with pytest.raises(FixtureFormatError):
            _load_fixtures(fixtures_dir)

    def test_innocence_well_formed_fixture_still_loads(self, tmp_path):
        from scripts.bot.wa_blind_bench import _load_fixtures

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        fixtures = _load_fixtures(fixtures_dir)
        assert fixtures == [{"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}]

    @pytest.mark.asyncio
    async def test_end_to_end_malformed_fixture_leaves_no_partial_output_files(self, tmp_path, monkeypatch):
        """The mandate's core property: a malformed fixture mixed in with
        a well-formed one must crash BEFORE run_bench opens any output
        file — never a half-written blind transcript / key file."""

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        lines = [
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}),
            "[1, 2]",  # malformed — not a dict
        ]
        (fixtures_dir / "fixtures_en.local.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

        class _FakeResult:
            refusal = False
            text = "answer"
            latency_ms = 12.3
            attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult()

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        from scripts.bot.wa_blind_bench import FixtureFormatError

        output_dir = tmp_path / "out"
        with pytest.raises(FixtureFormatError):
            await run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=output_dir,
                candidates=["gpt-5.6-terra"],
                seed=42,
            )
        assert not output_dir.exists(), "no output directory/files should exist when the corpus was malformed"

    def test_error_message_never_contains_line_content_or_fixtures_dir_path(self, tmp_path):
        """VINCOLO (R7-3): the error message must never contain the raw
        line content nor any operator-chosen path component — only the
        file's own generated basename + line number."""
        from scripts.bot.wa_blind_bench import FixtureFormatError, _load_fixtures

        secret_dir_name = "ContactNameSecretFixturesDir"
        fixtures_dir = tmp_path / secret_dir_name
        fixtures_dir.mkdir()
        secret_line_content = "TOP_SECRET_LINE_CONTENT_MARKER"
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            f'["{secret_line_content}"]\n',
            encoding="utf-8",
        )

        with pytest.raises(FixtureFormatError) as exc_info:
            _load_fixtures(fixtures_dir)

        message = str(exc_info.value)
        assert secret_dir_name not in message
        assert secret_line_content not in message
        assert str(fixtures_dir) not in message
        assert "fixtures_en.local.jsonl" in message
        assert "line 1" in message


class TestR6_6AllFailedStatus:
    """R6-6 (Kimi K3 round-6 review): a run that reaches `RAN` (exit 0)
    with EVERY response an `[ERROR: ...]` placeholder is not a completed
    benchmark pass — it's a run that never produced a provider response on
    any candidate. `WA_BLIND_BENCH_STATUS=RAN_ALL_FAILED` + non-zero
    `main()` exit distinguishes that from a genuine (possibly
    partial-failure) `RAN`."""

    @staticmethod
    def _fixtures_dir(tmp_path, n=1):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        lines = [
            json.dumps(
                {
                    "id": f"fixture-{i:06d}",
                    "language": "en",
                    "role": "user",
                    "history": [],
                    "text": f"question {i}",
                },
            )
            for i in range(1, n + 1)
        ]
        (fixtures_dir / "fixtures_en.local.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return fixtures_dir

    @pytest.mark.asyncio
    async def test_guilt_all_candidates_failing_yields_all_failed_status(self, tmp_path, monkeypatch, capsys):
        fixtures_dir = self._fixtures_dir(tmp_path)

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                raise RuntimeError("simulated total failure")

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        stats = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "out",
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
        )

        assert stats["all_failed"] is True
        assert stats["errors"] == stats["responses"] == 2
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN_ALL_FAILED" in captured.out
        assert f"{_STATUS_PREFIX}RAN\n" not in captured.out

    def test_guilt_main_returns_nonzero_when_all_responses_fail(self, tmp_path, monkeypatch):
        import scripts.bot.wa_blind_bench as module

        fixtures_dir = self._fixtures_dir(tmp_path)

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                raise RuntimeError("simulated total failure")

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(tmp_path / "out"),
                "--candidates",
                "gpt-5.6-terra",
            ],
        )
        rc = module.main()
        assert rc == 1

    @pytest.mark.asyncio
    async def test_innocence_mixed_success_and_failure_stays_ran_with_error_count(self, tmp_path, monkeypatch, capsys):
        """Innocence: partial failure (one candidate errors, one succeeds
        on the same fixture) must stay `RAN` (exit-0 territory) but report
        the error count in the returned stats and the log."""
        fixtures_dir = self._fixtures_dir(tmp_path)

        class _FakeResult:
            refusal = False
            text = "a real answer"
            latency_ms = 12.3
            attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                if model == "gpt-5.6-luna":
                    raise RuntimeError("simulated failure for luna only")
                return _FakeResult()

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        stats = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "out",
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
        )

        assert stats["all_failed"] is False
        assert stats["errors"] == 1
        assert stats["responses"] == 2
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN\n" in captured.out
        assert "RAN_ALL_FAILED" not in captured.out

    @pytest.mark.asyncio
    async def test_innocence_all_success_stays_ran_zero_errors(self, tmp_path, monkeypatch, capsys):
        fixtures_dir = self._fixtures_dir(tmp_path)

        class _FakeResult:
            refusal = False
            text = "a real answer"
            latency_ms = 12.3
            attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult()

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        stats = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "out",
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
        )

        assert stats["all_failed"] is False
        assert stats["errors"] == 0
        assert stats["responses"] == 2
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN\n" in captured.out

    @pytest.mark.asyncio
    async def test_innocence_genuine_response_starting_with_error_marker_not_counted_as_failed(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        """R14-3 (Kimi K3 round-14 review): failure counting used to test
        `response_text.startswith("[ERROR:")` against the model's own
        (attacker/model-controlled) text — a GENUINE response that
        happens to start with that exact literal (a model quoting an
        error message back, an adversarial fixture, ...) must NOT be
        miscounted as a failure. Counting now reads the STRUCTURAL
        `attempts`/`latency_ms is None` signal `_run_one_fixture` already
        sets on its `except` branch, never the response text's own
        content — this is the case that in the limit (every fixture)
        would previously have flipped a genuinely successful run to
        `RAN_ALL_FAILED`."""
        fixtures_dir = self._fixtures_dir(tmp_path)

        class _FakeResult:
            refusal = False
            text = "[ERROR: the customer's own message, quoted back verbatim]"
            latency_ms = 12.3
            attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult()

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        stats = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=tmp_path / "out",
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
        )

        assert stats["all_failed"] is False
        assert stats["errors"] == 0
        assert stats["responses"] == 2
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN\n" in captured.out
        assert "RAN_ALL_FAILED" not in captured.out


class TestR7_1PerFixtureFailureLogNeverNamesTheRealModel:
    """R7-1 (Kimi K3 round-7 review): the per-fixture failure log used to
    print the REAL model name — combined with the `[ERROR: ...]` marker
    already visible in plain text inside the blind transcript itself, a
    scorer reading BOTH the transcript and this process's own log output
    could match a failed response's label back to its real model for
    every fixture that hit an error, de-blinding exactly the mapping the
    separate key file exists to keep secret."""

    @staticmethod
    def _fixtures_dir(tmp_path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )
        return fixtures_dir

    @pytest.mark.asyncio
    async def test_guilt_real_model_name_never_appears_in_any_log_record_on_failure(
        self,
        tmp_path,
        monkeypatch,
        caplog,
    ):
        import logging as _logging

        fixtures_dir = self._fixtures_dir(tmp_path)

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                raise RuntimeError("simulated failure")

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        with caplog.at_level(_logging.DEBUG):
            stats = await run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=tmp_path / "out",
                candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
                seed=42,
            )

        assert stats["errors"] == 2
        for record in caplog.records:
            msg = record.getMessage()
            assert "gpt-5.6-terra" not in msg, f"real model name leaked into a per-fixture log line: {msg!r}"
            assert "gpt-5.6-luna" not in msg, f"real model name leaked into a per-fixture log line: {msg!r}"

    @pytest.mark.asyncio
    async def test_innocence_failure_log_still_names_the_fixture_and_label(self, tmp_path, monkeypatch, caplog):
        """The fix must not go silent — the warning should still carry
        useful diagnostic info (fixture id + opaque label), just never the
        real model name."""
        import logging as _logging

        fixtures_dir = self._fixtures_dir(tmp_path)

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                raise RuntimeError("simulated failure")

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        with caplog.at_level(_logging.DEBUG):
            await run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=tmp_path / "out",
                candidates=["gpt-5.6-terra"],
                seed=42,
            )

        messages = [r.getMessage() for r in caplog.records]
        assert any("fixture-000001" in m and "label" in m for m in messages), (
            f"expected a per-fixture failure log naming the fixture id and 'label', got: {messages!r}"
        )


class TestR7_4OutputDirPathNeverLoggedVerbatim:
    """R7-4 (Kimi K3 round-7 review): `blind_path`/`key_path` embed the
    operator-chosen `--output-dir` component (an R6-3-class leak, a
    directory can be named after what it holds) — this checks the
    "Wrote blind transcript"/"Wrote label key"/SCORING log lines and the
    SKIPPED_NO_FIXTURES message never carry that path verbatim."""

    @pytest.mark.asyncio
    async def test_end_to_end_output_dir_contact_name_never_reaches_any_log_record(
        self,
        tmp_path,
        monkeypatch,
        caplog,
    ):
        import logging as _logging

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        contact_name = "OutputDirSecretContact"
        output_dir = tmp_path / f"WhatsApp Chat with {contact_name} bench-runs"

        class _FakeResult:
            refusal = False
            text = "answer"
            latency_ms = 12.3
            attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult()

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        with caplog.at_level(_logging.DEBUG):
            stats = await run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=output_dir,
                candidates=["gpt-5.6-terra"],
                seed=42,
            )

        assert stats["fixtures"] == 1
        for record in caplog.records:
            msg = record.getMessage()
            assert contact_name not in msg, f"output-dir contact name leaked into log: {msg!r}"
            assert str(output_dir) not in msg, f"full output-dir path leaked into log: {msg!r}"

    def test_no_fixtures_found_message_does_not_log_the_fixtures_dir_path(self, tmp_path, monkeypatch, capsys):
        contact_name = "FixturesDirSecretContact"
        fixtures_dir = tmp_path / f"WhatsApp Chat with {contact_name}"
        fixtures_dir.mkdir()  # exists but empty

        import asyncio as _asyncio

        _asyncio.run(
            run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=tmp_path / "out",
                candidates=["gpt-5.6-terra"],
                seed=42,
            ),
        )

        captured = capsys.readouterr()
        assert contact_name not in captured.out
        assert str(fixtures_dir) not in captured.out


class TestRunProducesBlindTranscriptAndSeparateKey:
    @pytest.mark.asyncio
    async def test_blind_transcript_excludes_model_names_key_file_has_them(self, tmp_path, monkeypatch):
        """The blind transcript must never let a reader infer the model
        from the JSON itself (only opaque A/B labels); the key file, which
        IS allowed to name models, must be a SEPARATE file."""

        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "out"

        class _FakeResult:
            def __init__(self, model: str):
                self.model = model
                self.refusal = False
                # Deliberately does NOT embed the model name in the answer
                # text — the blind mechanism hides which shuffled label
                # maps to which real model in the TRANSCRIPT's own fields,
                # it cannot (and is not meant to) redact a model that
                # literally writes its own name into its answer.
                self.text = f"a generic answer, response id {id(self)}"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        # Patch the harness facade itself; no paid/API-key client exists on
        # this execution path.
        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        stats = await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=output_dir,
            candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
            seed=42,
        )

        assert stats["fixtures"] == 1
        assert stats["skipped"] == 0

        blind_path = output_dir / "blind_transcript.local.jsonl"
        key_path = output_dir / "label_key.local.jsonl"
        assert blind_path.exists()
        assert key_path.exists()

        blind_text = blind_path.read_text(encoding="utf-8")
        assert "gpt-5.6-terra" not in blind_text
        assert "gpt-5.6-luna" not in blind_text

        key_text = key_path.read_text(encoding="utf-8")
        key_lines = key_text.splitlines()
        # R6-2: the key file's FIRST line is now the run's secret nonce,
        # not the first fixture's key_row. R8-6: that first line now also
        # carries `seed`/`candidates` (load-bearing for reproducing the
        # shuffle via --reuse-nonce-from, see that fix's own tests below).
        nonce_row = json.loads(key_lines[0])
        assert set(nonce_row.keys()) == {"nonce", "seed", "candidates"}
        assert nonce_row["nonce"] not in blind_text, "the secret nonce must never reach the blind transcript"
        key_row = json.loads(key_lines[1])
        assert set(key_row["label_map"].values()) == {"gpt-5.6-terra", "gpt-5.6-luna"}

        import stat

        assert stat.S_IMODE(blind_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


class TestR8_1InvalidUtf8FixtureFileDoesNotCrash:
    """R8-1 (Kimi K3 round-8 review): `_load_fixtures` had no
    `errors="replace"` — a single non-UTF-8 byte in a fixtures file raised
    a raw `UnicodeDecodeError` straight out of the file iterator, uncaught
    by the per-line `json.JSONDecodeError` handling. Now the mangled byte
    becomes U+FFFD, which becomes invalid JSON and is handled by the R8-11
    fix as a clean `FixtureFormatError`."""

    def test_guilt_invalid_utf8_byte_becomes_fixture_format_error_not_unicode_decode_error(self, tmp_path: Path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        good_line = json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "clean fixture"}).encode("utf-8")
        (fixtures_dir / "fixtures_en.local.jsonl").write_bytes(b"\xff\xfe garbage\n" + good_line + b"\n")

        with pytest.raises(FixtureFormatError):
            _load_fixtures(fixtures_dir)

    def test_innocence_valid_utf8_file_still_loads_normally(self, tmp_path: Path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "clean fixture"}) + "\n",
            encoding="utf-8",
        )
        fixtures = _load_fixtures(fixtures_dir)
        assert len(fixtures) == 1


class TestR8_3LatencyAndAttemptsOnlyInKeyFile:
    """R8-3(a) (Kimi K3 round-8 review): per-response `latency_ms`/
    `attempts` are recorded in the key file's `key_row`, keyed by the
    shuffled label — NEVER in the blind transcript, which is the exact
    de-blinding side-channel `label_map` itself already lives in the key
    file to avoid."""

    @pytest.mark.asyncio
    async def test_guilt_latency_never_appears_in_the_blind_transcript(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeResult:
            refusal = False
            text = "answer"
            latency_ms = 987.6
            attempts = 3

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult()

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        output_dir = tmp_path / "out"
        await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=output_dir,
            candidates=["gpt-5.6-terra"],
            seed=42,
        )

        blind_text = (output_dir / "blind_transcript.local.jsonl").read_text(encoding="utf-8")
        assert "987.6" not in blind_text
        assert "latency_ms" not in blind_text
        assert "attempts" not in blind_text

    @pytest.mark.asyncio
    async def test_innocence_latency_and_attempts_recorded_in_key_file(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeResult:
            refusal = False
            text = "answer"
            latency_ms = 987.6
            attempts = 3

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult()

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        output_dir = tmp_path / "out"
        await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=output_dir,
            candidates=["gpt-5.6-terra"],
            seed=42,
        )

        key_lines = (output_dir / "label_key.local.jsonl").read_text(encoding="utf-8").splitlines()
        key_row = json.loads(key_lines[1])
        label = next(iter(key_row["label_map"]))
        assert key_row["latency_ms"][label] == 987.6
        assert key_row["attempts"][label] == 3

    @pytest.mark.asyncio
    async def test_innocence_failed_response_records_none_for_both_fields(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                raise RuntimeError("simulated failure")

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        output_dir = tmp_path / "out"
        await run_bench(
            fixtures_dir=fixtures_dir,
            output_dir=output_dir,
            candidates=["gpt-5.6-terra"],
            seed=42,
        )

        key_lines = (output_dir / "label_key.local.jsonl").read_text(encoding="utf-8").splitlines()
        key_row = json.loads(key_lines[1])
        label = next(iter(key_row["label_map"]))
        assert key_row["latency_ms"][label] is None
        assert key_row["attempts"][label] is None


class TestR8_4SafeFixtureRefFallback:
    """R8-4 (Kimi K3 round-8 review): `_load_fixtures`' glob
    (`fixtures_*.local.jsonl`) is looser than the exact shape the actual
    writer generates — `_safe_fixture_ref` refuses to log a basename that
    doesn't match `fixtures_{en,it,id,other}.local.jsonl` exactly, falling
    back to an opaque per-file ordinal instead."""

    def test_innocence_exact_generated_basename_is_returned_verbatim(self, tmp_path: Path):
        path = tmp_path / "fixtures_en.local.jsonl"
        assert _safe_fixture_ref(path, file_index=1) == "fixtures_en.local.jsonl"

    def test_guilt_contact_renamed_basename_falls_back_to_opaque_ordinal(self, tmp_path: Path):
        path = tmp_path / "fixtures_JohnDoeContact.local.jsonl"
        ref = _safe_fixture_ref(path, file_index=3)
        assert ref == "fixtures file #3"
        assert "JohnDoeContact" not in ref


class TestR8_6SeedAndCandidatesTracking:
    """R8-6 (Kimi K3 round-8 review): the shuffle is a function of
    nonce + seed + candidates, not the nonce alone — `--reuse-nonce-from`
    must adopt `seed`/`candidates` from the key file, fail loud on a
    conflicting explicit CLI value, and fail loud on an OLDER key file
    that predates this tracking (only "nonce" on its first line)."""

    @staticmethod
    def _fixtures_dir(tmp_path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )
        return fixtures_dir

    @staticmethod
    def _patch_fake_client(monkeypatch):
        class _FakeResult:
            def __init__(self, model):
                self.refusal = False
                self.text = f"answer from {model}"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

    def test_guilt_conflicting_seed_fails_loud(self, tmp_path, monkeypatch):
        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        import asyncio as _asyncio

        stats_a = _asyncio.run(
            run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=tmp_path / "run_a",
                candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
                seed=42,
            ),
        )
        assert stats_a["fixtures"] == 1
        key_a_path = tmp_path / "run_a" / "label_key.local.jsonl"

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "run_b"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--seed",
                "99",
                "--reuse-nonce-from",
                str(key_a_path),
            ],
        )
        rc = module.main()
        assert rc == 1, "an explicit --seed conflicting with the key file's own seed must fail loud"
        assert not output_dir.exists()

    def test_guilt_conflicting_candidates_fails_loud(self, tmp_path, monkeypatch):
        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        import asyncio as _asyncio

        stats_a = _asyncio.run(
            run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=tmp_path / "run_a",
                candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
                seed=42,
            ),
        )
        assert stats_a["fixtures"] == 1
        key_a_path = tmp_path / "run_a" / "label_key.local.jsonl"

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "run_b"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--candidates",
                "gpt-5.6-sol",
                "--reuse-nonce-from",
                str(key_a_path),
            ],
        )
        rc = module.main()
        assert rc == 1, "an explicit --candidates conflicting with the key file's own list must fail loud"
        assert not output_dir.exists()

    def test_innocence_matching_explicit_seed_and_candidates_succeeds(self, tmp_path, monkeypatch):
        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        import asyncio as _asyncio

        stats_a = _asyncio.run(
            run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=tmp_path / "run_a",
                candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
                seed=42,
            ),
        )
        assert stats_a["fixtures"] == 1
        key_a_path = tmp_path / "run_a" / "label_key.local.jsonl"

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "run_b"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--seed",
                "42",
                "--candidates",
                "gpt-5.6-terra",
                "gpt-5.6-luna",
                "--reuse-nonce-from",
                str(key_a_path),
            ],
        )
        rc = module.main()
        assert rc == 0, "an explicit --seed/--candidates that MATCHES the key file's own values must succeed"

    def test_guilt_old_format_key_file_without_seed_or_candidates_fails_loud(self, tmp_path, monkeypatch):
        """A key file predating R8-6 (only 'nonce' on its first line) must
        fail loud when neither --seed nor --candidates is supplied
        explicitly — never silently fall back to today's default."""
        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        old_key_file = tmp_path / "old_label_key.local.jsonl"
        old_key_file.write_text(json.dumps({"nonce": "an-old-nonce-value"}) + "\n", encoding="utf-8")

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(old_key_file),
            ],
        )
        rc = module.main()
        assert rc == 1
        assert not output_dir.exists()

    def test_innocence_old_format_key_file_with_explicit_seed_and_candidates_succeeds(self, tmp_path, monkeypatch):
        """The old-format-fails-loud posture only blocks the SILENT
        fallback — an operator who supplies BOTH --seed and --candidates
        explicitly can still reproduce against an old-format key file."""
        self._patch_fake_client(monkeypatch)
        fixtures_dir = self._fixtures_dir(tmp_path)

        old_key_file = tmp_path / "old_label_key.local.jsonl"
        old_key_file.write_text(json.dumps({"nonce": "an-old-nonce-value"}) + "\n", encoding="utf-8")

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--seed",
                str(_DEFAULT_SEED),
                "--candidates",
                "gpt-5.6-terra",
                "--reuse-nonce-from",
                str(old_key_file),
            ],
        )
        rc = module.main()
        assert rc == 0


class TestR8_9BinaryReuseNonceFromFileFailsLoud:
    """R8-9 (Kimi K3 round-8 review): `UnicodeDecodeError` — raised by
    `read_text(encoding="utf-8")` on a binary/non-UTF-8
    `--reuse-nonce-from` file — is a sibling of `ValueError`, NOT a
    subclass of `json.JSONDecodeError`, so it was not covered by the
    prior except tuple and propagated raw."""

    def test_guilt_binary_key_file_fails_loud_not_a_raw_traceback(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        bad_key_file = tmp_path / "binary_key.local.jsonl"
        bad_key_file.write_bytes(b"\xff\xfe\x00\x01not utf-8 at all")

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(bad_key_file),
            ],
        )
        rc = module.main()
        assert rc == 1, "a binary/non-UTF-8 --reuse-nonce-from file must fail loud (rc=1), never raise"
        assert not output_dir.exists()


class TestR9_4EmptyCandidatesNeverSilentlyAdopted:
    """R9-4 (Kimi K3 round-9 review): `all(isinstance(c, str) for c in
    file_candidates)` is vacuously True on `[]` — a `--reuse-nonce-from`
    key file with `"candidates": []` used to be ADOPTED as valid, run
    zero models, and report `RAN` / exit 0 for a run that benchmarked
    nothing. Fixed in two layers: (a) `main()`'s key-file adoption now
    requires a non-empty list of non-empty strings; (b) `run_bench` itself
    refuses an empty candidates list as defense in depth."""

    def test_guilt_key_file_with_empty_candidates_never_reports_ran(self, tmp_path, monkeypatch, capsys):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        key_file = tmp_path / "empty_candidates_key.local.jsonl"
        key_file.write_text(
            json.dumps({"nonce": "a" * 32, "seed": 42, "candidates": []}) + "\n",
            encoding="utf-8",
        )

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(key_file),
            ],
        )
        rc = module.main()
        assert rc == 1, "an empty 'candidates' list in a key file must never be silently adopted"
        assert not output_dir.exists(), "no output files should be written — the check runs before adoption"
        # R10-1(a) reinforcement, 2026-08-15 (Kimi K3 round-10 review):
        # this site used to skip `_print_status` entirely — assert BOTH
        # halves of the broken-contract shape: `RAN` must never appear,
        # AND the correct status (`FAILED_NO_CANDIDATES`, symmetry with
        # the `run_bench`-level `CandidatesEmptyError` catch) must.
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN" not in captured.out
        assert f"{_STATUS_PREFIX}FAILED_NO_CANDIDATES" in captured.out

    def test_guilt_run_bench_itself_refuses_empty_candidates(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        import asyncio as _asyncio

        from scripts.bot.wa_blind_bench import CandidatesEmptyError

        output_dir = tmp_path / "out"
        with pytest.raises(CandidatesEmptyError):
            _asyncio.run(
                run_bench(
                    fixtures_dir=fixtures_dir,
                    output_dir=output_dir,
                    candidates=[],
                    seed=42,
                ),
            )
        assert not output_dir.exists(), "no output files should be written before the candidates check"

    def test_innocence_key_file_with_valid_candidates_adopts_normally(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeResult:
            def __init__(self, model):
                self.refusal = False
                self.text = f"answer from {model}"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        key_file = tmp_path / "valid_key.local.jsonl"
        key_file.write_text(
            json.dumps({"nonce": "a" * 32, "seed": 42, "candidates": ["gpt-5.6-terra"]}) + "\n",
            encoding="utf-8",
        )

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(key_file),
            ],
        )
        rc = module.main()
        assert rc == 0
        assert (output_dir / "blind_transcript.local.jsonl").exists()


class TestR10_1StatusContractOnEveryEarlyExit:
    """R10-1 (Kimi K3 round-10 review): every early `return 1` in
    `main()`'s `--reuse-nonce-from`/adoption block used to skip
    `_print_status` entirely, breaking the "any outcome is
    machine-greppable" contract this module's own docstring promises.
    Fixed with a new `FAILED_BAD_REUSE_FILE` status on 7 of the 9 sites
    (the other 2, candidates-empty-or-malformed and duplicate-candidates,
    print `FAILED_NO_CANDIDATES` instead — covered by
    `TestR9_4EmptyCandidatesNeverSilentlyAdopted`'s reinforced guilt
    test), plus a new `FAILED_IO` status catching an `OSError` raised
    inside `run_bench` (e.g. from `_mkdir_private`'s symlink refusal,
    R9-8) that used to propagate raw. R12-3 count correction, 2026-08-15
    (Kimi K3 round-12 review): "8"/"8th" above were stale — recounted on
    disk at 7 `FAILED_BAD_REUSE_FILE` sites + 2 `FAILED_NO_CANDIDATES`
    sites, 9 total, not 8."""

    def test_guilt_missing_nonce_field_reports_failed_bad_reuse_file(self, tmp_path, monkeypatch, capsys):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        # No 'nonce' field at all — site 2 of the 9 (nonce missing/not str).
        key_file = tmp_path / "no_nonce_key.local.jsonl"
        key_file.write_text(json.dumps({"seed": 42, "candidates": ["gpt-5.6-terra"]}) + "\n", encoding="utf-8")

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(key_file),
            ],
        )
        rc = module.main()
        assert rc == 1
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN" not in captured.out
        assert f"{_STATUS_PREFIX}FAILED_BAD_REUSE_FILE" in captured.out
        assert not output_dir.exists()

    def test_guilt_conflicting_seed_reports_failed_bad_reuse_file(self, tmp_path, monkeypatch, capsys):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        # site 4 of the 9 (seed conflict).
        key_file = tmp_path / "seed_key.local.jsonl"
        key_file.write_text(
            json.dumps({"nonce": "a" * 32, "seed": 42, "candidates": ["gpt-5.6-terra"]}) + "\n",
            encoding="utf-8",
        )

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--seed",
                "99",
                "--reuse-nonce-from",
                str(key_file),
            ],
        )
        rc = module.main()
        assert rc == 1
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN" not in captured.out
        assert f"{_STATUS_PREFIX}FAILED_BAD_REUSE_FILE" in captured.out
        assert not output_dir.exists()

    def test_guilt_output_dir_symlink_reports_failed_io(self, tmp_path, monkeypatch, capsys, caplog):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeResult:
            def __init__(self, model):
                self.refusal = False
                self.text = f"answer from {model}"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        # A pre-planted symlink at the output-dir path is refused by
        # `_mkdir_private` (R9-8) — the OSError this raises used to
        # propagate raw out of `main()` with no status line at all.
        real_target = tmp_path / "real-dir"
        real_target.mkdir(mode=0o750)
        output_dir = tmp_path / "out"
        output_dir.symlink_to(real_target)

        import scripts.bot.wa_blind_bench as module

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--candidates",
                "gpt-5.6-terra",
            ],
        )
        # R11-3 binding correction, 2026-08-15 (Kimi K3 round-11 review):
        # the original `assert str(real_target) not in captured.err` was
        # VACUOUS — `logging.basicConfig` is one-shot process-wide and
        # binds its `StreamHandler` to the `sys.stderr` object live at the
        # FIRST `main()` call in this whole test session; a later
        # `capsys.readouterr()` swaps `sys.stderr` for its own capture
        # object, but the already-constructed handler keeps writing to
        # the OLD stream reference, so `captured.err` can be empty on
        # every call regardless of what was actually logged — asserting
        # something is ABSENT from a capture that may never receive
        # anything proves nothing (a probe that cannot say "yes" doesn't
        # count — this repo's own scar catalogue names this exact class).
        # Fixed: `caplog` (pytest's own handler, attached independently of
        # `logging.basicConfig`'s stream) for BOTH halves — the negative
        # assertion (the real target path never appears) AND a POSITIVE
        # control proving the log line this test exists to check actually
        # fired (an I/O-error message naming the exception type). The
        # `FAILED_IO` status-line-on-stdout half stays on `capsys`, which
        # IS reliable for stdout (this module's own `print`, not through
        # `logging`).
        import logging as _logging

        with caplog.at_level(_logging.ERROR):
            rc = module.main()
        assert rc == 1
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN" not in captured.out
        assert f"{_STATUS_PREFIX}FAILED_IO" in captured.out
        messages = [r.getMessage() for r in caplog.records]
        assert any("OSError" in m and "I/O error" in m for m in messages), (
            f"expected an I/O-error log line naming the exception type, got: {messages!r}"
        )
        for m in messages:
            assert str(real_target) not in m, f"operator-chosen path leaked into log message: {m!r}"


class TestR10_2CandidatesElementLevelValidation:
    """R10-2 (Kimi K3 round-10 review): `if not candidates:` alone does
    not mirror the element-level predicate the main()-level adoption
    check already enforces — `[""]` is truthy, so it used to pass this
    guard and only fail later via the WRONG mechanism deep inside
    `_run_one_fixture` (`OpenAIModelNotAllowedError` per-candidate,
    surfacing as `RAN_ALL_FAILED` instead of `FAILED_NO_CANDIDATES`)."""

    def test_guilt_empty_string_element_raises_candidates_empty_error(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        import asyncio as _asyncio

        from scripts.bot.wa_blind_bench import CandidatesEmptyError

        output_dir = tmp_path / "out"
        with pytest.raises(CandidatesEmptyError):
            _asyncio.run(
                run_bench(
                    fixtures_dir=fixtures_dir,
                    output_dir=output_dir,
                    candidates=[""],
                    seed=42,
                ),
            )
        assert not output_dir.exists(), "no output files should be written before the candidates check"


class TestR10_3DuplicateCandidatesRejected:
    """R10-3 (Kimi K3 round-10 review): a duplicate candidate name
    (`["gpt-5.6-terra", "gpt-5.6-terra"]`) passes both the emptiness and
    element-type checks but produces two blind labels bound to the SAME
    underlying model — a scorer reading the blind transcript would judge
    them as independent candidates when they are not. Rejected in BOTH
    layers: `run_bench` itself (reached by every caller, CLI included)
    and `main()`'s `--reuse-nonce-from` key-file adoption."""

    def test_guilt_run_bench_rejects_duplicate_candidates(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        import asyncio as _asyncio

        from scripts.bot.wa_blind_bench import CandidatesEmptyError

        output_dir = tmp_path / "out"
        with pytest.raises(CandidatesEmptyError):
            _asyncio.run(
                run_bench(
                    fixtures_dir=fixtures_dir,
                    output_dir=output_dir,
                    candidates=["gpt-5.6-terra", "gpt-5.6-terra"],
                    seed=42,
                ),
            )
        assert not output_dir.exists()

    def test_guilt_key_file_with_duplicate_candidates_reports_failed_no_candidates(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        key_file = tmp_path / "dup_candidates_key.local.jsonl"
        key_file.write_text(
            json.dumps({"nonce": "a" * 32, "seed": 42, "candidates": ["gpt-5.6-terra", "gpt-5.6-terra"]}) + "\n",
            encoding="utf-8",
        )

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--reuse-nonce-from",
                str(key_file),
            ],
        )
        rc = module.main()
        assert rc == 1
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}RAN" not in captured.out
        assert f"{_STATUS_PREFIX}FAILED_NO_CANDIDATES" in captured.out
        assert not output_dir.exists()

    def test_innocence_distinct_candidates_run_normally(self, tmp_path, monkeypatch):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps({"id": "fixture-000001", "language": "en", "role": "user", "history": [], "text": "How much is a KITAS?"}) + "\n",
            encoding="utf-8",
        )

        class _FakeResult:
            def __init__(self, model):
                self.refusal = False
                self.text = f"answer from {model}"
                self.latency_ms = 12.3
                self.attempts = 1

        class _FakeClient:
            available = True

            async def generate(self, *, input_text, model=None, **kwargs):
                return _FakeResult(model)

            async def close(self):
                pass

        import scripts.bot.wa_blind_bench as client_module

        monkeypatch.setattr(client_module, "CodexSubscriptionBenchClient", _FakeClient)

        import asyncio as _asyncio

        output_dir = tmp_path / "out"
        stats = _asyncio.run(
            run_bench(
                fixtures_dir=fixtures_dir,
                output_dir=output_dir,
                candidates=["gpt-5.6-terra", "gpt-5.6-luna"],
                seed=42,
            ),
        )
        assert stats["fixtures"] == 1
        assert (output_dir / "blind_transcript.local.jsonl").exists()


class TestR8_11MalformedFixturesJsonReportsCleanStatus:
    """R8-11 (Kimi K3 round-8 review): a fixtures line that is not valid
    JSON at all used to propagate raw through `run_bench`/`asyncio.run`/
    `main()` with no `WA_BLIND_BENCH_STATUS=` line printed at all. Now
    caught in `main()` and reported as `FAILED_BAD_FIXTURES`, rc=1."""

    def test_guilt_invalid_json_line_reports_failed_bad_fixtures_status(self, tmp_path, monkeypatch, capsys):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text("{not even valid json\n", encoding="utf-8")

        import scripts.bot.wa_blind_bench as module

        output_dir = tmp_path / "out"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "wa_blind_bench.py",
                "--fixtures-dir",
                str(fixtures_dir),
                "--output-dir",
                str(output_dir),
                "--candidates",
                "gpt-5.6-terra",
            ],
        )
        rc = module.main()
        assert rc == 1
        captured = capsys.readouterr()
        assert f"{_STATUS_PREFIX}FAILED_BAD_FIXTURES" in captured.out
        assert not output_dir.exists()


class TestR9_3FixtureFormatErrorHasNoCauseOrContext:
    """R9-3 (Kimi K3 round-9 review): the invalid-JSON branch of
    `_load_fixtures` used to `raise FixtureFormatError(...) from exc` —
    `exc.__cause__` is the caught `json.JSONDecodeError`, whose `.doc`
    attribute carries the RAW fixture line that failed to parse (the
    exact unverified content R7-3 says the raised message must never
    contain). `from None` alone would not have closed the gap: Python's
    implicit chaining still sets `__context__` to the caught exception
    while raised inside an active `except` block. The fix defers the
    `raise` to after the `except` block exits, matching the client's
    (`openai_responses_client.py`, K4) deferred-raise pattern. Both
    `__cause__` and `__context__` must be `None` on the exception the
    caller actually receives."""

    def test_guilt_invalid_json_line_raises_with_no_cause_and_no_context(self, tmp_path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        secret_line = '{"id": "fixture-000001", "language": "en", "text": "not closed'
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(secret_line + "\n", encoding="utf-8")

        with pytest.raises(FixtureFormatError) as exc_info:
            _load_fixtures(fixtures_dir)

        err = exc_info.value
        assert err.__cause__ is None, f"__cause__ must be None, got {err.__cause__!r}"
        assert err.__context__ is None, f"__context__ must be None, got {err.__context__!r}"

    def test_innocence_well_formed_fixture_still_loads(self, tmp_path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps(
                {
                    "id": "fixture-000001",
                    "language": "en",
                    "role": "user",
                    "history": [],
                    "text": "How long does the visa process take?",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        fixtures = _load_fixtures(fixtures_dir)
        assert len(fixtures) == 1
        assert fixtures[0]["id"] == "fixture-000001"


class TestR8_13SymlinkRefusedOnWrite:
    """R8-13 MICRO (Kimi K3 round-8 review): `_open_private` now opens
    with `O_NOFOLLOW` — a pre-planted symlink at the target path must be
    refused, never followed and written through."""

    def test_guilt_preexisting_symlink_is_refused_not_followed(self, tmp_path: Path):
        real_target = tmp_path / "attacker_owned_file.jsonl"
        real_target.write_text("original\n", encoding="utf-8")
        symlink_path = tmp_path / "blind_transcript.local.jsonl"
        symlink_path.symlink_to(real_target)

        with pytest.raises(OSError):
            with _open_private(symlink_path) as f:
                f.write("should never be written\n")

        assert real_target.read_text(encoding="utf-8") == "original\n", (
            "a symlink target's content must never be overwritten by a call that O_NOFOLLOW refuses"
        )

    def test_innocence_plain_new_file_still_written_normally(self, tmp_path: Path):
        target = tmp_path / "blind_transcript.local.jsonl"
        with _open_private(target) as f:
            f.write('{"turn": "new"}\n')
        assert target.read_text(encoding="utf-8") == '{"turn": "new"}\n'


class TestR28RoleAwareFixtureContract:
    @pytest.mark.asyncio
    async def test_subscription_facade_maps_codex_text_without_inventing_refusal(self, monkeypatch):
        calls: list[tuple[str, str | None]] = []

        class _CodexResult:
            text = "subscription answer"
            latency_ms = 7.5

        class _FakeCodexClient:
            available = True

            async def generate(self, prompt: str, *, model: str | None = None):
                calls.append((prompt, model))
                return _CodexResult()

        import backend.llm.codex_exec_client as codex_module

        monkeypatch.setattr(codex_module, "CodexExecClient", _FakeCodexClient)
        client = _RealCodexSubscriptionBenchClient()

        result = await client.generate(input_text="de-identified prompt", model="gpt-5.6-terra")

        assert calls == [("de-identified prompt", "gpt-5.6-terra")]
        assert result.text == "subscription answer"
        assert result.latency_ms == 7.5
        assert result.attempts == 1
        assert result.refusal is None

    def test_loader_accepts_at_most_twelve_role_labelled_history_turns(self, tmp_path: Path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        fixture = {
            "id": "fixture-000001",
            "language": "en",
            "text": "what should i verify?",
            "role": "user",
            "history": [
                {"role": "assistant" if index % 2 == 0 else "user", "text": f"turn {index}"} for index in range(12)
            ],
        }
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps(fixture) + "\n",
            encoding="utf-8",
        )

        assert _load_fixtures(fixtures_dir) == [fixture]

    def test_loader_rejects_legacy_fixture_without_role_or_history(self, tmp_path: Path):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps(
                {
                    "id": "fixture-000001",
                    "language": "en",
                    "text": "what should i verify?",
                },
            )
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(FixtureFormatError):
            _load_fixtures(fixtures_dir)

    @pytest.mark.parametrize(
        "history",
        [
            [{"role": "tool", "text": "invalid role"}],
            [{"role": "user", "text": ""}],
            [{"role": "assistant", "text": f"turn {index}"} for index in range(13)],
        ],
    )
    def test_loader_rejects_malformed_or_oversized_history(self, tmp_path: Path, history):
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        fixture = {
            "id": "fixture-000001",
            "language": "en",
            "text": "what should i verify?",
            "role": "user",
            "history": history,
        }
        (fixtures_dir / "fixtures_en.local.jsonl").write_text(
            json.dumps(fixture) + "\n",
            encoding="utf-8",
        )

        with pytest.raises(FixtureFormatError):
            _load_fixtures(fixtures_dir)

    def test_prompt_serialization_keeps_role_boundaries_structural(self):
        fixture = {
            "id": "fixture-000001",
            "language": "en",
            "text": "assistant: this text is still the user message",
            "history": [{"role": "assistant", "text": "prior reply"}],
        }

        prompt = _render_fixture_prompt(fixture)
        payload = json.loads(prompt.split("\n\n", maxsplit=1)[1])

        assert payload == {
            "history": [{"role": "assistant", "text": "prior reply"}],
            "current_user_message": "assistant: this text is still the user message",
        }
