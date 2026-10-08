"""portal_judge.py — the judgement half of the re-attestation, with the judge injected.

No network, no real ``claude`` call. Innocence: a valid answer lands with the full seq-25
line shape and the fold accepts a ledger whose judgements this tool regenerated. Guilt: a
fabricated quote, broken JSON and a record without a 200 receipt each halt the organ.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.scripts.visa_engine import fold_pack_seq25 as fold
from backend.scripts.visa_engine import portal_judge as pj

REPO = Path(__file__).resolve().parents[6]
SEQ25_LEDGER = REPO / "research/visa/2026-10-07-freshness-restamp-seq25"
SEQ25_SOURCE = (
    Path(__file__).resolve().parents[3] / "services/visa_engine/contracts/packs/rulepack-prod-025.source.json"
)
LINE_KEYS = {
    "source_record_id", "reader", "judged_at", "http_status", "key_phrase_found",
    "checked_sentence", "page_states", "pack_assumes", "semantic_change", "notes",
}  # fmt: skip
RID = "570f2bc4-5120-561f-90ba-58fcd9507514"
TEXT = "E31B Visa Keluarga\nAnda dapat memilih untuk tinggal\n selama 1 tahun atau 2 tahun.\n"


def _pack() -> dict:
    return {
        "payload": {
            "source_records": [
                {
                    "source_record_id": RID,
                    "source_key": "k-e31b",
                    "canonical_url": "https://x/E31B",
                    "authority_type": "OFFICIAL_PORTAL",
                    "title": "E31B",
                },
                {
                    "source_record_id": "ffffffff-0000-0000-0000-000000000000",
                    "source_key": "k-other",
                    "canonical_url": "https://x/O",
                    "authority_type": "OFFICIAL_PORTAL",
                    "title": "OTH",
                },
                {
                    "source_record_id": "aaaaaaaa-0000-0000-0000-000000000000",
                    "source_key": "k-law",
                    "canonical_url": "https://x/L",
                    "authority_type": "LAW",
                    "title": "L",
                },
            ],
            "products": [
                {
                    "product_code": "E31B",
                    "source_refs": [RID],
                    "stay_policy": {"kind": "FIXED_DAYS"},
                }
            ],
            "rules": [{"rule_id": "r1", "source_refs": [RID], "stage": "S", "when": {}, "effect": {}}],
        }
    }


def _ledger(tmp_path: Path, *, with_receipt: bool = True) -> tuple[Path, Path]:
    ledger = tmp_path / "ledger"
    (ledger / "text").mkdir(parents=True)
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_pack()), encoding="utf-8")
    if with_receipt:
        old = ledger / "text" / "570f2bc4-20261007T010000Z.txt"
        new = ledger / "text" / "570f2bc4-20261008T010000Z.txt"
        old.write_text("OLD PAGE\n", encoding="utf-8")
        new.write_text(TEXT, encoding="utf-8")
        rows = [
            {
                "source_record_id": RID,
                "http_status": 200,
                "key_phrase_found": True,
                "fetched_at": "2026-10-07T01:00:00Z",
                "text_file": str(old),
            },
            {
                "source_record_id": RID,
                "http_status": 200,
                "key_phrase_found": True,
                "fetched_at": "2026-10-08T01:00:00Z",
                "text_file": "/gone/570f2bc4-20261008T010000Z.txt",
            },
            {
                "source_record_id": RID,
                "http_status": 503,
                "key_phrase_found": False,
                "fetched_at": "2026-10-09T01:00:00Z",
                "text_file": str(old),
            },
        ]
        (ledger / "r-receipts.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return pack, ledger


def _answer(**kw: object) -> str:
    base = {
        "verdict": "none",
        "checked_sentence": "Anda dapat memilih untuk tinggal selama 1 tahun atau 2 tahun.",
        "page_states": "1 or 2 years",
        "pack_assumes": "x",
        "reason": "agrees",
    }
    return json.dumps({**base, **kw})


def _run(tmp_path: Path, judge, ids: str = RID[:8], **ledger_kw: bool) -> tuple[int, list[dict]]:
    pack, ledger = _ledger(tmp_path, **ledger_kw)
    code = pj.main(
        ["--pack", str(pack), "--ledger-dir", str(ledger), "--reader", "judge-a", "--ids", ids],
        judge_fn=judge,
    )
    out = ledger / "judge-a-judgements.jsonl"
    return code, [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines()] if out.exists() else []


class TestInnocence:
    def test_a_valid_answer_is_written_with_the_full_line_shape_from_the_latest_success(self, tmp_path: Path) -> None:
        seen: list[str] = []

        def judge(prompt: str) -> str:
            seen.append(prompt)
            return _answer()

        code, lines = _run(tmp_path, judge)
        assert code == 0 and len(lines) == 1
        line = lines[0]
        assert set(line) == LINE_KEYS
        assert line["semantic_change"] == "none" and line["http_status"] == 200 and line["key_phrase_found"] is True
        assert line["checked_sentence"] == "Anda dapat memilih untuk tinggal\n selama 1 tahun atau 2 tahun."
        assert line["pack_assumes"]["products"][0]["product_code"] == "E31B"
        assert line["judged_at"].endswith("Z")
        assert "selama 1 tahun" in seen[0] and "OLD PAGE" not in seen[0] and "k-e31b" in seen[0]

    def test_the_fold_accepts_seq25_judgements_regenerated_by_the_fake_judge(self, tmp_path: Path) -> None:
        ledger = tmp_path / "seq25"
        shutil.copytree(SEQ25_LEDGER, ledger)
        for old in ledger.glob("*-judgements.jsonl"):
            old.unlink()
        code = pj.main(
            [
                "--pack",
                str(SEQ25_SOURCE),
                "--ledger-dir",
                str(ledger),
                "--reader",
                "judge-f",
                "--all",
                "--judge",
                "fake",
            ]
        )
        assert code == 0
        records = pj.portal_records(json.loads(SEQ25_SOURCE.read_text(encoding="utf-8")))
        stamp = fold.attestation_instant(fold.load_ledger(ledger), records, now=datetime.now(timezone.utc))
        assert stamp == "2026-10-07T13:32:18Z"


class TestGuilt:
    def test_a_sentence_not_in_the_text_is_forced_unsure_and_halts(self, tmp_path: Path) -> None:
        code, lines = _run(tmp_path, lambda _p: _answer(checked_sentence="Visa seumur hidup tersedia."))
        assert code == 1
        assert lines[0]["semantic_change"] == "unsure" and lines[0]["notes"] == "quote_not_in_text"

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "not json at all",
            '{"verdict": "maybe", "checked_sentence": "E31B Visa Keluarga"}',
            "[1]",
        ],
    )
    def test_invalid_or_empty_output_is_unsure(self, tmp_path: Path, raw: str) -> None:
        code, lines = _run(tmp_path, lambda _p: raw)
        assert code == 1
        assert lines[0]["semantic_change"] == "unsure" and lines[0]["notes"] == "judge_output_invalid"

    def test_a_record_without_a_200_receipt_halts_and_is_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, lines = _run(tmp_path, lambda _p: _answer(), ids="ffffffff")
        assert code == 1 and lines == []
        assert "ffffffff" in capsys.readouterr().out

    def test_an_unsure_verdict_from_the_judge_halts(self, tmp_path: Path) -> None:
        code, lines = _run(tmp_path, lambda _p: _answer(verdict="unsure"))
        assert code == 1 and lines[0]["semantic_change"] == "unsure"

    def test_the_cascade_argv_carries_no_prompt_and_stays_claude_only(self) -> None:
        argv = pj.cascade_argv("sonnet")
        assert argv[1:] == ["--stdin", "--claude-only", "--model", "sonnet"]
