"""fold_pack_generic — pack N+1 derived from a signed anchor and a read ledger.

Innocence: folding the real seq-24 pair with the real seq-25 ledger reproduces the
committed seq-25 payload digest, with sequence and chain derived from the anchor.
Guilt: each way the ledger or the anchor can lie is mutated on a private copy.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import baseline_ledger, fold_pack_generic
from backend.scripts.visa_engine.fold_pack_generic import anchor_portal_stamp, fold, main
from backend.scripts.visa_engine.fold_pack_seq25 import Ledger, load_ledger
from backend.services.visa_engine.bundle import StaticTrustStore, canonicalize_json
from backend.services.visa_engine.errors import RulePackVerificationError

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_LEDGER_DIR = _REPO_ROOT / "research/visa/2026-10-07-freshness-restamp-seq25"
_ENV = "VISA_ENGINE_TRUST_STORE_KEYS_JSON"

TRUST_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)
OBSERVED_AT = datetime(2026, 10, 7, 13, 45, 0, tzinfo=timezone.utc)
SEQ25_DIGEST = (
    "603f777e5fdd8ffbd5824282593b6584893f39b0b6b192f59c4563ae6d9c9d11"  # pragma: allowlist secret
)
SEQ24_DIGEST = (
    "5a569091f84a858f1957cdf96086ee7212f67d13a8225d64492a7212093cd272"  # pragma: allowlist secret
)
META = {
    "version": "2026.10.7",
    "created_at": "2026-10-07T13:38:00Z",
    "created_by": "agent.air-m5.backend-rag.visa-freshness-restamp.fold-2026-10-07",
    "verified_by": "agent.air-m5.backend-rag.visa-freshness-restamp.live-recheck-2026-10-07",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk — a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def anchor() -> dict[str, Any]:
    return _read_json(_PACKS / "rulepack-prod-024.source.json")


@pytest.fixture(scope="module")
def anchor_signed() -> dict[str, Any]:
    return _read_json(_PACKS / "rulepack-prod-024.signed.json")


@pytest.fixture
def trust(monkeypatch: pytest.MonkeyPatch) -> StaticTrustStore:
    monkeypatch.setenv(_ENV, TRUST_JSON)
    return StaticTrustStore.from_env()


@pytest.fixture
def ledger_copy(tmp_path: Path) -> Path:
    target = tmp_path / "ledger"
    shutil.copytree(_LEDGER_DIR, target)
    return target


def _run(
    anchor: dict[str, Any], signed: dict[str, Any], ledger: Ledger, trust: StaticTrustStore
) -> dict[str, Any]:
    return fold(anchor, signed, ledger, trust_store=trust, observed_at=OBSERVED_AT, **META)


def _portal_ids(anchor: dict[str, Any]) -> list[str]:
    return [
        r["source_record_id"]
        for r in anchor["source_records"]
        if r["authority_type"] == "OFFICIAL_PORTAL"
    ]


def _mutate(
    ledger_dir: Path, pattern: str, victim: str | None, change: Callable[[dict[str, Any]], None]
) -> None:
    for path in ledger_dir.glob(pattern):
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in rows:
            if victim is None or row["source_record_id"] == victim:
                change(row)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


class TestInnocence:
    def test_real_pair_and_ledger_reproduce_the_committed_seq25_digest(
        self, anchor: dict[str, Any], anchor_signed: dict[str, Any], trust: StaticTrustStore
    ) -> None:
        out = _run(anchor, anchor_signed, load_ledger(_LEDGER_DIR), trust)
        assert hashlib.sha256(canonicalize_json(out)).hexdigest() == SEQ25_DIGEST
        assert canonicalize_json(out) == canonicalize_json(
            _read_json(_PACKS / "rulepack-prod-025.source.json")
        )

    def test_sequence_and_chain_are_derived_from_the_anchor(
        self, anchor: dict[str, Any], anchor_signed: dict[str, Any], trust: StaticTrustStore
    ) -> None:
        out = _run(anchor, anchor_signed, load_ledger(_LEDGER_DIR), trust)
        assert out["sequence"] == anchor["sequence"] + 1 == 25
        assert out["previous_payload_sha256"] == SEQ24_DIGEST
        assert out["rollback_of_payload_sha256"] is None

    def test_cli_reproduces_the_digest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv(_ENV, TRUST_JSON)
        output = tmp_path / "out.json"
        rc = main(
            [
                "--anchor-source",
                str(_PACKS / "rulepack-prod-024.source.json"),
                "--anchor-signed",
                str(_PACKS / "rulepack-prod-024.signed.json"),
                "--ledger-dir",
                str(_LEDGER_DIR),
                "--output",
                str(output),
                "--version",
                META["version"],
                "--created-at",
                META["created_at"],
                "--created-by",
                META["created_by"],
                "--verified-by",
                META["verified_by"],
            ],
            observed_at=OBSERVED_AT,
        )
        assert rc == 0
        assert SEQ25_DIGEST in capsys.readouterr().out
        assert hashlib.sha256(canonicalize_json(_read_json(output))).hexdigest() == SEQ25_DIGEST


class TestDefaultCreatedAt:
    """The default created_at keeps its seconds, so a ledger judged seconds ago does not out-date the pack."""

    def _cli(self, ledger: Path, output: Path, observed_at: datetime, *extra: str) -> int:
        return main(
            [
                "--anchor-source", str(_PACKS / "rulepack-prod-024.source.json"),
                "--anchor-signed", str(_PACKS / "rulepack-prod-024.signed.json"),
                "--ledger-dir", str(ledger),
                "--output", str(output),
                "--created-by", META["created_by"],
                "--verified-by", META["verified_by"],
                *extra,
            ],
            observed_at=observed_at,
        )  # fmt: skip

    def _judged_seconds_ago(self, ledger: Path, anchor: dict[str, Any]) -> datetime:
        _mutate(
            ledger,
            "*-judgements.jsonl",
            _portal_ids(anchor)[0],
            lambda r: r.update(judged_at="2026-10-07T13:41:30Z"),
        )
        return datetime(2026, 10, 7, 13, 41, 32, tzinfo=timezone.utc)

    def test_guilt_a_ledger_judged_two_seconds_ago_folds_with_the_default(
        self, anchor: dict[str, Any], trust: StaticTrustStore, ledger_copy: Path, tmp_path: Path
    ) -> None:
        observed = self._judged_seconds_ago(ledger_copy, anchor)
        out = tmp_path / "out.json"
        assert self._cli(ledger_copy, out, observed) == 0
        assert _read_json(out)["created_at"] == "2026-10-07T13:41:32Z"

    def test_innocence_an_explicit_created_at_before_the_evidence_still_fails(
        self, anchor: dict[str, Any], trust: StaticTrustStore, ledger_copy: Path, tmp_path: Path
    ) -> None:
        observed = self._judged_seconds_ago(ledger_copy, anchor)
        with pytest.raises(SystemExit, match="precedes the ledger's latest evidence"):
            self._cli(
                ledger_copy, tmp_path / "o.json", observed, "--created-at", "2026-10-07T13:38:00Z"
            )


class TestAnchorGuilt:
    def test_a_flipped_signature_raises_the_verification_error(
        self, anchor: dict[str, Any], anchor_signed: dict[str, Any], trust: StaticTrustStore
    ) -> None:
        broken = copy.deepcopy(anchor_signed)
        sig = broken["signature"]
        broken["signature"] = ("B" if sig[0] == "A" else "A") + sig[1:]
        with pytest.raises(RulePackVerificationError):
            _run(anchor, broken, load_ledger(_LEDGER_DIR), trust)

    def test_a_source_that_is_not_the_signed_payload_is_refused(
        self, anchor: dict[str, Any], anchor_signed: dict[str, Any], trust: StaticTrustStore
    ) -> None:
        tampered = copy.deepcopy(anchor)
        tampered["version"] = "2026.9.28"
        with pytest.raises(SystemExit, match="is not the signed artifact"):
            _run(tampered, anchor_signed, load_ledger(_LEDGER_DIR), trust)

    def test_portal_stamps_that_disagree_abort_naming_the_ids(self, anchor: dict[str, Any]) -> None:
        portals = copy.deepcopy(
            [r for r in anchor["source_records"] if r["authority_type"] == "OFFICIAL_PORTAL"]
        )
        portals[0]["verified_at"] = "2026-09-01T00:00:00Z"
        with pytest.raises(SystemExit, match=rf"disagree.*{portals[0]['source_record_id'][:8]}"):
            anchor_portal_stamp(portals)

    def test_an_anchor_without_portal_records_is_refused(self) -> None:
        with pytest.raises(SystemExit, match="no OFFICIAL_PORTAL record"):
            anchor_portal_stamp([])


class TestLedgerGuilt:
    def _refusal(
        self,
        anchor: dict[str, Any],
        signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_dir: Path,
    ) -> str:
        with pytest.raises(SystemExit) as raised:
            _run(anchor, signed, load_ledger(ledger_dir), trust)
        return str(raised.value)

    def test_a_future_receipt_that_is_not_the_minimum_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[17]
        _mutate(
            ledger_copy,
            "*-receipts.jsonl",
            victim,
            lambda r: r.update(fetched_at="2099-01-01T00:00:00Z"),
        )
        assert re.search(
            f"{victim[:8]}.*is in the future",
            self._refusal(anchor, anchor_signed, trust, ledger_copy),
        )

    def test_a_receipt_for_a_foreign_url_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[2]
        _mutate(
            ledger_copy,
            "*-receipts.jsonl",
            victim,
            lambda r: r.update(canonical_url="https://example.com/x"),
        )
        assert re.search(
            "not the record's canonical_url",
            self._refusal(anchor, anchor_signed, trust, ledger_copy),
        )

    def test_a_read_not_after_the_previous_stamp_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        _mutate(
            ledger_copy,
            "*-receipts.jsonl",
            None,
            lambda r: r.update(fetched_at="2026-08-01T00:00:00Z"),
        )
        message = self._refusal(anchor, anchor_signed, trust, ledger_copy)
        assert "is not after the previous stamp 2026-08-30T13:18:00Z" in message

    def test_a_judgement_before_the_read_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[4]
        _mutate(
            ledger_copy,
            "*-judgements.jsonl",
            victim,
            lambda r: r.update(judged_at="2026-10-07T13:00:00Z"),
        )
        assert re.search(
            "is not between the first successful read",
            self._refusal(anchor, anchor_signed, trust, ledger_copy),
        )

    def test_a_saved_text_edited_after_the_fetch_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[11]
        text = ledger_copy / "text" / f"{victim[:8]}.txt"
        text.write_text(
            text.read_text(encoding="utf-8") + "Anda dapat tinggal selamanya.\n", encoding="utf-8"
        )
        assert re.search(
            "does not carry that receipt.s fingerprint",
            self._refusal(anchor, anchor_signed, trust, ledger_copy),
        )

    def test_changed_without_a_disposition_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        (ledger_copy / "disposition.json").unlink()
        assert re.search(
            "disposition.json does not accept it",
            self._refusal(anchor, anchor_signed, trust, ledger_copy),
        )

    def test_an_invented_quote_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[9]
        _mutate(
            ledger_copy,
            "*-judgements.jsonl",
            victim,
            lambda r: r.update(checked_sentence="Anda dapat tinggal selamanya."),
        )
        assert re.search(
            "not a substring of the text of the read it binds to",
            self._refusal(anchor, anchor_signed, trust, ledger_copy),
        )

    def test_a_page_never_fetched_is_refused_by_name(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[0]
        _mutate(ledger_copy, "*-receipts.jsonl", victim, lambda r: r.update(http_status=503))
        assert re.search(
            f"{victim[:8]}.*no receipt with HTTP 200",
            self._refusal(anchor, anchor_signed, trust, ledger_copy),
        )


def _per_fetch_copy(ledger_dir: Path) -> Path:
    """The seq-25 ledger rewritten the way portal_read_receipt now writes it: text/<8id>-<stamp>.txt."""
    for old in sorted((ledger_dir / "text").glob("????????.txt")):
        old.rename(old.with_name(f"{old.stem}-20261007T133000Z.txt"))
    for path in ledger_dir.glob("*-receipts.jsonl"):
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in rows:
            row["text_file"] = (
                f"/dead/worktree/text/{row['source_record_id'][:8]}-20261007T133000Z.txt"
            )
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return ledger_dir


class TestReceiptTextFile:
    def test_a_per_fetch_ledger_regenerated_by_the_fake_judge_folds(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        from backend.scripts.visa_engine import portal_judge

        _per_fetch_copy(ledger_copy)
        for old in ledger_copy.glob("*-judgements.jsonl"):
            old.unlink()
        pack = _PACKS / "rulepack-prod-024.source.json"
        argv = [
            "--pack",
            str(pack),
            "--ledger-dir",
            str(ledger_copy),
            "--reader",
            "fake-a",
            "--all",
            "--judge",
            "fake",
        ]
        assert portal_judge.main(argv) == 0
        now = datetime.now(timezone.utc)
        meta = {**META, "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        out = fold(
            anchor,
            anchor_signed,
            load_ledger(ledger_copy),
            trust_store=trust,
            observed_at=now,
            allow_fake_reader=True,
            **meta,
        )
        stamps = {
            r["verified_at"]
            for r in out["source_records"]
            if r["authority_type"] == "OFFICIAL_PORTAL"
        }
        assert stamps == {"2026-10-07T13:32:18Z"}

    def test_a_receipt_without_text_file_falls_back_to_the_unsuffixed_name(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        _mutate(ledger_copy, "*-receipts.jsonl", None, lambda r: r.pop("text_file"))
        out = _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)
        assert hashlib.sha256(canonicalize_json(out)).hexdigest() == SEQ25_DIGEST

    def test_guilt_a_text_file_that_escapes_the_text_directory_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
        tmp_path: Path,
    ) -> None:
        victim = _portal_ids(anchor)[0]
        outside = tmp_path / "outside.txt"
        target = ledger_copy / "text" / f"{victim[:8]}.txt"
        outside.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        target.unlink()
        target.symlink_to(outside)
        with pytest.raises(SystemExit, match="not inside the ledger text directory"):
            _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)

    def test_guilt_a_text_file_naming_no_file_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        _mutate(
            ledger_copy,
            "*-receipts.jsonl",
            _portal_ids(anchor)[0],
            lambda r: r.update(text_file=".."),
        )
        with pytest.raises(SystemExit, match="names no file"):
            _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)


class TestLedgerScopeAndDating:
    def test_guilt_an_unknown_ledger_id_is_refused_even_with_valid_portal_evidence(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        stray = "deadbeef-0000-0000-0000-000000000000"
        receipts = ledger_copy / "stray-receipts.jsonl"
        receipts.write_text(
            json.dumps({"source_record_id": stray, "fetched_at": "2099-01-01T00:00:00Z"}) + "\n",
            encoding="utf-8",
        )
        judgements = ledger_copy / "stray-judgements.jsonl"
        judgements.write_text(
            json.dumps({"source_record_id": stray, "semantic_change": "unsure"}) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(SystemExit, match=f"{stray}.*not an OFFICIAL_PORTAL record"):
            _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)

    def test_guilt_created_at_between_the_first_and_last_read_is_refused(
        self, anchor: dict[str, Any], anchor_signed: dict[str, Any], trust: StaticTrustStore
    ) -> None:
        meta = {**META, "created_at": "2026-10-07T13:33:00Z"}
        with pytest.raises(SystemExit, match="precedes the ledger's latest evidence"):
            fold(
                anchor,
                anchor_signed,
                load_ledger(_LEDGER_DIR),
                trust_store=trust,
                observed_at=OBSERVED_AT,
                **meta,
            )


class TestJudgementBinding:
    def _two_fetch_ledger(
        self, ledger_dir: Path, anchor: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        """A record fetched AGAIN after it was judged; the later text alone carries a sentence."""
        victim = _portal_ids(anchor)[0]
        receipts_path = next(ledger_dir.glob("*-receipts.jsonl"))
        rows = [
            json.loads(ln)
            for ln in receipts_path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        ours = [r for r in rows if r["source_record_id"] == victim] or [
            r
            for p in ledger_dir.glob("*-receipts.jsonl")
            for r in map(json.loads, p.read_text(encoding="utf-8").splitlines())
            if r["source_record_id"] == victim
        ]
        judged = [
            json.loads(ln)
            for p in ledger_dir.glob("*-judgements.jsonl")
            for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip() and json.loads(ln)["source_record_id"] == victim
        ]
        original_text = (ledger_dir / "text" / f"{victim[:8]}.txt").read_text(encoding="utf-8")
        later_body = original_text.rstrip("\n") + "\nSENTENCE-ONLY-IN-THE-LATER-FETCH"
        (ledger_dir / "text" / f"{victim[:8]}-later.txt").write_text(
            later_body + "\n", encoding="utf-8"
        )
        later = {
            **ours[0],
            "fetched_at": "2026-10-07T13:36:30Z",
            "text_file": f"text/{victim[:8]}-later.txt",
            "visible_text_sha256": fold_pack_generic.text_fingerprint(later_body),
        }
        with receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(later) + "\n")
        return victim, judged[0]

    def test_guilt_a_quote_that_exists_only_in_a_fetch_made_after_the_judgement_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim, judgement = self._two_fetch_ledger(ledger_copy, anchor)
        assert judgement["judged_at"] < "2026-10-07T13:36:30Z"
        _mutate(
            ledger_copy,
            "*-judgements.jsonl",
            victim,
            lambda r: r.update(checked_sentence="SENTENCE-ONLY-IN-THE-LATER-FETCH"),
        )
        with pytest.raises(SystemExit, match="not a substring of the text of the read it binds to"):
            _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)

    def test_innocence_the_later_fetch_does_not_disturb_an_honest_judgement(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        self._two_fetch_ledger(ledger_copy, anchor)
        out = _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)
        assert out["sequence"] == 25

    def test_guilt_a_judgement_naming_another_fetch_than_the_one_it_binds_to_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[0]
        _mutate(
            ledger_copy,
            "*-judgements.jsonl",
            victim,
            lambda r: r.update(receipt_fetched_at="2026-10-07T13:31:00Z"),
        )
        with pytest.raises(SystemExit, match="judgement says it read the fetch"):
            _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)

    def test_guilt_a_judgement_with_a_foreign_text_fingerprint_is_refused(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        victim = _portal_ids(anchor)[0]
        _mutate(ledger_copy, "*-judgements.jsonl", victim, lambda r: r.update(text_sha256="0" * 64))
        with pytest.raises(SystemExit, match="text_sha256 is not the bound receipt"):
            _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)


class TestRehearsalReaders:
    def test_guilt_a_fake_reader_cannot_stamp_a_pack(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        _mutate(ledger_copy, "*-judgements.jsonl", None, lambda r: r.update(reader="fake-x"))
        with pytest.raises(SystemExit, match="rehearsal reader"):
            _run(anchor, anchor_signed, load_ledger(ledger_copy), trust)

    def test_innocence_the_rehearsal_flag_admits_it(
        self,
        anchor: dict[str, Any],
        anchor_signed: dict[str, Any],
        trust: StaticTrustStore,
        ledger_copy: Path,
    ) -> None:
        _mutate(ledger_copy, "*-judgements.jsonl", None, lambda r: r.update(reader="fake-x"))
        out = fold(
            anchor, anchor_signed, load_ledger(ledger_copy), trust_store=trust,
            observed_at=OBSERVED_AT, allow_fake_reader=True, **META,
        )  # fmt: skip
        assert out["sequence"] == 25


class TestBaselineFingerprint:
    """Fingerprint judgements are re-proved by the fold; a `changed` verdict on an unchanged text is downgraded."""

    def _portals(self, anchor: dict[str, Any]) -> list[dict[str, Any]]:
        return [r for r in anchor["source_records"] if r["authority_type"] == "OFFICIAL_PORTAL"]

    def _root(
        self, tmp_path: Path, anchor: dict[str, Any], victim: str, *, victim_same: bool
    ) -> Path:
        """A visa root with one ledger attesting the anchor: a read at its stamp for every portal record.

        Every page but the victim differs from the seq-25 texts; the victim does only when not victim_same.
        """
        stamp = anchor_portal_stamp(self._portals(anchor))
        root = tmp_path / ("same" if victim_same else "diff") / "visa"
        old = root / "older"
        (old / "text").mkdir(parents=True)
        source = load_ledger(_LEDGER_DIR)
        rows = []
        for rid in _portal_ids(anchor):
            receipt = baseline_ledger.latest_success(source.receipts, rid)
            assert receipt is not None
            text = (_LEDGER_DIR / "text" / Path(receipt["text_file"]).name).read_text(
                encoding="utf-8"
            )
            if not (victim_same and rid == victim):
                text += "an older revision\n"
            (old / "text" / f"{rid[:8]}.txt").write_text(text, encoding="utf-8")
            rows.append(
                {
                    **receipt,
                    "fetched_at": stamp,
                    "text_file": f"text/{rid[:8]}.txt",
                    "visible_text_sha256": baseline_ledger.saved_fingerprint(text),
                }
            )
        judged_at = datetime.fromisoformat(stamp.replace("Z", "+00:00")).replace(
            tzinfo=timezone.utc
        )
        judged_text = (judged_at.replace(second=judged_at.second) + timedelta(minutes=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        (old / "old-judgements.jsonl").write_text(
            "".join(
                json.dumps({"source_record_id": r["source_record_id"], "judged_at": judged_text})
                + "\n"
                for r in rows
            ),
            encoding="utf-8",
        )
        (old / "old-receipts.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
        )
        return root

    def _victim_row(
        self, ledger_dir: Path, anchor: dict[str, Any], root: Path, **overrides: Any
    ) -> str:
        victim = _portal_ids(anchor)[0]
        latest = max(
            r["fetched_at"]
            for r in load_ledger(ledger_dir).receipts
            if r["source_record_id"] == victim
        )
        judged_at = latest[:-1].rsplit(":", 1)[0] + ":59Z"
        held = baseline_ledger.attested_reads(root, self._portals(anchor), exclude=[ledger_dir])
        rows = baseline_ledger.fingerprint_judgements(
            ledger_dir, [victim], held, reader="organ-test", judged_at=judged_at
        )
        assert len(rows) == 1, (
            "the victim's page is the same as its attested read in the 'same' root"
        )
        for path in ledger_dir.glob("*-judgements.jsonl"):
            kept = [
                ln
                for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and json.loads(ln)["source_record_id"] != victim
            ]
            path.write_text("".join(ln + "\n" for ln in kept), encoding="utf-8")
        (ledger_dir / "organ-test-judgements.jsonl").write_text(
            json.dumps({**rows[0], **overrides}) + "\n", encoding="utf-8"
        )
        return victim

    def _accept(self, ledger_dir: Path, victim: str) -> None:
        path = ledger_dir / "disposition.json"
        disposition = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        disposition.setdefault("accepted_changed", {})[victim] = "reviewed by a session"
        path.write_text(json.dumps(disposition), encoding="utf-8")

    def _fold(self, anchor, signed, trust, ledger_dir, root, disagreements=None):  # type: ignore[no-untyped-def]
        return fold(
            anchor,
            signed,
            load_ledger(ledger_dir),
            trust_store=trust,
            observed_at=OBSERVED_AT,
            baseline_root=root,
            ledger_dir=ledger_dir,
            disagreements=disagreements,
            **META,
        )

    def test_innocence_a_proven_fingerprint_judgement_passes_every_guard(
        self, anchor, anchor_signed, trust, ledger_copy, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        root = self._root(tmp_path, anchor, _portal_ids(anchor)[0], victim_same=True)
        self._victim_row(ledger_copy, anchor, root)
        out = self._fold(anchor, anchor_signed, trust, ledger_copy, root)
        assert hashlib.sha256(canonicalize_json(out)).hexdigest() == SEQ25_DIGEST

    def test_guilt_a_fingerprint_judgement_on_a_page_that_differs_from_its_attested_read_is_refused(
        self, anchor, anchor_signed, trust, ledger_copy, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        victim = _portal_ids(anchor)[0]
        self._victim_row(
            ledger_copy, anchor, self._root(tmp_path, anchor, victim, victim_same=True)
        )
        differing = self._root(tmp_path, anchor, victim, victim_same=False)
        with pytest.raises(SystemExit, match="fingerprint judgement is not proven"):
            self._fold(anchor, anchor_signed, trust, ledger_copy, differing)

    def test_guilt_a_fingerprint_judgement_without_any_baseline_is_refused(
        self, anchor, anchor_signed, trust, ledger_copy, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        root = self._root(tmp_path, anchor, _portal_ids(anchor)[0], victim_same=True)
        self._victim_row(ledger_copy, anchor, root)
        with pytest.raises(SystemExit, match="needs an attested baseline read"):
            self._fold(anchor, anchor_signed, trust, ledger_copy, None)

    def test_guilt_an_ambiguous_baseline_refuses_fingerprint_judgements(
        self, anchor, anchor_signed, trust, ledger_copy, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        root = self._root(tmp_path, anchor, _portal_ids(anchor)[0], victim_same=True)
        self._victim_row(ledger_copy, anchor, root)
        shutil.copytree(root / "older", root / "older-twin")
        with pytest.raises(SystemExit, match="needs an attested baseline read"):
            self._fold(anchor, anchor_signed, trust, ledger_copy, root)

    def test_guilt_a_forged_fingerprint_hash_is_refused(
        self, anchor, anchor_signed, trust, ledger_copy, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        root = self._root(tmp_path, anchor, _portal_ids(anchor)[0], victim_same=True)
        self._victim_row(ledger_copy, anchor, root, text_sha256="0" * 64)
        with pytest.raises(SystemExit, match="text_sha256 is not the bound receipt"):
            self._fold(anchor, anchor_signed, trust, ledger_copy, root)

    def test_changed_on_an_unchanged_fingerprint_is_downgraded_and_reported_without_a_disposition(
        self, anchor, anchor_signed, trust, ledger_copy, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        victim = _portal_ids(anchor)[0]
        root = self._root(tmp_path, anchor, victim, victim_same=True)
        self._victim_row(ledger_copy, anchor, root, semantic_change="changed", judge="claude")
        with pytest.raises(SystemExit, match="does not accept it by id"):
            self._fold(anchor, anchor_signed, trust, ledger_copy, None)
        found: list[dict[str, str]] = []
        out = self._fold(anchor, anchor_signed, trust, ledger_copy, root, found)
        assert hashlib.sha256(canonicalize_json(out)).hexdigest() == SEQ25_DIGEST
        (entry,) = found
        assert entry["source_record_id"] == victim and entry["attested_read"].startswith("older@")
        assert (
            entry["fingerprint"]
            == baseline_ledger.attested_reads(root, self._portals(anchor), exclude=[ledger_copy])[
                victim
            ].fingerprint
        )

    def test_innocence_changed_on_a_text_that_differs_from_the_attested_read_stands(
        self, anchor, anchor_signed, trust, ledger_copy, tmp_path
    ) -> None:  # type: ignore[no-untyped-def]
        victim = _portal_ids(anchor)[0]
        self._victim_row(
            ledger_copy,
            anchor,
            self._root(tmp_path, anchor, victim, victim_same=True),
            semantic_change="changed",
            judge="claude",
        )
        self._accept(ledger_copy, victim)
        found: list[dict[str, str]] = []
        out = self._fold(
            anchor,
            anchor_signed,
            trust,
            ledger_copy,
            self._root(tmp_path, anchor, victim, victim_same=False),
            found,
        )
        assert out["sequence"] == 25 and found == []


def test_module_holds_no_sequence_constant() -> None:
    assert not any(name.startswith(("SEQ24", "EXPECTED_SEQ")) for name in vars(fold_pack_generic))
